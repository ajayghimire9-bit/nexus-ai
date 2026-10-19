"""Offline audit only: no environment construction, inference or fitting."""
import gzip
import itertools
import json
import subprocess
import time

import numpy as np

from nexus.evolution1.fixtures import Event, verify_journal
from nexus.evolution1.resources import Work
from nexus.evolution2 import full_policy_source as h


def verify(p, journal_path=None):
    c=p['config'];h.validate_result(p,c)
    if not p['declared_complete']:raise ValueError('incomplete_capture')
    for name,expected in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{name}'],cwd=h.ROOT)
        import hashlib
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('execution_code_hash')
    for name,expected in p['historical_artifacts_sha256'].items():h.verify_file(h.ROOT/name,expected)
    journal_path=journal_path or h.JOURNAL
    h.verify_file(journal_path,p['resource_journal_sha256'])
    h.verify_checkpoints(p['models'],c)
    if any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_state_mismatch')
    for r in p['source_arrays']:h.verify_file(h.ROOT/r['path'],r['sha256'])
    expected=set(itertools.product(c['families'],c['model_bundles'],c['episodes'],c['controllers'],range(200)))
    seen=set();work=Work();events=0;by_controller={k:Work() for k in c['controllers']}
    rows={(r['family'],r['model_bundle'],r['episode'],r['controller']):r for r in p['episodes']}
    max_reward_error=0.
    for row in p['episodes']:
        reward_fn=h.pendulum_step_reward if row['family']=='pendulum' else h.acrobot_step_reward
        for step in row['steps']:
            error=abs(float(reward_fn(np.asarray(step['obs']),step['action'],np.asarray(step['next_obs']))[0])-step['reward'])
            max_reward_error=max(max_reward_error,error)
            if error>1e-5:raise ValueError('published_reward_mismatch')
    with gzip.open(journal_path,'rt') as src:
        for line in src:
            record=json.loads(line)
            ident=(record['family'],record['model'],record['episode'],record['controller'],record['tick'])
            if ident not in expected or ident in seen or record['status']!='complete_execution':raise ValueError('journal_grid')
            seen.add(ident)
            chain=tuple(Event(**x) for x in record['events']);verify_journal(chain)
            payloads=[(e.kind,json.loads(e.payload_json)) for e in chain]
            obs=rows[ident[:4]]['steps'][ident[4]]['obs']
            plan=h.operation_plan(h.controllers()[record['controller']],np.asarray(obs),3)
            planned=payloads[0][1]['operations']
            if [x['cost'] for x in planned]!=[op.cost.payload() for op in plan]:raise ValueError('journal_plan')
            reservations=[v for k,v in payloads if k=='reserved']
            settlements=[v for k,v in payloads if k=='settled']
            if [v['operation'] for v in reservations]!=[op.key for op in plan]:raise ValueError('reservation_order')
            if [v['operation'] for v in settlements]!=[op.key for op in plan] or any(v['outcome']!='success' for v in settlements):
                raise ValueError('settlement_integrity')
            for op in plan:
                work=work.plus(op.cost)
                by_controller[record['controller']]=by_controller[record['controller']].plus(op.cost)
            events+=len(chain)
    if seen!=expected or work.payload()!=p['resources']['completed']:raise ValueError('complete_resource_reconciliation')
    if h.analyze(p['episodes'],c)!=p['analysis']:raise ValueError('analysis_reproduction')
    return dict(valid=True,decision_journals=len(seen),hash_chained_events=events,completed=work.payload(),
                by_controller={k:v.payload() for k,v in by_controller.items()},
                historical_json_preserved=len(p['historical_artifacts_sha256']),frozen_models=len(p['models']),
                max_published_reward_error=max_reward_error,new_real_steps=0,neural_inference=0)


if __name__=='__main__':
    target=h.ROOT/'artifacts/unified_full_policy_validation.json'
    if target.exists():raise FileExistsError('preserve_validation')
    t0=time.perf_counter()
    p=json.loads(h.RESULT.read_text())
    result=verify(p)
    result.update(capture_sha256=h.sha(h.RESULT),audit_wall_s=time.perf_counter()-t0)
    result['session_ledger']={'used_before_s':p['session_ledger']['used_after_s'],
        'used_after_s':p['session_ledger']['used_after_s']+result['audit_wall_s'],
        'remaining_after_s':3600-p['session_ledger']['used_after_s']-result['audit_wall_s']}
    with target.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result))
