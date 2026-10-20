"""Registered authored-history experiment; evaluator owns laws, labels and final data.

No historic task bank or checkpoint is opened. Source examples and validation
are separate arguments. Final episodes are generated only after all candidates
are frozen and their manifest is durably saved by the existing host worker.
"""
import copy
import hashlib
import math
from pathlib import Path
import random
import statistics as st
import sys
import time
from dataclasses import asdict
from nexus.evolution1.catalogue import digest
from nexus.seed.experimental import write_new
from .state import State, observe
from .features import evaluate, grammar
from .learning import Example, base, induce, fit_table, predict_table

METHODS = ['fixed', 'induced', 'all_history', 'replay', 'gru32']
KINDS = ['earlier', 'order', 'noise', 'unavailable']


def config_check(c):
    expected = dict(schema='seed_executable_world_v1', tasks={'train':list(range(971000, 971016))},
        kinds=KINDS, methods=METHODS, source_episodes=96, validation_episodes=48, final_episodes=96,
        gru_updates=200, gru_lr=.01, ridge=1., feature_margin=.02, complexity_penalty=.001,
        practical_brier_gain=.03, retention_tolerance=.01, max_wall_s=120,
        max_authored_steps=34560, max_outer_updates=3200, max_imagined_transitions=0,
        carried_used_s=1971.6321034559958, carried_remaining_s=1628.3678965440042)
    if any(digest(c.get(k)) != digest(v) for k,v in expected.items()): raise ValueError('locked_executable_world_recipe')
    return dict(real_steps=c['max_authored_steps'], imagined_transitions=0, outer_updates=c['max_outer_updates'])


def episode(seed, role, i, kind):
    """Known laws are evaluator-only. Public codes carry no dependency hint.

    A fresh random category binding per task; all methods receive the same codes
    and source outcomes, making their meaning identifiable through experience.
    """
    roles = {'source': 100000, 'validation': 200000, 'final': 300000}
    if role not in roles or kind not in KINDS: raise ValueError('registered_episode_role')
    rng = random.Random(seed*1000000+roles[role]+i)
    categories = list(range(4)); random.Random(seed+17).shuffle(categories)
    first, reset = categories[:2]
    hidden_events = [rng.randrange(4) for _ in range(rng.randint(2, 8))]
    if kind == 'order':
        a = [i for i,c in enumerate(hidden_events) if c == first]
        b = [i for i,c in enumerate(hidden_events) if c == reset]
        signal = bool(a and (not b or a[-1] > b[-1]))
    elif kind == 'unavailable': signal = bool(rng.randrange(2))
    else: signal = first in hidden_events
    action, flag = rng.randrange(2), bool(rng.randrange(2))
    outcome = signal ^ bool(action) ^ flag
    visible = [rng.randrange(4) if kind == 'noise' and rng.random() < .15 else c for c in hidden_events]
    raw = dict(entities=[dict(id='object',type='item',attributes=dict(flag=flag,ready=None))], relations=[],
               events=[dict(code=c, entity='object', time=j) for j,c in enumerate(visible)],
               time=len(visible), source='sensor')
    state = observe(State(episode=f'{role}-{seed}-{i}'), raw)
    return Example(state.episode, state, action, bool(outcome))


def wire(x):
    return dict(episode=x.episode, action=x.action, outcome=x.outcome,
                flag=x.state.current[0]['attributes']['flag'], codes=[e['code'] for e in x.state.events])


def vector(x):
    binding=x.state.current[0]['id']
    context=[float(x.action==a and base(x)[1] is f) for a in (0,1) for f in (False,True)]
    history=[float(evaluate(p,x.state,binding)) for p in grammar()]
    # Generic context/predicate interactions, same conditional expressiveness as
    # the induced table. A weak additive-only XOR baseline would be misleading.
    return context+[v*h for v in context for h in history]


def sequence(rows):
    import torch
    x = torch.zeros((len(rows), 9, 8))
    lengths = []
    for i, row in enumerate(rows):
        codes = [e['code'] for e in row.state.events]
        for j, code in enumerate(codes): x[i,j,code] = 1.
        x[i,len(codes),4] = 1.; x[i,len(codes),5] = row.action
        x[i,len(codes),6] = float(base(row)[1]); x[i,len(codes),7] = 1.
        lengths.append(len(codes))
    return x, torch.tensor(lengths)


def fit_recurrent(rows, seed, c, check, work=None):
    import torch
    from torch import nn
    # Same GRU32 approach, NEW source-trained weights, not the incompatible frozen
    # multimodal sensor adapter. h and optimizer reset per independent task.
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        model = nn.ModuleDict(dict(gru=nn.GRU(8,32,batch_first=True),head=nn.Linear(32,1)))
    x, last = sequence(rows); y = torch.tensor([float(r.outcome) for r in rows])
    opt = torch.optim.Adam(model.parameters(),lr=c['gru_lr']); losses=[]
    for step in range(c['gru_updates']):
        check(); opt.zero_grad(); h,_ = model['gru'](x)
        logits=model['head'](h[torch.arange(len(rows)),last]).squeeze(-1)
        loss=nn.functional.binary_cross_entropy_with_logits(logits,y)
        if not torch.isfinite(loss): raise ValueError('nonfinite_recurrent_no_retry')
        loss.backward(); opt.step()
        if work is not None:
            work['updates']+=1;work['training_examples']+=len(rows)
        if step in (0,49,99,199): losses.append(dict(update=step+1,loss=float(loss.detach())))
    model.eval()
    return model, losses


def fit_methods(train, validation, seed, c, check, work=None):
    from nexus.nn.ridge import fit_ridge
    timing={};start=time.perf_counter()
    change=induce(train,validation,margin=c['feature_margin'],penalty=c['complexity_penalty'],retained=train[:16])
    timing['induction_and_validation']=time.perf_counter()-start;start=time.perf_counter()
    features=[change['feature']] if change['accepted'] else []
    models=dict(fixed=fit_table(train,[]),induced=fit_table(train,features))
    timing['empirical_tables']=time.perf_counter()-start;start=time.perf_counter()
    # All permitted history predicates; no feature search or validation selection.
    models['all_history']=fit_ridge([vector(x) for x in train],[float(x.outcome) for x in train],ridge=c['ridge'])
    timing['all_history_ridge']=time.perf_counter()-start;start=time.perf_counter()
    replay={}
    for x in train: replay.setdefault((base(x),tuple(e['code'] for e in x.state.events)),[]).append(float(x.outcome))
    models['replay']=replay
    timing['replay']=time.perf_counter()-start;start=time.perf_counter()
    models['gru32'], losses=fit_recurrent(train,seed,c,check,work)
    timing['gru32']=time.perf_counter()-start
    return models,features,change,losses,timing


def predictions(models, features, rows):
    import torch
    from nexus.nn.ridge import predict_ridge
    out={m:[] for m in METHODS}
    for x in rows:
        out['fixed'].append(predict_table(models['fixed'],x,[]))
        out['induced'].append(predict_table(models['induced'],x,features))
        out['all_history'].append(max(0.,min(1.,predict_ridge(models['all_history'],vector(x)))))
        replay=models['replay'].get((base(x),tuple(e['code'] for e in x.state.events)))
        out['replay'].append(st.mean(replay) if replay else predict_table(models['fixed'],x,[]))
    with torch.no_grad():
        xx,last=sequence(rows); h,_=models['gru32']['gru'](xx)
        out['gru32']=torch.sigmoid(models['gru32']['head'](h[torch.arange(len(rows)),last]).squeeze(-1)).tolist()
    return out


def fitted_wire(models):
    return dict(fixed=[dict(key=list(k),probability=v) for k,v in models['fixed'].items()],
        induced=[dict(key=list(k),probability=v) for k,v in models['induced'].items()],
        all_history=dict(scale=models['all_history'][0].tolist(),beta=models['all_history'][1].tolist()),
        replay=[dict(base=list(k[0]),codes=list(k[1]),outcomes=v) for k,v in models['replay'].items()])


def summary(rows,c):
    by_kind={}
    for kind in KINDS:
        group=[r for r in rows if r['kind']==kind]
        by_kind[kind]={m:st.mean(r['metrics'][m]['brier'] for r in group) for m in METHODS}
    primary=[r for r in rows if r['kind'] in ('earlier','order')]
    deltas=[r['metrics']['fixed']['brier']-r['metrics']['induced']['brier'] for r in primary]
    mean=st.mean(deltas); half=2.364624251*st.stdev(deltas)/math.sqrt(8)
    retention=max(r['change'].get('forgetting',0.) for r in rows)
    passed=mean>=c['practical_brier_gain'] and mean-half>0 and retention<=c['retention_tolerance']
    return dict(label='source_feature_screen_passed' if passed else 'source_feature_screen_failed',
        primary={m:st.mean(r['metrics'][m]['brier'] for r in primary) for m in METHODS},
        fixed_minus_induced=dict(mean=mean,ci95=[mean-half,mean+half],task_values=deltas,
                                unit='eight_authored_dependency_tasks',exploratory=True),
        by_kind=by_kind,max_retention_excess=retention,accepted=sum(r['change']['accepted'] for r in rows),
        unavailable_information_limit=dict(expected_best_accuracy=.5,minimum_expected_brier=.25,
            reason='Independent fair hidden bit; finite samples may exceed chance.'),
        transfer_evaluated=False,investigation_transfer_evaluated=False,promoted=False)


def _run(request):
    import torch
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    c=request['inputs']['study_config'];config_check(c)
    directory=Path.cwd()
    start=time.monotonic(); resources=dict(real_steps=0,imagined_transitions=0,updates=0,
        training_examples=0,search_candidates=0,assessment_examples=0)
    result=dict(schema=c['schema'],declared_complete=False,config=c,rows=[],analysis=None)
    def check():
        if time.monotonic()-start>=c['max_wall_s']-3: raise TimeoutError('registered_cap_no_retry')
    frozen=[]; frozen_manifest=[]
    def collect(seed,role,n,kind):
        values=[]
        for i in range(n):
            check();x=episode(seed,role,i,kind);resources['real_steps']+=len(x.state.events)+1
            if resources['real_steps']>c['max_authored_steps']:raise ValueError('interaction_cap')
            values.append(x)
        return values
    try:
        # All fitting/acceptance and checkpoint recording precede final generation.
        for j,seed in enumerate(c['tasks']['train']):
            check();kind=KINDS[j//4]
            train=collect(seed,'source',c['source_episodes'],kind)
            validation=collect(seed,'validation',c['validation_episodes'],kind)
            models,features,change,losses,timing=fit_methods(train,validation,seed,c,check,resources)
            checkpoint={k:v.detach().tolist() for k,v in models['gru32'].state_dict().items()}
            frozen_manifest.append(dict(task=seed,feature=features,change_sha256=digest(change),fitted_sha256=digest(fitted_wire(models)),
                source_sha256=digest([wire(x) for x in train]),validation_sha256=digest([wire(x) for x in validation]),
                gru_sha256=digest(checkpoint)))
            frozen.append((seed,kind,train,validation,models,features,change,losses,timing,checkpoint))
            resources['search_candidates']+=change['candidates_evaluated']
            write_partial(directory/'preparation.json',dict(models=frozen_manifest,
                checkpoints=[dict(seed=f[0],state=f[-1]) for f in frozen],resources=resources,declared_complete=False))
        write_new(directory/'frozen_manifest.json',dict(config_sha256=digest(c),models=frozen_manifest))
        result['frozen_manifest']=frozen_manifest
        result['frozen_manifest_sha256']=digest(frozen_manifest)
        result['frozen_before_final']=True
        for seed,kind,train,validation,models,features,change,losses,timing,checkpoint in frozen:
            check();final=collect(seed,'final',c['final_episodes'],kind)
            before=digest({k:v.detach().tolist() for k,v in models['gru32'].state_dict().items()})
            prediction_start=time.perf_counter();pred=predictions(models,features,final)
            timing['all_method_prediction']=time.perf_counter()-prediction_start
            if before!=digest({k:v.detach().tolist() for k,v in models['gru32'].state_dict().items()}):raise ValueError('evaluation_changed_weights')
            metrics={m:dict(brier=st.mean((p-float(x.outcome))**2 for p,x in zip(pred[m],final)),
                accuracy=st.mean((p>=.5)==x.outcome for p,x in zip(pred[m],final))) for m in METHODS}
            result['rows'].append(dict(seed=seed,kind=kind,feature=features,change=change,metrics=metrics,fitted=fitted_wire(models),
                data={role:[wire(x) for x in data] for role,data in [('source',train),('validation',validation),('final',final)]},
                predictions=pred,gru_checkpoint=checkpoint,gru_curve=losses,
                timings_s=timing,parameter_counts=dict(fixed=len(models['fixed']),induced=len(models['induced']),
                    all_history=364,replay_label_slots=len(train),gru32=sum(p.numel() for p in models['gru32'].parameters())),
                gru_parameter_count=sum(p.numel() for p in models['gru32'].parameters())))
            resources['assessment_examples']+=len(final)*len(METHODS)
            write_partial(directory/'progress.json',result)
        result['declared_complete']=True;result['analysis']=summary(result['rows'],c)
    except Exception as exc:
        result['failure']=dict(type=type(exc).__name__,message=str(exc));result['partial_resources']=resources;write_partial(directory/'progress.json',result)
        raise
    resources['cpu_s']=time.process_time();resources['worker_wall_s']=time.monotonic()-start
    resources['network_forwards']=len(c['tasks']['train'])*(c['gru_updates']+1)
    resources['history_ridge_feature_width']=364
    resources['history_ridge_fits']=16
    return dict(adapter=c['schema'],study=result,resources=resources,
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def run(request):
    from .features import WORK
    counter={};token=WORK.set(counter)
    try:
        out=_run(request);out['resources'].update(counter);return out
    finally:WORK.reset(token)


def write_partial(path,result):
    # Existing worker progress channel, private and explicitly incomplete until valid.
    import json
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result,allow_nan=False));temp.replace(path)


def validate_output(output,c,caps):
    config_check(c);r=output['study']
    if r.get('declared_complete') is not True or digest(r.get('config'))!=digest(c):raise ValueError('incomplete_study')
    rows=r['rows']
    if len(rows)!=16 or [r['seed'] for r in rows]!=c['tasks']['train']:raise ValueError('complete_task_grid')
    if r.get('frozen_before_final') is not True:raise ValueError('final_before_freeze')
    manifest=r.get('frozen_manifest')
    if type(manifest) is not list or len(manifest)!=16 or [x['task'] for x in manifest]!=c['tasks']['train'] or digest(manifest)!=r.get('frozen_manifest_sha256'):raise ValueError('frozen_manifest_grid')
    for j,row in enumerate(rows):
        if row['kind']!=KINDS[j//4] or set(row['metrics'])!=set(METHODS) or set(row['predictions'])!=set(METHODS):raise ValueError('complete_method_grid')
        episode_sets=[]
        for role,n in [('source',96),('validation',48),('final',96)]:
            data=row['data'][role]
            expected=[f'{role}-{row["seed"]}-{i}' for i in range(n)]
            if len(data)!=n or [x['episode'] for x in data]!=expected:raise ValueError('complete_episode_grid')
            episode_sets.append(set(expected))
            for x in data:
                if set(x)!={'episode','action','outcome','flag','codes'} or type(x['action']) is not int or x['action'] not in (0,1) or type(x['outcome']) is not bool or type(x['flag']) is not bool or type(x['codes']) is not list or not 2<=len(x['codes'])<=8 or any(type(v) is not int or not 0<=v<4 for v in x['codes']):raise ValueError('raw_episode_schema')
        if any(episode_sets[a]&episode_sets[b] for a in range(3) for b in range(a)):raise ValueError('data_leakage')
        for method in METHODS:
            p=row['predictions'][method]
            if len(p)!=96 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p):raise ValueError('finite_complete_predictions')
            metrics=row['metrics'][method]
            if set(metrics)!={'brier','accuracy'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in metrics.values()):raise ValueError('finite_metrics')
            errors=[(v-float(x['outcome']))**2 for v,x in zip(p,row['data']['final'])]
            if abs(st.mean(errors)-metrics['brier'])>1e-12:raise ValueError('brier_arithmetic')
            if abs(st.mean((v>=.5)==x['outcome'] for v,x in zip(p,row['data']['final']))-metrics['accuracy'])>1e-12:raise ValueError('accuracy_arithmetic')
        frozen=manifest[j]
        if (digest(row['gru_checkpoint'])!=frozen['gru_sha256'] or digest(row['fitted'])!=frozen['fitted_sha256'] or
            digest(row['change'])!=frozen['change_sha256'] or row['feature']!=frozen['feature'] or
            digest(row['data']['source'])!=frozen['source_sha256'] or digest(row['data']['validation'])!=frozen['validation_sha256']):raise ValueError('changed_frozen_candidate')
        if not row['gru_checkpoint']:raise ValueError('missing_checkpoint')
        def finite_tree(value):
            if type(value) is list:return bool(value) and all(finite_tree(v) for v in value)
            return type(value) in (int,float) and math.isfinite(value)
        if any(not finite_tree(v) for v in row['gru_checkpoint'].values()):raise ValueError('nonfinite_checkpoint')
        shapes={'gru.weight_ih_l0':(96,8),'gru.weight_hh_l0':(96,32),
                'gru.bias_ih_l0':(96,), 'gru.bias_hh_l0':(96,), 'head.weight':(1,32),'head.bias':(1,)}
        checkpoint=row['gru_checkpoint']
        if set(checkpoint)!=set(shapes):raise ValueError('complete_checkpoint_parameters')
        for name,shape in shapes.items():
            values=checkpoint[name]
            if len(values)!=shape[0] or (len(shape)==2 and any(type(v) is not list or len(v)!=shape[1] for v in values)):raise ValueError('checkpoint_shape')
        if set(row['fitted'])!={'fixed','induced','all_history','replay'} or set(row['fitted']['all_history'])!={'scale','beta'} or any(len(row['fitted']['all_history'][k])!=364 for k in ('scale','beta')):raise ValueError('complete_fitted_parameters')
    if digest(summary(rows,c))!=digest(r['analysis']):raise ValueError('aggregation_mismatch')
    work=output['resources']
    for name in ('real_steps','imagined_transitions','updates'):
        if type(work[name]) is not int or not 0<=work[name]<=caps[name]:raise ValueError('execution_budget')
    observed=sum(len(x['codes'])+1 for row in rows for data in row['data'].values() for x in data)
    if work['real_steps']!=observed or work['updates']!=3200 or work['imagined_transitions']!=0:raise ValueError('resource_arithmetic')


def saved_replay(root):
    import json
    root=Path(root);r=json.loads((root/'artifacts/seed_executable_world.json').read_text())
    c=r['config'];caps=dict(real_steps=c['max_authored_steps'],updates=c['max_outer_updates'],imagined_transitions=0)
    validate_output(dict(study=r,resources=r['resources']),c,caps)
    return dict(id='seed-executable-world-1',mode='exploration',status='complete_development',
        wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],
        revision=r['execution_sha'],resources=r['resources'],curve=[],executable_world=r['analysis'])
