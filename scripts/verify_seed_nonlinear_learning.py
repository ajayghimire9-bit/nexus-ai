"""Saved-result arithmetic only; stdlib, no inference or scientific reruns."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.nonlinear_learning_audit import validate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-checkpoints',action='store_true');a=p.parse_args()
    raw=ROOT/'artifacts/seed_nonlinear_learning.json';r=json.loads(raw.read_text());c=json.loads((ROOT/'configs/seed_nonlinear_learning.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_execution_not_scientific_negative')
    validate(r,c)
    if a.check_checkpoints:
        base=Path(r['host_result_path']).parent
        for row in r['controllers']:
            for arm in row['arms'].values():
                file=base/arm['checkpoint']
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=arm['sha256']:raise ValueError('missing_or_wrong_local_checkpoint: '+str(file))
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        checkpoints_checked=a.check_checkpoints,analysis=r['analysis'],resources=dict(real=sum(r['costs'].values()),imagined=r['imagined_transitions'],wall_s=r['wall_s'])),indent=2))


if __name__=='__main__':main()
