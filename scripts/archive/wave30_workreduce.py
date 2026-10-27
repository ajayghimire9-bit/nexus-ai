"""Sound work reduction at fixed scope and verdict, on the frozen v1 kernel (file unchanged; its `apply` is wrapped
in this process only to COUNT evaluations). Variants on the same 80 admission_val evidence objects:
  baseline: as produced; FF: fail-fast demonstration ordering (pairs sorted by estimated falsification rate, i.e.
  the fraction of scope tools whose depth-1 output mismatches the pair - estimation work charged);
  L0: no lemmas; LS: selective lemmas (only for tools that SURVIVE the first demonstration at depth 1, since tools
  rejected by the first pair cost one evaluation anyway; lemma verification is charged 2 units each);
  FF+LS. Verdict (label, k) must be identical in every variant."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import checker_kernel as K
from nexus.wave30_harness import verify_kernel_pin
verify_kernel_pin()
EV = json.loads((ROOT / "runs/experimental/wave30/evidence_adm_A1_complete.json").read_text())
CNT = {"n": 0}
_apply = K.apply
def counting_apply(spec, xs):
    CNT["n"] += 1
    return _apply(spec, xs)
K.apply = counting_apply


def depth1_out(spec, x):
    try:
        return K.key(_apply(spec, x))
    except Exception:
        return "<raised>"


def fail_fast(ev):
    tools = ev["scope"]["tools"]
    cost = 0
    rates = []
    for x, y in ev["public"]:
        ky = K.key(y)
        miss = sum(depth1_out(s, x) != ky for s in tools)
        cost += len(tools)
        rates.append(miss / max(1, len(tools)))
    order = sorted(range(len(ev["public"])), key=lambda j: -rates[j])
    remap = {old: new for new, old in enumerate(order)}
    lem = [dict(l, public_index=remap[l["public_index"]]) for l in ev["lemmas"]]
    return dict(ev, public=[ev["public"][j] for j in order], lemmas=lem), cost


def selective(ev):
    x0, y0 = ev["public"][0]
    k0 = K.key(y0)
    tools = ev["scope"]["tools"]
    keep = [l for l in ev["lemmas"] if depth1_out(tools[l["tool"]], x0) == k0]
    return dict(ev, lemmas=keep), len(tools) + 2 * len(keep)


variants = {
    "baseline": lambda e: (e, 2 * len(e["lemmas"])),
    "L0": lambda e: (dict(e, lemmas=[]), 0),
    "FF": lambda e: (lambda r: (r[0], r[1] + 2 * len(r[0]["lemmas"])))(fail_fast(e)),
    "LS": selective,
    "FF+LS": lambda e: (lambda a: (lambda b: (b[0], a[1] + b[1]))(selective(a[0])))(fail_fast(e)),
}
res, verdicts = {}, {}
t_all = time.perf_counter()
for name, f in variants.items():
    evals = chains = prep = 0
    t0 = time.perf_counter()
    out = []
    for e in EV:
        e2, c = f(e)
        prep += c
        CNT["n"] = 0
        v = K.check(e2)
        evals += CNT["n"]
        chains += v.get("chains_checked", 0)
        out.append((v["label"], v.get("k")))
    res[name] = dict(kernel_evaluations=evals, chains_checked=chains, preparation_work=prep,
                     total=evals + prep, wall_s=round(time.perf_counter() - t0, 1))
    verdicts[name] = out
inv = all(verdicts[n] == verdicts["baseline"] for n in verdicts)
with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as fh:
    fh.write(json.dumps(dict(run="wave30-workreduce", wall_s=time.perf_counter() - t_all, status="COMPLETE")) + "\n")
(ROOT / "artifacts/wave30_workreduce.json").write_text(json.dumps(dict(results=res, verdict_invariant=inv,
                                                                      n=len(EV)), indent=1))
print(json.dumps(res, indent=1), "verdict invariant:", inv)
