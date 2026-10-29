"""Phase 2 unit checks (no experiment outcomes are produced or read; C5 / C6 / E5 / E6 are only built, never searched)."""
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.campaign2 import seeds as SD, substrate as S, improver as I, state as ST, agent_loop as AL  # noqa: E402
from nexus.campaign2.worlds2 import UNTOUCHED  # noqa: E402


def test_phase2_seeds_fresh_disjoint_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "agi2"}
    assert len(mine) == 10
    assert min(r.start for r in mine.values()) >= max(r.stop for k, r in R.REGISTRY.items() if k[0] != "agi2")
    assert SD.ONE_USE <= R.ONE_USE and not (set(mine) - SD.ONE_USE) & R.ONE_USE


def test_panels_and_reductions():
    p = SD.panels()
    assert [len(p[k]) for k in ("withheld", "ce_fresh", "untouched", "improver_panel")] == [16, 16, 16, 12]
    assert {(w, f) for w, f, *_ in p["untouched"]} == set(UNTOUCHED)
    for k in ("withheld", "ce_fresh", "improver_panel"):
        assert not {(w, f) for w, f, *_ in p[k]} & set(UNTOUCHED)
    for n in (48, 32, 24):
        red = SD.reduced(n)
        assert len(red) == n and sum(t[4] == "untouched" for t in red) == 16
    assert 43614 not in {t[3] for t in SD.reduced(48)} and 43664 in {t[3] for t in SD.reduced(48)}


def test_untouched_families_never_in_learning_roles():
    assert not set(UNTOUCHED) & set(SD.LEARN + SD.ADMIT + SD.WITHHELD)
    assert all(SD.role_of(w, f) == "untouched" for w, f in UNTOUCHED)


def test_world_f_pure_synthesis_tasks_have_no_draft():
    odd = AL.task_of("F", "F1", 1, SD.RANGES[("agi2", "dev")].start + 1)
    even = AL.task_of("F", "F1", 1, SD.RANGES[("agi2", "dev")].start + 2)
    assert odd.meta["pure_synthesis"] and odd.view().draft is None
    assert not even.meta["pure_synthesis"] and even.view().draft is not None


def test_graded_credit():
    assert AL.ex_score((1, 2, 3), (1, 2, 3)) == 1.0
    assert AL.ex_score((1, 2, 9, 9), (1, 2, 3, 4)) == 0.5
    assert AL.ex_score(3, 4) == 0.0


def test_acceptance_barrier_is_locked_outside_pi_and_M():
    assert AL.ACCEPT == dict(margin=1, confirm_q=4, fit_alpha=0.1)
    for k in AL.ACCEPT:
        assert k not in ST.pi0() and k not in I.TUNE
        assert all(k not in p for _, p in I.M0)


def test_lazy_lambdas_reach_a_body_beyond_the_old_cap():
    # latch: scan(\a x. ite_i(lt(3, x), 1, a), 0, s); body cost 9 > the Phase 1 cap 6
    xs = [((1, 5, 2, 0),), ((4, 1, 1),), ((0, 2, 7, 1, 1),)]
    f = lambda s: tuple(__import__("itertools").accumulate(s, lambda a, x: 1 if x > 3 else a, initial=0))[1:]  # noqa: E731
    ys = [f(x[0]) for x in xs]
    srch = S.Search(xs, ("l",), "l", ST.pi0()["costs"], lambda v: list(v) == ys, lam_max=99,
                    prims=["scan", "ite_i", "lt"], deadline=time.process_time() + 20)
    for c in srch.levels(16):
        if srch.hyps:
            break
    assert srch.hyps and "scan" in S.to_src(srch.hyps[0][1])


def test_admission_provisional_needs_positive_evidence():
    lin = AL.Lineage("t", ST.empty_state(I.M0), 1, ROOT / "artifacts/agi2_dev/tmp", (), (), rng_key="t")
    base = [dict(solved=False, silent=False, cpu=0.6, graded=0.4)] * 3
    rule = dict(neutral=True, speedup=0.2, eps=0.05)
    assert not lin._admit(base, base, rule, dict(kind="L", tier="provisional"))[0]
    assert lin._admit(base, base, rule, dict(kind="L", tier="validated"))[0]
    up = [dict(solved=False, silent=False, cpu=0.6, graded=0.6)] * 3
    assert lin._admit(base, up, rule, dict(kind="L", tier="provisional"))[0]
    assert not lin._admit(base, base, rule, dict(kind="pi_costs"))[0]


def test_seed_streams_are_paired_on_clone():
    a = AL.SeedStream(range(10))
    next(a)
    b, c = a.clone(), a.clone()
    assert [next(b) for _ in range(3)] == [next(c) for _ in range(3)] == [1, 2, 3]


def test_placebo_matches_with_hole_fill():
    item = dict(kind="L", body=("p", "sub", ("p", "sub", ("h", 0), ("p", "mul", ("h", 1), ("h", 2))), ("h", 1)),
                holes=("i", "i", "i"), out="i")
    b = I.placebo_for(item, random.Random(1), {S.to_src(item["body"])})
    assert b is not None and S.size(b) == S.size(item["body"])


def test_budget_phase2():
    import agi2_budget as B
    assert B.TOTAL == 3200.0 and sum(B.ceilings().values()) == 3200
    assert B.stage_of("mi-agi2-eval-main-c0") == "eval"
