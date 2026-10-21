"""Recorded evidence only. No registered collection or live learner runs."""
import importlib.util
import json
from pathlib import Path
from nexus.seed import source_acquisition as a

ROOT=Path(__file__).resolve().parents[1]


def test_saved_full_numerical_replay():
    r=json.loads((ROOT/'artifacts/seed_source_acquisition.json').read_text())
    a.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=4000))
    assert r['registration']['dirty'] is False


def test_independent_saved_arithmetic_and_immutability():
    p=ROOT/'scripts/verify_seed_source_acquisition.py'
    spec=importlib.util.spec_from_file_location('acquisition_verify',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.verify(ROOT)==json.loads((ROOT/'artifacts/seed_source_acquisition_audit.json').read_text())


def test_negative_screens_and_fixed_eight_example_endpoint():
    r=json.loads((ROOT/'artifacts/seed_source_acquisition.json').read_text());s=r['analysis']
    assert s['heuristic_transfer_screen']==s['strong_advantage_screen']=='failed'
    assert s['repetition_wins_vs_variance']==3 and s['promoted'] is False
    assert s['primary']['learned']>s['primary']['original_order']>s['primary']['source_prior']
    assert len({v['8'] for m,v in s['by_budget'].items() if m!='keep'})==1
    assert a.saved_replay(ROOT)['verification']=='saved_independent_audit_hash'


def test_ledger_and_frozen_execution_revision():
    r=json.loads((ROOT/'artifacts/seed_source_acquisition.json').read_text())
    assert r['execution_sha']=='2a7670284a6a530c8cb739c340ec6a7a06971ef7'
    assert r['resources']['real_steps']==3072 and r['resources']['fitted_ridge_models']==8
    assert r['execution_debit_s']==6 and r['session_used_s']==1996.6321034559958
    assert r['session_remaining_s']==1603.3678965440042
