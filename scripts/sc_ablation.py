"""Part S dev ablation table (NOT LOCKED) from artifacts/sc_dev/ablation/p<seed>_<arm>.json. Writes artifacts/sc_ablation.json."""
import collections, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("SchemaRepair_Learned", "SchemaRepair_Hand", "SchemaRepair_Shuffled", "NoMapping_Learned", "Fixed_Policy")
R = {}
for p in sorted((ROOT / "artifacts/sc_dev/ablation").glob("p*_*.json")):
    d = json.loads(p.read_text())
    R[(d["seed"], d["arm"])] = d["result"]
tab, per = {}, collections.defaultdict(dict)
for a in ARMS:
    rs = [r for (s, x), r in R.items() if x == a]
    f = [r.get("fields", {}) for r in rs]
    src = collections.Counter()
    for r in rs:
        ss = r.get("solution_sources") or {}
        if ss.get("build"):
            src["build:" + ss["build"]] += 1
        for x in ss.get("relearns", []):
            src["relearn:" + str(x)] += 1
        for x in ss.get("mapping", []):
            src["mapping:" + x] += 1
    tab[a] = dict(n=len(rs), independently_correct=sum(r["independently_correct"] for r in rs), data_ok=sum(r["data_ok"] for r in rs),
                  incorrect_healthy_claim=sum(x.get("incorrect_healthy_claim", False) for x in f),
                  wrong_machine_deployed=sum(x.get("wrong_machine_deployed", False) for x in f),
                  schema_fault_detected=f"{sum(bool(x.get('schema_fault') and x.get('schema_alarm_tick') is not None) for x in f)}/{sum(bool(x.get('schema_fault')) for x in f)}",
                  schema_fault_missed=sum(x.get("schema_fault_missed", False) for x in f),
                  unresolved_escalations=sum(r.get("human_repairs", 0) for r in rs),
                  human_repair_failed=sum(x.get("human_repair_failed", False) for x in f),
                  crash_identical=f"{sum(r.get('crash_ok') is True for r in rs)}/{sum(r.get('crash_ok') is not None for r in rs)}",
                  abstain=sum(r["outcome"] == "ABSTAIN" for r in rs), timed_out=sum(r["outcome"] == "TIMED_OUT" for r in rs),
                  crashed=sum(r["outcome"] == "CRASHED" for r in rs), sources=dict(src),
                  mq=sum((r.get("cost") or {}).get("queries", {}).get("mq", 0) for r in rs),
                  incident_labels=sum((r.get("cost") or {}).get("queries", {}).get("incident", 0) for r in rs),
                  cpu_s=round(sum((r.get("cost") or {}).get("build_cpu_s", 0) + (r.get("cost") or {}).get("ops_cpu_s", 0) for r in rs), 1))
    for (s, x), r in R.items():
        if x == a:
            per[(s, r["fault"], r["domain"])][a] = ("CORRECT" if r["independently_correct"] else "SILENT" if r.get("silent") else
                                                   r["outcome"] + ("/human" + str(r["human_repairs"]) if r.get("human_repairs") else "")
                                                   + ("/data_ok" if r["data_ok"] else "/bad"))
json.dump(dict(arms=tab, projects={f"{k[0]} {k[1]} {k[2]}": v for k, v in sorted(per.items())}), open(ROOT / "artifacts/sc_ablation.json", "w"), indent=1)
print("| arm | indep. correct | data correct | incorrect healthy claim | wrong machine deployed | schema fault detected | escalations (human) | human repair failed | crash identical | abstain | sources | mq | CPU s |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for a, t in tab.items():
    print(f"| {a} | {t['independently_correct']}/{t['n']} | {t['data_ok']} | {t['incorrect_healthy_claim']} | {t['wrong_machine_deployed']} | {t['schema_fault_detected']} | "
          f"{t['unresolved_escalations']} | {t['human_repair_failed']} | {t['crash_identical']} | {t['abstain']} | {t['sources']} | {t['mq']:,} | {t['cpu_s']} |")
print()
for k, v in sorted(per.items()):
    print(k, v)
