"""sc validation gate / confirmation scorecard (NOT LOCKED).  python scripts/sc_score.py val|val_b|test
val / val_b: gate.json - PASSED iff NEXUS_Confirmed is independently correct on 8/8 with 0 incorrect healthy claims.
test: scorecard.json - full-system criterion: 16/16 independently correct, 0 silent, 0 human repairs, crash recovery identical."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("NEXUS_Confirmed", "NEXUS_U5", "Fixed_Policy", "Conventional")
split = sys.argv[1]
n = 16 if split == "test" else 8
d = ROOT / f"artifacts/sc_{split}"
R = {(k, a): (json.loads((d / f"p{k}_{a}.json").read_text())["result"] if (d / f"p{k}_{a}.json").exists() else None)
     for k in range(n) for a in ARMS}
tab = {}
for a in ARMS:
    ev = [R[(k, a)] for k in range(n) if R[(k, a)] is not None]
    f = [r.get("fields", {}) for r in ev]
    tab[a] = dict(evaluated=len(ev), independently_correct=sum(r["independently_correct"] for r in ev), data_ok=sum(r["data_ok"] for r in ev),
                  silent=sum(r.get("silent", False) for r in ev), human_repairs=sum(r.get("human_repairs", 0) for r in ev),
                  wrong_machine_deployed=sum(x.get("wrong_machine_deployed", False) for x in f),
                  schema_detected=f"{sum(bool(x.get('schema_fault') and x.get('schema_alarm_tick') is not None) for x in f)}/{sum(bool(x.get('schema_fault')) for x in f)}",
                  schema_missed=sum(x.get("schema_fault_missed", False) for x in f), human_repair_failed=sum(x.get("human_repair_failed", False) for x in f),
                  crash_identical=f"{sum(r.get('crash_ok') is True for r in ev)}/{sum(r.get('crash_ok') is not None for r in ev)}",
                  timed_out=sum(r["outcome"] == "TIMED_OUT" for r in ev), crashed=sum(r["outcome"] == "CRASHED" for r in ev),
                  by_fault={x: f"{sum(r['independently_correct'] for r in ev if r['fault'] == x)}/{sum(r['fault'] == x for r in ev)}" for x in sorted({r['fault'] for r in ev})},
                  by_domain={x: f"{sum(r['independently_correct'] for r in ev if r['domain'] == x)}/{sum(r['domain'] == x for r in ev)}" for x in sorted({r['domain'] for r in ev})})
per = []
for k in range(n):
    r0 = next((R[(k, a)] for a in ARMS if R[(k, a)]), {})
    per.append(dict(index=k, seed=r0.get("project"), domain=r0.get("domain"), fault=r0.get("fault"),
                    **{a: None if R[(k, a)] is None else ("CORRECT" if R[(k, a)]["independently_correct"] else "SILENT" if R[(k, a)].get("silent")
                       else R[(k, a)]["outcome"] + (f"/human{R[(k, a)]['human_repairs']}" if R[(k, a)].get("human_repairs") else "")
                       + ("/data_ok" if R[(k, a)]["data_ok"] else "/bad")) for a in ARMS}))
c = tab["NEXUS_Confirmed"]
crash_ok = all(R[(k, "NEXUS_Confirmed")] and R[(k, "NEXUS_Confirmed")].get("crash_ok") is not False for k in range(n))
ok = c["evaluated"] == n and c["independently_correct"] == n and c["silent"] == 0 and (split != "test" or (c["human_repairs"] == 0 and crash_ok))
json.dump(dict(split=split, n=n, arms=tab, projects=per, passed=ok), open(d / ("scorecard.json" if split == "test" else "gate.json"), "w"), indent=1)
print("| arm | evaluated | independently correct | silent | data correct | human repairs | wrong machine deployed | schema fault detected | schema missed | human repair failed | crash identical | by fault | by domain |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for a, t in tab.items():
    print(f"| {a} | {t['evaluated']}/{n} | {t['independently_correct']} | {t['silent']} | {t['data_ok']} | {t['human_repairs']} | {t['wrong_machine_deployed']} | "
          f"{t['schema_detected']} | {t['schema_missed']} | {t['human_repair_failed']} | {t['crash_identical']} | {t['by_fault']} | {t['by_domain']} |")
for p in per:
    print(p)
print(("criterion" if split == "test" else "gate"), "PASSED" if ok else "NOT MET")
