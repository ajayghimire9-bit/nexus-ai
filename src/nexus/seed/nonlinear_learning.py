"""One bounded Seed study over existing frozen features and correction APIs.

The optimizer takes source tasks only. The inner curve function accepts no
evaluator callback. Oracle outcomes remain in separately collected records.
"""
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import time

import torch
from nexus.evolution1.catalogue import digest
from .action_readout import ActionReadout, features
from .grounded_world import AuthoredWorld,tensors
from .state_contract import Belief
from .plasticity import PlasticityController
from . import learning_benchmark as lb
from .action_ranking import rank_metrics
from .spatial_transfer import identity
from .nonlinear_learning_audit import config_check, summarize, validate
from nexus.world.seed_rssm import SeedRSSM


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Meter:
    def __init__(self,c,progress=None):
        self.c=c;self.start=time.monotonic();self.costs=dict(collection=0,control=0)
        self.imagined=0;self.posterior=0;self.progress=progress

    def check(self):
        if time.monotonic()-self.start>=self.c['max_wall_s']:raise TimeoutError('study_wall_cap')

    def charge(self,role):
        self.check()
        if sum(self.costs.values())>=self.c['max_authored_steps']:raise ValueError('study_real_cap')
        self.costs[role]+=1

    def model(self,n=9,posterior=False):
        self.check()
        if posterior:self.posterior+=n
        else:
            if self.imagined+n>self.c['max_imagined_transitions']:raise ValueError('study_imagined_cap')
            self.imagined+=n


def historical_initials(root,paths):
    """Read state identities only; historical outcome values never select states."""
    found=set()
    def walk(value,goal=None):
        if type(value) is dict:
            g=value.get('goal',goal);obj=value.get('before')
            if type(obj) is dict and g is not None and all(k in obj for k in ('x','y','color','shape','size')):
                found.add(identity(obj,g))
            for child in value.values():walk(child,g)
        elif type(value) is list:
            for child in value:walk(child,goal)
    hashes={}
    for name in paths:
        p=root/name;hashes[name]=file_hash(p);walk(json.loads(p.read_text()))
    return found,hashes


def fresh_world(seed,goal,index,used):
    w=lb.world_at(seed,goal,index);w.information_reward=False
    rng=random.Random(seed+177)
    for attempt in range(1024):
        if identity(w.obj,w.goal) not in used:
            used.add(identity(w.obj,w.goal));return w
        w.obj.update(color=rng.choice(('red','blue','green')),shape=rng.choice(('circle','square','triangle')),size=rng.choice(('small','large')))
        if attempt>=32:w.obj.update(x=rng.randrange(6),y=rng.randrange(6))
        if (w.obj['x'],w.obj['y'])==w.goal:w.obj['x']=(w.obj['x']+1)%6
    raise ValueError('fresh_initial_space_exhausted')


def score_basis(model,head,w,meter,belief=None,previous=0,token=0):
    b=belief or Belief(model);args=tensors([w.observe()])
    meter.model(1,posterior=True)
    with torch.no_grad():b.observe(model.encode(*args),torch.tensor([previous]),token)
    meter.model(9)
    x,world_base=features(model,b.h,b.z,args[2],b.memory)
    with torch.no_grad():base=world_base+head(x);basis=head.adaptation_features(x)
    lb.count('readout_score_batches');lb.count('readout_basis_batches')
    return basis,base,world_base


def collect(model,head,seed,goal,old_goal,meter,used):
    records={};arrays={}
    for role,count,target,offset in [('support',8,goal,100),('old',4,old_goal,200),('query',3,goal,300),('retention',3,old_goal,400)]:
        xs=[];ys=[];records[role]=[]
        for i in range(count):
            w=fresh_world(seed+offset+i,target,i,used);basis,base,_=score_basis(model,head,w,meter)
            action=(seed//10000+i)%9
            row=dict(seed=seed+offset+i,before=dict(w.obj),goal=list(target),action=action,
                     base=base.tolist(),proprio=w.observe()['proprio'].tolist(),outcomes=[])
            selected=range(9) if role in ('query','retention') else [action]
            for a in selected:
                other=copy.deepcopy(w);meter.charge('collection');obs,reward,done,_=other.step(a)
                row['outcomes'].append(dict(action=a,reward=reward,done=done,truncated=False,
                    after=dict(other.obj),next_proprio=obs['proprio'].tolist()))
                xs.append(basis[a]);ys.append(reward-float(base[a]))
            records[role].append(row)
        arrays[role+'_x']=torch.stack(xs);arrays[role+'_y']=torch.tensor(ys)
    task=lb.LessonTask(*(arrays[k] for k in ('support_x','support_y','query_x','query_y','old_x','old_y','retention_x','retention_y')))
    data={k:v.tolist() for k,v in arrays.items()}
    return task,dict(seed=seed,goal=list(goal),records=records,record_sha256=digest(records),
                     arrays=data,array_sha256=digest(data),dtype='float32',feature_width=33)


def controller(seed,static=False,*,width=33):
    torch.manual_seed(seed);m=PlasticityController(width)
    with torch.no_grad():m.logits.bias.normal_(0,.01)
    if static:m.logits.weight.requires_grad_(False)
    return m


def fit_source(tasks,seed,static,c,check,*,curve_fn=None,model_factory=None):
    """No development/audit parameter or file access. Source outer labels only."""
    start=time.monotonic();m=(model_factory or controller)(seed,static);before={k:v.detach().clone() for k,v in m.state_dict().items()}
    trainable=sum(p.numel() for p in m.parameters() if p.requires_grad)
    opt=torch.optim.Adam([p for p in m.parameters() if p.requires_grad],lr=c['meta_lr'])
    rng=random.Random(seed+41);order=[]
    while len(order)<c['meta_updates']:
        cycle=list(range(len(tasks)));rng.shuffle(cycle);order.extend(cycle)
    training=[]
    for step,index in enumerate(order[:c['meta_updates']],1):
        check();rows,_=(curve_fn or lb.curve)(tasks[index],m,'learned',check)
        error=torch.stack([v for _,v,_ in rows]).mean();forget=torch.stack([v for _,_,v in rows]).mean()
        loss=error+c['retention_weight']*forget
        if not torch.isfinite(loss):raise ValueError('nonfinite_outer_loss')
        opt.zero_grad();loss.backward()
        grad=sum(float(p.grad.square().sum()) for p in m.parameters() if p.grad is not None)**.5
        if not torch.isfinite(torch.tensor(grad)):raise ValueError('nonfinite_outer_gradient')
        opt.step()
        training.append(dict(update=step,task_index=index,query_mse=float(error.detach()),
                             forgetting=float(forget.detach()),gradient_norm=grad))
    change=sum(float((m.state_dict()[k]-v).square().sum()) for k,v in before.items())**.5
    m.eval()
    for p in m.parameters():p.requires_grad_(False)
    return m,dict(training=training,parameter_change_l2=change,seconds=time.monotonic()-start,
        trainable_parameters=trainable,source_schedule_sha256=digest(order[:c['meta_updates']]),
        support_examples=c['meta_updates']*8,query_examples=c['meta_updates']*4*27,
        retention_examples=c['meta_updates']*4*27)


def evaluate(task,raw,model,method,check):
    rows,snaps=lb.curve(task,model,'learned' if method=='static' else method,check)
    base=torch.tensor([v for state in raw['records']['query'] for v in state['base']])
    truths=[a['reward'] for state in raw['records']['query'] for a in state['outcomes']]
    out=[]
    for budget,error,forget in rows:
        predicted=(base+task.query_x@snaps[budget]).tolist()
        ranks=[rank_metrics(predicted[i:i+9],truths[i:i+9]) for i in range(0,27,9)]
        out.append(dict(budget=budget,query_mse=float(error.detach()),forgetting=float(forget.detach()),
            theta=snaps[budget].tolist(),scores=predicted,
            regret=sum(v['regret'] for v in ranks)/3,optimal_rate=sum(v['optimal'] for v in ranks)/3))
    return out,snaps


def rollout(model,head,initial,seed,method,theta,scale,c,meter):
    from .latent_planner import plan
    w=copy.deepcopy(initial);belief=Belief(model);previous=0;rng=random.Random(seed+71)
    result=dict(seed=seed,steps=[],return_sum=0.,success=False)
    for t in range(c['control_steps']):
        meter.check();before=dict(w.obj)
        if method=='greedy':
            dx=w.goal[0]-w.obj['x'];dy=w.goal[1]-w.obj['y'];a=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2)
        elif method=='random':a=rng.randrange(9)
        elif method=='latent_mpc':
            meter.model(1,posterior=True);args=tensors([w.observe()])
            with torch.no_grad():belief.observe(model.encode(*args),torch.tensor([previous]),t)
            meter.model(48);a,_=plan(model,belief.h,belief.z,belief.memory,seed=seed*100+t)
        else:
            x,base,world=score_basis(model,head,w,meter,belief,previous,t)
            scores=world if method=='frozen_world' else base if method=='frozen_readout' else base+(x/scale)@theta
            a=int(scores.argmax())
        meter.charge('control');_,reward,done,_=w.step(a);previous=a
        result['steps'].append(dict(before=before,after=dict(w.obj),goal=list(w.goal),action=a,reward=reward,done=done))
        result['return_sum']+=reward;result['success']=done
        if done:break
    return result


def run(request):
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository']);torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True);meter=Meter(c);lb.WORK.clear()
    r=dict(config=c,config_sha256=digest(c),declared_complete=False,tasks={k:[] for k in c['tasks']},
        controllers=[],curves={k:{} for k in ('development','audit')},control={},costs=meter.costs,
        dtype='float32',mode='experimental_development_with_fresh_internal_assessment')
    def progress():
        r.update(wall_s=time.monotonic()-meter.start,imagined_transitions=meter.imagined,posterior_rows=meter.posterior)
        p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    try:
        if file_hash(root/c['parent_model'])!=c['parent_sha256'] or file_hash(root/c['parent_readout'])!=c['readout_sha256']:
            raise ValueError('historical_checkpoint_hash')
        core,_=SeedRSSM.load(root/c['parent_model'],c['parent_sha256'])
        head=ActionReadout.load(root/c['parent_readout'],c['readout_sha256'],c['parent_sha256'])
        before=copy.deepcopy(core.state_dict());bank=core.world_memory_bank.clone();head_before=copy.deepcopy(head.state_dict())
        used,hashes=historical_initials(root,c['closed_artifacts'])
        if hashes!=c['closed_sha256']:raise ValueError('closed_artifact_provenance_changed')
        r.update(closed_initials=[list(t) for t in sorted(used)],historical_hashes=hashes)
        tasks={}
        for role in ('train','development'):
            tasks[role]=[]
            for seed,goal in zip(c['tasks'][role]['seeds'],c['tasks'][role]['goals']):
                task,raw=collect(core,head,seed,goal,c['old_goal'],meter,used);tasks[role].append(task);r['tasks'][role].append(raw)
            progress()
        scale=lb.scale_features(torch.cat([t for task in tasks['train'] for t in (task.support_x,task.old_x)]));r['scale']=scale.tolist()
        for role in tasks:tasks[role]=[lb.scaled(t,scale) for t in tasks[role]]
        models={}
        for seed in c['outer_seeds']:
            models[seed]={};entry=dict(seed=seed,arms={});r['controllers'].append(entry)
            for method in ('learned','static'):
                m,info=fit_source(tasks['train'],seed,method=='static',c,meter.check)
                path=Path(f'controller-{seed}-{method}.json');checkpoint=m.export(path,dict(config_sha256=digest(c),source_only=True,source_hash=digest(r['tasks']['train'])))
                info.update(checkpoint=path.name,sha256=checkpoint,weights={k:v.tolist() for k,v in m.state_dict().items()})
                entry['arms'][method]=info;models[seed][method]=m;progress()
        r['locked_before_audit']=dict(selection='final_64_updates_no_development_tuning',
            weights_sha256=digest(r['controllers']),source_sha256=digest(r['tasks']['train']),scale_sha256=digest(r['scale']))
        # Save the fitted rules BEFORE generating any assessment outcomes.
        progress();Path('frozen-before-audit.json').write_text(json.dumps(r['locked_before_audit'],allow_nan=False))
        tasks['audit']=[]
        for seed,goal in zip(c['tasks']['audit']['seeds'],c['tasks']['audit']['goals']):
            task,raw=collect(core,head,seed,goal,c['old_goal'],meter,used);tasks['audit'].append(lb.scaled(task,scale));r['tasks']['audit'].append(raw)
        for role in ('development','audit'):
            for seed in c['outer_seeds']:
                cells={};r['curves'][role][str(seed)]=cells
                for task,raw in zip(tasks[role],r['tasks'][role]):
                    raw['initial_theta']=lb.initial(task).tolist();cell={};cells[str(raw['seed'])]=cell
                    for method in c['methods']:
                        cell[method],_=evaluate(task,raw,models[seed].get(method),method,meter.check)
            progress()
        for i,(seed,goal) in enumerate(zip(c['tasks']['audit']['seeds'],c['tasks']['audit']['goals'])):
            initials=[fresh_world(seed+1000+j,goal,1,used) for j in range(c['control_episodes'])]
            cell={};r['control'][str(seed)]=cell
            for outer in c['outer_seeds']:
                for method in c['methods']:
                    theta=torch.tensor(r['curves']['audit'][str(outer)][str(seed)][method][-1]['theta'])
                    cell[f'{outer}/{method}']=[rollout(core,head,w,seed+1000+j,method,theta,scale,c,meter) for j,w in enumerate(initials)]
            for method in c['references']:
                cell[method]=[rollout(core,head,w,seed+1000+j,method,None,scale,c,meter) for j,w in enumerate(initials)]
            progress()
        r.update(frozen_core=all(torch.equal(v,core.state_dict()[k]) for k,v in before.items()),
            frozen_bank=torch.equal(bank,core.world_memory_bank),frozen_readout=all(torch.equal(v,head.state_dict()[k]) for k,v in head_before.items()),
            model_work=dict(core.work),update_work=dict(lb.WORK))
        progress();r['analysis']=summarize(r);validate(r,c);r['declared_complete']=True
    except Exception as exc:
        import traceback
        r['failure']=repr(exc);r['traceback']=traceback.format_exc();progress()
        raise
    progress()
    a=r['analysis'];learned=a['curve_means']['learned'];best=min(a['curve_means'][m] for m in c['methods'][1:])
    return dict(adapter='seed_nonlinear_learning_v1',study=r,
        metrics=dict(mse=learned,baseline_mse=best,worst_error_increase=a['forgetting']['learned']-a['forgetting']['fixed']),
        curve=[dict(update=b,train_mse=a['per_budget'][str(b)]['learned']['mse']['mean'],
                    development_mse=min(a['per_budget'][str(b)][m]['mse']['mean'] for m in c['methods'][1:])) for b in c['budgets']],
        model=dict(schema='seed_update_rules_v1',controllers=r['controllers']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1),
        resources=dict(updates=2*len(c['outer_seeds'])*c['meta_updates'],real_steps=sum(meter.costs.values()),
            imagined_transitions=meter.imagined,posterior_rows=meter.posterior,cpu_s=time.process_time(),
            parameter_count=3*(165+33),source_query_examples=6*c['meta_updates']*4*27,
            source_support_examples=6*c['meta_updates']*8))
