#!/usr/bin/env python3
"""Recorded-data audit, independent selected-index arithmetic; no simulation."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
from nexus.world import visited_commitment as m


def interval(values):
    mean=statistics.mean(values);half=2.262*statistics.stdev(values)/math.sqrt(10)
    return dict(mean=mean,lo=mean-half,hi=mean+half)


def audit():
    cfg=m.load_config();p=json.loads(m.OUTPUT.read_text());parent,stage=m.prior.parent_evidence()
    if p.get('complete') is not True:raise RuntimeError('incomplete or invalid execution')
    m.require_allocation(cfg)
    if p['allocation_sha256']!=m.prior.sha(m.ALLOCATION):raise ValueError('allocation digest mismatch')
    rebuilt=m.validate(p,cfg,parent,stage)
    for key in rebuilt:
        if p[key]!=rebuilt[key]:raise ValueError('saved summary differs from raw capture')
    values={}
    for row in p['cells']:
        first=[math.fsum(tr['rewards']) for tr in row['first_traces']]
        blocks=[math.fsum(pre['rewards'])+math.fsum(tail['rewards']) for pre,tail in zip(row['prefixes'],row['block_tails'])]
        for name,scores in row['scores'].items():
            original=max(range(16),key=lambda i:scores['base'][i]);corrected=max(range(16),key=lambda i:scores['corrected'][i])
            gain1=first[row['sequences'][corrected][0]]-first[row['sequences'][original][0]]
            gain16=blocks[corrected]-blocks[original]
            values[row['decoder'],row['task'],row['state'],name]=dict(gain1=gain1,gain16=gain16,interaction=gain16-gain1)
    groups={}
    definitions=[('pooled',range(3),range(2),[str(s) for s in cfg['students']],p['comparisons']),('zero_context',range(3),range(2),['zero'],p['zero_context'])]
    definitions += [(f'task_{t}',[t],range(2),[str(s) for s in cfg['students']],p['per_task'][str(t)]) for t in range(3)]
    definitions += [(name,range(3),[v],[str(s) for s in cfg['students']],p['per_visitor'][name]) for v,name in enumerate(('student','zero'))]
    for name,tasks,visitors,students,target in definitions:
        groups[name]={}
        for metric in ('gain1','gain16','interaction'):
            paired=[statistics.mean(values[d,t,v,s][metric] for t,v,s in itertools.product(tasks,visitors,students)) for d in cfg['decoders']];ci=interval(paired)
            for key in ci:
                if not math.isclose(ci[key],target[metric]['interval'][key],abs_tol=1e-8):raise ValueError('independent aggregation differs')
            groups[name][metric]=dict(per_decoder=paired,interval=ci)
    return dict(audit_passed=True,kind='independent_arithmetic_not_external_scientific_replication',raw_sha256=hashlib.sha256(m.OUTPUT.read_bytes()).hexdigest(),groups=groups,new_environment_steps=0,model_inference_calls=0)


def figure(result):
    entries=[('Pooled: one action','pooled','gain1'),('Pooled: 16 actions','pooled','gain16'),('Pooled: interaction','pooled','interaction'),('Student-visited','student','interaction'),('Zero-visited','zero','interaction')]+[(f'dev{t}: interaction',f'task_{t}','interaction') for t in range(3)]
    intervals=[result['groups'][g][metric]['interval'] for _,g,metric in entries];low=min(0,min(c['lo'] for c in intervals))-5;high=max(c['hi'] for c in intervals)+5
    def x(value):return 215+(value-low)/(high-low)*515
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="540"><rect width="1050" height="540" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="30" font-size="20">Phase-50 visited-state commitment replication</text>',
        '<text x="24" y="54" font-size="13">Equal visitor weighting; common-zero continuation; ten independent decoder units.</text>',
        f'<line x1="{x(0):.2f}" x2="{x(0):.2f}" y1="75" y2="460" stroke="gray" stroke-dasharray="4 4"/>']
    for i,((label,_,_),ci) in enumerate(zip(entries,intervals)):
        y=100+45*i
        parts.extend([f'<text x="24" y="{y+4}" font-size="14">{label}</text>',f'<line x1="{x(ci["lo"]):.2f}" x2="{x(ci["hi"]):.2f}" y1="{y}" y2="{y}" stroke="#2c699a" stroke-width="3"/>',f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="5" fill="#2c699a"/>',f'<text x="755" y="{y+4}" font-size="13">{ci["mean"]:+.2f} [{ci["lo"]:+.2f}, {ci["hi"]:+.2f}]</text>'])
    parts.append('<text x="24" y="510" font-size="13">Return differences, paired 95% intervals; task/visitor sensitivities exploratory.</text></g></svg>')
    return ''.join(parts)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();result=audit()
    if args.write:
        output=Path('artifacts/visited_commitment_audit.json');plot=Path('artifacts/visited_commitment.svg')
        if output.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        output.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps(result,indent=2))
