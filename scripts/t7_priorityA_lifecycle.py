"""Priority A, targeted (NOT LOCKED): lifecycle relearning with the X3 kinds present (known class) on fresh dev seeds
t7/tdev 0-4, small training streams (16 keys; field discovery needs > 12 distinct keys, as after a fault onset), held-out 200 keys. Frozen u5 learner vs covered
learner: exact held-out, key accuracy, membership queries, CPU."""
import json, sys, time
sys.path.insert(0, "src")
from pathlib import Path
from nexus import t7_seeds, t7_world, t7_repair as TR, u5_stateful as SF, u5_statesplit as SP, seed_registry as R  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/t7_dev"
rows = []
for fam in ("L.barrier", "C.clearing", "I.session", "E.meter"):
    for s in R.REGISTRY[("t7", "tdev")]:
        for arm in ("u5_learner", "covered"):
            t = SF.StreamTask(fam, s, n_train_keys=16, x3_train=True, x3_test=True)
            c0 = time.process_time()
            r = SP.learn_class(t.train, t.y_train, t.query, seed=s) if arm == "u5_learner" else TR.learn_class_covered(t.train, t.y_train, t.query, seed=s)
            cpu = time.process_time() - c0
            if r and r.get("source"):
                cls = SP.compile_class(r["source"], r["name"])
                sc = t.score(lambda evs: SP.run_class(cls, evs))
            else:
                sc = dict(exact=False, key_acc=0.0)
            rows.append(dict(family=fam, seed=s, arm=arm, exact=sc["exact"], key_acc=round(sc["key_acc"], 4), queries=t.n_queries, cpu_s=round(cpu, 3)))
            print(fam, s, arm, sc["exact"], round(sc["key_acc"], 3), t.n_queries, round(cpu, 2), flush=True)
agg = {a: dict(exact=sum(r["exact"] for r in rows if r["arm"] == a), key_acc=round(sum(r["key_acc"] for r in rows if r["arm"] == a) / 20, 4),
               queries=sum(r["queries"] for r in rows if r["arm"] == a), cpu_s=round(sum(r["cpu_s"] for r in rows if r["arm"] == a), 2))
       for a in ("u5_learner", "covered")}
(ART / "pA_lifecycle.json").write_text(json.dumps(dict(rows=rows, aggregate=agg), indent=1))
print("AGG", agg)
