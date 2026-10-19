"""One locked full-feedback study; --audit performs offline verification only."""
import argparse
import importlib.util
import json
import platform
import subprocess
import time

import gymnasium
import numpy as np
import torch

from nexus.evolution2 import full_policy_source as h
from nexus.evolution2 import return_feedback as r
from nexus.evolution2 import feedback_coverage as coverage

CONFIG=h.ROOT/'configs/e3_2_return_feedback.json'
VALIDATION=h.ROOT/'artifacts/e3_2_return_feedback_validation.json'


def audit(c):
    is_coverage=c['version']=='coverage_feedback_v1'
    validation=h.ROOT/'artifacts/e3_4_feedback_coverage_validation.json' if is_coverage else VALIDATION
    if validation.exists():raise FileExistsError('preserve_audit')
    start=time.perf_counter();paths=h.run_paths(c)
    spec=importlib.util.spec_from_file_location('full_policy_verifier',h.ROOT/'scripts/verify_unified_full_policy_source.py')
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    p=json.loads(paths['result'].read_text());result=verifier.verify(p,paths['journal'])
    if is_coverage:
        if coverage.verify_selectors(p,c)!=p['coverage_analysis']:raise ValueError('coverage_reproduction')
        result.update(frozen_predictor_reproduced=True,ridge_fits=0,capture_sha256=h.sha(paths['result']),audit_wall_s=time.perf_counter()-start)
        used=p['session_ledger']['used_after_s']+result['audit_wall_s']
        result['session_ledger']=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used)
        with validation.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
        return result
    h.verify_file(r.MANIFEST,p['predictor_manifest_sha256']);h.verify_file(r.PREDICTIONS,p['predecision_file_sha256'])
    manifest=json.loads(r.MANIFEST.read_text())
    bank=r.paired_training([x for x in p['episodes'] if x['split']=='training'],c)
    if bank!=manifest['training_pairs']:raise ValueError('training_provenance')
    selector=r.FrozenReturnSelector.restore(c,manifest)
    for f in c['families']:
        n=r.FamilyNormalizer.fit(f,r.load_source_train_obs(f,(0,1)))
        if n.mean.tolist()!=manifest['normalizers'][f]['mean'] or n.std.tolist()!=manifest['normalizers'][f]['std']:raise ValueError('source_normalization')
    for key,s in selector.supports.items():
        if r.digest(dict(obs=s.obs.tolist(),action=s.action.tolist(),next_obs=s.next_obs.tolist()))!=manifest['support_sha256'][key]:raise ValueError('support_hash')
    if [selector.features(x['public']).tolist() for x in bank]!=manifest['feature_rows']:raise ValueError('training_feature_reproduction')
    for record in p['selection_decisions']:
        public={k:record[k] for k in ('family','model_bundle','episode','initial_obs','completed_real_steps')}
        if selector.decide(public)!=record:raise ValueError('predecision_reproduction')
    disk=[json.loads(line) for line in r.PREDICTIONS.read_text().splitlines()]
    if disk!=p['selection_decisions'] or r.analyze_selection(p,c)!=p['selection_analysis']:raise ValueError('selection_reproduction')
    result.update(frozen_predictor_reproduced=True,ridge_fits=0,capture_sha256=h.sha(paths['result']),audit_wall_s=time.perf_counter()-start)
    used=p['session_ledger']['used_after_s']+result['audit_wall_s']
    result['session_ledger']=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used)
    with validation.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    return result


def run(c):
    paths=h.run_paths(c)
    is_coverage=c['version']=='coverage_feedback_v1'
    extra=[p for b in coverage.BUDGETS for p in coverage.paths(b)] if is_coverage else [r.MANIFEST,r.PREDICTIONS]
    if any(p.exists() for p in [paths['result'],paths['usage'],paths['journal'],*extra]):raise FileExistsError('one_run_only')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=h.ROOT,text=True).strip():raise RuntimeError('commit_before_execution')
    names=['scripts/run_e3_2_return_feedback.py','scripts/verify_unified_full_policy_source.py',
        'src/nexus/evolution2/full_policy_source.py','src/nexus/evolution2/return_feedback.py',
        'src/nexus/evolution2/generated_strategies.py','src/nexus/evolution2/planner_adapter.py',
        'src/nexus/world/dynamics.py','src/nexus/world/rewards.py','src/nexus/tasks/spec.py',
        'src/nexus/tasks/wrappers.py','tests/test_e3_2_return_feedback.py']
    names += [str(paths[k].relative_to(h.ROOT)) for k in ('config','allocation','protocol')]
    if is_coverage:names+=['src/nexus/evolution2/feedback_coverage.py','tests/test_e3_4_feedback_coverage.py']
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=h.ROOT,text=True).splitlines())
    if not set(names)<=tracked:raise RuntimeError('uncommitted_implementation')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip()
    torch.set_num_threads(1);selector=coverage.CoverageSelectors(c) if is_coverage else r.FrozenReturnSelector(c)
    start=time.perf_counter();cpu=time.process_time()
    p=h.run(c,on_training=selector.fit,on_decision=selector.decide)
    try:
        if is_coverage:
            p['partial_predictor_budgets']=[b for b,s in selector.selectors.items() if s.ready]
            if len(p['partial_predictor_budgets'])==3:
                for b,s in selector.selectors.items():h.verify_file(coverage.paths(b)[0],s.manifest_sha)
                p.update(predictor_files=selector.files(),predictor_accounting=dict(ridge_fits=6,unique_training_pairs=36,
                    pair_observations_processed_per_mode=72,feature_dimension=192,antisymmetric_rows_per_fit=[24,48,72],
                    cached_support_transitions_unique=128,cached_support_rows_processed=384,
                    cached_source_normalization_observations_unique=4096,source_normalization_rows_processed=12288,
                    training_real_steps=14400,evaluation_real_steps=6400))
            if p['declared_complete']:p['coverage_analysis']=coverage.analyze(p,c)
        elif selector.ready:
            h.verify_file(r.MANIFEST,selector.manifest_sha)
            p.update(predictor_manifest_sha256=selector.manifest_sha,predecision_file_sha256=h.sha(r.PREDICTIONS),
                predictor_accounting=dict(ridge_fits=2,unique_training_pairs=12,feature_dimension=selector.manifest['feature_dimension'],
                    antisymmetric_rows_per_fit=24,cached_support_transitions=128,cached_source_normalization_observations=4096,
                    training_real_steps=4800,evaluation_real_steps=6400))
        if p['declared_complete'] and not is_coverage:p['selection_analysis']=r.analyze_selection(p,c)
        if time.perf_counter()-start>=c['time_cap_s']:raise TimeoutError('pipeline_cap')
    except Exception as exc:p['declared_complete']=False;p['failure']=f'{type(exc).__name__}: {exc}'
    p['resources']['host_wall_s']=p['resources']['wall_s']
    p['resources'].update(wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu)
    used=p['session_ledger']['used_before_s']+p['resources']['wall_s']
    p['session_ledger'].update(used_after_s=used,remaining_after_s=3600-used)
    p.update(execution_sha=revision,code_sha256={n:h.sha(h.ROOT/n) for n in names},
        dependencies=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__,cpu_threads=1))
    with paths['result'].open('x') as out:json.dump(p,out,allow_nan=False);out.write('\n')
    return {k:p.get(k) for k in ('declared_complete','failure','selection_analysis','coverage_analysis','resources','session_ledger')}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--audit',action='store_true');parser.add_argument('--coverage',action='store_true');args=parser.parse_args()
    config=h.ROOT/'configs/e3_4_feedback_coverage.json' if args.coverage else CONFIG
    c=json.loads(config.read_text());print(json.dumps(audit(c) if args.audit else run(c)))
