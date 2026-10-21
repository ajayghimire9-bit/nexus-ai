"""Repository-only saved evidence; no untracked binaries or collection."""
import importlib.util
import json
from pathlib import Path
from nexus.seed import compiled_greedy as c

ROOT=Path(__file__).resolve().parents[1]


def test_saved_complete_replay_and_frozen_models():
    r=json.loads((ROOT/'artifacts/seed_compiled_greedy.json').read_text())
    c.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=0))
    assert r['host_receipt']['status']=='complete_development'
    assert r['registration']['dirty'] is False


def test_saved_independent_verification():
    path=ROOT/'scripts/verify_seed_compiled_greedy.py'
    spec=importlib.util.spec_from_file_location('compiled_audit',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.verify(ROOT)
    assert result==json.loads((ROOT/'artifacts/seed_compiled_greedy_audit.json').read_text())


def test_cost_claim_and_no_learning_promotion():
    r=json.loads((ROOT/'artifacts/seed_compiled_greedy.json').read_text());a=r['analysis']
    assert a['screen']=='passed' and not a['promoted']
    assert a['means']['compiled_greedy']['total_work']==2208
    assert a['means']['tree_greedy']['total_work']==6012
    assert r['resources']['real_steps']==r['resources']['source_fits']==r['resources']['network_forwards']==0
    assert a['exploratory_question_interval']['low']<0<a['exploratory_question_interval']['high']


def test_protocol_and_result_revisions_separate():
    r=json.loads((ROOT/'artifacts/seed_compiled_greedy.json').read_text())
    assert r['execution_sha']=='7081cc79c0e7f8a98125db7864cfcc3e17d1cb88'
    assert r['session_used_s']==1987.6321034559958
    assert r['session_remaining_s']==1612.3678965440042
