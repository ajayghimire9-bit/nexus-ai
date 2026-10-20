"""Saved evidence checks, with no scientific collector or neural runtime."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.seed import query_replication as qr

ROOT=Path(__file__).resolve().parents[1]
def raw():return json.loads((ROOT/'artifacts/seed_query_replication.json').read_text())


def test_preserved_invalid_receipt_and_separate_complete_arithmetic_validation():
    r=raw();v=json.loads((ROOT/'artifacts/seed_query_replication_validation.json').read_text())
    assert r['declared_complete'] is False and r['host_receipt']['status']=='invalid_integrity'
    assert v['validated_complete'] is True and v['scientific_rerun'] is False
    assert v['raw_sha256']==hashlib.sha256((ROOT/'artifacts/seed_query_replication.json').read_bytes()).hexdigest()
    assert v['parameter_counts']=={'parent_model':30278,'parent_readout':2209}
    assert sum(v['parameter_counts'].values())==r['resources']['parameter_count']
    qr.verify_offline_receipt(ROOT,r,r['config'])


def test_independent_stdlib_arithmetic_verifier_and_no_scientific_imports():
    code='import runpy,sys;p=runpy.run_path(sys.argv[1],run_name="saved_check");r=p["verify"]();assert r["valid"] and r["checked_cached_states"]==900;assert r["max_metric_error"]<2e-6;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_query_replication.py')],check=True,timeout=30)


def test_complete_split_grid_and_query_lock_replay():
    r=raw();c=r['config'];assert qr.validate(r,c,qr.source_pack(ROOT,c))
    all_seeds=[v['seed'] for t in r['queries'].values() for q in t.values() for v in q['records']]
    assert len(all_seeds)==len(set(all_seeds))==288
    assert sum(len(v['outcomes']) for t in r['queries'].values() for q in t.values() for v in q['records'])==2592
    assert sum(len(v['before'])+sum(len(a) for a in v['candidates'].values()) for cells in r['rows'].values() for v in cells.values())==900


def test_changed_validation_or_changed_check_arrays_fail(tmp_path):
    import shutil
    for name in ('configs/seed_query_replication.json','artifacts/seed_query_replication.json','artifacts/seed_query_replication_validation.json','scripts/validate_seed_query_replication.py','src/nexus/seed/query_replication.py'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    r=raw();c=r['config'];path=tmp_path/'artifacts/seed_query_replication_validation.json'
    v=json.loads(path.read_text());v['scientific_rerun']=True;path.write_text(json.dumps(v))
    with pytest.raises(ValueError):qr.verify_offline_receipt(tmp_path,r,c)
    v['scientific_rerun']=False;path.write_text(json.dumps(v))
    path=tmp_path/'artifacts/seed_query_replication.json';data=json.loads(path.read_text());data['queries']['95000000']['check']['arrays']['y'][0]+=1;path.write_text(json.dumps(data))
    with pytest.raises(ValueError):qr.verify_offline_receipt(tmp_path,r,c)


def test_session_budget_debit_no_new_fitting_and_frozen_hashes():
    r=raw();c=r['config'];assert r['execution_debit_s']==5
    assert r['session_used_s']==c['carried_used_s']+5 and r['session_remaining_s']==c['carried_remaining_s']-5
    assert r['resources']['updates']==r['resources']['counterfactual_updates']==r['resources']['normalization_fit_rows']==0
    assert r['frozen_before']==r['frozen_after'] and r['fixed_before_sha256']==r['fixed_after_sha256']
    assert r['analysis']['independent_pretrained_cores']==1 and r['analysis']['learning_to_learn_established'] is False


def test_gui_read_only_replay_exposes_correction_and_exact_analysis():
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.query_replication import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r["status"]=="complete_offline_validation_of_unchanged_capture";assert r["failure"]=="ValueError: query_execution_resource_grid";assert r["query_replication"]==json.load(open(Path(sys.argv[2])/"artifacts/seed_query_replication.json"))["analysis"];assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
