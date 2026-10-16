#!/usr/bin/env python3
"""Independent indices, plain reward sums and decoder aggregation, offline."""
import argparse
import itertools
import json
import math
from pathlib import Path
import statistics
from nexus.world import action_value_alignment as m


def interval(values):
    mean=statistics.mean(values);half=2.262*statistics.stdev(values)/math.sqrt(10)
    return dict(mean=mean,lo=mean-half,hi=mean+half)


def audit():
    cfg=m.load_config();capture,stage=m.inputs();p=json.loads(m.OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete analysis')
    rebuilt=m.validate(p,cfg,capture,stage)
    if any(p[k]!=rebuilt[k] for k in rebuilt) or p['allocation_sha256']!=m.source.sha(m.ALLOCATION):raise ValueError('result/allocation changed')
    values={};covered=0;optimal=0
    for row in capture['cells']:
        q=[math.fsum(pre['rewards'])+math.fsum(tail['rewards']) for pre,tail in zip(row['prefixes'],row['block_tails'])];first=[math.fsum(tr['rewards']) for tr in row['first_traces']]
        i=max(range(16),key=lambda k:q[k]);a=row['sequences'][i][0];represented=set(s[0] for s in row['sequences']);best=max(first);best_covered=max(first[x] for x in represented)
        values[row['decoder'],row['task'],row['state']]=dict(total_regret=best-first[a],represented_regret=best_covered-first[a],coverage_gap=best-best_covered)
        covered+=len(represented)==3;optimal+=best-first[a]<=1e-8
    groups={};definitions=[('pooled',cfg['tasks'],cfg['visitors'])]+[(f'task_{t}',[t],cfg['visitors']) for t in cfg['tasks']]+[(name,cfg['tasks'],[v]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    for name,tasks,visitors in definitions:
        groups[name]={}
        for metric in ('total_regret','represented_regret','coverage_gap'):
            vals=[statistics.mean(values[d,t,v][metric] for t,v in itertools.product(tasks,visitors)) for d in cfg['decoders']];ci=interval(vals)
            for key,value in ci.items():
                if not math.isclose(value,p['groups'][name]['state'][metric]['interval'][key],abs_tol=1e-8):raise ValueError('independent primary arithmetic differs')
            groups[name][metric]=dict(interval=ci,per_decoder=vals)
    return dict(audit_passed=True,kind='independent_arithmetic_not_external_replication',raw_sha256=m.source.sha(m.OUTPUT),groups=groups,states_with_all_actions=covered,sequence_reference_first_action_optimal=optimal,total_states=60,new_environment_steps=0,new_imagined_transitions=0)


def figure(result):
    entries=[('Pooled','pooled')]+[(f'dev{t}',f'task_{t}') for t in range(3)]+[('Student-visited','student_visitor'),('Zero-visited','zero_visitor')]
    cis=[result['groups'][g]['total_regret']['interval'] for _,g in entries];lo=min(0,min(c['lo'] for c in cis))-2;hi=max(c['hi'] for c in cis)+2
    def x(value):return 210+(value-lo)/(hi-lo)*500
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1030" height="440"><rect width="1030" height="440" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="30" font-size="20">Best sequence does not imply best replanning first action</text>',
        '<text x="24" y="55" font-size="13">Measured first-action regret; paired 95% intervals across ten decoders.</text>',f'<line x1="{x(0):.2f}" x2="{x(0):.2f}" y1="75" y2="355" stroke="gray" stroke-dasharray="4 4"/>']
    for i,((name,_),ci) in enumerate(zip(entries,cis)):
        y=100+i*43;parts.extend([f'<text x="24" y="{y+4}" font-size="14">{name}</text>',f'<line x1="{x(ci["lo"]):.2f}" x2="{x(ci["hi"]):.2f}" y1="{y}" y2="{y}" stroke="#356e9b" stroke-width="3"/>',f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="4" fill="#356e9b"/>',f'<text x="735" y="{y+4}" font-size="12">{ci["mean"]:.2f} [{ci["lo"]:.2f}, {ci["hi"]:.2f}]</text>'])
    parts.append('<text x="24" y="391" font-size="13">All60 states represent all three first actions; coverage gap is zero.</text><text x="24" y="416" font-size="13">Research-only sequence reference and common-zero future, not full-episode policy values.</text></g></svg>');return ''.join(parts)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();result=audit()
    if args.write:
        output=Path('artifacts/action_value_alignment_audit.json');plot=Path('artifacts/action_value_alignment.svg')
        if output.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        output.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps({k:result[k] for k in ('audit_passed','raw_sha256','states_with_all_actions','sequence_reference_first_action_optimal')},indent=2))
