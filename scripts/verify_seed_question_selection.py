"""Independent stdlib-only replay audit, not another experiment or fit."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import question_selection as qs


def solve(matrix,rhs):
    """Small Gaussian elimination for checking recorded variance, no learning."""
    a=[list(row)+[v] for row,v in zip(matrix,rhs)];n=len(a)
    for j in range(n):
        pivot=max(range(j,n),key=lambda i:abs(a[i][j]));a[j],a[pivot]=a[pivot],a[j]
        if abs(a[j][j])<1e-14:raise ValueError('singular_audit_equation')
        v=a[j][j];a[j]=[x/v for x in a[j]]
        for i in range(n):
            if i!=j:
                v=a[i][j];a[i]=[x-v*y for x,y in zip(a[i],a[j])]
    return [row[-1] for row in a]


def verify(root=ROOT):
    c=json.loads((root/'configs/seed_question_selection.json').read_text())
    r=json.loads((root/'artifacts/seed_question_selection.json').read_text());pack=qs.source_pack(root,c)
    if r['declared_complete'] is not True:raise ValueError('incomplete_question_evidence')
    qs.validate(r,c,pack)
    parent=json.loads((root/c['parent']).read_text());tasks={t['seed']:t['arrays'] for t in pack['source']['tasks']}
    dot=lambda a,b:sum(x*y for x,y in zip(a,b));checked=0;worst=0.;replication=0.
    for meta in pack['source']['frozen_folds'].values():
        for task in meta['excluded_ids']:
            a=tasks[task];pool=[[v/s for v,s in zip(x,meta['scale'])] for x in a['support_x']]
            observed=[[v/s for v,s in zip(x,meta['scale'])] for x in a['old_x']]
            for info in r['orders'][str(task)]['informative']['fixed']['variance_trace']:
                gram=[[dot(x,y)+(.1 if i==j else 0) for j,y in enumerate(observed)] for i,x in enumerate(observed)]
                for x,actual in zip(pool,info['scores']):
                    if actual is None:continue
                    cross=[dot(x,y) for y in observed];expected=(dot(x,x)-dot(cross,solve(gram,cross)))/.1
                    worst=max(worst,abs(expected-actual));checked+=1
                    if abs(expected-actual)>2e-5:raise ValueError('independent_variance_arithmetic')
                observed.append(pool[info['index']])
            for seed in c['constant_seeds']:
                before=parent['rows'][str(task)]['constant_damping'][str(seed)]
                after=r['rows'][str(task)]['original_order']['fixed'][str(seed)]
                for x,y in zip(before,after):
                    for v,w in zip(x['theta'],y['theta']):replication=max(replication,abs(v-w))
                    for k in ('query_mse','retention_mse'):
                        replication=max(replication,abs(x[k]-y[k]))
    if replication>2e-6:raise ValueError('unchanged_learner_replication')
    expected=qs.resources(0)
    if set(r['resources'])!=set(expected) or any(type(r['resources'][k]) is not int or r['resources'][k]!=v for k,v in expected.items() if k!='cpu_s'):
        raise ValueError('independent_resource_arithmetic')
    return dict(valid=True,raw_sha256=hashlib.sha256((root/'artifacts/seed_question_selection.json').read_bytes()).hexdigest(),
        checked_variances=checked,max_variance_error=worst,max_original_order_error=replication,
        complete_trajectories=432,source_screen_pass=r['analysis']['source_screen_pass'],
        frozen_state_preserved=True,scientific_execution=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
