"""Exclusive precommitted tiny MLP authored-development engineering pilot."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.perception import TinyCommandEncoder, VOCAB, DIRECTIONS, HIDDEN, SCHEMA, slots, features


def dataset(config, split):
    templates=config['train_templates'] if split=='training' else config['evaluation_templates']
    refs=config['train_references'] if split=='training' else config['evaluation_references']
    return [dict(text=t.format(ref=ref,hint=hint),direction=label,template=t,reference=ref)
        for t in templates for ref in refs for label in DIRECTIONS for hint in config['direction_labels'][label]]


def fit(training, config, seed, check_time):
    import torch
    from torch import nn
    from nexus.nn.factory import build_mlp
    torch.manual_seed(seed)
    trunk,width=build_mlp(len(VOCAB),(HIDDEN,),'tanh')
    model=nn.Sequential(trunk,nn.Linear(width,4))
    x=torch.tensor([features(slots(r['text'])[1]) for r in training],dtype=torch.float32)
    y=torch.tensor([DIRECTIONS.index(r['direction']) for r in training])
    optimizer=torch.optim.Adam(model.parameters(),lr=config['learning_rate'])
    losses=[]
    for step in range(config['updates']):
        check_time();optimizer.zero_grad();loss=nn.functional.cross_entropy(model(x),y)
        if not torch.isfinite(loss):raise ValueError('nonfinite_loss')
        loss.backward();optimizer.step();losses.append(float(loss.detach()))
    layer=trunk[0][0];head=model[1]
    data=dict(schema=SCHEMA,vocab=list(VOCAB),hidden=HIDDEN,labels=list(DIRECTIONS),trained=True,
        weights=dict(w1=layer.weight.detach().tolist(),b1=layer.bias.detach().tolist(),
                     w2=head.weight.detach().tolist(),b2=head.bias.detach().tolist()),
        provenance=dict(seed=seed,updates=config['updates'],source='authored_training_only'))
    return model,data,losses


def main():
    path=ROOT/'artifacts/seed_encoder_pilot.json'
    if path.exists():raise FileExistsError('consumed_pilot_no_rerun')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_precommitted_protocol_required')
    claim=ROOT/'runs/seed-encoder-pilot.claim';claim.parent.mkdir(exist_ok=True)
    with claim.open('x') as f:f.write('one run')
    start=time.perf_counter();raw=(ROOT/'configs/seed_hybrid_architecture.json').read_bytes();c=json.loads(raw)
    if c['hidden_size']!=HIDDEN or c['minimum_logit_margin']!=.5 or c['updates']!=120 or c['max_wall_s']!=30:
        raise ValueError('locked_runtime_configuration')
    result=dict(config_sha256=hashlib.sha256(raw).hexdigest(),config=c,
        execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        kind=c['kind'],declared_complete=False,rows=[],environment_interactions=0,
        python=sys.version,platform=platform.platform())
    def check_time():
        if time.perf_counter()-start>c['max_wall_s']:raise TimeoutError('30_second_cap')
    try:
        import torch
        torch.set_num_threads(1);result['torch_version']=torch.__version__
        training=dataset(c,'training');evaluation=dataset(c,'evaluation')
        result['authored_data']=dict(training=training,evaluation=evaluation)
        result['unique_authored_label_rows']=len(training)+len(evaluation)
        result['data_sha256']=hashlib.sha256(json.dumps(result['authored_data'],sort_keys=True).encode()).hexdigest()
        # Strong simple baseline learns only the eight hint->label associations
        # from the same training rows. No held-out labels inform its mapping.
        from nexus.seed.perception import DIRECTION_WORDS
        lookup={next(t for t in slots(r['text'])[1] if t in DIRECTION_WORDS):r['direction'] for r in training}
        result['training_lookup_baseline_accuracy']=sum(lookup[next(t for t in slots(r['text'])[1] if t in DIRECTION_WORDS)]==r['direction'] for r in evaluation)/len(evaluation)
        for seed in c['seeds']:
            model,data,losses=fit(training,c,seed,check_time)
            data['provenance'].update(execution_sha=result['execution_sha'],config_sha256=result['config_sha256'],data_sha256=result['data_sha256'])
            encoder=TinyCommandEncoder(data);predictions=[];maximum_error=0.
            for row in evaluation:
                check_time();tokens=slots(row['text'])[1]
                with torch.no_grad():gold=model(torch.tensor([features(tokens)],dtype=torch.float32))[0].tolist()
                scores=encoder.logits(tokens);maximum_error=max(maximum_error,max(abs(a-b) for a,b in zip(gold,scores)))
                proposal=encoder.propose(row['text'])
                predictions.append(dict(**row,proposal=proposal,correct=proposal is not None and proposal['direction']==row['direction']))
            if maximum_error>c['torch_export_tolerance']:raise ValueError('json_export_disagreement')
            model_path=ROOT/f'artifacts/seed_command_encoder_{seed}.json'
            with model_path.open('x') as f:json.dump(data,f,allow_nan=False)
            result['rows'].append(dict(seed=seed,losses=losses,predictions=predictions,
                accuracy=sum(p['correct'] for p in predictions)/len(predictions),
                parameter_count=encoder.parameter_count,maximum_export_error=maximum_error,
                checkpoint=str(model_path.relative_to(ROOT)),sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                updates=c['updates'],training_examples_processed=c['updates']*len(training)))
        result['declared_complete']=len(result['rows'])==len(c['seeds'])
        result['screen_pass']=result['declared_complete'] and all(r['accuracy']>=c['minimum_all_seed_accuracy'] for r in result['rows'])
    except Exception as exc:
        result['failure']=repr(exc)
    result['wall_s']=time.perf_counter()-start
    with path.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','authored_data','config')},indent=2))
    if not result['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
