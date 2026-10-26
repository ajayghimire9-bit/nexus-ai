"""Re-run the admission_val tasks whose outcome differs across A1b-full priors, with full instrumentation."""
import json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import nexus.wave30_harness as H
from nexus import checker_kernel as K
from nexus.wave25_factored import run
from nexus.wave30_arms import stream
H.verify_kernel_pin()
src = json.loads((ROOT / "artifacts/wave30_inc2_dev_A1b-full_online.json").read_text())["prior_final"]
fams = sorted(src); vals = [src[f] for f in fams]; random.Random("w30-shuffled-history").shuffle(vals)
PRIORS = {"useful": src, "none": None, "shuffled": dict(zip(fams, vals))}
CASES = [(7001, 10), (7001, 14), (7002, 4), (7005, 2)]
log = {}
orig_round = H._searcher_round
def round_logged(public, query, tools, m, *, early):
    st, hyps = orig_round(public, query, tools, m, early=early)
    log["rounds"].append(dict(n_public=len(public), status=st, witnesses=[K.key(h[1]) for h in hyps[:3]],
                              witness_programs=[[t.name for t in h[2]] for h in hyps[:3]]))
    return st, hyps
H._searcher_round = round_logged
out = []
t0 = time.perf_counter()
for seed, i in CASES:
    t = stream(seed)[i]
    for name, counts in PRIORS.items():
        log.clear(); log["rounds"] = []; log["oracle"] = []
        def oracle(x, c=t["teacher"]):
            y = run(c, x); log["oracle"].append(dict(x=x, y=y)); return y
        view = H.TaskView(tuple(t["public"]), t["query"], oracle)
        res = H.solve("A1b-full", view, prior=H.FrozenPrior(counts), seed=seed, label=f"A1b-full:{i}")
        ev = H.evaluate(t, res)
        out.append(dict(seed=seed, task=i, prior=name, initial_public=[list(p) for p in t["public"]], query=t["query"],
                        oracle_observations=log["oracle"], oracle_cost=len(log["oracle"]) * 20,
                        scope_tools=res["n_tools"], scope_kind=res["scope_kind"], prover_rounds=log["rounds"],
                        prover_status=res["prover_status"], label=res["label"], kernel_k=res["kernel_k"],
                        correct=ev["correct"], work=res["work"], work_by=res["work_by"], teacher=t["teacher_spec"],
                        truth=t["answer"]))
        print(seed, i, name, res["label"], ev["correct"], len(log["oracle"]), res["work"], flush=True)
with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as f:
    f.write(json.dumps(dict(run="wave30-reconcile", wall_s=time.perf_counter() - t0, status="COMPLETE")) + "\n")
(ROOT / "artifacts/wave30_reconcile.json").write_text(json.dumps(out, default=repr, indent=1))
