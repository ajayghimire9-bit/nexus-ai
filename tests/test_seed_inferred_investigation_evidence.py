"""Saved repository evidence only; no new collection or neural execution."""
import importlib.util
import json
from pathlib import Path
from nexus.seed import inferred_investigation as n

ROOT=Path(__file__).resolve().parents[1]


def test_saved_full_grid_and_source_boundaries():
    r=json.loads((ROOT/'artifacts/seed_inferred_investigation.json').read_text())
    n.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=13000))
    assert r['registration']['dirty'] is False
    assert r['all_sources_frozen_before_targets'] and r['all_choices_locked_before_final']


def test_independent_saved_arithmetic_and_history():
    p=ROOT/'scripts/verify_seed_inferred_investigation.py'
    spec=importlib.util.spec_from_file_location('inferred_verify',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.verify(ROOT)==json.loads((ROOT/'artifacts/seed_inferred_investigation_audit.json').read_text())


def test_negative_hybrid_result_not_promoted_as_learning_success():
    r=json.loads((ROOT/'artifacts/seed_inferred_investigation.json').read_text());a=r['analysis']
    assert a['hybrid_screen']=='failed' and a['compiled_screen']=='passed' and a['promoted'] is False
    assert a['source_model_recovery'] is True
    assert a['means']['tree_greedy']['total_work']==19880
    assert a['means']['compiled_greedy']['total_work']==9765
    assert a['question_savings']['compiled_greedy']['low']<0<a['question_savings']['compiled_greedy']['high']


def test_carried_resource_ledger_and_clean_source_commit():
    r=json.loads((ROOT/'artifacts/seed_inferred_investigation.json').read_text())
    assert r['execution_sha']=='3fb6831aa9282e55828cb4158dd4e6278d66117a'
    assert r['resources']['real_steps']==12544 and r['execution_debit_s']==3
    assert r['session_used_s']==1990.6321034559958 and r['session_remaining_s']==1609.3678965440042
    assert r['resources']['network_forwards']==r['resources']['updates']==r['resources']['imagined_transitions']==0
