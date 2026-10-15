#!/usr/bin/env python3
"""Read-only by default; independent raw-to-decoder primary arithmetic."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

from nexus.world.terminal_value import OUTPUT,FIT,load_config
from nexus.world.terminal_value_execution import validate_capture

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args()
    cfg=load_config()
    if not OUTPUT.is_file() or not FIT.is_file():raise RuntimeError('no executed terminal-value experiment to audit')
    p=json.loads(OUTPUT.read_text());stage=json.loads(FIT.read_text())
    if not p['complete']:raise RuntimeError('incomplete/invalid execution cannot be called a scientific result')
    validate_capture(p,cfg,stage);raw={}
    for row in p['cells']:
        key=tuple(row[k] for k in ('decoder','task','state'))
        returns=[sum(tr['rewards']) for tr in row['traces']];seq=row['sequences'];deltas=[]
        for s in cfg['students']:
            scores=row['scores'][str(s)];chosen={kind:max(range(16),key=scores[kind].__getitem__) for kind in ('base','corrected')}
            deltas.append(returns[seq[chosen['corrected']][0]]-returns[seq[chosen['base']][0]])
        if key in raw:raise RuntimeError('duplicate primary cell')
        raw[key]=statistics.mean(deltas)
    if set(raw)!=set(itertools.product(cfg['decoders'],range(3),range(2))):raise RuntimeError('incomplete primary grid')
    values=[statistics.mean(raw[(d,t,j)] for t,j in itertools.product(range(3),range(2))) for d in cfg['decoders']]
    mean=statistics.mean(values);se=statistics.stdev(values)/math.sqrt(10)
    interval=dict(n=10,df=9,mean=mean,lo=mean-2.262*se,hi=mean+2.262*se)
    saved=p['comparisons']['primary']['interval']
    if any(not math.isclose(interval[k],saved[k],abs_tol=1e-8) for k in ('mean','lo','hi')):raise RuntimeError('paired aggregation mismatch')
    result=dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',interval=interval,per_decoder=values,
        source_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),new_environment_steps=0)
    if args.write:
        out=Path('artifacts/terminal_value_audit.json')
        if out.exists():raise RuntimeError('refusing audit overwrite')
        out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
