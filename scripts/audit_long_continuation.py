#!/usr/bin/env python3
"""Offline arithmetic audit; no simulator calls, no model loading, no old aggregator."""
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path

import yaml


def audit():
    source=Path('artifacts/long_continuation.json')
    payload=json.loads(source.read_text())
    cfg=yaml.safe_load(Path('configs/long_continuation.yaml').read_text())
    assert payload['diagnostic_complete'], 'incomplete execution is not scientific evidence'
    assert hashlib.sha256(Path('configs/long_continuation.yaml').read_bytes()).hexdigest()==payload['config_sha256']
    pairs={}
    for row in payload['states']:
        d,t,p,slot=(row[k] for k in ('decoder','task','phase','slot'))
        students=cfg['students'] if slot==5 else [slot]
        for s in students:
            key=(d,t,p,'zero' if slot==5 else 'student',s)
            assert key not in pairs, 'duplicate state comparison'
            a=row['full'][str(s)]['rewards']; z=row['full']['zero']['rewards']
            assert len(a)==len(z)==64 and all(math.isfinite(x) for x in a+z)
            # Sum reward differences directly, rather than reuse saved window totals.
            pairs[key]=sum(x-y for x,y in zip(a[16:],z[16:]))
    expected=set(itertools.product(cfg['decoders'],range(4),cfg['phases'],('student','zero'),cfg['students']))
    assert set(pairs)==expected, 'planned cells missing'
    values=[sum(pairs[(d,t,p,v,s)]/80 for t,p,v,s in
                itertools.product(range(4),cfg['phases'],('student','zero'),cfg['students'])) for d in cfg['decoders']]
    mean=statistics.mean(values); se=statistics.stdev(values)/math.sqrt(10)
    ci={'n':10,'df':9,'mean':mean,'lo':mean-2.262*se,'hi':mean+2.262*se}
    saved=payload['comparisons']['full_late']['interval']
    assert all(math.isclose(ci[k],saved[k],abs_tol=1e-9) for k in ('mean','lo','hi'))
    assert all(c['before']==c['after'] and c['contexts_before']==c['contexts_after'] for c in payload['frozen_checks'])
    return {'audit_passed':True,'kind':'independent_arithmetic_implementation_not_external_replication',
            'artifact_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'execution_sha':payload['implementation_sha'],'raw_comparisons':len(pairs),
            'primary_interval':ci,'per_decoder':values,'new_environment_steps':0,
            'limitations':['No external simulator re-execution; published reward timing was checked during execution.',
                           'Finite known physics and one reset per task constrain generalization.',
                           'State distributions diverge during full-policy continuations; this is not a unique causal decomposition.']}


if __name__=='__main__':
    out=Path('artifacts/long_continuation_audit.json')
    if out.exists(): raise SystemExit('refusing to overwrite existing audit')
    result=audit(); out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))
