"""Registered E3.11 host adapter over existing planners, ridge and ledger."""
from copy import deepcopy
from dataclasses import asdict
import itertools
import json
import math
import time
import numpy as np
from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work,Operation,Clock,Limits,ReservationLedger,model_work
from nexus.evolution2.generated_strategies import execute,AdvantagePredictor
from nexus.evolution2.full_policy_source import controllers,operation_plan
from nexus.evolution2.planner_evidence import ForwardCheckedStep


def grid(c,role):
    return set(itertools.product(c['families'],c['model_bundles'],c[role+'_episodes']))


def seeds(c,f,e):
    offset=c['families'].index(f)*10000+e*1000
    return {k:c[k+'_seed_base']+offset for k in ('env','planner','probe','evidence')}


def registered_seeds(c):
    roles={k:set() for k in ('env','planner','probe','evidence')}
    for f,e in itertools.product(c['families'],c['training_episodes']+c['evaluation_episodes']):
        s=seeds(c,f,e)
        for k in roles:roles[k].update(range(s[k]+8,s[k]+200) if k=='planner' else range(s[k],s[k]+(2 if k=='evidence' else 1)))
    keys=list(roles)
    if any(roles[a]&roles[b] for a,b in itertools.combinations(keys,2)):raise ValueError('seed_role_collision')
    return set.union(*roles.values())


def simulator_fingerprint(env):
    """Trusted restoration metadata, never a feature passed to a learner."""
    inner=env.unwrapped;wrappers=[];current=env
    while True:
        wrappers.append((type(current).__name__,getattr(current,'__dict__',{}).get('_elapsed_steps')))
        if not hasattr(current,'env'):break
        current=current.env
    last_u=getattr(inner,'last_u',None)
    state=dict(state=np.asarray(inner.state).tolist(),rng=inner.np_random.bit_generator.state,
        wrappers=wrappers,last_u=None if last_u is None else float(last_u))
    return digest(state)


def restore_copy(env):
    before=simulator_fingerprint(env);copy=deepcopy(env)
    if simulator_fingerprint(copy)!=before:raise ValueError('exact_simulator_restoration')
    return copy,before


def feature_vector(evidence,support_mae):
    if set(evidence)!={'successor_anchor','rank_blend'}:raise ValueError('paired_forecasts')
    a,b=(evidence[k] for k in ('successor_anchor','rank_blend'))
    survival=lambda x:float(np.prod(1-np.asarray(x['termination_estimates']),axis=0).mean())
    x=[1.,float(max(b['scores'])-max(a['scores'])),survival(b)-survival(a),float(support_mae)]
    if not np.isfinite(x).all():raise ValueError('finite_probe_features')
    return x


class ProbeSelector:
    """Same AdvantagePredictor, two fixed family fits; no outcome lookup path."""
    def __init__(self,rows,c):
        ids=[(r['family'],r['bundle'],r['episode']) for r in rows]
        if len(ids)!=len(grid(c,'training')) or set(ids)!=grid(c,'training') or any(r['role']!='training' for r in rows):raise ValueError('fresh_training_feedback_only')
        self.means={f'{f}:{b}':float(np.mean([r['returns']['rank_blend']-r['returns']['successor_anchor'] for r in rows if (r['family'],r['bundle'])==(f,b)])) for f,b in itertools.product(c['families'],c['model_bundles'])}
        self.models={}
        for f in c['families']:
            model=AdvantagePredictor()
            selected=[r for r in rows if r['family']==f]
            for r in selected:
                model.observe(r['features'],r['returns']['rank_blend']-r['returns']['successor_anchor'],
                    baseline=self.means[f'{f}:{r["bundle"]}'],event=f'{f}:{r["bundle"]}:{r["episode"]}',provenance='revealed_source')
            model.predict(selected[0]['features']);self.models[f]=model

    def state(self):
        return dict(means=self.means,models={f:dict(scale=m.model[0].tolist(),beta=m.model[1].tolist(),fit_calls=m.fit_calls) for f,m in self.models.items()})

    def fingerprint(self):return digest(self.state())

    def decide(self,f,b,features):
        base=self.means[f'{f}:{b}'];prediction=self.models[f].predict(features,baseline=base)
        choose=lambda v:'rank_blend' if v>0 else 'successor_anchor'
        return dict(estimated_advantage=prediction,model_mean=base,choices=dict(contextual_selector=choose(prediction),
            model_mean=choose(base),always_successor='successor_anchor',always_rank_blend='rank_blend'))


class Dispatch:
    def __init__(self,host,ops,ledger):self.host=host;self.ops={o.key:o for o in ops};self.ledger=ledger

    def model(self,key,obs,actions):
        cost=model_work(np.asarray(obs).reshape(-1,self.host.wm.net.obs_dim).shape,int(np.asarray(actions).size))
        if cost!=self.ops[key].cost:raise ValueError('actual_model_batch_matches_plan')
        ticket=self.ledger.reserve(key,self.host.clock())
        try:value=self.host.instrument.step_reserved(np.asarray(obs),np.asarray(actions),ticket)
        except BaseException:self.ledger.settle(ticket,'failed',self.host.clock());raise
        self.ledger.settle(ticket,'success',self.host.clock());return value

    def environment(self,key,env,action):
        if type(action) is not int or not 0<=action<3 or self.ops[key].kind!='environment':raise ValueError('registered_real_action')
        ticket=self.ledger.reserve(key,self.host.clock())
        try:value=env.step(action)
        except BaseException:self.ledger.settle(ticket,'failed',self.host.clock());raise
        self.ledger.settle(ticket,'success',self.host.clock());return value

    def action(self,label,family,obs,seed,prefix):
        strategy=controllers()[label];keys=[prefix+o.key for o in operation_plan(strategy,obs,3) if o.kind=='model'];cursor=[0]
        outer=self
        class Model:
            def step(self,o,a):
                key=keys[cursor[0]];result=outer.model(key,o,a);cursor[0]+=1;return result
        action=execute(strategy,family,obs,Model(),seed=seed)
        if cursor[0]!=len(keys):raise ValueError('planner_calls_complete')
        return int(action)


def planning_ops(label,obs,prefix):
    return tuple(Operation(prefix+o.key,o.kind,o.cost) for o in operation_plan(controllers()[label],obs,3) if o.kind=='model')


class Host:
    """Trusted worker binder; all metering remains ReservationLedger-owned."""
    def __init__(self,c,clock,journal):
        self.c=c;self.clock=clock;self.journal=journal
        self.reserved=Work();self.completed=Work();self.unknown=Work();self.wm=None
    def bind(self,wm):self.wm=wm;self.instrument=ForwardCheckedStep(wm)
    def perform(self,ops,body,meta):
        upper=Work()
        for op in ops:upper=upper.plus(op.cost)
        cap=Work(real_steps=self.c['real_cap'],imagined_transitions=self.c['imagined_cap'],model_calls=self.c['model_call_cap'],network_forwards=self.c['network_forward_cap'])
        if not self.reserved.plus(upper).fits(cap):raise ValueError('global_pre_dispatch_cap')
        self.reserved=self.reserved.plus(upper)
        ledger=ReservationLedger(tuple(ops),Limits(upper,upper,int(self.c['time_cap_s']*1e9),int(self.c['time_cap_s']*1e9)))
        try:value=body(Dispatch(self,ops,ledger))
        finally:
            report=ledger.close(self.clock());self.completed=self.completed.plus(report.physical_completed_reported);self.unknown=self.unknown.plus(report.physical_unknown_upper_bound)
            self.journal.write((json.dumps(dict(meta=meta,report=asdict(report)),separators=(',',':'))+'\n').encode())
        if report.status!='complete_execution':raise ValueError('complete_execution_required')
        return value,report
    def resources(self):return {k:asdict(v) for k,v in [('reserved',self.reserved),('completed',self.completed),('unknown_upper',self.unknown)]}


def manifest(c,revision):
    tasks=[f'{f}:{b}' for f,b in itertools.product(c['families'],c['model_bundles'])]
    cases=[]
    for task,e,label in itertools.product(tasks,c['evaluation_episodes'],c['controllers']):
        f=task.split(':')[0];s=seeds(c,f,e)
        cases.append(dict(task=task,episode=e,condition=label,reset_seed=s['env'],planner_seed=s['planner'],probe_steps=8,remaining_steps=192))
    return dict(kind='registered_fresh_study',registered=True,authorized=True,protocol_commit=revision,
        planned_tasks=tasks,planned_episodes=c['evaluation_episodes'],conditions=c['controllers'],cases=cases,
        n_actions=3,total_real_cap=6272,total_imagined_cap=10000000,per_case_real_cap=192,per_case_imagined_cap=294912)


def analyze(rows,c):
    out={};passed=True
    for f in c['families']:
        models=[]
        for b in c['model_bundles']:
            selected=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            means={m:float(np.mean([r['returns'][r['decision']['choices'][m]] for r in selected])) for m in c['methods']}
            truth=np.array([r['returns']['rank_blend']-r['returns']['successor_anchor'] for r in selected])
            prediction=np.array([r['decision']['estimated_advantage'] for r in selected])
            models.append(dict(bundle=b,mean_returns=means,advantage_mae=float(np.abs(truth-prediction).mean()),
                sign_accuracy=float(np.mean((truth>0)==(prediction>0))),
                feature_std=np.std([r['features'] for r in selected],axis=0).tolist(),
                overrides=sum(r['decision']['choices']['contextual_selector']!=r['decision']['choices']['model_mean'] for r in selected),
                regret={m:float(np.mean([max(r['returns'].values())-r['returns'][r['decision']['choices'][m]] for r in selected])) for m in c['methods']}))
        contrasts={}
        for baseline in c['methods'][1:]:
            x=[m['mean_returns']['contextual_selector']-m['mean_returns'][baseline] for m in models]
            mean=float(np.mean(x));half=12.7062047364*float(np.std(x,ddof=1))/math.sqrt(2)
            contrasts[baseline]=dict(per_model=x,mean=mean,ci95=[mean-half,mean+half],unit='two pretrained models',interval='unadjusted exploratory df1')
        point=contrasts['model_mean']['mean']>=c['practical_margin'] and all(x>0 for x in contrasts['model_mean']['per_model'])
        passed&=point;out[f]=dict(models=models,mean_returns={m:float(np.mean([r['mean_returns'][m] for r in models])) for m in c['methods']},contrasts=contrasts,point_screen=point)
    return dict(families=out,label='development_point_screen_passed_not_confirmed' if passed else 'post_probe_context_selection_not_established',
        inference='Exploratory existing source models, two per family; no unfamiliar-physics or general-control claim.')


def validate(p,c):
    expected={(f,b,e,role) for role in ('training','evaluation') for f,b,e in grid(c,role)}
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['pairs']]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('complete_independent_pair_grid')
    for r in p['pairs']:
        if set(r['paths'])!=set(c['controllers']):raise ValueError('complete_controller_grid')
        if len(r['prefix'])!=8 or any(x['step']!=i for i,x in enumerate(r['prefix'])):raise ValueError('complete_chronological_probe')
        if len(r['features'])!=4 or not np.isfinite(r['features']).all():raise ValueError('finite_features')
        if r['support_hash']!=digest(tuple(r['prefix'])):raise ValueError('shared_support_hash')
        if not np.allclose(r['features'],feature_vector(r['evidence'],r['support_prediction_mae']),rtol=0,atol=1e-12):raise ValueError('forecast_feature_replay')
        for i,step in enumerate(r['prefix']):
            if i and step['observation']!=r['prefix'][i-1]['next_observation']:raise ValueError('probe_continuity')
            if type(step['reward']) not in (int,float) or not math.isfinite(step['reward']):raise ValueError('finite_probe_reward')
        if set(r['returns'])!=set(c['controllers']):raise ValueError('complete_return_grid')
        dim=3 if r['family']=='pendulum' else 6
        for forecast in r['evidence'].values():
            actions=np.asarray(forecast['actions']);states=np.asarray(forecast['states']);probs=np.asarray(forecast['termination_estimates'])
            if actions.shape!=(16,16) or actions.dtype.kind not in 'iu' or np.any(actions<0) or np.any(actions>2) or states.shape!=(16,16,dim) or probs.shape!=(16,16):raise ValueError('complete_forecast_grid')
            if not np.isfinite(states).all() or not np.isfinite(probs).all() or not np.isfinite(forecast['scores']).all() or np.any(probs<0) or np.any(probs>1):raise ValueError('finite_forecasts')
        for label,path in r['paths'].items():
            if len(path['steps'])!=192 or path['restored_hash']!=r['restoration_hash']:raise ValueError('restored_complete_path')
            for i,s in enumerate(path['steps']):
                if s['tick']!=i+8 or s['planner_seed']!=seeds(c,r['family'],r['episode'])['planner']+i+8:raise ValueError('paired_tick_seed')
                if type(s['reward']) not in (float,int) or not math.isfinite(s['reward']):raise ValueError('finite_reward')
                if type(s['action']) is not int or s['action'] not in range(3) or np.asarray(s['obs']).shape!=(dim,) or np.asarray(s['next_obs']).shape!=(dim,) or not np.isfinite(s['obs']).all() or not np.isfinite(s['next_obs']).all():raise ValueError('finite_observation_action')
                if s['terminated'] is not False or s['truncated'] is not (i==191):raise ValueError('episode_boundary')
                previous=path['steps'][i-1]['next_obs'] if i else r['prefix'][-1]['next_observation']
                if s['obs']!=previous:raise ValueError('transition_continuity')
            if not math.isclose(sum(s['reward'] for s in path['steps']),r['returns'][label],rel_tol=0,abs_tol=1e-8):raise ValueError('actual_return_accounting')
        if r['role']=='evaluation':
            if set(r['decision']['choices'])!=set(c['methods']) or any(v not in c['controllers'] for v in r['decision']['choices'].values()):raise ValueError('complete_frozen_decisions')
            if r['decision']['recipe_hash']!=p['selector_hash']:raise ValueError('frozen_selector')
    actual=p['resources']['completed']
    if actual!=dict(real_steps=10976,imagined_transitions=16129288,model_calls=638596,network_forwards=638596) or any(p['resources']['unknown_upper'].values()):raise ValueError('resource_reconciliation')
    if p['observed_model_calls']!=638596 or p['observed_forwards']!=638596:raise ValueError('actual_forward_hook_counts')
    if len(p['models'])!=4 or {(r['family'],r['bundle']) for r in p['models']}!=set(itertools.product(c['families'],c['model_bundles'])) or any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_checkpoint_states')
    return True
