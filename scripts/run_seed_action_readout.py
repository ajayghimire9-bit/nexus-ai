"""One bounded residual-readout study with a pre-audit checkpoint manifest."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    path=ROOT/'artifacts/seed_action_readout.json'
    if path.exists():raise FileExistsError('consumed_readout_study')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_protocol_required')
    start=time.perf_counter();c=json.loads((ROOT/'configs/seed_action_readout.json').read_text())
    if (c['updates'],c['learning_rate'],c['batch_size'])!=(800,.003,128):raise ValueError('locked_readout_optimizer')
    claim=ROOT/'runs/action-readout.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write('single bounded fit and fresh evaluation')
    r=dict(config=c,execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source=[],audit=[],models=[],control={},authored_steps=0,imagined_transitions=0,optimizer_updates=0,training_example_presentations=0,declared_complete=False)
    def check():
        if time.perf_counter()-start>c['max_wall_s']:raise TimeoutError('readout_wall_cap')
    def charge():
        check()
        if r['authored_steps']>=c['max_authored_steps']:raise ValueError('readout_interaction_cap')
        r['authored_steps']+=1
    def imagine(n):
        check()
        if r['imagined_transitions']+n>c['max_imagined_transitions']:raise ValueError('readout_imagined_cap')
        r['imagined_transitions']+=n
    try:
        import torch
        torch.set_num_threads(1)
        from nexus.world.seed_rssm import SeedRSSM
        from nexus.seed.action_ranking import registered_world,outcomes,hash_file,rank_metrics
        from nexus.seed.action_readout import features,fit
        from nexus.seed.grounded_world import AuthoredWorld,tensors
        from nexus.seed.latent_planner import plan
        from nexus.seed.readout_audit import validate,require_manifest
        r['config_sha256']=hash_file(ROOT/'configs/seed_action_readout.json');r['torch_version']=torch.__version__
        parent=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text());models={};before={};heads={}
        for p in parent['models']:
            model,_=SeedRSSM.load(ROOT/p['checkpoint'],p['sha256']);models[p['recipe']]=model;before[p['recipe']]=copy.deepcopy(model.state_dict())
        def collect(kind,count,start_seed):
            for i in range(count):
                w=registered_world(start_seed+i,i)
                r[kind].append(dict(seed=start_seed+i,group='boundary' if i%2==0 else 'interior',before=dict(w.obj),goal=list(w.goal),outcomes=outcomes(w,charge)))
        def state_features(model,record):
            w=AuthoredWorld(record['seed']);w.obj=dict(record['before']);w.goal=tuple(record['goal'])
            with torch.no_grad():
                args=tensors([w.observe()]);e=model.encode(*args);h,z=model.initial();h,z,_=model.observe(h,z,torch.zeros(1,dtype=torch.long),e)
                imagine(9);return features(model,h,z,args[2])
        collect('source',c['training_states'],c['training_seed_start'])
        r['source_sha256']=__import__('hashlib').sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()
        r['action_means']=[sum(s['outcomes'][a]['reward'] for s in r['source'])/len(r['source']) for a in range(9)]
        for p in parent['models']:
            name=p['recipe'];model=models[name];parts=[state_features(model,s) for s in r['source']]
            x=torch.cat([p[0] for p in parts]);base=torch.cat([p[1] for p in parts]);y=torch.tensor([o['reward'] for s in r['source'] for o in s['outcomes']])
            record=dict(recipe=name,parent_hash=p['sha256'],heads=[]);r['models'].append(record);heads[name]={}
            for seed in c['readout_seeds']:
                check();fit_start=time.perf_counter();r['in_progress_fit']=dict(recipe=name,seed=seed,losses=[])
                def progress(update,loss):
                    r['in_progress_fit']['losses'].append(loss);r['optimizer_updates']+=1;r['training_example_presentations']+=128
                head,losses=fit(x,base,y,seed=seed,updates=c['updates'],check=check,progress=progress)
                dest=ROOT/f'artifacts/seed_action_{name}_{seed}.json'
                sha=head.export(dest,dict(parent_hash=p['sha256'],source_sha256=r['source_sha256'],config_sha256=r['config_sha256'],execution_sha=r['execution_sha'],seed=seed))
                head.sha256=sha;head.parent_hash=p['sha256'];heads[name][seed]=head
                record['heads'].append(dict(seed=seed,checkpoint=str(dest.relative_to(ROOT)),sha256=sha,losses=losses,training_wall_s=time.perf_counter()-fit_start,parameter_count=sum(p.numel() for p in head.parameters())))
        manifest=dict(config_sha256=r['config_sha256'],source_sha256=r['source_sha256'],execution_sha=r['execution_sha'],models=[dict(recipe=m['recipe'],parent_hash=m['parent_hash'],heads=[{k:h[k] for k in ('seed','checkpoint','sha256')} for h in m['heads']]) for m in r['models']])
        manifest_path=ROOT/'artifacts/seed_action_readout_manifest.json'
        with manifest_path.open('x') as f:json.dump(manifest,f,indent=2,allow_nan=False)
        r['manifest_sha256']=hash_file(manifest_path)
        # Nothing below can alter a fitted head. No held-out states were opened above.
        require_manifest(r,ROOT)
        collect('audit',c['audit_states'],c['audit_seed_start'])
        for row in r['audit']:
            row['models']={};actual=[o['reward'] for o in row['outcomes']]
            for name,model in models.items():
                x,base=state_features(model,row)
                scores=dict(frozen_reward=base.tolist(),source_mean=r['action_means'])
                with torch.no_grad():
                    for seed,head in heads[name].items():scores[f'calibrated_{seed}']=(base+head(x)).tolist()
                row['models'][name]=dict(scores=scores,metrics={k:rank_metrics(v,actual) for k,v in scores.items()})
        for name,model in models.items():
            r['control'][name]={}
            for method in c['methods']:
                rows=[];r['control'][name][method]=rows
                for i in range(c['control_episodes']):
                    seed=c['control_seed_start']+i;w=AuthoredWorld(seed);h,z=model.initial();prev=0;rng=random.Random(seed+91)
                    row=dict(seed=seed,steps=[],return_sum=0.,success=False);rows.append(row)
                    for t in range(c['control_steps']):
                        check()
                        with torch.no_grad():
                            args=tensors([w.observe()]);e=model.encode(*args);h,z,_=model.observe(h,z,torch.tensor([prev]),e)
                            if method.startswith('calibrated_'):
                                imagine(9);action,info=heads[name][int(method.split('_')[1])].rank(model,h,z,args[2])
                            elif method=='frozen_reward':
                                imagine(9);_,base=features(model,h,z,args[2]);action=int(base.argmax());info={}
                            elif method=='latent_mpc':imagine(48);action,info=plan(model,h,z,seed=seed*100+t)
                            elif method=='source_mean':action=max(range(9),key=lambda a:r['action_means'][a]);info={}
                            elif method=='random':action=rng.randrange(9);info={}
                            else:
                                dx=w.goal[0]-w.obj['x'];dy=w.goal[1]-w.obj['y'];action=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2);info={}
                        before_state=dict(w.obj);charge();_,reward,done,actual=w.step(action)
                        row['steps'].append(dict(action=action,reward=reward,done=done,before=before_state,after=dict(w.obj),goal=list(w.goal),planning=info))
                        row['return_sum']+=reward;row['success']=done;prev=action
                        if done:break
        r['frozen']={name:all(torch.equal(v,models[name].state_dict()[k]) for k,v in state.items()) for name,state in before.items()}
        r['model_work']={name:model.work for name,model in models.items()}
        r['wall_s']=time.perf_counter()-start;validate(r,ROOT);r['declared_complete']=True
    except Exception as e:
        import traceback
        r['failure']=repr(e);r['traceback']=traceback.format_exc()
    r['wall_s']=time.perf_counter()-start
    with path.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(json.dumps({k:r.get(k) for k in ('declared_complete','failure','wall_s','authored_steps','imagined_transitions','execution_sha')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
