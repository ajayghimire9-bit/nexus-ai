"""Launch the registered tanh/4411 readout alongside the unchanged MPC button."""
import argparse
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8775);p.add_argument('--max-runtime-s',type=int,default=900);args=p.parse_args()
    result=json.loads((ROOT/'artifacts/seed_action_readout.json').read_text())
    if result['declared_complete'] is not True:raise ValueError('complete_readout_study_required')
    config=result['config']
    if (config['gui_recipe'],config['gui_seed'])!=('compact_tanh',4411):raise ValueError('fixed_gui_registration')
    parent=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text())
    m=next(m for m in parent['models'] if m['recipe']=='compact_tanh')
    row=next(m for m in result['models'] if m['recipe']=='compact_tanh');head=next(h for h in row['heads'] if h['seed']==4411)
    for path in (m['checkpoint'],head['checkpoint']):
        if (ROOT/path).resolve().parent!=(ROOT/'artifacts').resolve():raise ValueError('checkpoint_path')
    sys.argv=[str(ROOT/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(args.port),'--max-runtime-s',str(args.max_runtime_s),'--seed-grounded-model',str(ROOT/m['checkpoint']),'--seed-grounded-sha256',m['sha256'],'--seed-action-readout',str(ROOT/head['checkpoint']),'--seed-action-readout-sha256',head['sha256']]
    runpy.run_path(str(ROOT/'scripts/run_learning_lab.py'),run_name='__main__')


if __name__=='__main__':main()
