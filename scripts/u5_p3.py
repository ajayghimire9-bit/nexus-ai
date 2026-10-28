"""Pillar 3 dev experiment (NOT LOCKED).  python scripts/u5_p3.py wake | admit | eval ARM | final
wake:  the promoted Pillar 2 learner solves SRC_TRAIN (hybrid, 4 s/task); candidates = generalised sub-programs of ITS OWN
       solutions (u5_library.candidates; >= 2 uses). This discovery CPU is charged to both learned-library arms.
admit: mdl = greedy compression of the src corpus; utility = greedy forward selection by measured search utility on ADM
       (L + C families, tadm 0-1; 28 tasks; 2 s/task; top 10 candidates by uses; admission CPU charged).
eval:  ARM in none | mdl | utility on DEV (selection) and HELD (report only; IoT = unseen domain), 4 s/task.
Promotion (predeclared): most DEV generalising solves; <= 1 solve = tie, broken by charged CPU (DEV search CPU +
discovery + admission) if it differs by >= 10%, else the simpler arm (none < mdl < utility). An arm whose DEV wrong
generalisations exceed none's by > 1 is not eligible."""
import sys, time
from u5_common import SRC_TRAIN, ADM, DEV, HELD, K, save, load, node_dump, node_load, learner_cfg, eval_suite
from nexus import u5_library as LB

P = load("p2_policy.json")
pol = load("p2.json")["promoted"]
cfg = learner_cfg(pol, P)
cmd = sys.argv[1]
if cmd == "wake":
    c0 = time.process_time()
    sols = []
    for t in SRC_TRAIN():
        node, st, _ = K.solve_hybrid(t.train, t.y_train, cfg, budget_s=4.0)
        if node is not None:
            sols.append(node)
    cands = LB.candidates(sols)
    save("p3_wake.json", dict(policy=pol, solutions=[node_dump(n) for n in sols], n_candidates=len(cands),
                              cpu_s=round(time.process_time() - c0, 3)))
    print("wake solved", len(sols), "candidates", len(cands))
elif cmd == "admit":
    w = load("p3_wake.json")
    sols = [node_load(s) for s in w["solutions"]]
    cands = LB.candidates(sols)
    c0 = time.process_time()
    mdl = LB.admit_mdl(sols, cands)
    mdl_cpu = time.process_time() - c0
    util, log, util_cpu = LB.admit_utility(cands, ADM(), cfg, 2.0, top_k=10, max_s=700.0)
    save("p3_libs.json", dict(mdl=[[f, p, node_dump(b)] for f, p, b in mdl], utility=[[f, p, node_dump(b)] for f, p, b in util],
                              mdl_cpu_s=round(mdl_cpu, 3), utility_cpu_s=round(util_cpu, 3), utility_log=log,
                              mdl_source=LB.lib_source(mdl), utility_source=LB.lib_source(util)))
    print("mdl", len(mdl), "utility", len(util), "cpu", round(mdl_cpu, 2), round(util_cpu, 1))
elif cmd == "eval":
    arm = sys.argv[2]
    libs = load("p3_libs.json")
    lib = [] if arm == "none" else [(f, p, node_load(b)) for f, p, b in libs[arm]]
    out = dict(arm=arm, dev=eval_suite(DEV(), cfg, lib), held=eval_suite(HELD(), cfg, lib))
    save(f"p3_eval_{arm}.json", out)
    print(arm, "dev", out["dev"]["correct"], "held", out["held"]["correct"], "cpu", out["dev"]["cpu_s"], out["held"]["cpu_s"])
else:
    libs, w = load("p3_libs.json"), load("p3_wake.json")
    ev = {a: load(f"p3_eval_{a}.json") for a in ("none", "mdl", "utility")}
    charged = {a: ev[a]["dev"]["cpu_s"] + (0 if a == "none" else w["cpu_s"] + libs[f"{a}_cpu_s"]) for a in ev}
    elig = [a for a in ("none", "mdl", "utility")
            if ev[a]["dev"]["wrong_generalisation"] <= ev["none"]["dev"]["wrong_generalisation"] + 1]
    best = "none"
    for a in elig[1:] if elig[0] == "none" else elig:
        dc = ev[a]["dev"]["correct"] - ev[best]["dev"]["correct"]
        if dc > 1 or (abs(dc) <= 1 and charged[a] <= 0.9 * charged[best]):
            best = a
    save("p3.json", dict(promoted=best, charged_dev_cpu_s=charged, eligible=elig,
                         table={a: dict(dev=ev[a]["dev"]["correct"], dev_wrong=ev[a]["dev"]["wrong_generalisation"], dev_cpu=ev[a]["dev"]["cpu_s"],
                                        held=ev[a]["held"]["correct"], held_wrong=ev[a]["held"]["wrong_generalisation"], held_cpu=ev[a]["held"]["cpu_s"],
                                        n_fns=0 if a == "none" else len(libs[a])) for a in ev}))
    print("PROMOTED", best, charged)
