"""No model execution. --checkpoints explicitly requires every local model file."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.contract_audit import validate,verify_files


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoints',action='store_true');a=p.parse_args()
    r=json.loads((ROOT/'artifacts/seed_contract_study.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_study')
    cfg=ROOT/'configs/seed_contract_study.json'
    if json.loads(cfg.read_text())!=r['config'] or hashlib.sha256(cfg.read_bytes()).hexdigest()!=r['config_sha256']:raise ValueError('locked_config_hash')
    result=validate(r);verify_files(r,ROOT,local_checkpoints=a.checkpoints)
    print(json.dumps(dict(result,local_checkpoints_verified=a.checkpoints),sort_keys=True))
