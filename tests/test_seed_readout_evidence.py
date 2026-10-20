"""Repository-only evidence checks; no neural/environment imports."""
import copy
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]


def verifier():
    spec=importlib.util.spec_from_file_location('readout_verify',ROOT/'scripts/verify_seed_surprise_readout.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_saved_outcomes_reproduce_locked_arithmetic_without_neural_execution():
    import sys
    r=verifier().verify()
    assert r['verified_ranking_cells']==256 and r['authored_steps']==4773
    assert r['analysis']['screen_passed'] and r['analysis']['paired_returns']['greedy']['ci95'][1]<0
    assert r['meta_contrasts']['historical_best']['mean']==0


def test_saved_declared_success_does_not_replace_metric_validation():
    import json
    from nexus.seed.readout_validation import validate
    r=json.loads((ROOT/'artifacts/seed_surprise_readout.json').read_text());c=json.loads((ROOT/'configs/seed_surprise_readout.json').read_text())
    r['audit'][0]['metrics']['frozen']['regret']=float('inf')
    with pytest.raises(ValueError):validate(r,c)
