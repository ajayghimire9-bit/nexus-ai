"""Source-only information-sufficiency audit; no label collection or fitting.

Reuses source_acquisition's fixed learner, public grammar, feature function and
expected_gain. Query inputs change; posterior, observed prefix and model do not.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from nexus.evolution1.catalogue import digest
from . import source_acquisition as a
from .investigation_transfer import FROZEN

PARENT='afff98802bbadd0cc79ea2f5fd786c37c9a3670347e4ba01290f461b71e6f370'


def configuration():
    return dict(schema='seed_query_context_v1',tasks={'source':list(range(1745100000,1745100128))},
        families=list(range(1745000001,1745000009)),source_tasks_per_block=16,
        prefixes=[0,1,2,4],query_rule='eight_recorded_query_singletons',
        tolerance=1e-10,practical_gap=1e-4,max_wall_s=60,max_authored_steps=0,
        max_outer_updates=0,max_imagined_transitions=0,
        carried_used_s=1996.6321034559958,carried_remaining_s=1603.3678965440042,
        parent_sha256=PARENT)


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_query_context_recipe')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root):
    """Project saved source fields only. Never return target rows or outcomes."""
    raw=(Path(root)/'artifacts/seed_source_acquisition.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT:raise ValueError('parent_hash')
    return project_source(json.loads(raw))


def project_source(record):
    return [dict(id=b['id'],source=b['source'],model={k:b['model'][k] for k in ('scale','beta')}) for b in record['blocks']]


def gain_matrix(table,ids,candidates,queries,cost):
    """Uniform fixed learner: reduction in Bayes MSE = covariance² / variance.

    These are posterior expectations under a supplied finite prior, NOT observed
    gains or access to an unknown task's answers. Columns are singleton queries.
    """
    import numpy as np
    x=a.read_table(table,ids,candidates,cost).astype(float)
    y=a.read_table(table,ids,queries,cost).astype(float)
    dx=x-x.mean(axis=0);dy=y-y.mean(axis=0)
    variance=(dx*dx).mean(axis=0)
    cov=dx.T@dy/len(ids)
    cost['covariance_multiply_adds']+=len(ids)*len(candidates)*len(queries)
    return np.divide(cov*cov,variance[:,None],out=np.zeros_like(cov),where=variance[:,None]>0)


def context(table,ids,pool,queries,observed,model,cost,tolerance):
    import numpy as np
    from nexus.nn.ridge import predict_ridge
    candidates=[x for x in pool if x not in {q for q,_ in observed}]
    if not candidates or set(pool)&set(queries):raise ValueError('disjoint_public_inputs')
    feats=[a.features(table,ids,x,observed,len(candidates),cost) for x in candidates]
    scores=[predict_ridge((np.asarray(model['scale']),np.asarray(model['beta'])),f) for f in feats]
    gains=gain_matrix(table,ids,candidates,queries,cost)
    opt=gains.max(axis=0);means=gains.mean(axis=1)
    # Intersection of tolerance-optimal actions. An empty intersection proves
    # no query-blind choice is optimal across every paired query context.
    sets=[[candidates[i] for i in range(len(candidates)) if opt[j]-gains[i,j]<=tolerance] for j in range(len(queries))]
    common=set(candidates).intersection(*(set(s) for s in sets))
    chosen=int(np.argmax(scores));var=int(np.argmax([f[6] for f in feats]))
    # Expected regret for ANY query-blind choice is bounded below by this gap.
    gap=float(opt.mean()-means.max())
    return dict(candidates=candidates,queries=list(queries),observed=observed,posterior_size=len(ids),
        features=feats,feature_hash=digest(feats),scores=scores,gains=gains.tolist(),
        optimal_sets=sets,common_optima=sorted(common),alias_gap=max(0.,gap),
        incompatible=not bool(common),
        expected_regret=dict(learned=float((opt-gains[chosen]).mean()),
            variance=float((opt-gains[var]).mean()),original_order=float((opt-gains[0]).mean()),
            best_query_blind=max(0.,gap),query_aware=0.),
        choices=dict(learned=candidates[chosen],variance=candidates[var],original_order=candidates[0]))


def calculate(pack,c,check=lambda:None):
    import numpy as np
    entries,instructions=a.catalogue();table=np.asarray([e['answers'] for e in entries],bool)
    cost=a.meter();cost['covariance_multiply_adds']=0;rows=[]
    for block in pack:
        for source in block['source']:
            task=source['task'];pool,queries=a.split_inputs(task)
            order=list(range(8));random.Random(task+700).shuffle(order)
            for prefix in c['prefixes']:
                check();ids=np.arange(len(table));observed=[]
                for index in order[:prefix]:
                    x=pool[index];answer=source['answers'][x]
                    ids=a.update(table,ids,x,answer,cost);observed.append((x,answer))
                data=context(table,ids,pool,queries,observed,block['model'],cost,c['tolerance'])
                rows.append(dict(block=block['id'],task=task,prefix=prefix,**data))
    summary=summarize(rows,c)
    return dict(rows=rows,analysis=summary,cost=cost,catalogue_hash=digest(entries),program_instructions=instructions)


def summarize(rows,c):
    blocks=sorted({r['block'] for r in rows})
    # All task/prefix counts are fixed equal; no inferential intervals because
    # this is a deterministic information audit, not fresh validation.
    means={m:sum(r['expected_regret'][m] for r in rows)/len(rows) for m in ('learned','variance','original_order','best_query_blind','query_aware')}
    incompatible=sum(r['incompatible'] for r in rows)
    material=sum(r['alias_gap']>=c['practical_gap'] for r in rows)
    return dict(contexts=len(rows),paired_query_contexts=len(rows)*8,incompatible=incompatible,
        material_gap_contexts=material,mean_alias_gap=means['best_query_blind'],max_alias_gap=max(r['alias_gap'] for r in rows),
        expected_regret=means,
        per_block=[dict(block=b,incompatible=sum(r['incompatible'] for r in rows if r['block']==b),
            mean_alias_gap=sum(r['alias_gap'] for r in rows if r['block']==b)/64) for b in blocks],
        per_prefix=[dict(prefix=p,incompatible=sum(r['incompatible'] for r in rows if r['prefix']==p),
            mean_alias_gap=sum(r['alias_gap'] for r in rows if r['prefix']==p)/128) for p in c['prefixes']],
        verdict='query_information_missing' if incompatible>0 and material>0 else 'not_demonstrated',
        scope='deterministic source-only posterior expectations; no actual target gain or causation claim',promoted=False)


def run(request):
    import numpy as np
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository'])
    start=time.monotonic();cpu=time.process_time()
    frozen={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FROZEN}
    if frozen!=FROZEN:raise ValueError('frozen_checkpoint_hash')
    def check():
        if time.monotonic()-start>c['max_wall_s']-3:raise TimeoutError('query_context_cap')
    r=dict(config=c,declared_complete=False,parent_sha256=PARENT)
    try:
        pack=source_pack(root);r.update(calculate(pack,c,check));r['source_projection_sha256']=digest(pack)
        r['frozen_before']=frozen;r['frozen_after']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FROZEN}
        if r['frozen_after']!=frozen:raise ValueError('frozen_checkpoint_changed')
        r['declared_complete']=True
    except Exception as e:
        r['failure']=dict(type=type(e).__name__,message=str(e));Path('progress.json').write_text(json.dumps(r,allow_nan=False));raise
    return dict(adapter=c['schema'],study=r,resources=dict(real_steps=0,imagined_transitions=0,updates=0,network_forwards=0,
        cpu_s=time.process_time()-cpu,worker_wall_s=time.monotonic()-start,
        cached_source_labels_available=128*16,cached_distinct_prefix_labels_used=128*4,cached_prefix_label_reads=128*7,
        contexts=len(r['rows']),program_instructions=r['program_instructions'],matrix_entries=r['cost']['matrix_entries'],
        covariance_multiply_adds=r['cost']['covariance_multiply_adds']),
        runtime=dict(python=sys.version,numpy=np.__version__,device='cpu',threads=1))


def validate_cells(rows,c,pack):
    # Expected grid comes from the LOCKED configuration, never produced rows
    # or a shortened source projection.
    n=c['source_tasks_per_block']
    expected=[(b,task,p) for i,b in enumerate(c['families']) for task in c['tasks']['source'][n*i:n*(i+1)] for p in c['prefixes']]
    if [(x['block'],x['task'],x['prefix']) for x in rows]!=expected:raise ValueError('complete_context_grid')
    for row in rows:
        pool,queries=a.split_inputs(row['task'])
        if row['queries']!=queries or len(row['candidates'])!=8-row['prefix'] or len(set(row['candidates']))!=len(row['candidates']) or not set(row['candidates'])<=set(pool):raise ValueError('complete_query_candidate_grid')
        if len(row['gains'])!=len(row['candidates']) or any(len(v)!=8 for v in row['gains']):raise ValueError('complete_gain_grid')
        values=[v for vector in row['gains'] for v in vector]+[row['alias_gap']]+list(row['expected_regret'].values())
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('finite_numeric_cells')


def validate_output(o,c,caps):
    config_check(c);r=o['study'];root=Path(__file__).resolve().parents[3]
    if r.get('declared_complete') is not True or digest(r.get('config'))!=digest(c):raise ValueError('complete_query_context_audit')
    validate_cells(r['rows'],c,source_pack(root))
    # Full deterministic replay validates raw cells before aggregate arithmetic.
    replay=calculate(source_pack(root),c)
    if digest(replay)!=digest({k:r[k] for k in replay}):raise ValueError('audit_arithmetic_or_raw_cells')
    if r['source_projection_sha256']!=digest(source_pack(root)) or r['parent_sha256']!=PARENT or r['frozen_before']!=FROZEN or r['frozen_after']!=FROZEN:raise ValueError('audit_provenance')
    for k,v in dict(real_steps=0,imagined_transitions=0,updates=0,network_forwards=0,cached_source_labels_available=2048,cached_distinct_prefix_labels_used=512,cached_prefix_label_reads=896,contexts=512,
        program_instructions=replay['program_instructions'],matrix_entries=replay['cost']['matrix_entries'],covariance_multiply_adds=replay['cost']['covariance_multiply_adds']).items():
        if type(o['resources'].get(k)) is not int or o['resources'][k]!=v:raise ValueError('audit_accounting')
    for k in ('cpu_s','worker_wall_s'):
        if type(o['resources'].get(k)) not in (int,float) or not math.isfinite(o['resources'][k]) or o['resources'][k]<0:raise ValueError('finite_runtime')


def saved_replay(root):
    root=Path(root);raw=(root/'artifacts/seed_query_context.json').read_bytes();r=json.loads(raw)
    receipt=json.loads((root/'artifacts/seed_query_context_audit.json').read_text())
    if receipt.get('valid') is not True or receipt.get('raw_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('query_context_receipt_required')
    config_check(r['config'])
    if r.get('declared_complete') is not True:raise ValueError('incomplete_query_context')
    return dict(id='seed-query-context-1',mode='exploration',status='complete_development',wall_s=r['host_receipt']['wall_s'],
        memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],resources=r['resources'],curve=[],query_context=r['analysis'])
