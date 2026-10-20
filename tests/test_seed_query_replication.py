"""Synthetic source-contract tests; never runs the scientific collector."""
from copy import deepcopy
import json
from pathlib import Path
import statistics as st
import subprocess
import sys
import pytest
import torch
from nexus.evolution1.catalogue import digest
from nexus.seed import query_replication as qr
from test_seed_question_headroom import headroom_pack,headroom_result
from test_seed_question_selection import question_pack,question_result
from test_seed_sequential_consistency import synthetic_pack

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_query_replication.json').read_text())


def analytic_query(seeds,offset):
    """Arithmetic fixture, not a simulator/agent call."""
    records=[];xs=[];ys=[]
    for j,seed in enumerate(seeds):
        k=offset+j;pos=k%35;obj=dict(id='o1',x=pos%6,y=pos//6,color=('red','blue','green')[(k//35)%3],shape=('circle','square','triangle')[(k//105)%3],size='small')
        outcomes=[]
        for a in range(9):
            after=dict(obj)
            for dx,dy in {0:[(-1,0)],1:[(1,0)],2:[(0,-1)],3:[(0,1)],7:[(1,0),(0,1)],8:[(-1,0),(0,-1)]}.get(a,[]):
                if 0<=after['x']+dx<6 and 0<=after['y']+dy<6:after['x']+=dx;after['y']+=dy
            dist=lambda o:abs(o['x']-5)+abs(o['y']-5)
            reward=.2*(dist(obj)-dist(after))-.02+int(dist(after)==0)
            outcomes.append(dict(action=a,reward=reward,done=dist(after)==0,truncated=False,after=after,next_proprio=[0.]*12))
            xs.append([.01*(1+(k+a+i)%9) for i in range(33)]);ys.append(float(torch.tensor(reward)))
        records.append(dict(seed=seed,before=obj,goal=[5,5],base=[0.]*9,proprio=[0.]*12,outcomes=outcomes))
    arrays=dict(x=xs,y=ys)
    return dict(records=records,arrays=arrays,record_sha256=digest(records),array_sha256=digest(arrays),dtype='float32',shapes={'x':[108,33],'y':[108]})


@pytest.fixture(scope='module')
def replication(headroom_result,headroom_pack):
    c=config();pack=dict(rows=headroom_result['study']['rows'],parent_sha256=c['parent_sha256'],
        frozen_folds=headroom_pack['questions']['source']['frozen_folds'],goals={str(t):[5,5] for t in c['tasks']['train']},
        history_sha256='test',closed_initials=[])
    r=dict(config=c,source_pack_sha256=digest(pack),fixed_before_sha256=digest(pack),fixed_after_sha256=digest(pack),
        frozen_before=dict(core=c['parent_model_sha256'],readout=c['parent_readout_sha256'],state='test'),
        queries={str(t):{} for t in c['tasks']['train']},rows={str(t):{} for t in c['tasks']['train']},closed_initials=[],
        costs=dict(collection=2592,control=0),imagined_transitions=2592,posterior_rows=288)
    scales={str(t):f['scale'] for f in pack['frozen_folds'].values() for t in f['excluded_ids']}
    for role in qr.ROLES:
        if role=='check':r['selection_manifest']=qr.selection_manifest(r['rows'],r['queries'],c,pack)
        for i,t in enumerate(c['tasks']['train']):
            tid=str(t);q=analytic_query(c['query_seeds'][tid][role],i*24+(12 if role=='check' else 0));r['queries'][tid][role]=q
            for b in c['budgets']:
                r['rows'][tid][str(b)]=qr.score_snapshots(pack['rows'][tid][str(b)],q,scales[tid],role,r['rows'][tid].get(str(b)))
    r.update(frozen_after=deepcopy(r['frozen_before']),selection_manifest_sha256=digest(r['selection_manifest']),selection_locked_before_check=True)
    r['analysis']=qr.summarize(r['rows'],r['selection_manifest']['choices'],c,pack)
    assert qr.validate(r,c,pack);return r,pack


def test_complete_toy_grid_and_task_cluster_interval(replication):
    r,p=replication;a=r['analysis'];values=[v['variance']-v['selected'] for v in a['per_task'].values()]
    assert len(values)==12 and a['contrasts']['variance']['mean']==st.mean(values)
    half=2.200985160*st.stdev(values)/12**.5
    assert a['contrasts']['variance']['ci95']==pytest.approx([st.mean(values)-half,st.mean(values)+half],abs=1e-15)
    assert a['independent_pretrained_cores']==1 and a['learning_to_learn_established'] is False
    for cells in a['cells'].values():assert cells['8']['check']['selected']==cells['8']['check']['variance']


def selection_only(rows):
    r=deepcopy(rows)
    for cells in r.values():
        for cell in cells.values():
            for arms in [cell['before']]+list(cell['candidates'].values()):
                for row in arms.values():
                    row.pop('check_mse');row.pop('check_blocks')
    return r


def test_check_outcomes_cannot_change_locked_choices(replication):
    r,p=replication;before=qr.select_candidates(selection_only(r['rows']),config())
    poisoned=deepcopy(r['rows'])
    for cells in poisoned.values():
        for cell in cells.values():
            for arms in cell['candidates'].values():
                for row in arms.values():row['check_mse']=-1e20;row['check_blocks']=[-1e20]*12
    assert qr.select_candidates(selection_only(poisoned),config())==before
    # Passing combined assessment payload is itself rejected.
    with pytest.raises(ValueError,match='selection_metric_grid'):qr.select_candidates(poisoned,config())


def test_selection_is_one_common_choice_after_averaging_fits(replication):
    r,_=replication;rows=selection_only(r['rows']);cell=rows['95000000']['1']
    for arms in cell['candidates'].values():
        for v in arms.values():v.update(selection_mse=100.,selection_blocks=[100.]*12)
    for key,vals in [('0',[0.,8.,8.]),('1',[4.,4.,4.])]:
        for s,v in zip(config()['constant_seeds'],vals):cell['candidates'][key][str(s)].update(selection_mse=v,selection_blocks=[v]*12)
    assert qr.select_candidates(rows,config())['95000000']['1']==1
    for v in cell['candidates']['0'].values():v.update(selection_mse=4.,selection_blocks=[4.]*12)
    assert qr.select_candidates(rows,config())['95000000']['1']==0


@pytest.mark.parametrize('fault',['task','budget','candidate','fit','start','action','block','metric','bool','string','nan','infinity','array','reward','frozen','choice','lock','closed','seed'])
def test_incomplete_invalid_grids_rejected(replication,fault):
    r,p=deepcopy(replication);row=r['rows']['95000000']['1']['candidates']['0']['7201']
    q=r['queries']['95000000']['check']
    if fault=='task':del r['rows']['95000000']
    elif fault=='budget':del r['rows']['95000000']['8']
    elif fault=='candidate':del r['rows']['95000000']['1']['candidates']['0']
    elif fault=='fit':del r['rows']['95000000']['1']['candidates']['0']['7201']
    elif fault=='start':q['records'].pop()
    elif fault=='action':q['records'][0]['outcomes'].pop()
    elif fault=='block':row['check_blocks'].pop()
    elif fault=='metric':del row['selection_mse']
    elif fault=='bool':row['check_mse']=True
    elif fault=='string':row['check_blocks'][0]='0'
    elif fault=='nan':row['check_mse']=float('nan')
    elif fault=='infinity':row['check_blocks'][0]=float('inf')
    elif fault=='array':q['arrays']['y'][0]+=.1
    elif fault=='reward':q['records'][0]['outcomes'][0]['reward']+=1
    elif fault=='frozen':r['frozen_after']['state']='changed'
    elif fault=='choice':r['selection_manifest']['choices']['95000000']['1']=99
    elif fault=='lock':r['selection_locked_before_check']=False
    elif fault=='closed':r['closed_initials'].append([0,0,'red','square','small',5,5])
    elif fault=='seed':q['records'][0]['seed']=config()['query_seeds']['95000000']['selection'][0]
    with pytest.raises((ValueError,KeyError)):qr.validate(r,config(),p)


def test_selection_manifest_must_be_saved_and_exact(replication,tmp_path):
    m=replication[0]['selection_manifest'];path=tmp_path/'locked.json'
    with pytest.raises(ValueError):qr.require_selection(path,m)
    path.write_text(json.dumps(m));qr.require_selection(path,m)
    bad=deepcopy(m);bad['choices']['95000000']['1']=99
    with pytest.raises(ValueError):qr.require_selection(path,bad)
    bad=deepcopy(m);bad['complete']=False;path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):qr.require_selection(path,bad)


def test_closed_seeds_and_checkpoint_provenance_are_verified_without_neural_import():
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.query_replication import source_pack;c=json.load(open(Path(sys.argv[2])/"configs/seed_query_replication.json"));p=source_pack(Path(sys.argv[2]),c);assert len(p["rows"])==12;assert len(p["closed_initials"])>1000;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
    c=config();c['parent_model_sha256']='0'*64
    with pytest.raises(ValueError,match='query_parent_hash'):qr.source_pack(ROOT,c)
    c=config();c['seed_inventory']['artifacts/seed_contract_gui.json']='0'*64
    with pytest.raises(ValueError,match='query_history_hash'):qr.source_pack(ROOT,c)
    assert qr.historical_seeds({'nested':{'episode_seeds':[1,2]},'score':900})=={1,2}


def test_closed_seed_reuse_rejected_before_inference(monkeypatch):
    original=qr.historical_seeds;injected=config()['query_seeds']['95000000']['check'][0]
    monkeypatch.setattr(qr,'historical_seeds',lambda v:original(v)|{injected})
    c=config()
    # Keep the altered conservative inventory internally consistent so overlap
    # itself, rather than only the inventory checksum, must reject it.
    old=set()
    for n in c['seed_inventory']:old.update(qr.historical_seeds(json.loads((ROOT/n).read_text())))
    c['historical_seed_sha256']=digest(sorted(old))
    with pytest.raises(ValueError,match='closed_query_seed_reuse'):qr.source_pack(ROOT,c)


def test_better_check_oracle_cannot_upgrade_failed_locked_choice(replication):
    r,p=deepcopy(replication)
    for cells in r['rows'].values():
        for cell in cells.values():
            for row in cell['before'].values():row['check_mse']=1.
            for index,arms in cell['candidates'].items():
                for row in arms.values():row['check_mse']=.1 if index!=str(cell['variance_index']) else 2.
    choices={t:{b:cell['variance_index'] for b,cell in cells.items()} for t,cells in r['rows'].items()}
    a=qr.summarize(r['rows'],choices,config(),p)
    assert a['check_means']['check_oracle']<a['check_means']['selected']
    assert a['screen_passed'] is False and a['label']=='question_utility_stability_not_demonstrated'


def test_verifier_imports_in_isolated_stdlib_python():
    code='import runpy,sys;r=runpy.run_path(sys.argv[1],run_name="import_only");assert callable(r["verify"]);assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_query_replication.py')],check=True,timeout=10)


@pytest.mark.parametrize('k,v',[('budgets',[1,2,4]),('starts_per_role',11),('minimum_fraction',.01),('max_authored_steps',2593),('max_posterior_rows',289),('max_wall_s',61),('constant_seeds',[7201])])
def test_locked_plan_cannot_shrink_or_expand(k,v):
    c=config();c[k]=v
    with pytest.raises(ValueError):qr.config_check(c)


def test_resource_caps_apply_before_work():
    from nexus.seed.nonlinear_learning import Meter
    c=config();m=Meter(c);m.posterior=288;m.imagined=2592;m.costs['collection']=2592
    with pytest.raises(ValueError,match='posterior_cap'):m.model(1,posterior=True)
    with pytest.raises(ValueError,match='imagined_cap'):m.model(1)
    with pytest.raises(ValueError,match='real_cap'):m.charge('collection')
    assert (m.posterior,m.imagined,m.costs['collection'])==(288,2592,2592)


def test_collector_clones_each_action_and_preserves_model_state(monkeypatch):
    from nexus.seed import nonlinear_learning as nl
    # Tiny fixture implements the existing API without constructing a world.
    class Fixture:
        def __init__(self):self.obj={'x':0};self.steps=0;self.flags=[0,0,0];self.goal=(5,5)
        def observe(self):return {'proprio':torch.zeros(12)}
        def step(self,a):
            assert self.obj['x']==0 and self.steps==0
            self.steps+=1;self.obj['x']=a
            return self.observe(),float(a),False,{}
    class Meter:
        def __init__(self):self.charges=0
        def charge(self,role):assert role=='collection';self.charges+=1
    origins=[]
    def fresh(*args):w=Fixture();origins.append(w);return w
    monkeypatch.setattr(nl,'fresh_world',fresh)
    monkeypatch.setattr(nl,'score_basis',lambda *args:(torch.arange(9*33).reshape(9,33).float(),torch.arange(9).float()/10,None))
    m=Meter();q=qr.collect_queries(object(),object(),list(range(12)),[5,5],m,set())
    assert m.charges==108 and len(q['arrays']['y'])==108
    assert all(w.steps==0 and w.obj=={'x':0} for w in origins)
    assert q['arrays']['y'][7]==pytest.approx(6.3,abs=1e-6)


def test_frozen_feature_path_is_deterministic_and_does_not_change_networks():
    # Model inference on a zero tensor fixture; no authored state is constructed.
    from nexus.world.seed_rssm import SeedRSSM
    from nexus.seed.action_readout import ActionReadout,features
    from nexus.seed.state_contract import Belief
    torch.manual_seed(7);m=SeedRSSM();head=ActionReadout();b=Belief(m)
    before=digest({k:v.tolist() for k,v in m.state_dict().items()});h=b.h.clone();z=b.z.clone()
    x1,base1=features(m,b.h,b.z,torch.zeros(1,12));x2,base2=features(m,b.h,b.z,torch.zeros(1,12))
    assert torch.equal(x1,x2) and torch.equal(base1,base2)
    assert torch.equal(b.h,h) and torch.equal(b.z,z)
    assert before==digest({k:v.tolist() for k,v in m.state_dict().items()})
    initial=digest({k:v.tolist() for k,v in head.state_dict().items()})
    for _ in range(2):head.adaptation_features(x1);head(x1)
    assert initial==digest({k:v.tolist() for k,v in head.state_dict().items()})
