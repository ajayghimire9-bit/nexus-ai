"""Recorded evidence only; no collection, source fit, neural inference or run."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_independent_saved_arithmetic_provenance_and_history():
    result=json.loads(subprocess.check_output([sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_investigation_transfer.py')],cwd=ROOT,text=True))
    assert result['valid'] and result['recorded_policy_replays']==160
    assert result['historical_artifacts_unchanged']==797
    assert result['collection']==result['model_inference']==result['training']==0


def test_negative_screen_and_read_only_display():
    from nexus.seed.investigation_transfer import saved_replay
    row=saved_replay(ROOT);s=row['investigation_transfer']
    assert s['screen']=='failed' and not s['promoted']
    assert s['means']['learned']['questions']==3.375
    assert s['checks']==dict(exhaustive=False,fixed_order=False,greedy=False,no_library=True)
    assert row['resources']['real_steps']==1536
