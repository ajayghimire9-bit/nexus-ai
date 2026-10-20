"""One fresh frozen-readout spatial transfer test; no fitting or selection."""
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
import torch
from nexus.seed.action_readout import ActionReadout,features
from nexus.seed.action_ranking import rank_metrics
from nexus.seed.grounded_world import tensors
from nexus.seed.state_contract import Belief
from nexus.seed.latent_planner import plan
from nexus.seed.spatial_transfer import world,identity,closed_initials,validate,summarize
from nexus.world.seed_rssm import SeedRSSM
ROOT=Path(__file__).resolve().parents[1]


def run():
    dest=ROOT/'artifacts/seed_spatial_transfer.json'
    if dest.exists():raise ValueError('one_run_consumed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('precommitted_protocol_required')
    cfg=ROOT/'configs/seed_spatial_transfer.json';c=json.loads(cfg.read_text());start=time.monotonic();torch.set_num_threads(1)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    r=dict(config=c,config_sha256=sha(cfg),execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),declared_complete=False,ranking={},control={},authored_steps=0,imagined_transitions=0)
    def check():
        if time.monotonic()-start>min(c['max_wall_s'],c['carried_remaining_s']):raise TimeoutError('transfer_time_cap')
    def charge():
        check()
        if r['authored_steps']>=c['max_authored_steps']:raise ValueError('real_cap')
        r['authored_steps']+=1
    def imagine(n):
        check()
        if r['imagined_transitions']+n>c['max_imagined_transitions']:raise ValueError('imagined_cap')
        r['imagined_transitions']+=n
    def save():dest.write_text(json.dumps(r,indent=2,allow_nan=False))
    model=None
    try:
        for name in ('parent_results','parent_manifest','parent_model'):
            key='parent_sha256' if name=='parent_model' else name+'_sha256'
            if sha(ROOT/c[name])!=c[key]:raise ValueError('parent_hash_'+name)
        parent=json.loads((ROOT/c['parent_results']).read_text());manifest=json.loads((ROOT/c['parent_manifest']).read_text())
        if [h['seed'] for h in manifest['heads']]!=c['head_seeds']:raise ValueError('locked_head_seeds')
        model,_=SeedRSSM.load(ROOT/c['parent_model'],c['parent_sha256']);before=copy.deepcopy(model.state_dict());bank=model.world_memory_bank.clone()
        heads={h['seed']:ActionReadout.load(ROOT/h['checkpoint'],h['sha256'],c['parent_sha256']) for h in manifest['heads']};head_before={s:copy.deepcopy(h.state_dict()) for s,h in heads.items()}
        used=closed_initials(parent);r['closed_initials']=[list(t) for t in sorted(used)];r['checkpoint_manifest']=manifest
        def observed(w,b,prev=0,t=0):
            check()
            args=tensors([w.observe()])
            with torch.no_grad():b.observe(model.encode(*args),torch.tensor([prev]),t)
            return args[2]
        for gi,g in enumerate(c['groups']):
            r['ranking'][g]=[];r['control'][g]={}
            for i in range(c['ranking_states_per_group']):
                seed=c['ranking_seed_start']+gi*10000+i;w=world(seed,g,used);used.add(identity(w.obj,w.goal));b=Belief(model);prop=observed(w,b);imagine(9);x,base=features(model,b.h,b.z,prop,b.memory)
                actual=[]
                for a in range(9):other=copy.deepcopy(w);charge();_,reward,_,_=other.step(a);actual.append(reward)
                scores={'frozen':base.tolist()}
                with torch.no_grad():
                    for s,h in heads.items():scores[f'readout_{s}']=(base+h(x)).tolist()
                r['ranking'][g].append(dict(seed=seed,before=dict(w.obj),goal=list(w.goal),actual=actual,scores=scores,metrics={m:rank_metrics(v,actual) for m,v in scores.items()}))
            for stream in range(c['streams']):
                initials=[]
                for j in range(c['episodes_per_stream']):
                    seed=c['control_seed_start']+gi*10000+stream*100+j;w=world(seed,g,used);used.add(identity(w.obj,w.goal));initials.append((seed,w))
                cells={};r['control'][g][str(stream)]=cells
                for method in c['methods']:
                    cells[method]=[]
                    for seed,initial in initials:
                        w=copy.deepcopy(initial);b=Belief(model);prev=0;rng=random.Random(seed+7);e=dict(seed=seed,steps=[],return_sum=0.,success=False);cells[method].append(e)
                        for t in range(c['episode_steps']):
                            check();prop=observed(w,b,prev,t)
                            if method.startswith('readout_'):imagine(9);a,info=heads[int(method[8:])].rank(model,b.h,b.z,prop,b.memory)
                            elif method=='frozen':imagine(9);_,base=features(model,b.h,b.z,prop,b.memory);a=int(base.argmax());info={}
                            elif method=='latent_mpc':imagine(48);a,info=plan(model,b.h,b.z,b.memory,seed=seed*100+t)
                            elif method=='random':a=rng.randrange(9);info={}
                            else:
                                dx=w.goal[0]-w.obj['x'];dy=w.goal[1]-w.obj['y'];a=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2);info={}
                            old=dict(w.obj);charge();_,reward,done,_=w.step(a);e['steps'].append(dict(before=old,after=dict(w.obj),goal=list(w.goal),action=a,reward=reward,done=done,planning=info));e['return_sum']+=reward;e['success']=done;prev=a
                            if done:break
            save()
        r['frozen_core']=all(torch.equal(v,model.state_dict()[k]) for k,v in before.items());r['frozen_bank']=torch.equal(bank,model.world_memory_bank)
        r['frozen_readouts']=all(torch.equal(v,heads[s].state_dict()[k]) for s,d in head_before.items() for k,v in d.items())
        r['model_work']=dict(model.work);r['wall_s']=time.monotonic()-start;validate(r,c);r['analysis']=summarize(r);r['declared_complete']=True
    except Exception as e:
        import traceback
        r['failure']=repr(e);r['traceback']=traceback.format_exc()
    if model is not None:r['model_work']=dict(model.work)
    r['wall_s']=time.monotonic()-start;r['execution_debit_s']=int(r['wall_s'])+2;r['session_used_s']=c['carried_used_s']+r['execution_debit_s'];r['session_remaining_s']=c['carried_remaining_s']-r['execution_debit_s'];save()
    print(json.dumps({k:r.get(k) for k in ('declared_complete','failure','wall_s','authored_steps','imagined_transitions','analysis')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':run()
