"""Recorded evidence only; no fitting or scientific execution."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.seed.update_diagnosis import source_pack,validate,saved_replay

ROOT=Path(__file__).resolve().parents[1]


def result():
    return json.loads((ROOT/'artifacts/seed_update_diagnosis.json').read_text())


def test_saved_complete_source_arithmetic_and_negative_label():
    r=result();assert validate(r,r['config'],source_pack(ROOT,r['config']))
    assert r['analysis']['label']=='pattern_not_supported'
    assert r['analysis']['harmed_source_tasks']==5
    card=saved_replay(ROOT)
    assert card['mode']=='recorded_source_only_diagnosis'
    assert card['diagnosis']==r['analysis']
    assert r['resources']['real_steps']==r['resources']['imagined_transitions']==0


@pytest.mark.parametrize('fault',['seed','task','method','prefix','prediction','update','weight'])
def test_saved_rows_and_parameter_integrity_reject_corruption(fault):
    r=result();c=r['config'];pack=source_pack(ROOT,c);task=r['rows']['6401']['95000000']
    if fault=='seed':del r['rows']['6401']
    elif fault=='task':del r['rows']['6401']['95000000']
    elif fault=='method':del task['learned']
    elif fault=='prefix':task['learned'].pop()
    elif fault=='prediction':task['learned'][0]['query_mse']+=1
    elif fault=='update':task['learned'][0]['theta'][0]+=1
    else:pack['controllers'][0]['arms']['learned']['logits.bias'][0]+=1
    with pytest.raises(ValueError):validate(r,c,pack)


def test_gui_replay_is_stdlib_only_without_loading_models():
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.update_diagnosis import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['diagnosis']['generalization_test'] is False;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)
