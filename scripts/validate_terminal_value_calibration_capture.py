#!/usr/bin/env python3
"""Recover the unchanged full capture offline after a numeric summation-type bug."""
import argparse
import json
from pathlib import Path
import subprocess
from nexus.world.terminal_value_calibration import OUTPUT,load_config,parent_evidence,validate
from nexus.world.planning_value import sha


def validate_saved():
    p=json.loads(OUTPUT.read_text());parent,stage=parent_evidence()
    result=validate(p,load_config(),parent,stage)
    return dict(complete=True,kind='offline_validation_no_resimulation',source_sha256=sha(OUTPUT),
        source_implementation_sha=p['implementation_sha'],validation_implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),raw_capture_complete=p['complete'],
        original_failure=p.get('failure'),fix='sum builtin float reward list exactly as collection; do not sum NumPy scalar objects',
        new_environment_steps=0,**result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args();result=validate_saved()
    if args.write:
        dest=Path('artifacts/terminal_value_calibration_validation.json')
        if dest.exists():raise RuntimeError('refusing overwrite')
        if result['source_dirty']:raise RuntimeError('commit validator before saving recovery record')
        dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='summaries'},indent=2))
