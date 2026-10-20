"""Independent saved arithmetic audit: no training, inference or collection."""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from nexus.seed import answer_free_utility as q
from verify_seed_question_selection import solve


def verify(root=ROOT):
    c=json.loads((root/'configs/seed_answer_free_utility.json').read_text());r=json.loads((root/'artifacts/seed_answer_free_utility.json').read_text());p=q.source_pack(root,c)
    q.validate_output(dict(adapter=q.SCHEMA,study=r,resources=r['resources'],model={'folds':{f:v['model'] for f,v in r['folds'].items()}}),c,{'cpu_s':60},p)
    dot=lambda a,b:sum(x*y for x,y in zip(a,b));count=0;worst=0.
    for fid,f in r['folds'].items():
        scale=p['frozen_folds'][fid]['scale']
        for tid in map(str,f['train_ids']+f['excluded_ids']):
            a=p['tasks'][tid]['arrays'];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']]
            ref=f['training_references'][tid] if int(tid) in f['train_ids'] else p['reference'][tid]
            cases=f['training_cases'][tid] if int(tid) in f['train_ids'] else f['held_cases'][tid]
            for b,rows in cases.items():
                observed=ox+[sx[i] for i in ref['order'][:int(b)-1]]
                gram=[[dot(x,y)+(.1 if i==j else 0.) for j,y in enumerate(observed)] for i,x in enumerate(observed)]
                for i,row in rows.items():
                    x=sx[int(i)];cross=[dot(x,y) for y in observed]
                    expected=(dot(x,x)-dot(cross,solve(gram,cross)))/.1
                    error=abs(expected-row['variance']);count+=1;worst=max(worst,error)
                    if error>2e-5:raise ValueError('independent_answer_free_variance')
    per={}
    for t in c['tasks']['train']:
        f=r['folds'][str(c['tasks']['train'].index(t)%4)];cells=f['evaluation'][str(t)]
        per[str(t)]={m:sum(cells[str(b)]['query_mse'][m] for b in (1,2,4))/3 for m in q.METHODS}
    means={m:sum(v[m] for v in per.values())/12 for m in q.METHODS}
    if any(abs(v-r['analysis']['primary_means'][m])>1e-15 for m,v in means.items()):raise ValueError('independent_answer_free_means')
    contrasts={}
    for m in ('variance','uniform','original_order','keep','source_mean'):
        values=[per[str(t)][m]-per[str(t)]['learned'] for t in c['tasks']['train']];mean=sum(values)/12
        half=2.200985160*st.stdev(values)/12**.5;ci=[mean-half,mean+half];saved=r['analysis']['contrasts'][m]
        if max(abs(v-w) for v,w in zip(ci,saved['ci95']))>1e-15:raise ValueError('independent_answer_free_interval')
        contrasts[m]={'mean':mean,'ci95':ci}
    return dict(valid=True,raw_sha256=hashlib.sha256((root/'artifacts/seed_answer_free_utility.json').read_bytes()).hexdigest(),
        checked_variances=count,max_variance_error=worst,primary_means=means,paired_contrasts=contrasts,
        complete_grid=True,frozen_preserved=True,source_screen_pass=r['analysis']['source_screen_pass'],scientific_execution=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
