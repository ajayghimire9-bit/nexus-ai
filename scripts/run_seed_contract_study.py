"""Exclusive bounded matched scratch experiment; historical weights never change."""
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    path=ROOT/'artifacts/seed_contract_study.json'
    if path.exists():raise FileExistsError('consumed_contract_study')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_protocol_required')
    start=time.perf_counter();c=json.loads((ROOT/'configs/seed_contract_study.json').read_text())
    claim=ROOT/'runs/seed-contract.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write('one matched study')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    old={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'artifacts').glob('*') if p.is_file()}
    r=dict(config=c,config_sha256=sha(ROOT/'configs/seed_contract_study.json'),execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source=[],ranking=[],models=[],control={},references={},authored_steps=0,imagined_transitions=0,optimizer_updates=0,declared_complete=False)
    def check():
        if time.perf_counter()-start>c['max_wall_s']:raise TimeoutError('contract_study_wall_cap')
    def charge():
        check()
        if r['authored_steps']>=c['max_authored_steps']:raise ValueError('contract_study_interaction_cap')
        r['authored_steps']+=1
    def imagine(n):
        check()
        if r['imagined_transitions']+n>c['max_imagined_transitions']:raise ValueError('contract_study_imagined_cap')
        r['imagined_transitions']+=n
    episodes=[];models={};saved={}
    try:
        import torch
        torch.set_num_threads(1)
        from nexus.world.seed_rssm import SeedRSSM
        from nexus.seed.state_contract import Belief
        from nexus.seed.grounded_meta import RECIPES
        from nexus.seed.grounded_training import collect,train
        from nexus.seed.grounded_world import AuthoredWorld,tensors
        from nexus.seed.action_ranking import registered_world,outcomes,rank_metrics
        from nexus.seed.latent_planner import plan
        from nexus.seed.capability_audit import language_audit,concept_audit
        collect(range(c['training_seed_start'],c['training_seed_start']+c['training_episodes']),c['source_steps'],charge,episodes,information_reward=False)
        r['source']=[dict(seed=e['seed'],steps=e['steps']) for e in episodes]
        r['source_sha256']=hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()
        checkpoint_dir=ROOT/'runs/seed-contract/checkpoints';checkpoint_dir.mkdir(parents=True,exist_ok=True)
        for recipe in RECIPES:
            for seed in c['model_seeds']:
                for condition in c['conditions']:
                    check();identity=f'{recipe.name}_{seed}_{condition}';fit_start=time.perf_counter()
                    r['current_fit']=dict(identity=identity,losses=[])
                    if condition=='untrained':
                        torch.manual_seed(seed);model=SeedRSSM(recipe.trunk_width,recipe.activation);model.semantics='aligned_v1'
                        with torch.no_grad():model.world_memory_bank=model.encode(*tensors([e['frames'][0] for e in episodes[:32]])).detach().clone()
                        training=dict(losses=[],updates=0,parameter_count=sum(p.numel() for p in model.parameters()))
                    else:
                        cfg=dict(c,model_seed=seed)
                        def progress(row):r['current_fit']['losses'].append(row);r['optimizer_updates']+=1
                        model,training=train(recipe,episodes,cfg,check,progress,semantics=condition)
                    model.eval()
                    for p in model.parameters():p.requires_grad_(False)
                    provenance=dict(execution_sha=r['execution_sha'],source_sha256=r['source_sha256'],config_sha256=r['config_sha256'],identity=identity)
                    dest=checkpoint_dir/(identity+'.json');digest=model.export(dest,provenance)
                    row=dict(identity=identity,recipe=recipe.name,seed=seed,condition=condition,training=training,fit_wall_s=time.perf_counter()-fit_start,checkpoint=str(dest.relative_to(ROOT)),sha256=digest)
                    if (recipe.name,seed,condition)==(c['gui_recipe'],c['gui_seed'],'aligned_v1'):
                        gui=ROOT/'artifacts/seed_contract_gui.json';row['gui_sha256']=model.export(gui,provenance)
                    models[identity]=model;saved[identity]=(copy.deepcopy(model.state_dict()),None if model.world_memory_bank is None else model.world_memory_bank.clone());r['models'].append(row)
        r['language']=language_audit()
        for i in range(c['ranking_states']):
            check();seed=c['ranking_seed_start']+i;w=registered_world(seed,i);w.information_reward=False
            row=dict(seed=seed,before=dict(w.obj),goal=list(w.goal),outcomes=outcomes(w,charge),models={});r['ranking'].append(row)
            actual=[o['reward'] for o in row['outcomes']];target=torch.tensor([o['proprio'] for o in row['outcomes']]);dims=[0,1,4,5,6,7,8,9,10]
            for identity,model in models.items():
                metrics={}
                for modality,mask in [('all',None),('pixels',(False,True,False)),('structured',(False,False,True))]:
                    with torch.no_grad():
                        e=model.encode(*tensors([w.observe()]),mask=mask);b=Belief(model);b.observe(e,torch.zeros(1,dtype=torch.long),0)
                        imagine(9);h,z,_,_=model.transition(b.h.expand(9,-1),b.z.expand(9,-1),torch.arange(9),b.memory.expand(9,-1));pred=model.heads(h,z)
                        if modality=='all':metrics['reward']=rank_metrics(pred['reward'].tolist(),actual)
                        else:metrics[modality+'_non_goal_mae']=float((pred['state'][:,dims]-target[:,dims]).abs().mean())
                row['models'][identity]=metrics
        for identity,model in models.items():
            check();r['control'][identity]={};r['models'][list(models).index(identity)]['concepts']=concept_audit(model,c['concept_seed'])
            for prune in c['pruning']:
                key='pruned' if prune else 'unpruned';rows=[];r['control'][identity][key]=rows
                for i in range(c['control_episodes']):
                    seed=c['control_seed_start']+i;w=AuthoredWorld(seed);w.information_reward=False;b=Belief(model)
                    with torch.no_grad():b.observe(model.encode(*tensors([w.observe()])),torch.zeros(1,dtype=torch.long),0)
                    row=dict(seed=seed,steps=[],return_sum=0.,success=False);rows.append(row)
                    for t in range(c['control_steps']):
                        imagine(48 if prune else 64);action,info=plan(model,b.h,b.z,b.memory,seed=seed*100+t,prune=prune)
                        before=dict(w.obj);charge();obs,reward,done,extra=w.step(action)
                        row['steps'].append(dict(action=action,reward=reward,done=done,before=before,after=dict(w.obj),goal=list(w.goal),planning=info));row['return_sum']+=reward;row['success']=done
                        with torch.no_grad():b.observe(model.encode(*tensors([obs])),torch.tensor([action]),t+1)
                        if done:break
        for method in ('random','greedy'):
            rows=[];r['references'][method]=rows
            for i in range(c['control_episodes']):
                seed=c['control_seed_start']+i;w=AuthoredWorld(seed);w.information_reward=False;rng=random.Random(seed+91)
                row=dict(seed=seed,steps=[],return_sum=0.,success=False);rows.append(row)
                for _ in range(c['control_steps']):
                    if method=='random':action=rng.randrange(9)
                    else:
                        dx=w.goal[0]-w.obj['x'];dy=w.goal[1]-w.obj['y'];action=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2)
                    before=dict(w.obj);charge();_,reward,done,_=w.step(action)
                    row['steps'].append(dict(action=action,reward=reward,done=done,before=before,after=dict(w.obj),goal=list(w.goal)));row['return_sum']+=reward;row['success']=done
                    if done:break
        r['frozen']={identity:all(torch.equal(v,models[identity].state_dict()[k]) for k,v in state.items()) and (bank is None or torch.equal(bank,models[identity].world_memory_bank)) for identity,(state,bank) in saved.items()}
        r['model_work']={k:m.work for k,m in models.items()}
        r['historical_artifacts_unchanged']=all(sha(ROOT/name)==h for name,h in old.items())
        from nexus.seed.contract_audit import validate
        r['wall_s']=time.perf_counter()-start;validate(r);r['declared_complete']=True
    except Exception as e:
        import traceback
        r['failure']=repr(e);r['traceback']=traceback.format_exc()
    if not r['source']:r['source']=[dict(seed=e['seed'],steps=e['steps']) for e in episodes]
    r['wall_s']=time.perf_counter()-start
    with path.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(json.dumps({k:r.get(k) for k in ('declared_complete','failure','wall_s','authored_steps','imagined_transitions','optimizer_updates','execution_sha')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
