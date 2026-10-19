"""Local replay and authored sessions only, never scientific environments."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.request import urlopen
import pytest
from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost
from nexus.evolution2.cycle_checkpoint import load_cycle,encode

ROOT=Path(__file__).resolve().parents[1]


def cli():
    spec=importlib.util.spec_from_file_location('fixture_session',ROOT/'scripts/run_learning_lab_session.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('method',['unified','reset_memory'])
def test_durable_session_restores_host_costs_and_exact_learning_after_process_restart(tmp_path,method):
    folder=tmp_path/'saved';first=cli().run(folder,new=True,seed=7,method=method)
    script=ROOT/'scripts/run_learning_lab_session.py'
    done=subprocess.run([sys.executable,str(script),'--directory',str(folder),'--expected-head',first['head']],cwd=ROOT,env=os.environ,text=True,capture_output=True,timeout=15)
    assert done.returncode==0,done.stderr
    last=json.loads(done.stdout);assert last['task_cursor']==4 and last['host_calls']>=first['host_calls']
    restored=load_cycle(folder/last['checkpoint'],expected_sha256=last['checkpoint_sha256'],provenance=last['provenance'])
    full=LearningCycle(7,method,objective='training_incumbent_progress_v1');host=FixtureHost(7,max_calls=256)
    for task in ('A','B','A','C'):
        full.begin_task(task)
        for _ in range(2):
            if full.step(host,task) is None:break
    assert encode(full)==encode(restored) and last['host_calls']==host.calls
    assert last['scientific'] is False and last['new_environment_interactions']==last['model_inference']==0
    assert last['charged_training_units']==full.charged.cpu_units
    with pytest.raises(ValueError,match='already_complete'):cli().run(folder)


@pytest.mark.parametrize('fault',['head','file','method','lock'])
def test_resume_rejects_changed_or_concurrent_state(tmp_path,fault):
    folder=tmp_path/'session';first=cli().run(folder,new=True,seed=7)
    kwargs={}
    if fault=='head':kwargs['expected_head']='0'*64
    elif fault=='file':(folder/first['checkpoint']).write_text('{}')
    elif fault=='method':kwargs['method']='reset_memory'
    elif fault=='lock':(folder/'.active').mkdir()
    with pytest.raises((ValueError,FileExistsError)):cli().run(folder,**kwargs)
    assert len(list(folder.glob('revision-*.json')))==1


def test_minimal_replay_launch_works_with_isolated_stdlib_only_python():
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    child=subprocess.Popen([sys.executable,'-I','-S',str(ROOT/'scripts/nexus_lab.py'),'--port',str(port),'--max-runtime-s','15'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert 'NEXUS Learning Lab:' in child.stdout.readline()
        for endpoint in ('/api/status','/api/training-audit'):
            with urlopen(f'http://127.0.0.1:{port}'+endpoint,timeout=3.) as r:payload=json.load(r)
            if endpoint=='/api/status':assert payload['live_environment'] is False and payload['fixtures_enabled'] is False
            else:assert payload['live'] is False and payload['query_outcomes_used']==0
    finally:
        child.terminate();child.communicate(timeout=3.)


def test_followup_resource_arithmetic_is_not_execution_permission():
    c=json.loads((ROOT/'configs/measured_learning_followups.json').read_text());assert c['execution_authorized'] is False and c['allocation'] is None and c['numerical_task_seeds'] is None
    p=c['continual'];assert p['model_units']*(len(p['stream'])*(p['training_resets_per_block']*p['training_paths_per_reset']+p['query_resets_per_block']*p['query_paths_per_reset'])+p['retention_A_probe_resets']*3)*p['steps_per_path']==p['proposed_real_steps']==49600
    p=c['learning_rules'];assert p['model_units']*(p['source_blocks']+p['development_blocks']+p['untouched_blocks'])*(p['training_resets_per_block']*p['training_paths_per_reset']+p['query_resets_per_block']*p['query_paths_per_reset'])*p['steps_per_path']==p['proposed_real_steps']==67200
    for name in ('continual','learning_rules'):assert c[name]['proposed_time_cap_s']<=900 and c[name]['proposed_real_steps']<=100000
    assert c['transfer']['new_checkpoint_training_authorized'] is False


def test_orphaned_snapshot_blocks_before_any_additional_fixture_evaluation(tmp_path,monkeypatch):
    folder=tmp_path/'session';cli().run(folder,new=True)
    (folder/'cycle-0001.json').write_text('orphaned interrupted write')
    monkeypatch.setattr(FixtureHost,'evaluate',lambda *args:(_ for _ in ()).throw(AssertionError('no_repeat_evaluation')))
    with pytest.raises(ValueError,match='orphaned_snapshot'):cli().run(folder)
