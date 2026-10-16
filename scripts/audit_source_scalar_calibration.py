#!/usr/bin/env python3
"""Independent source coefficient and saved-return arithmetic; no simulation."""
import argparse
import itertools
import json
import math
from pathlib import Path
import statistics
from nexus.world import source_scalar_calibration as m


def interval(values):
    mean=statistics.mean(values);half=2.262*statistics.stdev(values)/math.sqrt(10)
    return dict(mean=mean,lo=mean-half,hi=mean+half)


def audit():
    checked=m.audit();p=json.loads(m.OUTPUT.read_text());fit=json.loads(m.FIT.read_text());cfg=m.load_config();_,stage=m.visited.prior.parent_evidence()
    source=json.loads(Path('artifacts/terminal_value_calibration.json').read_text());numerator=[];denominator=[]
    for row in source['cells']:
        if row['task'] not in range(8):continue
        y=row['targets'];ym=statistics.mean(y)
        for name in map(str,range(5)):
            x=row['predictions'][name]['imagined'];xm=statistics.mean(x)
            numerator.extend((a-xm)*(b-ym) for a,b in zip(x,y));denominator.extend((a-xm)**2 for a in x)
    den=math.fsum(denominator);beta=min(1.,max(0.,math.fsum(numerator)/den)) if den>1e-12 else 0.
    if not math.isclose(beta,fit['beta'],abs_tol=1e-12,rel_tol=0):raise ValueError('independent source-only coefficient differs')
    values={}
    for row in p['cells']:
        d,t,v=row['decoder'],row['task'],row['state']
        constant=statistics.mean(math.fsum(tr['rewards']) for r in stage['source_cells'] if r['decoder']==d for tr in r['traces'])
        tails=[math.fsum(tr['rewards']) for tr in row['block_tails']];blocks=[math.fsum(pre['rewards'])+tail for pre,tail in zip(row['prefixes'],tails)];first=[math.fsum(tr['rewards']) for tr in row['first_traces']]
        for name,s in row['scores'].items():
            cal=[constant+beta*(x-constant) for x in s['terminal']];score=[b+a*x for b,a,x in zip(s['base'],s['survival'],cal)]
            base=max(range(16),key=lambda i:s['base'][i]);uncal=max(range(16),key=lambda i:s['corrected'][i]);scaled=max(range(16),key=lambda i:score[i])
            e=[a-b for a,b in zip(s['terminal'],tails)];ec=[a-b for a,b in zip(cal,tails)];em=statistics.mean(e);ecm=statistics.mean(ec)
            values[d,t,v,name]=dict(gain_vs_base=blocks[scaled]-blocks[base],gain_vs_uncalibrated=blocks[scaled]-blocks[uncal],first_gain_vs_base=first[row['sequences'][scaled][0]]-first[row['sequences'][base][0]],first_gain_vs_uncalibrated=first[row['sequences'][scaled][0]]-first[row['sequences'][uncal][0]],centered_error_benefit=statistics.mean((x-em)**2 for x in e)-statistics.mean((x-ecm)**2 for x in ec))
    definitions=[('pooled',range(3),range(2),list(map(str,range(5)))),('zero_context',range(3),range(2),['zero'])]
    definitions += [(f'task_{t}',[t],range(2),list(map(str,range(5)))) for t in range(3)]
    definitions += [(name,range(3),[v],list(map(str,range(5)))) for v,name in enumerate(('student_visitor','zero_visitor'))]
    groups={}
    for name,tasks,visitors,contexts in definitions:
        groups[name]={}
        for metric in next(iter(values.values())):
            vals=[statistics.mean(values[d,t,v,s][metric] for t,v,s in itertools.product(tasks,visitors,contexts)) for d in range(10)];ci=interval(vals)
            for key,val in ci.items():
                if not math.isclose(val,p['scalar_groups'][name][metric]['interval'][key],abs_tol=1e-8):raise ValueError('independent reward/statistical arithmetic differs')
            groups[name][metric]=dict(interval=ci,per_decoder=vals)
    return dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',raw_sha256=checked['raw_sha256'],fit_sha256=m.sha(m.FIT),beta=beta,groups=groups,new_environment_steps=0,new_imagined_transitions=0)


def figure(result):
    entries=[('Pooled vs none','pooled','gain_vs_base'),('Pooled vs original','pooled','gain_vs_uncalibrated')]+[(f'dev{t} vs none',f'task_{t}','gain_vs_base') for t in range(3)]+[('Student visitor','student_visitor','gain_vs_base'),('Zero visitor','zero_visitor','gain_vs_base')]
    cis=[result['groups'][g][metric]['interval'] for _,g,metric in entries];low=min(0,min(c['lo'] for c in cis))-1;high=max(0,max(c['hi'] for c in cis))+1
    def x(value):return 220+(value-low)/(high-low)*490
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="490"><rect width="1050" height="490" fill="white"/><g font-family="Arial" fill="#172432">',f'<text x="24" y="30" font-size="20">Source-only scalar: beta={result["beta"]:.5f}, fresh visited states</text>',
        '<text x="24" y="55" font-size="13">Full-sequence selected64 return; ten decoder units; paired 95% intervals.</text>',f'<line x1="{x(0):.2f}" x2="{x(0):.2f}" y1="75" y2="410" stroke="gray" stroke-dasharray="4 4"/>']
    for i,((label,_,_),ci) in enumerate(zip(entries,cis)):
        y=100+43*i;parts.extend([f'<text x="24" y="{y+4}" font-size="14">{label}</text>',f'<line x1="{x(ci["lo"]):.2f}" x2="{x(ci["hi"]):.2f}" y1="{y}" y2="{y}" stroke="#356e9b" stroke-width="3"/>',f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="4" fill="#356e9b"/>',f'<text x="745" y="{y+4}" font-size="12">{ci["mean"]:+.3f} [{ci["lo"]:+.3f}, {ci["hi"]:+.3f}]</text>'])
    parts.append('<text x="24" y="451" font-size="13">Known development physics. Counterfactual sequence selection, not deployed full-episode control.</text></g></svg>');return ''.join(parts)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();result=audit()
    if args.write:
        output=Path('artifacts/source_scalar_audit.json');plot=Path('artifacts/source_scalar_calibration.svg')
        if output.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        output.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps(dict(audit_passed=True,beta=result['beta'],raw_sha256=result['raw_sha256']),indent=2))
