#!/usr/bin/env python3
"""Independent scalar arithmetic on saved predictions/rewards only."""
import argparse
import itertools
import json
import math
from pathlib import Path
import statistics
from nexus.world import visited_value_ranking as m


def ordered_accuracy(predicted,actual):
    correct=[]
    for i in range(16):
        for j in range(i+1,16):
            dp=predicted[i]-predicted[j];dy=actual[i]-actual[j]
            correct.append(.5 if dp==0 or dy==0 else float((dp>0)==(dy>0)))
    return math.fsum(correct)/120


def interval(values):
    mean=statistics.mean(values);half=2.262*statistics.stdev(values)/math.sqrt(10)
    return dict(mean=mean,lo=mean-half,hi=mean+half)


def audit():
    cfg=m.load_config();source,stage=m.inputs(cfg);p=json.loads(m.OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete analysis')
    rebuilt=m.validate(p,cfg,source,stage)
    if any(p[key]!=rebuilt[key] for key in rebuilt):raise ValueError('saved analysis summaries changed')
    if p['allocation_sha256']!=m.sha(m.ALLOCATION):raise ValueError('allocation hash changed')
    results={}
    for row in source['cells']:
        prefix=[math.fsum(tr['rewards']) for tr in row['prefixes']];tail=[math.fsum(tr['rewards']) for tr in row['block_tails']];q=[a+b for a,b in zip(prefix,tail)]
        for name,s in row['scores'].items():
            pred=s['terminal'];e=[a-b for a,b in zip(pred,tail)];mean=statistics.mean(e);variance=statistics.mean((x-statistics.mean(tail))**2 for x in tail)
            mse=statistics.mean(x*x for x in e);centered=statistics.mean((x-mean)**2 for x in e)
            a=max(range(16),key=lambda k:s['base'][k]);b=max(range(16),key=lambda k:s['corrected'][k])
            results[row['decoder'],row['task'],row['state'],name]=dict(tail_mse=mse,tail_bias_sq=mean*mean,tail_centered_mse=centered,centered_benefit=variance-centered,tail_rank_advantage=ordered_accuracy(pred,tail)-.5,return_gain=q[b]-q[a])
    groups={}
    definitions=[('pooled',cfg['tasks'],cfg['visitors'],[str(s) for s in cfg['students']]),('zero_context',cfg['tasks'],cfg['visitors'],['zero'])]
    definitions += [(f'task_{t}',[t],cfg['visitors'],[str(s) for s in cfg['students']]) for t in cfg['tasks']]
    definitions += [(name,cfg['tasks'],[v],[str(s) for s in cfg['students']]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    for name,tasks,visitors,contexts in definitions:
        groups[name]={}
        for metric in next(iter(results.values())):
            vals=[statistics.mean(results[d,t,v,s][metric] for t,v,s in itertools.product(tasks,visitors,contexts)) for d in cfg['decoders']];ci=interval(vals)
            for k,value in ci.items():
                if not math.isclose(value,p['groups'][name][metric]['interval'][k],abs_tol=1e-8):raise ValueError('independent arithmetic mismatch')
            groups[name][metric]=dict(per_decoder=vals,interval=ci)
    return dict(audit_passed=True,kind='independent_scalar_arithmetic_not_external_replication',raw_sha256=m.sha(m.OUTPUT),groups=groups,new_environment_steps=0,new_imagined_transitions=0,model_inference_calls=0)


def figure(result):
    entries=[('Pooled','pooled'),('Student-visited','student_visitor'),('Zero-visited','zero_visitor')]+[(f'dev{t}',f'task_{t}') for t in range(3)]
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="460"><rect width="1100" height="460" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="28" font-size="20">Visited-state tail information: magnitude versus ordering</text>']
    for panel,metric in enumerate(('centered_benefit','tail_rank_advantage')):
        cis=[result['groups'][g][metric]['interval'] for _,g in entries];low=min(0,min(c['lo'] for c in cis));high=max(0,max(c['hi'] for c in cis));span=high-low;low-=span*.08;high+=span*.08
        start=170+panel*505
        def x(value):return start+(value-low)/(high-low)*285
        title='Centered MSE benefit (positive better)' if panel==0 else 'Pair accuracy minus 0.5'
        parts.extend([f'<text x="{start}" y="60" font-size="13">{title}</text>',f'<line x1="{x(0):.2f}" x2="{x(0):.2f}" y1="80" y2="360" stroke="gray" stroke-dasharray="4 4"/>'])
        for i,((label,_),ci) in enumerate(zip(entries,cis)):
            y=105+i*44
            if panel==0:parts.append(f'<text x="20" y="{y+4}" font-size="14">{label}</text>')
            parts.extend([f'<line x1="{x(ci["lo"]):.2f}" x2="{x(ci["hi"]):.2f}" y1="{y}" y2="{y}" stroke="#356e9b" stroke-width="3"/>',f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="4" fill="#356e9b"/>',f'<text x="{start+300}" y="{y+4}" font-size="11">{ci["mean"]:+.3f}</text>'])
    parts.append('<text x="24" y="407" font-size="13">Paired 95% intervals across ten decoders; visitor/task subsets exploratory.</text><text x="24" y="432" font-size="13">Recorded-data reanalysis only. Ordering information need not imply calibrated magnitudes or better selection.</text></g></svg>')
    return ''.join(parts)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();result=audit()
    if args.write:
        out=Path('artifacts/visited_value_ranking_audit.json');plot=Path('artifacts/visited_value_ranking.svg')
        if out.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        out.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps(dict(audit_passed=True,raw_sha256=result['raw_sha256']),indent=2))
