"""Saved negative evidence only: no scientific collection or new candidates."""
import importlib.util
import json
from pathlib import Path
import pytest
from nexus.seed import conditioned_acquisition as q

ROOT=Path(__file__).resolve().parents[1]


def test_saved_complete_arithmetic_and_resource_accounting():
    r=json.loads((ROOT/'artifacts/seed_conditioned_acquisition.json').read_text())
    q.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=2500))
    assert r['execution_sha']=='609c4d46654826a539494a6a201338bf73bc0e09'
    assert r['session_used_s']==2005.6321034559958 and r['execution_debit_s']==6
    assert r['analysis']['transfer_screen']==r['analysis']['strong_advantage_screen']=='failed'
    assert r['analysis']['repetition_wins']['blind']==0


def test_independent_negative_evidence_and_readonly_view():
    spec=importlib.util.spec_from_file_location('conditioned_saved_verifier',ROOT/'scripts/verify_seed_conditioned_acquisition.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.verify(ROOT)==json.loads((ROOT/'artifacts/seed_conditioned_acquisition_audit.json').read_text())
    assert q.saved_replay(ROOT)['conditioned_acquisition']['promoted'] is False


def test_expected_grid_is_not_inferred_from_produced_tasks():
    r=json.loads((ROOT/'artifacts/seed_conditioned_acquisition.json').read_text())
    r['blocks'].pop()
    with pytest.raises(ValueError,match='complete_repetition_grid'):q.validate_grid(r,q.configuration())
