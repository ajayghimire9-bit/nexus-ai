"""Part G analysis (NOT LOCKED): separate growth-rule comparison, fallback disabled, fresh sc/ep_held3 (pre-registered rule G).
Writes artifacts/sc_partg.json; prints the table."""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba_summ import summ, BUDGETS
ROOT = Path(__file__).resolve().parents[1]
ARMS = [("Learned", "learned"), ("Hand", "hand"), ("Shuffled", "shuffled"), ("Random", "random")]


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


E = {n: sorted((json.loads(l) for l in (ROOT / f"artifacts/sc_dev/eps_{a}_ep_held3_0.jsonl").read_text().splitlines() if l.strip()),
               key=lambda r: r["seed"]) for n, a in ARMS}
assert all(len(v) == 300 for v in E.values()) and len({tuple(r["seed"] for r in v) for v in E.values()}) == 1
S = {}
for n, v in E.items():
    d = summ(v)
    d["solve_ci"] = wilson(d["correct"], d["n"])
    d["false_accept_ci"] = wilson(d["silent"], d["accepted"])
    d["silent_out_of_alphabet"] = sum(r["silent"] and r["out_of_alphabet"] for r in v)
    d["wall_s"] = round(sum(r["wall_s"] for r in v), 1)
    d["maxrss_mb"] = max(r["maxrss_mb"] for r in v)
    S[n] = d
T = {}
for c in ("Hand", "Shuffled", "Random"):
    b = sum(x["exact"] and not y["exact"] for x, y in zip(E["Learned"], E[c]))
    d = sum(y["exact"] and not x["exact"] for x, y in zip(E["Learned"], E[c]))
    T[c] = dict(learned_only=b, comparator_only=d, p_one_sided=sign_p(b, d))
L = S["Learned"]
G = dict(more_than_hand=L["correct"] > S["Hand"]["correct"] and T["Hand"]["p_one_sided"] < 0.05,
         more_than_shuffled=L["correct"] > S["Shuffled"]["correct"] and T["Shuffled"]["p_one_sided"] < 0.05,
         false_acceptance_ok=L["false_accept_pct"] <= min(S["Hand"]["false_accept_pct"], S["Shuffled"]["false_accept_pct"]) + 1.0)
G["advantage_retained"] = all(G.values())
G["failure_information_matters"] = T["Shuffled"]["p_one_sided"] < 0.05
json.dump(dict(arms=S, sign_tests=T, rule_G=G), open(ROOT / "artifacts/sc_partg.json", "w"), indent=1)
print("| growth rule (fallback disabled) | correct (95 % CI) | ≤500 / 1k / 2k / 4k | wrong among accepted (95 % CI) | abstain | queries | CPU s |")
print("|---|---|---|---|---|---|---|")
for n, d in S.items():
    print(f"| {n} | {d['correct']}/300 = {d['correct_pct']} % ({d['solve_ci'][0]}–{d['solve_ci'][1]}) | {' / '.join(str(d['curve'][b]) for b in BUDGETS)} | "
          f"{d['silent']}/{d['accepted']} = {d['false_accept_pct']} % ({d['false_accept_ci'][0]}–{d['false_accept_ci'][1]}); {d['silent_out_of_alphabet']} out of scope | "
          f"{d['abstain']} | {d['queries']:,} | {d['cpu_s']} |")
print("sign tests:", json.dumps(T))
print("rule G:", json.dumps(G))
