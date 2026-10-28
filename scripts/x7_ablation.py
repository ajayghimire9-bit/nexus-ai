"""x7 development ablation summary (NOT LOCKED; development data only). Reads artifacts/x7_dev/ablation, artifacts/x7_sc_dev/recheck
and the sc ablation (artifacts/sc_dev/ablation, read-only); writes artifacts/x7_ablation.json and prints markdown tables."""
import glob, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ["Expression_Learned", "FieldOnly_Learned", "Expression_Hand", "Expression_Shuffled", "NoPrune_Learned", "NoMapping_Learned"]


def load(pat):
    out = {}
    for f in sorted(glob.glob(str(ROOT / pat))):
        d = json.loads(Path(f).read_text())
        out[(d["seed"], d["arm"])] = d["result"]
    return out


def summ(rs):
    n = len(rs)
    g = lambda k: sum(bool(r.get(k)) for r in rs)                    # noqa: E731
    f = lambda k: sum(bool((r.get("fields") or {}).get(k)) for r in rs)  # noqa: E731
    stages = Counter(s for r in rs for s in (r.get("solution_sources") or {}).get("stages", []))
    cost = [r.get("cost") or {} for r in rs]
    return dict(n=n, independently_correct=g("independently_correct"), data_ok=g("data_ok"), silent=g("silent"),
                human=sum(r.get("human_repairs", 0) or 0 for r in rs), abstain=sum(r.get("outcome") == "ABSTAIN" for r in rs),
                timeouts_crashes=sum(r.get("outcome") not in ("COMPLETED", "ABSTAIN") for r in rs),
                wrong_machine=f("wrong_machine_deployed"), false_schema_incidents=sum((r.get("fields") or {}).get("false_schema_incidents", 0) or 0 for r in rs),
                crash_identical=sum(r.get("crash_ok") is True for r in rs), stages=dict(stages),
                build_B_cpu_s=round(sum(c.get("build_B_cpu_s", 0) or 0 for c in cost), 1),
                ops_cpu_s=round(sum(c.get("ops_cpu_s", 0) or 0 for c in cost), 1),
                mapping_cpu_s=round(sum(c.get("mapping_cpu_s", 0) or 0 for c in cost), 1),
                mq=sum((c.get("queries") or {}).get("mq", 0) for c in cost),
                incident_labels=sum((c.get("queries") or {}).get("incident", 0) for c in cost))


def cls_part(src):
    i = src.find("class StateMachine_")
    j = src.find("\n\n\n# field mapping")
    return src[i:j + 1 if j > 0 else None] if i >= 0 else None


def main():
    dev = load("artifacts/x7_dev/ablation/p*_*.json")
    rc = load("artifacts/x7_sc_dev/recheck/p*_*.json")
    old = load("artifacts/sc_dev/ablation/p*_*.json")
    out = dict(x7_dev={}, sc_recheck={}, per_project=[], pruning=[], helper={}, learner_identity=[])
    for fam in ("XR", "XD1", "XD2", "XD3", "ALL"):
        for a in ARMS:
            rs = [r for (s, arm), r in dev.items() if arm == a and (fam == "ALL" or r.get("fault") == fam)]
            if rs:
                out["x7_dev"][f"{fam}|{a}"] = summ(rs)
    for a in ("Expression_Learned", "FieldOnly_Learned"):
        out["sc_recheck"][a] = summ([r for (s, arm), r in rc.items() if arm == a])
    out["sc_recheck"]["sc_SchemaRepair_Learned_(d23c9fa, stored)"] = summ([r for (s, arm), r in old.items() if arm == "SchemaRepair_Learned"])
    seeds = sorted({s for s, _ in dev} | {s for s, _ in rc})
    for s in seeds:
        row = dict(seed=s)
        for a in ARMS:
            r = dev.get((s, a)) or rc.get((s, a))
            if r:
                row.update(fault=r.get("fault"), domain=r.get("domain"))
                row[a] = ("CORRECT" if r.get("independently_correct") else "SILENT" if r.get("silent") else
                          f"human{r.get('human_repairs')}/{'data_ok' if r.get('data_ok') else 'BAD'}" if r.get("human_repairs") else r.get("outcome"))
                row[a + "_stages"] = (r.get("solution_sources") or {}).get("stages")
                if a == "Expression_Learned":
                    row["adapters"] = [m.get("path") for m in r.get("adapters") or [] if m]
        o = old.get((s, "SchemaRepair_Learned"))
        if o:
            row["sc_d23c9fa"] = "CORRECT" if o.get("independently_correct") else o.get("outcome")
        out["per_project"].append(row)
    for (s, a), r in sorted({**dev, **rc}.items()):
        for x in r.get("log") or []:
            if x.get("step") == "dependencies" and a in ("Expression_Learned", "NoPrune_Learned"):
                rep = x.get("report") or {}
                er = sorted({f for fs in (x.get("emitted_reads") or {}).values() for f in fs})
                out["pruning"].append(dict(seed=s, arm=a, fault=r.get("fault"), emitted_reads=er, live_reads=rep.get("reads_after"),
                                           dead_regs=rep.get("dead_regs"), unbound=rep.get("unbound_fields"),
                                           identity_removed=rep.get("identity_updates_removed"),
                                           sensitivity=(rep.get("sensitivity") or {}).get("disagreeing_events")))
                break
    for s in sorted({s for s, _ in rc}):
        o, n = old.get((s, "SchemaRepair_Learned")), rc.get((s, "Expression_Learned"))
        if not (o and n):
            continue
        dep = next((x for x in n.get("log") or [] if x.get("step") == "dependencies"), {})
        oc = cls_part(o.get("build_source") or "") if o.get("outcome") != "ABSTAIN" else None
        out["learner_identity"].append(dict(seed=s, sc_build=o.get("outcome") != "ABSTAIN", x7_build=n.get("outcome") != "ABSTAIN",
                                            same_unpruned_class=(hashlib.sha256(oc.encode()).hexdigest() == dep.get("unpruned_class_sha256")) if oc else None,
                                            sc_learner=(o.get("solution_sources") or {}).get("build"), x7_learner=(n.get("solution_sources") or {}).get("build"),
                                            x7_build_B_cpu_s=(n.get("cost") or {}).get("build_B_cpu_s")))
    for pat, key in (("artifacts/x7_dev/ablation/p*_HELPER.json", "x7_dev"), ("artifacts/x7_sc_dev/recheck/p*_HELPER.json", "sc_dev"),
                     ("artifacts/x7_pcheck/p*_HELPER.json", "x7_pcheck")):
        hs = [json.loads(Path(f).read_text())["result"] for f in sorted(glob.glob(str(ROOT / pat)))]
        out["helper"][key] = dict(n=len(hs), wrong_rows=sum(h["wrong_rows"] for h in hs), wrong_after_resume=sum(h["wrong_rows_after_resume"] for h in hs),
                                  faults=dict(Counter(h["fault"] for h in hs)),
                                  formats={h["fault"]: sorted(h["late_formats"]) for h in hs})
    (ROOT / "artifacts/x7_ablation.json").write_text(json.dumps(out, indent=1, default=str))
    print("| family | arm | indep correct | silent | human | abstain | t/o-crash | false schema incidents | build_B CPU | ops CPU | mq |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for k, v in out["x7_dev"].items():
        fam, a = k.split("|")
        print(f"| {fam} | {a} | {v['independently_correct']}/{v['n']} | {v['silent']} | {v['human']} | {v['abstain']} | {v['timeouts_crashes']} | "
              f"{v['false_schema_incidents']} | {v['build_B_cpu_s']} | {v['ops_cpu_s']} | {v['mq']} |")
    for k, v in out["sc_recheck"].items():
        print(f"| sc dev 14 | {k} | {v['independently_correct']}/{v['n']} | {v['silent']} | {v['human']} | {v['abstain']} | {v['timeouts_crashes']} | - | "
              f"{v['build_B_cpu_s']} | {v['ops_cpu_s']} | {v['mq']} |")
    print(json.dumps(out["helper"], default=str)[:1500])
    for r in out["learner_identity"]:
        print(r)
    if "-v" in sys.argv:
        for r in out["per_project"]:
            print(r)
        for r in out["pruning"]:
            print(r)


if __name__ == "__main__":
    main()
