"""MI-3 unit checks (no experiment outcomes are produced or read)."""
import copy
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import mi3_seeds, mi3_accept as A, mi3_search as MS, mi_learner as ML, mi2_learner as M2  # noqa: E402,F401
from nexus import seed_registry as R  # noqa: E402


def test_seed_ranges_fresh_and_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "mi3"}
    assert len(mine) == 6
    others = [r for k, r in R.REGISTRY.items() if k[0] != "mi3"]
    assert min(r.start for r in mine.values()) >= max(r.stop for r in others)
    assert ("mi3", "accept_audit") in R.ONE_USE and ("mi3", "winner_eval") in R.ONE_USE
    assert not {("mi3", "dev"), ("mi3", "screen_calibration"), ("mi3", "discovery"), ("mi3", "selection")} & R.ONE_USE


def test_26801_regression_old_silent_new_rejects():
    ep = A.Episode3(26801, "ADDC")
    assert "ADD" in ep.interface and "ADD" not in {e["kind"] for e in ep.train}
    r, _ = M2.full_space(ep, ML.lpl_domain(M2.A5_PROG), ep.seed, cap_s=15.0)
    assert ML.score(ep, r)["silent"]                                   # the MI-2 failure, reproduced
    ep = A.Episode3(26801, "ADDC")
    r, st = A.full_space3(ep, ML.lpl_domain(M2.A5_PROG), ep.seed, cap_s=15.0)
    assert r is None and st["outcome"] == "interface_gap"


def test_interface_tier_silent_when_alphabet_covers_interface():
    ep = A.Episode3(28400, "MUL")                                      # mi3/dev
    L = M2.LearnerMI2(ep.train, ep.y_train, ep.query, seed=ep.seed, max_s=4.0)
    L.domain_fn = M2.witness_fn(ep, "end")
    assert L.learn() is not None and set(ep.interface) <= set(L.alpha)
    cex, rec = A.interface_cex(L, ep.interface)
    assert cex == [] and rec["queries"] == 0


def test_interface_tier_catches_dropped_kind():
    ep = A.Episode3(28400, "K")
    k = sorted({e["kind"] for e in ep.train} & {e["kind"] for e in ep.test})[0]
    from nexus import mi_ocean as M
    tr = [dict(e) for e in ep.train if e["kind"] != k]
    L = M2.LearnerMI2(tr, M.run(ep.machine, tr), ep.query, seed=ep.seed, max_s=4.0)
    L.domain_fn = M2.witness_fn(ep, "end")
    if L.learn() is None:
        return
    cex, rec = A.interface_cex(L, ep.interface)
    assert k in rec["missing"] and cex


def test_staged_schedule_rules():
    pool = MS.pool_of("discovery", MS.FAMS_U, 8)
    scr, rest = MS.screen_split(pool)
    assert len(scr) == 6 and len(rest) == 18 and {f for _, f in scr} == set(MS.FAMS_U)
    row = lambda e, x: dict(exact=e, explained=x, cpu_s=0.1)          # noqa: E731
    assert MS.survives([row(True, 0.0)] + [row(False, 0.0)] * 5, 0.75)
    assert MS.survives([row(False, 0.8)] * 6, 0.75) and not MS.survives([row(False, 0.5)] * 6, 0.75)
    full = dict(full_fitness=[0, 0.0, -1.0], screen_fitness=[3, 1.0, -1.0])
    screened = dict(full_fitness=None, screen_fitness=[5, 1.0, -0.1])
    assert MS.rank_key(full) > MS.rank_key(screened)


def test_random_search_ignores_fitness_and_pairs_streams():
    import mi3_discover as DI
    a = [dict(DI.propose("R", 1, []), full_fitness=[0, 0.0, 0.0], screen_fitness=[0, 0.0, 0.0])]
    b = [dict(copy.deepcopy(a[0]), full_fitness=[9, 1.0, 0.0])]
    assert DI.propose("R", 1, a) == DI.propose("R", 1, b)
    assert DI.propose("E", 2, []) == DI.propose("E", 2, [])


def test_budget_stage_prefixes():
    import mi3_budget as B
    assert B.stage_of("mi-3-disc-E-S_L1-1") == "disc" and B.stage_of("mi-3-diag-26801-1") == "s1"
    assert B.TOTAL == 8000.0 and sum(B.ceilings().values()) == 8000


def test_calibration_pool_and_references_build():
    import mi3_cal as C
    import mi3_eval as E
    assert len(C.CANDS) == 24 and len({c["name"] for c in C.CANDS}) == 24
    sigs = {}
    for c in C.CANDS + list(E.REFS.values()):
        dom, max_s = MS.domain_of(c)
        sigs[c.get("name", c["kind"])] = MS.space_signature(c)[0]
        assert dom({})[0][0] == ("var", "acc")
    assert sigs["dup_seed"] == sigs["seed_lpl"]                        # a syntactic duplicate is behaviourally identical
    r = MS.eval_one(MS.domain_of(dict(kind="a5"))[0], 60.0, 28401, "ADDC")   # mi3/dev
    assert set(r) >= {"exact", "silent", "accepted", "outcome", "cpu_s", "learner_cpu_s"}
