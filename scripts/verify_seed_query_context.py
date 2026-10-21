"""Independent outcome-branch arithmetic on saved source-only audit cells."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import source_acquisition as a,query_context as q
from nexus.evolution1.catalogue import digest


def verify(root=ROOT):
    raw=(root/'artifacts/seed_query_context.json').read_bytes();r=json.loads(raw);c=r['config'];q.config_check(c)
    pack=q.source_pack(root);q.validate_cells(r['rows'],c,pack)
    assert r['declared_complete'] is True
    # Independent parity truth table, no runtime interpreter.
    import itertools
    monomials=[term for k in (1,2,3) for term in itertools.combinations(range(4),k)]
    table=np.asarray([[bool(sum(all(x&(1<<i) for i in term) for term in terms)%2)^neg for x in range(16)]
        for k in (2,3) for terms in itertools.combinations(monomials,k) for neg in (False,True)],bool)
    source={s['task']:s for b in pack for s in b['source']};blocks={b['id']:b for b in pack}
    matrix_entries=0;covariance_ops=0
    for row in r['rows']:
        pool,query=a.split_inputs(row['task']);order=list(range(8))
        import random
        random.Random(row['task']+700).shuffle(order)
        seen=[(pool[i],source[row['task']]['answers'][pool[i]]) for i in order[:row['prefix']]]
        mask=np.ones(910,bool)
        for x,y in seen:
            matrix_entries+=int(mask.sum());mask &= table[:,x]==y
        t=table[mask];candidates=[x for x in pool if x not in {x for x,_ in seen}]
        assert candidates==row['candidates'] and len(t)==row['posterior_size'] and digest(seen)==digest(row['observed'])
        values=t[:,query].astype(float);before=np.mean((values-values.mean(axis=0))**2,axis=0);g=[];feats=[]
        for x in candidates:
            after=np.zeros(8)
            for answer in (False,True):
                sub=values[t[:,x]==answer]
                if len(sub):after+=len(sub)/len(t)*np.mean((sub-sub.mean(axis=0))**2,axis=0)
            g.append(before-after)
            p=float(t[:,x].mean());feats.append([1.]+[float(bool(x&(1<<i))) for i in range(4)]+[p,p*(1-p),min(((x^z).bit_count()/4 for z,_ in seen),default=1.),sum(y for _,y in seen)/len(seen) if seen else .5,len(candidates)/8])
        matrix_entries+=len(t)*(2*len(candidates)+8);covariance_ops+=len(t)*len(candidates)*8
        assert np.allclose(g,row['gains'],atol=1e-12,rtol=0) and np.allclose(feats,row['features'],atol=1e-12,rtol=0)
        assert digest(row['features'])==row['feature_hash']
        model=blocks[row['block']]['model'];score=np.asarray(feats)/model['scale']@np.asarray(model['beta'])
        assert np.allclose(score,row['scores'],atol=1e-12,rtol=0)
        g=np.asarray(g);best=g.max(axis=0);sets=[[x for i,x in enumerate(candidates) if best[j]-g[i,j]<=c['tolerance']] for j in range(8)]
        common=set(candidates).intersection(*(set(s) for s in sets))
        assert sets==row['optimal_sets'] and sorted(common)==row['common_optima'] and row['incompatible']==(not bool(common))
        gap=max(0.,float(best.mean()-g.mean(axis=1).max()));assert abs(gap-row['alias_gap'])<1e-12
        choices={'learned':int(np.argmax(score)),'variance':int(np.argmax([f[6] for f in feats])),'original_order':0}
        for name,index in choices.items():
            assert row['choices'][name]==candidates[index]
            assert abs(float((best-g[index]).mean())-row['expected_regret'][name])<1e-12
        assert abs(gap-row['expected_regret']['best_query_blind'])<1e-12 and row['expected_regret']['query_aware']==0
    assert matrix_entries==r['resources']['matrix_entries'] and covariance_ops==r['resources']['covariance_multiply_adds']
    means={m:float(np.mean([x['expected_regret'][m] for x in r['rows']])) for m in r['analysis']['expected_regret']}
    assert all(abs(v-r['analysis']['expected_regret'][m])<1e-12 for m,v in means.items())
    assert sum(x['incompatible'] for x in r['rows'])==r['analysis']['incompatible']
    assert sum(x['alias_gap']>=c['practical_gap'] for x in r['rows'])==r['analysis']['material_gap_contexts']
    for item in r['analysis']['per_block']:
        subset=[x for x in r['rows'] if x['block']==item['block']]
        assert len(subset)==64 and sum(x['incompatible'] for x in subset)==item['incompatible']
        assert abs(float(np.mean([x['alias_gap'] for x in subset]))-item['mean_alias_gap'])<1e-12
    for item in r['analysis']['per_prefix']:
        subset=[x for x in r['rows'] if x['prefix']==item['prefix']]
        assert len(subset)==128 and sum(x['incompatible'] for x in subset)==item['incompatible']
        assert abs(float(np.mean([x['alias_gap'] for x in subset]))-item['mean_alias_gap'])<1e-12
    assert digest(q.summarize(r['rows'],c))==digest(r['analysis'])
    for name in ('real_steps','updates','network_forwards','imagined_transitions'):assert type(r['resources'][name]) is int and r['resources'][name]==0
    assert r['resources']['cached_source_labels_available']==2048
    assert r['resources']['cached_distinct_prefix_labels_used']==512 and r['resources']['cached_prefix_label_reads']==896
    assert r['source_projection_sha256']==digest(pack) and r['parent_sha256']==q.PARENT
    assert r['frozen_before']==r['frozen_after']==q.FROZEN
    for name,sha in q.FROZEN.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
    base='94bdad2a7c5c080e6bf105089243e225f3876579'
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'artifacts'],cwd=root,text=True).splitlines()
    for name in names:
        assert (root/name).read_bytes()==subprocess.check_output(['git','show',base+':'+name],cwd=root)
    for name,sha in r['registration']['source_hashes'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',r['execution_sha']+':'+name],cwd=root)).hexdigest()==sha
    assert abs(r['session_used_s']-c['carried_used_s']-r['execution_debit_s'])<1e-8
    return dict(valid=True,raw_sha256=hashlib.sha256(raw).hexdigest(),contexts_verified=len(r['rows']),
        gain_cells_verified=sum(len(x['candidates'])*8 for x in r['rows']),historical_artifacts_unchanged=len(names),
        execution_sha=r['execution_sha'],independent_arithmetic='outcome-branch squared-error enumeration',new_collection=0)


if __name__=='__main__':
    result=verify()
    if '--write' in sys.argv:
        destination=ROOT/'artifacts/seed_query_context_audit.json'
        if destination.exists():raise ValueError('audit_receipt_exists')
        destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
