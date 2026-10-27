"""Audit of Wave 31 v3 source-learning cost (NOT LOCKED; accounting replay, no new arm outcomes).
For each seed and fold, the source learning of scripts/wave31_v3_compare.py is replayed exactly (Fresh, depth 4,
Checker v3, axiom rotation, then the library build), and the same source tasks are also solved as plain Fresh-v3 (no
proofs). Split:
  (a) baseline = Fresh-v3 solving the source tasks (what Fresh-v3 would pay on those tasks anyway);
  (b) marginal = (source solves with axiom rotation - baseline) + library build (skeletons, macros, axiom selection).
The replayed total is cross-checked against the recorded artifact total."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import wave31_evaluator as E, wave31_tasks as T


def main():
    split, seeds = sys.argv[1], [int(s) for s in sys.argv[2].split(",")]
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); out = {}
    for s in seeds:
        rec = json.load(open(ROOT / f"artifacts/wave31v3_{split}_{s}.json"))
        out[s] = {}
        for h in ("records", "strings", "grids", "graphs"):
            src = T.source_stream3(s, h)
            ch = E.Child("0")
            rows, progs = [], []
            for i, t in enumerate(src):
                r = ev.solve(ch, t, "Fresh", "matched", [], f"{s}:{h}:src{i}", {"matched_depth": 4, "checker": 3, "proofs": f"rotate:{i}"})
                rows.append(r)
                if r["label"] == "exhaustive_UNIQUE":
                    progs.append(r["candidate"])
            c0 = E.instructions(ch.p.pid)
            ev.library(ch, progs, f"{s}:{h}", (), max_holes=1, depth=4)
            build = E.instructions(ch.p.pid) - c0
            ch.close()
            ch = E.Child("0")
            base = [ev.solve(ch, t, "Fresh", "matched", [], f"{s}:{h}:src{i}", {"matched_depth": 4, "checker": 3, "proofs": "none"})
                    for i, t in enumerate(src)]
            ch.close()
            actual = sum(r["ext"]["evaluator_work"] for r in rows)
            baseline = sum(r["ext"]["evaluator_work"] for r in base)
            out[s][h] = dict(n=len(src), actual_solves=actual, baseline=baseline, build=build,
                             rotation_delta=actual - baseline, recorded_total=rec["folds"][h]["source"]["evaluator_work"],
                             baseline_child=sum(r["ext"]["child_instr"] for r in base),
                             baseline_checker=sum(r["ext"]["eval_instr"] for r in base))
    (ROOT / f"artifacts/wave31_source_audit_{split}.json").write_text(json.dumps(out, sort_keys=True))
    E.ledger_append(dict(run=f"wave31-source-audit-{split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    tot = {k: sum(f[k] for d in out.values() for f in d.values()) for k in ("n", "actual_solves", "baseline", "build",
                                                                            "rotation_delta", "recorded_total", "baseline_child", "baseline_checker")}
    print(json.dumps({k: (v if k == "n" else round(v / 1e9, 3)) for k, v in tot.items()}))


if __name__ == "__main__":
    main()
