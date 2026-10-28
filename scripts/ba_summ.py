"""Joint Step 3 metrics for episode files (NOT LOCKED).  python scripts/ba_summ.py FILE [FILE ...]  (files concatenated)"""
import json, sys
BUDGETS = (500, 1000, 2000, 4000)


def summ(rows):
    n = len(rows)
    acc = sum(r["accepted"] for r in rows)
    sil = sum(r["silent"] for r in rows)
    cor = sum(r["exact"] for r in rows)
    ab = sum(r["abstain"] for r in rows)
    return dict(n=n, correct=cor, correct_pct=round(100 * cor / n, 1), accepted=acc, silent=sil,
                false_accept_pct=round(100 * sil / acc, 1) if acc else None, silent_pct=round(100 * sil / n, 1),
                abstain=ab, abstain_pct=round(100 * ab / n, 1), queries=sum(r["queries"] for r in rows),
                cpu_s=round(sum(r["cpu_s"] for r in rows), 1),
                curve={b: sum(r["exact"] and r["queries"] <= b for r in rows) for b in BUDGETS},
                unaccepted_exact=sum(r.get("unaccepted_exact", False) for r in rows))


if __name__ == "__main__":
    rows = [json.loads(l) for f in sys.argv[1:] for l in open(f) if l.strip()]
    print(json.dumps(summ(rows)))
