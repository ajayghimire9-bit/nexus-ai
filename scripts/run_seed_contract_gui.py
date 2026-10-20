"""Fixed aligned/tanh/5511 GUI; no training and no automatic model selection."""
import argparse
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8776);p.add_argument('--max-runtime-s',type=int,default=900);a=p.parse_args()
    r=json.loads((ROOT/'artifacts/seed_contract_study.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('complete_contract_study_required')
    m=next(m for m in r['models'] if m['identity']=='compact_tanh_5511_aligned_v1')
    sys.argv=[str(ROOT/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(a.port),'--max-runtime-s',str(a.max_runtime_s),'--seed-grounded-model',str(ROOT/'artifacts/seed_contract_gui.json'),'--seed-grounded-sha256',m['gui_sha256']]
    runpy.run_path(str(ROOT/'scripts/run_learning_lab.py'),run_name='__main__')
