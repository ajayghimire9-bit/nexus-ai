"""R2 minimal reproducer of the R1 test-7953 silent error (NOT LOCKED; de4/dev only). Forced incidents
snapshot_interrupted @ tick 11 + clock_skew @ tick 13 (the combination recorded in the R1 outputs; the sealed de3 world is not
regenerated); the correct pipeline under the R1 operator (B0) and the R1 reconciliation. Reports, per world: R1 reconciliation
verdict, final data correctness and the exact differing quarantine rows vs the truth reference.
  python scripts/r2_repro_quarantine.py OUT.json [seeds]"""
import json, sys, tempfile, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import r2_seeds, seed_registry as R  # noqa: F401
from nexus import r2_env as E2, r2_template as T2, r1_ops as RO, r1_evaluator as RV, s4_evaluator as V, s5_ops as O
from nexus.wave31_evaluator import ledger_append


def main(outp, seeds):
    t0 = time.perf_counter()
    out = {}
    for seed in seeds:
        w = E2.make_world(seed, "dev")
        encs, incs = E2.ops_world(w, "dev", seed, forced=[("snapshot_interrupted", 11), ("clock_skew", 13)])
        work = Path(tempfile.mkdtemp(prefix="r2rq_"))
        b = work / "b"; b.mkdir()
        ch = T2.correct_choice()
        (b / "pipeline.py").write_text(T2.emit(ch))
        (b / "config.json").write_text(json.dumps(T2.config_from_spec(w["spec"])))
        op = RO.NexusOpsR1("NEXUS_Fresh", detector="fixed_ratio", seed=seed, spec=w["spec"], mode="B0")
        env, service = RO.run_ops(encs, incs, work / "ops", b, op, ch)
        oe = RV.evaluate_ops(encs["truth"], env, service)
        got = Counter(map(tuple, V.read_state(env.rt["state"])["quarantine"] or []))
        want = Counter(map(tuple, RV.expected(encs["truth"], 14)["quarantine"]))
        rec = RO.reconcile(env, w["spec"])
        out[w["spec"]["project"]] = dict(data_ok=oe["data_ok"], tables=oe["tables"], r1_reconcile_ok=rec[0],
                                         only_pipeline=sorted(map(list, (got - want).elements())),
                                         only_truth=sorted(map(list, (want - got).elements())),
                                         ledger=[(e["tick"], e["kind"], e.get("signature")) for e in op.ledger if e["kind"] != "false_alarm"])
        print(w["spec"]["project"], out[w["spec"]["project"]]["data_ok"], out[w["spec"]["project"]]["r1_reconcile_ok"],
              out[w["spec"]["project"]]["only_pipeline"][:3], out[w["spec"]["project"]]["only_truth"][:3], flush=True)
        O._rm(work)
    Path(outp).write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    ledger_append(dict(run="r2-dev-repro-quarantine", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(R.REGISTRY[("de4", "dev")]))
