"""Synthetic source-only tests; no simulator construction or learned inference."""
import copy
import gzip
import importlib.util
import itertools
import json

import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work
from nexus.evolution2 import full_policy_source as h
from nexus.evolution2 import return_feedback as r
from nexus.evolution2 import feedback_coverage as q


def fixture():
    c=json.loads((h.ROOT/'configs/e3_4_feedback_coverage.json').read_text());rows=[]
    for f,b,e,k in itertools.product(c['families'],c['model_bundles'],c['episodes'],c['controllers']):
        reset,base=h.seeds(c,f,b,e);obs=[float(e)/10+b]*(3 if f=='pendulum' else 6)
        reward=-1. if k=='successor_anchor' else -.5-b
        steps=[dict(tick=t,reward=reward,obs=obs.copy(),next_obs=obs.copy(),action=1,planner_seed=base+t,
                    terminated=False,truncated=t==199) for t in range(200)]
        rows.append(dict(family=f,model_bundle=b,episode=e,controller=k,reset_seed=reset,planner_base=base,
            initial_obs_hash=digest(obs),steps=steps,split='training' if e<9 else 'evaluation',**{'return':reward*200}))
    return c,dict(episodes=rows,resources=dict(completed=Work(real_steps=20800).payload(),unknown_upper=Work().payload()))


@pytest.fixture
def source(monkeypatch):
    from nexus.core.strategy_memory import SupportBatch
    def observations(f,b):return np.arange(24*(3 if f=='pendulum' else 6)).reshape(24,-1)/100.
    def support(f,b,start,n):
        x=np.arange(n*(3 if f=='pendulum' else 6)).reshape(n,-1)/100.+b
        return SupportBatch(x,np.arange(n)%3,x+.01,np.zeros(n))
    monkeypatch.setattr(r,'load_source_train_obs',observations);monkeypatch.setattr(r,'support_from_source',support)


def fit(c,p,persist=False):
    obj=q.CoverageSelectors(c,persist);obj.fit(tuple(x for x in p['episodes'] if x['split']=='training'));return obj


def decide(obj,p,c):
    records=[]
    for i,(f,b,e) in enumerate(itertools.product(c['families'],c['model_bundles'],range(9,13))):
        row=next(x for x in p['episodes'] if (x['family'],x['model_bundle'],x['episode'])==(f,b,e))
        records.append(obj.decide(dict(family=f,model_bundle=b,episode=e,initial_obs=row['steps'][0]['obs'],completed_real_steps=14400+i*400)))
    p['selection_decisions']=records


def test_training_prefix_excludes_all_later_feedback(source):
    c,p=fixture();a=fit(c,p);mutated=copy.deepcopy(p)
    for row in mutated['episodes']:
        if row['episode']>=3 and row['controller']=='rank_blend':
            for step in row['steps']:step['reward']=-4.
            row['return']=-800.
    b=fit(c,mutated)
    assert a.selectors[3].learned_hash()==b.selectors[3].learned_hash()
    assert a.selectors[6].learned_hash()!=b.selectors[6].learned_hash()
    for budget,s in a.selectors.items():
        assert len(s.manifest['training_pairs'])==budget*4
        assert s.manifest['training_real_steps']==budget*1600
        assert all(x['public']['episode']<budget for x in s.manifest['training_pairs'])


def test_evaluation_returns_cannot_change_any_snapshot(source):
    c,p=fixture();a=fit(c,p);mutated=copy.deepcopy(p)
    for row in mutated['episodes']:
        if row['split']=='evaluation':row['return']=-999999.
    b=fit(c,mutated)
    assert [s.learned_hash() for s in a.selectors.values()]==[s.learned_hash() for s in b.selectors.values()]
    decide(a,p,c);decide(b,mutated,c);assert a.selectors[9].records==b.selectors[9].records


def test_manifests_precede_all_shared_preoutcome_choices(source,tmp_path,monkeypatch):
    monkeypatch.setattr(q,'paths',lambda b:(tmp_path/f'm{b}.json',tmp_path/f'p{b}.jsonl'))
    c,p=fixture();a=fit(c,p,True)
    for b in q.BUDGETS:
        assert h.sha(q.paths(b)[0])==a.selectors[b].manifest_sha
        assert not q.paths(b)[1].read_text()
    decide(a,p,c)
    assert all(len(q.paths(b)[1].read_text().splitlines())==16 for b in q.BUDGETS)
    assert sum(m.fit_calls for s in a.selectors.values() for m in s.predictors.values())==6
    before=[s.learned_hash() for s in a.selectors.values()]
    q.analyze(p,c);assert before==[s.learned_hash() for s in a.selectors.values()]
    with pytest.raises(RuntimeError):a.fit([])


def test_deterministic_reproduction_and_restore(source):
    c,p=fixture();a=fit(c,p);b=fit(c,p);decide(a,p,c)
    other=copy.deepcopy(p);decide(b,other,c)
    assert p['selection_decisions']==other['selection_decisions']
    for budget in q.BUDGETS:
        restored=r.FrozenReturnSelector.restore(c,a.selectors[budget].manifest)
        for row in a.selectors[budget].records:
            public={k:row[k] for k in ('family','model_bundle','episode','initial_obs','completed_real_steps')}
            assert restored.decide(public)==row


def test_aggregation_and_shared_return_table(source):
    c,p=fixture();obj=fit(c,p);decide(obj,p,c);a=q.analyze(p,c)
    assert a['primary_budget']==9 and not a['primary_point_screen']
    for family in c['families']:
        expected=a['by_budget']['9']['by_family'][family]['mean_returns']['quality_predictor']-a['by_budget']['3']['by_family'][family]['mean_returns']['quality_predictor']
        assert a['coverage_effect'][family]['predictor_return_9_minus_3']==expected
        assert a['by_budget']['9']['by_family'][family]['mean_returns']['model_mean']==-150.
    assert a['independent_models_per_family']==2


@pytest.mark.parametrize('bad',['budget','method','model','episode','count','nan','outer'])
def test_missing_or_invalid_grid_fails(source,bad):
    c,p=fixture();obj=fit(c,p);decide(obj,p,c)
    if bad=='budget':p['selection_decisions'][0]['budgets'].pop('6')
    if bad=='method':p['selection_decisions'][0]['budgets']['9']['choices'].pop('uniform')
    if bad=='model':p['episodes']=[row for row in p['episodes'] if row['model_bundle']!=1]
    if bad=='episode':p['episodes'].pop()
    if bad=='count':p['selection_decisions'][0]['budgets']['9']['completed_real_steps']=0
    if bad=='nan':p['selection_decisions'][0]['budgets']['9']['estimates']['model_mean']=float('nan')
    if bad=='outer':p['selection_decisions'][0]['episode']=0
    with pytest.raises(ValueError):q.analyze(p,c)


def test_locked_profile_prefix_and_seed_uniqueness():
    c,_=fixture();assert len(h.requested_seeds(c))==10452
    for name in ('unified_full_policy_source.json','unified_full_policy_replication.json','unified_crossed_reset.json','e3_2_return_feedback.json'):
        old=json.loads((h.ROOT/'configs'/name).read_text());assert not h.requested_seeds(c)&h.requested_seeds(old)
    jobs=h.model_jobs(c,[0,1,2,3]);assert [x[1] for x in jobs]==['training']*4+['evaluation']*4
    assert tuple(jobs[0][2])==tuple(range(9)) and tuple(jobs[-1][2])==(9,10,11,12)
    with pytest.raises(ValueError):h.run(c)
    c['episodes'].pop()
    with pytest.raises(ValueError):h.validate_config(c)


def test_lossless_ordered_journal_rotation_and_missing_tamper_fail(tmp_path):
    path=tmp_path/'journal.jsonl.gz';records=[json.dumps(dict(i=i)).encode()+b'\n' for i in range(7)]
    with h.DecisionJournal(path,3) as out:
        for row in records:out.write(row)
    assert len(out.paths)==3
    assert [sum(1 for _ in gzip.open(p,'rt')) for p in out.paths]==[3,3,1]
    assert b''.join(gzip.open(p,'rb').read() for p in out.paths)==b''.join(records)
    digests=[h.sha(p) for p in out.paths]
    out.paths[1].write_bytes(b'changed')
    with pytest.raises(ValueError):h.verify_file(out.paths[1],digests[1])
    out.paths[0].unlink()
    with pytest.raises(FileNotFoundError):h.verify_file(out.paths[0],digests[0])


def test_same_planning_work_at_all_budgets():
    from nexus.evolution2.planner_adapter import FakeStepModel
    from nexus.evolution1.catalogue import plan_bound
    c,_=fixture()
    for family,size in (('pendulum',3),('acrobot',6)):
        for name in c['controllers']:
            calls=[]
            class Counted(FakeStepModel):
                def step(self,o,a):
                    calls.append(h.model_work(np.asarray(o).reshape(-1,size).shape,np.asarray(a).size))
                    return super().step(o,a)
            strategy=h.controllers()[name];h.execute(strategy,family,np.ones(size),Counted(size,3),seed=4)
            counts={v.rule.name:plan_bound(v,3,cap).candidates_per_root for v,cap in strategy.components(np.ones(size))}
            assert counts==({'SUCCESSOR':31} if name=='successor_anchor' else {'FLAT':48,'SUCCESSOR':15})
            assert calls==[op.cost for op in h.operation_plan(strategy,np.ones(size),3)[:-1]]
            assert sum(w.imagined_transitions for w in calls)==1491
            assert len(calls)==(51 if name=='successor_anchor' else 67)


@pytest.mark.parametrize('bad',['missing','duplicate','order','hash'])
def test_full_verifier_rejects_invalid_part_grid_before_checkpoint_access(tmp_path,monkeypatch,bad):
    spec=importlib.util.spec_from_file_location('coverage_journal_verifier',h.ROOT/'scripts/verify_unified_full_policy_source.py')
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    c,p=fixture();p.update(config=c,declared_complete=True,code_sha256={},historical_artifacts_sha256={})
    monkeypatch.setattr(h,'ROOT',tmp_path)
    base=h.run_paths(c)['journal'];base.parent.mkdir()
    parts=[]
    for i in range(6):
        path=base.with_name(base.name.replace('.jsonl.gz',f'.part{i:02}.jsonl.gz'));path.write_bytes(b'fixture')
        parts.append(dict(path=str(path.relative_to(tmp_path)),sha256=h.sha(path)))
    if bad=='missing':parts.pop()
    if bad=='duplicate':parts[-1]=parts[0]
    if bad=='order':parts.reverse()
    if bad=='hash':parts[0]['sha256']='0'*64
    p['resource_journal_parts']=parts
    with pytest.raises(ValueError,match='file_hash_mismatch' if bad=='hash' else 'journal_part_grid'):verifier.verify(p)


def test_full_prefix_coefficient_replay_uses_no_fitting(source,tmp_path,monkeypatch):
    c,p=fixture();monkeypatch.setattr(h,'ROOT',tmp_path);(tmp_path/'artifacts').mkdir()
    obj=fit(c,p,True);decide(obj,p,c);p['predictor_files']=obj.files()
    def forbidden(*args,**kwargs):raise AssertionError('no_refitting')
    monkeypatch.setattr(r.AdvantagePredictor,'observe',forbidden)
    assert q.verify_selectors(p,c)==q.analyze(p,c)
