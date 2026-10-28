"""x7 unit tests (fast; no scientific experiment, no held-out family, no sealed data)."""
import random

from nexus import u5_stateful as SF
from nexus import u5_statesplit as SP
from nexus import x7_contract as XC
from nexus import x7_expr as X
from nexus import x7_regsearch as XR
from nexus import t7_repair as TR


def test_expr_semantics_and_bounds():
    e = {"a": 5, "b": 2.5, "s": "12.50", "n": {"m": 4}, "z": 0, "none": None}
    assert X.ev(("b", "-", ("f", "a"), ("f", "b")), e) == 2.5
    assert X.ev(("b", "/", ("f", "a"), ("f", "z")), e) is X.MISSING          # guarded division
    assert X.ev(("f", "none"), e) is X.MISSING and X.ev(("f", "absent"), e) is X.MISSING
    assert X.ev(("b", "+", ("f", "absent"), ("c", 1)), e) is X.MISSING        # MISSING never becomes 0
    assert X.ev(("p", "s"), e) == 12.5 and X.ev(("f", "s"), e) is X.MISSING
    assert X.ev(("f", "n.m"), e) == 4
    c = ("if", "absent", ("f", "a"), ("f", "b"))
    assert X.ev(c, e) == 2.5 and X.branch(c, e) == "else"
    body = ("b", "+", ("f", "a"), ("b", "/", ("f", "b"), ("c", 100)))
    assert X.size(body) == 5 and X.depth(body) == 2
    w = X.wrap_missing("v", body)
    assert X.size(w) == 8 and X.depth(w) == 3


def test_enumeration_finds_generic_difference_and_scaling():
    rnd = random.Random(1)
    recs = []
    for _ in range(20):
        g, f = round(rnd.uniform(10, 90), 2), round(rnd.uniform(0, 5), 2)
        recs.append({"g": g, "h": f, "k": rnd.randint(0, 9), "n": {"q": g * 1000}})
    bodies = X.enumerate_bodies(["g", "h", "k", "n.q"], [], recs, max_tier=2)
    sig = {X.src(b) for _, b in bodies}
    assert "(g - h)" in sig and "(n.q / 1000)" in sig
    tiers = [t for t, _ in bodies]
    assert tiers == sorted(tiers)


def _machine():
    """A per-key sum machine: OPEN resets, ADD adds x, CLOSE emits the sum; reg_1 is DEAD and binds a distractor."""
    acc, x = ("var", "acc"), ("var", "x")
    m = dict(key="k", ctrl="op", n=2, init=0, alpha=["OPEN", "ADD", "CLOSE"],
             delta={(0, "OPEN"): 1, (0, "ADD"): 0, (0, "CLOSE"): 0, (1, "OPEN"): 1, (1, "ADD"): 1, (1, "CLOSE"): 0},
             lam={(0, "OPEN"): (), (0, "ADD"): ("q:invalid",), (0, "CLOSE"): ("q:invalid",), (1, "OPEN"): ("q:invalid",),
                  (1, "ADD"): (), (1, "CLOSE"): ("sum",)},
             regs=[dict(field="v", init=0, upd={(1, "ADD"): ("b", "+", acc, x), (1, "CLOSE"): ("const", 0), (1, "OPEN"): acc}),
                   dict(field="batch", init=0, upd={(1, "ADD"): ("b", "+", acc, x)})],
             sources={((1, "CLOSE"), 0, 1): ("reg", 0)})
    return m


def _stream(n=30, seed=0, drop=None):
    rnd, out = random.Random(seed), []
    for i in range(n):
        k = f"K{i % 4}"
        e = {"k": k, "op": ["OPEN", "ADD", "ADD", "CLOSE"][(i // 4) % 4], "v": round(rnd.uniform(1, 50), 2), "batch": rnd.randint(0, 9)}
        if drop:
            e.pop(drop)
        out.append(e)
    return out


def _payload(m, events, emitted=False):
    src, name = SP.class_source(m)
    return dict(x7=True, source=src, name=name, machine=m, contract=XC.infer(m, events, emitted=emitted), mappings=[], benign_paths={})


def test_pruning_is_exact_and_removes_unused_inputs():
    m = _machine()
    pm, rep = XC.prune(m)
    assert rep["dead_regs"] == [1] and rep["identity_updates_removed"] == 1 and len(pm["regs"]) == 1
    assert rep["reads_after"] == ["v"] and "batch" in rep["reads_before"]
    s = XC.sensitivity(m, pm, _stream())
    assert s["disagreeing_events"] == 0 and s["removed_inputs"] == ["batch"]
    assert "batch" not in SP.class_source(pm)[0]


def test_unused_distractor_removal_no_incident_required_field_removal_mismatch():
    m, pm = _machine(), XC.prune(_machine())[0]
    build = _stream()
    p = _payload(pm, build)
    r = XC.ContractRunnerX(p)
    for e in _stream(seed=3, drop="batch"):
        r.ingest(e)
    assert r.pop_incidents() == [] and r.pop_notices() == []               # pruned: removing the distractor is harmless
    r = XC.ContractRunnerX(_payload(m, build, emitted=True))
    for e in _stream(seed=3, drop="batch"):
        r.ingest(e)
    assert r.pop_incidents()                                               # emitted-code reads: a FALSE incident (ablation)
    r = XC.ContractRunnerX(p)
    out = [r.ingest(e) for e in _stream(seed=4, drop="v")]
    inc = r.pop_incidents()
    assert inc and inc[0]["expected_fields"] == ["v"] and [XC.MISMATCH_ROW] in out   # required field: explicit mismatch


def test_legitimate_missing_kept_distinct_and_new_paths_are_notices():
    pm = XC.prune(_machine())[0]
    build = _stream()
    for e in build:
        if e["op"] == "ADD" and e["k"] == "K1":
            e["v"] = None                                                  # nullable on ADD in the build data
    p = _payload(pm, build)
    assert "v" in p["contract"]["nullable"].get("ADD", [])
    r = XC.ContractRunnerX(p)
    r.ingest({"k": "Z", "op": "OPEN", "batch": 1})
    r.ingest({"k": "Z", "op": "ADD", "batch": 1})
    assert r.pop_incidents() == [] and r.outcomes.get("LEGITIMATELY_MISSING") == 1
    r.ingest({"k": "Z", "op": "ADD", "v": 2.0, "batch": 1, "v_new": 3})
    nt = r.pop_notices()
    assert nt and nt[0]["new_paths"] == ["v_new"]


def test_adapter_versions_apply_by_observable_condition():
    pm = XC.prune(_machine())[0]
    p = _payload(pm, _stream())
    expr = X.wrap_missing("v", ("b", "-", ("f", "g"), ("f", "h")))
    p["mappings"] = [dict(field="v", expr=expr, path=X.src(expr), version=1, when="", kinds=["ADD"], paths=["g", "h", "v"])]
    r = XC.ContractRunnerX(p)
    evs = [{"k": "A", "op": "OPEN"}, {"k": "A", "op": "ADD", "v": 2.0}, {"k": "A", "op": "ADD", "g": 10.0, "h": 4.0},
           {"k": "A", "op": "CLOSE"}]
    out = [r.ingest(e) for e in evs]
    assert out[-1] == [("sum", 8.0, None)] and r.outcomes["MAPPED_v1"] == 1 and r.outcomes["PRESENT_VALID"] == 1


def test_reset_pruning_returns_the_same_register_program():
    for fam, seed in (("I.session", 3), ("C.clearing", 5)):
        task = SF.StreamTask(fam, seed, n_train_keys=12)
        out = []
        for cls in (TR.Learner2, XR.Learner2X):
            L = cls(task.train, task.y_train, task.query, seed=seed, max_s=30.0)
            hyp = L.learn_control()
            regs = L.learn_registers(hyp)
            out.append(None if regs is None else repr([sorted((str(k), SP.S.src(g)) for k, g in r["upd"].items()) for r in regs[0]]))
        assert out[0] == out[1]
