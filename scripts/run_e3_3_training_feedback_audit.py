"""Bounded offline training-feedback audit. No collection/model execution."""
import argparse
import json
import platform
import signal
import subprocess
import time

import numpy as np

from nexus.evolution1.catalogue import digest
from nexus.evolution2.full_policy_source import ROOT,sha,verify_file
from nexus.evolution2 import training_feedback_audit as a

CONFIG=ROOT/'configs/e3_3_training_feedback_audit.json'
PROTOCOL=ROOT/'docs/NEXUS_E3_3_TRAINING_FEEDBACK_PROTOCOL.md'
ALLOCATION=ROOT/'configs/e3_3_training_feedback_allocation.json'
RESULT=ROOT/'artifacts/e3_3_training_feedback_audit.json'
FROZEN=ROOT/'artifacts/e3_3_frozen_fold_predictions.json'
USAGE=ROOT/'artifacts/e3_3_training_feedback_usage.json'
VALIDATION=ROOT/'artifacts/e3_3_training_feedback_validation.json'
PREVIOUS=ROOT/'artifacts/e3_2_return_feedback_validation.json'


def validate_config(c):
    expected=dict(version='e3_3_training_only_v1',input='artifacts/e3_2_frozen_predictor.json',
        input_sha256='e84d55ce4b8f3bd6dbc4cda1edcbecfe411e808ed91c63a16504b52fb3453b83',
        families=['pendulum','acrobot'],model_bundles=[0,1],training_episode_ids=[0,1,2],held_out_blocks=[0,1,2],
        feature_dimension=192,ridge=1.0,shuffle_seed_base=31,practical_return_margin=1.0,
        time_cap_s=15,env_cap=0,imagined_cap=0,neural_inference_cap=0,ridge_fit_cap=6)
    if json.dumps(c,sort_keys=True)!=json.dumps(expected,sort_keys=True):raise ValueError('locked_config')


def load_training(c):
    validate_config(c);path=ROOT/c['input'];verify_file(path,c['input_sha256'])
    saved=json.loads(path.read_text())
    bank,features=saved['training_pairs'],saved['feature_rows']
    a.validate_bank(bank,features)
    return bank,features


def write_new(path,data):
    with path.open('x') as out:json.dump(data,out,allow_nan=False);out.write('\n');out.flush()


def verify(c):
    if VALIDATION.exists():raise FileExistsError('preserve_validation')
    start=time.perf_counter();p=json.loads(RESULT.read_text());validate_config(c)
    if not p['declared_complete'] or p['config']!=c:raise ValueError('complete_locked_run_required')
    bank,features=load_training(c);verify_file(FROZEN,p['frozen_fold_sha256'])
    frozen=json.loads(FROZEN.read_text())
    if frozen['training_projection_sha256']!=digest([bank,features]):raise ValueError('training_projection')
    analysis=a.verify_frozen_folds(frozen['folds'],bank,features)
    if analysis!=p['analysis'] or p['ridge_fits_completed']!=6:raise ValueError('analysis_or_fit_count')
    for name,expected in p['historical_artifacts_sha256'].items():verify_file(ROOT/name,expected)
    import hashlib
    for name,expected in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('execution_source_hash')
    wall=time.perf_counter()-start;used=p['session_ledger']['used_after_s']+wall
    out=dict(valid=True,capture_sha256=sha(RESULT),frozen_fold_sha256=sha(FROZEN),folds=3,predictions=12,
        coefficient_models_verified=6,ridge_fits=0,new_real_steps=0,new_imagined_transitions=0,neural_inference=0,
        historical_json_preserved=len(p['historical_artifacts_sha256']),wall_s=wall,
        session_ledger=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used))
    write_new(VALIDATION,out);return out


def run(c):
    validate_config(c)
    if any(x.exists() for x in (RESULT,FROZEN,USAGE)):raise FileExistsError('one_run_only')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT,text=True).strip():raise RuntimeError('commit_first')
    names=['scripts/run_e3_3_training_feedback_audit.py','src/nexus/evolution2/training_feedback_audit.py',
        'src/nexus/evolution2/generated_strategies.py','src/nexus/evolution2/planner_quality_diagnostic.py',
        'src/nexus/evolution2/return_feedback.py','tests/test_e3_3_training_feedback_audit.py']
    names += [str(p.relative_to(ROOT)) for p in (CONFIG,PROTOCOL,ALLOCATION)]
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    if not set(names)<=tracked:raise RuntimeError('tracked_implementation_required')
    allocation=json.loads(ALLOCATION.read_text());prior=json.loads(PREVIOUS.read_text())
    verify_file(PREVIOUS,allocation['previous_validation_sha256'])
    if not allocation['authorized'] or allocation['runs']!=1 or allocation['automatic_retry'] is not False:raise ValueError('one_run_authority')
    if allocation['config_sha256']!=sha(CONFIG) or allocation['protocol_sha256']!=sha(PROTOCOL):raise ValueError('allocation_hash')
    if allocation['env_cap']!=0 or allocation['imagined_cap']!=0 or allocation['ridge_fit_cap']!=6:raise ValueError('allocation_caps')
    used=prior['session_ledger']['used_after_s']
    if used!=allocation['session_used_before_s'] or allocation['time_cap_s']!=c['time_cap_s'] or used+c['time_cap_s']>3600:raise ValueError('budget')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    start=time.perf_counter();cpu=time.process_time();deadline=start+c['time_cap_s']
    write_new(USAGE,dict(consumed=True,automatic_retry=False,allocation_sha256=sha(ALLOCATION),execution_sha=revision))
    p=dict(declared_complete=False,config=c,execution_sha=revision,code_sha256={n:sha(ROOT/n) for n in names},
        dependencies=dict(python=platform.python_version(),numpy=np.__version__),ridge_fits_reserved=0,ridge_fits_completed=0,
        real_steps=0,imagined_transitions=0,neural_inference=0,folds_completed=0)
    def guard(stage):
        if time.perf_counter()>=deadline:raise TimeoutError('time_cap')
        if stage=='reserve':
            if p['ridge_fits_reserved']>=6:raise ValueError('fit_cap')
            p['ridge_fits_reserved']+=1
        elif stage=='complete':p['ridge_fits_completed']+=1
    def alarm(signum,frame):raise TimeoutError('time_cap_alarm')
    previous_handler=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,c['time_cap_s'])
    folds=[]
    try:
        p['historical_artifacts_sha256']={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'artifacts').rglob('*.json') if f not in (RESULT,FROZEN,USAGE,VALIDATION)}
        bank,features=load_training(c)
        for held in c['held_out_blocks']:
            guard('check');folds.append(a.predict_fold(bank,features,held,fit_guard=guard));p['folds_completed']+=1
        write_new(FROZEN,dict(training_projection_sha256=digest([bank,features]),execution_sha=revision,folds=folds))
        p['frozen_fold_sha256']=sha(FROZEN);guard('check')
        p['analysis']=a.verify_frozen_folds(folds,bank,features)
        for name,expected in p['historical_artifacts_sha256'].items():verify_file(ROOT/name,expected)
        guard('check');p['declared_complete']=True
    except (Exception,KeyboardInterrupt) as exc:
        p['failure']=f'{type(exc).__name__}: {exc}';p['partial_folds']=folds
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)
    wall=time.perf_counter()-start;p.update(wall_s=wall,cpu_s=time.process_time()-cpu)
    p['session_ledger']=dict(used_before_s=used,used_after_s=used+wall,remaining_after_s=3600-used-wall)
    write_new(RESULT,p)
    return {k:p.get(k) for k in ('declared_complete','failure','analysis','ridge_fits_completed','wall_s','session_ledger')}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    c=json.loads(CONFIG.read_text());print(json.dumps(verify(c) if args.verify else run(c)))
