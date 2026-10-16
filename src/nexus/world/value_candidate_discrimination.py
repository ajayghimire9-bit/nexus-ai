"""Bounded frozen inference and recorded-outcome analysis; no environment collection."""
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
import torch
import yaml
from nexus.world.planning_value import sha,finite_array
from nexus.world.terminal_value import NAMES,TerminalReadout,score_conditions
from nexus.world.terminal_value_execution import checked_id_grid,fingerprints,save
from nexus.world.terminal_value_calibration import (parent_evidence,load_models,validate as validate_calibration,load_config as calibration_config)
from nexus.world.long_continuation import paired_interval
from nexus.world.long_continuation_execution import ExecutionMeter
from nexus.world.prediction_control_gap import candidate_sequences

CONFIG=Path('configs/value_candidate_discrimination.yaml')
PROTOCOL=Path('docs/NEXUS_VALUE_CANDIDATE_DISCRIMINATION_PROTOCOL.md')
OUTPUT=Path('artifacts/value_candidate_discrimination.json')
LOCK='737da7623b973f4ef176838dee742149f38a6d95ef3cc28fa859be099a635db8'
METRICS=('base_return','value_return','constant_return','actual16_return','benefit','vs_constant','base_regret','value_regret','constant_regret','actual16_regret','base_best','value_best','constant_best','tail_mse','tail_bias_sq','tail_centered_mse','constant_centered_mse','tail_centered_gain')


def inputs():
    if sha(CONFIG)!=LOCK or LOCK not in PROTOCOL.read_text():raise ValueError('protocol/config drift')
    cfg=yaml.safe_load(CONFIG.read_text())
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed input drift')
    parent,stage=parent_evidence()
    capture=json.loads(Path('artifacts/terminal_value_calibration.json').read_text())
    proof=json.loads(Path('artifacts/terminal_value_calibration_validation.json').read_text())
    rebuilt=validate_calibration(capture,calibration_config(),parent,stage)
    if proof.get('complete') is not True or proof['source_sha256']!=sha('artifacts/terminal_value_calibration.json') or any(proof[k]!=rebuilt[k] for k in ('label','summaries')):raise ValueError('missing/stale complete calibration proof')
    return cfg,parent,stage,capture


def error_decomposition(predicted,actual):
    p=finite_array(predicted,(4,));y=finite_array(actual,(4,));e=p-y
    mse=float(np.mean(e*e));bias=float(np.mean(e)**2);centered=float(np.mean((e-e.mean())**2));baseline=float(np.mean((y-y.mean())**2))
    if not math.isclose(mse,bias+centered,rel_tol=1e-12,abs_tol=1e-8):raise ValueError('MSE decomposition failure')
    return dict(tail_mse=mse,tail_bias_sq=bias,tail_centered_mse=centered,constant_centered_mse=baseline,tail_centered_gain=baseline-centered)


def cell_metrics(prefix,calibration,scores,indices):
    if set(scores)!=set(NAMES):raise ValueError('missing context')
    r16=np.array([sum(tr['rewards']) for tr in prefix['rollouts']],dtype=float)
    tail=finite_array(calibration['targets'],(4,));total=r16+tail;out={}
    for name in NAMES:
        s=scores[name];base=finite_array(s['base'],(16,));corrected=finite_array(s['corrected'],(16,));alive=finite_array(s['survival'],(16,))
        terminal=finite_array(s['terminal'],(16,));x=finite_array(s['inputs'],(16,11))
        if not np.allclose(corrected,base+alive*terminal,rtol=0,atol=1e-8) or np.any((alive<0)|(alive>1)):raise ValueError('value/survival scoring mismatch')
        if not np.allclose(x[indices],calibration['inputs'][name]['imagined'],rtol=0,atol=1e-6):raise ValueError('recorded endpoint replay mismatch')
        constant=finite_array(calibration['predictions'][name]['constant'],(4,))
        if not np.all(constant==constant[0]):raise ValueError('nonconstant reference')
        chosen={'base':int(np.argmax(base[indices])),'value':int(np.argmax(corrected[indices])),
                'constant':int(np.argmax(base[indices]+alive[indices]*constant)),'actual16':int(np.argmax(r16))}
        m={k+'_return':float(total[i]) for k,i in chosen.items()}
        m.update({k+'_regret':float(max(total)-total[i]) for k,i in chosen.items()})
        m.update({k+'_best':float(abs(total[i]-max(total))<=1e-8) for k,i in chosen.items() if k!='actual16'})
        m.update(benefit=m['value_return']-m['base_return'],vs_constant=m['value_return']-m['constant_return'])
        m.update(error_decomposition(calibration['predictions'][name]['imagined'],calibration['targets']))
        if set(m)!=set(METRICS):raise ValueError('metric schema drift')
        out[name]=m
    return out


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(cfg['decoders'],cfg['tasks'])))
    for r in cells.values():
        if set(r['metrics'])!=set(NAMES):raise ValueError('missing context metrics')
        for m in r['metrics'].values():
            if set(m)!=set(METRICS):raise ValueError('missing required metric')
            finite_array([m[k] for k in METRICS],(len(METRICS),))
    summaries={}
    for group,tasks in [('development',cfg['development_tasks']),('source',cfg['source_tasks'])]:
        paired={}
        for metric in METRICS:
            values=[statistics.mean(cells[d,t]['metrics'][str(s)][metric] for t,s in itertools.product(tasks,cfg['students'])) for d in cfg['decoders']]
            paired[metric]=dict(per_decoder=values,interval=paired_interval(values))
        per_task={str(t):{metric:paired_interval([statistics.mean(cells[d,t]['metrics'][str(s)][metric] for s in cfg['students']) for d in cfg['decoders']]) for metric in ('benefit','vs_constant','tail_centered_gain')} for t in tasks}
        zero={metric:paired_interval([statistics.mean(cells[d,t]['metrics']['zero'][metric] for t in tasks) for d in cfg['decoders']]) for metric in ('benefit','vs_constant','tail_centered_gain')}
        summaries[group]=dict(metrics=paired,per_task=per_task,zero=zero)
    ci=summaries['development']['metrics']['benefit']['interval']
    label='exploratory_in_set_inconclusive'
    if ci['mean']>=cfg['practical_margin'] and ci['lo']>0:label='exploratory_in_set_gain'
    elif ci['hi']<0:label='exploratory_in_set_harm'
    return dict(label=label,summaries=summaries)


def validate_result(p,cfg,parent,stage,capture):
    prefix={r['task']:r for r in capture['prefixes']};cal={(r['decoder'],r['task']):r for r in capture['cells']}
    for row in p['cells']:
        d,t=row['decoder'],row['task'];prior=cal[d,t]
        if row['before']!=prior['before'] or row['after']!=prior['before']:raise ValueError('frozen model/context drift')
        expected=candidate_sequences(calibration_config()['candidate_base']+t)
        if not np.array_equal(row['sequences'],expected):raise ValueError('candidate pairing drift')
        readout=TerminalReadout(**stage['readouts'][str(d)]['state'])
        for s in row['scores'].values():
            if not np.allclose(readout.predict(s['inputs']),s['terminal'],rtol=0,atol=1e-8):raise ValueError('readout drift')
        rebuilt=cell_metrics(prefix[t],prior,row['scores'],cfg['candidate_indices'])
        if rebuilt!=row['metrics']:raise ValueError('raw/metric mismatch')
    if p['parents']!=cfg['parents'] or p['config_sha256']!=sha(CONFIG) or p['protocol_sha256']!=sha(PROTOCOL):raise ValueError('provenance drift')
    if p['model_states']!=cfg['model_cap'] or p['new_environment_steps']!=0:raise ValueError('resource counts drift')
    finite_array([p['wall_clock_s']],(1,))
    if not 0<=p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time limit exceeded')
    for key in ('checkpoint_before','checkpoint_after'):
        if p[key]!=dict(verified=120,missing=0,mismatched=0):raise ValueError('missing checkpoint audit')
    return summarize(p['cells'],cfg)


class InferenceMeter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.model_cap=cfg['model_cap'];self.env_cap=0;self.counts={'model_states':0}
    def check(self):
        if time.perf_counter()>self.deadline:raise TimeoutError('recorded-data inference cap reached')
    def instrument_env(self,env):raise RuntimeError('no environment permitted in recorded-data analysis')


def prepare():
    cfg,_,_,_=inputs()
    return dict(status='ready_recorded_data_only',config_sha256=sha(CONFIG),new_environment_steps=0,model_cap=cfg['model_cap'],time_cap_s=cfg['time_cap_s'])


def execute():
    cfg,parent,stage,capture=inputs()
    if OUTPUT.exists():raise RuntimeError('refusing overwrite/repeat')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean implementation first')
    started=time.perf_counter();meter=InferenceMeter(cfg)
    p=dict(complete=False,label='incomplete',source_dirty=False,implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),parents=cfg['parents'],cells=[],new_environment_steps=0)
    try:
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        p['checkpoint_before']=verify_checkpoint_integrity();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        prefix={r['task']:r for r in capture['prefixes']};cal={(r['decoder'],r['task']):r for r in capture['cells']}
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__)
        for d in cfg['decoders']:
            readout=TerminalReadout(**stage['readouts'][str(d)]['state']);digest=readout.digest()
            for t in cfg['tasks']:
                models=load_models(d,t,rep,confirmation,parent,stage);before=fingerprints(models)
                for m in models.values():meter.instrument_model(m)
                seq=candidate_sequences(calibration_config()['candidate_base']+t)
                scores={name:score_conditions(m,prefix[t]['obs'],seq,readout) for name,m in models.items()}
                after=fingerprints(models)
                if before!=after or digest!=readout.digest():raise ValueError('evaluation modified frozen inputs')
                p['cells'].append(dict(decoder=d,task=t,before=before,after=after,sequences=seq.tolist(),scores=scores,
                    metrics=cell_metrics(prefix[t],cal[d,t],scores,cfg['candidate_indices'])))
            p['wall_clock_s']=time.perf_counter()-started;p['model_states']=meter.counts['model_states'];save(OUTPUT,p)
            print(f'recorded analysis decoder={d} seconds={p["wall_clock_s"]:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started;p['model_states']=meter.counts['model_states']
        p.update(validate_result(p,cfg,parent,stage,capture));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;p['model_states']=meter.counts['model_states'];save(OUTPUT,p)
    return p
