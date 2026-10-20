"""Single registered development diagnostic; never retrains saved models."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    path=ROOT/'artifacts/seed_action_ranking.json'
    if path.exists():raise FileExistsError('consumed_action_ranking')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_protocol_required')
    from nexus.seed.action_ranking import hash_file
    c=json.loads((ROOT/'configs/seed_action_ranking.json').read_text())
    if hash_file(ROOT/'artifacts/seed_grounded_pilot.json')!=c['parent_receipt_sha256']:raise ValueError('parent_receipt_hash')
    claim=ROOT/'runs/action-ranking.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write('single development diagnostic')
    start=time.perf_counter();r=dict(config=c,config_sha256=hash_file(ROOT/'configs/seed_action_ranking.json'),execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),states=[],authored_steps=0,declared_complete=False)
    def check():
        if time.perf_counter()-start>c['max_wall_s']:raise TimeoutError('diagnostic_wall_cap')
    def charge():
        check()
        if r['authored_steps']>=c['max_authored_steps']:raise ValueError('diagnostic_interaction_cap')
        r['authored_steps']+=1
    try:
        import torch
        torch.set_num_threads(1)
        from nexus.world.seed_rssm import SeedRSSM
        from nexus.seed.action_ranking import registered_world,outcomes,predict,rank_metrics,validate_diagnostic
        receipt=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text());models={};before={}
        for m in receipt['models']:
            models[m['recipe']],_=SeedRSSM.load(ROOT/m['checkpoint'],m['sha256'])
            before[m['recipe']]=copy.deepcopy(models[m['recipe']].state_dict())
        for i in range(c['states']):
            check();seed=c['state_seed_start']+i;world=registered_world(seed,i)
            row=dict(seed=seed,group='boundary' if i%2==0 else 'interior',before=dict(world.obj),goal=list(world.goal),outcomes=outcomes(world,charge),models={});r['states'].append(row)
            actual=[o['reward'] for o in row['outcomes']]
            for name,model in models.items():
                prediction=predict(model,world)
                metrics=dict(reward=rank_metrics(prediction['reward'],actual),reward_plus_value=rank_metrics([a+.9*b for a,b in zip(prediction['reward'],prediction['value'])],actual))
                row['models'][name]=dict(prediction=prediction,metrics=metrics)
        r['frozen']={name:all(torch.equal(v,models[name].state_dict()[k]) for k,v in state.items()) for name,state in before.items()}
        r['model_work']={name:model.work for name,model in models.items()}
        validate_diagnostic(r);r['declared_complete']=True
    except Exception as e:r['failure']=repr(e)
    r['wall_s']=time.perf_counter()-start
    with path.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in r.items() if k not in ('states','config','model_work')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
