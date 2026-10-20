"""Read-only regression on the recorded question-utility study."""
import hashlib
import json
from pathlib import Path
import statistics as st
import subprocess
import sys
from nexus.seed import question_utility as q

ROOT=Path(__file__).resolve().parents[1]
def result():return json.loads((ROOT/'artifacts/seed_question_utility.json').read_text())


def test_valid_complete_run_preserves_failed_scientific_screen():
    r=result();assert r['declared_complete'] is True and r['host_receipt']['status']=='complete_development'
    assert r['analysis']['source_screen_pass'] is False
    assert r['analysis']['label']=='source_question_learning_not_demonstrated'
    assert r['analysis']['runtime_promotion'] is False and r['analysis']['learning_to_learn_established'] is False


def test_independent_stdlib_audit_covers_all_features_and_models():
    code='import runpy,sys;p=runpy.run_path(sys.argv[1],run_name="saved_audit");r=p["verify"]();assert r["valid"] and r["checked_variances"]==1008 and r["source_screen_pass"] is False;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_question_utility.py')],check=True,timeout=30)


def test_independent_paired_intervals_use_twelve_tasks():
    r=result();c=r['config']
    for m in ('action_mean','variance','keep'):
        values=[]
        for t in c['tasks']['train']:
            fold=r['folds'][str(c['tasks']['train'].index(t)%4)];cells=fold['evaluation'][str(t)]
            values.append(st.mean(v['query_mse'][m] for v in cells.values())-st.mean(v['query_mse']['learned'] for v in cells.values()))
        a=r['analysis']['contrasts'][m];half=2.200985160*st.stdev(values)/12**.5
        assert a['paired_task_values']==values and a['mean']==st.mean(values)
        assert max(abs(x-y) for x,y in zip(a['ci95'],[st.mean(values)-half,st.mean(values)+half]))<1e-15
        assert a['ci95'][0]<0<a['ci95'][1]


def test_cached_baselines_and_one_core_are_not_extra_replications():
    r=result();p=json.loads((ROOT/r['config']['parent']).read_text())
    for m in ('variance','uniform','keep'):assert r['analysis']['curve_means'][m]==p['analysis']['check_means'][m]
    assert r['analysis']['curve_means']['budget_mean']==r['analysis']['curve_means']['variance']
    assert r['analysis']['independent_pretrained_cores']==1
    for f in r['folds'].values():
        assert len(f['excluded_ids'])==3 and len(f['train_ids'])==9 and not set(f['excluded_ids'])&set(f['train_ids'])
        restored=json.loads(json.dumps(f['models']));assert q.decide(f['held_cases'],restored)==f['decisions']


def test_parent_protocol_frozen_state_and_resource_carry():
    r=result();c=r['config'];h=r['host_receipt']
    for key in ('parent','parent_validation'):assert hashlib.sha256((ROOT/c[key]).read_bytes()).hexdigest()==c[key+'_sha256']
    assert r['config_file_sha256']==hashlib.sha256((ROOT/'configs/seed_question_utility.json').read_bytes()).hexdigest()
    assert h['dataset_hashes']['protocol']==hashlib.sha256((ROOT/'docs/NEXUS_SEED_QUESTION_UTILITY_PROTOCOL.md').read_bytes()).hexdigest()
    assert r['frozen_before_sha256']==r['frozen_after_sha256']
    assert r['session_used_s']==c['carried_used_s']+r['execution_debit_s'] and r['session_remaining_s']==c['carried_remaining_s']-r['execution_debit_s']
    assert r['resources']['real_steps']==r['resources']['imagined_transitions']==r['resources']['world_model_forwards']==0
    assert sum(len(v['beta']) for f in r['folds'].values() for k,v in f['models'].items() if k in ('learned','shuffled_residual'))==432


def test_gui_replay_uses_only_tracked_json_and_stdlib():
    code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_utility import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r["question_utility"]["source_screen_pass"] is False;assert r["status"]=="complete_development";assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
