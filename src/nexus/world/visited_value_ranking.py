"""Recorded-outcome discrimination analysis; no learned-model inference."""
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
from nexus.world.planning_value import sha,finite_array
from nexus.world.terminal_value_execution import checked_id_grid,save
from nexus.world.long_continuation import paired_interval

CONFIG=Path('configs/visited_value_ranking.yaml')
PROTOCOL=Path('docs/NEXUS_VISITED_VALUE_RANKING_PROTOCOL.md')
ALLOCATION=Path('configs/visited_value_ranking_allocation.json')
OUTPUT=Path('artifacts/visited_value_ranking.json')
METRICS=('tail_mse','tail_bias_sq','tail_centered_mse','constant_mse','tail_variance','centered_benefit','absolute_benefit','tail_pair_accuracy','tail_rank_advantage','actual_tail_ties',
    'base_return','value_return','constant_return','actual16_return','actual_prefix_predicted_tail_return','base_regret','value_regret','constant_regret','actual16_regret','actual_prefix_predicted_tail_regret',
    'return_gain','vs_constant','full_rank_gain','prefix_mse','value_full_mse','constant_full_mse','full_centered_benefit','sequence_changed','constant_changed','mean_survival','min_survival','max_survival')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    for key,value in dict(decoders=list(range(10)),students=list(range(5)),tasks=list(range(3)),visitors=[0,1],contexts=['zero','0','1','2','3','4'],candidates=16,time_cap_s=120,new_environment_cap=0,new_imagined_cap=0).items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked grid/budget changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed input changed')
    return cfg


def inputs(cfg):
    from nexus.world import visited_commitment as parent
    p=json.loads(parent.OUTPUT.read_text());original,stage=parent.prior.parent_evidence()
    if p.get('complete') is not True:raise ValueError('incomplete source capture')
    validated=parent.validate(p,parent.load_config(),original,stage)
    if any(p[key]!=validated[key] for key in validated):raise ValueError('source summaries differ')
    return p,stage


def numeric(value,shape):
    # Internal NumPy arrays are allowed, but JSON booleans/strings remain invalid.
    return finite_array(value.tolist() if isinstance(value,np.ndarray) else value,shape)


def pair_accuracy(predicted,actual):
    p=numeric(predicted,(16,));a=numeric(actual,(16,));scores=[];ties=0
    for i,j in itertools.combinations(range(16),2):
        dp=p[i]-p[j];da=a[i]-a[j];ties+=int(da==0)
        scores.append(.5 if dp==0 or da==0 else float((dp>0)==(da>0)))
    return statistics.mean(scores),ties/120


def source_constant(stage,decoder):
    rows=[r for r in stage['source_cells'] if r['decoder']==decoder]
    if {r['task'] for r in rows}!=set(range(8)) or len(rows)!=8:raise ValueError('incomplete source-constant data')
    values=[math.fsum(finite_array(tr['rewards'],(48,)).tolist()) for row in rows for tr in row['traces']]
    if len(values)!=32:raise ValueError('source constant needs all32 traces')
    return statistics.mean(values)


def metrics(prefix,tail,scores,constant):
    r=numeric(prefix,(16,));y=numeric(tail,(16,));p=numeric(scores['terminal'],(16,));base=numeric(scores['base'],(16,));value=numeric(scores['corrected'],(16,));alive=numeric(scores['survival'],(16,))
    finite_array([constant],(1,))
    if not np.allclose(value,base+alive*p,rtol=0,atol=1e-8) or np.any((alive<0)|(alive>1)):raise ValueError('saved scores inconsistent')
    error=p-y;mse=float(np.mean(error**2));bias=float(np.mean(error)**2);centered=float(np.mean((error-error.mean())**2));variance=float(np.mean((y-y.mean())**2))
    if not math.isclose(mse,bias+centered,abs_tol=1e-8,rel_tol=1e-12):raise ValueError('decomposition mismatch')
    q=r+y;constant_score=base+alive*constant
    choices=dict(base=int(np.argmax(base)),value=int(np.argmax(value)),constant=int(np.argmax(constant_score)),actual16=int(np.argmax(r)),actual_prefix_predicted_tail=int(np.argmax(r+alive*p)))
    result={key+'_return':float(q[index]) for key,index in choices.items()}
    result.update({key+'_regret':float(max(q)-q[index]) for key,index in choices.items()})
    rank,ties=pair_accuracy(p,y);vb,_=pair_accuracy(value,q);bb,_=pair_accuracy(base,q)
    full_error=value-q;constant_error=constant_score-q
    result.update(tail_mse=mse,tail_bias_sq=bias,tail_centered_mse=centered,constant_mse=float(np.mean((constant-y)**2)),tail_variance=variance,centered_benefit=variance-centered,absolute_benefit=float(np.mean((constant-y)**2))-mse,
        tail_pair_accuracy=rank,tail_rank_advantage=rank-.5,actual_tail_ties=ties,return_gain=result['value_return']-result['base_return'],vs_constant=result['value_return']-result['constant_return'],full_rank_gain=vb-bb,
        prefix_mse=float(np.mean((base-r)**2)),value_full_mse=float(np.mean(full_error**2)),constant_full_mse=float(np.mean(constant_error**2)),full_centered_benefit=float(np.mean((constant_error-constant_error.mean())**2)-np.mean((full_error-full_error.mean())**2)),
        sequence_changed=float(choices['value']!=choices['base']),constant_changed=float(choices['constant']!=choices['base']),mean_survival=float(np.mean(alive)),min_survival=float(min(alive)),max_survival=float(max(alive)))
    if set(result)!=set(METRICS):raise ValueError('metric schema drift')
    finite_array([result[k] for k in METRICS],(len(METRICS),));return result


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','visitor'),set(itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors'])))
    for row in cells.values():
        if set(row['metrics'])!=set(cfg['contexts']):raise ValueError('missing context')
        for m in row['metrics'].values():
            if set(m)!=set(METRICS):raise ValueError('missing metric')
            finite_array([m[k] for k in METRICS],(len(METRICS),))
    groups={}
    definitions=[('pooled',cfg['tasks'],cfg['visitors'],[str(s) for s in cfg['students']]),('zero_context',cfg['tasks'],cfg['visitors'],['zero'])]
    definitions += [(f'task_{t}',[t],cfg['visitors'],[str(s) for s in cfg['students']]) for t in cfg['tasks']]
    definitions += [(name,cfg['tasks'],[v],[str(s) for s in cfg['students']]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    for name,tasks,visitors,contexts in definitions:
        groups[name]={}
        for metric in METRICS:
            values=[statistics.mean(cells[d,t,v]['metrics'][s][metric] for t,v,s in itertools.product(tasks,visitors,contexts)) for d in cfg['decoders']]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    benefit=groups['pooled']['centered_benefit']['interval'];ranking=groups['pooled']['tail_rank_advantage']['interval']
    label='within_state_tail_information_not_established'
    if benefit['lo']>0 and ranking['lo']>0:label='within_state_tail_information_detected'
    elif benefit['hi']<0:label='tail_centered_error_worse_than_constant'
    return dict(label=label,groups=groups)


def build_row(row,constant):
    prefix=[math.fsum(r['rewards']) for r in row['prefixes']];tails=[math.fsum(r['rewards']) for r in row['block_tails']]
    out={name:metrics(prefix,tails,score,constant) for name,score in row['scores'].items()}
    for name,result in out.items():
        if not math.isclose(result['return_gain'],row['metrics'][name]['gain16'],abs_tol=1e-8,rel_tol=0):raise ValueError('closed gain16 did not reproduce')
    return dict(decoder=row['decoder'],task=row['task'],visitor=row['state'],source_constant=constant,metrics=out)


def validate(p,cfg,capture,stage):
    expected={(r['decoder'],r['task'],r['state']):r for r in capture['cells']}
    rows=checked_id_grid(p['cells'],('decoder','task','visitor'),set(itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors'])))
    for key,row in rows.items():
        if row!=build_row(expected[key],source_constant(stage,key[0])):raise ValueError('saved metrics differ from input rewards')
    if p['config_sha256']!=sha(CONFIG) or p['protocol_sha256']!=sha(PROTOCOL) or p['parents']!=cfg['parents'] or p['source_dirty'] is not False:raise ValueError('provenance changed')
    if p['new_environment_steps']!=0 or p['new_imagined_transitions']!=0 or p['model_inference_calls']!=0:raise ValueError('analysis cannot collect/infer')
    for key,length in (('implementation_sha',40),('allocation_sha256',64)):
        value=p.get(key)
        if not isinstance(value,str) or len(value)!=length or any(c not in '0123456789abcdef' for c in value):raise ValueError('missing execution/allocation digest')
    finite_array([p['wall_clock_s']],(1,))
    if not 0<p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time cap exceeded')
    return summarize(p['cells'],cfg)


def require_allocation(cfg):
    allocation=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=120,runs=1,new_environment_cap=0,new_imagined_cap=0).items():
        if type(allocation.get(key)) is not type(value) or allocation[key]!=value:raise PermissionError('stale/missing bounded allocation')
    usage=json.loads(Path('artifacts/research_session_visited_commitment_usage.json').read_text())
    if usage['remaining_session_allowance_s']<cfg['time_cap_s']:raise PermissionError('session budget exhausted')


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean implementation before analysis')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started=time.perf_counter()
    def check():
        if time.perf_counter()-started>=cfg['time_cap_s']:raise TimeoutError('120-second analysis cap reached')
    p=dict(complete=False,label='incomplete',implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),parents=cfg['parents'],cells=[],new_environment_steps=0,new_imagined_transitions=0,model_inference_calls=0,dependencies=dict(python=sys.version,numpy=np.__version__))
    try:
        capture,stage=inputs(cfg);check()
        constants={d:source_constant(stage,d) for d in cfg['decoders']}
        for row in capture['cells']:
            check();p['cells'].append(build_row(row,constants[row['decoder']]))
        p['wall_clock_s']=time.perf_counter()-started;p.update(validate(p,cfg,capture,stage));check();p['complete']=True
    except Exception as exc:p['failure']=dict(type=type(exc).__name__,message=str(exc))
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p
