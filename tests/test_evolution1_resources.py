"""Synthetic operation/clock metadata only. No scientific worker is connected."""
from dataclasses import FrozenInstanceError, replace
import json
import subprocess
import sys

import pytest

from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.fixtures import verify_journal
from nexus.evolution1.resources import (
    Clock, Limits, Operation, ReservationLedger, Ticket, Work, model_work,
)


def limits(physical=None, logical=None, cpu=100, wall=100):
    cap = Work(10, 100, 10, 10)
    return Limits(physical or cap, logical or cap, cpu, wall)


ENV = Operation('env', 'environment', Work(real_steps=1))
MODEL = Operation('model', 'model', model_work((8, 3), 1))
CACHE = Operation('cache', 'cached', MODEL.cost, 'a'*64)


def test_observation_rows_not_action_array_size_determine_charge():
    assert model_work((8, 3), 1) == model_work((8, 3), 8) == Work(0,8,1,1)
    assert model_work((3,), 1) == Work(0,1,1,1)
    assert model_work((8, 3), 1, 2) == Work(0,8,1,2)


@pytest.mark.parametrize('shape,actions', [((8,3),2), ((0,3),1), ((True,3),1),
    ((8,0),1), ((8,3,2),1), ([8,3],1), ((3,),True), ((3,),0)])
def test_bad_batch_metadata_rejected(shape,actions):
    with pytest.raises(ContractError): model_work(shape,actions)


@pytest.mark.parametrize('value', [True, '1', -1, 1.0, float('nan'), float('inf')])
def test_work_and_time_require_finite_integer_counts(value):
    with pytest.raises(ContractError): Work(value)
    with pytest.raises(ContractError): Clock(value, 0)


def test_operation_plan_and_cache_reference_are_strict():
    for plan in ([], (), (ENV,ENV), ('env',)):
        with pytest.raises(ContractError): ReservationLedger(plan,limits())
    for op in (lambda: Operation('e','environment',Work(real_steps=2)),
               lambda: Operation('m','model',Work(imagined_transitions=8)),
               lambda: Operation('c','cached',MODEL.cost),
               lambda: Operation('c','cached',MODEL.cost,True),
               lambda: Operation('../file','environment',ENV.cost)):
        with pytest.raises(ContractError): op()


def test_complete_plan_has_exact_physical_logical_and_cache_accounting():
    ledger = ReservationLedger((ENV,MODEL,CACHE),limits())
    for i,op in enumerate((ENV,MODEL,CACHE)):
        ticket = ledger.reserve(op.key,Clock(2*i,2*i))
        ledger.settle(ticket,'success',Clock(2*i+1,2*i+1))
    report = ledger.close(Clock(6,6))
    assert report.status == 'complete_execution' and report.reason is None
    assert report.physical_reserved == report.physical_completed_reported == Work(1,8,1,1)
    assert report.logical_charged == Work(1,16,2,2)
    assert report.physical_unknown_upper_bound == Work()
    assert report.unresolved_keys == () and report.pending_key is None
    assert report.completed_keys == ('env','model','cache')
    assert report.elapsed == Clock(6,6)
    assert verify_journal(report.events,report.events[-1].fingerprint,len(report.events))
    plan_event = json.loads(report.events[0].payload_json)
    assert [op['key'] for op in plan_event['operations']] == ['env','model','cache']
    cache_event = json.loads(report.events[5].payload_json)
    assert cache_event['cache_record_hash'] == 'a'*64
    with pytest.raises(FrozenInstanceError): report.status = 'invalid'
    with pytest.raises(ContractError): ledger.reserve('env',Clock(7,7))
    with pytest.raises(ContractError): ledger.close(Clock(7,7))


@pytest.mark.parametrize('dimension', range(4))
def test_every_work_dimension_is_reserved_before_dispatch(dimension):
    values = list(MODEL.cost.values()); values[dimension] = max(0,values[dimension]-1)
    op = MODEL if dimension else ENV
    if dimension == 0: values = [0,100,10,10]
    ledger = ReservationLedger((op,),limits(physical=Work(*values)))
    dispatched = []
    with pytest.raises(ContractError,match='pre_call_quota_exhausted'):
        ledger.reserve(op.key,Clock(0,0))
        dispatched.append(op.key)  # unreachable; no worker exists in this test
    report = ledger.close(Clock(1,1))
    assert not dispatched
    assert report.physical_reserved == Work() and report.logical_charged == Work()
    assert report.status == 'incomplete_execution' and report.reason == 'work_cap'


def test_cumulative_reservation_cannot_overshoot_cap_or_refund_failures():
    second = replace(MODEL,key='second')
    ledger = ReservationLedger((MODEL,second),limits(physical=MODEL.cost))
    ticket = ledger.reserve('model',Clock(0,0))
    ledger.settle(ticket,'success',Clock(1,1))
    with pytest.raises(ContractError): ledger.reserve('second',Clock(2,2))
    report = ledger.close(Clock(3,3))
    assert report.physical_reserved == MODEL.cost
    assert report.unresolved_keys == ('second',)
    assert report.status == 'incomplete_execution'


def test_cached_reuse_is_not_free_logical_budget():
    ledger = ReservationLedger((MODEL,CACHE),limits(logical=MODEL.cost))
    t = ledger.reserve('model',Clock(0,0)); ledger.settle(t,'success',Clock(1,1))
    with pytest.raises(ContractError): ledger.reserve('cache',Clock(2,2))
    report = ledger.close(Clock(3,3))
    assert report.physical_reserved == report.logical_charged == MODEL.cost


@pytest.mark.parametrize('outcome,status', [
    ('failed','incomplete_execution'), ('interrupted','incomplete_execution'),
    ('invalid_result','invalid_integrity')])
def test_failed_or_uncertain_work_keeps_charge_without_inventing_completion(outcome,status):
    ledger = ReservationLedger((MODEL,),limits())
    t = ledger.reserve('model',Clock(0,0))
    ledger.settle(t,outcome,Clock(1,1))
    report = ledger.close(Clock(2,2))
    assert report.status == status
    assert report.physical_reserved == report.logical_charged == MODEL.cost
    assert report.physical_completed_reported == Work()
    assert report.physical_unknown_upper_bound == MODEL.cost
    assert report.unresolved_keys == ('model',)


def test_interruption_between_reservation_and_settlement_is_explicit():
    ledger = ReservationLedger((MODEL,ENV),limits())
    ledger.reserve('model',Clock(0,0))
    report = ledger.close(Clock(1,1))
    assert report.status == 'incomplete_execution'
    assert report.pending_key == 'model'
    assert report.physical_unknown_upper_bound == MODEL.cost
    assert report.physical_reserved == MODEL.cost
    assert report.unresolved_keys == ('model','env')


def test_pending_duplicate_forged_replayed_and_cross_ledger_tickets_rejected():
    ledger = ReservationLedger((MODEL,ENV),limits())
    other = ReservationLedger((MODEL,),limits())
    t = ledger.reserve('model',Clock(0,0))
    alien = other.reserve('model',Clock(0,0))
    with pytest.raises(ContractError): ledger.reserve('env',Clock(0,0))
    for bad in (None,Ticket(MODEL),alien):
        with pytest.raises(ContractError): ledger.settle(bad,'success',Clock(1,1))
    ledger.settle(t,'success',Clock(1,1))
    with pytest.raises(ContractError): ledger.settle(t,'success',Clock(1,1))
    with pytest.raises(ContractError): ledger.reserve('model',Clock(1,1))
    report = ledger.close(Clock(2,2))
    assert report.physical_completed_reported == MODEL.cost
    assert report.status == 'incomplete_execution'  # planned ENV was omitted


@pytest.mark.parametrize('cpu,wall', [(100,0),(0,100),(101,1),(1,101)])
def test_elapsed_time_cap_denies_new_work_before_dispatch(cpu,wall):
    ledger = ReservationLedger((MODEL,),limits())
    with pytest.raises(ContractError): ledger.reserve('model',Clock(cpu,wall))
    report = ledger.close(Clock(cpu,wall))
    assert report.status == 'incomplete_execution' and report.reason == 'time_cap'
    assert report.physical_reserved == Work()


def test_late_completion_is_counted_but_cannot_be_labeled_complete():
    ledger = ReservationLedger((MODEL,),limits())
    t = ledger.reserve('model',Clock(0,0))
    ledger.settle(t,'success',Clock(101,101))
    report = ledger.close(Clock(101,101))
    assert report.physical_completed_reported == MODEL.cost
    assert report.status == 'incomplete_execution' and report.reason == 'time_cap'


def test_nonmonotonic_clock_marks_integrity_failure_and_preserves_pending_work():
    ledger = ReservationLedger((MODEL,),limits())
    t = ledger.reserve('model',Clock(5,5))
    with pytest.raises(ContractError): ledger.settle(t,'success',Clock(4,6))
    report = ledger.close(Clock(4,4))
    assert report.status == 'invalid_integrity' and report.reason == 'invalid_clock'
    assert report.elapsed == Clock(5,5)
    assert report.physical_unknown_upper_bound == MODEL.cost


def test_empty_success_reports_are_not_possible_and_failure_is_not_inconclusive():
    ledger = ReservationLedger((ENV,),limits())
    assert ledger.close(Clock(0,0)).status == 'incomplete_execution'
    # This ledger never classifies scientific hypotheses; only operation completion.


def test_cached_only_accounting_and_unknown_keys_do_not_invent_physical_work():
    ledger = ReservationLedger((CACHE,),limits(physical=Work()))
    with pytest.raises(ContractError): ledger.reserve('not_planned',Clock(0,0))
    t = ledger.reserve('cache',Clock(0,0)); ledger.settle(t,'success',Clock(1,1))
    report = ledger.close(Clock(2,2))
    assert report.status == 'complete_execution'
    assert report.physical_reserved == report.physical_completed_reported == Work()
    assert report.logical_charged == CACHE.cost


def test_initial_journal_anchor_binds_plan_and_limits():
    def close_for(plan, caps):
        return ReservationLedger(plan,caps).close(Clock(0,0))
    a = close_for((MODEL,),limits())
    b = close_for((replace(MODEL,key='different'),),limits())
    c = close_for((MODEL,),limits(cpu=101))
    assert len({r.events[0].fingerprint for r in (a,b,c)}) == 3


def test_reproducible_reports_and_import_boundary():
    reports = []
    for _ in range(2):
        ledger = ReservationLedger((MODEL,),limits())
        t = ledger.reserve('model',Clock(0,0)); ledger.settle(t,'success',Clock(1,1))
        reports.append(ledger.close(Clock(2,2)))
    assert reports[0] == reports[1]
    code = ('import sys; import nexus.evolution1.resources; '
            'assert not any(n in sys.modules for n in '
            '("torch","numpy","gymnasium","nexus.world","nexus.tasks"))')
    subprocess.run([sys.executable,'-B','-c',code],check=True)
