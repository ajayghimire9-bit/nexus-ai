#!/usr/bin/env python3
"""Recover completeness after a hash-format validation bug; no resimulation."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
from nexus.world.planning_value import load_config,validate_and_summarize

if __name__=='__main__':
    started=time.perf_counter()
    source=Path('artifacts/planning_value.json');out=Path('artifacts/planning_value_validation.json')
    if out.exists(): raise RuntimeError('refusing validation overwrite')
    raw=json.loads(source.read_text());cfg=load_config()
    if raw['complete'] or raw.get('failure')!={'type':'ValueError','message':'invalid support hash'}:
        raise RuntimeError('not the recorded hash-format failure')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    # The untracked raw capture is expected; processing source/config must be committed.
    if subprocess.check_output(['git','diff','HEAD','--','src','scripts','configs'],text=True).strip():
        raise RuntimeError('commit processing code first')
    for name,key in [('configs/planning_value.yaml','config_sha256'),('docs/NEXUS_PLANNING_VALUE.md','protocol_sha256')]:
        locked=subprocess.check_output(['git','show',raw['implementation_sha']+':'+name])
        if hashlib.sha256(locked).hexdigest()!=raw[key]:raise RuntimeError('execution provenance mismatch')
    result=validate_and_summarize(raw,cfg)
    result.update(processing_wall_clock_s=time.perf_counter()-started,complete=True,status='complete_data_recovered_by_offline_validation',
        raw_capture_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),processing_sha=revision,
        execution_sha=raw['implementation_sha'],new_environment_steps=0,support_hash_format='SHA256 first 16 hexadecimal characters',
        original_failure=raw['failure'],raw_capture_modified=False)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['comparisons']['primary'],indent=2))
