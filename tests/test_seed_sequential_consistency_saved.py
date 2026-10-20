"""Saved sequential evidence, original baseline replay and immutable provenance."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nexus.seed import sequential_consistency as seq

ROOT=Path(__file__).resolve().parents[1]


def result():return json.loads((ROOT/'artifacts/seed_sequential_consistency.json').read_text())


def test_actual_complete_failed_screen_and_unchanged_parents():
    r=result();assert r['declared_complete'] is True and seq.validate(r,r['config'],seq.source_pack(ROOT,r['config']))
    assert r['analysis']['source_screen_pass'] is False and r['analysis']['retention_pass'] is True
    assert r['analysis']['teaching_updates']['consistency_selector']==11
    assert seq.saved_replay(ROOT)['sequential_consistency']==r['analysis']


def test_all_recomputed_baseline_states_and_scores_reproduce_parent_exactly():
    r=result();old=json.loads((ROOT/'artifacts/seed_update_gate.json').read_text());count=0
    for t,cell in r['rows'].items():
        for m,parent in [('constant_damping','constant_gate'),('replay','replay'),('bounded_fixed','fixed_bounded'),('unit_cumulative','fixed_cumulative'),('none','none')]:
            for rep,trace in cell[m].items():
                seed=rep if m=='constant_damping' else '7201';expected=old['rows'][seed][t][parent]
                for a,b in zip(trace,expected):
                    assert a['theta']==b['theta'] and a['query_mse']==b['query_mse'] and a['retention_mse']==b['retention_mse']
                count+=1
    assert count==84


def test_first_decisions_reproduce_reference_but_later_trajectories_differ():
    r=result();parent=json.loads((ROOT/'artifacts/seed_prefix_consistency.json').read_text());changes=0
    for fold in parent['folds'].values():
        for t in fold['excluded_ids']:
            new=r['rows'][str(t)]['consistency_selector']['frozen'][1:];old=fold['cases'][str(t)]
            assert new[0]['predicted_utility']==old[0]['predictions']['consistency']
            changes+=sum((a['gate']>0)!=(b['predictions']['consistency']>0) for a,b in zip(new,old))
    assert changes==42


@pytest.mark.parametrize('fault',['task','method','replica','metric','feature','prediction','frozen'])
def test_actual_saved_corruptions_fail(fault):
    r=result();cell=r['rows']['95000000'];row=cell['consistency_selector']['frozen'][1]
    if fault=='task':del r['rows']['95000000']
    elif fault=='method':del cell['replay']
    elif fault=='replica':del cell['constant_damping']['7201']
    elif fault=='metric':del row['retention_mse']
    elif fault=='feature':row['features'][4]+=.1
    elif fault=='prediction':row['predicted_utility']=float('inf')
    else:r['frozen_after_sha256']='0'*64
    with pytest.raises((ValueError,KeyError)):seq.validate(r,r['config'],seq.source_pack(ROOT,r['config']))


def test_stdlib_replay_no_neural_runtime():
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.sequential_consistency import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['sequential_consistency']['fresh_validation'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)


def test_fresh_clone_works_without_private_files_and_missing_parent_fails(tmp_path,capsys):
    for name in ('artifacts/seed_sequential_consistency.json','configs/seed_sequential_consistency.json',
                 'artifacts/seed_prefix_consistency.json','artifacts/seed_update_gate.json',
                 'configs/seed_update_diagnosis.json','artifacts/seed_nonlinear_learning.json'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    spec=importlib.util.spec_from_file_location('seq_verifier',ROOT/'scripts/verify_seed_sequential_consistency.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=tmp_path
    module.main();assert json.loads(capsys.readouterr().out)['valid'] is True
    (tmp_path/'artifacts/seed_update_gate.json').unlink()
    with pytest.raises(FileNotFoundError):module.main()
