"""mi component ablation of the frozen invented procedure (NOT LOCKED; development pools disc + sel only, after the freeze; the
frozen candidate is not changed). Variants remove one generated component at a time. Writes artifacts/mi_dev/ablation.json."""
import copy, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import mi_seeds, mi_learner as ML, mi_lpl as LP  # noqa: F401
import mi_discover as MD
ROOT = Path(__file__).resolve().parents[1]


def variants(w):
    v = {"full (frozen)": w, "seed (existing procedure)": LP.SEED_BASELINE}
    a = copy.deepcopy(w); a["main"] = [s for s in a["main"] if s != ("call", "h0")]; v["without call h0"] = a
    b = copy.deepcopy(w); b["helpers"]["h0"] = [["dconsts", "P3", "int_diffs"], ["union", "P2", "P2", "P3"]]; v["h0: evidence constants only"] = b
    c = copy.deepcopy(w); c["helpers"]["h0"] = [["combine", "P2", "P0", "P1", "/"], ["union", "P2", "P2", "P3"]]; v["h0: division only"] = c
    d = copy.deepcopy(w); d["main"] = [s for s in d["main"] if not (s[0] == "combine" and s[4] == "/")]; v["without main-level division"] = d
    return v


def main():
    w = json.loads((ROOT / "artifacts/mi_dev/select_evolve.json").read_text())["winner"]["prog"]
    w = json.loads(json.dumps(w))
    for k in ("main",):
        w[k] = [tuple(s) if s[0] not in ("repeat", "if_feat") else tuple(s) for s in w[k]]
    w["helpers"] = {n: [tuple(s) if s[0] != "if_feat" else ("if_feat", s[1], s[2], s[3], [tuple(x) for x in s[4]], [tuple(x) for x in s[5]])
                        for s in b] for n, b in w["helpers"].items()}
    out = {}
    for name, p in variants(w).items():
        p = json.loads(json.dumps(p))
        p["main"] = [tuple(s) for s in p["main"]]
        p["helpers"] = {n: [tuple(s) if s[0] != "if_feat" else ("if_feat", s[1], s[2], s[3], [tuple(x) for x in s[4]], [tuple(x) for x in s[5]])
                            for s in b] for n, b in p.get("helpers", {}).items()}
        tot = 0
        res = {}
        for split in ("disc", "sel"):
            fit, r = MD.evaluate(ML.lpl_domain(p), MD.pool(split), split, 8.0)
            res[split] = dict(exact=sum(x["exact"] for x in r), by_family={f: sum(x["exact"] for x in r if x["family"] == f) for f in MD.UNF},
                              cpu_s=round(sum(x["cpu_s"] for x in r), 1))
            tot += res[split]["exact"]
        out[name] = dict(res, total=tot, space_size_empty_ctx=LP.hypothesis_space(p, {})[1]["size"],
                         space_size_sample_ctx=LP.hypothesis_space(p, {"obs": [12.0, 17.0, 22.0, 3.5], "n_trans": 6})[1]["size"])
        print(name, out[name]["total"], res, flush=True)
    (ROOT / "artifacts/mi_dev/ablation.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
