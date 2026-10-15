#!/usr/bin/env python3
"""Independent raw-reward arithmetic and RNG audit, not external replication."""
import hashlib
import itertools
import json
import math
import statistics
import subprocess
from pathlib import Path
import numpy as np
import yaml

if __name__=='__main__':
    path=Path('artifacts/planning_value.json'); p=json.loads(path.read_text())
    cfg=yaml.safe_load(Path('configs/planning_value.yaml').read_text())
    if not p['complete']: raise RuntimeError('incomplete run')
    for file,key in [('configs/planning_value.yaml','config_sha256'),('docs/NEXUS_PLANNING_VALUE.md','protocol_sha256')]:
        locked=subprocess.check_output(['git','show',p['implementation_sha']+':'+file])
        if hashlib.sha256(locked).hexdigest()!=p[key]: raise RuntimeError('execution provenance mismatch')
    if hashlib.sha256(Path(cfg['parent_artifact']).read_bytes()).hexdigest()!=p['parent_sha256']: raise RuntimeError('parent changed')
    prefix={r['task']:r for r in p['prefixes']}; cells={}; cache={}; checked=0
    for row in p['cells']:
        key=(row['decoder'],row['task'])
        if key in cells: raise RuntimeError('duplicate cell')
        t=row['task']; short=[sum(r['rewards']) for r in prefix[t]['rollouts']]
        long=[early+sum(tr['rewards']) for early,tr in zip(short,row['suffixes'])]
        exact=max(range(16),key=short.__getitem__); regret=max(long)-long[exact]
        if not math.isclose(regret,row['metrics']['primary'],abs_tol=1e-8): raise RuntimeError('regret arithmetic mismatch')
        chosen={k:max(range(16),key=v.__getitem__) for k,v in row['scores'].items()}
        delta=statistics.mean(long[chosen[str(s)]] for s in cfg['students'])-long[chosen['zero']]
        if not math.isclose(delta,row['metrics']['student_minus_zero64'],abs_tol=1e-8): raise RuntimeError('paired contrast mismatch')
        cells[key]=regret
        for trace in row['suffixes']:
            if len(trace['actions'])!=48 or len(trace['decisions'])!=48: raise RuntimeError('truncated continuation')
            for k,(action,dec) in enumerate(zip(trace['actions'],trace['decisions'])):
                seed=cfg['continuation_seed_base']+t*64+k
                if dec['seed']!=seed: raise RuntimeError('unpaired continuation seed')
                if seed not in cache: cache[seed]=np.random.default_rng(seed).integers(0,3,(16,16))
                if int(cache[seed][dec['selected_index'],0])!=action: raise RuntimeError('candidate/action mismatch')
                checked+=1
    if set(cells)!=set(itertools.product(cfg['decoders'],range(len(cfg['tasks'])))): raise RuntimeError('incomplete planned grid')
    values=[statistics.mean(cells[(d,t)] for t in range(8)) for d in cfg['decoders']]
    mean=statistics.mean(values);se=statistics.stdev(values)/math.sqrt(10)
    ci=dict(n=10,df=9,mean=mean,lo=mean-2.262*se,hi=mean+2.262*se)
    saved=p['comparisons']['primary']['interval']
    if any(not math.isclose(ci[k],saved[k],abs_tol=1e-8) for k in ('mean','lo','hi')): raise RuntimeError('decoder aggregation mismatch')
    from nexus.world.planning_value import validate_and_summarize
    validate_and_summarize(p,cfg)
    out=Path('artifacts/planning_value_audit.json')
    if out.exists(): raise RuntimeError('refusing audit overwrite')
    result=dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',interval=ci,
        per_decoder=values,decisions_verified=checked,new_environment_steps=0,
        artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),implementation_sha=p['implementation_sha'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))
