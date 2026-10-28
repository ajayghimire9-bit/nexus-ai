"""x7 validation gate / confirmation scorecard (NOT LOCKED).  python scripts/x7_score.py val|val_b|test
val / val_b: gate.json - PASSED iff Expression_Learned is independently correct 8/8 with 0 incorrect healthy claims, 0 human
             repairs and crash recovery identical 8/8 (pre-registered, report section 0.6).
test: scorecard.json - the pre-registered decision rules 1-4 (full system, expression beyond FieldOnly, growth policy,
      coverage vs cost)."""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("Expression_Learned", "FieldOnly_Learned", "Expression_Hand", "Expression_Shuffled", "Frozen_SC", "Fixed_Policy", "Conventional")
CPU_B = (5, 10, 20, 40, 80, 160)
MQ_B = (1000, 2000, 4000, 8000, 16000)


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def sign_p(a_only, b_only):
    n = a_only + b_only
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(a_only, n + 1)) / 2 ** n


def cpu(r):
    c = r.get("cost") or {}
    if "build_B_cpu_s" in c:
        return (c.get("build_B_cpu_s") or 0) + (c.get("ops_cpu_s") or 0)
    return (c.get("build_cpu_s") or 0) + (c.get("ops_cpu_s") or 0)


def mq(r):
    return ((r.get("cost") or {}).get("queries") or r.get("queries") or {}).get("mq", 0)


def cell(r):
    if r is None:
        return None
    if r.get("independently_correct"):
        return "CORRECT"
    if r.get("silent"):
        return "SILENT"
    s = r.get("outcome", "?")
    if r.get("human_repairs"):
        s += f"/human{r['human_repairs']}"
    return s + ("/data_ok" if r.get("data_ok") else "/bad")


def main():
    split = sys.argv[1]
    n = 16 if split == "test" else 8
    d = ROOT / f"artifacts/x7_{split}"
    R = {}
    for k in range(n):
        for a in ARMS:
            f = d / f"p{k}_{a}.json"
            R[(k, a)] = json.loads(f.read_text())["result"] if f.exists() else None
    arms = [a for a in ARMS if any(R[(k, a)] for k in range(n))]
    tab = {}
    for a in arms:
        ev = [R[(k, a)] for k in range(n) if R[(k, a)] is not None]
        f = [r.get("fields", {}) for r in ev]
        ic = sum(bool(r.get("independently_correct")) for r in ev)
        tab[a] = dict(evaluated=len(ev), independently_correct=ic, wilson95=wilson(ic, n), data_ok=sum(bool(r.get("data_ok")) for r in ev),
                      silent=sum(bool(r.get("silent")) for r in ev), human_repairs=sum(r.get("human_repairs", 0) or 0 for r in ev),
                      abstain=sum(r.get("outcome") == "ABSTAIN" for r in ev),
                      timeouts_crashes=sum(r.get("outcome") not in ("COMPLETED", "ABSTAIN") for r in ev),
                      wrong_machine_deployed=sum(bool(x.get("wrong_machine_deployed")) for x in f),
                      wrong_accepted_adapters=sum(x.get("wrong_accepted_adapters", 0) or 0 for x in f),
                      schema_detected=f"{sum(bool(x.get('schema_fault') and x.get('first_B_alarm_tick') is not None) for x in f)}/{sum(bool(x.get('schema_fault')) for x in f)}",
                      detection_delay=[x.get("detection_delay_ticks") for x in f if x.get("schema_fault")],
                      recovery_delay=[x.get("recovery_delay_ticks") for x in f if x.get("schema_fault")],
                      crash_identical=f"{sum(r.get('crash_ok') is True for r in ev)}/{sum(r.get('crash_ok') is not None for r in ev)}",
                      cpu_s=round(sum(cpu(r) for r in ev), 1), mq=sum(mq(r) for r in ev),
                      stages={s: sum(s in (r.get("solution_sources") or {}).get("stages", []) for r in ev)
                              for s in ("field selection", "expression synthesis", "lifecycle relearning", "lifecycle relearning (with adapter)",
                                        "shape verified benign", "human assistance", "build only")},
                      by_fault={x: f"{sum(bool(r.get('independently_correct')) for r in ev if r['fault'] == x)}/{sum(r['fault'] == x for r in ev)}"
                                for x in sorted({r['fault'] for r in ev})},
                      by_domain={x: f"{sum(bool(r.get('independently_correct')) for r in ev if r['domain'] == x)}/{sum(r['domain'] == x for r in ev)}"
                                 for x in sorted({r['domain'] for r in ev})})
    per = []
    for k in range(n):
        r0 = next((R[(k, a)] for a in arms if R[(k, a)]), {})
        per.append(dict(index=k, seed=r0.get("project"), domain=r0.get("domain"), fault=r0.get("fault"), **{a: cell(R[(k, a)]) for a in arms}))
    A = "Expression_Learned"
    ic = lambda k, a: bool(R[(k, a)] and R[(k, a)].get("independently_correct"))        # noqa: E731
    c = tab[A]
    crash_ok = all(R[(k, A)] and R[(k, A)].get("crash_ok") is True for k in range(n))
    full = c["evaluated"] == n and c["independently_correct"] == n and c["silent"] == 0 and c["human_repairs"] == 0 and crash_ok
    out = dict(split=split, n=n, arms=tab, projects=per)
    if split != "test":
        out["passed"] = full
        (d / "gate.json").write_text(json.dumps(out, indent=1, default=str))
    else:
        rules = {"1_full_system": dict(passed=full)}
        if "FieldOnly_Learned" in arms:
            x7 = [k for k in range(n) if R[(k, A)] and R[(k, A)]["fault"] in ("X7a", "X7b")]
            reg = [k for k in range(n) if k not in x7]
            a_only = sum(ic(k, A) and not ic(k, "FieldOnly_Learned") for k in range(n))
            b_only = sum(ic(k, "FieldOnly_Learned") and not ic(k, A) for k in range(n))
            ax7, bx7 = sum(ic(k, A) for k in x7), sum(ic(k, "FieldOnly_Learned") for k in x7)
            b_where_not_a = sum(ic(k, "FieldOnly_Learned") and not ic(k, A) for k in x7)
            areg, breg = sum(ic(k, A) for k in reg), sum(ic(k, "FieldOnly_Learned") for k in reg)
            p = sign_p(a_only, b_only)
            verdict = ("SUPPORTED" if ax7 - bx7 >= 5 and b_where_not_a == 0 and areg >= breg and p <= 0.05 else
                       "REJECTED" if ax7 <= bx7 else "INCONCLUSIVE")
            rules["2_expression_beyond_field_only"] = dict(A_x7=ax7, B_x7=bx7, A_regression=areg, B_regression=breg, A_only=a_only, B_only=b_only,
                                                           sign_p_one_sided=p, verdict=verdict)
        g = {}
        for o in ("Expression_Hand", "Expression_Shuffled"):
            if o in arms:
                a_only = sum(ic(k, A) and not ic(k, o) for k in range(n))
                o_only = sum(ic(k, o) and not ic(k, A) for k in range(n))
                p = sign_p(a_only, o_only)
                g[o] = dict(A=tab[A]["independently_correct"], other=tab[o]["independently_correct"], A_only=a_only, other_only=o_only, sign_p_one_sided=p,
                            A_cpu_s=tab[A]["cpu_s"], other_cpu_s=tab[o]["cpu_s"], A_mq=tab[A]["mq"], other_mq=tab[o]["mq"],
                            verdict="SUPPORTED" if p <= 0.05 else "INCONCLUSIVE" if a_only >= o_only else "REJECTED")
        rules["3_growth_policy"] = g
        cov = {}
        for a in arms:
            ev = [R[(k, a)] for k in range(n) if R[(k, a)]]
            cov[a] = dict(cpu={b: sum(bool(r.get("independently_correct")) and cpu(r) <= b for r in ev) for b in CPU_B},
                          mq={b: sum(bool(r.get("independently_correct")) and mq(r) <= b for r in ev) for b in MQ_B})
        rules["4_coverage_vs_cost"] = cov
        out["rules"] = rules
        out["passed"] = full
        (d / "scorecard.json").write_text(json.dumps(out, indent=1, default=str))
    print("| arm | evaluated | independently correct (95% CI) | silent | data correct | human | abstain | t/o-crash | wrong machine | schema detected | crash identical | CPU s | mq | by fault |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a, t in tab.items():
        print(f"| {a} | {t['evaluated']}/{n} | {t['independently_correct']} ({t['wilson95']}) | {t['silent']} | {t['data_ok']} | {t['human_repairs']} | {t['abstain']} | "
              f"{t['timeouts_crashes']} | {t['wrong_machine_deployed']} | {t['schema_detected']} | {t['crash_identical']} | {t['cpu_s']} | {t['mq']} | {t['by_fault']} |")
    print()
    print("| idx | seed | domain | fault | " + " | ".join(arms) + " |")
    print("|---" * (4 + len(arms)) + "|")
    for p in per:
        print(f"| {p['index']} | {p['seed']} | {p['domain']} | {p['fault']} | " + " | ".join(str(p.get(a)) for a in arms) + " |")
    print("PASSED" if out["passed"] else "NOT PASSED")
    if split == "test":
        print(json.dumps(out["rules"], indent=1, default=str))


if __name__ == "__main__":
    main()
