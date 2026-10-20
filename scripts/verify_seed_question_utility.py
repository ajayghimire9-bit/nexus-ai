"""Read-only independent numeric audit; no fitting or neural imports."""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from nexus.seed import question_utility as q
from verify_seed_question_selection import solve


def verify(root=ROOT):
    c=json.loads((root/'configs/seed_question_utility.json').read_text());r=json.loads((root/'artifacts/seed_question_utility.json').read_text());p=q.source_pack(root,c)
    if r['declared_complete'] is not True:raise ValueError('incomplete_question_learning')
    out=dict(adapter='seed_question_utility_v1',study=r,resources=r['resources'],model=dict(schema='seed_question_utility_models_v1',folds={f:v['models'] for f,v in r['folds'].items()}))
    q.validate_output(out,c,dict(cpu_s=c['max_wall_s']),p)
    checked=0;worst=0.;dot=lambda a,b:sum(v*w for v,w in zip(a,b))
    for fid,fold in r['folds'].items():
        scale=p['frozen_folds'][fid]['scale']
        for tid in map(str,fold['train_ids']+fold['excluded_ids']):
            a=p['tasks'][tid]['arrays'];pool=[[v/s for v,s in zip(x,scale)] for x in a['support_x']];anchors=[[v/s for v,s in zip(x,scale)] for x in a['old_x']]
            refs=fold['training_references'][tid] if int(tid) in fold['train_ids'] else p['reference'][tid]
            cases=fold['training_cases'][tid] if int(tid) in fold['train_ids'] else fold['held_cases'][tid]
            for b,rows in cases.items():
                seen=refs['order'][:int(b)-1];observed=anchors+[pool[i] for i in seen]
                gram=[[dot(x,y)+(.1 if i==j else 0) for j,y in enumerate(observed)] for i,x in enumerate(observed)]
                for i,row in rows.items():
                    x=pool[int(i)];cross=[dot(x,y) for y in observed];expected=(dot(x,x)-dot(cross,solve(gram,cross)))/.1
                    err=abs(expected-row['variance']);worst=max(worst,err);checked+=1
                    if err>2e-5:raise ValueError('independent_question_variance')
    contrast={}
    for baseline in ('variance','action_mean','keep'):
        values=[]
        for t in c['tasks']['train']:
            fold=r['folds'][str(c['tasks']['train'].index(t)%4)];cells=fold['evaluation'][str(t)]
            values.append(st.mean(v['query_mse'][baseline] for v in cells.values())-st.mean(v['query_mse']['learned'] for v in cells.values()))
        mean=st.mean(values);half=2.200985160*st.stdev(values)/12**.5;expected=r['analysis']['contrasts'][baseline]
        if values!=expected['paired_task_values'] or abs(mean-expected['mean'])>1e-15 or max(abs(v-w) for v,w in zip([mean-half,mean+half],expected['ci95']))>1e-15:raise ValueError('independent_question_interval')
        contrast[baseline]=dict(mean=mean,ci95=[mean-half,mean+half])
    return dict(valid=True,raw_sha256=hashlib.sha256((root/'artifacts/seed_question_utility.json').read_bytes()).hexdigest(),
        checked_variances=checked,max_variance_error=worst,paired_contrasts=contrast,
        source_screen_pass=r['analysis']['source_screen_pass'],frozen_state_preserved=True,scientific_execution=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
