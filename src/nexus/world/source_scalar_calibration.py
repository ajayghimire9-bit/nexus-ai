"""One source-fitted external scalar; original neural/readout weights unchanged."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
import numpy as np
import yaml
from nexus.world import visited_commitment as visited
from nexus.world.visited_value_ranking import source_constant

CONFIG=Path('configs/source_scalar_calibration.yaml')
PROTOCOL=Path('docs/NEXUS_SOURCE_SCALAR_PROTOCOL.md')
ALLOCATION=Path('configs/source_scalar_allocation.json')
FIT=Path('artifacts/source_scalar_fit.json')
OUTPUT=Path('artifacts/source_scalar_calibration.json')
FIELDS=('block_base','block_uncalibrated','block_calibrated','gain_vs_base','gain_vs_uncalibrated','first_base','first_uncalibrated','first_calibrated','first_gain_vs_base','first_gain_vs_uncalibrated','base_regret','uncalibrated_regret','calibrated_regret','centered_error_benefit','sequence_changed_vs_base','sequence_changed_vs_uncalibrated')


def sha(path):return visited.prior.sha(path)


def seed_sets(cfg):
    return [{visited.reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {s for d,t in itertools.product(range(10),range(3)) for s in visited.collection_seeds(cfg,d,t)},
        {visited.candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in visited.future_seeds(cfg,d,t,v)}]


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    for key,value in dict(decoders=list(range(10)),students=list(range(5)),states_per_task=2,phase=50,horizon=16,n_candidates=16,total_steps=64,practical_margin=1.0,time_cap_s=360,env_cap=75960,model_cap=15667200).items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked design/budget changed')
    if cfg['tasks']!=visited.prior.load_config()['tasks']:raise ValueError('physics changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('historical source/ledger changed')
    visited.check_seeds(cfg);blocked=set().union(*seed_sets(visited.load_config()))
    if blocked & set().union(*seed_sets(cfg)):raise ValueError('closed visited seeds reused')
    return cfg


def source_terms(cells):
    source=visited.checked_id_grid([r for r in cells if r['task'] in range(8)],('decoder','task'),set(itertools.product(range(10),range(8))))
    terms=[]
    for (d,t),row in source.items():
        y=visited.prior.finite_array(row['targets'],(4,));yc=y-y.mean()
        for s in range(5):
            p=visited.prior.finite_array(row['predictions'][str(s)]['imagined'],(4,));pc=p-p.mean()
            terms.append(dict(decoder=d,task=t,context=str(s),covariance_sum=float(pc@yc),variance_sum=float(pc@pc)))
    numerator=math.fsum(r['covariance_sum'] for r in terms);denominator=math.fsum(r['variance_sum'] for r in terms)
    degenerate=denominator<=1e-12;raw=0. if degenerate else numerator/denominator
    return dict(beta=float(min(1.,max(0.,raw))),beta_raw=float(raw),degenerate=degenerate,numerator=numerator,denominator=denominator,source_examples=1600,groups=terms)


def require_allocation(cfg):
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),runs=1,time_cap_s=360,env_cap=75960,model_cap=15667200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise PermissionError('stale/missing scalar allocation')
    usage=json.loads(Path('artifacts/research_session_visited_value_ranking_usage.json').read_text())
    if usage['remaining_session_allowance_s']<cfg['time_cap_s']:raise PermissionError('session budget exhausted')


def source_evidence():
    from nexus.world import terminal_value_calibration as cal
    capture=json.loads(cal.OUTPUT.read_text());proof=json.loads(Path('artifacts/terminal_value_calibration_validation.json').read_text());parent,stage=cal.parent_evidence()
    rebuilt=cal.validate(capture,cal.load_config(),parent,stage)
    if proof.get('complete') is not True or proof['source_sha256']!=sha(cal.OUTPUT) or any(proof[k]!=rebuilt[k] for k in ('label','summaries')):raise ValueError('missing complete source-calibration proof')
    return capture


def fit_source():
    cfg=load_config();require_allocation(cfg)
    if FIT.exists():raise RuntimeError('refusing source refit/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit protocol before fitting')
    started=time.perf_counter();result=dict(complete=False,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),source_sha256=sha('artifacts/terminal_value_calibration.json'),proof_sha256=sha('artifacts/terminal_value_calibration_validation.json'),implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,new_environment_steps=0,new_imagined_transitions=0)
    try:
        result.update(source_terms(source_evidence()['cells']))
        if time.perf_counter()-started>=cfg['time_cap_s']:raise TimeoutError('source fitting exceeded total cap')
        result['complete']=True
    except Exception as exc:result['failure']=dict(type=type(exc).__name__,message=str(exc))
    result['wall_clock_s']=time.perf_counter()-started
    visited.save(FIT,result);return result


def require_fit(cfg,*,committed=True):
    fit=json.loads(FIT.read_text())
    if fit.get('complete') is not True or fit.get('source_dirty') is not False or fit['config_sha256']!=sha(CONFIG) or fit['protocol_sha256']!=sha(PROTOCOL) or fit['source_sha256']!=sha('artifacts/terminal_value_calibration.json') or fit['proof_sha256']!=sha('artifacts/terminal_value_calibration_validation.json'):raise ValueError('stale/missing source-only fit')
    visited.prior.finite_array([fit[k] for k in ('beta','beta_raw','numerator','denominator')],(4,))
    if type(fit.get('source_examples')) is not int or fit['source_examples']!=1600 or type(fit.get('degenerate')) is not bool:raise ValueError('invalid source-fit schema')
    for key,value in source_terms(json.loads(Path('artifacts/terminal_value_calibration.json').read_text())['cells']).items():
        if fit.get(key)!=value:raise ValueError('fitted scalar not from locked source rule')
    visited.prior.finite_array([fit['wall_clock_s']],(1,))
    if not 0<fit['wall_clock_s']<cfg['time_cap_s']:raise ValueError('fit runtime invalid')
    if committed:
        saved=subprocess.check_output(['git','show','HEAD:'+str(FIT)],text=True)
        if saved!=FIT.read_text():raise ValueError('commit immutable fitted scalar before fresh collection')
        subprocess.run(['git','merge-base','--is-ancestor',fit['implementation_sha'],'HEAD'],check=True)
    return fit


def calibrated_score(scores,beta,constant):
    visited.prior.finite_array([beta,constant],(2,))
    if not 0<=beta<=1:raise ValueError('scalar outside registered bounds')
    b=visited.prior.finite_array(scores['base'],(16,));a=visited.prior.finite_array(scores['survival'],(16,));p=visited.prior.finite_array(scores['terminal'],(16,))
    return b+a*(constant+beta*(p-constant))


def row_metrics(row,beta,constant):
    first=np.asarray([visited.prior.total(tr['rewards'],64) for tr in row['first_traces']]);tails=np.asarray([visited.prior.total(tr['rewards'],48) for tr in row['block_tails']]);blocks=np.asarray([visited.prior.total(pre['rewards'],16)+tail for pre,tail in zip(row['prefixes'],tails)])
    seq=np.asarray(row['sequences']);out={}
    for name,s in row['scores'].items():
        base=visited.prior.finite_array(s['base'],(16,));uncal=visited.prior.finite_array(s['corrected'],(16,));scaled=calibrated_score(s,beta,constant)
        ids=dict(base=int(np.argmax(base)),uncalibrated=int(np.argmax(uncal)),calibrated=int(np.argmax(scaled)))
        m={f'block_{k}':float(blocks[i]) for k,i in ids.items()};m.update({f'first_{k}':float(first[int(seq[i,0])]) for k,i in ids.items()});m.update({k+'_regret':float(max(blocks)-blocks[i]) for k,i in ids.items()})
        p=np.asarray(s['terminal']);cal=constant+beta*(p-constant);e=p-tails;ec=cal-tails
        m.update(gain_vs_base=m['block_calibrated']-m['block_base'],gain_vs_uncalibrated=m['block_calibrated']-m['block_uncalibrated'],first_gain_vs_base=m['first_calibrated']-m['first_base'],first_gain_vs_uncalibrated=m['first_calibrated']-m['first_uncalibrated'],
            centered_error_benefit=float(np.mean((e-e.mean())**2)-np.mean((ec-ec.mean())**2)),sequence_changed_vs_base=float(ids['calibrated']!=ids['base']),sequence_changed_vs_uncalibrated=float(ids['calibrated']!=ids['uncalibrated']))
        if set(m)!=set(FIELDS):raise ValueError('scalar metric schema drift')
        visited.prior.finite_array([m[k] for k in FIELDS],(len(FIELDS),));out[name]=m
    return out


def summarize(rows,cfg):
    cells=visited.checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for row in cells.values():
        if set(row['metrics'])!=set(visited.prior.NAMES):raise ValueError('missing scoring context')
        for m in row['metrics'].values():
            if set(m)!=set(FIELDS):raise ValueError('missing scalar metric')
            visited.prior.finite_array([m[k] for k in FIELDS],(len(FIELDS),))
    definitions=[('pooled',range(3),range(2),[str(s) for s in range(5)]),('zero_context',range(3),range(2),['zero'])]
    definitions += [(f'task_{t}',[t],range(2),[str(s) for s in range(5)]) for t in range(3)]
    definitions += [(name,range(3),[v],[str(s) for s in range(5)]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    groups={}
    for name,tasks,visitors,students in definitions:
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][s][metric] for t,v,s in itertools.product(tasks,visitors,students)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=visited.prior.paired_interval(values))
    base=groups['pooled']['gain_vs_base']['interval'];uncal=groups['pooled']['gain_vs_uncalibrated']['interval']
    label='source_scalar_selection_gain' if base['mean']>=1 and base['lo']>0 and uncal['lo']>0 else 'scalar_selection_gain_not_established'
    return dict(label=label,groups=groups)


def finalize(p,cfg,parent,stage):
    fit=require_fit(cfg);rows=[]
    if p['source_fit_sha256']!=sha(FIT):raise ValueError('fitted scalar changed during evaluation')
    for row in p['cells']:
        rows.append(dict(decoder=row['decoder'],task=row['task'],state=row['state'],metrics=row_metrics(row,fit['beta'],source_constant(stage,row['decoder']))))
    result=summarize(rows,cfg)
    return dict(label=result['label'],uncalibrated_commitment_label=p['label'],scalar_rows=rows,scalar_groups=result['groups'])


def execute():
    cfg=load_config();require_allocation(cfg);fit=require_fit(cfg)
    return visited.execute(configuration=cfg,config_path=CONFIG,protocol_path=PROTOCOL,output=OUTPUT,allocation_path=ALLOCATION,preflight=require_allocation,finalize=finalize,prior_execution_s=fit['wall_clock_s'],execution_metadata=dict(source_fit_sha256=sha(FIT),source_fit_wall_s=fit['wall_clock_s'],beta=fit['beta']))


def audit():
    cfg=load_config();p=json.loads(OUTPUT.read_text());parent,stage=visited.prior.parent_evidence()
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid scalar evaluation')
    fit=require_fit(cfg)
    original=visited.validate(p,cfg,parent,stage,config_path=CONFIG,protocol_path=PROTOCOL)
    for key in original:
        if key!='label' and p[key]!=original[key]:raise ValueError('original control metrics changed')
    if p['uncalibrated_commitment_label']!=original['label'] or p['allocation_sha256']!=sha(ALLOCATION) or p['beta']!=fit['beta']:raise ValueError('fit/allocation provenance changed')
    rebuilt=finalize({**p,'label':original['label']},cfg,parent,stage)
    if any(p[k]!=v for k,v in rebuilt.items()):raise ValueError('scalar results do not reproduce')
    return dict(audit_passed=True,label=p['label'],beta=p['beta'],raw_sha256=sha(OUTPUT),groups=p['scalar_groups'])
