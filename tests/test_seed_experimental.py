"""Authored numeric engineering fixtures, never scientific environments."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed.experimental import Sandbox, data_rows, frozen_protocol, read, recipe, validate_output, write_new

ROOT = Path(__file__).resolve().parents[1]


def spec(identifier='trial', mode='exploration'):
    return dict(id=identifier, mode=mode,
        recipe=dict(hidden=[], activation='tanh', optimizer='adam', learning_rate=.05, updates=12, seed=91),
        train='source', development='dev', model_run=None, assessment=None, protocol=None, gate=None)


def dataset(prefix, offset):
    return dict(rows=[dict(id=f'{prefix}-{i}', x=[i*.1+offset], y=2*(i*.1+offset)+1) for i in range(4)])


@pytest.fixture
def host(tmp_path):
    h = Sandbox(ROOT, tmp_path/'host')
    for role, identifier, offset in [('train','source',0),('development','dev',.05),
                                      ('validation','assessment',.025),('confirmation','final',.075)]:
        p=tmp_path/(identifier+'.json');write_new(p,dataset(identifier,offset))
        h.register(identifier,role,p,'engineering test owner','authored numeric fixture, not science')
    h.grant('tiny','engineering test owner','unit-test fixture only',
            dict(wall_s=20,cpu_s=15,memory_mb=2048,real_steps=0,imagined_transitions=0,updates=20),
            session_limit_s=60,carried_used_s=0,memory_policy='sampled_rss')
    return h


@pytest.fixture
def complete(host):
    with host.locked():
        r=host.execute(spec(),'tiny')
    assert r['status']=='complete_development', r
    return host


def assessment(identifier='check', mode='validation'):
    return dict(id=identifier,mode=mode,recipe=None,train=None,development=None,
                model_run='trial',assessment='assessment' if mode=='validation' else 'final',
                protocol=None,gate=dict(minimum_gain=0,maximum_regression=100) if mode=='validation' else None)


def test_real_subprocess_learns_only_source_and_records_actual_curve(complete):
    h=complete;r=h.result('trial');w=r['worker']
    assert len(w['curve'])==12 and w['curve'][-1]['train_mse']<w['curve'][0]['train_mse']
    assert w['resources']['updates']==12 and w['resources']['real_steps']==0
    assert w['resources']['imagined_transitions']==0 and w['resources']['parameter_count']==2
    assert w['resources']['network_forwards']==37 and w['resources']['training_examples']==48
    assert w['resources']['development_examples']==52 and w['resources']['assessment_examples']==0
    inputs=read(h.directory/'attempts/trial/input.json')['inputs']
    assert set(inputs)=={'train','development'} and 'assessment' not in json.dumps(inputs)
    assert r['wall_s']>0 and r['peak_sampled_rss_mb']>0
    assert h.view()['experiments'][0]['model_sha256']==digest(w['model'])
    assert h.used_s()==pytest.approx(r['wall_s'])
    with pytest.raises(ValueError,match='consumed'):h.execute(spec(),'tiny')


def test_independent_gate_retention_rollback_and_one_use_assessment(complete):
    h=complete
    with h.locked():r=h.execute(assessment(),'tiny')
    assert r['status']=='complete_assessment' and r['worker']['resources']['updates']==0
    assert h.retain('check') is True and h.incumbent()=='trial'
    with pytest.raises(ValueError,match='already_decided'):h.retain('check')
    assert h.rollback() is None and h.incumbent() is None
    assert h.result('trial')['status']=='complete_development'
    with pytest.raises(ValueError,match='consumed'):h.execute(assessment('check-again'),'tiny')
    assert h.records('retention_decision')[0]['minimum_gain']==0


def test_validation_threshold_registered_before_result(host):
    a=assessment();a['gate']=None
    # Candidate is missing, and no assessment was consumed by preflight rejection.
    with pytest.raises(FileNotFoundError):host.execute(a,'tiny')
    assert not host.records('reserved')


def test_confirmation_requires_frozen_protocol_before_dispatch(complete):
    before=len(complete.records('reserved'))
    with pytest.raises(ValueError,match='frozen_confirmation_protocol'):
        complete.execute(assessment('final-check','confirmation'),'tiny')
    assert len(complete.records('reserved'))==before


def test_no_role_leakage_even_with_changed_ids(host,tmp_path):
    for change_ids in (False,True):
        d=dataset('source',0)
        if change_ids:
            for r in d['rows']:r['id']='renamed-'+r['id']
        p=tmp_path/('renamed' if change_ids else 'duplicate');write_new(p,d)
        with pytest.raises(ValueError,match='overlap'):host.register('bad','confirmation',p,'owner','fixture')
    with pytest.raises(ValueError,match='role'):host.dataset('final','train')
    s=spec();s['assessment']='final'
    with pytest.raises(ValueError,match='cannot_access'):host.execute(s,'tiny')


def test_tampered_grant_data_result_and_journal_fail(host,complete):
    h=complete
    path=h.directory/'attempts/trial/result.json';prior=read(path);changed=deepcopy(prior)
    changed['worker']['metrics']['mse']=0;path.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='result_integrity'):h.result('trial')
    path.write_text(json.dumps(prior))
    p=h.directory/'grants/tiny.json';g=read(p);g['caps']['wall_s']=999;p.write_text(json.dumps(g))
    with pytest.raises(ValueError,match='grant_hash'):h.execute(spec('other'),'tiny')
    event=sorted((h.directory/'events').glob('*.json'))[0];e=read(event);e['kind']='fake';event.write_text(json.dumps(e))
    with pytest.raises(ValueError,match='tampered'):h.events()


def test_failed_attempt_stays_charged_and_crash_reservation_counts(host):
    host.append('reserved',dict(run_id='interrupted',mode='exploration',dataset_hashes={},wall_cap_s=20))
    assert host.used_s()==20
    with pytest.raises(ValueError,match='reset'):host.grant('reset','owner','not allowed',
        dict(wall_s=1,cpu_s=1,memory_mb=32,real_steps=0,imagined_transitions=0,updates=1),60,1)
    host.append('reserved',dict(run_id='interrupted-two',mode='exploration',dataset_hashes={},wall_cap_s=40))
    with pytest.raises(ValueError,match='session_budget'):host.execute(spec(),'tiny')


def test_gpu_and_unmetered_updates_fail_closed(host):
    host.grant('gpu','owner','recording intent, not backend availability',
        dict(wall_s=1,cpu_s=1,memory_mb=32,real_steps=0,imagined_transitions=0,updates=1),60,0,device='gpu')
    with pytest.raises(ValueError,match='backend_unavailable'):host.execute(spec(),'gpu')
    a=spec();a['recipe']['updates']=21
    with pytest.raises(ValueError,match='update_cap'):host.execute(a,'tiny')
    assert not host.records('reserved')


def test_deadline_failure_logged_and_no_automatic_retry(host):
    # CPU library startup exceeds the deliberately tiny wall allowance.
    host.grant('deadline','owner','kill-path engineering test',
        dict(wall_s=.001,cpu_s=1,memory_mb=2048,real_steps=0,imagined_transitions=0,updates=20),60,0,memory_policy='sampled_rss')
    with host.locked():r=host.execute(spec(),'deadline')
    assert r['status']=='incomplete_execution' and r['failure']=='wall_cap'
    assert host.used_s()>0 and len(host.records('reserved'))==1
    assert host.incumbent() is None


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,'0.1'])
def test_nonfinite_and_nonnumeric_dataset_rejected(bad):
    d=dataset('x',0);d['rows'][0]['y']=bad
    with pytest.raises(ValueError):data_rows(d)


@pytest.mark.parametrize('mutation',['metric','curve','resource','model','nan'])
def test_complete_grid_and_finite_output_rejection(complete,mutation):
    out=deepcopy(complete.result('trial')['worker'])
    if mutation=='metric':del out['metrics']['mse']
    if mutation=='curve':out['curve'].pop()
    if mutation=='resource':out['resources']['updates']=True
    if mutation=='model':out['model']['state']={}
    if mutation=='nan':out['metrics']['mse']=float('nan')
    with pytest.raises(ValueError):validate_output(out,spec(),read(complete.directory/'grants/tiny.json')['caps'])


def test_recipe_rejects_unbounded_structures_or_arbitrary_code():
    for update in ({'hidden':[1024]}, {'optimizer':'exec'}, {'seed':True}, {'updates':0}, {'learning_rate':float('nan')}):
        value=spec()['recipe'];value.update(update)
        with pytest.raises(ValueError):recipe(value)


def test_fixed_seed_reproduces_model_and_queries_cannot_train():
    from nexus.seed.experimental_worker import run
    request=dict(mode='exploration',recipe=spec()['recipe'],inputs=dict(train=dataset('a',0),development=dataset('b',.05)))
    first=run(request)
    request['inputs']['development']['rows'][0]['y']=123
    second=run(request)
    assert first['model']==second['model']
    assert first['curve'][0]['development_mse']!=second['curve'][0]['development_mse']
    assert first['curve'][0]['train_mse']==second['curve'][0]['train_mse']


def test_cli_and_dashboard_read_only_without_neural_import(tmp_path):
    result=subprocess.run([sys.executable,'-I','-S',str(ROOT/'scripts/nexus_experimental.py'),
        '--directory',str(tmp_path/'dashboard'),'status'],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['experiments']==[]
    source=(ROOT/'web/learning-lab/experimental.html').read_text()
    assert "fetch('/api/experimental'" in source and 'textContent' in source and 'innerHTML' not in source
    assert 'method:' not in source and 'approve' in source
    from nexus.seed.cli import main
    main(['--repository',str(ROOT),'experimental','--directory',str(tmp_path/'cli'),'status'])


def test_kernel_memory_requirement_is_never_silently_downgraded(host,monkeypatch):
    host.grant('strict','owner','strict memory requested',
        dict(wall_s=1,cpu_s=1,memory_mb=128,real_steps=0,imagined_transitions=0,updates=20),60,0)
    monkeypatch.setattr(sys,'platform','darwin')
    with pytest.raises(ValueError,match='kernel_memory_enforcement_unavailable'):host.execute(spec(),'strict')
    assert not host.records('reserved')


def test_validation_compares_actual_incumbent_and_cannot_promote_a_tie(complete,tmp_path):
    h=complete
    with h.locked():h.execute(assessment(),'tiny')
    assert h.retain('check')
    path=tmp_path/'independent.json';write_new(path,dataset('second-assessment',.12))
    h.register('second','validation',path,'owner','fresh numeric fixture')
    a=assessment('second-check');a['assessment']='second'
    with h.locked():r=h.execute(a,'tiny')
    assert r['status']=='complete_assessment' and r['baseline_run']=='trial'
    assert r['worker']['metrics']['mse']==r['worker']['metrics']['baseline_mse']
    assert h.retain('second-check') is False and h.incumbent()=='trial'


def test_workspace_fork_uses_new_branch_without_touching_incumbent(tmp_path):
    repo=tmp_path/'repo';repo.mkdir();(repo/'AGENTS.md').write_text('engineering fixture')
    subprocess.run(['git','init','-b','fixture'],cwd=repo,check=True,capture_output=True)
    subprocess.run(['git','add','AGENTS.md'],cwd=repo,check=True)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                    'commit','-m','fixture'],cwd=repo,check=True,capture_output=True)
    h=Sandbox(repo,tmp_path/'workspaces');created=Path(h.fork('candidate'))
    assert (created/'AGENTS.md').read_text()=='engineering fixture'
    assert subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()=='fixture'
    assert subprocess.check_output(['git','branch','--show-current'],cwd=created,text=True).strip()=='codex/experimental-candidate'
    subprocess.run(['git','worktree','remove',str(created)],cwd=repo,check=True)


def test_actual_committed_protocol_binding_and_tamper_rejection(tmp_path):
    repo=tmp_path/'protocol';repo.mkdir()
    subprocess.run(['git','init','-b','fixture'],cwd=repo,check=True,capture_output=True)
    model_hash=digest('model fixture');data_hash=digest('data fixture')
    path=repo/'protocol.json'
    write_new(path,dict(schema='experimental_confirmation_v1',candidate_sha256=model_hash,
                       assessment_sha256=data_hash,primary_metric='mse',success_mse_at_most=.1,
                       independent_unit='authored fixture task, not science'))
    subprocess.run(['git','add','protocol.json'],cwd=repo,check=True)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                    'commit','-m','freeze fixture protocol'],cwd=repo,check=True,capture_output=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    p=dict(commit=commit,path='protocol.json',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
           candidate_sha256=model_hash,assessment_sha256=data_hash)
    assert frozen_protocol(repo,p,model_hash,data_hash)['success_mse_at_most']==.1
    for key in ('candidate_sha256','assessment_sha256','sha256'):
        changed=dict(p);changed[key]='0'*64
        with pytest.raises(ValueError,match='binding'):frozen_protocol(repo,changed,model_hash,data_hash)
    with pytest.raises(ValueError):frozen_protocol(repo,None,model_hash,data_hash)


def test_run_store_cannot_be_historical_artifact_directory():
    with pytest.raises(ValueError,match='historical'):Sandbox(ROOT,ROOT/'artifacts')


def test_conservative_or_external_session_debit_is_additive_not_a_fake_run(host):
    host.debit('carry',1.5,'conservative accounting above actual host charge','fixture receipt')
    assert host.used_s()==1.5 and not host.records('reserved')
    with pytest.raises(ValueError,match='duplicate'):host.debit('carry',1.5,'same','same')
    with pytest.raises(ValueError):host.debit('negative',-1,'cannot refund','fixture')
