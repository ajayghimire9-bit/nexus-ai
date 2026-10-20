"""Actual saved results are replayed, not refitted or recollected."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nexus.seed import learning_choice as lc

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text())


def test_actual_results_complete_negative_and_known_anchor_safe():
    r=read('artifacts/seed_learning_choice.json');c=read('configs/seed_learning_choice.json');p=lc.source_pack(ROOT,c)
    assert lc.validate(r,c,p) and r['declared_complete'] is True
    a=r['analysis'];assert not any(a[k] for k in ('coverage_screen_pass','protection_screen_pass','strong_baseline_screen_pass','runtime_promotion','fresh_validation'))
    assert a['retention_pass'] is True and a['known_anchor_cap_pass'] is True
    assert a['choices']==dict(learn=4,ask=80,retain=12)
    assert lc.saved_replay(ROOT)['learning_choice']==a


def test_refit_reference_exactly_reproduces_original_models_and_trajectories():
    r=read('artifacts/seed_learning_choice.json');old=read('artifacts/seed_prefix_consistency.json');seq=read('artifacts/seed_sequential_consistency.json')
    for f in range(4):assert r['folds'][str(f)]['models']['reference']['model']==old['folds'][str(f)]['models']['consistency']
    for t,cell in r['rows'].items():
        assert [v['theta'] for v in cell['reference_refit']]==[v['theta'] for v in seq['rows'][t]['consistency_selector']['frozen']]
        assert r['analysis']['per_task'][t]['constant_damping']==seq['analysis']['per_task'][t]['constant_damping']
    assert r['resources']['cached_baseline_trajectories']==108 and r['resources']['evaluation_trajectories']==36


@pytest.mark.parametrize('fault',['task','model','prefix','question','metric','state','scale','frozen'])
def test_actual_saved_corruptions_fail(fault):
    r=read('artifacts/seed_learning_choice.json');c=r['config'];row=r['rows']['95000000']['protected_rollin'][1]
    if fault=='task':del r['rows']['95000000']
    elif fault=='model':del r['folds']['0']['models']['rollin']
    elif fault=='prefix':r['rows']['95000000']['protected_rollin'].pop()
    elif fault=='question':row['decision']['question']='fabricated answer'
    elif fault=='metric':row['known_damage']=False
    elif fault=='state':row['theta'][0]+=.1
    elif fault=='scale':r['folds']['0']['models']['rollin']['error_scale']=float('inf')
    else:r['frozen_after_sha256']='0'*64
    with pytest.raises((ValueError,KeyError)):lc.validate(r,c,lc.source_pack(ROOT,c))


def test_verifier_runs_without_private_binaries_or_neural_imports(tmp_path):
    names=('artifacts/seed_learning_choice.json','configs/seed_learning_choice.json',
        'artifacts/seed_sequential_consistency.json','artifacts/seed_prefix_consistency.json',
        'artifacts/seed_update_gate.json','configs/seed_update_diagnosis.json','artifacts/seed_nonlinear_learning.json')
    for n in names:
        p=tmp_path/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,p)
    code="import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.learning_choice import saved_replay;d=saved_replay(Path(sys.argv[2]));assert d['learning_choice']['coverage_screen_pass'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(tmp_path)],check=True)
    (tmp_path/'artifacts/seed_update_gate.json').unlink()
    assert subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(tmp_path)],capture_output=True).returncode!=0
