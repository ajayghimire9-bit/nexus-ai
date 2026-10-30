"""Phase 11 Stage 1 development timing / reach (NOT LOCKED; agi11/dev fixtures only, no learned library, no target).
  python scripts/agi11_dev.py OUT.json N_EACH [REL_CAP SC_CAP WALL] [kinds,comma,separated]
For every family / composition kind: build a dev task, solve with the fixed search and NO library (the F0 configuration), verify the
submission natively on DuckDB against the hidden batches, and record outcome, wrong, counters (relational evaluations, micro-evaluations,
full checks, evidence requests), wall, expanded size and the expanded program."""
import json, resource, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase11 import manifest11 as M, synth11 as S, tasks11 as T, verify11 as V  # noqa: E402


def main(out, n_each, rel_cap=S.REL_CAP, sc_cap=S.SC_CAP, wall=S.WALL_S, kinds=None):
    n_each = int(n_each)
    todo = M.dev_tasks(n_each)
    if kinds:
        ks = set(kinds.split(","))
        todo = [t for t in todo if t[0] in ks]
    rows = []
    t0 = time.time()
    for kind, seed in todo:
        tb = time.time()
        learner, admin, hidden = T.build(kind, seed)
        gen_s = time.time() - tb
        r = S.solve(learner, budget=S.Budget(int(rel_cap), int(sc_cap), float(wall)), evidence=lambda: admin["evidence"])
        v = V.verify(r["program"], {}, hidden) if r["program"] is not None else None
        row = dict(kind=kind, seed=seed, outcome=r["outcome"], verified=bool(v and v["ok"]), wrong=bool(v and not v["ok"]), size=r.get("size"),
                   counters=r["counters"], log=r["log"], wall=r["wall"], wall_bound=r["wall_bound"], gen_s=round(gen_s, 3), width=hidden["width"],
                   program=r["expanded"], conformance_mismatch=(v or {}).get("conformance_mismatch"))
        rows.append(row)
        print(kind, seed, row["outcome"], "V" if row["verified"] else ("W" if row["wrong"] else "-"), "rel", r["counters"].get("rel_evals"),
              "micro", r["counters"].get("micro_evals"), "wall", r["wall"], "size", row["size"], flush=True)
    summ = dict(n=len(rows), verified=sum(r["verified"] for r in rows), wrong=sum(r["wrong"] for r in rows), wall=round(time.time() - t0, 1),
                peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 1),
                by_kind={k: f"{sum(r['verified'] for r in rows if r['kind'] == k)}/{sum(1 for r in rows if r['kind'] == k)}" for k in dict.fromkeys(r["kind"] for r in rows)})
    Path(out).write_text(json.dumps(dict(summary=summ, rows=rows), indent=1, default=str))
    print(json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
