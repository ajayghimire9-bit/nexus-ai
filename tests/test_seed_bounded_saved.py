"""Saved comparison integrity only; no new update executions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.seed.bounded_correction import source_pack,validate,saved_replay

ROOT=Path(__file__).resolve().parents[1]


def result():return json.loads((ROOT/'artifacts/seed_bounded_correction.json').read_text())


def test_saved_source_decisions_are_separate_and_raw_bytes_preserved():
    r=result();c=r['config'];assert validate(r,c,source_pack(ROOT,c))
    assert r['analysis']['stabilization_pass'] is True
    assert r['analysis']['beats_replay'] is False
    assert r['analysis']['learned_specific_pass'] is False
    assert r['analysis']['advance_source_screen'] is False
    assert hashlib.sha256((ROOT/'artifacts/seed_bounded_correction.json').read_bytes()).hexdigest()=='28209e17eb34ab72c188f42504aa606227c0291c98e13a8d7b11b3a7bd3bc009'


@pytest.mark.parametrize('fault',['cached','theta','alpha','rms','task','decision'])
def test_saved_corruption_rejection(fault):
    r=result();c=r['config'];pack=source_pack(ROOT,c);cell=r['rows']['6401']['95000000']
    if fault=='cached':cell['replay'][0]['theta'][0]+=1
    elif fault=='theta':cell['learned_bounded'][1]['theta'][0]+=1
    elif fault=='alpha':r['limit_trace']['6401']['95000000']['learned_bounded'][0]['alpha']=True
    elif fault=='rms':r['limit_trace']['6401']['95000000']['learned_bounded'][0]['actual_rms']+=1
    elif fault=='task':del r['rows']['6401']['95000000']
    else:r['analysis']['beats_replay']=True
    with pytest.raises(ValueError):validate(r,c,pack)


def test_browser_replay_needs_no_models_or_neural_imports():
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.bounded_correction import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r['bounded']['runtime_promotion'] is False;assert not any(k in sys.modules for k in ('torch','numpy','gymnasium','nexus.seed.grounded_world'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True)
