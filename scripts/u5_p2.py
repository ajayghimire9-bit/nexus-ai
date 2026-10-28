"""Pillar 2 dev experiment (NOT LOCKED).  python scripts/u5_p2.py train | eval ENGINE | decide
train: NEXUS wakes on SRC_TRAIN (L + C families, tsrc 0-4; 70 tasks) with the BASELINE policy and the hybrid engine
       (4 s per task); count costs and the affinity model are fit on its OWN solved searches only.
eval:  the 3 policies (baseline / count / exec) on DEV (21 families x tdev 0-1; 42 tasks), 4 s per task, primary engine
       hybrid (construction then the unchanged Phase 1 decomposition over the constructed bank), secondary pure
       construction. Every scoring CPU second is inside the per-task CPU.
Promotion (predeclared, hybrid engine): most generalising solves; a difference of <= 1 solve is a tie, broken by total
CPU if it differs by >= 10%; a remaining tie goes to the simpler policy (baseline < count < exec)."""
import sys, time
from u5_common import ART, SRC_TRAIN, DEV, K, W, save, load, node_dump, learner_cfg, eval_suite

if sys.argv[1] == "train":
    c0 = time.process_time()
    sols, samples, rows = [], [], []
    for t in SRC_TRAIN():
        node, st, s = K.solve_hybrid(t.train, t.y_train, K.default_config("baseline"), budget_s=4.0)
        rows.append(dict(task=t.tid, solved=st["solved"], cpu_s=st["cpu_s"], size=st["size"]))
        if node is not None:
            sols.append(node)
            samples += K.affinity_samples(s, node)
    costs = K.count_costs(sols)
    w, b = K.fit_affinity_xy(samples)
    save("p2_policy.json", dict(op_cost=costs, weights=w, bias=b, n_solutions=len(sols), n_samples=len(samples),
                                train_rows=rows, solutions=[node_dump(n) for n in sols], train_cpu_s=round(time.process_time() - c0, 3)))
    print("train solved", len(sols), "/", len(rows), "cpu", round(time.process_time() - c0, 1), costs, w, b)
elif sys.argv[1] == "eval":                         # one engine per charged call (900 s cap); the rule is unchanged
    engine = sys.argv[2]
    P = load("p2_policy.json")
    out = {}
    for pol in ("baseline", "count", "exec"):
        r = eval_suite(DEV(), learner_cfg(pol, P), [], engine=engine)
        out[f"{engine}/{pol}"] = r
        print(engine, pol, "correct", r["correct"], "/", r["n"], "wrong_gen", r["wrong_generalisation"], "cpu", r["cpu_s"], flush=True)
    save(f"p2_eval_{engine}.json", out)
else:
    out = {**load("p2_eval_hybrid.json"), **load("p2_eval_construct.json")}
    h = {p: out[f"hybrid/{p}"] for p in ("baseline", "count", "exec")}
    order = ["baseline", "count", "exec"]
    best = order[0]
    for p in order[1:]:
        dc = h[p]["correct"] - h[best]["correct"]
        if dc > 1 or (abs(dc) <= 1 and h[p]["cpu_s"] <= 0.9 * h[best]["cpu_s"]):
            best = p
    save("p2.json", dict(results=out, promoted=best, rule="most generalising solves (hybrid); <=1 solve = tie -> >=10% CPU; else simpler"))
    print("PROMOTED", best)
