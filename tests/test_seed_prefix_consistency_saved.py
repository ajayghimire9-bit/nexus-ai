"""Recorded-source audit regression; no models fitted or scientific data collected."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nexus.seed.prefix_consistency import source_pack,validate,saved_replay

ROOT=Path(__file__).resolve().parents[1]


def result():return json.loads((ROOT/'artifacts/seed_prefix_consistency.json').read_text())


def test_saved_source_audit_failed_without_relabeling_secondary_signal():
    r=result();assert r['declared_complete'] is True and validate(r,r['config'],source_pack(ROOT,r['config']))
    a=r['analysis'];assert a['signal_screen_pass'] is False and a['fold_wins']==2
    assert a['metrics']['consistency']['regret']<a['metrics']['constant']['regret']
    assert a['metrics']['full']['mse']>a['metrics']['constant']['mse']
    assert saved_replay(ROOT)['prefix_consistency']==a


@pytest.mark.parametrize('fault',['fold','task','prefix','method','metric','coefficient','hash','boolean'])
def test_actual_saved_grid_or_arithmetic_corruption_fails(fault):
    r=result();f=r['folds']['0'];row=f['cases']['95000000'][0]
    if fault=='fold':del r['folds']['0']
    elif fault=='task':del f['cases']['95000000']
    elif fault=='prefix':f['cases']['95000000'].pop()
    elif fault=='method':del row['predictions']['full']
    elif fault=='metric':del row['query_before']
    elif fault=='coefficient':f['models']['full']['beta'][0]+=.1
    elif fault=='hash':f['models_sha256']='0'*64
    else:row['utility']=False
    with pytest.raises((ValueError,KeyError)):validate(r,r['config'],source_pack(ROOT,r['config']))


def test_stdlib_replay_imports_no_neural_or_numeric_runtime():
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.prefix_consistency import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['prefix_consistency']['fresh_validation'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)


def test_fresh_clone_verification_needs_no_local_binary_or_fit(tmp_path,capsys):
    for name in ('artifacts/seed_prefix_consistency.json','artifacts/seed_nonlinear_learning.json',
                 'configs/seed_prefix_consistency.json','configs/seed_update_diagnosis.json'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    spec=importlib.util.spec_from_file_location('prefix_verifier',ROOT/'scripts/verify_seed_prefix_consistency.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=tmp_path
    module.main();assert json.loads(capsys.readouterr().out)['valid'] is True
    p=tmp_path/'artifacts/seed_prefix_consistency.json';r=json.loads(p.read_text());r['declared_complete']=False;p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='incomplete'):module.main()
