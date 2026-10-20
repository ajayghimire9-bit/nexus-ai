"""Independent read-only arithmetic checks of the saved source audit."""
import hashlib
import json
from pathlib import Path
import statistics as st
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
def result():return json.loads((ROOT/'artifacts/seed_question_headroom.json').read_text())


def test_isolated_standalone_verifier_checks_all_counterfactuals():
    code='import runpy,sys;p=runpy.run_path(sys.argv[1],run_name="saved_audit");r=p["verify"]();assert r["checked_counterfactuals"]==756;assert r["max_prior_choice_error"]==0.;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_question_headroom.py')],check=True,timeout=30)


def test_independent_primary_aggregation_and_interval_use_tasks_not_candidates():
    r=result();c=r['config'];values=[]
    for task in c['tasks']['train']:
        variances=[];oracles=[]
        for b in c['budgets']:
            cell=r['rows'][str(task)][str(b)]
            errors={i:st.mean(arms[str(s)]['query_mse'] for s in c['constant_seeds']) for i,arms in cell['candidates'].items()}
            variances.append(errors[str(cell['variance_index'])]);oracles.append(min(errors.values()))
        values.append(st.mean(variances)-st.mean(oracles))
    mean=st.mean(values);half=2.200985160*st.stdev(values)/12**.5;a=r['analysis']['primary_contrast']
    assert a['paired_task_values']==values
    assert a['mean']==pytest.approx(mean,abs=1e-15) and a['ci95']==pytest.approx([mean-half,mean+half],abs=1e-15)


def test_terminal_singleton_is_same_candidate_and_not_additional_headroom():
    r=result();parent=json.loads((ROOT/r['config']['parent']).read_text())
    for task,cells in r['rows'].items():
        cell=cells['8'];assert len(cell['candidates'])==1
        for seed,row in cell['candidates'][str(cell['variance_index'])].items():
            old=parent['rows'][task]['informative']['fixed'][seed][8]
            assert row['theta']==old['theta'] and row['query_mse']==old['query_mse']
        assert r['analysis']['cells'][task]['8']['oracle_regret']==0.


def test_provenance_resources_ledger_and_immutable_parent():
    r=result();c=r['config'];parent=ROOT/c['parent'];old=json.loads(parent.read_text())
    assert hashlib.sha256(parent.read_bytes()).hexdigest()==c['parent_sha256']
    assert r['config_file_sha256']==hashlib.sha256((ROOT/'configs/seed_question_headroom.json').read_bytes()).hexdigest()
    assert r['host_receipt']['dataset_hashes']['protocol']==hashlib.sha256((ROOT/'docs/NEXUS_SEED_QUESTION_HEADROOM_PROTOCOL.md').read_bytes()).hexdigest()
    assert r['session_used_s']==old['session_used_s']+r['execution_debit_s']
    assert r['session_remaining_s']==old['session_remaining_s']-r['execution_debit_s']
    updates=sum(len(arms) for cells in r['rows'].values() for cell in cells.values() for arms in cell['candidates'].values())
    keeps=sum(len(cell['before']) for cells in r['rows'].values() for cell in cells.values())
    assert updates==r['resources']['counterfactual_updates']==r['resources']['cumulative_solves']
    assert updates+keeps==r['resources']['evaluated_states']
    assert (updates+keeps)*27==r['resources']['query_score_rows']==r['resources']['retention_score_rows']
    assert r['frozen_before_sha256']==r['frozen_after_sha256']==old['frozen_after_sha256']
    assert r['reference_before_sha256']==r['reference_after_sha256']


def test_saved_gui_replay_uses_only_tracked_json_and_stdlib():
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_headroom import saved_replay;r=saved_replay(Path(sys.argv[2]));assert r["question_headroom"]==json.load(open(Path(sys.argv[2])/"artifacts/seed_question_headroom.json"))["analysis"];assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
