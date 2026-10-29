"""MI-2 development-only component ablation of a frozen procedure (NOT LOCKED; after the freeze; selection pool mi2/sel only).
  python scripts/mi2_ablate.py ARM        ARM = a frozen arm tag in artifacts/mi2_freeze.json (e.g. A2)
Variants: the frozen procedure; each top-level main statement except `ret` removed in turn; each helper emptied in turn. Scored
with the discovery evaluator (3 s CPU cap). Never feeds back into any frozen candidate. -> artifacts/mi2_dev/ablation_<ARM>.json"""
import copy, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mi2_discover as DSC
from nexus import mi_learner as ML, mi_lpl as LP
ROOT = Path(__file__).resolve().parents[1]


def main(arm):
    fr = json.loads((ROOT / "artifacts/mi2_freeze.json").read_text())
    w = json.loads((ROOT / fr["arms"]["val"][arm]["file"]).read_text())["winner"]
    prog = w["prog"]
    out_p = ROOT / f"artifacts/mi2_dev/ablation_{arm}.json"
    out = json.loads(out_p.read_text()) if out_p.exists() else dict(arm=arm, source=LP.source(prog), variants=[])
    done = {v["name"] for v in out["variants"]}
    variants = [("frozen", prog)]
    for i, st in enumerate(prog["main"]):
        if st[0] != "ret":
            p = copy.deepcopy(prog)
            del p["main"][i]
            variants.append((f"-main[{i}] {' '.join(map(str, st))[:60]}", p))
    for h in prog.get("helpers", {}):
        p = copy.deepcopy(prog)
        p["helpers"][h] = []
        variants.append((f"-helper {h}", p))
    rows = DSC.pool("a", "sel")
    T0 = time.perf_counter()
    for name, p in variants:
        if name in done or time.perf_counter() - T0 > 760:
            continue
        fit, res = DSC.evaluate(ML.lpl_domain(p), rows)
        out["variants"].append(dict(name=name, fitness=fit, per_family={f: sum(r["exact"] for r in res if r["family"] == f) for f in DSC.POOLS["a"]["sel"][1]},
                                    space_size=LP.hypothesis_space(p, {})[1]["size"]))
        out_p.write_text(json.dumps(out, indent=1))
        print(name, fit, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
