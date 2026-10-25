"""Wave 25 refocus: persistent version spaces, dual-ledger vault, reasoning procedure (dev seeds only)."""
from collections import Counter

import pytest

from nexus.wave24_domains import vkey
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, Searcher, meter
from nexus.wave25_contracts import learn_contracts
from nexus.wave25_factored import MAX_DEPTH, TASK_BUDGET, ints_world, records_world, run
from nexus.wave25_s3 import enumerate_H, outputs
from nexus.wave25_vault import (PROVED_SOUND, REFUTED, UNPROVED_HEURISTIC, ContractVault, ReasoningProcedure,
                                episode_grammar, make_episodes, run_episode, task_context)


def _rp(seed=1):
    return ReasoningProcedure(ContractVault(learn_contracts()), seed=seed)


def test_multi_query_preserves_version_space_and_witness_only_collapse_is_unsafe():
    """q1 stops on answer agreement without deleting V_t; q2 is re-partitioned over the same V_t."""
    found_unsafe = 0
    checked = 0
    for world in (ints_world(1), records_world(1)):
        rp = _rp()
        for ep in make_episodes(world, 31, 12):
            r = run_episode(ep, world, "full", rp=rp, seed=1)
            assert r["false_certificates"] == 0
            q1, q2 = r["queries"]
            if q1["status"] != UNIQUE:
                continue
            # rebuild V_t after q1 exactly as the episode did: public + q1 probe observations
            tools = episode_grammar(ep, world)
            checked += 1
            if q2["initial_status"] == AMBIGUOUS:
                # a witness-only collapse after q1 would have answered q2 with one program; show it can be wrong
                res = Searcher(tuple(ep.public), ep.queries[0], tools, popper=True, m=meter(TASK_BUDGET),
                               partial_depth=0, max_depth=MAX_DEPTH).run_to(MAX_DEPTH)
                H = enumerate_H(list(ep.public), [t.fn for t in tools], res.size, meter(10**12))
                same_q1 = [h for h, y in zip(H, outputs(H, ep.queries[0], meter(10**12)))
                           if y == vkey(ep.answers[0])]
                preds = {vkey(run(h, ep.queries[1])) for h in same_q1}
                if len(preds) > 1:
                    found_unsafe += 1
    assert checked > 5 and found_unsafe >= 1


def test_q2_needs_no_probe_when_version_space_already_agrees():
    world = records_world(1)
    rp = _rp()
    zero = 0
    for ep in make_episodes(world, 32, 12):
        r = run_episode(ep, world, "full", rp=rp, seed=1)
        q2 = r["queries"][1]
        if q2["initial_status"] == UNIQUE:
            assert q2["probes"] == 0 and q2["solved"]
            zero += 1
    assert zero >= 1


def test_only_proved_sound_contracts_may_prune():
    vault = ContractVault(learn_contracts())
    statuses = Counter(v.status for v in vault.validity)
    assert statuses[PROVED_SOUND] > 0 and statuses[REFUTED] > 0 and statuses[UNPROVED_HEURISTIC] >= 0
    roles = {"F", "S", "Sort", "Agg"}
    vault.pruner_props(roles, ["length", "provenance", "kind"])
    with pytest.raises(PermissionError):
        vault.pruner_props(roles, ["parity"])            # refuted for F/S: may never prune
    with pytest.raises(PermissionError):
        vault.pruner_props({"F", "S", "Sort", "Map", "Agg"}, ["max_atom"])   # not sound under Map


def test_soft_order_never_changes_a_verdict():
    rp = _rp()
    world = records_world(2)
    for ep in make_episodes(world, 33, 8):
        tools = episode_grammar(ep, world)
        for h in enumerate_H(list(ep.public), [t.fn for t in tools], 2, meter(10**12))[:5]:
            rp.record_witnesses(world, [h])
        a = Searcher(tuple(ep.public), ep.queries[1], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                     max_depth=MAX_DEPTH).run_to(MAX_DEPTH)
        b = Searcher(tuple(ep.public), ep.queries[1], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                     max_depth=MAX_DEPTH, order=rp.rank_candidates(world)).run_to(MAX_DEPTH)
        assert a.status == b.status
        assert {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}
    assert rp.vault.heuristics and all(v.status == UNPROVED_HEURISTIC for v in rp.vault.heuristics.values())


def test_utility_gating_deactivates_without_forgetting_and_re_explores():
    rp = _rp()
    ctx = ("RECORDS", "fan<40", "len<=3")
    roles = {"F", "S", "Sort", "Agg"}

    class R:                        # a result whose level 3 was never reached: no saving can be credited
        size = 1

        class searcher:
            early_stopped_depth = None
    for _ in range(4):
        rp.select_active_contracts(ctx, roles)
        rp.update_utility(ctx, Counter({("checks", "length"): 50, ("by", "length", 1): 3}), R, 40, 4)
    active = rp.select_active_contracts(ctx, roles)
    assert "length" not in active                      # negative lower-bound utility: deactivated here
    assert any(v.prop == "length" and v.status == PROVED_SOUND for v in rp.vault.validity)   # never forgotten
    other = ("RECORDS", "fan80+", "len>3")
    assert "length" in rp.select_active_contracts(other, roles)     # still active in an untried context
    explored = []
    for _ in range(6):                                  # every EXPLORE_EVERY-th task of the context re-measures
        explored.append("length" in rp.select_active_contracts(ctx, roles))
        rp.update_utility(ctx, Counter(), R, 40, 4)
    assert any(explored) and not all(explored)


def test_lower_bound_credit_requires_a_completed_level():
    rp = _rp()
    ctx = ("INT_LIST", "fan<40", "len<=3")

    class R:
        size = 3

        class searcher:
            early_stopped_depth = None
    rp.update_utility(ctx, Counter({("checks", "length"): 10, ("by", "length", 1): 2}), R, 30, 4)
    assert rp.vault.utility["length"].observed_work_saved == 2 * 30 * 4
    R.searcher.early_stopped_depth = 3                  # level 3 stopped early: no credit for depth-2 prunes
    rp.update_utility(ctx, Counter({("checks", "length"): 10, ("by", "length", 1): 2}), R, 30, 4)
    assert rp.vault.utility["length"].observed_work_saved == 2 * 30 * 4
