import itertools
import random

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_v4_core import meter
from nexus.wave25_factored import ints_world, run
from nexus.wave26_phase1 import records_world_f
from nexus.wave26_phase4 import Library, instantiate, make_fault_task
from nexus.wave27_core import (CONSOLIDATED, DEMOTED, PROBATIONARY, EpistemicLibrary, _violates, index_tools,
                               postconditions, prune_fns)


def _fits(chain, public):
    try:
        return all(vkey(run(chain, x)) == vkey(y) for x, y in public)
    except Exception:
        return False


def test_index_never_prunes_a_tool_of_a_fitting_chain():
    lib = Library()
    for wname, w in (("ints", ints_world(5)), ("records", records_world_f(5, 5))):
        rng = random.Random(f"t27:{wname}")
        n = 0
        for kind in ("dB", "dC", "dM", "dM", "dM"):
            t = make_fault_task(w, rng, kind)
            if t is None:
                continue
            inputs = [x for x, _ in t["public"]] + [t["query"]]
            tools = lib.tools(inputs, with_schemas=False)
            for s in (("ord", "pred", "id"), ("ord", "head", "id"), ("ord", "first_occ", "id")):
                tools += [Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,)) for c in instantiate(s, inputs)]
            kept = {id(t_.fn) for t_ in index_tools(tools, t["public"], meter(10**9), {})}
            fns = [t_.fn for t_ in tools]
            for d in (1, 2):
                for ch in itertools.product(fns, repeat=d):
                    if _fits(ch, t["public"]):
                        assert all(id(f) in kept for f in ch)
            n += 1
        assert n >= 3


def test_postconditions_hold_on_outputs():
    rng = random.Random(1)
    w = records_world_f(3, 5)
    xs = [w["sample"](rng) for _ in range(20)]
    for s in (("ord", "pred", "id"), ("ord", "head", "id"), ("ord", "tail", "id"), ("ord", "first_occ", "id")):
        for c in instantiate(s, xs[:5]):
            for x in xs:
                y = c(x)
                for post in postconditions(c):
                    assert not _violates(post, y)


def test_opaque_tier_is_not_pruned():
    opaque = Tool("op", lambda xs: xs[:1], "op", kind="primitive", parts=("Opaque",))
    lib = Library()
    inputs = [[3, 1, 2], [5, 4]]
    tools = lib.tools(inputs, with_schemas=False) + [opaque]
    public = [([3, 1, 2], [3, 1, 2, 9])]
    assert len(index_tools(tools, public, meter(10**9), {})) == len(tools)


def test_ladder_retain_consolidate_demote():
    lib = EpistemicLibrary()
    s = ("ord", "pred", "id")
    public = [([1, 5, 3, 8, 2, 9], [5, 8, 9])] * 4
    m = meter(10**9)
    assert lib.propose(s, label="t1", discovery_cost=10**6, public=public, probe_passed=True, m=m)
    assert lib.status(s) == PROBATIONARY and lib.core() == []
    lib.support(s, "t1")
    assert lib.status(s) == PROBATIONARY                  # same task does not count twice
    lib.support(s, "t2")
    assert lib.status(s) == CONSOLIDATED and lib.core() == [s]
    lib.counterexample(s, "t3")
    assert lib.status(s) == DEMOTED and lib.core() == []
    lib.support(s, "t4")
    assert lib.status(s) == DEMOTED                       # never re-consolidated


def test_admission_filter_rejects_unprobed_one_off():
    lib = EpistemicLibrary()
    s = ("ord", "tail", "id")
    public = [([1, 5, 3, 8, 2, 9], [2, 9])] * 4
    m = meter(10**9)
    assert not lib.propose(s, label="noise1", discovery_cost=10**5, public=public, probe_passed=False, m=m)
    assert s not in lib.schemas and lib.status(s) == "CANDIDATE"
    assert lib.propose(s, label="other", discovery_cost=10**5, public=public, probe_passed=False, m=m)
    # two union-scan-certified tasks are also the consolidation evidence (net benefit positive here)
    assert lib.status(s) == CONSOLIDATED
