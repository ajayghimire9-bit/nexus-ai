"""One precommitted source-record meta-learning test; no environment creation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import torch
from nexus.seed.plasticity_study import run
ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    config=ROOT/'configs/seed_memory_aware.json';c=json.loads(config.read_text())
    if not a.execute:raise SystemExit('Explicit --execute required; run once from committed clean implementation.')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise SystemExit('clean_committed_protocol_required')
    for f in ('configs/seed_memory_aware.json','docs/NEXUS_SEED_MEMORY_AWARE_PROTOCOL.md'):
        if subprocess.run(['git','ls-files','--error-unmatch',f],cwd=ROOT,capture_output=True).returncode:raise SystemExit('protocol_must_be_committed')
    out=ROOT/'artifacts/seed_memory_aware.json'
    if out.exists() or any((ROOT/'artifacts'/f'seed_plasticity_{s}.json').exists() for s in c['controller_seeds']):raise SystemExit('one_run_only_existing_output')
    torch.set_num_threads(1);start=time.monotonic()
    def check():
        if time.monotonic()-start>=min(c['max_wall_s'],c['carried_session_remaining_s']):raise TimeoutError('locked_execution_cap')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    record=dict(declared_complete=False,execution_sha=sha,config=c)
    try:
        record=run(ROOT,c,out,check,sha)
    except Exception as e:
        if out.exists():record=json.loads(out.read_text())
        record.update(declared_complete=False,failure=type(e).__name__+':'+str(e))
    record['command_wall_s']=time.monotonic()-start
    debit=int(record['command_wall_s'])+2 # conservatively allow cold interpreter/import overhead
    record.update(config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        conservative_execution_debit_s=debit,session_used_s=c['carried_session_used_s']+debit,
        session_remaining_s=c['carried_session_remaining_s']-debit)
    out.write_text(json.dumps(record,indent=2,allow_nan=False))
    print(json.dumps({k:record[k] for k in ('declared_complete','execution_sha','command_wall_s','session_used_s','session_remaining_s')}))
    if not record['declared_complete']:raise SystemExit(1)
