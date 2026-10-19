"""Locked fresh-episode replication. Reuses the existing metered host."""
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

CONFIG=h.ROOT/'configs/unified_full_policy_replication.json'
VALIDATION=h.ROOT/'artifacts/unified_full_policy_replication_validation.json'


def directional_screen(p):
    """Descriptive replication of fixed prior directions; no model-count inflation."""
    h.validate_result(p,p['config'])
    a=h.analyze(p['episodes'],p['config'])
    acro=a['paired_contrasts']['acrobot']['rank_blend']
    pend=a['paired_contrasts']['pendulum']['rank_blend']['successor_anchor']
    return dict(acrobot_gain_replicated_point_screen=all(v['point_screen'] for v in acro.values()),
        pendulum_harm_replicated_point_screen=pend['mean']<=-1. and all(x<0 for x in pend['per_model']),
        independent_models_per_family=2,new_independent_models=0,scientific_control_success=False)


def audit(paths):
    if VALIDATION.exists():raise FileExistsError('preserve_audit')
    start=time.perf_counter()
    spec=importlib.util.spec_from_file_location('full_policy_verifier',h.ROOT/'scripts/verify_unified_full_policy_source.py')
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    p=json.loads(paths['result'].read_text())
    result=verifier.verify(p,journal_path=paths['journal'])
    if directional_screen(p)!=p['directional_screen']:raise ValueError('directional_screen_reproduction')
    result.update(capture_sha256=h.sha(paths['result']),audit_wall_s=time.perf_counter()-start)
    used=p['session_ledger']['used_after_s']+result['audit_wall_s']
    result['session_ledger']=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=used,remaining_after_s=3600-used)
    with VALIDATION.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--audit',action='store_true');args=parser.parse_args()
    c=json.loads(CONFIG.read_text());paths=h.run_paths(c)
    if args.audit:
        print(json.dumps(audit(paths)));raise SystemExit(0)
    if paths['result'].exists():raise FileExistsError('preserve_closed_capture')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=h.ROOT,text=True).strip():
        raise RuntimeError('commit_implementation_protocol_first')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip()
    names=['scripts/run_unified_full_policy_replication.py','scripts/verify_unified_full_policy_source.py',
           'src/nexus/evolution2/full_policy_source.py','src/nexus/evolution2/generated_strategies.py',
           'src/nexus/evolution2/planner_adapter.py','src/nexus/world/dynamics.py','src/nexus/world/rewards.py',
           'src/nexus/tasks/spec.py','src/nexus/tasks/wrappers.py','tests/test_unified_full_policy_replication.py']
    names += [str(paths[k].relative_to(h.ROOT)) for k in ('config','allocation','protocol')]
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=h.ROOT,text=True).splitlines())
    if not set(names)<=tracked:raise RuntimeError('uncommitted_implementation')
    torch.set_num_threads(1)
    p=h.run(c)
    if p['declared_complete']:p['directional_screen']=directional_screen(p)
    p.update(execution_sha=revision,code_sha256={n:h.sha(h.ROOT/n) for n in names},
        dependencies=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,
                          gymnasium=gymnasium.__version__,cpu_threads=1))
    with paths['result'].open('x') as out:json.dump(p,out,allow_nan=False);out.write('\n')
    print(json.dumps({k:p.get(k) for k in ('declared_complete','failure','directional_screen','analysis','resources','session_ledger')}))
