"""Step 3 / Step 4 analysis (NOT LOCKED): joint metrics, learning curves, paired sign tests and the pre-registered rules S3, S4
(docs/NEXUS_BOUNDED_ACCEPTANCE_AND_GROWTH_REPORT.md §0.5-0.6). Writes artifacts/ba_step4.json; prints the tables."""
import collections, json, math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba_summ import summ, BUDGETS
ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/ba_dev"
ARMS = [("Learned_Growth_Rule", "learned", "bounded"), ("Shuffled_Growth_Rule", "shuffled", "bounded"),
        ("Hand_Designed_Growth_Rule", "hand", "bounded"), ("Random_Growth_Rule", "random", "bounded"),
        ("Hand + coverage acceptance (c84fc76 check)", "hand", "coverage")]


def eps(arm, acc):
    return [json.loads(l) for l in (ART / f"eps_{arm}_{acc}_ep_held2_0.jsonl").read_text().splitlines() if l.strip()]


def energy(arm, acc):
    p = ART / f"energy_{arm}_{acc}_edev2.json"
    return json.loads(p.read_text()) if p.exists() else None


def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def main():
    E = {name: eps(a, acc) for name, a, acc in ARMS}
    for v in E.values():
        v.sort(key=lambda r: r["seed"])
    assert len({tuple(r["seed"] for r in v) for v in E.values()}) == 1 and all(len(v) == 300 for v in E.values())
    S = {name: summ(v) for name, v in E.items()}
    EN = {name: energy(a, acc) for name, a, acc in ARMS}
    SE = {name: (summ(v) if v else None) for name, v in EN.items()}
    L, comps = "Learned_Growth_Rule", ["Hand_Designed_Growth_Rule", "Random_Growth_Rule", "Shuffled_Growth_Rule"]
    tests = {}
    for c in comps:
        b = sum(x["exact"] and not y["exact"] for x, y in zip(E[L], E[c]))
        d = sum(y["exact"] and not x["exact"] for x, y in zip(E[L], E[c]))
        tests[c] = dict(learned_only=b, comparator_only=d, p_one_sided=round(sign_p(b, d), 5))
    s4 = dict(
        c1_more_solves_and_sign_test=all(S[L]["correct"] > S[c]["correct"] and tests[c]["p_one_sided"] < 0.05 for c in comps),
        c2_false_acceptance=S[L]["false_accept_pct"] <= min(S[c]["false_accept_pct"] for c in comps) + 1.0,
        c3_energy=bool(SE[L]) and all(SE[L]["correct"] >= SE[c]["correct"] for c in comps) and SE[L]["silent"] <= SE["Hand_Designed_Growth_Rule"]["silent"],
        c4_curve=all(sum(S[L]["curve"][b] >= S[c]["curve"][b] for b in BUDGETS) >= 3 for c in comps))
    s4["promoted"] = all(s4.values())
    H, C = S["Hand_Designed_Growth_Rule"], S["Hand + coverage acceptance (c84fc76 check)"]
    s3 = dict(fa_bounded=H["false_accept_pct"], fa_coverage=C["false_accept_pct"],
              a_false_acceptance=H["false_accept_pct"] <= 3.0 and H["false_accept_pct"] <= C["false_accept_pct"] / 3,
              b_coverage=H["correct"] >= C["correct"] - 6)
    s3["passed"] = s3["a_false_acceptance"] and s3["b_coverage"]
    # analysis: what the growth rules do
    acts = {n: collections.Counter(a for r in v for a in r["actions"]) for n, v in E.items()}
    first = {n: collections.Counter(r["actions"][0] if r["actions"] else "none" for r in v) for n, v in E.items()}
    steps = {n: round(sum(r["steps"] for r in v) / len(v), 3) for n, v in E.items()}
    scope = {n: sum(r["silent"] and r["regime"] == "new_kind" for r in v) for n, v in E.items()}
    out = dict(micro=S, energy=SE, sign_tests=tests, S3=s3, S4=s4, actions=acts, first_action=first, mean_steps=steps,
               silent_new_kind_regime=scope, energy_rows={n: v for n, v in EN.items()})
    (ROOT / "artifacts/ba_step4.json").write_text(json.dumps(out, indent=1, default=str))
    hdr = "| arm | correct autonomous solves | accepted | silent | false acceptance among accepted | abstain | queries | CPU s | curve ≤500 / 1k / 2k / 4k |"
    for title, T in (("micro-episodes (ba/ep_held2, 300 fresh)", S), ("energy builds (ba/edev2, 12 fresh)", SE)):
        print(f"\n{title}\n{hdr}\n|---|---|---|---|---|---|---|---|---|")
        for n, d in T.items():
            if d:
                print(f"| {n} | {d['correct']} ({d['correct_pct']} %) | {d['accepted']} | {d['silent']} ({d['silent_pct']} %) | {d['false_accept_pct']} % | "
                      f"{d['abstain']} ({d['abstain_pct']} %) | {d['queries']:,} | {d['cpu_s']} | {' / '.join(str(d['curve'][b]) for b in BUDGETS)} |")
    print("\nsign tests (Learned vs X):", json.dumps(tests))
    print("S3:", json.dumps(s3))
    print("S4:", json.dumps(s4))
    print("mean growth steps:", json.dumps(steps))
    print("first action:", json.dumps({k: dict(v) for k, v in first.items()}))
    print("silent in new_kind regime:", json.dumps(scope))


if __name__ == "__main__":
    main()
