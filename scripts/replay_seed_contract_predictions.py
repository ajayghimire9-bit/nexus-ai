"""Exclusive frozen saved-state inference recovery; no new world steps/fits."""
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


if __name__=='__main__':
    output=ROOT/'artifacts/seed_contract_prediction_replay.json'
    if output.exists():raise FileExistsError('consumed_prediction_replay')
    start=time.perf_counter()
    import torch
    torch.set_num_threads(1)
    from nexus.seed.contract_audit import validate,verify_files
    from nexus.seed.grounded_world import AuthoredWorld,tensors
    from nexus.seed.state_contract import Belief
    from nexus.world.seed_rssm import SeedRSSM
    from nexus.seed.action_ranking import rank_metrics
    raw=(ROOT/'artifacts/seed_contract_study.json').read_bytes();study=json.loads(raw);validate(study);verify_files(study,ROOT,local_checkpoints=True)
    result=dict(parent_result_sha256=hashlib.sha256(raw).hexdigest(),rows=[],real_steps=0,imagined_transitions=0,declared_complete=False)
    try:
        for m in study['models']:
            model,_=SeedRSSM.load(ROOT/m['checkpoint'],m['sha256'])
            for s in study['ranking']:
                if time.perf_counter()-start>60:raise TimeoutError('prediction_replay_60s_cap')
                w=AuthoredWorld(s['seed']);w.obj=dict(s['before']);w.goal=tuple(s['goal']);w.information_reward=False
                with torch.no_grad():
                    e=model.encode(*tensors([w.observe()]));b=Belief(model);b.observe(e,torch.zeros(1,dtype=torch.long),0)
                    h,z,_,_=model.transition(b.h.expand(9,-1),b.z.expand(9,-1),torch.arange(9),b.memory.expand(9,-1));pred=model.heads(h,z)
                result['imagined_transitions']+=9
                scores=pred['reward'].tolist();actual=[o['reward'] for o in s['outcomes']];metrics=rank_metrics(scores,actual);old=s['models'][m['identity']]['reward']
                if any(abs(metrics[k]-old[k])>1e-7 for k in metrics):raise ValueError('saved_metric_replay_mismatch')
                result['rows'].append(dict(identity=m['identity'],seed=s['seed'],scores=scores,predicted_next_state=pred['state'].tolist(),metrics_match=True))
        if len(result['rows'])!=18*64 or result['imagined_transitions']!=10368:raise ValueError('complete_replay_grid')
        result['declared_complete']=True
    except Exception as e:result['failure']=repr(e)
    result['wall_s']=time.perf_counter()-start
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    if not result['declared_complete']:raise SystemExit(1)
