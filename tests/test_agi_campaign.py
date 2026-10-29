"""Multi-world campaign unit checks (no experiment outcomes are produced or read)."""
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.campaign import seeds as SD, substrate as S, improver as I, state as ST, agent_loop as AL  # noqa: E402
from nexus.campaign.worlds import FAMILIES, make_task, verify  # noqa: E402,F401
from nexus.campaign.worlds.base import QueryBudgetExceeded as QBE  # noqa: E402

PREFIX = {"A1": ("filter",), "A2": ("group",), "A3": ("semijoin", "join"), "A4": ("project", "route"),
          "B1": ("window",), "B2": ("latch", "hysteresis"), "B3": ("since", "cooldown"), "B4": ("registers",),
          "C1": ("stats",), "C2": ("transform",), "C3": ("restore",), "C4": ("act",), "D1": ("reach",), "D2": ("unlock",),
          "D3": ("fuel",), "D4": ("plan",), "E1": ("switch", "resp"), "E2": ("do", "resp"), "E3": ("chain", "lag"),
          "E4": ("control",), "F1": ("arith",), "F2": ("guard",), "F3": ("fold",), "F4": ("compose",)}


def mechanisms(descr):
    import re
    return set(re.findall(r"([a-z_]+)\[", descr))


def test_seed_ranges_fresh_disjoint_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "agi"}
    assert len(mine) == 9
    others = [r for k, r in R.REGISTRY.items() if k[0] != "agi"]
    assert min(r.start for r in mine.values()) >= max(r.stop for r in others)
    assert SD.ONE_USE <= R.ONE_USE and not ({k for k in mine} - SD.ONE_USE) & R.ONE_USE


def test_split_fixed_and_heldout_worlds_untouched():
    assert SD.SPLIT == {"A": dict(learn=("A2", "A3"), admit="A1", withheld="A4"),
                        "B": dict(learn=("B2", "B3"), admit="B1", withheld="B4"),
                        "D": dict(learn=("D2", "D4"), admit="D3", withheld="D1"),
                        "F": dict(learn=("F1", "F3"), admit="F2", withheld="F4")}
    used = {w for w, _ in SD.LEARN + SD.ADMIT}
    assert not used & {"C", "E"} and len(SD.LEARN) == 8 and len(SD.HELDOUT) == 8


@pytest.mark.parametrize("role_fams", ["learn", "admit"])
def test_source_and_admission_tasks_never_contain_withheld_or_heldout_mechanisms(role_fams):
    learn_names = set()
    for w, f in SD.LEARN:
        learn_names |= set(PREFIX[f])
    fams = SD.LEARN if role_fams == "learn" else SD.ADMIT
    k = 0
    for w, f in fams:
        for lv in (1, 2, 3, 4):
            for j in range(3):
                t = AL.task_of(w, f, lv, SD.RANGES[("agi", "dev")].start + 100 + k)
                k += 1
                assert mechanisms(t.descr) <= learn_names | set(PREFIX[f]), (t.tid, t.descr)


def test_view_hides_reference_and_meters_queries():
    t = AL.task_of("F", "F1", 1, SD.RANGES[("agi", "dev")].start + 7)
    v = t.view()
    assert not hasattr(v, "hidden_x") and not hasattr(v, "ref")
    for _ in range(t.q_budget):
        v.query(v.sample(random.Random(1)))
    with pytest.raises(QBE):
        v.query((1, 2))
    d4 = AL.task_of("D", "D4", 2, SD.RANGES[("agi", "dev")].start + 8).view()
    with pytest.raises(PermissionError):
        d4.ok(((9, 0, 1, 2, 3),), None, (1,))


def test_substrate_types_and_semantics():
    prog = ("p", "filterr", ("lam", "l", ("p", "lt", ("p", "nth", ("a", 0), ("c", 1)), ("c", 3))), ("x", 0))
    assert S.check_types(prog, ("L",)) == "L"
    assert S.run(prog, (((1, 2), (4, 5), (0, 3)),)) == ((1, 2),)
    assert S.run(("p", "coalesce", ("c", 2), ("c", 3)), ()) == 2
    assert S.run(("p", "div", ("c", 2), ("c", 0)), ()) == 0
    with pytest.raises(TypeError):
        S.check_types(("p", "add", ("x", 0), ("c", 1)), ("l",))


def test_search_finds_simple_program_and_dedups():
    xs = [((1, 2, 3),), ((4, 0),), ((5,),), ((),)]
    ys = [6, 4, 5, 0]
    srch = S.Search(xs, ("l",), "i", ST.pi0()["costs"], lambda v: list(v[:3]) == ys[:3], deadline=None)
    for c in srch.levels(4):
        if srch.hyps:
            break
    assert S.to_src(srch.hyps[0][1]) == "sum(x0)"
    keys = [(t, v) for t in srch.seen["top"] for v in [0]]
    assert len(keys) == len(set(keys))


def test_macro_compile_matches_expansion():
    st = ST.empty_state(I.M0)
    st["L"]["L0"] = dict(body=("p", "add", ("h", 0), ("p", "mul", ("h", 1), ("c", 2))), holes=("i", "i"), out="i",
                         src="", uses=[], util=0)
    prog = ("m", "L0", ("x", 0), ("x", 1))
    g = S.compile_ast(prog, ST.macros_of(st), ST.feats_of(st))
    assert g((3, 4), (), ()) == 11 == S.run(ST.expand(prog, st), (3, 4))


def test_antiunify_proposes_shared_abstraction():
    p1 = ("p", "sum", ("p", "filter", ("lam", "i", ("p", "lt", ("c", 3), ("a", 0))), ("x", 0)))
    p2 = ("p", "sum", ("p", "filter", ("lam", "i", ("p", "lt", ("c", 3), ("a", 0))), ("p", "rev", ("x", 0))))
    arch = [dict(tid="t1", sig=["l"], prog=p1), dict(tid="t2", sig=["l"], prog=p2)]
    st = ST.empty_state(I.M0)
    props = I.propose_L(arch, st, dict(method="antiunify", min_uses=2, max_size=8, max_holes=2, top_k=3), random.Random(0), set())
    assert props and all(p["holes"] and "x0" not in S.to_src(p["body"]) for p in props)
    assert any(S.to_src(p["body"]) == "sum(filter((\\x. lt(3, x)), $0))" for p in props)


def test_placebo_is_operationally_matched():
    item = dict(kind="L", body=("p", "sum", ("p", "filter", ("lam", "i", ("p", "lt", ("c", 3), ("a", 0))), ("h", 0))),
                holes=("l",), out="i")
    b = I.placebo_for(item, random.Random(5), {S.to_src(item["body"])})
    assert b is not None and S.size(b) == S.size(item["body"]) and S.check_types(b, (), holes=("l",)) == "i"


def test_admission_rejects_uninformative_and_silent():
    lin = AL.Lineage("t", ST.empty_state(I.M0), 1, ROOT / "artifacts/agi_dev/tmp", iter(()), iter(()), rng_key="t")
    base = [dict(solved=False, silent=False, cpu=0.6)] * 3
    rule = dict(neutral=True, speedup=0.2)
    assert not lin._admit(base, base, rule)[0] and lin._admit(base, base, rule, "L")[0]
    assert not lin._admit(base, base, dict(neutral=False, speedup=0.2), "L")[0]
    better = [dict(solved=True, silent=False, cpu=0.3)] + base[1:]
    assert lin._admit(base, better, rule)[0]
    worse = [dict(solved=False, silent=True, cpu=0.3)] + base[1:]
    assert not lin._admit(base, worse, rule)[0]


def test_m_random_and_mutate_stay_in_space():
    rng = random.Random(3)
    M = I.m_random(rng)
    assert [s[0] for s in M] == [s[0] for s in I.M0] and I.first(M, "propose_L")["method"] == "random"
    for _ in range(50):
        M2, e = I.m_mutate(I.M0, rng)
        assert len(I.stmt(M2, "propose_L")) <= 2 and I.first(M2, "admit") is not None


def test_budget_and_reductions():
    import agi_budget as B
    assert B.TOTAL == 4500.0 and sum(B.ceilings().values()) == 4500
    assert B.stage_of("mi-agi-src-Full-r0") == "src" and B.stage_of("mi-agi-eval-Full_r0") == "eval"
    for n in (56, 36, 24):
        red = SD.reduced(n)
        assert len(red) == n and {w for w, *_ in red} == set("ABCDEF")
        assert len({s for *_, s, _ in red}) == n
    assert len(SD.panels()["improver_panel"]) == 12
