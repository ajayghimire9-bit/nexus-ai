"""Saved fresh evidence only; no model inference or training."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from nexus.seed.learning_validation_audit import validate,interval
ROOT=Path(__file__).resolve().parents[1]


def test_fresh_capture_complete_and_both_gates_failed():
    r=json.loads((ROOT/'artifacts/seed_learning_validation.json').read_text())
    c=json.loads((ROOT/'configs/seed_learning_validation.json').read_text())
    assert validate(r,c) and not r['screens']['learning']['passed'] and not r['screens']['actions']['passed']
    assert r['transfer']['status']=='not_run_object_success_gate_failed'


@pytest.mark.parametrize('fault',['controller','task','method','budget','state','nan','boolean','control','meaning','instruction','selection','transfer'])
def test_missing_or_invalid_cells_rejected_from_registered_config(fault):
    r=json.loads((ROOT/'artifacts/seed_learning_validation.json').read_text());c=copy.deepcopy(r['config'])
    if fault=='controller':r['controllers'].pop()
    elif fault=='task':r['tasks']['audit'].pop()
    elif fault=='method':r['controllers'][0]['curves']['audit'][0]['methods'].pop('replay')
    elif fault=='budget':r['controllers'][0]['curves']['audit'][0]['methods']['learned'].pop()
    elif fault=='state':r['controllers'][0]['curves']['audit'][0]['methods']['learned'][0]['ranking'].pop()
    elif fault in ('nan','boolean'):r['controllers'][0]['curves']['audit'][0]['methods']['learned'][0]['query_mse']=float('nan') if fault=='nan' else True
    elif fault=='control':r['control'][str(c['task_seeds']['audit'][0])].pop('grid')
    elif fault=='meaning':r['meaning'][0]['tasks'].pop()
    elif fault=='instruction':r['meaning'][0]['instructions']['rows'].pop()
    elif fault=='selection':r['selection'][0]['policies']['adaptive'].pop()
    else:r['transfer']['status']='executed_after_object_success'
    with pytest.raises(ValueError):validate(r,c)


def test_intervals_have_task_stream_units_not_controller_pseudoreplication():
    assert interval([2.]*8)['ci95']==[2.,2.]
    with pytest.raises(ValueError):interval([2.]*24)
