"""E3.11B binding over the existing post-probe host; no new learner/meter."""
from dataclasses import asdict
import gzip
import hashlib
import itertools
import json
import os
import resource
import subprocess
import sys
import time
import numpy as np
from nexus.evolution1.resources import Operation, Work, Clock
from nexus.evolution2 import forecast_calibration as analysis
from nexus.evolution2 import post_probe as h
from nexus.evolution2.rollout_headroom import walk, validate_forecasts
from nexus.evolution2.full_policy_source import DecisionJournal, state_hash, task_spec
from nexus.evolution2.planner_adapter import iid_sequences
from nexus.evolution2.planner_evidence import evidence_operations, planner_evidence
from nexus.world.rewards import pendulum_step_reward, acrobot_step_reward


def settings(api):
    c=json.loads(api.CONFIG.read_text())
    expected=dict(version='e3_11b_execution_v1',families=['pendulum','acrobot'],model_bundles=[0,1],
        training_episodes=[],evaluation_episodes=[0,1,2,3],controllers=['successor_anchor','rank_blend'],
        env_seed_base=2131000000,planner_seed_base=2132000000,probe_seed_base=2133000000,evidence_seed_base=2134000000,
        time_cap_s=180,real_cap=6272,imagined_cap=9932800,model_call_cap=393728,network_forward_cap=393728,journal_chunk_decisions=1500)
    if any(k not in c or analysis.digest(c[k])!=analysis.digest(v) for k,v in expected.items()):
        raise ValueError('locked_calibration_settings')
    path=api.ROOT/c['analysis_config']
    if api.sha(path)!=c['analysis_config_sha256']:raise ValueError('preparation_settings_hash')
    a=json.loads(path.read_text());analysis.validate_config(a)
    return c,a


def preflight(api):
    c,a=settings(api);grant=json.loads(api.ALLOCATION.read_text())
    for key in ('time_cap_s','real_cap','imagined_cap','model_call_cap','network_forward_cap'):
        if grant.get(key)!=c[key]:raise ValueError('allocation_cap_mismatch')
    if grant.get('authorized') is not True or grant.get('runs')!=1 or grant.get('automatic_retry') is not False:
        raise ValueError('one_run_allocation_required')
    if grant.get('config_sha256')!=api.sha(api.CONFIG) or grant.get('protocol_sha256')!=api.sha(api.PROTOCOL):
        raise ValueError('allocation_hash')
    if any(x.exists() for x in (api.RESULT,api.USAGE,api.PREDICTIONS,api.VALIDATION)) or list(api.JOURNAL.parent.glob(api.JOURNAL.name.replace('.jsonl.gz','.part*.jsonl.gz'))):
        raise ValueError('one_run_only')
    old={str(p.relative_to(api.ROOT)):api.sha(p) for p in (api.ROOT/'artifacts').rglob('*.json')}
    audit=api.seed_audit(c,old)
    inventory=json.loads((api.ROOT/c['checkpoint_inventory']).read_text())['integrity']
    if api.sha(api.ROOT/c['checkpoint_inventory'])!=c['checkpoint_inventory_sha256']:raise ValueError('inventory_hash')
    if any(api.sha(api.ROOT/r['path'])!=r['sha256'] for r in inventory['checkpoints']+inventory['source_arrays']):raise ValueError('frozen_input_hash')
    analysis.training_means(api.ROOT/a['training_prior'],a['training_prior_sha256'],a)
    return audit


def check_real_step(step, previous, tick, planner_seed, family):
    dim=3 if family=='pendulum' else 6
    if step['tick']!=tick or step['planner_seed']!=planner_seed:raise ValueError('paired_tick_seed')
    if type(step['action']) is not int or step['action'] not in range(3):raise ValueError('real_action')
    if np.asarray(step['obs']).shape!=(dim,) or np.asarray(step['next_obs']).shape!=(dim,) or not np.isfinite(step['obs']).all() or not np.isfinite(step['next_obs']).all():raise ValueError('real_observation')
    if step['obs']!=previous:raise ValueError('real_transition_continuity')
    if step['terminated'] is not False or step['truncated'] is not (tick==199):raise ValueError('real_episode_boundary')
    value=analysis.number(step['reward'])
    reward=pendulum_step_reward if family=='pendulum' else acrobot_step_reward
    expected=float(reward(np.asarray(step['obs']),step['action'],np.asarray(step['next_obs']))[0])
    if not np.isclose(value,expected,rtol=0,atol=1e-5):raise ValueError('published_actual_reward')


def validate(p,c,a,means):
    analysis.validate_rows(p['rows'],a)
    keys=[(r['family'],r['bundle'],r['episode']) for r in p['records']]
    if len(keys)!=16 or set(keys)!=analysis.expected_grid(a):raise ValueError('complete_raw_case_grid')
    flat={(r['family'],r['bundle'],r['episode']):r for r in p['rows']}
    for r in p['records']:
        f,b,e=r['family'],r['bundle'],r['episode'];s=h.seeds(c,f,e);row=flat[f,b,e]
        prefix=r['prefix']
        if len(prefix)!=8 or r['prefix_hash']!=analysis.digest(prefix):raise ValueError('shared_probe_hash')
        previous=prefix[0]['obs']
        expected_probe=np.random.default_rng(s['probe']).integers(0,3,size=8).tolist()
        if [x['action'] for x in prefix]!=expected_probe:raise ValueError('registered_uniform_probe_actions')
        for tick,step in enumerate(prefix):
            check_real_step(step,previous,tick,s['probe'],f);previous=step['next_obs']
        if previous!=r['initial_observation']:raise ValueError('forecast_initial_observation')
        validate_forecasts(r,c['controllers'])
        if r['forecast_planner_seeds']!=[s['planner']+i for i in range(8,24)]:raise ValueError('forecast_planner_pairing')
        for label,path in r['paths'].items():
            if path['steps'][0]['action']!=r['actual'][label]['steps'][0]['action']:raise ValueError('first_forecast_action_reproduction')
        from nexus.evolution2.planner_adapter import iid_sequences
        tails=iid_sequences(s['evidence']+1,16,15,3)
        for label in c['controllers']:
            if not np.array_equal(np.asarray(r['common'][label]['actions'])[:,1:],tails):raise ValueError('shared_tail_pairing')
        predictions=dict(policy_forecast=r['paths']['rank_blend']['predicted_score']-r['paths']['successor_anchor']['predicted_score'],
            common_tail=max(r['common']['rank_blend']['scores'])-max(r['common']['successor_anchor']['scores']),training_mean=means[f'{f}:{b}'])
        if predictions!=row['predictions'] or row['forecast_sha256']!=r['forecast_sha256']:raise ValueError('raw_prediction_replay')
        if set(r['actual'])!=set(c['controllers']):raise ValueError('actual_controller_grid')
        for label,path in r['actual'].items():
            if len(path['steps'])!=192 or path['restored_hash']!=r['restoration_hash']:raise ValueError('restored_complete_path')
            previous=r['initial_observation']
            for i,step in enumerate(path['steps']):
                check_real_step(step,previous,i+8,s['planner']+i+8,f);previous=step['next_obs']
            if [x['reward'] for x in path['steps']]!=row['rewards'][label]:raise ValueError('actual_rewards_replay')
    target=dict(real_steps=c['real_cap'],imagined_transitions=c['imagined_cap'],model_calls=c['model_call_cap'],network_forwards=c['network_forward_cap'])
    if p['resources']['completed']!=target or p['resources']['reserved']!=target or any(p['resources']['unknown_upper'].values()):raise ValueError('metered_resource_counts')
    if p['observed_calls']!=393728 or p['observed_forwards']!=393728:raise ValueError('forward_hook_counts')
    expected=set(itertools.product(c['families'],c['model_bundles']))
    if len(p['models'])!=4 or {(r['family'],r['bundle']) for r in p['models']}!=expected or any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_model_grid')
    return True


def worker(api):
    use=json.loads(api.USAGE.read_text())
    if use['parent_pid']!=os.getppid() or os.environ.get('NEXUS_E311_PARENT')!=str(os.getppid()):raise ValueError('parent_launch_required')
    import torch
    from nexus.world.dynamics import WorldModel, DynamicsMLP
    from nexus.tasks.spec import make_task_env
    torch.set_num_threads(1);cpu=time.process_time_ns();c,a=settings(api)
    p=json.loads(api.RESULT.read_text());p.update(rows=[],records=[],kind='fresh_forecast_calibration',observed_calls=0,observed_forwards=0)
    means=analysis.training_means(api.ROOT/a['training_prior'],a['training_prior_sha256'],a)
    p['seed_audit']=api.seed_audit(c,p['historical_json_sha256'])
    inventory=json.loads((api.ROOT/c['checkpoint_inventory']).read_text())['integrity'];files=inventory['checkpoints']+inventory['source_arrays']
    if any(api.sha(api.ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_input_hash')
    clock=lambda:Clock(time.process_time_ns()-cpu,int((time.perf_counter()-use['start_monotonic'])*1e9))
    journal=DecisionJournal(api.JOURNAL,c['journal_chunk_decisions']);host=h.Host(c,clock,journal)
    def persist():p['resources']=host.resources();api.save(p)
    try:
        with journal, api.PREDICTIONS.open('x') as predictions_file:
            for item in inventory['checkpoints']:
                f,b=item['family'],item['bundle'];wm=WorldModel.load(api.ROOT/item['path'])
                if type(wm) is not WorldModel or type(wm.net) is not DynamicsMLP or wm.net.arch!='mlp' or tuple(wm.net.hidden)!=(64,64) or wm.kind!='residual' or str(wm.device)!='cpu' or wm.net.n_actions!=3:raise ValueError('frozen_cpu_mlp_profile')
                wm.net.eval();before=state_hash(wm);host.bind(wm);reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
                for e in c['evaluation_episodes']:
                    s=h.seeds(c,f,e);env=make_task_env(task_spec(f),seed=s['env']);obs,_=env.reset(seed=s['env'])
                    record=dict(family=f,bundle=b,episode=e,prefix=[],paths={},common={},actual={})
                    p['records'].append(record);p['active_work']=dict(stage='case',family=f,bundle=b,episode=e,unsettled_case_upper=dict(real_steps=392,imagined_transitions=620800,model_calls=24608,network_forwards=24608));persist()
                    try:
                        acts=np.random.default_rng(s['probe']).integers(0,3,size=8)
                        def probe_body(d):
                            nonlocal obs
                            for tick,action in enumerate(acts):
                                nxt,r,term,trunc,_=d.environment(f'probe_{tick}',env,int(action))
                                step=dict(tick=tick,obs=np.asarray(obs).tolist(),next_obs=np.asarray(nxt).tolist(),action=int(action),reward=float(r),terminated=bool(term),truncated=bool(trunc),planner_seed=s['probe'])
                                check_real_step(step,step['obs'],tick,s['probe'],f);record['prefix'].append(step);obs=nxt
                        host.perform(tuple(Operation(f'probe_{i}','environment',Work(real_steps=1)) for i in range(8)),probe_body,dict(stage='probe',family=f,bundle=b,episode=e))
                        initial=np.asarray(obs).copy();record['initial_observation']=initial.tolist();record['prefix_hash']=analysis.digest(record['prefix']);record['restoration_hash']=h.simulator_fingerprint(env)
                        for label in c['controllers']:
                            def evaluate(o,t):
                                ops=h.planning_ops(label,o,'')+(Operation('advance','model',Work(imagined_transitions=1,model_calls=1,network_forwards=1)),)
                                def body(d):
                                    action=d.action(label,f,o,s['planner']+8+t,'');nxt,prob=d.model('advance',o[None,:],np.array([action]));return action,nxt[0],float(prob[0])
                                value,_=host.perform(ops,body,dict(stage='forecast',family=f,bundle=b,episode=e,controller=label,tick=t));return value
                            path=walk(initial,evaluate,reward)
                            record['paths'][label]=path
                        record['forecast_planner_seeds']=[s['planner']+8+t for t in range(16)]
                        tails=iid_sequences(s['evidence']+1,16,15,3)
                        plans={label:np.column_stack((np.full(16,record['paths'][label]['steps'][0]['action']),tails)) for label in c['controllers']}
                        def common_body(d):return planner_evidence(plans,initial,host.instrument,reward,n_actions=3,ledger=d.ledger,clock=clock,fingerprint=lambda:state_hash(wm))
                        record['common'],_=host.perform(evidence_operations(plans,3),common_body,dict(stage='common_tail',family=f,bundle=b,episode=e))
                        guesses=dict(policy_forecast=record['paths']['rank_blend']['predicted_score']-record['paths']['successor_anchor']['predicted_score'],common_tail=max(record['common']['rank_blend']['scores'])-max(record['common']['successor_anchor']['scores']),training_mean=means[f'{f}:{b}'])
                        def persist_forecast(receipt):
                            predictions_file.write(json.dumps(receipt,allow_nan=False)+'\n');predictions_file.flush();os.fsync(predictions_file.fileno())
                            record['forecast_sha256']=receipt['forecast_sha256'];persist();return receipt['forecast_sha256']
                        def continuation(label):
                            restored,signature=h.restore_copy(env)
                            if signature!=record['restoration_hash']:raise ValueError('restoration_changed')
                            current=initial.copy();steps=[];record['actual'][label]=dict(restored_hash=signature,steps=steps)
                            try:
                                for tick in range(8,200):
                                    def body(d):
                                        action=d.action(label,f,current,s['planner']+tick,'');nxt,r,term,trunc,_=d.environment('environment',restored,action)
                                        return dict(tick=tick,obs=current.tolist(),next_obs=np.asarray(nxt).tolist(),action=action,reward=float(r),terminated=bool(term),truncated=bool(trunc),planner_seed=s['planner']+tick)
                                    step,_=host.perform(h.planning_ops(label,current,'')+(Operation('environment','environment',Work(real_steps=1)),),body,
                                        dict(stage='continuation',family=f,bundle=b,episode=e,controller=label,tick=tick,forecast_sha256=record['forecast_sha256']))
                                    check_real_step(step,current.tolist(),tick,s['planner']+tick,f);steps.append(step);current=np.asarray(step['next_obs'],dtype=np.float32)
                                    if tick%64==63:persist()
                                if steps[0]['action']!=record['paths'][label]['steps'][0]['action']:raise ValueError('live_first_action_mismatch')
                                return [x['reward'] for x in steps]
                            finally:restored.close()
                        p['rows'].append(analysis.capture_pair((f,b,e),guesses,persist_forecast,continuation,a))
                        if h.simulator_fingerprint(env)!=record['restoration_hash'] or state_hash(wm)!=before:raise ValueError('frozen_state_changed')
                        p['active_work']=None;persist()
                    finally:env.close()
                p['observed_calls']+=host.instrument.calls;p['observed_forwards']+=host.instrument.network_forwards
                p['models'].append({**item,'before':before,'after':state_hash(wm)})
            p['resources']=host.resources();validate(p,c,a,means);p['analysis']=analysis.analyze(p['rows'],a)
            p['analysis']['label']='development_forecast_point_screen_passed_not_confirmed' if p['analysis']['point_screen'] else 'forecast_utility_not_established'
            if any(api.sha(api.ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_files_changed')
            p['declared_complete']=True
    finally:
        p['resources']=host.resources();p['journal_parts']=[dict(path=str(path.relative_to(api.ROOT)),sha256=api.sha(path)) for path in journal.paths]
        p['predecision_sha256']=api.sha(api.PREDICTIONS) if api.PREDICTIONS.exists() else None
        p['worker_cpu_s']=(time.process_time_ns()-cpu)/1e9
        p['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__);api.save(p)


def verify(api):
    """Saved-data reward/forecast/journal replay only; no environments/models."""
    start=time.perf_counter();c,a=settings(api);p=json.loads(api.RESULT.read_text())
    if not p['declared_complete'] or p['config_sha256']!=api.sha(api.CONFIG) or p['protocol_sha256']!=api.sha(api.PROTOCOL):raise ValueError('complete_locked_capture')
    means=analysis.training_means(api.ROOT/a['training_prior'],a['training_prior_sha256'],a)
    validate(p,c,a,means)
    result=analysis.analyze(p['rows'],a);result['label']='development_forecast_point_screen_passed_not_confirmed' if result['point_screen'] else 'forecast_utility_not_established'
    if result!=p['analysis']:raise ValueError('analysis_replay')
    if api.sha(api.PREDICTIONS)!=p['predecision_sha256']:raise ValueError('immutable_predecision_file')
    predictions=[json.loads(line) for line in api.PREDICTIONS.read_text().splitlines()]
    expected=[{k:r[k] for k in ('family','bundle','episode','predictions','forecast_sha256')} for r in p['rows']]
    if predictions!=expected:raise ValueError('predecision_receipts_replay')
    receipts={(r['family'],r['bundle'],r['episode']):r['forecast_sha256'] for r in predictions}
    inventory=json.loads((api.ROOT/c['checkpoint_inventory']).read_text())['integrity']
    for item in inventory['checkpoints']+inventory['source_arrays']:
        if api.sha(api.ROOT/item['path'])!=item['sha256']:raise ValueError('frozen_file_hash')
    for name,value in p['historical_json_sha256'].items():
        if api.sha(api.ROOT/name)!=value:raise ValueError('historical_json_changed')
    for name,value in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=api.ROOT)
        if hashlib.sha256(raw).hexdigest()!=value:raise ValueError('execution_source_hash')
    totals={k:0 for k in ('real_steps','imagined_transitions','model_calls','network_forwards')}
    stages={};identifiers=set();records=0
    for part in p['journal_parts']:
        if api.sha(api.ROOT/part['path'])!=part['sha256']:raise ValueError('journal_hash')
        with gzip.open(api.ROOT/part['path'],'rt') as handle:
            for line in handle:
                entry=json.loads(line);report=entry['report'];meta=entry['meta'];records+=1
                key=(meta['family'],meta['bundle'],meta['episode']);stage=meta['stage']
                if key not in receipts:raise ValueError('unplanned_journal_case')
                ident=key+(stage,meta.get('controller'),meta.get('tick'))
                if ident in identifiers:raise ValueError('duplicate_journal_decision')
                identifiers.add(ident)
                if stage=='continuation' and meta.get('forecast_sha256')!=receipts[key]:raise ValueError('outcome_before_forecast_receipt')
                if report['status']!='complete_execution':raise ValueError('incomplete_journal')
                events=[(x['kind'],json.loads(x['payload_json'])) for x in report['events']]
                reserved={x['operation']:x['physical'] for kind,x in events if kind=='reserved'}
                settled=[x['operation'] for kind,x in events if kind=='settled' and x['outcome']=='success']
                if set(settled)!=set(reserved) or len(settled)!=len(reserved):raise ValueError('journal_settlement')
                stages.setdefault(stage,{k:0 for k in totals})
                for op in settled:
                    for k,value in reserved[op].items():totals[k]+=value;stages[stage][k]+=value
    if records!=6688 or totals!=p['resources']['completed']:raise ValueError('journal_count_replay')
    expected_stages=dict(probe=dict(real_steps=128,imagined_transitions=0,model_calls=0,network_forwards=0),
        forecast=dict(real_steps=0,imagined_transitions=763904,model_calls=30720,network_forwards=30720),
        common_tail=dict(real_steps=0,imagined_transitions=8192,model_calls=512,network_forwards=512),
        continuation=dict(real_steps=6144,imagined_transitions=9160704,model_calls=362496,network_forwards=362496))
    if stages!=expected_stages:raise ValueError('separate_stage_costs')
    elapsed=time.perf_counter()-start;ledger=p['session_ledger']
    output=dict(valid=True,capture_sha256=api.sha(api.RESULT),resource_records=records,stage_resources=stages,resources_verified=totals,
        new_real_steps=0,new_imagined_transitions=0,model_inference=False,wall_s=elapsed,
        session_ledger=dict(used_before_s=ledger['used_after_s'],used_after_s=ledger['used_after_s']+elapsed,remaining_after_s=ledger['remaining_after_s']-elapsed))
    with api.VALIDATION.open('x') as handle:json.dump(output,handle,indent=2);handle.write('\n')
    print(json.dumps(output));return 0
