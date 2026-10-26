import random

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_v4_core import NONE_FOUND, meter
from nexus.wave25_factored import ints_world
from nexus.wave26_phase1 import records_world_f
from nexus.wave26_phase4 import Library, certify, instantiate, make_fault_task, synthesize
from nexus.wave28_core import (_violates28, certify_pm, index28, is_subsequence_map, posts28, synthesize28)


def _opaque():
    def top2_dup(xs):
        out = sorted(xs, key=lambda v: repr(v))[:2]
        return out + out[:1]                 # breaks every closed postcondition (duplicate, extra item)
    return Tool("opq", top2_dup, "opq", kind="primitive", parts=("Opaque",))


def _tools(lib, inputs):
    tools = lib.tools(inputs, with_schemas=False)
    for s in (("ord", "pred", "id"), ("ord", "head", "id"), ("ord", "first_occ", "id"), ("ord", "all", "id")):
        tools += [Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,)) for c in instantiate(s, inputs)]
    return tools


def _answers(r):
    return None if r.status == NONE_FOUND else (r.size, frozenset(vkey(h[1]) for h in r.hypotheses))


def test_pruned_certificate_equals_unpruned_with_and_without_unproved_tool():
    lib = Library()
    n = 0
    for wname, w in (("ints", ints_world(7)), ("records", records_world_f(7, 5))):
        rng = random.Random(f"t28:{wname}")
        for kind in ("dB", "dM", "dM", "dC"):
            t = make_fault_task(w, rng, kind)
            if t is None:
                continue
            inputs = [x for x, _ in t["public"]] + [t["query"]]
            for extra in ([], [_opaque()]):
                tools = _tools(lib, inputs) + extra
                full = certify(t["public"], t["query"], tools, 2, meter(10**9))
                keep, macros = index28(tools, t["public"], 2, meter(10**9), {})
                pr = certify_pm(t["public"], t["query"], (keep, 2, macros), meter(10**9))
                assert _answers(full) == _answers(pr)
                n += 1
    assert n >= 8


def test_order_postcondition_and_subsequence_maps():
    rng = random.Random(3)
    w = records_world_f(3, 5)
    xs = [w["sample"](rng) for _ in range(25)]
    lib = Library()
    fns = [t.fn for t in _tools(lib, xs[:5])]
    for f in fns:
        for x in xs:
            try:
                y = f(x)
            except Exception:
                continue
            for post in posts28(f):
                assert not _violates28(post, y)
            if is_subsequence_map(f):
                it = iter(x)
                assert all(any(vkey(a) == vkey(b) for b in it) for a in y)     # y is a subsequence of x


def test_synthesis_hits_unchanged():
    for wname, w in (("ints", ints_world(9)), ("records", records_world_f(9, 5))):
        rng = random.Random(f"t28s:{wname}")
        for _ in range(3):
            t = make_fault_task(w, rng, "dM")
            if t is None:
                continue
            lib = Library()
            a = synthesize(list(t["public"]), t["query"], lib, meter(10**10))
            b = synthesize28(list(t["public"]), t["query"], lib, meter(10**10), {})
            assert [(s, sorted(c.name() for c in h)) for s, h in a] == [(s, sorted(c.name() for c in h)) for s, h in b]
