"""Saved-result audit only: no new observations, fitting or neural calls."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_saved_arithmetic_hashes_and_mixture_limit():
    r=json.loads(subprocess.check_output([sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_investigation_hybrid.py')],cwd=ROOT,text=True))
    assert r['valid'] and r['historical_artifacts_unchanged']==801
    assert r['recorded_policy_replays']==160 and r['source_cost_charged']
    assert r['collection']==r['training']==r['neural_inference']==0
    assert r['mixture_sensitivity']['mean_questions']['tree_greedy']==3.125
    assert r['mixture_sensitivity']['mean_questions']['greedy']==3


def test_registered_pass_not_promoted_or_significant_superiority():
    from nexus.seed.investigation_hybrid import saved_replay
    row=saved_replay(ROOT);s=row['investigation_transfer']
    assert s['screen']=='passed' and all(s['checks'].values()) and not s['promoted']
    assert s['question_savings']['greedy']['low']<0<s['question_savings']['greedy']['high']
    assert s['means']['tree_greedy']['max_questions']==4
    assert s['means']['tree_fixed']['five_question_tail']==6
