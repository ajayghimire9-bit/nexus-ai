"""Wave 25 anticipatory controller: no peeking, stop rule, revisable beliefs (dev seeds only)."""
from nexus.wave24_v4_core import UNIQUE
from nexus.wave25_anticipate import (AnticipatoryProcedure, QueryExpectationModel, make_regime_episodes,
                                     run_regime_episode)
from nexus.wave25_contracts import learn_contracts
from nexus.wave25_factored import records_world
from nexus.wave25_vault import ContractVault, Episode


def _proc(revisable=True):
    return AnticipatoryProcedure(ContractVault(learn_contracts()), seed=1, revisable=revisable)


def test_q1_behaviour_is_independent_of_held_out_follow_ups():
    world = records_world(1)
    for ep in make_regime_episodes(world, 41, 6, "B"):
        alone = Episode(ep.world, ep.public, ep.queries[:1], ep.answers[:1], ep.teacher)
        a = run_regime_episode(alone, world, "revisable", rp=_proc(), seed=1)
        b = run_regime_episode(ep, world, "revisable", rp=_proc(), seed=1)
        assert a["queries"][0] == b["queries"][0]        # identical probes, labels, status and work on q1


def test_no_probe_after_the_current_answer_is_certified():
    world = records_world(1)
    rp = _proc()
    for ep in make_regime_episodes(world, 42, 6, "B"):
        r = run_regime_episode(ep, world, "revisable", rp=rp, seed=1)
        for q in r["queries"]:
            if q["initial_status"] == UNIQUE:
                assert q["probes"] == 0
            assert not q["false_certificate"]


def test_continuation_belief_revises_down_without_follow_ups_and_fixed_does_not():
    rev, fixed = QueryExpectationModel(revisable=True), QueryExpectationModel(revisable=False)
    for _ in range(20):
        rev.end_episode(0)
        fixed.end_episode(0)
    assert rev.p_cont < 0.1 and fixed.p_cont == 1.0
    for _ in range(20):
        rev.end_episode(1)
    assert rev.p_cont > 0.85


def test_proxy_mixture_moves_toward_the_pool_matching_follow_up_ambiguity():
    qm = QueryExpectationModel()
    for _ in range(10):
        qm.observe_followup(True, {"related": 0.1, "boundary": 0.8})
    assert qm.weights()["boundary"] > 0.8
    for _ in range(30):
        qm.observe_followup(False, {"related": 0.1, "boundary": 0.8})
    assert qm.weights()["related"] > 0.8


def test_no_proxy_cost_when_no_follow_ups_are_expected():
    world = records_world(1)
    rp = _proc()
    for _ in range(40):
        rp.qm.end_episode(0)
    builds = rp.lookahead_log["proxy_builds"]
    for ep in make_regime_episodes(world, 43, 5, "A"):
        run_regime_episode(ep, world, "revisable", rp=rp, seed=1)
    assert rp.lookahead_log["proxy_builds"] == builds
