#!/usr/bin/env python3
"""Recorded-data arithmetic audit; no checkpoint loading or simulation."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
from nexus.world.commitment_value import OUTPUT, load_config, parent_evidence, validate


def interval(values):
    mean=statistics.mean(values); half=2.262*statistics.stdev(values)/math.sqrt(len(values))
    return dict(mean=mean,lo=mean-half,hi=mean+half,n=len(values))


def audit():
    cfg=load_config(); p=json.loads(OUTPUT.read_text()); parent,stage=parent_evidence()
    if p.get('complete') is not True:raise RuntimeError('incomplete or invalid execution')
    rebuilt=validate(p,cfg,parent,stage)
    for key in ('label','comparisons','per_task','zero_context'):
        if p[key]!=rebuilt[key]:raise ValueError('saved summary disagrees with validated raw cells')
    prefixes={(r['task'],r['state']):r for r in p['prefixes']}; values={}
    for row in p['cells']:
        d,t,j=row['decoder'],row['task'],row['state']; prefix=prefixes[t,j]
        for trace in row['first_traces']+row['block_tails']:
            for key,part in (('early',trace['rewards'][:16]),('late',trace['rewards'][16:]),('total',trace['rewards'])):
                saved=trace.get(key)
                if type(saved) not in (int,float) or not math.isfinite(saved) or not math.isclose(saved,math.fsum(part),rel_tol=0,abs_tol=1e-8):
                    raise ValueError('stored continuation reward sum mismatch')
        first=[math.fsum(trace['rewards']) for trace in row['first_traces']]
        block=[math.fsum(pre['rewards'])+math.fsum(tail['rewards']) for pre,tail in zip(prefix['rollouts'],row['block_tails'])]
        for name,scores in row['scores'].items():
            a=max(range(16),key=lambda k:scores['base'][k]); b=max(range(16),key=lambda k:scores['corrected'][k])
            gain1=first[prefix['sequences'][b][0]]-first[prefix['sequences'][a][0]]
            gain16=block[b]-block[a]
            values[d,t,j,name]=dict(gain1=gain1,gain16=gain16,interaction=gain16-gain1)
    groups={}
    for name,tasks,contexts,target in [('pooled',range(3),[str(s) for s in cfg['students']],p['comparisons']),('zero',range(3),['zero'],p['zero_context'])]+[(f'task_{t}',[t],[str(s) for s in cfg['students']],p['per_task'][str(t)]) for t in range(3)]:
        groups[name]={}
        for metric in ('gain1','gain16','interaction'):
            per_decoder=[statistics.mean(values[d,t,j,s][metric] for t,j,s in itertools.product(tasks,range(cfg['states_per_task']),contexts)) for d in cfg['decoders']]
            ci=interval(per_decoder)
            for k in ('mean','lo','hi'):
                if not math.isclose(ci[k],target[metric]['interval'][k],abs_tol=1e-8):raise ValueError('independent contrast mismatch')
            groups[name][metric]=dict(per_decoder=per_decoder,interval=ci)
    return dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',raw_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),groups=groups,new_environment_steps=0,model_inference_calls=0)


def plot(result):
    entries=[('Pooled: one action','pooled','gain1'),('Pooled: 16 actions','pooled','gain16'),('Pooled: interaction','pooled','interaction')]+[(f'dev{t}: interaction',f'task_{t}','interaction') for t in range(3)]
    intervals=[result['groups'][g][m]['interval'] for _,g,m in entries]
    low=min(0,min(c['lo'] for c in intervals))-5;high=max(c['hi'] for c in intervals)+5
    def x(value):return 210+(value-low)/(high-low)*540
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="440"><rect width="1050" height="440" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="30" font-size="20">Frozen value correction × commitment length</text>',
        '<text x="24" y="55" font-size="13">Development physics; common zero continuation to step 64; ten decoder units.</text>',
        f'<line x1="{x(0):.2f}" y1="75" x2="{x(0):.2f}" y2="365" stroke="gray" stroke-dasharray="4 4"/>']
    for i,((label,_,_),ci) in enumerate(zip(entries,intervals)):
        y=100+45*i
        parts.extend([f'<text x="24" y="{y+4}" font-size="14">{label}</text>',
            f'<line x1="{x(ci["lo"]):.2f}" x2="{x(ci["hi"]):.2f}" y1="{y}" y2="{y}" stroke="#2c699a" stroke-width="3"/>',
            f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="5" fill="#2c699a"/>',
            f'<text x="770" y="{y+4}" font-size="13">{ci["mean"]:+.2f} [{ci["lo"]:+.2f}, {ci["hi"]:+.2f}]</text>'])
    parts.append('<text x="24" y="400" font-size="13">Paired return differences, 95% decoder intervals. Not full-episode control confirmation.</text></g></svg>')
    Path('artifacts/commitment_value.svg').write_text(''.join(parts)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();result=audit()
    if args.write:
        dst=Path('artifacts/commitment_value_audit.json')
        if dst.exists() or Path('artifacts/commitment_value.svg').exists():raise RuntimeError('refusing overwrite')
        dst.write_text(json.dumps(result,indent=2)+'\n');plot(result)
    print(json.dumps(result,indent=2))
