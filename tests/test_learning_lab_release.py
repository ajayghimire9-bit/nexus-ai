"""Local packaging/recorded evidence only; no scientific simulators or weights."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest
from nexus.evolution2.learning_lab import load_operator_replay,load_preparation

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/f'scripts/{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_D_replay_displays_only_recorded_choices_and_failures():
    result=load_operator_replay(ROOT,parent_retention=True)
    assert result['study']=='E3.12D' and result['live'] is False
    assert len(result['training'])==32 and len(result['cases'])==16
    assert all(len(r['returns'])==2 for r in result['training'])
    assert all(r['decision']['parent_inclusive']['choice']!='parent' for r in result['cases'])
    assert any(c['harmful_change'] for c in result['cases'])
    p=load_preparation(ROOT)
    assert p['execution_authorized'] is False and p['caps']['model_call_cap']==1622400


def test_release_is_deterministic_allowlisted_and_no_weight_or_untracked_work(tmp_path):
    builder=load('package_learning_lab');first=tmp_path/'one.zip';second=tmp_path/'two.zip'
    a=builder.build(first);b=builder.build(second)
    assert a['sha256']==b['sha256'] and first.read_bytes()==second.read_bytes()
    with pytest.raises(FileExistsError):builder.build(first)
    with zipfile.ZipFile(first) as z:
        names=z.namelist()
        assert 'DEMO_MANIFEST.json' in names and 'offline.html' in names and 'scripts/run_learning_lab_session.py' in names
        assert 'src/nexus/evolution1/adapters.py' not in names
        assert not any(n.endswith(('.pt','.npz','.pth')) or '/.git/' in n or n.endswith('/.env') for n in names)
        assert 'scripts/run_e3_12_mutation_control.py' not in names
        z.extractall(tmp_path/'demo')
    verifier=load('verify_demo');assert verifier.verify(tmp_path/'demo')['valid'] is True
    (tmp_path/'demo/web/learning-lab/index.html').write_text('changed')
    with pytest.raises(ValueError,match='hash'):verifier.verify(tmp_path/'demo')


def test_clean_venv_acceptance_without_site_packages_or_installs(tmp_path):
    archive=tmp_path/'demo.zip';load('package_learning_lab').build(archive)
    result=load('check_learning_lab_release').check(archive)
    assert result['clean_stdlib_replay_passed'] and result['recorded_D_E_present'] and result['F_unexecuted']
    assert result['dependency_downloads']==result['new_scientific_environment_steps']==result['model_inference']==0
    assert result['fixture_restart_tested'] is False
