"""Independent saved-data arithmetic; stdlib only, no fitting or world replay."""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import query_replication as qr
from nexus.evolution1.catalogue import digest


def verify(root=ROOT):
    c=json.loads((root/'configs/seed_query_replication.json').read_text())
    r=json.loads((root/'artifacts/seed_query_replication.json').read_text());p=qr.source_pack(root,c)
    qr.validate(r,c,p)
    if r['declared_complete'] is not True:qr.verify_offline_receipt(root,r,c)
    errors={m:[] for m in ('selected','variance','keep')};checked=0;max_error=0.
    scales={str(t):f['scale'] for f in p['frozen_folds'].values() for t in f['excluded_ids']}
    def mse(t,theta,role):
        a=r['queries'][t][role]['arrays'];s=scales[t]
        return st.mean((sum(v/k*w for v,k,w in zip(x,s,theta))-y)**2 for x,y in zip(a['x'],a['y']))
    for t in map(str,c['tasks']['train']):
        means={m:[] for m in errors}
        for b in map(str,c['budgets']):
            fixed=p['rows'][t][b];cell=r['rows'][t][b]
            select={i:st.mean(mse(t,row['theta'],'selection') for row in arms.values()) for i,arms in fixed['candidates'].items()}
            # Selection itself uses saved float32 predictions: ties/near ties
            # are checked against those recorded values, not reranked at float64.
            chosen=min(sorted(select,key=int),key=lambda i:st.mean(v['selection_mse'] for v in cell['candidates'][i].values()))
            if int(chosen)!=r['selection_manifest']['choices'][t][b]:raise ValueError('independent_choice_replay')
            for key,arms in [('keep',fixed['before'])]+list(fixed['candidates'].items()):
                actual=cell['before'] if key=='keep' else cell['candidates'][key]
                for seed,row in arms.items():
                    for role in qr.ROLES:max_error=max(max_error,abs(mse(t,row['theta'],role)-actual[seed][role+'_mse']))
                    checked+=1
            for method,key in [('selected',chosen),('variance',str(fixed['variance_index'])),('keep',None)]:
                arms=cell['before'] if key is None else cell['candidates'][key]
                means[method].append(st.mean(v['check_mse'] for v in arms.values()))
        for m in errors:errors[m].append(st.mean(means[m]))
    contrasts={}
    for m in ('variance','keep'):
        values=[a-b for a,b in zip(errors[m],errors['selected'])];mean=st.mean(values);half=2.200985160*st.stdev(values)/12**.5
        expected=r['analysis']['contrasts'][m]
        if expected['paired_task_values']!=values or abs(expected['mean']-mean)>1e-15 or max(abs(a-b) for a,b in zip(expected['ci95'],[mean-half,mean+half]))>1e-15:raise ValueError('independent_task_interval')
        contrasts[m]=dict(mean=mean,ci95=[mean-half,mean+half])
    core=json.loads((root/c['parent_model']).read_text());head=json.loads((root/c['parent_readout']).read_text())
    frozen=digest(dict(core=core['weights'],readout=head['weights'],bank=core['world_memory_bank']))
    if frozen!=r['frozen_before']['state'] or max_error>2e-6:raise ValueError('independent_frozen_or_metric_check')
    return dict(valid=True,artifact_sha256=hashlib.sha256((root/'artifacts/seed_query_replication.json').read_bytes()).hexdigest(),
        checked_cached_states=checked,max_metric_error=max_error,frozen_network_state_sha256=frozen,
        paired_contrasts=contrasts,screen_passed=r['analysis']['screen_passed'],scientific_execution=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
