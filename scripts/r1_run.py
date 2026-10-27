"""R1 runner (NOT LOCKED). Per project, per arm (environments and memories reset between arms):
  build   the arm's build agent on docs + visible ticks 1-8 (r1_agent); scoped evidence + outcome label; the protected
          evaluator scores the submitted bundle (checkpoints 4 / 8 / 12, crash sweeps, rollback drill; r1_evaluator)
  ops     END-TO-END: the arm's OWN submitted pipeline and configuration through ticks 1-14 with the project's incidents (and
          its withheld class on test worlds), the arm's operator; not submitted -> end-to-end failure, ops not run
  comp    component benchmark (separately labelled): NEXUS_Fresh's operator on the supplied correct pipeline
Arms: Conventional_Checked (+ ConventionalOps), Fixed_Policy (+ FixedPolicyOps), NEXUS_Fresh, NEXUS_Placebo,
NEXUS_Experienced (+ NexusOpsR1, mode B0 | B1).
  --split src|dev   reusable (no claim recorded)       --split val|val_b one-use, refuses uncommitted frozen code
  --split test      one-use; worlds ONLY from the sealed vault blobs whose sha256 match artifacts/de3_test_vault/MANIFEST.json;
                    needs NEXUS_SEALED_HARNESS_TOKEN; refuses if an r1-test COMPLETE ledger row exists"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import r1_seeds  # noqa: F401  (registers the de3 ranges)
from nexus import r1_checks as RC, r1_monitor as M
from nexus import r1_agent as RA, r1_env as RE, r1_evaluator as RV, r1_ops as RO, r1_template as RT, s4_evaluator as V
from nexus import s5_ops as O, s6_library as SL, seed_registry as R
from nexus.wave31_evaluator import ledger_append, LEDGER

ARMS = ["Conventional_Checked", "Fixed_Policy", "NEXUS_Fresh", "NEXUS_Placebo", "NEXUS_Experienced"]
FROZEN = ["src/nexus/s4_env.py", "src/nexus/s4_template.py", "src/nexus/s4_evaluator.py", "src/nexus/s4_checks.py",
          "src/nexus/s4_agent.py", "src/nexus/s5_incidents.py", "src/nexus/s5_ops.py", "src/nexus/s6_library.py",
          "src/nexus/r1_seeds.py", "src/nexus/r1_env.py", "src/nexus/r1_template.py", "src/nexus/r1_monitor.py",
          "src/nexus/r1_checks.py", "src/nexus/r1_agent.py", "src/nexus/r1_evaluator.py", "src/nexus/r1_ops.py",
          "scripts/r1_run.py", "artifacts/r1_library.json", "artifacts/r1_freeze.json"]
MANIFEST = ROOT / "artifacts/de3_test_vault/MANIFEST.json"
OP_DETECTOR = "fixed_ratio"


def freeze():
    p = ROOT / "artifacts/r1_freeze.json"
    return json.loads(p.read_text()) if p.exists() else {"ops_mode": "B1"}


def profile():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".nexus_sealed_vault"))
    return ("(version 1)(allow default)" f'(deny file-write* (subpath "{ROOT}"))' f'(deny file-read* (subpath "{Path(vault).resolve()}"))'
            "(deny network*)")


def frozen_rev():
    d = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", *FROZEN], capture_output=True, text=True).stdout
    if d.strip():
        raise SystemExit(f"frozen files differ from HEAD:\n{d}")
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def worlds(split, seeds):
    if split != "test":
        for s in seeds:
            yield s, RE.make_world(s, split)
        return
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
    man = json.loads(MANIFEST.read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"])
    from nexus.s4_env import world_from_json
    for rel, h in sorted(man["files"].items()):
        blob = (vault / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != h:
            raise SystemExit(f"sealed blob {rel} does not match the manifest")
        w = world_from_json(blob.decode())
        yield w["seed"], w


def libs():
    p = ROOT / "artifacts/r1_library.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    return SL.Library.from_json(d["library"]), SL.Library(d["placebo"], True, "placebo")


def operator(arm, library, seed, spec, mode):
    if arm == "Conventional_Checked":
        return O.ConventionalOps(arm, seed=seed)
    if arm == "Fixed_Policy":
        return RO.FixedPolicyOps(arm, detector=OP_DETECTOR, library=None, seed=seed, spec=spec, mode=mode)
    return RO.NexusOpsR1(arm, detector=OP_DETECTOR, library=library, seed=seed, spec=spec, mode=mode)


def ops_once(w, split, seed, bundle, choice, op, work, tag):
    encs, incs = RE.ops_world(w, split, seed)
    t0 = time.process_time()
    env, service = RO.run_ops(encs, incs, work / f"ops_{tag}", bundle, op, choice, profile=profile())
    oe = RV.evaluate_ops(encs["truth"], env, service)
    healthy = RO.claims_healthy(op, env, w["spec"])
    oe.update(claims_healthy=healthy, silent=healthy and not oe["data_ok"], open_escalation=getattr(op, "open", None) is not None,
              self_detected=any(e["kind"] in ("escalated", "own_pipeline_localised", "own_pipeline_unrepaired", "repaired",
                                              "applied_not_reconciled") for e in op.ledger))
    return dict(eval=oe, cost=op.cost, ledger=op.ledger, incidents=encs["truth"]["incidents"], ops_cpu_s=time.process_time() - t0,
                service=service, actions=env.actions, x_class=encs["truth"].get("x_class"))


def run_project(seed, w, split, arms, art, lib=None, plc=None, mode=None, component=True, **_):
    if lib is None and plc is None:
        lib, plc = libs()
    mode = mode or freeze().get("ops_mode", "B1")
    enc = RE.encode(w, "build")
    out = {"features": w["features"], "x_class": w.get("x_class"), "arms": {}}
    chk = Path(tempfile.mkdtemp(prefix="r1chk_"))           # val-gate measurement: the correct replay vs the observations
    RE.write_log(enc, chk / "vis", 8, archive=True)
    out["replay_view_violations"] = sum(len(M.check_view(RC.grow_obs(chk / "vis" / "log", chk / "v", k), M.load_obs(chk / "vis" / "log", k)))
                                        for k in range(1, 9))
    shutil.rmtree(chk, ignore_errors=True)
    for arm in arms:
        library = lib if arm in ("NEXUS_Experienced", "Fixed_Policy") else plc if arm == "NEXUS_Placebo" else None
        if library is None and arm in ("NEXUS_Experienced", "NEXUS_Placebo"):
            continue
        d = Path(tempfile.mkdtemp(prefix="r1_"))
        ws = d / "ws"
        (ws / "docs").mkdir(parents=True)
        (ws / "docs/spec.json").write_text(json.dumps(w["spec"], sort_keys=True))
        RE.write_log(enc, ws / "visible", 8, archive=True)
        rec = RA.build(arm, ws, profile=profile(), library=library)
        cfg = json.loads((ws / "bundle/config.json").read_text())
        (d / "bad.json").write_text(json.dumps(dict(cfg, fx={k: v * 10 for k, v in cfg["fx"].items()})))
        ev = RV.evaluate(enc["truth"], V.run_protocol(ws / "bundle", enc, d / "ev", RE.write_log, RE.retention_fn, d / "bad.json",
                                                      seed=seed)) if rec["submitted"] else dict(correct=False, silent=False,
                                                                                                 reasons=["NOT_SUBMITTED"], data_ok=False)
        ops = None
        if rec["submitted"]:
            op = operator(arm, library if arm.startswith("NEXUS") else None, seed, w["spec"], mode)
            ops = ops_once(w, split, seed, ws / "bundle", rec["final_choice"], op, d, "e2e")
        sens = None
        if component and arm == "NEXUS_Fresh" and ops is not None and freeze().get("sensitivity_mode"):
            sm = freeze()["sensitivity_mode"]                 # NON-CONFIRMATORY: the same own pipeline, the other localiser
            sens = ops_once(w, split, seed, ws / "bundle", rec["final_choice"], operator(arm, None, seed, w["spec"], sm), d, "sens")
            sens["mode"] = sm
        comp = None
        if component and arm == "NEXUS_Fresh":
            b = d / "supplied"
            b.mkdir()
            (b / "pipeline.py").write_text(RT.emit(RT.correct_choice()))
            (b / "config.json").write_text(json.dumps(RT.config_from_spec(w["spec"])))
            comp = ops_once(w, split, seed, b, RT.correct_choice(), operator(arm, None, seed, w["spec"], mode), d, "comp")
        e2e = bool(rec["submitted"] and ops and ops["eval"]["correct"] and not ops["eval"]["open_escalation"])
        dst = art / w["spec"]["project"] / arm
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ws / "bundle", dst)
        if ops:
            (dst / "incident_ledger.jsonl").write_text("".join(json.dumps(x, default=str) + "\n" for x in ops["ledger"]))
        out["arms"][arm] = dict(build=rec, build_eval={k: v for k, v in ev.items() if k != "tables"}, ops=ops, component=comp,
                                e2e_correct=e2e, sensitivity=sens)
        O._rm(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(ARMS)); ap.add_argument("--seeds", default="")
    ap.add_argument("--max-s", type=float, default=840); ap.add_argument("--mode", default=None)
    ap.add_argument("--no-component", action="store_true")
    a = ap.parse_args()
    t0 = time.perf_counter()
    rev = None
    if a.split in ("src", "dev"):
        seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(R.REGISTRY[("de3", a.split)])
        R.claim("de3", a.split, seeds, run_id=f"de3-{a.split}", record=False)
    elif a.split in ("val", "val_b"):
        rev = frozen_rev()
        seeds = list(R.REGISTRY[("de3", a.split)])
        if not Path(a.out).exists():
            R.claim("de3", a.split, seeds, run_id=f"de3-{a.split}")
    else:
        rev = frozen_rev()
        rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
        if any(r.get("run") == "r1-test" and r.get("status") == "COMPLETE" for r in rows):
            raise SystemExit("the one-shot R1 test already completed")
        seeds = None
    outp = Path(a.out)
    res = json.loads(outp.read_text()) if outp.exists() else {"projects": {}, "revisions": []}
    res["revisions"].append(rev)
    art = ROOT / f"artifacts/r1_{a.split}"
    split = "val" if a.split == "val_b" else a.split
    done = True
    for seed, w in worlds(split, seeds):
        pid = w["spec"]["project"]
        if pid in res["projects"]:
            continue
        res["projects"][pid] = run_project(seed, w, split, a.arms.split(","), art, mode=a.mode, component=not a.no_component)
        outp.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
        row = res["projects"][pid]["arms"]
        print(pid, {k: (v["build"]["outcome"][:14], v["build_eval"].get("correct"), (v["ops"] or {}).get("eval", {}).get("correct"),
                        v["e2e_correct"], round(v["build"]["cost"]["total_cpu_s"], 1)) for k, v in row.items()},
              "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            done = False
            break
    ledger_append(dict(run="r1-test" if a.split == "test" else f"r1-{a.split}", wall_s=time.perf_counter() - t0,
                       status="COMPLETE" if done else "CHECKPOINT"))


if __name__ == "__main__":
    main()
