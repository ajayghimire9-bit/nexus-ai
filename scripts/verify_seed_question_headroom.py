"""Independent saved equation replay; no new models, optimizers or environments."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from nexus.seed import question_headroom as audit
from verify_seed_question_selection import solve


def verify(root=ROOT):
    c=json.loads((root/'configs/seed_question_headroom.json').read_text());path=root/'artifacts/seed_question_headroom.json'
    r=json.loads(path.read_text());pack=audit.source_pack(root,c)
    if r['declared_complete'] is not True:raise ValueError('incomplete_headroom_evidence')
    audit.validate(r,c,pack);tasks={t['seed']:t['arrays'] for t in pack['questions']['source']['tasks']}
    dot=lambda x,y:sum(a*b for a,b in zip(x,y));worst=0.;replication=0.;count=0
    for meta in pack['questions']['source']['frozen_folds'].values():
        for tid in meta['excluded_ids']:
            a=tasks[tid];ref=pack['reference'][str(tid)]
            sx=[[v/s for v,s in zip(x,meta['scale'])] for x in a['support_x']];ox=[[v/s for v,s in zip(x,meta['scale'])] for x in a['old_x']]
            for b in c['budgets']:
                cell=r['rows'][str(tid)][str(b)];seen=ref['order'][:b-1]
                for i,arms in cell['candidates'].items():
                    index=int(i);x=ox+[sx[j] for j in seen+[index]];y=a['old_y']+[a['support_y'][j] for j in seen+[index]]
                    gram=[[dot(v,w)+(.1 if p==q else 0) for q,w in enumerate(x)] for p,v in enumerate(x)]
                    for seed,row in arms.items():
                        initial=ref['paths'][seed][0]['theta'];coef=solve(gram,[v-dot(z,initial) for z,v in zip(x,y)])
                        expected=[v+sum(z[j]*alpha for z,alpha in zip(x,coef)) for j,v in enumerate(initial)]
                        worst=max(worst,max(abs(v-w) for v,w in zip(expected,row['proposal'])));count+=1
                        if index==cell['variance_index']:
                            before=ref['paths'][seed][b]
                            replication=max(replication,max(abs(v-w) for v,w in zip(before['theta'],row['theta'])))
                            replication=max(replication,abs(before['query_mse']-row['query_mse']),abs(before['retention_mse']-row['retention_mse']))
    if worst>2e-6 or replication>2e-6 or count!=756:raise ValueError('independent_counterfactual_arithmetic')
    expected=audit.resources(0)
    if set(r['resources'])!=set(expected) or any(type(r['resources'][k]) is not int or r['resources'][k]!=v for k,v in expected.items() if k!='cpu_s'):
        raise ValueError('independent_headroom_resources')
    return dict(valid=True,raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),checked_counterfactuals=count,
        max_posterior_error=worst,max_prior_choice_error=replication,label=r['analysis']['label'],
        cross_state_pass=r['analysis']['cross_state_pass'],frozen_state_preserved=True,scientific_execution=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
