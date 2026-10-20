"""Saved authored integration evidence, not independent scientific outcomes."""
import json
from pathlib import Path
import subprocess
import sys
from nexus.seed.core import Session
from nexus.seed import skill_library as lib
from nexus.seed import skill_programs as ir

ROOT=Path(__file__).resolve().parents[1]


def test_recorded_four_lab_demo_and_exact_restore():
    r=json.loads((ROOT/'artifacts/seed_shared_labs_demo.json').read_text())
    assert r['scientific'] is False and r['new_scientific_environment_interactions']==0
    assert r['restore_exact'] is True and r['authored_actions']==3 and len(r['trace'])==14
    s=Session.restore(r['snapshot']);assert s.snapshot()==r['snapshot'] and s.counts['sandbox_actions']==3
    entries=lib.view(s)['entries'];assert {v['name'] for v in entries}=={'flip','glim','nudge','lefter'}
    assert all(v['status']=='verified_on_authored_checks' for v in entries)
    assert lib.view(s)['learning_rules']['kind_n']=={'list/enumerate':1}
    assert r['ledger_unchanged']==dict(used_s=1943.6321034559958,remaining_s=1656.3678965440042)


def test_recorded_predictions_and_goal_reward_are_derived():
    r=json.loads((ROOT/'artifacts/seed_shared_labs_demo.json').read_text())
    for call in r['trace']:
        if call['request']['op']=='lab_run':
            assert ir.run(call['response']['program'],call['request']['input'])==call['response']['output']
        if call['request']['op']=='lab_goal':assert abs(call['response']['reward']-1.18)<1e-12
    assert sum(call['resources']['sandbox_actions'] for call in r['trace'])==3


def test_saved_demo_verification_without_neural_dependencies():
    code="import sys,json;sys.path.insert(0,sys.argv[1]);from nexus.seed.core import Session;r=json.load(open(sys.argv[2]));s=Session.restore(r['snapshot']);assert s.snapshot()==r['snapshot'];assert not any(m in sys.modules for m in ('torch','numpy','gymnasium'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT/'artifacts/seed_shared_labs_demo.json')],check=True)
