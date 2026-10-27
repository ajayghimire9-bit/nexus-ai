"""Wave 40 component tests (no experiment is executed): exact O(T) learned rows, Fixed+Repr reduction, payoff gate, witness
short-circuit soundness against Checker v5."""
import json
import random

from nexus import checker_kernel_v5 as V5
from nexus import w38_domains as D
from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w39_learn as W39
from nexus import w39_online as H
from nexus import w38_online as O
from nexus import w39_scope as S
from nexus import w40_learn as W
from nexus import w40_online as P
from nexus import w40_search as Q


def _task(d, m, seed="w40-comp"):
    return D.make_task(d, m, random.Random(f"{seed}:{d}:{m}"))


def test_fast_learned_and_hier_rows_equal_w39_exactly():
    progs = [t["teacher"] for t in D.stream("w40-comp-src", D.DOMAINS, "source", 2)]
    t = _task("tables", "present_names")
    tools = S.scope(t["public"], t["query"], 3)["tools"]
    learned = K.fit(progs)
    pl = K.placebo(learned, "x")
    hier = {"kind": "hier", "global": K.fit(progs, 1.0, 0.8, [100] * len(progs)), "local": K.fit(progs[:5]), "shrink": 1.0}
    hier0 = dict(hier, local=None)
    for pr in (learned, pl, hier, hier0):
        a, b = W39.cost_matrix(pr, tools)["cost"], W.cost_matrix_fast(pr, tools)["cost"]
        for r in (0, 1, 7, len(tools) // 2, len(tools)):
            assert a[r] == b[r]


def test_fixed_repr_without_programs_orders_like_fixed():
    t = _task("strings", "initials")
    tools = S.scope(t["public"], t["query"], 3)["tools"]
    fx = W39.cost_matrix({"kind": "fixed5"}, tools)["cost"]
    fr = W.cost_matrix({"kind": "fixed_repr", "repr": K.fit_repr([])}, tools)["cost"]
    for r in (0, 3, len(tools)):
        order = lambda row: sorted(range(len(tools)), key=lambda j: (round(row[j], 9), j))
        assert order(fx[r]) == order(fr[r])


def test_payoff_gate_switches_prior_off_when_it_does_not_pay():
    lr = P.PayoffGated(H.HierLearner(dict(O.BASELINE_80F9CC2, gate="regime"), 1.0), period=4, warm=2)
    view = {"public": [["ab", "a"]]}
    for k in range(12):
        lr.update([{"op": "strip"}], view)
        pr = lr.current_prior(view)
        lr.observe(100 if pr is None else 100, 5000 if pr is not None else 0)   # no saving, positive prior cost
    assert lr.off and any(e["event"] == "prior_off" for e in lr.log)
    assert lr.current_prior(view) is None


def test_payoff_gate_keeps_prior_when_it_pays():
    lr = P.PayoffGated(H.HierLearner(dict(O.BASELINE_80F9CC2, gate="regime"), 1.0), period=4, warm=2)
    view = {"public": [["ab", "a"]]}
    for k in range(12):
        lr.update([{"op": "strip"}], view)
        pr = lr.current_prior(view)
        lr.observe(10_000 if pr is None else 100, 100 if pr is not None else 0)
    assert not lr.off and lr.net() > 0


def test_witness_short_circuit_is_sound_against_checker_v5():
    """Whenever a disagreeing witness is found, the kernel says AMBIGUOUS; when the kernel says SCOPE_UNIQUE, no witness exists."""
    seen_amb = seen_uni = 0
    for i, (d, m) in enumerate(sorted(D.MECH)[::3]):
        t = _task(d, m, "w40-wit")
        if t is None:
            continue
        for pub in (t["public"], t["public"][:1]):
            depth = min(3, len(t["teacher"]))
            full = S.scope(pub, t["query"], depth)["tools"]
            keep = {json.dumps(x, sort_keys=True) for x in t["teacher"]}
            tools = [x for x in full if json.dumps(x, sort_keys=True) in keep] + \
                [x for x in full if json.dumps(x, sort_keys=True) not in keep][: (25 if depth == 3 else 100)]
            cm = K.cost_matrix(None, tools)
            cand = Q.search(pub, t["query"], tools, depth, cm, budget=10**7)
            if cand is None:
                continue
            claimed = L.run(cand, t["query"])
            w = Q.disagreeing_witness(pub, t["query"], tools, depth, cm, claimed)
            ev = {"checker_version": 5, "public": pub, "query": t["query"], "claimed_answer": claimed, "candidate": cand,
                  "scope": {"kind": "exhaustive", "tools": tools, "max_depth": depth}, "extra_queries": []}
            v = V5.check(json.loads(json.dumps(ev)))
            if w is not None:
                assert v["label"] == "AMBIGUOUS"; seen_amb += 1
            if v["label"] == "SCOPE_UNIQUE":
                assert w is None; seen_uni += 1
    assert seen_amb and seen_uni
