"""R1 analysis (NOT LOCKED): raw per-project results -> the corrected 7-measure scorecard (end-to-end primary), build-only
measures, paired project-level comparisons (ratio of pooled sums, paired bootstrap 95% CI over projects, sign counts),
withheld-class detection / repair, the component benchmark, evidence labels. Pure post-processing.
  python scripts/r1_analyze.py RESULTS.json [r1_library.json]"""
import json, random, sys
from pathlib import Path

ARMS = ["Conventional_Checked", "Fixed_Policy", "NEXUS_Fresh", "NEXUS_Placebo", "NEXUS_Experienced"]
X_DEC = {"X1": ("txn_isolation", "read_committed"), "X2": ("gap_handling", "wait_contiguous")}


def eng_cpu(a):
    """Fully loaded engineering CPU: build agent + every check / search run + library retrieval / applicability / failed
    reuse, + operator agent (incl. reconciliation, localisation, CEGIS bookkeeping) + every shadow / mini-trace run."""
    o = (a["ops"] or {"cost": {}})["cost"]
    return a["build"]["cost"]["total_cpu_s"] + o.get("agent_cpu_s", 0.0) + o.get("shadow_cpu_s", 0.0)


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


def x_status(p, a):
    """For a withheld-class world: did the DEPLOYED pipeline mishandle its class; was that self-detected; repaired?"""
    xc = p.get("x_class")
    if not xc or not a["ops"]:
        return None
    d, good = X_DEC[xc]
    deployed = a["build"]["final_choice"].get(d)
    redeploys = [x[1] for x in a["ops"]["actions"] if x[0] == "redeploy"]
    final = redeploys[-1].get(d) if redeploys and d in redeploys[-1] else deployed
    led = a["ops"]["ledger"]
    flagged = any(e["kind"] in ("own_pipeline_localised", "own_pipeline_unrepaired", "escalated", "applied_not_reconciled")
                  for e in led) or bool(redeploys)
    return dict(cls=xc, mishandled=deployed != good, self_detected=flagged if deployed != good else None, repaired=final == good,
                e2e=a["e2e_correct"])


def main(path, lib_path=None):
    R = json.load(open(path))
    P = R["projects"]
    arms = [a for a in ARMS if all(a in p["arms"] for p in P.values())]
    n = len(P)
    rows = {}
    for a in arms:
        xs = [p["arms"][a] for p in P.values()]
        ops = [x["ops"] for x in xs]
        be = [x["build_eval"] for x in xs]
        oe = [o["eval"] if o else None for o in ops]
        rows[a] = dict(
            e2e=sum(x["e2e_correct"] for x in xs), build_correct=sum(bool(e.get("correct")) for e in be),
            build_silent=sum(bool(e.get("silent")) for e in be), heldout_ok=sum(bool(e.get("heldout_ok")) for e in be),
            ops_data=sum(bool(e and e["data_ok"]) for e in oe), silent=sum(bool(e and e["silent"]) for e in oe),
            self_detected=sum(bool(e and not e["data_ok"] and (e["open_escalation"] or not e["claims_healthy"])) for e in oe),
            submitted=sum(x["build"]["submitted"] for x in xs), abstain=sum(x["build"]["outcome"].startswith("ABSTAIN") for x in xs),
            hard=sum(x["build"]["outcome"] == "HARD_FAIL" for x in xs),
            labels={l: sum(x["build"]["outcome"] == l for x in xs) for l in sorted({x["build"]["outcome"] for x in xs})},
            open_esc=sum(bool(e and e["open_escalation"]) for e in oe),
            escal=sum((o or {"cost": {}})["cost"].get("escalations", 0) for o in ops),
            clar=sum((e or {}).get("clarifications", 0) for e in oe),
            eo_fail=sum(e.get("eo_failures", 0) for e in be), eo_trials=sum(e.get("eo_trials", 0) for e in be),
            rollback_ok=sum(bool(e.get("rollback_ok")) for e in be),
            service=sum(bool(e and e["service_restored"]) for e in oe), fresh_viol=sum((e or {}).get("freshness_violations", 0) for e in oe),
            dup=sum((e or {}).get("duplicate_rows", 0) for e in oe), leaks=sum((e or {}).get("secret_leaks", 0) for e in oe),
            eng=[eng_cpu(x) for x in xs], build_cpu=sum(x["build"]["cost"]["total_cpu_s"] for x in xs),
            ops_cpu=sum(((o or {"cost": {}})["cost"].get("agent_cpu_s", 0.0) + (o or {"cost": {}})["cost"].get("shadow_cpu_s", 0.0)) for o in ops),
            checks=sum(x["build"]["cost"]["check_runs"] for x in xs), shadow=sum((o or {"cost": {}})["cost"].get("shadow_tests", 0) for o in ops),
            own=sum((o or {"cost": {}})["cost"].get("own_repairs", 0) for o in ops),
            fullv=sum((o or {"cost": {}})["cost"].get("full_verifications", 0) for o in ops),
            failed_reuse=sum(x["build"].get("failed_reuse", 0) + (o or {"cost": {}})["cost"].get("failed_reuse", 0) for x, o in zip(xs, ops)),
            lib_cpu=sum(x["build"]["cost"].get("retrieval_cpu_s", 0) + x["build"]["cost"].get("applicability_cpu_s", 0) +
                        (o or {"cost": {}})["cost"].get("library_retrieval_cpu_s", 0) +
                        (o or {"cost": {}})["cost"].get("library_applicability_cpu_s", 0) for x, o in zip(xs, ops)))
    W = 20
    print(f"projects {n}; withheld-class worlds {sum(bool(p.get('x_class')) for p in P.values())}")
    print(f"{'measure':16s} {'metric':52s} | " + " | ".join(f"{a[:W]:>{W}}" for a in arms))

    def line(m, lab, f):
        print(f"{m:16s} {lab:52s} | " + " | ".join(f"{str(f(rows[a])):>{W}}" for a in arms))
    line("1 Correctness", "PRIMARY end-to-end correct (build->own ops->data)", lambda r: f"{r['e2e']}/{n}")
    line("", "silent errors (claims healthy, data wrong)", lambda r: r["silent"])
    line("", "self-detected failures (data wrong, flagged)", lambda r: r["self_detected"])
    line("", "build independently correct (ckpt+EO+rollback)", lambda r: f"{r['build_correct']}/{n}")
    line("", "build silent errors / held-out ticks 9-12 ok", lambda r: f"{r['build_silent']} / {r['heldout_ok']}")
    line("", "ops final data correct (own pipeline)", lambda r: f"{r['ops_data']}/{n}")
    line("2 Completion", "submitted / abstained / hard fail", lambda r: f"{r['submitted']}/{r['abstain']}/{r['hard']}")
    line("", "build labels", lambda r: ",".join(f"{k.split('_')[-1][:5]}{v}" for k, v in r["labels"].items()))
    line("", "open escalation at end", lambda r: r["open_esc"])
    line("3 Reliability", "exactly-once crash trials failed / run", lambda r: f"{r['eo_fail']}/{r['eo_trials']}")
    line("", "rollback drill ok / service restored at end", lambda r: f"{r['rollback_ok']} / {r['service']}")
    line("", "freshness violations (ticks) / dup rows / leaks", lambda r: f"{r['fresh_viol']}/{r['dup']}/{r['leaks']}")
    line("4 Cost", "PRIMARY fully loaded engineering CPU s", lambda r: f"{sum(r['eng']):.1f}")
    line("", "build CPU s / ops engineering CPU s", lambda r: f"{r['build_cpu']:.1f}/{r['ops_cpu']:.1f}")
    line("", "check runs / shadow tests / full verifications", lambda r: f"{r['checks']}/{r['shadow']}/{r['fullv']}")
    line("", "own-pipeline repairs / failed reuse / lib CPU", lambda r: f"{r['own']}/{r['failed_reuse']}/{r['lib_cpu']:.2f}")
    line("5 Human dep.", "clarifications / escalations (all turns)", lambda r: f"{r['clar']}/{r['escal']}")
    pairs = [("NEXUS_Experienced", "NEXUS_Fresh"), ("NEXUS_Experienced", "NEXUS_Placebo"), ("NEXUS_Placebo", "NEXUS_Fresh"),
             ("NEXUS_Fresh", "Fixed_Policy")]
    for x, y in pairs:
        if x in rows and y in rows:
            a, b = rows[x]["eng"], rows[y]["eng"]
            lo, hi = boot(a, b)
            print(f"6 Learning       {x} / {y} fully loaded CPU = {sum(a) / sum(b):.3f} (95% CI {lo:.3f}-{hi:.3f}); "
                  f"cheaper in {sum(u < v for u, v in zip(a, b))}/{n}; e2e {rows[x]['e2e']} vs {rows[y]['e2e']}")
    if lib_path and "NEXUS_Experienced" in rows and "NEXUS_Fresh" in rows:
        L = json.load(open(lib_path))
        lc = L["learning_cost"]
        learn = lc["source_curriculum_cpu_s"] + lc["loo_maintenance_cpu_s"]
        save = (sum(rows["NEXUS_Fresh"]["eng"]) - sum(rows["NEXUS_Experienced"]["eng"])) / n
        print(f"6 Learning       dedicated source learning CPU {learn:.1f} s (curriculum {lc['source_curriculum_cpu_s']:.1f} + LOO "
              f"{lc['loo_maintenance_cpu_s']:.1f}); learning during useful work {lc.get('during_useful_work_cpu_s', 0.0):.1f} s; "
              f"saving/project {save:.2f} s; break-even {(learn / save) if save > 0 else float('inf'):.1f} projects; "
              f"total incl. learning {(sum(rows['NEXUS_Experienced']['eng']) + learn) / sum(rows['NEXUS_Fresh']['eng']):.3f}x Fresh")
    xw = [p for p in P.values() if p.get("x_class")]
    for a in arms:
        st = [x_status(p, p["arms"][a]) for p in xw]
        for cls in ("X1", "X2"):
            s = [x for x in st if x and x["cls"] == cls]
            if not s and not [p for p in xw if p["x_class"] == cls]:
                continue
            k = len([p for p in xw if p["x_class"] == cls])
            mis = [x for x in s if x["mishandled"]]
            print(f"7 Generalization {a:20s} {cls}: worlds {k}, ops run {len(s)}, deployed mishandles {len(mis)}, "
                  f"self-detected {sum(bool(x['self_detected']) for x in mis)}, repaired {sum(x['repaired'] for x in mis)}, "
                  f"e2e correct {sum(x['e2e'] for x in s)}/{k}")
    comp = [p["arms"]["NEXUS_Fresh"]["component"] for p in P.values() if "NEXUS_Fresh" in p["arms"] and p["arms"]["NEXUS_Fresh"].get("component")]
    if comp:
        print(f"component benchmark (NEXUS_Fresh operator, SUPPLIED correct pipeline): ops correct {sum(c['eval']['correct'] for c in comp)}/{len(comp)}, "
              f"silent {sum(c['eval']['silent'] for c in comp)}, escalations {sum(c['cost'].get('escalations', 0) for c in comp)}")
    return rows


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
