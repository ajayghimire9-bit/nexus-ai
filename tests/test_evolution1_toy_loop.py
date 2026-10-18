"""Adversarial toy-loop tests; all feedback/outcomes are synthetic scalars."""
from dataclasses import asdict, FrozenInstanceError, replace
import json
import importlib.util
import math
from pathlib import Path
import subprocess
import sys

import pytest

from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.fixtures import verify_journal
from nexus.evolution1.promotion import FixtureAuditor, FixturePromotionHarness
from nexus.evolution1.resources import Work
from nexus.evolution1.toy_loop import (
    AdaptiveProposer, ANCHORS, CONTEXT, DevelopmentGate, FixedProposer,
    RandomProposer, TEST_KEY, TrainingFeedback, VARIANTS,
    retain_or_rollback, run_cycle, run_training, synthetic_case,
)


def ids(run): return tuple(a.variant_id for a in run.attempts)


def test_informative_feedback_changes_parameters_and_the_next_proposal():
    rows,_ = synthetic_case('aligned_signal')
    learned = run_training(AdaptiveProposer(7),rows)
    withheld = run_training(AdaptiveProposer(7),rows,withhold_feedback=True)
    assert ids(learned)[:2] == ids(withheld)[:2] == tuple(v.fingerprint for v in ANCHORS)
    assert ids(learned)[2] != ids(withheld)[2]
    state = json.loads(learned.policy_after)
    assert state['updates'] == 4 and all(math.isfinite(w) for w in state['weights'])
    assert any(abs(w)>1e-8 for w in state['weights'])
    assert learned.policy_before != learned.policy_after
    assert learned.attempts[1].policy_after != learned.attempts[1].policy_before


def test_withheld_feedback_does_not_change_the_learning_state():
    run = run_training(AdaptiveProposer(7),synthetic_case('aligned_signal')[0],withhold_feedback=True)
    assert run.policy_before == run.policy_after
    assert all(a.policy_before == a.policy_after for a in run.attempts)
    assert json.loads(run.policy_after)['updates'] == 0


@pytest.mark.parametrize('policy_type',[AdaptiveProposer,RandomProposer,FixedProposer])
def test_same_seed_reproduces_full_trajectory_and_equal_registered_budgets(policy_type):
    rows,_ = synthetic_case('aligned_signal')
    a = run_training(policy_type(7),rows); b = run_training(policy_type(7),rows)
    assert a == b and len(a.attempts) == len(set(ids(a))) == 4 < 12
    assert a.resources.logical_charged == Work(real_steps=4,imagined_transitions=6144)
    assert a.resources.physical_reserved == a.resources.physical_completed_reported == Work()
    assert a.broker_charged.steps == a.broker_charged.cpu_units == 4
    assert a.resources.status == 'complete_execution'
    assert verify_journal(a.history,a.history[-1].fingerprint,len(a.history))


def test_failed_candidates_consume_budget_and_have_explicit_feedback():
    rows,_ = synthetic_case('aligned_signal'); rows = list(rows)
    rows[8] = replace(rows[8],score=None,failed=True)
    run = run_training(AdaptiveProposer(7),rows)
    assert run.attempts[1].failed and run.attempts[1].score is None
    assert run.broker_charged.steps == run.broker_charged.cpu_units == 4
    assert run.resources.logical_charged.real_steps == 4
    assert run.status == 'complete_execution'  # valid evaluated failure, not missing data


def test_duplicate_choice_gets_no_second_receipt_and_stops_incomplete(monkeypatch):
    policy = AdaptiveProposer(7)
    monkeypatch.setattr(policy,'choose',lambda available,context:ANCHORS[0])
    run = run_training(policy,synthetic_case('aligned_signal')[0])
    assert ids(run) == tuple(v.fingerprint for v in ANCHORS)
    assert len(run.broker_events) == 4  # exactly two reserve/settlement pairs
    assert run.broker_charged.steps == 2
    assert run.status == 'incomplete_execution' and run.candidate is None
    assert run.history[-1].kind == 'rejected_duplicate_or_invalid'


def test_resource_exhaustion_stops_without_a_gate_or_free_retry():
    train,dev = synthetic_case('aligned_signal')
    result = run_cycle(AdaptiveProposer(7),train,dev,
                       work_cap=Work(real_steps=2,imagined_transitions=3072))
    run = result['training']
    assert len(run['attempts']) == 2 and run['broker_charged']['steps'] == 2
    assert run['resources']['reason'] == 'work_cap'
    assert result['gate'] is None and result['decision'] == 'incomplete_no_promotion'
    assert result['incumbent'] == run['initial']


def test_development_outcomes_do_not_change_policy_or_training_history():
    train,dev = synthetic_case('aligned_signal')
    _,reverse = synthetic_case('development_reversal')
    good = run_cycle(AdaptiveProposer(7),train,dev)
    bad = run_cycle(AdaptiveProposer(7),train,reverse)
    assert good['training'] == bad['training']
    assert good['decision'] == 'fixture_promoted'
    assert bad['decision'] == 'development_rejected_preserved'
    assert bad['gate']['gain'] < 0
    assert bad['incumbent'] == bad['training']['initial']


def test_assessment_objects_or_extra_fields_cannot_enter_the_update_api():
    train,dev = synthetic_case('aligned_signal')
    run = run_training(AdaptiveProposer(7),train)
    gate = DevelopmentGate(dev).assess(run)
    policy = AdaptiveProposer(7); before = policy.learned_state()
    for bad in (gate,asdict(gate),dev,None,{'score':1,'phase':'development'}):
        with pytest.raises(ContractError): policy.update(bad,CONTEXT)
    assert policy.learned_state() == before
    with pytest.raises(TypeError):
        TrainingFeedback(VARIANTS[0].fingerprint,.5,False,'a'*64,assessment_score=1)


@pytest.mark.parametrize('value',[True,'0.5',float('nan'),float('inf'),-1,2])
def test_invalid_training_feedback_rejected(value):
    with pytest.raises(ContractError): TrainingFeedback(VARIANTS[0].fingerprint,value,False,'a'*64)


def test_replayed_training_feedback_cannot_double_update():
    policy = AdaptiveProposer(7)
    feedback = TrainingFeedback(VARIANTS[0].fingerprint,.7,False,'a'*64)
    policy.update(feedback,CONTEXT); state = policy.learned_state()
    with pytest.raises(ContractError): policy.update(feedback,CONTEXT)
    assert policy.learned_state() == state


def test_frozen_history_and_complete_gate_grid_are_required():
    train,dev = synthetic_case('aligned_signal')
    run = run_training(AdaptiveProposer(7),train)
    with pytest.raises(FrozenInstanceError): run.attempts[0].score = 1
    for bad in (dev[:-1],dev+(dev[0],),dev[:-1]+(dev[0],)):
        with pytest.raises(ContractError): DevelopmentGate(bad)
    for altered in (replace(run,history=run.history[:-1]),
                    replace(run,attempts=run.attempts[:2],history=run.history[:2]),
                    replace(run,candidate=run.initial),
                    replace(run,resources=replace(run.resources,status='incomplete_execution'))):
        with pytest.raises(ContractError): DevelopmentGate(dev).assess(altered)
    gate = DevelopmentGate(dev); gate.assess(run)
    with pytest.raises(ContractError): gate.assess(run)


def test_integrity_mismatch_after_promotion_rolls_back_and_keeps_archive():
    train,dev = synthetic_case('aligned_signal')
    run = run_training(AdaptiveProposer(7),train)
    bad_observed = replace(run.candidate,memory_state_hash='0'*64)
    result = run_cycle(AdaptiveProposer(7),train,dev,observed_snapshot=bad_observed)
    assert result['decision'] == 'integrity_mismatch_rolled_back'
    assert result['incumbent'] == asdict(run.initial)
    assert len(result['archive']) == 2
    assert [e[0] for e in result['promotion_events']] == ['promoted','rolled_back']


def test_rollback_restores_last_accepted_incumbent_not_always_the_original():
    train,_ = synthetic_case('aligned_signal')
    run = run_training(AdaptiveProposer(7),train)
    harness = FixturePromotionHarness(run.initial,TEST_KEY)
    accepted = run.candidate
    auditor = FixtureAuditor(TEST_KEY)
    harness.promote_for_test(accepted,'a'*64,auditor.attest(accepted,'a'*64,'pass'))
    next_candidate = replace(accepted,variant_id=VARIANTS[9].fingerprint)
    harness.promote_for_test(next_candidate,'b'*64,auditor.attest(next_candidate,'b'*64,'pass'))
    incumbent,rolled_back = retain_or_rollback(harness,replace(next_candidate,context_state_hash='0'*64))
    assert rolled_back and incumbent is accepted
    assert len(harness.archived_snapshots) == 3


def test_fixed_heuristic_can_outperform_the_adaptive_proposer():
    train,_ = synthetic_case('heuristic_counterexample')
    adaptive = run_training(AdaptiveProposer(7),train)
    fixed = run_training(FixedProposer(7),train)
    assert sum(a.score for a in fixed.attempts) > sum(a.score for a in adaptive.attempts)
    assert max(a.score for a in fixed.attempts) > max(a.score for a in adaptive.attempts)


def test_baselines_do_not_learn_and_exhaustive_search_is_forbidden():
    train,_ = synthetic_case('aligned_signal')
    for cls in (FixedProposer,RandomProposer):
        run = run_training(cls(7),train)
        assert run.policy_before == run.policy_after
    for n in (True,0,1,7,12,'4'):
        with pytest.raises(ContractError): run_training(AdaptiveProposer(7),train,proposals=n)


def test_toy_loop_imports_no_scientific_stack():
    code = ('import sys; import nexus.evolution1.toy_loop; '
            'assert not any(n in sys.modules for n in '
            '("numpy","torch","gymnasium","nexus.world","nexus.tasks"))')
    subprocess.run([sys.executable,'-B','-c',code],check=True)


def test_saved_example_builder_reproduces_and_counts_all_fixture_lookups():
    path = Path(__file__).resolve().parents[1]/'scripts/run_evolution1_toy_loop.py'
    spec = importlib.util.spec_from_file_location('toy_example',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    example = module.build_demo()
    assert example == module.build_demo()
    runs = [r for case in example['cases'].values() for r in case['runs'].values()]
    assert sum(len(r['training']['attempts']) for r in runs)+4 == example['demo_training_scalar_lookups'] == 40
    assert sum(r['gate']['query_count'] for r in runs) == example['demo_development_scalar_lookups'] == 18
    assert all(r['mode'] == 'synthetic_only' for r in runs)
    intervention = example['feedback_intervention']
    assert intervention['fed_indices'][:2] == intervention['withheld_indices'][:2]
    assert intervention['fed_indices'][2] != intervention['withheld_indices'][2]
