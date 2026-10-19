"""E3.1: verify existing headroom evidence; cross-score recorded transitions.

No environment factory, training, planner execution or strategy search.
"""
import argparse
from dataclasses import asdict
import importlib.util
import itertools
import json
import math
import platform
import subprocess
import time

import numpy as np
import torch

from nexus.evolution1.resources import Work, Operation, Clock, Limits, ReservationLedger, model_work
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution1.fixtures import Event, verify_journal
from nexus.evolution2.generated_strategies import leaf, universe
from nexus.evolution2.fit_clock import LOCKED_ARRAYS
from nexus.evolution2 import full_policy_source as h

CONFIG=h.ROOT/'configs/e3_1_learned_model_audit.json'
PROTOCOL=h.ROOT/'docs/NEXUS_E3_1_CALIBRATION_PROTOCOL.md'
ALLOCATION=h.ROOT/'configs/e3_1_learned_model_allocation.json'
OUTPUT=h.ROOT/'artifacts/e3_1_learned_model_audit.json'
USAGE=h.ROOT/'artifacts/e3_1_learned_model_usage.json'
VALIDATION=h.ROOT/'artifacts/e3_1_learned_model_validation.json'
METRICS=('mae','rmse','cos_mae','sin_mae','angular_velocity_mae','mean_termination_probability',
         'max_termination_probability','termination_brier','false_positive_fraction','positive_terminations')


def config():
    c=json.loads(CONFIG.read_text())
    validate_config(c)
    return c


def validate_config(c):
    expected=dict(version='e3_1_recorded_audit_v1',candidate_models=[0,1],visitor_models=[0,1],
        visitor_policies=['successor_anchor','rank_blend'],episodes=[0,1,2,3],episode_steps=200,
        batch_size=256,time_cap_s=30,real_interaction_cap=0,neural_row_cap=6400,false_positive_threshold=.5)
    if json.dumps({k:v for k,v in c.items() if k!='evidence_sha256'},sort_keys=True)!=json.dumps(expected,sort_keys=True):raise ValueError('configuration')
    names={'artifacts/unified_headroom_audit.json','artifacts/unified_full_policy_source.json',
           'artifacts/unified_full_policy_replication.json','artifacts/unified_crossed_reset.json',
           'artifacts/unified_crossed_reset_validation.json'}
    if set(c['evidence_sha256'])!=names:raise ValueError('evidence_grid')


def recorded_rows(c,capture):
    h.validate_result(capture,capture['config'])
    rows=[];slices=[]
    for visitor,policy,episode in itertools.product(c['visitor_models'],c['visitor_policies'],c['episodes']):
        matches=[r for r in capture['episodes'] if (r['model_bundle'],r['controller'],r['episode'])==(visitor,policy,episode)]
        if len(matches)!=1:raise ValueError('visitor_grid')
        start=len(rows);rows.extend(matches[0]['steps'])
        slices.append(dict(visitor_model=visitor,visitor_policy=policy,episode=episode,start=start,stop=len(rows)))
    return rows,slices


def query_arrays(rows):
    return {k:np.asarray([r[k] for r in rows],dtype) for k,dtype in
            (('obs',np.float32),('action',np.int64),('next_obs',np.float32),('terminated',bool),('truncated',bool))}


def query_hash(arrays):
    import hashlib
    digest=hashlib.sha256()
    for k,v in sorted(arrays.items()):
        digest.update(k.encode());digest.update(str((v.shape,v.dtype)).encode());digest.update(v.tobytes())
    return digest.hexdigest()


def metrics(pred,prob,target,terminated):
    pred,prob,target,terminated=map(np.asarray,(pred,prob,target,terminated))
    if pred.shape!=target.shape or pred.ndim!=2 or pred.shape[1]!=3 or prob.shape!=(len(pred),):raise ValueError('prediction_shape')
    if terminated.shape!=(len(pred),) or terminated.dtype.kind!='b':raise ValueError('termination_target')
    if not all(np.isfinite(x).all() for x in (pred,prob,target)) or (prob<0).any() or (prob>1).any():raise ValueError('nonfinite_or_probability')
    d=np.asarray(pred,float)-target
    per=np.mean(np.abs(d),axis=0)
    return dict(mae=float(np.mean(np.abs(d))),rmse=float(np.sqrt(np.mean(d*d))),
        cos_mae=float(per[0]),sin_mae=float(per[1]),angular_velocity_mae=float(per[2]),
        mean_termination_probability=float(np.mean(prob)),max_termination_probability=float(np.max(prob)),
        termination_brier=float(np.mean((prob-terminated.astype(float))**2)),
        false_positive_fraction=float(np.mean((prob>=.5)&~terminated)),positive_terminations=int(np.sum(terminated)))


def metric_cells(c,rows,slices,predictions):
    if set(predictions)!=set(map(str,c['candidate_models'])):raise ValueError('prediction_model_grid')
    result=[]
    for b in c['candidate_models']:
        pred=np.asarray(predictions[str(b)]['next_obs']);prob=np.asarray(predictions[str(b)]['termination_probability'])
        if pred.shape!=(3200,3) or prob.shape!=(3200,):raise ValueError('missing_prediction_rows')
        for s in slices:
            a,z=s['start'],s['stop'];query=rows[a:z]
            result.append(dict(candidate_model=b,**s,**metrics(pred[a:z],prob[a:z],
                np.asarray([x['next_obs'] for x in query]),np.asarray([x['terminated'] for x in query]))))
    return result


def summarize(c,cells):
    expected=set(itertools.product(c['candidate_models'],c['visitor_models'],c['visitor_policies'],c['episodes']))
    ids=[(r['candidate_model'],r['visitor_model'],r['visitor_policy'],r['episode']) for r in cells]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('incomplete_metric_grid')
    for r in cells:
        if any(type(r[k]) is not int for k in ('candidate_model','visitor_model','episode','start','stop')):raise ValueError('cell_type')
        if r['stop']-r['start']!=200:raise ValueError('cell_length')
        index=(c['visitor_models'].index(r['visitor_model'])*8+c['visitor_policies'].index(r['visitor_policy'])*4+r['episode'])*200
        if r['start']!=index or r['stop']!=index+200:raise ValueError('query_slice_identity')
        for k in METRICS:
            if type(r[k]) not in (int,float) or not math.isfinite(r[k]):raise ValueError('required_metric')
    means={str(b):{k:float(np.mean([r[k] for r in cells if r['candidate_model']==b])) for k in METRICS} for b in c['candidate_models']}
    strata=[]
    for visitor,policy in itertools.product(c['visitor_models'],c['visitor_policies']):
        part=[r for r in cells if (r['visitor_model'],r['visitor_policy'])==(visitor,policy)]
        strata.append(dict(visitor_model=visitor,visitor_policy=policy,
            model0_minus_model1={k:float(np.mean([r[k] for r in part if r['candidate_model']==0])-
                                      np.mean([r[k] for r in part if r['candidate_model']==1])) for k in METRICS}))
    return dict(means=means,model0_minus_model1={k:means['0'][k]-means['1'][k] for k in METRICS},visitor_strata=strata,
                independent_models=2,causal_explanation_established=False,learning_to_learn_established=False)


def evidence(c):
    validate_config(c)
    captures={}
    for name,expected in c['evidence_sha256'].items():
        h.verify_file(h.ROOT/name,expected);captures[name]=json.loads((h.ROOT/name).read_text())
    old=captures['artifacts/unified_headroom_audit.json']
    spec=importlib.util.spec_from_file_location('existing_headroom',h.ROOT/'scripts/audit_unified_headroom.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if not old['declared_complete'] or module.summarize(old['rows'],old['config'])!=old['summary']:raise ValueError('historical_headroom')
    fingerprints={s.fingerprint for s in universe()}
    action_counts=[]
    for row in old['rows']:
        if set(row['strategies'])!=fingerprints:raise ValueError('historical_grammar_grid')
        values=row['strategies'];best=max(v['raw_proxy'] for v in values.values())
        anchor=max(values[leaf(a).fingerprint]['raw_proxy'] for a in ANCHORS)
        if not math.isclose(best,row['grammar_best_raw'],abs_tol=1e-12) or not math.isclose(anchor,row['anchor_best_raw'],abs_tol=1e-12):raise ValueError('headroom_maxima')
        by_action={}
        for v in values.values():
            by_action.setdefault(v['action'],[]).append(v['raw_proxy'])
        if any(max(v)-min(v)>1e-12 for v in by_action.values()):raise ValueError('neutral_probe_action_label')
        action_counts.append(len(by_action))
    controls={};cost=0
    for name,p in captures.items():
        if 'episodes' not in p:continue
        if not p['declared_complete']:raise ValueError('incomplete_historical_control')
        h.validate_result(p,p['config'])
        a=h.analyze(p['episodes'],p['config'])
        if a!=p['analysis']:raise ValueError('historical_arithmetic')
        h.verify_file(h.run_paths(p['config'])['journal'],p['resource_journal_sha256'])
        controls[name]=a;cost+=p['resources']['completed']['real_steps']
    for p in (old,*[x for x in captures.values() if 'episodes' in x]):
        for name,expected in p['code_sha256'].items():
            import hashlib
            raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=h.ROOT)
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('historical_code_provenance')
    manifest=json.loads((h.ROOT/'artifacts/evolution2_fit_clock_run.json').read_text())
    selected=[r for r in manifest['fits'] if r['bundle'] in (0,1)]
    h.verify_checkpoints(selected,dict(families=['pendulum','acrobot'],model_bundles=[0,1]))
    arrays=[r for r in LOCKED_ARRAYS if r['bundle'] in (0,1)]
    for row in arrays:h.verify_file(h.ROOT/row['path'],row['sha256'])
    official={(r['family'],r['bundle']):r for r in selected}
    for row in old['provenance']:
        if row['sha256']!=official[(row['family'],row['bundle'])]['sha256'] or row['state_before']!=row['state_after']:raise ValueError('headroom_checkpoint_provenance')
    if old['source_array_sha256']!={r['path']:r['sha256'] for r in arrays}:raise ValueError('headroom_source_provenance')
    for p in [x for x in captures.values() if 'episodes' in x]:
        h.verify_checkpoints(p['models'],p['config'])
        for m in p['models']:
            if m['sha256']!=official[(m['family'],m['bundle'])]['sha256'] or m['before']!=m['after']:raise ValueError('control_checkpoint_provenance')
    return dict(previous_headroom=old['summary'],strategy_count=342,action_labels_per_state=action_counts,
        full_policy_comparisons=controls,historical_control_steps_reused_not_new=cost,
        checkpoint_files=selected,source_arrays=arrays,fit_manifest_sha256=h.sha(h.ROOT/'artifacts/evolution2_fit_clock_run.json'))


def run(c):
    start,cpu=time.perf_counter(),time.process_time();deadline=start+c['time_cap_s']
    a=json.loads(ALLOCATION.read_text())
    if (a['config_sha256']!=h.sha(CONFIG) or a['protocol_sha256']!=h.sha(PROTOCOL) or a['real_interaction_cap']!=0
        or a['authorized'] is not True or a['time_cap_s']!=30 or a['neural_row_cap']!=6400 or a['runs']!=1):raise ValueError('allocation')
    if USAGE.exists() or OUTPUT.exists():raise FileExistsError('preserve_one_run')
    with USAGE.open('x') as out:json.dump(dict(consumed=True,allocation_sha256=h.sha(ALLOCATION),automatic_retry=False),out)
    old={str(p.relative_to(h.ROOT)):h.sha(p) for p in (h.ROOT/'artifacts').rglob('*.json') if p not in (OUTPUT,USAGE)}
    p=dict(declared_complete=False,config=c,evidence={},predictions={},metric_cells=[],models=[],historical_artifacts_sha256=old)
    ops=tuple(Operation(f'model_{b}_batch_{i}','model',model_work((min(256,3200-o),3),min(256,3200-o)))
              for b in c['candidate_models'] for i,o in enumerate(range(0,3200,256)))
    cap=Work(imagined_transitions=6400,model_calls=26,network_forwards=26)
    ledger=ReservationLedger(ops,Limits(cap,cap,int(30e9),int(30e9)))
    clock=lambda:Clock(int((time.process_time()-cpu)*1e9),int((time.perf_counter()-start)*1e9))
    try:
        used=json.loads((h.ROOT/'artifacts/unified_crossed_reset_validation.json').read_text())['session_ledger']['used_after_s']
        if used!=a['session_used_before_s'] or used+30>3600:raise ValueError('session_ledger')
        p['evidence']=evidence(c)
        capture=json.loads((h.ROOT/'artifacts/unified_crossed_reset.json').read_text())
        rows,slices=recorded_rows(c,capture)
        queries=query_arrays(rows);signature=query_hash(queries)
        p['query_sha256']=signature;obs,actions=queries['obs'],queries['action']
        parent={m['bundle']:m for m in capture['models']}
        for b in c['candidate_models']:
            if time.perf_counter()>=deadline:raise TimeoutError('audit_cap')
            model=h.disposable_model('pendulum',b)
            if str(model.device)!='cpu' or model.net.arch!='mlp' or model.kind!='residual' or tuple(model.net.hidden)!=(64,64):raise ValueError('frozen_cpu_model')
            for param in model.net.parameters():param.requires_grad_(False)
            before=h.state_hash(model)
            if before!=parent[b]['before']:raise ValueError('parent_fingerprint')
            preds=[];probs=[]
            for i,o in enumerate(range(0,3200,256)):
                if time.perf_counter()>=deadline:raise TimeoutError('audit_cap')
                ticket=ledger.reserve(f'model_{b}_batch_{i}',clock())
                try:
                    nxt,prob=model.step(obs[o:o+256],actions[o:o+256])
                    metrics(nxt,prob,np.zeros_like(nxt),np.zeros(len(nxt),bool))
                except BaseException:ledger.settle(ticket,'interrupted',clock());raise
                ledger.settle(ticket,'success',clock());preds.extend(nxt.tolist());probs.extend(prob.tolist())
            after=h.state_hash(model);h.verify_file(h.ROOT/parent[b]['path'],parent[b]['sha256'])
            if after!=before:raise ValueError('frozen_model_changed')
            if query_hash(queries)!=signature:raise ValueError('queries_mutated')
            p['models'].append(dict(**parent[b],audit_before=before,audit_after=after,query_sha256=signature))
            p['predictions'][str(b)]=dict(next_obs=preds,termination_probability=probs)
        p['metric_cells']=metric_cells(c,rows,slices,p['predictions']);p['summary']=summarize(c,p['metric_cells'])
        if any(h.sha(h.ROOT/n)!=s for n,s in old.items()):raise ValueError('history_changed')
        if time.perf_counter()>=deadline:raise TimeoutError('audit_cap')
        p['declared_complete']=True
    except Exception as exc:p['failure']=f'{type(exc).__name__}: {exc}'
    report=ledger.close(clock());p['resource_journal']=[asdict(x) for x in report.events]
    p['resources']=dict(status=report.status,completed=report.physical_completed_reported.payload(),
        unknown_upper=report.physical_unknown_upper_bound.payload(),real_steps=0,fits=0,
        wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu)
    if report.status!='complete_execution':p['declared_complete']=False
    used=a['session_used_before_s']+p['resources']['wall_s']
    p['session_ledger']=dict(used_before_s=a['session_used_before_s'],used_after_s=used,remaining_after_s=3600-used)
    return p


def verify_saved():
    if VALIDATION.exists():raise FileExistsError('preserve_validation')
    start=time.perf_counter();p=json.loads(OUTPUT.read_text());c=config()
    if not p['declared_complete'] or p['config']!=c:raise ValueError('incomplete_capture')
    rows,slices=recorded_rows(c,json.loads((h.ROOT/'artifacts/unified_crossed_reset.json').read_text()))
    if query_hash(query_arrays(rows))!=p['query_sha256']:raise ValueError('query_hash')
    cells=metric_cells(c,rows,slices,p['predictions'])
    if cells!=p['metric_cells'] or summarize(c,cells)!=p['summary']:raise ValueError('metric_reproduction')
    if evidence(c)!=p['evidence']:raise ValueError('evidence_reproduction')
    import hashlib
    for name,expected in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=h.ROOT)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('execution_code_hash')
    verify_journal(tuple(Event(**x) for x in p['resource_journal']))
    if (p['resources']['completed']!=Work(imagined_transitions=6400,model_calls=26,network_forwards=26).payload()
        or p['resources']['unknown_upper']!=Work().payload() or p['resources']['status']!='complete_execution'):raise ValueError('inference_accounting')
    if len(p['models'])!=2 or {m['bundle'] for m in p['models']}!={0,1}:raise ValueError('frozen_model_grid')
    for m in p['models']:
        h.verify_file(h.ROOT/m['path'],m['sha256'])
        if m['audit_before']!=m['audit_after'] or m['audit_before']!=m['before']:raise ValueError('frozen_state')
        if m['query_sha256']!=p['query_sha256']:raise ValueError('unpaired_queries')
    for n,s in p['historical_artifacts_sha256'].items():h.verify_file(h.ROOT/n,s)
    wall=time.perf_counter()-start;used=p['session_ledger']['used_after_s']+wall
    result=dict(valid=True,capture_sha256=h.sha(OUTPUT),metric_cells=32,neural_inference=0,new_real_steps=0,
        wall_s=wall,historical_json_preserved=len(p['historical_artifacts_sha256']),
        session_ledger=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used))
    with VALIDATION.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:print(json.dumps(verify_saved()));raise SystemExit(0)
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=h.ROOT,text=True).strip():raise RuntimeError('commit_protocol_first')
    names=['scripts/audit_e3_1_learned_model.py','tests/test_e3_1_learned_model_audit.py',str(CONFIG.relative_to(h.ROOT)),str(PROTOCOL.relative_to(h.ROOT)),str(ALLOCATION.relative_to(h.ROOT))]
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=h.ROOT,text=True).splitlines())
    if not set(names)<=tracked:raise RuntimeError('uncommitted_protocol')
    torch.set_num_threads(1);p=run(config())
    p.update(execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip(),
        code_sha256={n:h.sha(h.ROOT/n) for n in names},dependencies=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,cpu_threads=1))
    with OUTPUT.open('x') as out:json.dump(p,out,allow_nan=False);out.write('\n')
    print(json.dumps({k:p.get(k) for k in ('declared_complete','failure','summary','resources','session_ledger')}))
