"""OOP-track Phase 1 runner (NOT LOCKED), adapted from scripts/r2_run.py (unchanged). de5 worlds (oop_env), one evaluator for
every arm (oop_evaluator). Arms:
  NEXUS_Synth           oop_agent build (8 switches replaced by synthesised code) + oop_ops (B1, C0; resynthesis in repair)
  NEXUS_Template        the frozen R2 NEXUS_Fresh (r2_agent + r2_ops B1 / C0): the same operator with author-written switches
  Fixed_Policy          the frozen R2 Fixed_Policy (r2 src option counts)        Conventional_Checked   the frozen R2 one
Per project, per arm:
  build      the arm's build agent; scoped evidence + label; protected build evaluation
  natural    the arm's OWN submitted pipeline, ticks 1-14, the project's incidents and its classes; end-to-end score
  forced     X1 / X2 only (their switches still exist): the class's decision forced to its naive option; template arms also
             X3 / X4 (R2's forced options). For NEXUS_Synth the X3 / X4 / D1 / D2 holes were synthesised from a window that
             never contains the class, so its natural deployment IS the forced condition: scored once, reported in both
             tables, flagged synth_natural_is_forced
  secondary  NEXUS_Synth only: its natural deployment again with the B0 localiser
A crash of the harness on any project stops the run (no resume loop; R2 lesson). --split test needs
NEXUS_SEALED_HARNESS_TOKEN and reads only vault blobs whose sha256 match artifacts/de5_test_vault/MANIFEST.json."""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import oop_seeds  # noqa: F401  (registers the de5 ranges)
from nexus import r1_checks as RC, r1_monitor as M
from nexus import oop_agent as OA, oop_env as RE, oop_evaluator as RV, oop_ops as OO, oop_template as OT
from nexus import r2_agent as RA, r2_ops as RO, r2_template as RT, s4_evaluator as V
from nexus import s5_ops as O, s6_library as SL, seed_registry as R
from nexus.wave31_evaluator import ledger_append, LEDGER

ARMS = ["NEXUS_Synth", "NEXUS_Template", "Fixed_Policy", "Conventional_Checked"]
FROZEN = ["src/nexus/oop_seeds.py", "src/nexus/oop_env.py", "src/nexus/oop_template.py", "src/nexus/oop_reconcile.py",
          "src/nexus/oop_synthesizer.py", "src/nexus/oop_examples.py", "src/nexus/oop_agent.py", "src/nexus/oop_ops.py",
          "src/nexus/oop_evaluator.py", "scripts/oop_run.py", "artifacts/oop_freeze.json",
          "src/nexus/r2_seeds.py", "src/nexus/r2_env.py", "src/nexus/r2_template.py", "src/nexus/r2_reconcile.py",
          "src/nexus/r2_ops.py", "src/nexus/r2_agent.py", "src/nexus/r2_evaluator.py", "artifacts/r2_library.json",
          "src/nexus/s4_env.py", "src/nexus/s4_template.py", "src/nexus/s4_evaluator.py", "src/nexus/s4_checks.py",
          "src/nexus/s4_agent.py", "src/nexus/s5_incidents.py", "src/nexus/s5_ops.py", "src/nexus/s6_library.py",
          "src/nexus/r1_seeds.py", "src/nexus/r1_env.py", "src/nexus/r1_template.py", "src/nexus/r1_monitor.py",
          "src/nexus/r1_checks.py", "src/nexus/r1_agent.py", "src/nexus/r1_evaluator.py", "src/nexus/r1_ops.py"]
MANIFEST = ROOT / "artifacts/de5_test_vault/MANIFEST.json"
FORCED_T = {"X1": ("txn_isolation", "read_uncommitted"), "X2": ("gap_handling", "skip"), "X3": ("fx_unknown", "error"),
            "X4": ("discount_unit", "percent_only")}
FORCED_S = {"X1": ("txn_isolation", "read_uncommitted"), "X2": ("gap_handling", "skip")}
OP_DETECTOR = "fixed_ratio"


def freeze():
    p = ROOT / "artifacts/oop_freeze.json"
    return json.loads(p.read_text()) if p.exists() else {"ops_mode": "B1", "c_mode": "C0"}


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


def src_counts():
    p = ROOT / "artifacts/r2_library.json"
    return json.loads(p.read_text()).get("option_counts", {}) if p.exists() else {}


def operator(arm, seed, spec, mode, c_mode=None):
    if arm == "Conventional_Checked":
        return O.ConventionalOps(arm, seed=seed)
    if arm == "Fixed_Policy":
        op = RO.FixedPolicyOps(arm, detector=OP_DETECTOR, library=None, seed=seed, spec=spec, mode=mode)
        op.src_counts = src_counts()
        return op
    cls = OO.NexusOpsSynth if arm == "NEXUS_Synth" else RO.NexusOpsR2
    op = cls(arm, detector=OP_DETECTOR, library=None, seed=seed, spec=spec, mode=mode)
    op.c_mode = c_mode or freeze().get("c_mode", "C0")
    return op


def ops_once(arm, w, split, seed, bundle, choice, op, work, tag):
    encs, incs = RE.ops_world(w, split, seed)
    t0 = time.process_time()
    mod = OO if arm == "NEXUS_Synth" else RO
    env, service = mod.run_ops(encs, incs, work / f"ops_{tag}", bundle, op, choice, profile=profile())
    oe = RV.evaluate_ops(encs["truth"], env, service)
    healthy = mod.claims_healthy(op, env, w["spec"])
    oe.update(claims_healthy=healthy, x_class=encs["truth"].get("x_class"), silent=healthy and not oe["data_ok"],
              open_escalation=getattr(op, "open", None) is not None,
              self_detected=any(e["kind"] in ("escalated", "own_pipeline_localised", "own_pipeline_unrepaired", "repaired",
                                              "applied_not_reconciled") for e in op.ledger))
    return dict(eval=oe, cost=op.cost, ledger=op.ledger, incidents=encs["truth"]["incidents"], ops_cpu_s=time.process_time() - t0,
                service=service, actions=env.actions, x_class=encs["truth"].get("x_class"), d_class=encs["truth"].get("d_class"),
                final_choice=dict(env.choice))


def _ok(r):
    return bool(r and r["eval"]["correct"] and not r["eval"]["open_escalation"])


def run_project(seed, w, split, arms, art, mode=None, forced=True, c_mode=None, secondary=True):
    mode = mode or freeze().get("ops_mode", "B1")
    enc = RE.encode(w, "build")
    out = {"features": w["features"], "x_class": w.get("x_class"), "d_class": w.get("d_class"), "arms": {}}
    chk = Path(tempfile.mkdtemp(prefix="oopchk_"))
    RE.write_log(enc, chk / "vis", 8, archive=True)
    out["replay_view_violations"] = sum(len(M.check_view(RC.grow_obs(chk / "vis" / "log", chk / "v", k), M.load_obs(chk / "vis" / "log", k)))
                                        for k in range(1, 9))
    shutil.rmtree(chk, ignore_errors=True)
    for arm in arms:
        d = Path(tempfile.mkdtemp(prefix="oop_"))
        ws = d / "ws"
        (ws / "docs").mkdir(parents=True)
        (ws / "docs/spec.json").write_text(json.dumps(w["spec"], sort_keys=True))
        RE.write_log(enc, ws / "visible", 8, archive=True)
        synth = arm == "NEXUS_Synth"
        if synth:
            rec = OA.build(arm, ws, profile=profile())
            emit = OT.emit
            snap = OT.snapshot()
        else:
            RA.COUNTS.clear(); RA.COUNTS.update(src_counts())
            rec = RA.build("NEXUS_Fresh" if arm == "NEXUS_Template" else arm, ws, profile=profile(), library=None)
            rec["arm"] = arm
            emit = RT.emit
        ev = dict(correct=False, silent=False, reasons=["NOT_SUBMITTED"], data_ok=False)
        if rec["submitted"]:
            cfg = json.loads((ws / "bundle/config.json").read_text())
            (d / "bad.json").write_text(json.dumps(dict(cfg, fx={k: v * 10 for k, v in cfg["fx"].items()})))
            ev = RV.evaluate(enc["truth"], V.run_protocol(ws / "bundle", enc, d / "ev", RE.write_log, RE.retention_fn, d / "bad.json",
                                                          seed=seed))
        ops = frc = sec = None
        if synth:
            OT.restore(snap)
        if rec["submitted"]:
            ops = ops_once(arm, w, split, seed, ws / "bundle", rec["final_choice"], operator(arm, seed, w["spec"], mode, c_mode), d, "e2e")
        fmap = FORCED_S if synth else FORCED_T
        if rec["submitted"] and forced and w.get("x_class") in fmap:
            dec, naive = fmap[w["x_class"]]
            fch = dict(rec["final_choice"], **{dec: naive})
            if synth:
                OT.restore(snap)
            fb = d / "forced_bundle"
            fb.mkdir()
            (fb / "pipeline.py").write_text(emit(fch))
            shutil.copy(ws / "bundle" / "config.json", fb / "config.json")
            frc = ops_once(arm, w, split, seed, fb, fch, operator(arm, seed, w["spec"], mode, c_mode), d, "forced")
            frc.update(forced=[dec, naive], natural_choice=rec["final_choice"].get(dec))
        if synth and rec["submitted"] and secondary:
            other = "B0" if mode == "B1" else "B1"
            OT.restore(snap)
            sec = ops_once(arm, w, split, seed, ws / "bundle", rec["final_choice"], operator(arm, seed, w["spec"], other, c_mode), d,
                           "secondary")
            sec.update(mode=other)
        dst = art / w["spec"]["project"] / arm
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ws / "bundle", dst)
        if ops:
            (dst / "incident_ledger.jsonl").write_text("".join(json.dumps(x, default=str) + "\n" for x in ops["ledger"]))
        if synth:
            (dst / "programs.json").write_text(json.dumps(OA.programs_json(), indent=1, sort_keys=True, default=str))
            if ops and ops["final_choice"].get("syn_decode"):
                try:
                    (dst / "deployed_synthesised_code.py").write_text(OT.synth_code(ops["final_choice"]))
                except KeyError:
                    pass
        out["arms"][arm] = dict(build=rec, build_eval={k: v for k, v in ev.items() if k != "tables"}, ops=ops, e2e_correct=_ok(ops),
                                forced=frc, forced_e2e=_ok(frc), secondary=sec, secondary_e2e=_ok(sec),
                                synth_natural_is_forced=synth and w.get("x_class") not in FORCED_S)
        O._rm(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(ARMS)); ap.add_argument("--seeds", default="")
    ap.add_argument("--max-s", type=float, default=840); ap.add_argument("--mode", default=None)
    ap.add_argument("--no-forced", action="store_true"); ap.add_argument("--no-secondary", action="store_true")
    ap.add_argument("--c-mode", default=None)
    a = ap.parse_args()
    t0 = time.perf_counter()
    rev = None
    if a.split in ("src", "dev"):
        seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(R.REGISTRY[("de5", a.split)])
        R.claim("de5", a.split, seeds, run_id=f"de5-{a.split}", record=False)
    elif a.split in ("val", "val_b"):
        rev = frozen_rev()
        seeds = list(R.REGISTRY[("de5", a.split)])
        if not Path(a.out).exists():
            R.claim("de5", a.split, seeds, run_id=f"de5-{a.split}")
    else:
        rev = frozen_rev()
        rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
        if any(r.get("run") == "oop-test" and r.get("status") in ("COMPLETE", "CRASHED") for r in rows):
            raise SystemExit("the one-shot OOP test already ran")
        seeds = None
    outp = Path(a.out)
    res = json.loads(outp.read_text()) if outp.exists() else {"projects": {}, "revisions": []}
    res["revisions"].append(rev)
    art = ROOT / f"artifacts/oop_{a.split}"
    split = "val" if a.split == "val_b" else a.split
    status = "COMPLETE"
    run = "oop-test" if a.split == "test" else f"oop-{a.split}"
    try:
        for seed, w in worlds(split, seeds):
            pid = w["spec"]["project"]
            if pid in res["projects"]:
                continue
            res["projects"][pid] = run_project(seed, w, split, a.arms.split(","), art, mode=a.mode, forced=not a.no_forced,
                                               c_mode=a.c_mode, secondary=not a.no_secondary)
            outp.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
            row = res["projects"][pid]["arms"]
            print(pid, {k: (v["build"]["outcome"][:14], v["build_eval"].get("correct"), v["e2e_correct"], v["forced_e2e"],
                            v["secondary_e2e"], round(v["build"]["cost"]["total_cpu_s"], 1)) for k, v in row.items()},
                  "%.0fs" % (time.perf_counter() - t0), flush=True)
            if time.perf_counter() - t0 > a.max_s:
                status = "CHECKPOINT"
                break
    except Exception:  # noqa: BLE001  - a harness crash ends the run; it is recorded, never retried automatically
        status = "CRASHED"
        res.setdefault("crashes", []).append(traceback.format_exc()[-3000:] if a.split != "test" else "harness crash (traceback "
                                                                                                    "withheld on the sealed split)")
        outp.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
        print("HARNESS CRASH - run stopped", flush=True)
    ledger_append(dict(run=run, wall_s=time.perf_counter() - t0, status=status))
    if status == "CRASHED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
