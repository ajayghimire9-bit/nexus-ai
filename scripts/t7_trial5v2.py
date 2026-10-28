"""Trial 5 v2 (NOT LOCKED; priority C after the owner addendum): ONE labelled example per target task (larger, genuinely ambiguous hypothesis sets; v1 had almost none to separate). Surviving metadata = the ordered list of experiment types only; no solution program, hypothesis or example from any source task reaches the target. Success requires every surviving hypothesis to match the oracle on all held-out inputs, so a target outside the candidate set counts as failure. Source: L, C, I families x t7/tsrc 0-1 (learn the experiment-type order; solution programs are
never stored). Target: the unseen energy domain (7 families x t7/theld 0-4; 35 tasks), 3 labelled examples, hypotheses from
NEXUS's construction bank. Arms: translation (learned order), info_gain (max partition entropy over the unlabelled pool),
fresh (random experiment types, verified), irrelevant (a size-matched order learned on a different problem: boolean-output
families only, reversed). All CPU charged (source learning reported separately and amortised over the 35 target tasks).
KEEP iff translation uses fewer mean queries than info_gain AND fresh, with total CPU (incl. amortised learning) no higher
than theirs, and success rate no lower."""
import json, random, sys, time
sys.path.insert(0, "scripts")
from u5_common import ROOT, K, W, load, learner_cfg
from nexus import t7_seeds, t7_world, t7_experiments as X, seed_registry as R  # noqa: F401
ART = ROOT / "artifacts/t7_dev"
cfg = learner_cfg("count", load("p2_policy.json"))
src = [W.Task(f"{f}#{s}", f, s) for f in W.FAMILIES if f[0] in "LCI" for s in list(R.REGISTRY[("t7", "tsrc")])[:2]]
tgt = [W.Task(f"{f}#{s}", f, s) for f in W.FAMILIES if f[0] == "E" for s in R.REGISTRY[("t7", "theld")]]
t0 = time.process_time()
order, score = X.learn_order(src, cfg, random.Random(1))
learn_cpu = time.process_time() - t0
boolsrc = [t for t in src if W.FAMILIES[t.family]["out"] == "bool"]
t1 = time.process_time()
irr, _ = X.learn_order(boolsrc, cfg, random.Random(2))
irr = list(reversed(irr))[:len(order)]
res = {}
for m in ("translation", "info_gain", "fresh", "irrelevant"):
    rows = []
    for t in tgt:
        t.queries = 0
        r = X.identify(t, m, cfg, random.Random(t.tid), order=order if m == "translation" else irr, n_lab=1, max_q=20)
        rows.append(dict(task=t.tid, **{k: v for k, v in r.items() if k != "eliminated"}))
    res[m] = dict(rows=rows, mean_queries=round(sum(r["queries"] for r in rows) / len(rows), 3),
                  success=sum(r["success"] for r in rows), cpu_s=round(sum(r["cpu_s"] for r in rows), 3))
    print(m, res[m]["mean_queries"], res[m]["success"], res[m]["cpu_s"], flush=True)
res["translation"]["cpu_s_with_learning"] = round(res["translation"]["cpu_s"] + learn_cpu, 3)
T = res["translation"]
keep = all(T["mean_queries"] < res[b]["mean_queries"] and T["cpu_s_with_learning"] <= res[b]["cpu_s"] and T["success"] >= res[b]["success"]
           for b in ("info_gain", "fresh"))
(ART / "t5v2b.json").write_text(json.dumps(dict(order=[list(o) for o in order], type_scores={str(k): round(v, 4) for k, v in score.items()},
                                             learn_cpu_s=round(learn_cpu, 3), irrelevant_order=[list(o) for o in irr], results=res,
                                             verdict="PROMOTION CANDIDATE" if keep else "NOT PROMOTED"), indent=1))
print("order", order[:5], "learn_cpu", round(learn_cpu, 1), "VERDICT", "KEPT" if keep else "REJECTED")
