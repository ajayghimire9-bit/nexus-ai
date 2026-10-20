"""Fresh source queries for FIXED question-counterfactual states.

Reuse nonlinear_learning's authored collector/feature path, question_headroom's
saved states, paired task intervals and the existing EXPERIMENTAL host. No inner
fitting, new learner, neural training or runtime question policy is introduced.
"""
import copy
import hashlib
import json
from pathlib import Path
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite, audit_episode
from . import question_headroom as headroom
from .update_diagnosis import paired

ROLES=('selection','check')
METHODS=('selected','variance','uniform','keep','check_oracle')


def config_check(c):
    tasks=list(range(95000000,95110001,10000))
    expected=dict(schema='seed_query_replication_v1',tasks={'train':tasks},
        constant_seeds=[7201,7202,7203],budgets=[1,2,4,8],starts_per_role=12,
        actions=list(range(9)),feature_width=33,minimum_fraction=.05,
        minimum_task_wins=8,retention_excess=.01,max_wall_s=60,
        max_authored_steps=2592,max_imagined_transitions=2592,
        max_posterior_rows=288,max_outer_updates=0,
        query_seeds={str(t):{r:[98200000+i*1000+o+j for j in range(12)]
            for r,o in [('selection',100),('check',200)]} for i,t in enumerate(tasks)})
    if any(digest(c.get(k))!=digest(v) for k,v in expected.items()):raise ValueError('locked_query_replication_recipe')
    if any(not finite(c[k]) or c[k]<0 for k in ('carried_used_s','carried_remaining_s')) or c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:
        raise ValueError('query_replication_carried_budget')
    return dict(real_steps=2592,imagined_transitions=2592,outer_updates=0)


def checkpoint_parameter_count(root,c):
    """Derive accounting from hash-verified weight arrays, not a magic total."""
    def count(v):
        if type(v) is list:return sum(count(x) for x in v)
        if not finite(v):raise ValueError('checkpoint_numeric_weights')
        return 1
    sizes={}
    for key in ('parent_model','parent_readout'):
        raw=(Path(root)/c[key]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=c[key+'_sha256']:raise ValueError('query_parameter_checkpoint_hash')
        sizes[key]=sum(count(v) for v in json.loads(raw)['weights'].values())
    return sizes


def historical_seeds(value):
    """Conservative identifier inventory, never reads scores to choose seeds."""
    found=set()
    def nums(v):
        if type(v) is int:found.add(v)
        elif type(v) is list:
            for x in v:nums(x)
        elif type(v) is dict:
            for x in v.values():nums(x)
    def walk(v):
        if type(v) is dict:
            for k,x in v.items():
                if 'seed' in k.lower():nums(x)
                walk(x)
        elif type(v) is list:
            for x in v:walk(x)
    walk(value);return found


def historical_identities(value):
    found=set()
    def walk(v,goal=None):
        if type(v) is dict:
            g=v.get('goal',goal);obj=v.get('before')
            if type(obj) is dict and g is not None and all(k in obj for k in ('x','y','color','shape','size')):
                found.add(tuple(obj[k] for k in ('x','y','color','shape','size'))+tuple(g))
            for x in v.values():walk(x,g)
        elif type(v) is list:
            for x in v:walk(x,goal)
    walk(value);return found


def source_pack(root,c):
    """Read-only preflight; no neural/world imports or scientific execution."""
    config_check(c);root=Path(root);seeds=set();closed=set()
    for name,sha in c['seed_inventory'].items():
        raw=(root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('query_history_hash: '+name)
        value=json.loads(raw);seeds.update(historical_seeds(value))
        states=historical_identities(value)
        if bool(states)!=(name in c['closed_artifacts']) or name in c['closed_artifacts'] and sha!=c['closed_artifacts'][name]:raise ValueError('query_closed_state_coverage')
        closed.update(states)
    if digest(sorted(seeds))!=c['historical_seed_sha256']:raise ValueError('historical_seed_inventory')
    registered={s for roles in c['query_seeds'].values() for values in roles.values() for s in values}
    if len(registered)!=288 or registered & seeds:raise ValueError('closed_query_seed_reuse')
    for key in ('parent','parent_model','parent_readout'):
        if hashlib.sha256((root/c[key]).read_bytes()).hexdigest()!=c[key+'_sha256']:raise ValueError('query_parent_hash: '+key)
    parent=json.loads((root/c['parent']).read_text());old=headroom.source_pack(root,parent['config'])
    headroom.validate(parent,parent['config'],old)
    if parent['declared_complete'] is not True or c['carried_used_s']!=parent['session_used_s'] or c['carried_remaining_s']!=parent['session_remaining_s']:
        raise ValueError('query_parent_completion_or_ledger')
    # Pass only fixed fits, normalization, source goals and cached retention.
    raw=json.loads((root/parent['config']['source_data']).read_text())
    return dict(parent_sha256=c['parent_sha256'],rows=parent['rows'],
        frozen_folds=old['questions']['source']['frozen_folds'],
        goals={str(t['seed']):t['goal'] for t in raw['tasks']['train']},
        history_sha256=digest(c['seed_inventory']),closed_initials=[list(v) for v in sorted(closed)])


def select_candidates(selection_rows,c):
    """Only selection-subset errors can enter this evaluator decision."""
    if set(selection_rows)!=set(map(str,c['tasks']['train'])):raise ValueError('selection_task_grid')
    choices={}
    for t,cells in selection_rows.items():
        if set(cells)!=set(map(str,c['budgets'])):raise ValueError('selection_budget_grid')
        choices[t]={}
        for b,cell in cells.items():
            if set(cell)!={'variance_index','before','candidates'} or len(cell['candidates'])!=9-int(b) or any(not i.isdecimal() or not 0<=int(i)<8 for i in cell['candidates']):raise ValueError('selection_candidate_grid')
            for arms in [cell['before']]+list(cell['candidates'].values()):
                if set(arms)!=set(map(str,c['constant_seeds'])):raise ValueError('selection_fit_seed_grid')
                for row in arms.values():
                    blocks=row.get('selection_blocks');metric=row.get('selection_mse')
                    if set(row)!={'selection_mse','selection_blocks'} or type(blocks) is not list or len(blocks)!=12 or any(not finite(v) or v<0 for v in blocks) or not finite(metric) or abs(metric-st.mean(blocks))>2e-6:raise ValueError('selection_metric_grid')
            errors={i:st.mean(row['selection_mse'] for row in arms.values()) for i,arms in cell['candidates'].items()}
            choices[t][b]=int(min(sorted(errors,key=int),key=lambda i:errors[i]))
    return choices


def selection_manifest(rows,queries,c,pack):
    return dict(schema='seed_query_selection_lock_v1',complete=True,config_sha256=digest(c),
        parent_sha256=pack['parent_sha256'],selection_data_sha256=digest({t:q['selection'] for t,q in queries.items()}),
        selection_metrics_sha256=digest(rows),choices=select_candidates(rows,c))


def require_selection(path,expected):
    if not Path(path).is_file() or json.loads(Path(path).read_text())!=expected or expected.get('complete') is not True:
        raise ValueError('saved_complete_selection_required_before_check')


def collect_queries(model,head,seeds,goal,meter,used):
    """Original frozen feature path, all nine actions from each identical start."""
    import torch
    from . import nonlinear_learning as nl
    records=[];xs=[];ys=[]
    for index,seed in enumerate(seeds):
        w=nl.fresh_world(seed,goal,index,used);before=dict(w.obj)
        x,base,_=nl.score_basis(model,head,w,meter)
        row=dict(seed=seed,before=before,goal=list(goal),base=base.tolist(),
            proprio=w.observe()['proprio'].tolist(),outcomes=[])
        for action in range(9):
            other=copy.deepcopy(w);meter.charge('collection');obs,reward,done,_=other.step(action)
            row['outcomes'].append(dict(action=action,reward=reward,done=done,truncated=False,
                after=dict(other.obj),next_proprio=obs['proprio'].tolist()))
            xs.append(x[action]);ys.append(reward-float(base[action]))
        if w.obj!=before or w.steps!=0 or w.flags!=[0,0,0]:raise ValueError('query_clone_changed_origin')
        records.append(row)
    arrays=dict(x=torch.stack(xs).tolist(),y=torch.tensor(ys).tolist())
    return dict(records=records,arrays=arrays,record_sha256=digest(records),array_sha256=digest(arrays),
        dtype='float32',shapes={'x':[108,33],'y':[108]})


def score_snapshots(fixed,query,scale,role,cell=None):
    """Assess cached fits only. No query tensor enters a fit or normalization."""
    import torch
    x=torch.tensor(query['arrays']['x'],dtype=torch.float32)/torch.tensor(scale,dtype=torch.float32);y=torch.tensor(query['arrays']['y'],dtype=torch.float32)
    out=cell if cell is not None else dict(variance_index=fixed['variance_index'],before={},candidates={})
    for key,arms in [('keep',fixed['before'])]+list(fixed['candidates'].items()):
        dest=out['before'] if key=='keep' else out['candidates'].setdefault(key,{})
        for seed,row in arms.items():
            errors=(x@torch.tensor(row['theta'],dtype=torch.float32)-y).square().reshape(12,9).mean(1).tolist()
            dest.setdefault(seed,{})[role+'_blocks']=errors;dest[seed][role+'_mse']=st.mean(errors)
    return out


def summarize(rows,choices,c,pack):
    cells={};per={};ret={m:[] for m in METHODS};selection_means=[]
    for t in c['tasks']['train']:
        tid=str(t);cells[tid]={}
        for b in c['budgets']:
            cell=rows[tid][str(b)];old=pack['rows'][tid][str(b)];arms=cell['candidates']
            avg=lambda i,metric:st.mean(v[metric] for v in arms[i].values())
            chosen=str(choices[tid][str(b)]);var=str(cell['variance_index'])
            oracle=min(sorted(arms,key=int),key=lambda i:avg(i,'check_mse'))
            q={m:avg(i,'check_mse') for m,i in [('selected',chosen),('variance',var),('check_oracle',oracle)]}
            q.update(uniform=st.mean(avg(i,'check_mse') for i in arms),keep=st.mean(v['check_mse'] for v in cell['before'].values()))
            r={m:st.mean(v['retention_mse'] for v in old['candidates'][i].values()) for m,i in [('selected',chosen),('variance',var),('check_oracle',oracle)]}
            r.update(uniform=st.mean(v['retention_mse'] for a in old['candidates'].values() for v in a.values()),keep=st.mean(v['retention_mse'] for v in old['before'].values()))
            cells[tid][str(b)]=dict(check=q,retention=r,selected_index=int(chosen),check_oracle_index=int(oracle),
                selection_mse=avg(chosen,'selection_mse'),selection_variance_mse=avg(var,'selection_mse'),
                candidate_check_mse={i:avg(i,'check_mse') for i in arms})
            selection_means.append(avg(chosen,'selection_mse'))
        per[tid]={m:st.mean(cells[tid][str(b)]['check'][m] for b in c['budgets']) for m in METHODS}
        for m in METHODS:ret[m].append(st.mean(cells[tid][str(b)]['retention'][m] for b in c['budgets']))
    means={m:st.mean(v[m] for v in per.values()) for m in METHODS};retmean={m:st.mean(v) for m,v in ret.items()}
    contrasts={m:paired([v[m]-v['selected'] for v in per.values()]) for m in ('variance','uniform','keep')}
    wins=sum(v['selected']<v['keep'] for v in per.values());retention=retmean['selected']<=retmean['variance']+c['retention_excess']
    practical=all(means['selected']<=(1-c['minimum_fraction'])*means[m] for m in ('variance','uniform','keep'))
    intervals=all(contrasts[m]['ci95'][0]>0 for m in ('variance','keep'))
    passed=practical and intervals and wins>=c['minimum_task_wins'] and retention
    return dict(label='question_utility_stability_replicated' if passed else 'question_utility_stability_not_demonstrated',
        screen_passed=passed,practical_pass=practical,interval_pass=intervals,retention_pass=retention,
        task_wins=wins,check_means=means,retention_means=retmean,contrasts=contrasts,per_task=per,cells=cells,
        selection_winner_mse=st.mean(selection_means),
        check_curves={m:{str(b):st.mean(cells[str(t)][str(b)]['check'][m] for t in c['tasks']['train']) for b in c['budgets']} for m in METHODS},
        uncertainty='Exploratory paired df11 task-cluster intervals, one core and reused source tasks/fits; no multiplicity adjustment. All gates required, no individual contrast establishes confirmation.',
        independent_pretrained_cores=1,deployable_question_policy=False,learning_to_learn_established=False,runtime_promotion=False)


def validate(r,c,pack):
    """Stdlib exact-grid and raw-metric replay, before any aggregate is trusted."""
    config_check(c);tids=set(map(str,c['tasks']['train']));seeds=set(map(str,c['constant_seeds']))
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or set(r['queries'])!=tids or set(r['rows'])!=tids:raise ValueError('query_replication_task_grid')
    if r['frozen_before']!=r['frozen_after'] or r['fixed_before_sha256']!=digest(pack) or r['fixed_after_sha256']!=digest(pack):raise ValueError('query_frozen_state_changed')
    for name,key in [('core','parent_model'),('readout','parent_readout')]:
        if r['frozen_before'][name]!=c[key+'_sha256']:raise ValueError('query_checkpoint_provenance')
    scales={str(t):f['scale'] for f in pack['frozen_folds'].values() for t in f['excluded_ids']}
    if r['closed_initials']!=pack['closed_initials']:raise ValueError('query_closed_identity_inventory')
    identities=set(map(tuple,r['closed_initials']));new_seeds=[]
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<=2e-6
    for t in sorted(tids):
        if set(r['queries'][t])!=set(ROLES) or set(r['rows'][t])!=set(map(str,c['budgets'])):raise ValueError('query_replication_role_budget_grid')
        for role in ROLES:
            q=r['queries'][t][role];a=q['arrays'];records=q['records']
            if q['dtype']!='float32' or q['shapes']!={'x':[108,33],'y':[108]} or set(a)!={'x','y'} or digest(a)!=q['array_sha256'] or digest(records)!=q['record_sha256']:raise ValueError('query_array_provenance')
            if len(a['x'])!=108 or len(a['y'])!=108 or any(len(x)!=33 or any(not finite(v) for v in x) for x in a['x']) or any(not finite(v) for v in a['y']):raise ValueError('query_finite_shape_grid')
            if [v['seed'] for v in records]!=c['query_seeds'][t][role]:raise ValueError('query_collection_seed_grid')
            for j,row in enumerate(records):
                obj=row['before'];ident=tuple(obj[k] for k in ('x','y','color','shape','size'))+tuple(row['goal'])
                if ident in identities or row['goal']!=pack['goals'][t]:raise ValueError('closed_or_duplicate_query_state')
                identities.add(ident);new_seeds.append(row['seed'])
                if len(row['base'])!=9 or any(not finite(v) for v in row['base']) or [v['action'] for v in row['outcomes']]!=list(range(9)):raise ValueError('query_action_grid')
                for i,o in enumerate(row['outcomes']):
                    audit_episode({'steps':[dict(o,before=obj,goal=row['goal'])]},1,information_reward=False)
                    if o['truncated'] is not False or not close(a['y'][j*9+i],o['reward']-row['base'][i]):raise ValueError('query_residual_label')
        for b in c['budgets']:
            cell=r['rows'][t][str(b)];fixed=pack['rows'][t][str(b)]
            if set(cell)!={'variance_index','before','candidates'} or type(cell['variance_index']) is not int or cell['variance_index']!=fixed['variance_index'] or set(cell['candidates'])!=set(fixed['candidates']):raise ValueError('query_candidate_grid')
            for key,arms in [('keep',cell['before'])]+list(cell['candidates'].items()):
                if set(arms)!=seeds:raise ValueError('query_fit_seed_grid')
                saved=fixed['before'] if key=='keep' else fixed['candidates'][key]
                for seed,row in arms.items():
                    if set(row)!={role+suffix for role in ROLES for suffix in ('_mse','_blocks')}:raise ValueError('query_metric_grid')
                    for role in ROLES:
                        a=r['queries'][t][role]['arrays'];theta=saved[seed]['theta'];scale=scales[t]
                        errors=[(sum(v/s*w for v,s,w in zip(x,scale,theta))-y)**2 for x,y in zip(a['x'],a['y'])]
                        expected=[st.mean(errors[j:j+9]) for j in range(0,108,9)]
                        actual=row[role+'_blocks']
                        if type(actual) is not list or len(actual)!=12 or any(not close(v,e) or v<0 for v,e in zip(actual,expected)) or not close(row[role+'_mse'],st.mean(actual)) or row[role+'_mse']<0:raise ValueError('query_metric_arithmetic')
    if len(new_seeds)!=288 or len(set(new_seeds))!=288:raise ValueError('query_seed_separation')
    selection_rows=copy.deepcopy(r['rows'])
    for cells in selection_rows.values():
        for cell in cells.values():
            for arms in [cell['before']]+list(cell['candidates'].values()):
                for row in arms.values():
                    for k in ('check_mse','check_blocks'):del row[k]
    manifest=selection_manifest(selection_rows,r['queries'],c,pack)
    if digest(r['selection_manifest'])!=digest(manifest) or r['selection_manifest_sha256']!=digest(manifest) or r['selection_locked_before_check'] is not True:raise ValueError('query_selection_manifest')
    if digest(r['analysis'])!=digest(summarize(r['rows'],manifest['choices'],c,pack)):raise ValueError('query_summary_arithmetic')
    expected_work=dict(collection=2592,control=0)
    if r['costs']!=expected_work or r['imagined_transitions']!=2592 or r['posterior_rows']!=288:raise ValueError('query_resource_accounting')
    return True


def run(request):
    import torch
    from . import nonlinear_learning as nl
    from .action_readout import ActionReadout
    from nexus.world.seed_rssm import SeedRSSM
    c=request['inputs']['study_config'];pack=request['inputs']['source_pack'];root=Path(request['inputs']['repository'])
    config_check(c);torch.set_num_threads(1);torch.use_deterministic_algorithms(True);meter=nl.Meter(c);nl.lb.WORK.clear()
    core,_=SeedRSSM.load(root/c['parent_model'],c['parent_model_sha256'])
    head=ActionReadout.load(root/c['parent_readout'],c['parent_readout_sha256'],c['parent_model_sha256'])
    fingerprint=lambda:digest(dict(core={k:v.tolist() for k,v in core.state_dict().items()},readout={k:v.tolist() for k,v in head.state_dict().items()},bank=core.world_memory_bank.tolist()))
    before=fingerprint();fixed=digest(pack)
    used,hashes=nl.historical_initials(root,c['closed_artifacts'])
    if hashes!=c['closed_artifacts']:raise ValueError('query_closed_initial_provenance')
    r=dict(config=c,source_pack_sha256=fixed,fixed_before_sha256=fixed,declared_complete=False,
        queries={str(t):{} for t in c['tasks']['train']},rows={str(t):{} for t in c['tasks']['train']},
        frozen_before=dict(core=c['parent_model_sha256'],readout=c['parent_readout_sha256'],state=before),
        closed_initials=[list(v) for v in sorted(used)],timing_s=dict(collection=0.,scoring=0.,analysis=0.),costs=meter.costs)
    def progress():
        r.update(wall_s=time.monotonic()-meter.start,imagined_transitions=meter.imagined,posterior_rows=meter.posterior)
        p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress();scales={str(t):f['scale'] for f in pack['frozen_folds'].values() for t in f['excluded_ids']}
    try:
        for role in ROLES:
            if role=='check':
                manifest=selection_manifest(r['rows'],r['queries'],c,pack)
                path=Path('locked-selection.json');path.write_text(json.dumps(manifest,allow_nan=False))
                require_selection(path,manifest);r.update(selection_manifest=manifest,selection_manifest_sha256=digest(manifest),selection_locked_before_check=True);progress()
            for t in c['tasks']['train']:
                tid=str(t);meter.check();tick=time.monotonic()
                q=collect_queries(core,head,c['query_seeds'][tid][role],pack['goals'][tid],meter,used);r['queries'][tid][role]=q
                r['timing_s']['collection']+=time.monotonic()-tick;tick=time.monotonic()
                for b in c['budgets']:
                    cell=r['rows'][tid].get(str(b))
                    r['rows'][tid][str(b)]=score_snapshots(pack['rows'][tid][str(b)],q,scales[tid],role,cell)
                r['timing_s']['scoring']+=time.monotonic()-tick;progress()
        tick=time.monotonic();r['analysis']=summarize(r['rows'],manifest['choices'],c,pack);r['timing_s']['analysis']=time.monotonic()-tick
        r.update(frozen_after=dict(core=nl.file_hash(root/c['parent_model']),readout=nl.file_hash(root/c['parent_readout']),state=fingerprint()),fixed_after_sha256=digest(pack),model_work=dict(core.work),update_work=dict(nl.lb.WORK))
        validate(r,c,pack);meter.check();r['declared_complete']=True;progress()
    except Exception as exc:
        import traceback
        r.update(declared_complete=False,failure=repr(exc),traceback=traceback.format_exc());progress()
        raise
    work=dict(updates=0,real_steps=sum(meter.costs.values()),imagined_transitions=meter.imagined,posterior_rows=meter.posterior,
        cpu_s=time.process_time(),evaluated_cached_states=900,cached_retention_rows=24300,new_query_score_rows=900*216,
        counterfactual_updates=0,normalization_fit_rows=0,parameter_count=sum(p.numel() for p in core.parameters())+sum(p.numel() for p in head.parameters()))
    a=r['analysis'];return dict(adapter='seed_query_replication_v1',study=r,resources=work,
        metrics=dict(mse=a['check_means']['selected'],baseline_mse=a['check_means']['variance']),curve=[],
        model=dict(schema='unchanged_query_replication_v1',**r['frozen_after']),runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);work=output['resources']
    if output['adapter']!='seed_query_replication_v1' or r['declared_complete'] is not True or output['model']!=dict(schema='unchanged_query_replication_v1',**r['frozen_after']):raise ValueError('incomplete_query_replication')
    sizes=checkpoint_parameter_count(Path(__file__).resolve().parents[3],c)
    for key,expected in dict(updates=0,real_steps=2592,imagined_transitions=2592,posterior_rows=288,evaluated_cached_states=900,cached_retention_rows=24300,new_query_score_rows=194400,counterfactual_updates=0,normalization_fit_rows=0,parameter_count=sum(sizes.values())).items():
        if type(work[key]) is not int or work[key]!=expected:raise ValueError('query_execution_resource_grid')
    if not finite(work['cpu_s']) or not 0<=work['cpu_s']<=caps['cpu_s'] or any(work[k]>caps[k] for k in ('real_steps','imagined_transitions','updates')):raise ValueError('query_execution_cap')
    if r['model_work']['encoder_rows']!=288 or r['model_work']['transition_rows']!=2880 or r['model_work']['head_rows']!=2592 or r['update_work']!={'readout_score_batches':288,'readout_basis_batches':288}:raise ValueError('query_model_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_query_replication.json').read_text());r=json.loads((root/'artifacts/seed_query_replication.json').read_text())
    status=r['host_receipt']['status']
    if r['declared_complete'] is not True:
        receipt=verify_offline_receipt(root,r,c)
        status=receipt['status']
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_query_replication',status=status,failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],metrics=dict(mse=r['analysis']['check_means']['selected'],baseline_mse=r['analysis']['check_means']['variance']),curve=[],resources=r['resources'],model_sha256=r['frozen_after']['state'],query_replication=r['analysis'])


def verify_offline_receipt(root,r,c):
    """A separate arithmetic validation can never rewrite the execution status."""
    receipt=json.loads((root/'artifacts/seed_query_replication_validation.json').read_text())
    raw=hashlib.sha256((root/'artifacts/seed_query_replication.json').read_bytes()).hexdigest()
    if (receipt.get('raw_sha256')!=raw or receipt.get('status')!='complete_offline_validation_of_unchanged_capture'
        or receipt.get('schema')!='seed_query_offline_validation_v1'
        or receipt.get('scientific_rerun') is not False or receipt.get('validated_complete') is not True
        or receipt.get('original_status')!=r['host_receipt']['status'] or receipt.get('analysis_sha256')!=digest(r['analysis'])
        or receipt.get('config_file_sha256')!=hashlib.sha256((root/'configs/seed_query_replication.json').read_bytes()).hexdigest()
        or receipt.get('protocol_file_sha256')!=r['host_receipt']['dataset_hashes']['protocol']
        or receipt.get('validator_sha256')!=hashlib.sha256((root/'scripts/validate_seed_query_replication.py').read_bytes()).hexdigest()
        or receipt.get('audit_module_sha256')!=hashlib.sha256((root/'src/nexus/seed/query_replication.py').read_bytes()).hexdigest()):raise ValueError('offline_query_validation_provenance')
    return receipt
