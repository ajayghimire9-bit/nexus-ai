"""MI-2 discovery summary (NOT LOCKED; reads development artifacts only).  python scripts/mi2_summary.py [POOLSET]
Per lineage: candidate count, evaluation CPU (failed candidates included), best discovery fitness and per-family exact, number
of candidates improving on the lineage's running best, silent rows; partial-credit check: across all candidates, the Spearman
correlation between the partial-credit term and exact count, and the fraction of episodes with partial credit > 0 that were
exact. -> artifacts/mi2_dev/summary_<POOLSET>.json"""
import glob, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
            j += 1
        for k in range(i, j + 1):
            r[s[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


def main(ps):
    out, ex, pa, ep_part, ep_exact = {}, [], [], 0, 0
    for f in sorted(glob.glob(str(ROOT / f"artifacts/mi2_dev/disc_{ps}_*_L*.json"))):
        d = json.loads(Path(f).read_text())
        c = d["cands"]
        best, improved = None, 0
        for x in c:
            if best is None or x["fitness"] > best:
                improved += best is not None
                best = x["fitness"]
        b = max(c, key=lambda x: (x["fitness"], -x["id"]))
        sel = ROOT / f.replace("disc_", "select_")
        sw = json.loads(sel.read_text()) if sel.exists() else {}
        out[Path(f).stem] = dict(candidates=len(c), eval_cpu_s=d["spent_cpu_s"], exhausted=d.get("exhausted", False),
                                 best_id=b["id"], best_fitness=b["fitness"], best_per_family=b["per_family"],
                                 improvements_over_running_best=improved, silent_rows=sum(x["silent"] for x in c),
                                 selected_id=sw.get("winner", {}).get("id"), selected_sel_fitness=sw.get("winner_sel_fitness"))
        for x in c:
            ex.append(x["exact"])
            pa.append(x["partial"])
            for r in x["per_episode"]:
                if r["explained"] > 0:
                    ep_part += 1
                    ep_exact += r["exact"]
    res = dict(lineages=out, partial_credit=dict(spearman_partial_vs_exact=spearman(pa, ex) if len(ex) > 2 else None,
                                                 episodes_with_partial=ep_part, of_which_exact=ep_exact))
    (ROOT / f"artifacts/mi2_dev/summary_{ps}.json").write_text(json.dumps(res, indent=1))
    for k, v in out.items():
        print(k, v)
    print(res["partial_credit"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "a")
