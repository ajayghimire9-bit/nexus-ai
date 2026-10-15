#!/usr/bin/env python3
"""Independent offline arithmetic implementation; no new environment experience."""
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path
import yaml
import numpy as np

if __name__=='__main__':
    cfg=yaml.safe_load(Path('configs/policy_switch.yaml').read_text())
    path=Path('artifacts/policy_switch.json');p=json.loads(path.read_text())
    if not p['complete']: raise RuntimeError('cannot audit incomplete results as scientific evidence')
    raw={};rng_cache={};decisions_checked=0
    for r in p['states']:
        students=cfg['students'] if r['slot']==5 else [r['slot']]
        executed=[r['traces']['ZZ']]+[tr for s in students for tr in r['traces'][str(s)].values()]
        for trace in executed:
            for action,decision in zip(trace['actions'],trace['decisions']):
                seed=decision['seed']
                if seed not in rng_cache: rng_cache[seed]=np.random.default_rng(seed).integers(0,3,size=(16,16))
                if int(rng_cache[seed][decision['selected_index'],0])!=action: raise RuntimeError('candidate RNG/action mismatch')
                decisions_checked+=1
        for s in students:
            tr=r['traces'][str(s)]
            if tr['SS']['middle_state']!=tr['SZ']['middle_state']: raise RuntimeError('prefix endpoint mismatch')
            key=(r['decoder'],r['phase'],'zero' if r['slot']==5 else 'student',s)
            if key in raw: raise RuntimeError('duplicate comparison')
            raw[key]=sum(a-b for a,b in zip(tr['SS']['rewards'][16:],tr['SZ']['rewards'][16:]))
    expected=set(itertools.product(cfg['decoders'],cfg['phases'],('student','zero'),cfg['students']))
    if set(raw)!=expected: raise RuntimeError('planned audit grid incomplete')
    values=[sum(raw[(d,phase,v,s)]/20 for phase,v,s in itertools.product(cfg['phases'],('student','zero'),cfg['students'])) for d in cfg['decoders']]
    mean=statistics.mean(values);se=statistics.stdev(values)/math.sqrt(10)
    ci={'n':10,'df':9,'mean':mean,'lo':mean-2.262*se,'hi':mean+2.262*se}
    saved=p['comparisons']['suffix']['interval']
    if any(not math.isclose(ci[k],saved[k],abs_tol=1e-9) for k in ('mean','lo','hi')): raise RuntimeError('audit interval disagreement')
    out=Path('artifacts/policy_switch_audit.json')
    if out.exists(): raise RuntimeError('refuse to overwrite audit')
    result={'audit_passed':True,'kind':'independent_arithmetic_not_external_replication',
            'interval':ci,'per_decoder':values,'comparisons':len(raw),'decisions_verified':decisions_checked,'new_environment_steps':0,
            'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'implementation_sha':p['implementation_sha']}
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))
