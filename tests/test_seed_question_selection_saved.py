"""Read-only saved scientific evidence. No fit, model, simulator or private file."""
import hashlib
import json
from pathlib import Path
import statistics as st
import subprocess
import sys
import pytest
from nexus.seed import question_selection as qs

ROOT=Path(__file__).resolve().parents[1]


def test_saved_primary_math_averages_random_orders_and_damping_inside_tasks():
    r=json.loads((ROOT/'artifacts/seed_question_selection.json').read_text());c=r['config']
    values=[]
    for task in c['tasks']['train']:
        row=r['rows'][str(task)]
        def score(method):return st.mean(path[p]['query_mse'] for replicas in row[method].values() for path in replicas.values() for p in c['curve_budgets'])
        values.append(score('random')-score('informative'))
    a=r['analysis']['primary_contrast'];mean=st.mean(values);half=2.200985160*st.stdev(values)/12**.5
    assert a['mean']==pytest.approx(mean,abs=1e-15)
    assert a['ci95']==pytest.approx([mean-half,mean+half],abs=1e-15)
    assert a['paired_task_values']==values


def test_stdlib_only_saved_audit_checks_variance_and_exact_old_learner_reproduction():
    code='import sys;sys.path.insert(0,sys.argv[1]);import verify_seed_question_selection as v;r=v.verify();assert r["checked_variances"]==432;assert r["max_original_order_error"]==0.;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts')],check=True,timeout=30)


def test_saved_host_source_hashes_and_debit_reproduce():
    r=json.loads((ROOT/'artifacts/seed_question_selection.json').read_text());c=r['config']
    assert r['config_file_sha256']==hashlib.sha256((ROOT/'configs/seed_question_selection.json').read_bytes()).hexdigest()
    assert r['session_used_s']==c['carried_used_s']+r['execution_debit_s']
    assert r['session_remaining_s']==c['carried_remaining_s']-r['execution_debit_s']
    assert r['host_receipt']['revision']==r['execution_sha']
    assert r['host_receipt']['dataset_hashes']['protocol']==hashlib.sha256((ROOT/'docs/NEXUS_SEED_QUESTION_SELECTION_PROTOCOL.md').read_bytes()).hexdigest()
    assert r['frozen_before_sha256']==r['frozen_after_sha256']


def test_saved_gui_replay_is_identical_and_has_no_scientific_imports():
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_selection import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r["resources"]["real_steps"]==0;assert r["resources"]["world_model_forwards"]==0;assert r["question_selection"]==json.load(open(Path(sys.argv[2])/"artifacts/seed_question_selection.json"))["analysis"];assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
