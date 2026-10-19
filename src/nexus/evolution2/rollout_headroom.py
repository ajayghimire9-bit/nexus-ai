"""Source-only policy-forecast diagnostic; reuses the existing metered host."""
from dataclasses import asdict
import gzip
import hashlib
import itertools
import json
import os
import subprocess
import time
import numpy as np
from nexus.evolution1.resources import Operation,Work,Clock
from nexus.evolution2 import post_probe as host_api
from nexus.evolution2.full_policy_source import DecisionJournal,state_hash
from nexus.evolution2.planner_adapter import iid_sequences
from nexus.evolution2.planner_evidence import evidence_operations,planner_evidence
from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward


def validate_config(c):
    fixed=dict(families=['pendulum','acrobot'],model_bundles=[0,1],source_offsets=[0,32,64,96],
        controllers=['successor_anchor','rank_blend'],rollout_steps=16,planner_seed_base=731003,
        forecast_difference_threshold=1e-6,time_cap_s=30,real_cap=0,imagined_cap=772096,
        model_call_cap=31232,network_forward_cap=31232)
    if json.dumps({k:c[k] for k in fixed},sort_keys=True)!=json.dumps(fixed,sort_keys=True):raise ValueError('locked_rollout_configuration')


def walk(initial,evaluate,reward,steps=16):
    """Pure loop: callback supplies only action and frozen-model predictions."""
    obs=np.asarray(initial,dtype=np.float32).copy();alive=1.;score=0.;rows=[]
    for t in range(steps):
        action,nxt,prob=evaluate(obs.copy(),t);nxt=np.asarray(nxt,dtype=np.float32)
        if type(action) is not int or action not in range(3) or nxt.shape!=obs.shape or not np.isfinite(nxt).all() or not np.isfinite(prob) or not 0<=prob<=1:raise ValueError('finite_predicted_policy_step')
        r=float(np.asarray(reward(obs,action,nxt)).reshape(-1)[0])
        if not np.isfinite(r):raise ValueError('finite_predicted_reward')
        rows.append(dict(step=t,obs=obs.tolist(),action=action,next_obs=nxt.tolist(),termination_probability=float(prob),predicted_reward=r,survival_before=alive))
        score+=alive*r;alive*=1-prob;obs=nxt
    return dict(steps=rows,predicted_score=score,final_survival=alive)


def analyze(rows,c):
    families={};unassessable=False
    for f in c['families']:
        cohort=[r for r in rows if r['family']==f and r['paths']['successor_anchor']['steps'][0]['action']==r['paths']['rank_blend']['steps'][0]['action']]
        visible=[];details=[]
        for r in cohort:
            a,b=(r['paths'][k] for k in c['controllers'])
            disagreements=sum(x['action']!=y['action'] for x,y in zip(a['steps'][1:],b['steps'][1:]))
            gap=b['predicted_score']-a['predicted_score']
            common=max(r['common']['rank_blend']['scores'])-max(r['common']['successor_anchor']['scores'])
            has=disagreements>0 and abs(gap)>c['forecast_difference_threshold'];visible.append(has)
            details.append(dict(bundle=r['bundle'],offset=r['offset'],later_action_disagreements=disagreements,predicted_score_gap=gap,
                common_score_gap=common,endpoint_l2=float(np.linalg.norm(np.asarray(b['steps'][-1]['next_obs'])-a['steps'][-1]['next_obs'])),headroom=has))
        if not cohort:unassessable=True
        families[f]=dict(same_first_contexts=len(cohort),visible_contexts=sum(visible),point_screen=any(visible),contexts=details)
    label='headroom_unassessable' if unassessable else ('controller_specific_forecast_headroom_visible' if all(x['point_screen'] for x in families.values()) else 'controller_specific_headroom_not_established')
    return dict(label=label,families=families,measured_environment_returns=False,scope='Forecast distinguishability only; no accuracy or control claim.')


def validate_forecasts(r,controllers):
    if set(r['paths'])!=set(controllers) or set(r['common'])!=set(controllers):raise ValueError('complete_controller_conditions')
    reward=pendulum_step_reward if r['family']=='pendulum' else acrobot_step_reward
    for path in r['paths'].values():
        steps=path['steps']
        if len(steps)!=16:raise ValueError('complete_rollout_steps')
        replay=walk(r['initial_observation'],lambda obs,t:(steps[t]['action'],steps[t]['next_obs'],steps[t]['termination_probability']),reward)
        if replay!=path:raise ValueError('reward_survival_or_continuity_replay')
    for label,forecast in r['common'].items():
        actions=np.asarray(forecast['actions']);states=np.asarray(forecast['states']);probabilities=np.asarray(forecast['termination_estimates'])
        dim=len(r['initial_observation'])
        if actions.shape!=(16,16) or actions.dtype.kind not in 'iu' or states.shape!=(16,16,dim) or probabilities.shape!=(16,16):raise ValueError('complete_common_forecasts')
        if not np.isfinite(states).all() or not np.isfinite(probabilities).all() or np.any(probabilities<0) or np.any(probabilities>1) or np.any(actions<0) or np.any(actions>2):raise ValueError('finite_common_forecasts')
        if not np.all(actions[:,0]==r['paths'][label]['steps'][0]['action']):raise ValueError('cached_first_action_pairing')
        state=np.repeat(np.asarray(r['initial_observation'],dtype=np.float32)[None,:],16,axis=0);alive=np.ones(16);scores=np.zeros(16)
        for t in range(16):
            nxt=states[t].astype(np.float32);scores+=alive*reward(state,actions[:,t],nxt);alive*=1-probabilities[t];state=nxt
        values=np.asarray(forecast['scores'])
        if values.shape!=(16,) or not np.isfinite(values).all() or not np.allclose(scores,values,rtol=0,atol=1e-9):raise ValueError('common_score_replay')
    a,b=(r['paths'][k]['steps'][0]['action'] for k in controllers)
    if a==b and r['common']['successor_anchor']['scores']!=r['common']['rank_blend']['scores']:raise ValueError('same_action_common_tail_identity')


def validate(p,c):
    expected=set(itertools.product(c['families'],c['model_bundles'],c['source_offsets']))
    keys=[(r['family'],r['bundle'],r['offset']) for r in p['rows']]
    if len(keys)!=len(expected) or set(keys)!=expected:raise ValueError('complete_fixed_source_grid')
    for r in p['rows']:
        validate_forecasts(r,c['controllers'])
    target=dict(real_steps=0,imagined_transitions=772096,model_calls=31232,network_forwards=31232)
    if p['resources']['completed']!=target or any(p['resources']['unknown_upper'].values()) or p['observed_calls']!=31232 or p['observed_forwards']!=31232:raise ValueError('metered_counts')
    expected_models=set(itertools.product(c['families'],c['model_bundles']))
    if len(p['models'])!=4 or {(r['family'],r['bundle']) for r in p['models']}!=expected_models or any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_model_grid')
    return True


def worker(api):
    use=json.loads(api.USAGE.read_text())
    if use['parent_pid']!=os.getppid() or os.environ.get('NEXUS_E311_PARENT')!=str(os.getppid()):raise ValueError('parent_launch_required')
    import torch
    from nexus.world.dynamics import WorldModel,DynamicsMLP
    torch.set_num_threads(1);cpu=time.process_time_ns()
    c=json.loads(api.CONFIG.read_text());validate_config(c)
    p=json.loads(api.RESULT.read_text());p['rows']=[];p['kind']='source_only_forecast_headroom'
    clock=lambda:Clock(time.process_time_ns()-cpu,int((time.perf_counter()-use['start_monotonic'])*1e9))
    inventory=json.loads((api.ROOT/c['checkpoint_inventory']).read_text())['integrity']
    files=inventory['checkpoints']+inventory['source_arrays']
    if any(api.sha(api.ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_input_hash')
    if len(inventory['checkpoints'])!=4 or {(r['family'],r['bundle']) for r in inventory['checkpoints']}!=set(itertools.product(c['families'],c['model_bundles'])):raise ValueError('checkpoint_grid')
    journal=DecisionJournal(api.JOURNAL);host=host_api.Host(c,clock,journal)
    p['observed_calls']=p['observed_forwards']=0
    def persist():p['resources']=host.resources();api.save(p)
    try:
        with journal:
            for item in inventory['checkpoints']:
                f,b=item['family'],item['bundle'];wm=WorldModel.load(api.ROOT/item['path'])
                if type(wm) is not WorldModel or type(wm.net) is not DynamicsMLP or wm.net.arch!='mlp' or wm.kind!='residual' or str(wm.device)!='cpu' or wm.net.n_actions!=3:raise ValueError('frozen_cpu_mlp_only')
                wm.net.eval();before=state_hash(wm);host.bind(wm)
                source=next(x for x in inventory['source_arrays'] if x['family']==f and x['bundle']==b and '_train.npz' in x['path'])
                with np.load(api.ROOT/source['path'],allow_pickle=False) as data:obs_source=data['obs'][c['source_offsets']].copy()
                reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
                for index,offset in enumerate(c['source_offsets']):
                    seed=c['planner_seed_base']+c['families'].index(f)*100000+b*20000+index*1000
                    initial=obs_source[index];row=dict(family=f,bundle=b,offset=offset,initial_observation=initial.tolist(),paths={},planner_seed=seed)
                    p['active_work']=dict(family=f,bundle=b,offset=offset,unknown_context_upper=dict(real_steps=0,imagined_transitions=48256,model_calls=1952,network_forwards=1952));persist()
                    for label in c['controllers']:
                        def evaluate(obs,t):
                            ops=host_api.planning_ops(label,obs,'')+(Operation('advance','model',Work(imagined_transitions=1,model_calls=1,network_forwards=1)),)
                            def body(d):
                                a=d.action(label,f,obs,seed+t,'');nxt,prob=d.model('advance',obs[None,:],np.array([a]));return a,nxt[0],float(prob[0])
                            result,_=host.perform(ops,body,dict(kind='policy_rollout',family=f,bundle=b,offset=offset,controller=label,step=t))
                            return result
                        row['paths'][label]=walk(initial,evaluate,reward,steps=c['rollout_steps'])
                    tails=iid_sequences(seed+500,16,15,3)
                    plans={label:np.column_stack((np.full(16,row['paths'][label]['steps'][0]['action']),tails)) for label in c['controllers']}
                    def common_body(d):return planner_evidence(plans,initial,host.instrument,reward,n_actions=3,ledger=d.ledger,clock=clock,fingerprint=lambda:state_hash(wm))
                    row['common'],_=host.perform(evidence_operations(plans,3),common_body,dict(kind='common_tail',family=f,bundle=b,offset=offset))
                    p['rows'].append(row);p['active_work']=None;persist()
                p['observed_calls']+=host.instrument.calls;p['observed_forwards']+=host.instrument.network_forwards
                p['models'].append({**item,'before':before,'after':state_hash(wm)})
            p['resources']=host.resources();validate(p,c);p['analysis']=analyze(p['rows'],c)
            if any(api.sha(api.ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_files_changed')
            p['declared_complete']=True
    finally:
        p['resources']=host.resources();p['journal_parts']=[dict(path=str(path.relative_to(api.ROOT)),sha256=api.sha(path)) for path in journal.paths]
        p['worker_cpu_s']=time.process_time();p['dependencies']=dict(torch=torch.__version__,numpy=np.__version__);api.save(p)


def verify(api):
    start=time.perf_counter();p=json.loads(api.RESULT.read_text());c=json.loads(api.CONFIG.read_text())
    if not p['declared_complete'] or p['config_sha256']!=api.sha(api.CONFIG):raise ValueError('complete_locked_capture')
    validate(p,c)
    if analyze(p['rows'],c)!=p['analysis']:raise ValueError('screen_replay')
    for n,h in p['historical_json_sha256'].items():
        if api.sha(api.ROOT/n)!=h:raise ValueError('historical_json_changed')
    for n,h in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{n}'],cwd=api.ROOT)
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('execution_code_hash')
    totals={k:0 for k in ('real_steps','imagined_transitions','model_calls','network_forwards')};records=0
    for part in p['journal_parts']:
        if api.sha(api.ROOT/part['path'])!=part['sha256']:raise ValueError('journal_hash')
        with gzip.open(api.ROOT/part['path'],'rt') as handle:
            for line in handle:
                records+=1;receipt=json.loads(line)['report']
                if receipt['status']!='complete_execution':raise ValueError('incomplete_journal')
                events=[(e['kind'],json.loads(e['payload_json'])) for e in receipt['events']]
                reserved={e['operation']:e['physical'] for kind,e in events if kind=='reserved'}
                settled=[e['operation'] for kind,e in events if kind=='settled' and e['outcome']=='success']
                if set(settled)!=set(reserved) or len(settled)!=len(reserved):raise ValueError('journal_operations')
                for key in settled:
                    for field,cost in reserved[key].items():totals[field]+=cost
    if totals!=p['resources']['completed']:raise ValueError('journal_count_replay')
    elapsed=time.perf_counter()-start;prior=p['session_ledger']
    output=dict(valid=True,capture_sha256=api.sha(api.RESULT),resource_records=records,resources_verified=totals,
        new_real_steps=0,new_imagined_transitions=0,model_inference=False,wall_s=elapsed,
        session_ledger=dict(used_before_s=prior['used_after_s'],used_after_s=prior['used_after_s']+elapsed,remaining_after_s=prior['remaining_after_s']-elapsed))
    with api.VALIDATION.open('x') as handle:json.dump(output,handle,indent=2);handle.write('\n')
    print(json.dumps(output));return 0
