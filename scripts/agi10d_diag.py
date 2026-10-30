"""Phase 10D wrong-submission diagnostic (NOT LOCKED; training-stream / development data only).  python scripts/agi10d_diag.py REP SEED OUT.json
Rebuilds training task SEED of repetition REP (manifest10d.train_spec), replays the logged wake path of that task from the
repetition's wake log, and reports the submitted vs true stg node, the visible evidence and the hidden verdict per batch."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import dag10d as D, ir10d as IR, manifest10d as MD, world10d as W  # noqa: E402


def main(rep, seed, out):
    rep, seed = int(rep), int(seed)
    w = next(json.loads(l) for l in open(ROOT / f"artifacts/agi10d_train/rep{rep}.wake.jsonl") if json.loads(l)["seed"] == seed)
    p = W.make_project10d(MD.train_spec(rep, w["i"]), seed, ROOT / "var/agi10d_ws/diag")
    inv = D.Inv10d(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    from nexus.de_phase10d import search10d as SD, lineage10d as LD
    ck = json.loads((ROOT / f"artifacts/agi10d_train/rep{rep}.N{(w['n'] // 30) * 30 or 30}.json").read_text()) if False else None
    r = SD.search(inv, LD.memory(), LD.WORK, LD.WALL)                # fixed-guide re-search (the learner's memory at that time is not saved)
    res = dict(pid=p["pid"], logged=w, research_outcome=r["outcome"], research_path=r.get("path"))
    if r["outcome"] == "submitted":
        res["hidden"] = D.verify_hidden(p, r["specs"])
        res["stg_diff"] = {rel: dict(sub={k: v for k, v in r["specs"][0][rel].items() if v != truth["stg"][rel].get(k)},
                                     truth={k: v for k, v in truth["stg"][rel].items() if v != r["specs"][0][rel].get(k)})
                           for rel in truth["stg"] if r["specs"][0][rel] != truth["stg"][rel]}
        res["int_equal"], res["fct_equal"] = r["specs"][1] == truth["int"], r["specs"][2] == truth["fct"]
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, default=str)[:2500])


if __name__ == "__main__":
    main(*sys.argv[1:])
