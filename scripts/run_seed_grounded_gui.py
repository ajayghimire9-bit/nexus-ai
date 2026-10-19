"""Launch the fixed verified model without manually copying its hash."""
import argparse
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8774);p.add_argument('--max-runtime-s',type=int,default=900);a=p.parse_args()
    r=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('complete_model_receipt_required')
    name=r['config']['deployment_recipe']
    if name!='compact_tanh':raise ValueError('locked_deployment_recipe')
    rows=[m for m in r['models'] if m['recipe']==name]
    if len(rows)!=1:raise ValueError('unique_deployment_checkpoint')
    m=rows[0];path=(ROOT/m['checkpoint']).resolve()
    if path.parent!=(ROOT/'artifacts').resolve():raise ValueError('checkpoint_path')
    sys.argv=[str(ROOT/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(a.port),'--max-runtime-s',str(a.max_runtime_s),'--seed-grounded-model',str(path),'--seed-grounded-sha256',m['sha256']]
    runpy.run_path(str(ROOT/'scripts/run_learning_lab.py'),run_name='__main__')


if __name__=='__main__':main()
