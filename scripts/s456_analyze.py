"""Stages 4-6 analysis (NOT LOCKED): raw per-project results -> the 7-measure scorecard, Stage 4 / 5 / 6 tables, the drift
detector comparison, and paired project-level effects (ratio of pooled sums, paired bootstrap 95% CI over projects, sign
counts). Pure post-processing.  python scripts/s456_analyze.py RESULTS.json [library.json]"""
import json, math, random, sys
from pathlib import Path

ARMS = ["Conventional_Checked", "NEXUS_Fresh", "NEXUS_Placebo", "NEXUS_Experienced", "Conventional_NoCheck"]
OPDET = "fixed_ratio"


def eng_cpu(a):
    """PRIMARY cost metric: engineering CPU per project = build (agent + every check / repair-search pipeline run + library
    retrieval / applicability / failed reuse) + operations engineering (operator agent CPU + shadow-test CPU). Scheduled
    production runs are identical for all arms and reported separately as operating cost."""
    b = a["build"]["cost"]["total_cpu_s"]
    o = a["ops"].get(OPDET) or a["ops"].get("none") or {}
    oc = o.get("cost", {})
    return b + oc.get("agent_cpu_s", 0.0) + oc.get("shadow_cpu_s", 0.0)


def boot(xs, ys, n=4000, seed=0):
    r = random.Random(seed)
    idx = list(range(len(xs)))
    vals = []
    for _ in range(n):
        s = [r.choice(idx) for _ in idx]
        den = sum(ys[i] for i in s)
        vals.append(sum(xs[i] for i in s) / den if den else float("nan"))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def main(path, lib_path=None):
    R = json.load(open(path))
    P = R["projects"]
    arms = [a for a in ARMS if all(a in p["arms"] for p in P.values())]
    n = len(P)
    rows = {}
    for a in arms:
        xs = [p["arms"][a] for p in P.values()]
        ops = [x["ops"].get(OPDET) or x["ops"].get("none") for x in xs]
        be = [x["build_eval"] for x in xs]
        rows[a] = dict(
            build_correct=sum(bool(e.get("correct")) for e in be), build_silent=sum(bool(e.get("silent")) for e in be),
            heldout_ok=sum(bool(e.get("heldout_ok")) for e in be), eo_fail=sum(e.get("eo_failures", 0) for e in be),
            eo_trials=sum(e.get("eo_trials", 0) for e in be), rollback_ok=sum(bool(e.get("rollback_ok")) for e in be),
            submitted=sum(x["build"]["submitted"] for x in xs), abstain=sum(x["build"]["outcome"].startswith("ABSTAIN") for x in xs),
            hard=sum(x["build"]["outcome"] == "HARD_FAIL" for x in xs),
            ops_correct=sum(o["eval"]["correct"] for o in ops), ops_data=sum(o["eval"]["data_ok"] for o in ops),
            ops_service=sum(o["eval"]["service_restored"] for o in ops), fresh_viol=sum(o["eval"]["freshness_violations"] for o in ops),
            dup=sum(o["eval"]["duplicate_rows"] for o in ops), leaks=sum(o["eval"]["secret_leaks"] for o in ops),
            quarantined=sum(o["eval"]["quarantined"] for o in ops), late=sum(o["eval"]["late"] for o in ops),
            unresolved=sum(1 for o in ops for k, v in o["eval"]["restore_ticks"].items() if v is None),
            clar=sum(o["eval"].get("clarifications", 0) for o in ops), escal=sum(o["cost"].get("escalations", 0) for o in ops),
            eng=[eng_cpu(x) for x in xs], build_cpu=sum(x["build"]["cost"]["total_cpu_s"] for x in xs),
            rejected=sum(x["build"]["cost"]["rejected_cpu_s"] for x in xs), checks=sum(x["build"]["cost"]["check_runs"] for x in xs),
            final_checks=sum(x["build"]["cost"].get("final_check_runs", 0) for x in xs),
            proposals=sum(x["build"]["cost"]["proposals"] for x in xs),
            shadow=sum(o["cost"].get("shadow_tests", 0) for o in ops), shadow_cpu=sum(o["cost"].get("shadow_cpu_s", 0) for o in ops),
            lib_cpu=sum(x["build"]["cost"].get("retrieval_cpu_s", 0) + x["build"]["cost"].get("applicability_cpu_s", 0) +
                        (o["cost"].get("library_retrieval_cpu_s", 0) + o["cost"].get("library_applicability_cpu_s", 0)) for x, o in zip(xs, ops)),
            failed_reuse=sum(x["build"].get("failed_reuse", 0) for x in xs), failed_reuse_cpu=sum(x["build"].get("failed_reuse_cpu_s", 0) for x in xs),
            operating=sum(o["ops_cpu_s"] for o in ops))
    W = 34
    print(f"projects {n}; withheld-class worlds {sum(p['withheld'] for p in P.values())}")
    print("measure | metric | " + " | ".join(a[:W] for a in arms))
    def line(m, lab, f):
        print(f"{m:16s} {lab:46s} | " + " | ".join(f"{f(rows[a])!s:>{min(W, len(a))}}" for a in arms))
    line("1 Correctness", "build independently correct (ckpt+EO+rollback)", lambda r: f"{r['build_correct']}/{n}")
    line("", "build silent errors (submitted, wrong)", lambda r: r["build_silent"])
    line("", "held-out ticks 9-12 correct", lambda r: f"{r['heldout_ok']}/{n}")
    line("", "ops: final data correct", lambda r: f"{r['ops_data']}/{n}")
    line("", "quarantined / late records (visible)", lambda r: f"{r['quarantined']}/{r['late']}")
    line("2 Completion", "build submitted / abstained / hard fail", lambda r: f"{r['submitted']}/{r['abstain']}/{r['hard']}")
    line("", "incidents unresolved at end", lambda r: r["unresolved"])
    line("3 Reliability", "exactly-once crash trials failed / run", lambda r: f"{r['eo_fail']}/{r['eo_trials']}")
    line("", "rollback drill ok", lambda r: f"{r['rollback_ok']}/{n}")
    line("", "ops service restored at end", lambda r: f"{r['ops_service']}/{n}")
    line("", "freshness violations (ticks)", lambda r: r["fresh_viol"])
    line("", "duplicate rows / secret leaks", lambda r: f"{r['dup']}/{r['leaks']}")
    line("4 Cost", "PRIMARY engineering CPU s (sum)", lambda r: f"{sum(r['eng']):.1f}")
    line("", "build CPU s / rejected+search CPU s", lambda r: f"{r['build_cpu']:.1f}/{r['rejected']:.1f}")
    line("", "check runs (all) / final accepted suite", lambda r: f"{r['checks']}/{r['final_checks']}")
    line("", "proposals / ops shadow tests", lambda r: f"{r['proposals']}/{r['shadow']}")
    line("", "library retrieval+applicability CPU s", lambda r: f"{r['lib_cpu']:.3f}")
    line("", "failed reuse (count / CPU s)", lambda r: f"{r['failed_reuse']}/{r['failed_reuse_cpu']:.1f}")
    line("", "operating CPU s (ops harness incl. runs)", lambda r: f"{r['operating']:.1f}")
    line("5 Human dep.", "clarifications / escalations / repairs", lambda r: f"{r['clar']}/{r['escal']}/0")
    if "NEXUS_Fresh" in rows:
        f = rows["NEXUS_Fresh"]["eng"]
        for other in ("NEXUS_Experienced", "NEXUS_Placebo"):
            if other in rows:
                x = rows[other]["eng"]
                lo, hi = boot(x, f)
                wins = sum(a < b for a, b in zip(x, f))
                print(f"6 Learning       {other} / NEXUS_Fresh engineering CPU = {sum(x) / sum(f):.3f} (95% CI {lo:.3f}-{hi:.3f}); "
                      f"cheaper in {wins}/{n} projects")
        if "NEXUS_Experienced" in rows and "NEXUS_Placebo" in rows:
            x, y = rows["NEXUS_Experienced"]["eng"], rows["NEXUS_Placebo"]["eng"]
            lo, hi = boot(x, y)
            print(f"6 Learning       NEXUS_Experienced / NEXUS_Placebo = {sum(x) / sum(y):.3f} (95% CI {lo:.3f}-{hi:.3f}); "
                  f"cheaper in {sum(a < b for a, b in zip(x, y))}/{n}")
        if lib_path:
            L = json.load(open(lib_path))
            lc = L["learning_cost"]
            learn = lc["source_curriculum_cpu_s"] + lc["loo_maintenance_cpu_s"]
            save = (sum(f) - sum(rows["NEXUS_Experienced"]["eng"])) / n
            print(f"6 Learning       library construction CPU {learn:.1f} s (source curriculum {lc['source_curriculum_cpu_s']:.1f} + "
                  f"LOO maintenance {lc['loo_maintenance_cpu_s']:.1f}); saving/project {save:.2f} s; break-even "
                  f"{(learn / save) if save > 0 else float('inf'):.1f} projects; total incl. learning "
                  f"{(sum(rows['NEXUS_Experienced']['eng']) + learn) / sum(f):.3f}x Fresh over these {n} projects")
    w = [p for p in P.values() if p["withheld"]]
    if w:
        for a in arms:
            print(f"7 Generalization {a}: withheld-class worlds build correct {sum(bool(p['arms'][a]['build_eval'].get('correct')) for p in w)}/{len(w)}, "
                  f"ops correct {sum((p['arms'][a]['ops'].get(OPDET) or p['arms'][a]['ops'].get('none'))['eval']['correct'] for p in w)}/{len(w)}")
    det = {}
    for p in P.values():
        fr = p["arms"].get("NEXUS_Fresh", {}).get("ops", {})
        for d, o in fr.items():
            x = det.setdefault(d, dict(correct=0, n=0, alarms=0, true=0, delay=[], cpu=0.0))
            x["n"] += 1; x["correct"] += o["eval"]["correct"]; x["cpu"] += o.get("detector_cpu_s", 0.0)
            shifts = {(s["supplier"]) for s in o.get("unit_shift", [])}
            for al in o.get("alarms", []):
                if al.get("trigger") in (d, None):
                    x["alarms"] += 1
                    if al["supplier"] in shifts:
                        x["true"] += 1
                        st = next(s["tick"] for s in o["unit_shift"] if s["supplier"] == al["supplier"])
                        x["delay"].append(al["tick"] - st)
    if det:
        print("drift detectors (NEXUS_Fresh ops; every variant also has the producer-metadata trigger):")
        for d, x in det.items():
            print(f"   {d:18s} ops correct {x['correct']}/{x['n']}  detector alarms {x['alarms']} (on shifted suppliers {x['true']}, "
                  f"false {x['alarms'] - x['true']})  mean delay {sum(x['delay']) / len(x['delay']) if x['delay'] else float('nan'):.1f} ticks  "
                  f"detector CPU {x['cpu']:.3f} s")
    return rows


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
