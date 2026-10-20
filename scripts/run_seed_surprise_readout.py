"""One precommitted fresh readout experiment; old 64-state audit is unopened."""
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
import torch
from nexus.seed.action_readout import fit,features
from nexus.seed.action_ranking import rank_metrics,registered_world
from nexus.seed.grounded_world import tensors,AuthoredWorld
from nexus.seed.state_contract import Belief
from nexus.seed.latent_planner import plan
from nexus.seed.readout_validation import validate,summarize,require_manifest
from nexus.seed.surprise import SurpriseGate
from nexus.world.seed_rssm import SeedRSSM
ROOT=Path(__file__).resolve().parents[1]


def run():
    dest=ROOT/'artifacts/seed_surprise_readout.json'
    if dest.exists():raise ValueError('one_run_consumed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('precommitted_clean_protocol_required')
    cfg=ROOT/'configs/seed_surprise_readout.json';c=json.loads(cfg.read_text());start=time.monotonic();torch.set_num_threads(1)
    r=dict(config=c,config_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),declared_complete=False,authored_steps=0,imagined_transitions=0,source=[],development=[],audit=[],models=[],control={})
    def check():
        if time.monotonic()-start>min(c['max_wall_s'],c['session_remaining_s']):raise TimeoutError('readout_cap')
    def charge(n=1):
        check()
        if r['authored_steps']+n>c['max_authored_steps']:raise ValueError('authored_cap')
        r['authored_steps']+=n
    def imagine(n):
        check()
        if r['imagined_transitions']+n>c['max_imagined_transitions']:raise ValueError('imagined_cap')
        r['imagined_transitions']+=n
    def save():dest.write_text(json.dumps(r,indent=2,allow_nan=False))
    try:
        model,_=SeedRSSM.load(ROOT/c['parent_model'],c['parent_sha256']);before=copy.deepcopy(model.state_dict());bank=model.world_memory_bank.clone()
        def observe(w,b,previous=0,token=0):
            args=tensors([w.observe()])
            with torch.no_grad():b.observe(model.encode(*args),torch.tensor([previous]),token)
            return args[2]
        def collect(split):
            xs=[];bases=[];ys=[]
            for i in range(c[split]['states']):
                check();seed=c[split]['start']+i;w=registered_world(seed,i);w.information_reward=False
                # Balanced declared strata: boundary/interior/one-move/macro.
                # Placement uses geometry only; no outcomes or predictions.
                if i%4>=2:
                    w.obj.update(x=2,y=2);dx,dy=((1,0),(-1,0),(0,1),(0,-1))[(i//4)%4] if i%4==2 else ((1,1),(-1,-1))[(i//4)%2]
                    w.goal=(2+dx,2+dy)
                b=Belief(model);prop=observe(w,b);imagine(9);x,base=features(model,b.h,b.z,prop,b.memory)
                actual=[]
                for action in range(9):
                    other=copy.deepcopy(w);charge();_,reward,_,_=other.step(action);actual.append(reward)
                row=dict(seed=seed,stratum=i%4,before=dict(w.obj),goal=list(w.goal),actual=actual,base=base.tolist())
                r[split].append(row);xs.append(x);bases.append(base);ys.extend(actual)
            return torch.cat(xs),torch.cat(bases),torch.tensor(ys)
        x,base,y=collect('source');r['source_hash']=hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest();heads={}
        from nexus.seed.edit_credit_audit import evaluate
        r['edit_credit']=evaluate(x,base,y,check)
        for seed in c['readout_seeds']:
            fit_start=time.monotonic();head,losses=fit(x,base,y,seed=seed,updates=c['updates'],check=check)
            path=ROOT/f'artifacts/seed_readout_{seed}.json';sha=head.export(path,dict(parent_hash=c['parent_sha256'],source_sha256=r['source_hash'],config_sha256=r['config_sha256'],execution_sha=r['execution_sha'],seed=seed))
            head.sha256=sha;head.parent_hash=c['parent_sha256'];heads[seed]=head
            r['models'].append(dict(seed=seed,checkpoint=str(path.relative_to(ROOT)),sha256=sha,losses=losses,parameter_count=sum(p.numel() for p in head.parameters()),training_wall_s=time.monotonic()-fit_start))
        dx,db,dy=collect('development');dh=hashlib.sha256(json.dumps(r['development'],sort_keys=True).encode()).hexdigest()
        gate=SurpriseGate((dy-db).tolist(),development_hash=dh,threshold=c['surprise_threshold'])
        # This scale binds the frozen reward scorer,not the trained readout.
        r['surprise_calibration']=dict(scale=gate.scale,threshold=gate.threshold,development_hash=dh,predictor=c['parent_sha256'],auto_promotion=False)
        manifest=dict(config_sha256=r['config_sha256'],execution_sha=r['execution_sha'],source_hash=r['source_hash'],heads=[{k:m[k] for k in ('seed','checkpoint','sha256')} for m in r['models']],selection='all_three_fixed_800_update_heads_no_dev_selection',rank4='implemented_not_enabled_no_capacity_increase')
        mp=ROOT/'artifacts/seed_readout_manifest.json'
        with mp.open('x') as f:json.dump(manifest,f,indent=2,allow_nan=False)
        r['manifest_sha256']=hashlib.sha256(mp.read_bytes()).hexdigest()
        require_manifest(r,ROOT)
        for m in r['models']:
            if hashlib.sha256((ROOT/m['checkpoint']).read_bytes()).hexdigest()!=m['sha256']:raise ValueError('checkpoint_hash')
        ax,ab,ay=collect('audit');r['surprise_audit']=[]
        for i,row in enumerate(r['audit']):
            sl=slice(i*9,(i+1)*9);scores=dict(frozen=ab[sl].tolist())
            with torch.no_grad():
                for seed,head in heads.items():scores[f'readout_{seed}']=(ab[sl]+head(ax[sl])).tolist()
            row['scores']=scores;row['metrics']={k:rank_metrics(v,row['actual']) for k,v in scores.items()}
            for a in range(9):r['surprise_audit'].append(gate.observe(actual_reward=row['actual'][a],predicted_reward=row['base'][a],receipt_id=f'{row["seed"]}/{a}',phase='actual_experience'))
        for task in c['control_task_seeds']:
            r['control'][str(task)]={}
            for method in c['methods']:
                episodes=[];r['control'][str(task)][method]=episodes
                for j in range(c['control_episodes_per_task']):
                    seed=task+100+j;w=AuthoredWorld(seed);w.information_reward=False;b=Belief(model);prev=0;rng=random.Random(seed+7);e=dict(seed=seed,steps=[],return_sum=0.,success=False);episodes.append(e)
                    for t in range(c['control_steps']):
                        prop=observe(w,b,prev,t)
                        if method.startswith('readout_'):
                            imagine(9);action,info=heads[int(method[8:])].rank(model,b.h,b.z,prop,b.memory)
                        elif method=='frozen':
                            imagine(9);_,scores=features(model,b.h,b.z,prop,b.memory);action=int(scores.argmax());info={}
                        elif method=='latent_mpc':
                            imagine(48);action,info=plan(model,b.h,b.z,b.memory,seed=seed*100+t)
                        elif method=='random':action=rng.randrange(9);info={}
                        else:
                            gx=w.goal[0]-w.obj['x'];gy=w.goal[1]-w.obj['y'];action=(1 if gx>0 else 0) if gx else (3 if gy>0 else 2);info={}
                        old=dict(w.obj);charge();_,reward,done,_=w.step(action)
                        e['steps'].append(dict(before=old,after=dict(w.obj),goal=list(w.goal),action=action,reward=reward,done=done,planning=info));e['return_sum']+=reward;e['success']=done;prev=action
                        if done:break
            save()
        r['frozen_core']=all(torch.equal(v,model.state_dict()[k]) for k,v in before.items());r['frozen_bank']=torch.equal(bank,model.world_memory_bank)
        r['model_work']=dict(model.work);r['wall_s']=time.monotonic()-start;validate(r,c);r['analysis']=summarize(r);r['declared_complete']=True
    except Exception as e:
        import traceback
        r['failure']=repr(e);r['traceback']=traceback.format_exc()
    r['wall_s']=time.monotonic()-start;r['execution_debit_s']=int(r['wall_s'])+2;r['session_used_s']=c['session_used_s']+r['execution_debit_s'];r['session_remaining_s']=c['session_remaining_s']-r['execution_debit_s'];save()
    print(json.dumps({k:r.get(k) for k in ('declared_complete','failure','wall_s','authored_steps','imagined_transitions','analysis')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':run()
