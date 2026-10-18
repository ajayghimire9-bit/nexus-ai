"""Deterministic synthetic contracts only: no planner/model/environment execution."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nexus.evolution1.catalogue import (
    ContractError, Generator, Rule, Variant, catalogue, parse_proposal, plan_bound,
)
from nexus.evolution1.fixtures import (
    FixtureBroker, FixtureCost, FixtureTable, PublicFixtureContext, TrainingFixture,
    verify_journal,
)
from nexus.evolution1.promotion import (
    FixtureAudit, FixtureAuditor, FixturePromotionHarness, FixtureSnapshot,
)

VARIANTS = catalogue()
KEY = b'synthetic-test-key-only'
HEAD = 'a' * 64


def table(failed=False):
    return FixtureTable(PublicFixtureContext(3, 3, 200, 1536), [
        TrainingFixture(v.fingerprint, None if failed else i / 12, failed, 10)
        for i, v in enumerate(VARIANTS)
    ])


def broker(t=None, cap=None, attempts=32):
    return FixtureBroker(t if t is not None else table(),
                         cap if cap is not None else FixtureCost(2400, 4000000, 120), attempts)


def snapshot(index):
    return FixtureSnapshot(VARIANTS[index].fingerprint, str(index + 1) * 64, 'a'*64, 'b'*64)


def test_closed_catalogue_roundtrip_and_immutable_values():
    assert len(VARIANTS) == len({v.fingerprint for v in VARIANTS}) == 12
    assert VARIANTS == catalogue()
    for v in VARIANTS:
        assert parse_proposal(v.wire()) == v
        assert v.wire() == parse_proposal(v.wire()).wire()
        with pytest.raises(FrozenInstanceError):
            v.horizon = 64


@pytest.mark.parametrize('field,value', [
    ('horizon', True), ('horizon', '16'), ('horizon', 16.0), ('horizon', 32),
    ('rule', 'eval'), ('rule', 1), ('generator', 'exec'), ('catalogue', 'a'*64),
])
def test_invalid_values_rejected(field, value):
    payload = VARIANTS[0].payload(); payload[field] = value
    with pytest.raises(ContractError):
        parse_proposal(json.dumps(payload))


@pytest.mark.parametrize('field', ['code', 'path', 'seed', 'split', 'holdout',
                                   'budget', 'permissions', 'callback', 'command'])
def test_no_extra_capabilities_in_message(field):
    payload = VARIANTS[0].payload(); payload[field] = '__import__("os")'
    with pytest.raises(ContractError):
        parse_proposal(json.dumps(payload))


@pytest.mark.parametrize('wire', [None, b'{}', '{}', '[]', 'null', '"hello"',
    '{"horizon":4,"horizon":8}', '{"x":NaN}', '{"x":Infinity}',
    '['*500 + '0' + ']'*500, ' '*1025])
def test_hostile_or_incomplete_wire_rejected(wire):
    with pytest.raises(ContractError):
        parse_proposal(wire)


@pytest.mark.parametrize('actions', [3, 5])
def test_cost_bounds_are_maximal_without_exceeding_cap(actions):
    for v in VARIANTS:
        bound = plan_bound(v, actions, 1536)
        n = bound.candidates_per_root
        cost = n*v.horizon if v.rule is Rule.FLAT else actions + actions*n*v.horizon
        increment = v.horizon if v.rule is Rule.FLAT else actions*v.horizon
        assert bound.imagined_per_decision == cost <= 1536 < cost + increment


@pytest.mark.parametrize('actions,cap', [(True,1536),(3,True),('3',1536),
                                        (0,1536),(3,1537),(16,16)])
def test_bad_or_infeasible_bounds_rejected(actions, cap):
    with pytest.raises(ContractError):
        plan_bound(Variant(Rule.SUCCESSOR,Generator.IID,16), actions, cap)


@pytest.mark.parametrize('value', [True, '1', -1, 1.5, float('inf')])
def test_costs_require_nonnegative_integers(value):
    with pytest.raises(ContractError):
        FixtureCost(value, 0, 0)


@pytest.mark.parametrize('score', [True, '0.1', float('nan'), float('inf'), -0.1, 1.1])
def test_fixture_scores_are_finite_and_typed(score):
    with pytest.raises(ContractError):
        TrainingFixture(VARIANTS[0].fingerprint, score, False, 10)


def test_only_complete_training_catalogue_can_be_loaded():
    context = table().context
    rows = [TrainingFixture(v.fingerprint, .5, False, 10) for v in VARIANTS]
    for bad in (rows[:-1], rows+[rows[0]], rows[:-1]+[rows[0]]):
        with pytest.raises(ContractError): FixtureTable(context, bad)
    with pytest.raises(ContractError):
        TrainingFixture(VARIANTS[0].fingerprint,.5,False,10,purpose='confirmation')


@pytest.mark.parametrize('cap', [FixtureCost(199, 4000000, 120),
    FixtureCost(2400, 1, 120), FixtureCost(2400, 4000000, 9)])
def test_budget_rejection_has_no_feedback_or_materialization(cap):
    t = table(); b = broker(t,cap)
    with pytest.raises(ContractError): b.submit(VARIANTS[0].wire())
    assert b.charged == FixtureCost(0,0,0)
    assert t.fixture_materializations == 0
    assert [e.kind for e in b.journal()] == ['rejected']


def test_reservation_accounting_cache_reuse_and_duplicate_handling():
    t = table(); b = broker(t)
    receipt = b.submit(VARIANTS[0].wire())
    assert receipt.charged == b.charged == FixtureCost(200,307200,10)
    assert [e.kind for e in b.journal()] == ['reserved','settled']
    with pytest.raises(ContractError): b.submit(VARIANTS[0].wire())
    assert b.charged == receipt.charged and t.fixture_materializations == 1
    # A new search process pays its full fixture cost despite table reuse.
    assert broker(t).submit(VARIANTS[0].wire()).charged == receipt.charged
    assert t.fixture_materializations == 1
    old = b.journal()
    b.submit(VARIANTS[1].wire())
    assert len(old) == 3 and len(b.journal()) == 5
    assert b.charged == receipt.charged.plus(receipt.charged)
    assert verify_journal(b.journal())
    assert set(json.loads(receipt.wire())) == {
        'mode','catalogue','variant_id','score','failed','charged','cumulative','event_id'}
    assert set(json.loads(b.public_context())) == {
        'mode','catalogue','n_actions','obs_dim','episode_steps','imagined_cap'}


def test_failed_fixture_is_explicit_and_still_fully_charged():
    b = broker(table(True)); receipt = b.submit(VARIANTS[0].wire())
    assert receipt.failed and receipt.score is None
    assert receipt.charged == FixtureCost(200,307200,10)


def test_full_grid_and_cumulative_budget_are_enforced():
    t = table(); b = broker(t)
    receipts = [b.submit(v.wire()) for v in VARIANTS]
    assert t.fixture_materializations == 12
    assert b.charged.steps == 2400 and b.charged.cpu_units == 120
    assert b.charged.imagined_states == sum(r.charged.imagined_states for r in receipts)
    limited = broker(cap=receipts[0].charged)
    limited.submit(VARIANTS[0].wire())
    with pytest.raises(ContractError,match='fixture_budget_exhausted'):
        limited.submit(VARIANTS[1].wire())
    assert limited.charged == receipts[0].charged


def test_internal_fault_does_not_refund_or_allow_retry(monkeypatch):
    t = table(); b = broker(t)
    def fault(_): raise RuntimeError('private fixture detail')
    monkeypatch.setattr(t, '_read', fault)
    with pytest.raises(ContractError, match='^fixture_materialization_failed$'):
        b.submit(VARIANTS[0].wire())
    assert b.charged == FixtureCost(200,307200,10)
    assert b.journal()[-1].kind == 'internal_failure'
    with pytest.raises(ContractError, match='duplicate_proposal'):
        b.submit(VARIANTS[0].wire())


def test_bounded_attempts_and_invalid_proposals_are_not_free_unbounded_queries():
    b = broker(attempts=2)
    for _ in range(2):
        with pytest.raises(ContractError): b.submit('{}')
    before = b.journal()
    with pytest.raises(ContractError, match='attempt_limit'): b.submit(VARIANTS[0].wire())
    assert b.journal() == before and b.charged == FixtureCost(0,0,0)


def test_journal_reproduction_and_tamper_detection():
    b1, b2 = broker(), broker()
    for b in (b1,b2):
        for v in VARIANTS[:2]: b.submit(v.wire())
    events = b1.journal()
    assert events == b2.journal() and verify_journal(events)
    for altered in (events[1:], events[::-1], events[:1]+events[2:],
                    (replace(events[0],payload_json='{}'),)+events[1:]):
        with pytest.raises(ContractError): verify_journal(altered)
    # A valid prefix cannot be detected as truncated without an external head.
    assert verify_journal(events[:-1])
    assert verify_journal(events, events[-1].fingerprint, len(events))
    with pytest.raises(ContractError):
        verify_journal(events[:-1], events[-1].fingerprint, len(events))
    with pytest.raises(ContractError):
        verify_journal(events, expected_count=True)


def test_boolean_event_index_cannot_impersonate_integer():
    b = broker(); b.submit(VARIANTS[0].wire())
    events = b.journal()
    with pytest.raises(ContractError):
        verify_journal((events[0], replace(events[1], sequence=True)))


@pytest.mark.parametrize('decision', [[], {}, True, 'approve'])
def test_audit_decisions_fail_with_contract_error_for_invalid_types(decision):
    with pytest.raises(ContractError):
        FixtureAuditor(KEY).attest(snapshot(1), HEAD, decision)


def test_audited_fixture_promotion_rollback_preserves_state_references_and_archive():
    initial, candidate = snapshot(0), snapshot(1)
    h = FixturePromotionHarness(initial,KEY)
    audit = FixtureAuditor(KEY).attest(candidate,HEAD,'pass')
    h.promote_for_test(candidate,HEAD,audit)
    assert h.incumbent is candidate
    assert h.rollback_for_test() is initial and h.incumbent is initial
    assert h.archived_snapshots == (initial,candidate)
    assert [e[0] for e in h.events] == ['promoted','rolled_back']
    with pytest.raises(ContractError,match='audit_replay'):
        h.promote_for_test(candidate,HEAD,audit)
    with pytest.raises(ContractError): h.rollback_for_test()


@pytest.mark.parametrize('decision', ['reject','incomplete','invalid'])
def test_nonpassing_audit_never_promotes(decision):
    h = FixturePromotionHarness(snapshot(0),KEY)
    audit = FixtureAuditor(KEY).attest(snapshot(1),HEAD,decision)
    with pytest.raises(ContractError): h.promote_for_test(snapshot(1),HEAD,audit)
    assert h.incumbent == snapshot(0) and len(h.archived_snapshots) == 1


def test_missing_forged_stale_or_wrong_candidate_audits_rejected():
    initial,candidate = snapshot(0),snapshot(1)
    h = FixturePromotionHarness(initial,KEY)
    audit = FixtureAuditor(KEY).attest(candidate,HEAD,'pass')
    bad_cases = [(candidate,HEAD,None),
                 (candidate,'b'*64,audit), (snapshot(2),HEAD,audit),
                 (candidate,HEAD,replace(audit,signature='0'*64)),
                 (candidate,HEAD,FixtureAuditor(b'wrong-fixture-key').attest(candidate,HEAD,'pass'))]
    for args in bad_cases:
        with pytest.raises(ContractError): h.promote_for_test(*args)
    with pytest.raises(ContractError):
        FixtureAudit(candidate.fingerprint,HEAD,'pass',True)
    assert h.incumbent == initial and not h.events


def test_import_does_not_load_scientific_stack():
    # Fresh interpreter, no pytest/plugin imports obscuring the import boundary.
    code = ('import sys; import nexus.evolution1.catalogue; '
            'import nexus.evolution1.fixtures; import nexus.evolution1.promotion; '
            'assert not any(x in sys.modules for x in '
            '["torch","numpy","gymnasium","nexus.world","nexus.tasks"])')
    subprocess.run([sys.executable,'-B','-c',code],check=True)


def test_source_contracts_have_no_dynamic_execution_or_io_imports():
    import ast
    root = Path(__file__).resolve().parents[1]/'src/nexus/evolution1'
    allowed = {'dataclasses','enum','hashlib','itertools','json','math','hmac','random',
               'catalogue','fixtures','promotion','resources'}
    for path in root.glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): assert all(n.name in allowed for n in node.names)
            if isinstance(node,ast.ImportFrom): assert node.module in allowed
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                assert node.func.id not in {'open','exec','eval','compile','__import__'}
