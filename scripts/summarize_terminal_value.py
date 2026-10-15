#!/usr/bin/env python3
"""Recorded secondary analysis only. No model loading, fitting, or simulation."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np

from nexus.world.terminal_value import OUTPUT,FIT,load_config
from nexus.world.terminal_value_execution import validate_capture
from nexus.world.long_continuation import paired_interval


def summarize_saved():
    cfg=load_config();p=json.loads(OUTPUT.read_text());stage=json.loads(FIT.read_text())
    if not p['complete']:raise RuntimeError('incomplete scientific run')
    validate_capture(p,cfg,stage)
    per_task={}
    for task in range(3):
        values=[statistics.mean(r['metrics']['primary'] for r in p['cells'] if r['decoder']==d and r['task']==task) for d in cfg['decoders']]
        per_task[cfg['eval_task_ids'][task]]=dict(per_decoder=values,interval=paired_interval(values))
    raw=[];changed_student=0;changed_zero=0
    for row in p['cells']:
        seq=row['sequences'];returns=[sum(tr['rewards']) for tr in row['traces']];student=[];student_v=[]
        for name,scores in row['scores'].items():
            actions={kind:seq[int(np.argmax(scores[kind]))][0] for kind in ('base','corrected')}
            if name=='zero':
                zero=returns[actions['base']];zero_v=returns[actions['corrected']];changed_zero+=actions['base']!=actions['corrected']
            else:
                student.append(returns[actions['base']]);student_v.append(returns[actions['corrected']]);changed_student+=actions['base']!=actions['corrected']
        raw.append(dict(decoder=row['decoder'],task=row['task'],state=row['state'],student=statistics.mean(student),
            student_value=statistics.mean(student_v),zero=zero,zero_value=zero_v))
    means={name:statistics.mean(statistics.mean(r[name] for r in raw if r['decoder']==d) for d in cfg['decoders']) for name in ('student','student_value','zero','zero_value')}
    source={}
    for d in cfg['decoders']:
        labels=np.array([sum(tr['rewards']) for r in stage['source_cells'] if r['decoder']==d for tr in r['traces']])
        source[str(d)]=dict(constant_training_rmse=float(labels.std()),ridge_training_rmse=stage['readouts'][str(d)]['fit_rmse'],
                           unique_targets=32,rows_with_repeated_context_targets=192)
    return dict(kind='registered_secondary_descriptive_analysis',multiplicity='unadjusted_task_intervals',
        source_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),fit_sha256=hashlib.sha256(FIT.read_bytes()).hexdigest(),
        per_task=per_task,condition_mean_common64_return=means,per_cell_condition_returns=raw,source_training=source,
        student_action_changes=int(changed_student),student_action_comparisons=300,zero_action_changes=int(changed_zero),zero_action_comparisons=60,
        new_environment_steps=0)


def figure(result):
    entries=[('Pooled',json.loads(OUTPUT.read_text())['comparisons']['primary']['interval'])]+[(name.replace('pendulum_ctx_',''),r['interval']) for name,r in result['per_task'].items()]
    def x(v):return 220+(v+25)/40*640
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="950" height="365">','<rect width="950" height="365" fill="white"/>','<g font-family="Arial,sans-serif" fill="#172432">',
           '<text x="24" y="30" font-size="20">Terminal-value correction: same-state first-action return</text>',
           '<text x="24" y="53" font-size="12">Corrected student minus unchanged student; 95% intervals across ten decoders.</text>']
    for tick in (-20,-10,0,10):
        xx=x(tick);parts.append(f'<line x1="{xx}" y1="75" x2="{xx}" y2="288" stroke="#e0e5eb"/><text x="{xx}" y="312" font-size="12" text-anchor="middle">{tick}</text>')
    parts.append(f'<line x1="{x(0)}" y1="75" x2="{x(0)}" y2="288" stroke="#6a7280" stroke-dasharray="4 4"/>')
    for i,(label,ci) in enumerate(entries):
        y=100+i*55;color='#246995' if i==0 else '#65768a'
        parts.extend([f'<text x="24" y="{y+4}" font-size="14">{label}</text>',f'<line x1="{x(ci["lo"]):.2f}" y1="{y}" x2="{x(ci["hi"]):.2f}" y2="{y}" stroke="{color}" stroke-width="3"/>',
            f'<circle cx="{x(ci["mean"]):.2f}" cy="{y}" r="5" fill="{color}"/>',f'<text x="870" y="{y+4}" font-size="12">{ci["mean"]:+.2f}</text>'])
    parts.extend(['<text x="24" y="343" font-size="12">Development diagnostic: common zero-policy continuation, not full-episode controller return.</text>','</g></svg>'])
    return ''.join(parts)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args()
    result=summarize_saved()
    if args.write:
        path=Path('artifacts/terminal_value_analysis.json');plot=Path('artifacts/terminal_value.svg')
        if path.exists() or plot.exists():raise RuntimeError('refusing analysis overwrite')
        path.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps({k:v for k,v in result.items() if k!='per_cell_condition_returns'},indent=2))
