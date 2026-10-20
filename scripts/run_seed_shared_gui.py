"""Same bounded Lab server with an owner-hash-verified shared encoder only."""
import argparse
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8782);p.add_argument('--max-runtime-s',type=int,default=900)
    p.add_argument('--symbolic',action='store_true');p.add_argument('--core',type=Path);p.add_argument('--core-sha256');p.add_argument('--seed-directory',type=Path,default=ROOT/'runs/seed-shared-sessions');a=p.parse_args()
    if bool(a.core)!=bool(a.core_sha256) or a.symbolic and a.core:p.error('Supply both core path/hash, or symbolic mode.')
    args=[str(ROOT/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(a.port),'--max-runtime-s',str(a.max_runtime_s),'--seed-directory',str(a.seed_directory)]
    if not a.symbolic:
        if a.core:core=a.core;sha=a.core_sha256
        else:
            r=json.loads((ROOT/'artifacts/seed_memory_aware.json').read_text());core=ROOT/r['config']['parent_model'];sha=r['config']['parent_sha256']
        if not core.is_file():p.error('Recorded frozen core is missing. Restore its exact recorded binary, or use --symbolic; no replacement is trained.')
        args+=['--seed-shared-model',str(core),'--seed-shared-sha256',sha]
    sys.path.insert(0,str(ROOT/'src'));sys.argv=args
    print(f'Shared labs: http://127.0.0.1:{a.port}/labs',flush=True)
    runpy.run_path(str(ROOT/'scripts/run_learning_lab.py'),run_name='__main__')

if __name__=='__main__':main()
