"""Bounded offline training-feedback audit. No collection/model execution."""
import argparse
import json
import os
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
PROFILE='e3_3'


def configure_residual():
    """Exact second profile; no arbitrary input or target registration."""
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,FROZEN,USAGE,VALIDATION,PREVIOUS,PROFILE
    PROFILE='e3_5'
    CONFIG=ROOT/'configs/e3_5_residual_advantage.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_5_RESIDUAL_ADVANTAGE_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_5_residual_advantage_allocation.json'
    RESULT=ROOT/'artifacts/e3_5_residual_advantage.json'
    FROZEN=ROOT/'artifacts/e3_5_frozen_fold_predictions.json'
    USAGE=ROOT/'artifacts/e3_5_residual_advantage_usage.json'
    VALIDATION=ROOT/'artifacts/e3_5_residual_advantage_validation.json'
    PREVIOUS=ROOT/'artifacts/e3_4_feedback_coverage_validation.json'


def configure_features():
    """Feature ablation adapter; reuse the same one-run host and ridge learner."""
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,FROZEN,USAGE,VALIDATION,PREVIOUS,PROFILE,a
    from nexus.evolution2 import feature_informativeness
    a=feature_informativeness;PROFILE='e3_6'
    CONFIG=ROOT/'configs/e3_6_feature_informativeness.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_6_FEATURE_INFORMATIVENESS_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_6_feature_informativeness_allocation.json'
    RESULT=ROOT/'artifacts/e3_6_feature_informativeness.json'
    FROZEN=ROOT/'artifacts/e3_6_frozen_fold_predictions.json'
    USAGE=ROOT/'artifacts/e3_6_feature_informativeness_usage.json'
    VALIDATION=ROOT/'artifacts/e3_6_feature_informativeness_validation.json'
    PREVIOUS=ROOT/'artifacts/e3_5_residual_advantage_validation.json'


def configure_transitions():
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,FROZEN,USAGE,VALIDATION,PREVIOUS,PROFILE
    configure_features();PROFILE='e3_7'
    CONFIG=ROOT/'configs/e3_7_transition_evidence.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_7_TRANSITION_EVIDENCE_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_7_transition_evidence_allocation.json'
    RESULT=ROOT/'artifacts/e3_7_transition_evidence.json'
    FROZEN=ROOT/'artifacts/e3_7_frozen_fold_predictions.json'
    USAGE=ROOT/'artifacts/e3_7_transition_evidence_usage.json'
    VALIDATION=ROOT/'artifacts/e3_7_transition_evidence_validation.json'
    PREVIOUS=ROOT/'artifacts/e3_7_preflight_recovery.json'


def configure_compact():
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,FROZEN,USAGE,VALIDATION,PREVIOUS,PROFILE
    configure_transitions();PROFILE='e3_8'
    CONFIG=ROOT/'configs/e3_8_compact_interactions.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_8_COMPACT_INTERACTIONS_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_8_compact_interactions_allocation.json'
    RESULT=ROOT/'artifacts/e3_8_compact_interactions.json'
    FROZEN=ROOT/'artifacts/e3_8_frozen_fold_predictions.json'
    USAGE=ROOT/'artifacts/e3_8_compact_interactions_usage.json'
    VALIDATION=ROOT/'artifacts/e3_8_compact_interactions_validation.json'
    PREVIOUS=ROOT/'artifacts/e3_7_transition_evidence_validation.json'


def validate_config(c):
    expected=dict(version='e3_3_training_only_v1',input='artifacts/e3_2_frozen_predictor.json',
        input_sha256='e84d55ce4b8f3bd6dbc4cda1edcbecfe411e808ed91c63a16504b52fb3453b83',
        families=['pendulum','acrobot'],model_bundles=[0,1],training_episode_ids=[0,1,2],held_out_blocks=[0,1,2],
        feature_dimension=192,ridge=1.0,shuffle_seed_base=31,practical_return_margin=1.0,
        time_cap_s=15,env_cap=0,imagined_cap=0,neural_inference_cap=0,ridge_fit_cap=6)
    if PROFILE in ('e3_5','e3_6','e3_7','e3_8'):
        expected.update(version='e3_5_training_residual_v1',input='artifacts/e3_4_predictor_b9.json',
            input_sha256='5bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a',
            training_episode_ids=list(range(9)),held_out_blocks=list(range(9)),ridge_fit_cap=27)
    if PROFILE in ('e3_6','e3_7','e3_8'):
        expected.update(version='e3_6_within_model_features_v1',time_cap_s=30,ridge_fit_cap=720,
            feature_groups={k:list(v) for k,v in a.groups(PROFILE).items()},permutation_ids=list(a.PERMUTATIONS),
            permutation_seed_base=613000,minimum_mae_reduction=.05,minimum_permutation_wins=18)
    if PROFILE in ('e3_7','e3_8'):
        from nexus.evolution2.transition_evidence import SOURCES
        expected.update(version='e3_7_transition_evidence_v1',ridge_fit_cap=360,support_rows=32,
            support_statistics=['normalized_mean_absolute_delta','normalized_linear_residual_mae','action_coverage'],
            source_arrays=list(SOURCES),descriptor_lstsq_calls=4)
    if PROFILE=='e3_8':expected.update(version='e3_8_compact_interactions_v1',feature_dimension=21,feature_builder='compact_observation_support_v1')
    if json.dumps(c,sort_keys=True)!=json.dumps(expected,sort_keys=True):raise ValueError('locked_config')


def load_training(c,provenance=None):
    validate_config(c);path=ROOT/c['input'];verify_file(path,c['input_sha256'])
    saved=json.loads(path.read_text())
    bank,features=saved['training_pairs'],saved['feature_rows']
    if PROFILE in ('e3_7','e3_8'):
        from nexus.evolution2.transition_evidence import prepare
        if provenance is not None:provenance['support_descriptor_lstsq_calls']=0
        def count_descriptor():
            if provenance is not None:provenance['support_descriptor_lstsq_calls']+=1
        features,records=prepare(saved,bank,features,on_descriptor=count_descriptor)
        if provenance is not None:provenance['source_support']=records
        if PROFILE=='e3_8':
            from nexus.evolution2.compact_interactions import augment
            features=augment(features)
    a.validate_bank(bank,features,PROFILE)
    return bank,features


def write_new(path,data):
    with path.open('x') as out:json.dump(data,out,allow_nan=False);out.write('\n');out.flush()


def verify(c):
    if VALIDATION.exists():raise FileExistsError('preserve_validation')
    start=time.perf_counter();p=json.loads(RESULT.read_text());validate_config(c)
    if not p['declared_complete'] or p['config']!=c:raise ValueError('complete_locked_run_required')
    provenance={};bank,features=load_training(c,provenance);verify_file(FROZEN,p['frozen_fold_sha256'])
    if PROFILE in ('e3_7','e3_8') and provenance.get('source_support')!=p['source_support']:raise ValueError('source_support_provenance')
    frozen=json.loads(FROZEN.read_text())
    if frozen['training_projection_sha256']!=digest([bank,features]):raise ValueError('training_projection')
    analysis=a.verify_frozen_folds(frozen['folds'],bank,features,PROFILE)
    if analysis!=p['analysis'] or p['ridge_fits_completed']!=c['ridge_fit_cap']:raise ValueError('analysis_or_fit_count')
    if PROFILE in ('e3_6','e3_7','e3_8') and p['feature_variability']!=a.variability(bank,features,PROFILE):raise ValueError('feature_variability')
    for name,expected in p['historical_artifacts_sha256'].items():verify_file(ROOT/name,expected)
    import hashlib
    for name,expected in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('execution_source_hash')
    wall=time.perf_counter()-start;used=p['session_ledger']['used_after_s']+wall
    out=dict(valid=True,capture_sha256=sha(RESULT),frozen_fold_sha256=sha(FROZEN),folds=len(c['held_out_blocks']),predictions=len(bank),
        coefficient_models_verified=c['ridge_fit_cap'],ridge_fits=0,new_real_steps=0,new_imagined_transitions=0,neural_inference=0,
        historical_json_preserved=len(p['historical_artifacts_sha256']),wall_s=wall,
        session_ledger=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used))
    if PROFILE in ('e3_7','e3_8'):out['support_descriptor_lstsq_calls']=4
    write_new(VALIDATION,out);return out


def run(c):
    validate_config(c)
    if any(x.exists() for x in (RESULT,FROZEN,USAGE)):raise FileExistsError('one_run_only')
    thread_env={key:os.environ.get(key) for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}
    if PROFILE in ('e3_5','e3_6','e3_7','e3_8') and any(v!='1' for v in thread_env.values()):raise ValueError('single_cpu_thread_environment_required')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT,text=True).strip():raise RuntimeError('commit_first')
    names=['scripts/run_e3_3_training_feedback_audit.py','src/nexus/evolution2/training_feedback_audit.py',
        'src/nexus/evolution2/generated_strategies.py','src/nexus/evolution2/planner_quality_diagnostic.py',
        'src/nexus/evolution2/return_feedback.py','tests/test_e3_3_training_feedback_audit.py']
    names += [str(p.relative_to(ROOT)) for p in (CONFIG,PROTOCOL,ALLOCATION)]
    if PROFILE=='e3_5':names.append('tests/test_e3_5_residual_advantage.py')
    if PROFILE=='e3_6':names+=['src/nexus/evolution2/feature_informativeness.py','tests/test_e3_6_feature_informativeness.py',
        'src/nexus/core/strategy_memory.py']
    if PROFILE in ('e3_7','e3_8'):names+=['src/nexus/evolution2/feature_informativeness.py','src/nexus/evolution2/transition_evidence.py',
        'src/nexus/evolution2/fit_clock.py','src/nexus/core/strategy_memory.py','tests/test_e3_7_transition_evidence.py']
    if PROFILE=='e3_8':names+=['src/nexus/evolution2/compact_interactions.py','tests/test_e3_8_learning_interfaces.py',
        'src/nexus/core/episode_context.py','src/nexus/evolution2/planner_evidence.py','src/nexus/evolution2/continual_state.py',
        'src/nexus/evolution2/staged_study.py','src/nexus/evolution2/learning_lab.py','src/nexus/meta/controller.py',
        'scripts/demo_learning_interfaces.py','scripts/build_learning_lab_replay.py','scripts/run_fresh_contextual_study.py',
        'configs/fresh_contextual_selection_design.json']
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    if not set(names)<=tracked:raise RuntimeError('tracked_implementation_required')
    allocation=json.loads(ALLOCATION.read_text());prior=json.loads(PREVIOUS.read_text())
    verify_file(PREVIOUS,allocation['previous_validation_sha256'])
    if not allocation['authorized'] or allocation['runs']!=1 or allocation['automatic_retry'] is not False:raise ValueError('one_run_authority')
    if allocation['config_sha256']!=sha(CONFIG) or allocation['protocol_sha256']!=sha(PROTOCOL):raise ValueError('allocation_hash')
    if allocation['env_cap']!=0 or allocation['imagined_cap']!=0 or allocation['ridge_fit_cap']!=c['ridge_fit_cap']:raise ValueError('allocation_caps')
    used=prior['session_ledger']['used_after_s']
    if used!=allocation['session_used_before_s'] or allocation['time_cap_s']!=c['time_cap_s'] or used+c['time_cap_s']>3600:raise ValueError('budget')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    start=time.perf_counter();cpu=time.process_time();deadline=start+c['time_cap_s']
    write_new(USAGE,dict(consumed=True,automatic_retry=False,allocation_sha256=sha(ALLOCATION),execution_sha=revision))
    p=dict(declared_complete=False,config=c,execution_sha=revision,code_sha256={n:sha(ROOT/n) for n in names},
        dependencies=dict(python=platform.python_version(),numpy=np.__version__),ridge_fits_reserved=0,ridge_fits_completed=0,
        real_steps=0,imagined_transitions=0,neural_inference=0,folds_completed=0)
    if PROFILE in ('e3_5','e3_6','e3_7','e3_8'):p['dependencies']['thread_env']=thread_env
    def guard(stage):
        if time.perf_counter()>=deadline:raise TimeoutError('time_cap')
        if stage=='reserve':
            if p['ridge_fits_reserved']>=c['ridge_fit_cap']:raise ValueError('fit_cap')
            p['ridge_fits_reserved']+=1
        elif stage=='complete':p['ridge_fits_completed']+=1
    def alarm(signum,frame):raise TimeoutError('time_cap_alarm')
    previous_handler=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,c['time_cap_s'])
    folds=[]
    try:
        p['historical_artifacts_sha256']={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'artifacts').rglob('*.json') if f not in (RESULT,FROZEN,USAGE,VALIDATION)}
        bank,features=load_training(c,provenance=p)
        for held in c['held_out_blocks']:
            guard('check');folds.append(a.predict_fold(bank,features,held,fit_guard=guard,profile=PROFILE));p['folds_completed']+=1
        write_new(FROZEN,dict(training_projection_sha256=digest([bank,features]),execution_sha=revision,folds=folds))
        p['frozen_fold_sha256']=sha(FROZEN);guard('check')
        p['analysis']=a.verify_frozen_folds(folds,bank,features,PROFILE)
        if PROFILE in ('e3_6','e3_7','e3_8'):p['feature_variability']=a.variability(bank,features,PROFILE)
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
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true')
    group=parser.add_mutually_exclusive_group();group.add_argument('--residual',action='store_true');group.add_argument('--features',action='store_true');group.add_argument('--transitions',action='store_true');group.add_argument('--compact',action='store_true');args=parser.parse_args()
    if args.residual:configure_residual()
    if args.features:configure_features()
    if args.transitions:configure_transitions()
    if args.compact:configure_compact()
    c=json.loads(CONFIG.read_text());print(json.dumps(verify(c) if args.verify else run(c)))
