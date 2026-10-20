"""Saved-source replay and corruption audits; no scientific fits or collection."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nexus.seed.update_gate import source_pack,validate,saved_replay
from nexus.seed.cumulative_learning import checkpoint_bytes

ROOT=Path(__file__).resolve().parents[1]


def result():return json.loads((ROOT/'artifacts/seed_update_gate.json').read_text())


def test_complete_saved_negative_result_and_replication_unit():
    r=result();assert r['declared_complete'] is True and validate(r,r['config'],source_pack(ROOT,r['config']))
    assert r['analysis']['source_screen_pass'] is False and r['analysis']['retention_pass'] is True
    assert r['analysis']['curve_means']['constant_gate']<r['analysis']['curve_means']['learned_gate']
    assert saved_replay(ROOT)['update_gate']==r['analysis']


@pytest.mark.parametrize('fault',['seed','task','method','checkpoint','training','training_metric','gate','context','proposal','state','frozen'])
def test_raw_corruption_rejected(fault):
    r=result();row=r['rows']['7201']['95000000']['learned_gate'][1]
    if fault=='seed':del r['rows']['7201']
    elif fault=='task':del r['rows']['7201']['95000000']
    elif fault=='method':del r['rows']['7201']['95000000']['constant_gate']
    elif fault=='checkpoint':r['folds']['0']['models']['7201']['learned_gate']['sha256']='0'*64
    elif fault=='training':r['folds']['0']['models']['7201']['learned_gate']['training'].pop()
    elif fault=='training_metric':del r['folds']['0']['models']['7201']['learned_gate']['training'][0]['gradient_norm']
    elif fault=='gate':row['gate']+=.1
    elif fault=='context':row['gate_context'][0]+=.1
    elif fault=='proposal':row['proposal'][0]+=.1
    elif fault=='state':row['theta'][0]+=.1
    else:r['frozen_during_evaluation']=False
    with pytest.raises((ValueError,KeyError)):validate(r,r['config'],source_pack(ROOT,r['config']))


def test_isolated_cli_and_replay_import_no_neural_runtime():
    command=[sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_update_gate.py')]
    r=subprocess.run(command,check=True,capture_output=True,text=True)
    assert json.loads(r.stdout)['checkpoints_reconstructible']==24
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.update_gate import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['update_gate']['fresh_validation'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)


def test_fresh_clone_missing_checkpoint_fails_and_restore_is_exact(tmp_path,monkeypatch):
    for name in ('artifacts/seed_update_gate.json','artifacts/seed_nonlinear_learning.json',
                 'configs/seed_update_gate.json','configs/seed_update_diagnosis.json'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    spec=importlib.util.spec_from_file_location('shared_gate_verifier',ROOT/'scripts/verify_seed_cumulative_learning.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=tmp_path
    kwargs=dict(study_name='seed_update_gate',identifier='seed-update-gate-1',width=1,validator=validate,packer=source_pack)
    monkeypatch.setattr(sys,'argv',['verify','--check-checkpoints'])
    with pytest.raises(ValueError,match='missing_or_wrong_checkpoint'):m.main(**kwargs)
    directory=tmp_path/'restored';monkeypatch.setattr(sys,'argv',['verify','--restore-checkpoints',str(directory)])
    m.main(**kwargs);assert len(list(directory.glob('*.json')))==24
    for f in result()['folds'].values():
        for arms in f['models'].values():
            for info in arms.values():assert (directory/info['checkpoint']).read_bytes()==checkpoint_bytes(info,width=1)
    with pytest.raises(FileExistsError):m.main(**kwargs)
