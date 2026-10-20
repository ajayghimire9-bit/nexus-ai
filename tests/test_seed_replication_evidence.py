"""Repository-only verification; no scientific collection or fitting."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_independent_replay_and_provenance():
    r=json.loads(subprocess.check_output([sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_investigation_replication.py')],cwd=ROOT,text=True))
    assert r['valid'] and r['old_artifacts_unchanged']==805 and r['policy_replays']==480
    assert r['independent_trees']==3 and r['df']==2
    assert r['training']==r['collection']==r['neural_inference']==0


def test_honest_failed_screen_and_independent_units():
    from nexus.seed.investigation_replication import saved_replay
    row=saved_replay(ROOT);a=row['investigation_transfer']
    assert a['screen']=='failed' and not a['checks']['greedy_quality'] and not a['promoted']
    assert a['means']['tree_greedy']['questions']>a['means']['greedy']['questions']
    assert a['question_savings']['greedy']['n']==3
    assert a['checks']['tail_removed'] and a['checks']['total_reduction']
