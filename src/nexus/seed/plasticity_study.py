"""Bounded source-record experiment over SAME frozen SeedRSSM and adapters."""
import hashlib
import json
import math
from pathlib import Path
import random
import time
import torch
from .plasticity import PlasticityController,TrainingLesson,learning_curve,correction
from .adaptive_state import reward_features
from .grounded_world import observation,tensors
from .state_contract import Belief
from nexus.world.seed_rssm import SeedRSSM


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_tasks(root,c,check):
    if sha(root/c['parent_model'])!=c['parent_sha256'] or sha(root/c['source_result'])!=c['source_sha256']:raise ValueError('locked_parent_or_source_hash')
    model,_=SeedRSSM.load(root/c['parent_model'],c['parent_sha256'])
    before={k:v.clone() for k,v in model.state_dict().items()};bank=model.world_memory_bank.clone()
    raw=json.loads((root/c['source_result']).read_text())['source'];encoded=[]
    for episode in raw:
        b=Belief(model);previous=0;flags=[0,0,0];xs=[];ys=[]
        for token,step in enumerate(episode['steps']):
            check()
            with torch.no_grad():
                sensors=tensors([observation(step['before'],tuple(step['goal']),flags)])
                b.observe(model.encode(*sensors),torch.tensor([previous]),token)
                action=step['action'];x=reward_features(b.h,b.z,sensors[2])[action]
                nh,nz,_,_=model.transition(b.h,b.z,torch.tensor([action]),b.memory)
                base=model.heads(nh,nz)['reward'][0]
                xs.append(x);ys.append(float(step['reward'])-float(base))
            previous=action
            if 4<=action<=6:flags[action-4]=1
        encoded.append((torch.stack(xs),torch.tensor(ys),episode['seed']))
    tasks={};ids={};excluded={}
    for split,(lo,hi) in c['split_episode_indices'].items():
        tasks[split]=[];ids[split]=[];excluded[split]=[]
        for i in range(lo,hi):
            x,y,seed=encoded[i]
            if len(x)<c['minimum_episode_rows']:
                excluded[split].append(seed);continue
            donor=lo+(i-lo+1)%(hi-lo);ox,oy,_=encoded[donor]
            k=c['support_rows']
            tasks[split].append(TrainingLesson(x[:k],y[:k],x[k:],y[k:],ox[:2],oy[:2]));ids[split].append(seed)
    preserved=all(torch.equal(before[k],v) for k,v in model.state_dict().items()) and torch.equal(bank,model.world_memory_bank)
    return tasks,ids,excluded,dict(encoder_rows=model.work['encoder_rows'],posterior_prior_rows=len([s for e in raw for s in e['steps']]),imagined_candidate_rows=model.work['transition_rows']-model.work['encoder_rows'],frozen_core=preserved)


def fixed_curve(task,mode):
    m=PlasticityController(len(task.support_x[0]))
    if mode=='replay_sgd':return learning_curve(m,task,baseline=True)
    with torch.no_grad():
        m.logits.weight.zero_();m.logits.bias.fill_(math.log((1-.05)/(2-1)))
    return learning_curve(m,task)


def evaluate(m,tasks,ids,check):
    rows=[]
    for task,seed in zip(tasks,ids):
        check()
        methods={}
        with torch.no_grad():
            for mode in ('learned','fixed_protected','replay_sgd'):
                out=learning_curve(m,task) if mode=='learned' else fixed_curve(task,mode)
                objective,theta,curve,forget=out
                methods[mode]=dict(objective=float(objective),query_learning_curve=curve.tolist(),
                    query_auc=float(curve.mean()),forgetting=float(forget.mean()),theta_norm=float(theta.norm()))
        rows.append(dict(source_episode_seed=seed,methods=methods))
    return rows


def validate_result(r,c):
    if r['config']!=c or r['new_real_steps']!=0 or not r['model_work']['frozen_core']:raise ValueError('study_provenance')
    if r['episode_ids']!=c['expected_episode_ids']:raise ValueError('locked_episode_grid')
    if r['model_work']['imagined_candidate_rows']>c['max_imagined_transitions']:raise ValueError('imagined_cap')
    if [s['seed'] for s in r['seeds']]!=c['controller_seeds']:raise ValueError('planned_controller_grid')
    for s in r['seeds']:
        if len(s['training'])!=c['meta_updates'] or s['parameter_change']<=0:raise ValueError('missing_meta_updates')
        for split in c['split_episode_indices']:
            rows=s['evaluation'][split]
            if [row['source_episode_seed'] for row in rows]!=r['episode_ids'][split] or not rows:raise ValueError('missing_episode_grid')
            for row in rows:
                if set(row['methods'])!={'learned','fixed_protected','replay_sgd'}:raise ValueError('missing_method')
                for metrics in row['methods'].values():
                    if set(metrics)!={'objective','query_learning_curve','query_auc','forgetting','theta_norm'}:raise ValueError('missing_metric')
                    values=[v for k,v in metrics.items() if k!='query_learning_curve']+metrics['query_learning_curve']
                    if len(metrics['query_learning_curve'])!=c['support_rows'] or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('nonfinite_or_shortened_metrics')
    sets=[set(r['episode_ids'][k]) for k in c['split_episode_indices']]
    if any(sets[i]&sets[j] for i in range(len(sets)) for j in range(i)):raise ValueError('source_split_overlap')
    return True


def run(root,c,out,check,execution_sha):
    started=time.monotonic();tasks,ids,excluded,work=source_tasks(root,c,check)
    result=dict(schema='seed_memory_aware_result_v1',config=c,execution_sha=execution_sha,episode_ids=ids,
                excluded_short_episodes=excluded,model_work=work,seeds=[],new_real_steps=0,declared_complete=False)
    result['compute']=dict(meta_optimizer_steps=0,learned_inner_support_examples=0,baseline_inner_support_examples=0,
        meta_query_prediction_examples=0,baseline_query_prediction_examples=0,
        evaluation_inner_support_examples=0,evaluation_query_prediction_examples=0,
        anchor_initialization_solves=0,protected_update_solves=0,replay_anchor_prediction_examples=0)
    for seed in c['controller_seeds']:
        torch.manual_seed(seed);rng=random.Random(seed);m=PlasticityController();opt=torch.optim.Adam(m.parameters(),lr=c['meta_lr'])
        initial={k:v.clone() for k,v in m.state_dict().items()};training=[]
        for i in range(c['meta_updates']):
            check();task=tasks['train'][rng.randrange(len(tasks['train']))]
            loss,*_=learning_curve(m,task,retention_weight=c['retention_weight'])
            baseline=fixed_curve(task,'replay_sgd')[0].detach()
            objective=loss-baseline # baseline has no phi gradient
            opt.zero_grad();objective.backward()
            grad=math.sqrt(sum(float(p.grad.square().sum()) for p in m.parameters()))
            if not math.isfinite(grad):raise ValueError('nonfinite_meta_gradient')
            opt.step();training.append(dict(update=i+1,objective=float(objective.detach()),gradient_norm=grad))
            meter=result['compute'];k=len(task.support_x)
            meter['meta_optimizer_steps']+=1;meter['learned_inner_support_examples']+=k;meter['baseline_inner_support_examples']+=k
            meter['meta_query_prediction_examples']+=k*len(task.query_x);meter['baseline_query_prediction_examples']+=k*len(task.query_x)
            meter['anchor_initialization_solves']+=2;meter['protected_update_solves']+=k
            meter['replay_anchor_prediction_examples']+=k*len(task.old_x)
        evaluation={split:evaluate(m,tasks[split],ids[split],check) for split in tasks}
        for group in tasks.values():
            for task in group:
                meter['evaluation_inner_support_examples']+=3*len(task.support_x)
                meter['evaluation_query_prediction_examples']+=3*len(task.support_x)*len(task.query_x)
                meter['anchor_initialization_solves']+=3;meter['protected_update_solves']+=2*len(task.support_x)
                meter['replay_anchor_prediction_examples']+=len(task.support_x)*len(task.old_x)
        checkpoint=root/'artifacts'/f'seed_plasticity_{seed}.json'
        h=m.export(checkpoint,dict(execution_sha=execution_sha,source_sha256=c['source_sha256'],parent_sha256=c['parent_sha256'],seed=seed))
        result['seeds'].append(dict(seed=seed,training=training,evaluation=evaluation,
            parameter_change=sum(float((v-initial[k]).square().sum()) for k,v in m.state_dict().items())**.5,
            checkpoint=str(checkpoint.relative_to(root)),sha256=h))
        out.write_text(json.dumps(result,indent=2,allow_nan=False))
    result['wall_s']=time.monotonic()-started
    validate_result(result,c);result['declared_complete']=True
    out.write_text(json.dumps(result,indent=2,allow_nan=False))
    return result
