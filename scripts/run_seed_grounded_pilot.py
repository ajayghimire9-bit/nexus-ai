"""Exclusive bounded authored pilot. Commit protocol and implementation first."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import platform
import resource
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    output=ROOT/'artifacts/seed_grounded_pilot.json'
    if output.exists():raise FileExistsError('consumed_grounded_pilot')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_protocol_commit_required')
    start=time.perf_counter();raw=(ROOT/'configs/seed_grounded_pilot.json').read_bytes();c=json.loads(raw)
    from nexus.seed.grounded_audit import validate,validate_config
    validate_config(c)
    claim=ROOT/'runs/seed-grounded.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write('one run')
    result=dict(config=c,config_sha256=hashlib.sha256(raw).hexdigest(),
        execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        models=[],authored_world_steps=0,imagined_transitions=0,declared_complete=False)
    def check():
        if time.perf_counter()-start>c['max_wall_s']:raise TimeoutError('grounded_pilot_time_cap')
    def charge():
        check()
        if result['authored_world_steps']>=c['max_authored_steps']:raise ValueError('authored_interaction_cap')
        result['authored_world_steps']+=1
    def imagine_charge(n):
        check()
        if result['imagined_transitions']+n>c['max_imagined_transitions']:raise ValueError('imagined_transition_cap')
        result['imagined_transitions']+=n
    training=[];queries=[]
    serialize=lambda eps:[dict(seed=e['seed'],steps=e['steps']) for e in eps]
    try:
        import torch
        torch.set_num_threads(1)
        result['runtime']=dict(python=platform.python_version(),torch=torch.__version__,platform=platform.platform(),device='cpu',torch_threads=torch.get_num_threads())
        from nexus.seed.grounded_training import collect,train,prediction_metrics,evaluate_control
        from nexus.seed.grounded_meta import OuterSeedMeta
        collect(c['training_seeds'],c['source_episode_steps'],charge,training)
        collect(c['prediction_seeds'],c['source_episode_steps'],charge,queries)
        result['source_episodes']=serialize(training);result['prediction_episodes']=serialize(queries)
        result['source_data_sha256']=hashlib.sha256(json.dumps(result['source_episodes'],sort_keys=True).encode()).hexdigest()
        result['query_data_sha256']=hashlib.sha256(json.dumps(result['prediction_episodes'],sort_keys=True).encode()).hexdigest()
        meta=OuterSeedMeta()
        for name in c['recipes']:
            check();recipe=meta.propose(in_episode=False,remaining_s=c['max_wall_s']-(time.perf_counter()-start),remaining_steps=c['max_authored_steps']-result['authored_world_steps'])
            if recipe.name!=name:raise ValueError('registered_recipe_schedule')
            result['current_training']=dict(recipe=name,updates=[])
            fit_start=time.perf_counter()
            model,train_metrics=train(recipe,training,c,check,lambda row:result['current_training']['updates'].append(row))
            train_metrics['wall_s']=time.perf_counter()-fit_start
            meta.reveal(recipe,dict(id='training-'+name,observed_training_loss=train_metrics['losses'][-1]['total']),phase='training')
            path=ROOT/f'artifacts/seed_grounded_{name}.json'
            sha=model.export(path,dict(execution_sha=result['execution_sha'],config_sha256=result['config_sha256'],source_data_sha256=result['source_data_sha256'],recipe=name))
            record=dict(recipe=name,checkpoint=str(path.relative_to(ROOT)),sha256=sha,training=train_metrics,control={})
            result['models'].append(record)
            record['prediction']=prediction_metrics(model,queries);check()
            for method in c['methods']:
                record['control'][method]=[]
                evaluate_control(model,c['control_seeds'],c['control_episode_steps'],method,charge,check,record['control'][method],imagine_charge)
            before=json.loads(path.read_text())['weights']
            record['frozen_evaluation']=before=={k:v.detach().tolist() for k,v in model.state_dict().items()}
            if not record['frozen_evaluation']:raise ValueError('evaluation_changed_model')
            record['measured_model_work']=dict(model.work)
        result['outer_history']=[e.__dict__ for e in meta.journal.snapshot()]
        result['wall_s']=time.perf_counter()-start
        validate(result,ROOT);result['declared_complete']=True
    except Exception as exc:
        result['failure']=repr(exc);result['traceback']=traceback.format_exc()
    result['source_episodes']=serialize(training);result['prediction_episodes']=serialize(queries)
    result['wall_s']=time.perf_counter()-start
    result['peak_process_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('config','models','source_episodes','prediction_episodes','outer_history')},indent=2))
    if not result['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
