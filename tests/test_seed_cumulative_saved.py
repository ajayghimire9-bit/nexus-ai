"""Recorded cross-fit evidence; no training or environment execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nexus.seed.cumulative_learning import source_pack,validate,saved_replay,checkpoint_bytes

ROOT=Path(__file__).resolve().parents[1]


def result():return json.loads((ROOT/'artifacts/seed_cumulative_learning.json').read_text())


def test_saved_crossfit_complete_arithmetic_and_failed_screen():
    r=result();c=r['config'];assert validate(r,c,source_pack(ROOT,c))
    assert r['analysis']['source_screen_pass'] is False and r['analysis']['retention_pass'] is True
    assert len(r['analysis']['per_seed_curve']['learned_cumulative'])==3
    assert saved_replay(ROOT)['cumulative']==r['analysis']


@pytest.mark.parametrize('fault',['fold','train_ids','seed','weight','schedule','query','checkpoint','frozen'])
def test_saved_corruption_is_rejected(fault):
    r=result();c=r['config'];pack=source_pack(ROOT,c);f=r['folds']['0'];info=f['models']['7101']['learned_cumulative']
    if fault=='fold':del r['folds']['0']
    elif fault=='train_ids':f['train_ids'][0]=f['excluded_ids'][0]
    elif fault=='seed':del r['rows']['7101']
    elif fault=='weight':info['weights']['logits.bias'][0]+=1
    elif fault=='schedule':info['training'][0]['task_index']=99
    elif fault=='query':r['rows']['7101']['95000000']['learned_cumulative'][0]['query_mse']+=1
    elif fault=='checkpoint':info['sha256']='0'*64
    else:r['frozen_during_evaluation']=False
    with pytest.raises((ValueError,KeyError)):validate(r,c,pack)


def test_replay_and_checkpoint_reconstruction_use_no_neural_runtime():
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.cumulative_learning import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['cumulative']['fresh_validation'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)


def test_missing_explicit_checkpoints_fail_and_new_restore_is_exact(tmp_path,monkeypatch,capsys):
    # A minimal fresh-clone fixture deliberately has no ignored checkpoint files.
    for name in ('artifacts/seed_cumulative_learning.json','artifacts/seed_nonlinear_learning.json',
                 'configs/seed_cumulative_learning.json','configs/seed_update_diagnosis.json'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    spec=importlib.util.spec_from_file_location('cumulative_verifier',ROOT/'scripts/verify_seed_cumulative_learning.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=tmp_path
    monkeypatch.setattr(sys,'argv',['verify','--check-checkpoints'])
    with pytest.raises(ValueError,match='missing_or_wrong_checkpoint'):m.main()
    restored=tmp_path/'restored';monkeypatch.setattr(sys,'argv',['verify','--restore-checkpoints',str(restored)])
    m.main();assert len(list(restored.glob('*.json')))==24
    for fold in result()['folds'].values():
        for arms in fold['models'].values():
            for info in arms.values():assert (restored/info['checkpoint']).read_bytes()==checkpoint_bytes(info)
    with pytest.raises(FileExistsError):m.main()
