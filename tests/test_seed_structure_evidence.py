"""Tracked-result checks only; no fit, inference, private binary or collection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_saved_arithmetic_and_provenance_are_reproducible_without_optional_packages():
    output=subprocess.check_output([sys.executable,'-I','-S',str(ROOT/'scripts/verify_seed_executable_world.py')],text=True,cwd=ROOT)
    result=json.loads(output)
    assert result['valid'] and result['predictions_checked']==7680
    assert result['artifact_sha256']=='f18adb4df4ba929e4e7f2d262d001420afa3925021328e8bd785031814138115'
    assert result['authored_observations']==22925 and not result['scientific_execution']
    record=json.loads((ROOT/'artifacts/seed_executable_world.json').read_text())
    assert record['execution_sha']=='bc57da126051d0aa5d148fcbf05bb4704f2571e1'
    audit=json.loads((ROOT/'artifacts/seed_executable_world_audit.json').read_text())
    assert audit['execution_tree_clean'] is True
    assert audit['execution_sha']==record['execution_sha']
    for p,sha in audit['source_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha
    assert record['frozen_before_final'] is True


def test_history_weights_remain_exact_and_gui_replay_is_data_only():
    expected={'artifacts/seed_contract_gui.json':'cfe06a6737c8e225564ebcaea9ba4678aabd45b61129828e64354e74fa3c8d1b',
              'artifacts/seed_readout_6301.json':'8129cbd4768f4cd5dce938cd8b6740172bf5dbe8742dcb97c497951ad5e87745'}
    for path,sha in expected.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    from nexus.seed.structure.study import saved_replay
    result=saved_replay(ROOT)
    assert result['mode']=='exploration' and result['resources']['real_steps']==22925
    # A repository-only replay cannot silently import optional neural packages.
    code=f"import sys;sys.path.insert(0,{str(ROOT/'src')!r});from nexus.seed.structure.study import saved_replay;saved_replay({str(ROOT)!r});assert 'torch' not in sys.modules;assert 'numpy' not in sys.modules"
    subprocess.run([sys.executable,'-I','-S','-c',code],check=True,cwd=ROOT)
