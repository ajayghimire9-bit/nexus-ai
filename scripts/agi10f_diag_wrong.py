"""Phase 10F audit of the ONE Phase 10E training wrong submission (NOT LOCKED; training data only, no evaluation target).
  python scripts/agi10f_diag_wrong.py OUT.json
rep1 task 24: P10D.T_cdc_key+dirty.sqlite.postgres.101524 (agi10ede/train), submitted path json_coalesce_before -> add_partition
-> add_filter, wrong on the hidden batches (the wake log keeps the operator names, not the parameters). The project is rebuilt on
the FROZEN Phase 10E generator / substrate and every path of that operator shape is enumerated: which complete paths pass every
visible check, node contract and acceptance rule (`ok`, i.e. would be submitted) and which of those fail the hidden batches."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import world10d as W  # noqa: E402
from nexus.de_phase10e import dag10e as D, manifest10e as ME  # noqa: E402


def main(out):
    t0 = time.time()
    spec = ME.train_spec(1, 24)
    p = W.make_project10d(spec, 101524, ROOT / "var/agi10f_ws/diag")
    inv = D.Inv10e(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    rows = []
    for s1, p1 in D.candidates("json_coalesce_before", inv.legacy[0], inv.dom(0, inv.legacy)):
        sp1 = [s1] + inv.legacy[1:]
        for s2, p2 in D.candidates("add_partition", s1, inv.dom(0, sp1)):
            sp2 = [s2] + sp1[1:]
            for s3, p3 in D.candidates("add_filter", s2, inv.dom(0, sp2)):
                sp3 = [s3] + sp2[1:]
                ev = inv.run(sp3, True)
                if ev["ok"]:
                    h = D.verify_hidden(p, sp3)
                    rows.append(dict(path=[p1, p2, p3], hidden_ok=h["ok"], fails=h["fails"]))
    wrong = [r for r in rows if not r["hidden_ok"]]
    rel = sorted({r["path"][1].split("|")[0] for r in wrong})
    diff = {}
    for r in wrong[:3]:
        sp = D.replay(inv, [(0, "json_coalesce_before", r["path"][0]), (0, "add_partition", r["path"][1]), (0, "add_filter", r["path"][2])])
        diff[" -> ".join(r["path"])] = {n: sp[0][n] for n in sp[0] if sp[0][n] != truth["stg"].get(n)}
    res = dict(project=p["pid"], spec=spec, truth_stg_orders=truth["stg"]["stg_orders"], n_ok_paths=len(rows), n_wrong_ok_paths=len(wrong),
               wrong_partition_relations=rel, wrong_examples=wrong[:12], correct_examples=[r for r in rows if r["hidden_ok"]][:6], stg_diff_vs_truth=diff,
               wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("project", "n_ok_paths", "n_wrong_ok_paths", "wrong_partition_relations", "wall")}))
    for r in wrong[:6]:
        print("WRONG", r)


if __name__ == "__main__":
    main(*sys.argv[1:])
