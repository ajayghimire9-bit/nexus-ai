"""Phase 10C Stage 3 expressibility check (NOT LOCKED; diagnostic).  python scripts/agi10c_external_check.py OUT.json
For the external tasks that lift at adapter level 2 but got no verified candidate (T01, T08, T15), an EXHAUSTIVE breadth-first
enumeration of L0 operator candidates (engines6.candidates, depth <= 3, duplicates removed) from the lifted legacy checks
whether ANY reachable program reproduces the reference output on all rows (DuckDB). reachable -> class 4 (search horizon /
ranking: search10c missed it within 1,500 executions); unreachable -> class 3 (L0 cannot represent the repair)."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import engines6 as E, ir6, pipeline6 as P6  # noqa: E402
import agi10c_external as X  # noqa: E402


def main(out):
    t0 = time.time()
    res = {}
    for tid in ("T01", "T08", "T15"):
        t = next(x for x in X.TASKS if x["id"] == tid)
        p, cols, out_all, header, rs = X.project(dict(t, _text=X.adapt2(t)), ROOT / "var/agi10c_ws/external_chk")
        inv = P6.Inv6(p, gate=False)
        want = W.table_key([dict(zip(cols, r)) for r in out_all], cols)
        frontier, seen, n, hit = [(inv.legacy[0], [])], {json.dumps(inv.legacy[0], sort_keys=True)}, 0, None
        for depth in range(3):
            nxt = []
            for spec, path in frontier:
                for op in E.OPS:
                    for s2, prm in E.candidates(op, spec, inv.dom(0, [spec])):
                        k = json.dumps(s2, sort_keys=True)
                        if k in seen:
                            continue
                        seen.add(k)
                        n += 1
                        try:
                            r = E.ENGINES["duckdb"]().run(ir6.lower(s2, "duckdb"), header, rs, {})
                            if W.table_key(r["clean"], cols) == want:
                                hit = path + [(op, prm)]
                                break
                        except Exception:                      # noqa: BLE001
                            pass
                        nxt.append((s2, path + [(op, prm)]))
                    if hit:
                        break
                if hit:
                    break
            if hit:
                break
            frontier = nxt
        res[tid] = dict(programs_checked=n, reachable=hit is not None, path=hit, legacy=inv.legacy[0], cls=4 if hit else 3)
        print(tid, res[tid]["cls"], n, hit, flush=True)
    Path(out).write_text(json.dumps(dict(results=res, wall=round(time.time() - t0, 1)), indent=1, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
