"""Hash-bound adaptive Seed GUI. No automatic meta-training or model selection."""
import argparse
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8777);p.add_argument('--max-runtime-s',type=int,default=900);p.add_argument('--seed-directory',type=Path,default=ROOT/'runs/seed-adaptive-sessions');p.add_argument('--with-readout',action='store_true');a=p.parse_args()
    r=json.loads((ROOT/'artifacts/seed_memory_aware.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('complete_source_study_required')
    m=next(s for s in r['seeds'] if s['seed']==r['config']['gui_controller_seed'])
    sys.argv=[str(ROOT/'scripts/run_learning_lab.py'),'--allow-seed','--port',str(a.port),'--max-runtime-s',str(a.max_runtime_s),
        '--seed-directory',str(a.seed_directory),'--seed-grounded-model',str(ROOT/r['config']['parent_model']),
        '--seed-grounded-sha256',r['config']['parent_sha256'],'--seed-plasticity-controller',str(ROOT/m['checkpoint']),
        '--seed-plasticity-sha256',m['sha256']]
    if a.with_readout:
        import hashlib
        study=ROOT/'artifacts/seed_surprise_readout.json';q=json.loads(study.read_text())
        from nexus.seed.readout_validation import validate,require_manifest,summarize
        cfg=ROOT/'configs/seed_surprise_readout.json';locked=json.loads(cfg.read_text())
        validate(q,locked);require_manifest(q,ROOT)
        if hashlib.sha256(cfg.read_bytes()).hexdigest()!=q['config_sha256'] or not q['declared_complete'] or not summarize(q)['screen_passed']:raise ValueError('successful_readout_screen_required')
        # First registered seed,not the best audit performer.
        head=q['models'][0]
        sys.argv+=['--seed-action-readout',str(ROOT/head['checkpoint']),'--seed-action-readout-sha256',head['sha256'],'--seed-surprise-study',str(study),'--seed-surprise-sha256',hashlib.sha256(study.read_bytes()).hexdigest()]
    runpy.run_path(str(ROOT/'scripts/run_learning_lab.py'),run_name='__main__')
