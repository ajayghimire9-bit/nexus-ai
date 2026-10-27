"""Stages 4-6 combined runner (NOT LOCKED). Per project, per arm (environments and memories reset between arms):
  build (Stage 4): the arm's build agent on docs + visible ticks 1-8; the protected s4 evaluator scores the submitted bundle
                   (checkpoints 4 / 8 / 12, crash sweeps, rollback drill)
  ops   (Stage 5): the arm's operator runs the handed-over production pipeline (identical for every arm) through ticks 1-14
                   with the project's hidden-cause incidents; evaluate_ops scores it
Arms: Conventional_Checked (+ ConventionalOps), NEXUS_Fresh, NEXUS_Placebo, NEXUS_Experienced (+ NexusOps with the
operator detector), Conventional_NoCheck (+ RestartOnly; descriptive ablation). Detector sub-experiment: NEXUS_Fresh ops
also with bocpd_merge_exact and disabled.
  --split src|dev   reusable (no claim recorded)
  --split val|val_b one-use, claimed whole; refuses uncommitted Stages 4-6 code
  --split test      one-use; worlds ONLY from the sealed vault blobs whose sha256 match artifacts/de2_test_vault/MANIFEST.json;
                    needs NEXUS_SEALED_HARNESS_TOKEN; refuses if a de2-s456-test ledger row exists"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import s456_seeds  # noqa: F401  (registers the de2 ranges)
from nexus import s4_agent as A, s4_env as E, s4_evaluator as V, s4_template as T, s5_incidents as I, s5_ops as O
from nexus import s6_library as SL, seed_registry as R
from nexus.wave31_evaluator import ledger_append, LEDGER

ARMS = ["Conventional_Checked", "NEXUS_Fresh", "NEXUS_Placebo", "NEXUS_Experienced", "Conventional_NoCheck"]
FROZEN = ["src/nexus/s4_env.py", "src/nexus/s4_template.py", "src/nexus/s4_evaluator.py", "src/nexus/s4_checks.py",
          "src/nexus/s4_agent.py", "src/nexus/s5_incidents.py", "src/nexus/s5_ops.py", "src/nexus/s6_library.py",
          "src/nexus/s456_seeds.py", "scripts/s456_run.py", "artifacts/s6_library.json", "artifacts/s5_detector_calibration.json"]
MANIFEST = ROOT / "artifacts/de2_test_vault/MANIFEST.json"
OP_DETECTOR = "fixed_ratio"


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
            yield s, E.make_world(s, split)
        return
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
    man = json.loads(MANIFEST.read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"])
    for rel, h in sorted(man["files"].items()):
        blob = (vault / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != h:
            raise SystemExit(f"sealed blob {rel} does not match the manifest")
        w = E.world_from_json(blob.decode())
        yield w["seed"], w


def libs():
    p = ROOT / "artifacts/s6_library.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    return SL.Library.from_json(d["library"]), SL.Library(d["placebo"], True, "placebo")


def run_project(seed, w, split, arms, art, detectors=True, lib=None, plc=None):
    if lib is None and plc is None:
        lib, plc = libs()
    enc = E.encode(w, "build")
    out = {"features": w["features"], "withheld": w["withheld"], "arms": {}}
    for arm in arms:
        library = lib if arm == "NEXUS_Experienced" else plc if arm == "NEXUS_Placebo" else None
        if library is None and arm in ("NEXUS_Experienced", "NEXUS_Placebo"):
            continue
        d = Path(tempfile.mkdtemp(prefix="s456_"))
        ws = d / "ws"
        (ws / "docs").mkdir(parents=True)
        (ws / "docs/spec.json").write_text(json.dumps(w["spec"], sort_keys=True))
        E.write_log(enc, ws / "visible", E.VISIBLE)
        rec = A.build(arm, ws, profile=profile(), library=library)
        cfg = json.loads((ws / "bundle/config.json").read_text())
        (d / "bad.json").write_text(json.dumps(dict(cfg, fx={k: v * 10 for k, v in cfg["fx"].items()})))
        ev = V.evaluate(enc["truth"], V.run_protocol(ws / "bundle", enc, d / "ev", E.write_log, E.retention, d / "bad.json",
                                                    seed=seed)) if rec["submitted"] else dict(correct=False, silent=False,
                                                                                               reasons=["NOT_SUBMITTED"], data_ok=False)
        ops = {}
        variants = [(OP_DETECTOR, arm)] + ([("bocpd_merge_exact", arm), ("disabled", arm)] if detectors and arm == "NEXUS_Fresh" else [])
        for det, _ in variants:
            encs, incs = I.ops_world(w, split, seed)
            b = d / f"prod_{det}"
            b.mkdir()
            (b / "pipeline.py").write_text(T.emit(T.correct_choice()))
            (b / "config.json").write_text(json.dumps(T.config_from_spec(w["spec"])))
            op = (O.ConventionalOps if arm == "Conventional_Checked" else O.RestartOnly if arm == "Conventional_NoCheck" else O.NexusOps)(
                arm, detector=det if arm.startswith("NEXUS") else None, library=library, seed=seed)
            t0 = time.process_time()
            env, service = O.run_ops(encs, incs, d / f"ops_{det}", b, op, profile=profile())
            oe = I.evaluate_ops(encs["truth"], env, service)
            shift = [dict(supplier=i.supplier, tick=i.tick) for i in incs if i.name == "unit_shift"]
            ops[det if arm.startswith("NEXUS") else "none"] = dict(eval=oe, cost=op.cost, ledger=op.ledger,
                                                                  incidents=encs["truth"]["incidents"], unit_shift=shift,
                                                                  alarms=op.det_state.get("alarms", []) + op.det_state.get("dismissed", []) + op.det_state.get("resolved", []),
                                                                  detector_cpu_s=op.det_state.get("cpu_s", 0.0),
                                                                  ops_cpu_s=time.process_time() - t0, service=service)
            if det == OP_DETECTOR or not arm.startswith("NEXUS"):
                dst = art / w["spec"]["project"] / arm
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(ws / "bundle", dst)
                (dst / "incident_ledger.jsonl").write_text("".join(json.dumps(x, default=str) + "\n" for x in op.ledger))
        out["arms"][arm] = dict(build=rec, build_eval={k: v for k, v in ev.items() if k != "tables"}, ops=ops)
        shutil.rmtree(d, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(ARMS)); ap.add_argument("--seeds", default="")
    ap.add_argument("--max-s", type=float, default=860); ap.add_argument("--no-detectors", action="store_true")
    a = ap.parse_args()
    t0 = time.perf_counter()
    rev = None
    if a.split in ("src", "dev"):
        seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(R.REGISTRY[("de2", a.split)])
        R.claim("de2", a.split, seeds, run_id=f"de2-{a.split}", record=False)
    elif a.split in ("val", "val_b"):
        rev = frozen_rev()
        seeds = list(R.REGISTRY[("de2", a.split)])
        outp = Path(a.out)
        if not outp.exists():
            R.claim("de2", a.split, seeds, run_id=f"de2-{a.split}")
    else:
        rev = frozen_rev()
        rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
        if any(r.get("run") == "de2-s456-test" and r.get("status") == "COMPLETE" for r in rows):
            raise SystemExit("the one-shot Stages 4-6 test already completed")
        seeds = None
    outp = Path(a.out)
    res = json.loads(outp.read_text()) if outp.exists() else {"projects": {}, "revisions": []}
    res["revisions"].append(rev)
    art = ROOT / f"artifacts/s456_{a.split}"
    split = "val" if a.split == "val_b" else a.split
    done = True
    for seed, w in worlds(split, seeds):
        pid = w["spec"]["project"]
        if pid in res["projects"]:
            continue
        res["projects"][pid] = run_project(seed, w, split, a.arms.split(","), art, detectors=not a.no_detectors)
        outp.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
        row = res["projects"][pid]["arms"]
        print(pid, {k: (v["build"]["outcome"][:14], v["build_eval"].get("correct"),
                        {d: o["eval"]["correct"] for d, o in v["ops"].items()}, round(v["build"]["cost"]["total_cpu_s"], 1))
                    for k, v in row.items()}, "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            done = False
            break
    run = "de2-s456-test" if a.split == "test" else f"de2-s456-{a.split}"
    ledger_append(dict(run=run, wall_s=time.perf_counter() - t0, status="COMPLETE" if done else "CHECKPOINT"))


if __name__ == "__main__":
    main()
