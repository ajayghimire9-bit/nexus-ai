"""Sequence objective versus measured first-action/common-zero values, offline."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
import numpy as np
import yaml
from nexus.world import source_scalar_calibration as source

CONFIG=Path('configs/action_value_alignment.yaml')
PROTOCOL=Path('docs/NEXUS_ACTION_VALUE_ALIGNMENT_PROTOCOL.md')
ALLOCATION=Path('configs/action_value_alignment_allocation.json')
OUTPUT=Path('artifacts/action_value_alignment.json')
STATE_METRICS=('total_regret','represented_regret','coverage_gap','sequence_first_return','best_action_return','best_represented_return','optimal_first_action','all_actions_represented')
REFERENCE_METRICS=tuple(f'{method}_{metric}' for method in ('base','uncalibrated','calibrated') for metric in ('first_return','first_regret','sequence_advantage','action_agreement'))


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    for key,value in dict(decoders=list(range(10)),tasks=list(range(3)),visitors=[0,1],students=list(range(5)),contexts=['zero','0','1','2','3','4'],time_cap_s=60,practical_margin=1.0,new_environment_cap=0,new_imagined_cap=0).items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked grid/budget drift')
    for file,digest in cfg['parents'].items():
        if source.sha(file)!=digest:raise ValueError('closed parent changed')
    return cfg


def state_values(sequences,block_returns,first_returns):
    seq=np.asarray(sequences)
    if seq.shape!=(16,16) or not np.issubdtype(seq.dtype,np.integer) or np.any((seq<0)|(seq>2)):raise ValueError('sixteen registered discrete sequences required')
    block=source.visited.prior.finite_array(block_returns,(16,));first=source.visited.prior.finite_array(first_returns,(3,))
    selected=int(np.argmax(block));action=int(seq[selected,0]);represented=sorted(set(seq[:,0].tolist()))
    best=float(max(first));covered=float(max(first[represented]));value=float(first[action])
    metrics=dict(total_regret=best-value,represented_regret=covered-value,coverage_gap=best-covered,sequence_first_return=value,best_action_return=best,best_represented_return=covered,optimal_first_action=float(best-value<=1e-8),all_actions_represented=float(len(represented)==3))
    if any(metrics[k]<0 for k in ('total_regret','represented_regret','coverage_gap')) or not math.isclose(metrics['total_regret'],metrics['represented_regret']+metrics['coverage_gap'],abs_tol=1e-8,rel_tol=0):raise ValueError('regret/coverage decomposition mismatch')
    return dict(metrics=metrics,selected_sequence=selected,selected_first_action=action,best_first_action=int(np.argmax(first)),represented_actions=represented)


def build_row(row,beta,constant):
    first=[math.fsum(tr['rewards']) for tr in row['first_traces']]
    blocks=[math.fsum(pre['rewards'])+math.fsum(tail['rewards']) for pre,tail in zip(row['prefixes'],row['block_tails'])]
    geometry=state_values(row['sequences'],blocks,first);refs={}
    for name,s in row['scores'].items():
        scores=dict(base=s['base'],uncalibrated=s['corrected'],calibrated=source.calibrated_score(s,beta,constant).tolist());metrics={}
        for method,values in scores.items():
            index=int(np.argmax(source.visited.prior.finite_array(values,(16,))));action=row['sequences'][index][0];value=first[action]
            metrics.update({f'{method}_first_return':value,f'{method}_first_regret':max(first)-value,f'{method}_sequence_advantage':geometry['metrics']['sequence_first_return']-value,f'{method}_action_agreement':float(action==geometry['selected_first_action'])})
        refs[name]=metrics
    return dict(decoder=row['decoder'],task=row['task'],visitor=row['state'],geometry=geometry,references=refs)


def summarize(rows,cfg):
    cells=source.visited.checked_id_grid(rows,('decoder','task','visitor'),set(itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors'])))
    for row in cells.values():
        if set(row['geometry']['metrics'])!=set(STATE_METRICS) or set(row['references'])!=set(cfg['contexts']):raise ValueError('missing state metric/context')
        geometry=row['geometry']
        for key,maximum in (('selected_sequence',15),('selected_first_action',2),('best_first_action',2)):
            if type(geometry[key]) is not int or not 0<=geometry[key]<=maximum:raise ValueError('invalid research-reference index')
        if not geometry['represented_actions'] or any(type(a) is not int or a not in (0,1,2) for a in geometry['represented_actions']) or geometry['represented_actions']!=sorted(set(geometry['represented_actions'])):raise ValueError('invalid first-action coverage')
        source.visited.prior.finite_array([row['geometry']['metrics'][k] for k in STATE_METRICS],(len(STATE_METRICS),))
        for ref in row['references'].values():
            if set(ref)!=set(REFERENCE_METRICS):raise ValueError('missing reference metric')
            source.visited.prior.finite_array([ref[k] for k in REFERENCE_METRICS],(len(REFERENCE_METRICS),))
    groups={};definitions=[('pooled',cfg['tasks'],cfg['visitors'])]+[(f'task_{t}',[t],cfg['visitors']) for t in cfg['tasks']]+[(name,cfg['tasks'],[v]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    for name,tasks,visitors in definitions:
        state={};ref={};zero={}
        for metric in STATE_METRICS:
            vals=[statistics.mean(cells[d,t,v]['geometry']['metrics'][metric] for t,v in itertools.product(tasks,visitors)) for d in cfg['decoders']]
            state[metric]=dict(per_decoder=vals,interval=source.visited.prior.paired_interval(vals))
        for metric in REFERENCE_METRICS:
            for dest,contexts in ((ref,list(map(str,cfg['students']))),(zero,['zero'])):
                vals=[statistics.mean(cells[d,t,v]['references'][s][metric] for t,v,s in itertools.product(tasks,visitors,contexts)) for d in cfg['decoders']]
                dest[metric]=dict(per_decoder=vals,interval=source.visited.prior.paired_interval(vals))
        groups[name]=dict(state=state,student_references=ref,zero_references=zero)
    total=groups['pooled']['state']['total_regret']['interval'];represented=groups['pooled']['state']['represented_regret']['interval']
    label='alignment_gap_not_established'
    if total['mean']>=1 and total['lo']>0:
        label='sequence_first_action_misalignment_detected' if represented['mean']>=1 and represented['lo']>0 else 'first_action_gap_with_coverage_or_uncertainty'
    return dict(label=label,groups=groups)


def inputs():
    audit=source.audit();capture=json.loads(source.OUTPUT.read_text());_,stage=source.visited.prior.parent_evidence()
    if not audit['audit_passed']:raise ValueError('invalid source evaluation')
    return capture,stage


def validate(p,cfg,capture,stage):
    cells=source.visited.checked_id_grid(p['cells'],('decoder','task','visitor'),set(itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors'])))
    old={(r['decoder'],r['task'],r['state']):r for r in capture['cells']};beta=json.loads(source.FIT.read_text())['beta']
    for key,row in cells.items():
        if row!=build_row(old[key],beta,source.source_constant(stage,key[0])):raise ValueError('raw action-value arithmetic mismatch')
    if p['config_sha256']!=source.sha(CONFIG) or p['protocol_sha256']!=source.sha(PROTOCOL) or p['parents']!=cfg['parents'] or p['source_dirty'] is not False:raise ValueError('provenance changed')
    for key,length in (('implementation_sha',40),('allocation_sha256',64)):
        s=p.get(key)
        if not isinstance(s,str) or len(s)!=length or any(c not in '0123456789abcdef' for c in s):raise ValueError('missing execution/allocation provenance')
    if p['new_environment_steps']!=0 or p['new_imagined_transitions']!=0 or p['world_model_inference_calls']!=0:raise ValueError('offline analysis cannot simulate')
    source.visited.prior.finite_array([p['wall_clock_s']],(1,))
    if not 0<p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time cap exceeded')
    return summarize(p['cells'],cfg)


def require_allocation(cfg):
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=source.sha(CONFIG),protocol_sha256=source.sha(PROTOCOL),time_cap_s=60,runs=1,new_environment_cap=0,new_imagined_cap=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise PermissionError('stale/missing offline allocation')
    usage=json.loads(Path('artifacts/research_session_source_scalar_usage.json').read_text())
    if usage['remaining_session_allowance_s']<cfg['time_cap_s']:raise PermissionError('session allowance exhausted')


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before calculation')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started=time.perf_counter()
    def check():
        if time.perf_counter()-started>=cfg['time_cap_s']:raise TimeoutError('60-second offline cap reached')
    p=dict(complete=False,label='incomplete',cells=[],implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,config_sha256=source.sha(CONFIG),protocol_sha256=source.sha(PROTOCOL),allocation_sha256=source.sha(ALLOCATION),parents=cfg['parents'],new_environment_steps=0,new_imagined_transitions=0,world_model_inference_calls=0,dependencies=dict(python=sys.version,numpy=np.__version__))
    try:
        capture,stage=inputs();check();beta=json.loads(source.FIT.read_text())['beta']
        constants={d:source.source_constant(stage,d) for d in cfg['decoders']}
        for row in capture['cells']:check();p['cells'].append(build_row(row,beta,constants[row['decoder']]))
        p['wall_clock_s']=time.perf_counter()-started;p.update(validate(p,cfg,capture,stage));check();p['complete']=True
    except Exception as exc:p['failure']=dict(type=type(exc).__name__,message=str(exc))
    p['wall_clock_s']=time.perf_counter()-started;source.visited.save(OUTPUT,p);return p
