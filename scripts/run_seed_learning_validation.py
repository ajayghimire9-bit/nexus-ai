"""One locked fresh Seed validation run; no GRU fitting or historical reruns."""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
import torch
from nexus.seed.learning_benchmark import collect_task,scaled,scale_features,curve,rollout,METHODS,LEARNING_METHODS,WORK
from nexus.seed.plasticity import PlasticityController
from nexus.seed.semantic_lessons import task as meaning_task,evaluate as meaning_evaluate,instruction_audit
from nexus.seed.learning_selection import episode as selection_episode
from nexus.seed.grounded_meta import OuterSeedMeta
from nexus.seed.list_transfer import evaluate as transfer_evaluate
from nexus.seed.action_ranking import rank_metrics
from nexus.world.seed_rssm import SeedRSSM
ROOT=Path(__file__).resolve().parents[1]


def run():
    out=ROOT/'artifacts/seed_learning_validation.json'
    if out.exists():raise ValueError('one_run_consumed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('clean_precommitted_protocol_required')
    c=json.loads((ROOT/'configs/seed_learning_validation.json').read_text());start=time.monotonic();torch.set_num_threads(1)
    r=dict(schema='seed_learning_validation_result_v1',config=c,config_sha256=hashlib.sha256((ROOT/'configs/seed_learning_validation.json').read_bytes()).hexdigest(),execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),declared_complete=False,
        costs={},tasks={},controllers=[],meaning=[],selection=[],control={},transfer=dict(status='blocked_pending_object_gates'))
    model=None
    def check():
        if time.monotonic()-start>=min(c['max_wall_s'],c['carried_session_remaining_s']):raise TimeoutError('locked_execution_cap')
        if WORK.get('imagined_rows',0)>c['max_imagined_transitions']:raise ValueError('imagined_cap')
    def charge(role,n=1):
        check()
        if sum(r['costs'].values())+n>c['max_authored_interactions']:raise ValueError('interaction_cap')
        r['costs'][role]=r['costs'].get(role,0)+n
    def save():out.write_text(json.dumps(r,indent=2,allow_nan=False))
    try:
        model,_=SeedRSSM.load(ROOT/c['parent_model'],c['parent_sha256']);before={k:v.clone() for k,v in model.state_dict().items()};bank=model.world_memory_bank.clone()
        tasks={}
        for split,seeds in c['task_seeds'].items():
            tasks[split]=[];r['tasks'][split]=[]
            for seed in seeds:
                t,raw=collect_task(model,seed,charge,check);tasks[split].append(t);r['tasks'][split].append(raw)
        scale=scale_features(torch.cat([x for t in tasks['train'] for x in (t.support_x,t.old_x)]));r['feature_scale']=scale.tolist()
        tasks={k:[scaled(t,scale) for t in v] for k,v in tasks.items()};controllers=[];weights={}
        for seed in c['controller_seeds']:
            check();torch.manual_seed(seed);rng=random.Random(seed);m=PlasticityController();opt=torch.optim.Adam(m.parameters(),lr=c['meta_lr']);tr=[]
            for step in range(c['meta_updates']):
                t=tasks['train'][rng.randrange(len(tasks['train']))];rows,_=curve(t,m,'learned',check)
                loss=torch.stack([e+.5*f.clamp(min=0) for _,e,f in rows]).mean()
                opt.zero_grad();loss.backward();grad=sum(float(p.grad.square().sum()) for p in m.parameters())**.5
                if not torch.isfinite(loss) or not grad<float('inf'):raise ValueError('nonfinite_outer_step')
                opt.step();tr.append(dict(step=step+1,loss=float(loss.detach()),gradient_norm=grad))
            path=ROOT/'artifacts'/f'seed_validation_controller_{seed}.json'
            sha=m.export(path,dict(execution_sha=r['execution_sha'],seed=seed,parent=c['parent_sha256'],config_sha256=r['config_sha256']))
            m.eval()
            for p in m.parameters():p.requires_grad_(False)
            controllers.append(m);record=dict(seed=seed,training=tr,checkpoint=str(path.relative_to(ROOT)),sha256=sha,curves={})
            for split,group in tasks.items():
                record['curves'][split]=[]
                for i,t in enumerate(group):
                    methods={}
                    for method in LEARNING_METHODS:
                        rows,snaps=curve(t,m,method,check);scores=[]
                        for k,error,forget in rows:
                            theta=snaps[k];ranking=[]
                            for j,raw in enumerate(r['tasks'][split][i]['records']['query']):
                                pred=(torch.tensor(raw['base'])+t.query_x[j*9:(j+1)*9]@theta).tolist()
                                ranking.append(dict(predicted=pred,metrics=rank_metrics(pred,raw['actual'])))
                            scores.append(dict(budget=k,query_mse=float(error),forgetting=float(forget),ranking=ranking))
                        methods[method]=scores
                        if split=='audit':weights[(seed,i,method)]=snaps[8]
                    record['curves'][split].append(dict(seed=c['task_seeds'][split][i],methods=methods))
            r['controllers'].append(record);save()
        # Fresh closed-loop episodes; no learning from evaluation outcomes.
        for i,seed in enumerate(c['task_seeds']['audit']):
            goal=r['tasks']['audit'][i]['goal'];cell={}
            for ci,mseed in enumerate(c['controller_seeds']):
                for method in METHODS:
                    cell[f'{mseed}/{method}']=[rollout(model,seed+1000+j,goal,weights[(mseed,i,method)],scale,charge,check,c['control_steps']) for j in range(c['control_episodes'])]
            for method in ('frozen','grid'):
                cell[method]=[rollout(model,seed+1000+j,goal,torch.zeros(62),scale,charge,check,c['control_steps'],grid=method=='grid') for j in range(c['control_episodes'])]
            r['control'][str(seed)]=cell;save()
        # Separate semantic task records; teacher outcomes never enter features.
        lessons=[]
        for i,seed in enumerate(c['meaning_seeds']):
            check();l=meaning_task(model,seed,'unary' if i<6 else 'relation',i);charge('meaning_labels',18);lessons.append(l)
        demonstrations=None
        for ci,m in enumerate(controllers):
            instructions=instruction_audit(model,m,c['instruction_seed'],demonstrations)
            demonstrations=instructions['support']
            r['meaning'].append(dict(controller_seed=c['controller_seeds'][ci],tasks=[meaning_evaluate(l,m) for l in lessons],instructions=instructions))
        charge('instruction_demonstrations',32) # same demonstration bank reused
        # Existing meta-controller sees only separately paid source probes.
        train=[];audit=[]
        for split,seeds in [('train',c['selector_train_seeds']),('audit',c['selector_audit_seeds'])]:
            group=train if split=='train' else audit
            for i,seed in enumerate(seeds):
                check();l=meaning_task(model,seed,'unary',i);charge('selector_authored_label_bank',18);group.append(l)
        for ci,m in enumerate(controllers):
            meta=OuterSeedMeta()
            for l in train:check();selection_episode(l,m,meta,'adaptive',training=True)
            policies={mode:[selection_episode(l,m,meta,mode) for l in audit] for mode in ('adaptive','random','fixed')}
            r['selection'].append(dict(controller_seed=c['controller_seeds'][ci],source_journal=[dict(kind=e.kind,payload=json.loads(e.payload_json),fingerprint=e.fingerprint) for e in meta.journal.snapshot()],policies=policies))
        from nexus.seed.learning_validation_audit import summarize,validate
        r['screens']=summarize(r)
        gates={k:r['screens'][k]['passed'] for k in ('learning','actions')}
        if all(gates.values()):
            rows=transfer_evaluate(controllers,c['transfer_seeds'],gates,check);charge('list_teaching_and_query_labels',len(rows)*16)
            r['transfer']=dict(status='executed_after_object_success',rows=rows)
        else:r['transfer']=dict(status='not_run_object_success_gate_failed',gates=gates)
        r['frozen_core']=all(torch.equal(before[k],v) for k,v in model.state_dict().items()) and torch.equal(bank,model.world_memory_bank)
        r['model_work']=dict(model.work);r['update_work']=dict(WORK);r['wall_s']=time.monotonic()-start
        validate(r,c);r['declared_complete']=True
    except Exception as e:
        import traceback
        r['failure']=repr(e);r['traceback']=traceback.format_exc()
    r['wall_s']=time.monotonic()-start;r['execution_debit_s']=int(r['wall_s'])+2
    r['session_used_s']=c['carried_session_used_s']+r['execution_debit_s'];r['session_remaining_s']=c['carried_session_remaining_s']-r['execution_debit_s']
    save();print(json.dumps({k:r.get(k) for k in ('declared_complete','failure','wall_s','costs','screens','session_remaining_s')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':run()
