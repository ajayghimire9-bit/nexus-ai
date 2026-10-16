#!/usr/bin/env python3
"""Independent selected-index arithmetic; recorded data only, no model loading."""
import argparse
import json
import math
from pathlib import Path
import statistics
from nexus.world.value_candidate_discrimination import inputs,OUTPUT,validate_result
from nexus.world.planning_value import sha


def audit():
    cfg,parent,stage,capture=inputs();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete analysis')
    validate_result(p,cfg,parent,stage,capture)
    prefixes={r['task']:r for r in capture['prefixes']};cal={(r['decoder'],r['task']):r for r in capture['cells']}
    observations={};changed=0;constant_changed=0
    for row in p['cells']:
        d,t=row['decoder'],row['task'];real=[sum(r['rewards'])+tail for r,tail in zip(prefixes[t]['rollouts'],cal[d,t]['targets'])]
        for name,scores in row['scores'].items():
            idx=cfg['candidate_indices'];base=max(range(4),key=lambda i:scores['base'][idx[i]])
            corrected=max(range(4),key=lambda i:scores['corrected'][idx[i]])
            constant=cal[d,t]['predictions'][name]['constant'][0]
            const_idx=max(range(4),key=lambda i:scores['base'][idx[i]]+scores['survival'][idx[i]]*constant)
            observations[d,t,name]=real[corrected]-real[base]
            changed+=corrected!=base;constant_changed+=const_idx!=base
    groups={}
    for group,tasks in [('source',cfg['source_tasks']),('development',cfg['development_tasks'])]:
        vals=[statistics.mean(observations[d,t,str(s)] for t in tasks for s in cfg['students']) for d in cfg['decoders']]
        mean=statistics.mean(vals);se=statistics.stdev(vals)/math.sqrt(10);interval=dict(mean=mean,lo=mean-2.262*se,hi=mean+2.262*se)
        target=p['summaries'][group]['metrics']['benefit']['interval']
        for k,v in interval.items():
            if not math.isclose(v,target[k],abs_tol=1e-8):raise RuntimeError('independent primary mismatch')
        groups[group]=dict(interval=interval,per_decoder=vals)
    return dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',source_sha256=sha(OUTPUT),groups=groups,
        changed_context_selections=changed,constant_changed_context_selections=constant_changed,total_context_comparisons=660,new_environment_steps=0)


def figure(result):
    p=json.loads(OUTPUT.read_text());entries=[('Development pooled',result['groups']['development']['interval']),('Source pooled',result['groups']['source']['interval'])]
    entries += [('Development '+k,p['summaries']['development']['per_task'][k]['benefit']) for k in ('8','9','10')]
    low=min(-5,min(r['lo'] for _,r in entries));high=max(5,max(r['hi'] for _,r in entries));span=high-low;low-=.08*span;high+=.08*span
    def x(v):return 210+(v-low)/(high-low)*580
    pieces=['<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="420"><rect width="1020" height="420" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="30" font-size="20">Recorded-data sequence selection: terminal correction</text>',
        '<text x="24" y="53" font-size="13">Corrected minus original chosen64 return, four labeled candidates; ten decoder units.</text>',
        f'<line x1="{x(0):.2f}" y1="70" x2="{x(0):.2f}" y2="340" stroke="#8d949b" stroke-dasharray="4 4"/>']
    for i,(name,ci) in enumerate(entries):
        y=95+i*50
        pieces += [f'<text x="24" y="{y+4}" font-size="14">{name}</text>',f'<line x1="{x(ci["lo"]):.2f}" y1="{y}" x2="{x(ci["hi"]):.2f}" y2="{y}" stroke="#376d9d" stroke-width="3"/>',f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="5" fill="#376d9d"/>',f'<text x="810" y="{y+4}" font-size="12">{ci["mean"]:+.2f} [{ci["lo"]:+.2f}, {ci["hi"]:+.2f}]</text>']
    pieces += ['<text x="24" y="373" font-size="12">Exploratory reanalysis; full16-action commitment plus zero48 continuation. No new episodes.</text>','<text x="24" y="396" font-size="12">Not first-action replanning, best-of-sixteen actual selection, or independent control confirmation.</text></g></svg>']
    return ''.join(pieces)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args();result=audit()
    if args.write:
        output=Path('artifacts/value_candidate_discrimination_audit.json');plot=Path('artifacts/value_candidate_discrimination.svg')
        if output.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        output.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps(result,indent=2))
