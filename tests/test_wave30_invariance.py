"""Invariance law (permanent regression): with identical final observations, identical declared scope and completed
checking, the exhaustive verdict is invariant to candidate (tool) order and to demonstration order; and with the
order-invariant probe design, the final observations themselves do not depend on candidate order."""
import random

import nexus.wave30_harness as H
from nexus import checker_kernel as K
from nexus.wave25_factored import run
from nexus.wave30_arms import DEPTH, a1_tools, spec_of, stream


def _ev(t, public, specs):
    return {"version": 1, "public": public, "query": t["query"], "claimed_answer": t["answer"],
            "candidate": t["teacher_spec"], "scope": {"kind": "exhaustive", "tools": specs, "max_depth": DEPTH},
            "lemmas": [], "trace": {}}


def test_kernel_verdict_invariant_to_tool_and_demonstration_order():
    for seed, i in ((7002, 4), (7005, 2), (751, 3)):
        t = stream(seed)[i]
        specs = [spec_of(tl.fn) for tl in a1_tools([x for x, _ in t["public"]] + [t["query"]])]
        pub = [list(p) for p in t["public"]]
        base = K.check(_ev(t, pub, specs))
        for s in range(3):
            sp, pp = specs[:], pub[:]
            random.Random(s).shuffle(sp)
            random.Random(100 + s).shuffle(pp)
            v = K.check(_ev(t, pp, sp))
            assert (v["label"], v.get("k"), v["fitting"]) == (base["label"], base.get("k"), base["fitting"])


def test_complete_probe_design_is_order_invariant():
    H.PROBE_DESIGN["mode"] = "complete"
    try:
        t = stream(7002)[4]
        outs = set()
        for counts in (None, {f: (7.0 if f.startswith("comp") else 1.0) for f in H.FAMILIES},
                       {f: (7.0 if not f.startswith("comp") else 1.0) for f in H.FAMILIES}):
            seen = []
            def oracle(x, c=t["teacher"]):
                seen.append(K.key(x))
                return run(c, x)
            r = H.solve("A1b-full", H.TaskView(tuple(t["public"]), t["query"], oracle), prior=H.FrozenPrior(counts),
                        seed=7002, label="A1b-full:4")
            outs.add((tuple(seen), r["label"], K.key(r["answer"])))
        assert len(outs) == 1
    finally:
        H.PROBE_DESIGN["mode"] = "early"
