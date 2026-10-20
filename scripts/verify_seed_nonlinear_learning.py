"""Saved-result arithmetic only; stdlib, no inference or scientific reruns."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.nonlinear_learning_audit import validate
from nexus.evolution1.catalogue import digest


def checkpoint_bytes(r,arm):
    provenance=dict(config_sha256=digest(r['config']),source_only=True,source_hash=digest(r['tasks']['train']))
    wire=dict(schema='seed_plasticity_v1',width=33,provenance=provenance,
              weights={k:arm['weights'][k] for k in ('logits.weight','logits.bias')})
    raw=json.dumps(wire,allow_nan=False).encode()
    if hashlib.sha256(raw).hexdigest()!=arm['sha256']:raise ValueError('nonreproducible_checkpoint_bytes')
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-checkpoints',action='store_true')
    p.add_argument('--restore-checkpoints',type=Path,help='write NEW rule JSON files, from saved weights only; no model training');a=p.parse_args()
    raw=ROOT/'artifacts/seed_nonlinear_learning.json';r=json.loads(raw.read_text());c=json.loads((ROOT/'configs/seed_nonlinear_learning.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_execution_not_scientific_negative')
    validate(r,c)
    for row in r['controllers']:
        for arm in row['arms'].values():
            raw_checkpoint=checkpoint_bytes(r,arm)
            if a.restore_checkpoints:
                directory=a.restore_checkpoints.resolve()
                if directory.is_relative_to(ROOT/'artifacts'):raise ValueError('private_new_checkpoint_directory_required')
                directory.mkdir(parents=True,exist_ok=True)
                with (directory/arm['checkpoint']).open('xb') as f:f.write(raw_checkpoint)
    if a.check_checkpoints:
        base=Path(r['host_result_path']).parent
        for row in r['controllers']:
            for arm in row['arms'].values():
                file=base/arm['checkpoint']
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=arm['sha256']:raise ValueError('missing_or_wrong_local_checkpoint: '+str(file))
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        checkpoints_checked=a.check_checkpoints,rule_checkpoints_reconstructible=True,
        analysis=r['analysis'],resources=dict(real=sum(r['costs'].values()),imagined=r['imagined_transitions'],wall_s=r['wall_s'])),indent=2))


if __name__=='__main__':main()
