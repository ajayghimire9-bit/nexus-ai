"""Stdlib result/checkpoint audit. Never imports Torch or runs adaptation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.cumulative_learning import validate,source_pack,checkpoint_bytes


def main(*,study_name='seed_cumulative_learning',identifier='seed-cumulative-learning-1',width=33,validator=validate,packer=source_pack):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-checkpoints',action='store_true')
    p.add_argument('--restore-checkpoints',type=Path)
    a=p.parse_args();path=ROOT/'artifacts'/f'{study_name}.json';r=json.loads(path.read_text())
    c=json.loads((ROOT/'configs'/f'{study_name}.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_cumulative_execution')
    validator(r,c,packer(ROOT,c));count=0
    base=ROOT/'runs/experimental/attempts'/identifier
    for fold in r['folds'].values():
        for arms in fold['models'].values():
            for info in arms.values():
                raw=checkpoint_bytes(info,width=width);count+=1
                if a.check_checkpoints:
                    file=base/info['checkpoint']
                    if not file.is_file() or file.read_bytes()!=raw:raise ValueError('missing_or_wrong_checkpoint: '+str(file))
                if a.restore_checkpoints:
                    directory=a.restore_checkpoints.resolve()
                    if directory.is_relative_to(ROOT/'artifacts') or directory==base.resolve():raise ValueError('new_private_restore_directory_required')
                    directory.mkdir(parents=True,exist_ok=True)
                    with (directory/info['checkpoint']).open('xb') as f:f.write(raw)
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_screen_pass=r['analysis']['source_screen_pass'],checkpoints_reconstructible=count,
        local_checkpoints_checked=a.check_checkpoints,scientific_execution=False),indent=2))


if __name__=='__main__':main()
