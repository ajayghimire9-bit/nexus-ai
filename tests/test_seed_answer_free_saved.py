"""Saved-evidence verification only: no fitting, neural imports or collection."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def audited():
    proc=subprocess.run([sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_answer_free_utility.py')],text=True,capture_output=True,check=True,timeout=30)
    return json.loads(proc.stdout),json.loads((ROOT/'artifacts/seed_answer_free_utility.json').read_text())


def test_saved_raw_complete_is_distinct_from_failed_scientific_screen(audited):
    v,r=audited
    assert v['valid'] and r['declared_complete'] and r['host_receipt']['status']=='complete_development'
    assert r['analysis']['label']=='source_screen_failed' and not v['source_screen_pass']
    assert not r['analysis']['runtime_promotion'] and not r['analysis']['learning_to_learn_established']


def test_independent_variance_arithmetic_and_singleton(audited):
    v,r=audited;assert v['checked_variances']==1008 and v['max_variance_error']<2e-5
    s=r['analysis'];assert s['primary_means']['original_order']==s['primary_means']['source_mean']
    assert len({s['by_budget']['8'][m] for m in ('learned','variance','uniform','original_order','source_mean','oracle')})==1


def test_resource_and_ledger_conservation(audited):
    _,r=audited;w=r['resources']
    assert all(w[k]==0 for k in ('real_steps','imagined_transitions','world_model_forwards','updates'))
    assert w['predictor_ridge_solves']==4 and w['predictor_coefficients']==44
    assert r['session_used_s']==r['config']['carried_used_s']+r['execution_debit_s']
    assert r['session_remaining_s']==r['config']['carried_remaining_s']-r['execution_debit_s']
    assert abs(r['session_used_s']+r['session_remaining_s']-3600)<1e-9


def test_isolated_verifier_has_no_neural_or_scientific_runtime():
    code='import runpy,sys;r=runpy.run_path(sys.argv[1],run_name="import_only");r["verify"]();assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_answer_free_utility.py')],check=True,timeout=30)
