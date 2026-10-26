"""Checker v3 validation (spec docs/NEXUS_CHECKER_V3_SPEC.md §4). No experiment runs."""
import hashlib
import itertools
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))
from v3_diff import FIELDS, both, case, same  # noqa: E402

from nexus import checker_kernel_v2 as V2  # noqa: E402
from nexus import checker_kernel_v3 as V3  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SORT = {"op": "Sort", "path": ".", "desc": False}
RMAX = {"op": "running_max"}
DIFF = {"op": "diff"}
ROT = {"op": "rotate", "k": 1}


def ev3(pub, q, cand, tools, d, proofs=(), kind="exhaustive"):
    ans = V3.run_chain(cand, q)[0]
    return {"checker_version": 3, "public": pub, "query": q, "claimed_answer": ans, "candidate": cand,
            "scope": {"kind": kind, "tools": tools, "max_depth": d}, "lemmas": [], "proofs": list(proofs)}


def test_pins_v1_v2_untouched_and_v3_pinned():
    for f, pinf in (("checker_kernel.py", "checker_kernel.sha256"), ("checker_kernel_v2.py", "checker_kernel_v2.sha256"),
                    ("checker_kernel_v3.py", "checker_kernel_v3.sha256")):
        pin = (ROOT / "src/nexus" / pinf).read_text().split()[0]
        assert hashlib.sha256((ROOT / "src/nexus" / f).read_bytes()).hexdigest() == pin, f


def test_v3_imports_nothing_from_nexus():
    src = (ROOT / "src/nexus/checker_kernel_v3.py").read_text()
    imports = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert imports == ["import itertools", "import json"]


def test_differential_bounded_random_vs_v2():
    rng = random.Random(7)
    n = 0
    labels = set()
    for _ in range(900):
        e = case(rng, depth=rng.choice((1, 2, 3, 4)))
        if e is None:
            continue
        if e["scope"]["max_depth"] == 4:
            e["scope"]["tools"] = e["scope"]["tools"][:5]
        if not all(s in e["scope"]["tools"] for s in e["candidate"]):
            continue
        a, b = both(e)
        assert same(a, b), {f: (a.get(f), b.get(f)) for f in FIELDS}
        n += 1
        labels.add(a["label"])
    assert n > 400 and {"exhaustive_UNIQUE", "AMBIGUOUS"} <= labels


def _demo_only_unsound(pub, q, tools, d):
    """Deliberately UNSOUND variant: classes keyed on public points only, one representative kept per class."""
    reps = {tuple(V2.key(x) for x, _ in pub): (list(x for x, _ in pub), q)}
    answers = set()
    for _ in range(d):
        nxt = {}
        for xs, qq in reps.values():
            for t in tools:
                ys = [V3.run_chain([t], x)[0] for x in xs]
                if any(y is None for y in ys):
                    continue
                k = tuple(V3.canon(y) for y in ys)
                nxt.setdefault(k, (ys, V3.run_chain([t], qq)[0]))
        for k, (ys, qa) in nxt.items():
            if [V3.canon(y) for y in ys] == [V3.canon(y) for _, y in pub]:
                answers.add(V3.canon(qa))
        reps = nxt
    return len(answers)


def test_agree_on_demos_diverge_on_query_inside_parent():
    # Sort and running_max agree on sorted demos; they diverge on the unsorted query, and only show it after `diff`.
    pub = [[[0, 1, 3], [1, 2]], [[1, 2, 2], [1, 0]]]
    q = [2, 0, 1]
    tools = [SORT, RMAX, DIFF]
    # hand count: [diff] -> [-2,1], [Sort,diff] -> [1,1], [running_max,diff] -> [0,0]: k = 3
    v = V3.check(ev3(pub, q, [SORT, DIFF], tools, 2))
    v2 = V2.check(dict(ev3(pub, q, [SORT, DIFF], tools, 2), checker_version=2))
    assert v["label"] == v2["label"] == "AMBIGUOUS" and v["k"] == v2["k"] == 3
    assert _demo_only_unsound(pub, q, tools, 2) < v["k"]       # the unsound variant loses the running_max branch


def _two_rep_truncation(pub, q, tools, d):
    """Deliberately UNSOUND variant: keeps at most two distinct query values per public-class at each layer."""
    layer = {tuple(V3.canon(x) for x, _ in pub): [(list(x for x, _ in pub), q)]}
    answers = set()
    for _ in range(d):
        nxt = {}
        for members in layer.values():
            for xs, qq in members:
                for t in tools:
                    ys = [V3.run_chain([t], x)[0] for x in xs]
                    qa = V3.run_chain([t], qq)[0]
                    if any(y is None for y in ys):
                        continue
                    k = tuple(V3.canon(y) for y in ys)
                    bucket = nxt.setdefault(k, [])
                    if len({V3.canon(m[1]) for m in bucket} | {V3.canon(qa)}) <= 2 and \
                            V3.canon(qa) not in {V3.canon(m[1]) for m in bucket}:
                        bucket.append((ys, qa))
        for k, members in nxt.items():
            if list(k) == [V3.canon(y) for _, y in pub]:
                answers |= {V3.canon(m[1]) for m in members}
        layer = nxt
    return len(answers)


def test_no_two_representative_truncation():
    # constant demo: the rotations are indistinguishable on it but give 3 distinct query intermediates, which
    # stay distinct after the parent `diff`.
    pub = [[[2, 2, 2, 2], [0, 0, 0]]]
    q = [1, 2, 3, 9]
    tools = [{"op": "rotate", "k": 0}, {"op": "rotate", "k": 1}, {"op": "rotate", "k": 3}, DIFF]
    cand = [tools[0], DIFF]
    v3 = V3.check(ev3(pub, q, cand, tools, 2))
    v2 = V2.check(dict(ev3(pub, q, cand, tools, 2), checker_version=2))
    # hand count: [1,1,6] ([diff], [rot0,diff], [diff,rot0], [diff,rot3]), [1,6,-8], [-8,1,1], [1,6,1]: k = 4
    assert v3["label"] == v2["label"] == "AMBIGUOUS" and v3["k"] == v2["k"] == 4
    assert _two_rep_truncation(pub, q, tools, 2) < v3["k"]     # truncation loses an alternative


def test_probe_refinement_is_stateless():
    pub = [[[0, 1, 3], [1, 2]], [[1, 2, 2], [1, 0]]]
    q, tools = [2, 0, 1], [SORT, RMAX, DIFF]
    base = ev3(pub, q, [SORT, DIFF], tools, 2)
    probed = ev3(pub + [[[3, 1, 2], [1, 1]]], q, [SORT, DIFF], tools, 2)
    assert V3.check(probed)["label"] == "exhaustive_UNIQUE"
    assert V3.check(base)["label"] == "AMBIGUOUS"              # no state carried from the previous call


def test_order_invariance():
    rng = random.Random(3)
    for _ in range(150):
        e = case(rng, depth=rng.choice((1, 2, 3)))
        if e is None or not all(s in e["scope"]["tools"] for s in e["candidate"]):
            continue
        e3 = dict(e, checker_version=3, proofs=[])
        a = V3.check(e3)
        tools = list(e["scope"]["tools"]); rng.shuffle(tools)
        pub = list(e["public"]); rng.shuffle(pub)
        b = V3.check(dict(e3, public=pub, scope=dict(e["scope"], tools=tools)))
        assert (a["label"], a.get("k"), a.get("fitting")) == (b["label"], b.get("k"), b.get("fitting"))


def test_step_bound_logic_matches_direct_semantics(monkeypatch):
    """With a tiny bound, shared evaluation must equal direct per-chain enumeration (or abstain on a straddle)."""
    rng = random.Random(11)
    monkeypatch.setattr(V3, "STEP_BOUND", 14)
    checked = 0
    for _ in range(300):
        e = case(rng, depth=rng.choice((2, 3)))
        if e is None or not all(s in e["scope"]["tools"] for s in e["candidate"]):
            continue
        tools, D = e["scope"]["tools"], e["scope"]["max_depth"]
        pub, q = e["public"], e["query"]
        if any(V3.run_chain(e["candidate"], x)[0] is None for x, _ in pub) or V3.run_chain(e["candidate"], q)[0] is None:
            continue
        v = V3.check(dict(e, checker_version=3, proofs=[], claimed_answer=V3.run_chain(e["candidate"], q)[0]))
        if v.get("reason") == "step_bound_straddle":
            continue
        answers = {}
        for k in range(1, D + 1):
            for ch in itertools.product(range(len(tools)), repeat=k):
                c = [tools[i] for i in ch]
                outs = [V3.run_chain(c, x)[0] for x, _ in pub]
                if all(o is not None and V3.canon(o) == V3.canon(y) for o, (_, y) in zip(outs, pub)):
                    a = V3.run_chain(c, q)[0]
                    answers[V3.ERROR_ANSWER if a is None else V3.canon(a)] = 1
        assert v.get("answers") == len(answers), (v, answers)
        checked += 1
    assert checked > 50


@pytest.mark.parametrize("ax,tool,cond_vals", [
    ("sort_fixpoint", SORT, [list(p) for n in range(6) for p in itertools.product(range(3), repeat=n)]
     + [list(p) for n in range(5) for p in itertools.product("ab", repeat=n)]),
    ("runheads_fixpoint", {"op": "run_heads"}, [list(p) for n in range(6) for p in itertools.product(range(3), repeat=n)]),
    ("runmax_fixpoint", RMAX, [list(p) for n in range(6) for p in itertools.product(range(-1, 2), repeat=n)]),
    ("top_fixpoint", {"op": "ir_counter_top", "k": 2},
     [{"counts": [[a, n] for a, n in zip(ks, ns)]} for r in range(4) for ks in itertools.combinations(range(4), r)
      for ns in itertools.product((1, 2), repeat=r)]),
])
def test_axioms_bounded_exhaustive(ax, tool, cond_vals):
    cond = V3._top_cond(tool["k"]) if ax == "top_fixpoint" else V3.AXIOMS[ax][1]
    assert V3.AXIOMS[ax][0](tool)
    held = 0
    for v in cond_vals:
        if cond(v):
            held += 1
            assert V3.run_op(tool, v) == v and V2.run([tool], v)[0] == v
    assert held > 0


def test_proofs_never_change_the_verdict_and_bad_proofs_abstain():
    rng = random.Random(5)
    applied = 0
    for _ in range(400):
        e = case(rng, depth=rng.choice((2, 3)))
        if e is None or not all(s in e["scope"]["tools"] for s in e["candidate"]):
            continue
        tools = e["scope"]["tools"]
        pf = [{"axiom": ax, "tool": i} for i, t in enumerate(tools) for ax, (m, _c) in V3.AXIOMS.items() if m(t)]
        a = V3.check(dict(e, checker_version=3, proofs=[]))
        b = V3.check(dict(e, checker_version=3, proofs=pf))
        assert all(a.get(f) == b.get(f) for f in FIELDS)
        applied += b.get("proofs_applied", 0)
    assert applied > 0
    pub = [[[0, 1, 3], [1, 2]]]
    bad = ev3(pub, [2, 0, 1], [SORT, DIFF], [SORT, RMAX, DIFF], 2, proofs=[{"axiom": "sort_fixpoint", "tool": 2}])
    assert V3.check(bad)["reason"] == "bad_proof"
    assert V3.check(dict(bad, proofs=[{"axiom": "nonsense", "tool": 0}]))["reason"] == "bad_proof"
    assert V3.check(dict(bad, proofs=[], lemmas=[{"tool": 0}]))["reason"] == "v2_lemmas_not_accepted"
    assert V3.check(dict(bad, proofs=[], checker_version=2))["reason"] == "wrong_checker_version"
    assert V3.check(dict(bad, proofs=[], claimed_answer=[9]))["reason"] == "candidate_fails"
