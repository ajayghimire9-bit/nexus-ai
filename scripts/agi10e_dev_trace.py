"""Phase 10E Stage 1 development trace (NOT LOCKED; one agi10ede/dev S_replay project).  python scripts/agi10e_dev_trace.py SEED
Where the replay repair sits in the fixed root order, how its partition step is classified, and where A1 search spends work."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import world10d as W  # noqa: E402
from nexus.de_phase10e import dag10e as D, lineage10e as LE, search10e as SD  # noqa: E402


def main(seed):
    seed = int(seed)
    p = W.make_project10d(dict(family="S_replay", faults=["replay"], engine="duckdb", legacy="snowflake", names="base"), seed, ROOT / "var/agi10e_ws/dev")
    inv = D.Inv10e(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    kc = truth["stg"]["stg_order_items"]["dedup"]["key"][1][1]
    ev0 = inv.run(inv.legacy, True)
    order = SD.candidates(inv, {}, dict(specs=inv.legacy, ev=ev0), "whole")
    pos = next(i for i, c in enumerate(order) if c["op"] == "add_partition" and c["prm"] == f"stg_order_items|{kc}")
    mid = D.replay(inv, [(0, "add_partition", f"stg_order_items|{kc}")])
    ev1 = inv.run(mid, True)
    print(json.dumps(dict(n_root=len(order), partition_pos=pos, ops_before=collections.Counter(c["op"] for c in order[:pos]),
                          root_score=ev0["score"], mid_score=ev1["score"], root_failed=ev0["failed"], mid_failed=ev1["failed"],
                          root_stage_fail=ev0["stage_fail"], mid_stage_fail=ev1["stage_fail"]), default=list))
    r = SD.search(inv, LE.memory(), 600, 4.0)
    print(json.dumps(dict(outcome=r["outcome"], work=r["work"], wall=r["wall"], events=r["events"], best=r.get("best_partial")), default=list))


if __name__ == "__main__":
    main(*sys.argv[1:])
