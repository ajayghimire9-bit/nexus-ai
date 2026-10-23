"""Re-execute only saved, authored final patches in the existing bounded worker.

No search, candidate training, model call or new task. Does not rewrite results.
"""
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.agent_loop_worker import run_worker_subprocess


def replay(config, records):
    started=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    rows=[]
    for spec in config['coding']:
        event=next(r for r in records if r.get('operation')=='assessment_worker' and r['scope']=='coding:'+spec['id'])
        actual=run_worker_subprocess(event['argument'])
        def values(result):
            return [(row.get('actual'),row.get('passed'),row.get('error')) for row in result.get('results',[])]
        if actual.get('status')!=event['output'].get('status') or values(actual)!=values(event['output']):
            raise ValueError('saved_patch_replay_mismatch:'+spec['id'])
        rows.append(dict(id=spec['id'],files_sha256=hashlib.sha256(json.dumps(event['argument']['files'],sort_keys=True).encode()).hexdigest(),
                         status=actual.get('status'),all_passed=actual.get('all_passed'),results=actual.get('results',[])))
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(valid=True,projects=len(rows),case_calls=sum(len(r['results']) for r in rows),results=rows,
                wall_s=time.perf_counter()-started,child_cpu_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                accounting='assessment-only consistency replay; not another scientific comparison',
                model_calls=0,new_environment_steps=0)


if __name__=='__main__':
    config=json.loads((ROOT/'configs/seed_capability_audit.json').read_text())
    raw=ROOT/'artifacts/seed_capability_audit_raw.jsonl'
    records=[json.loads(s) for s in raw.read_text().splitlines()]
    result=replay(config,records)
    result['raw_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
    with (ROOT/'artifacts/seed_capability_tool_replay.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))
