#!/usr/bin/env python3
"""Offline preparation only: audits saved JSON and estimates costs. No MPC run."""
import argparse
import json
from pathlib import Path
from nexus.world.long_continuation import prepare

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',default='artifacts/long_continuation_preparation.json')
    args=parser.parse_args()
    path=Path(args.out)
    if path.exists(): raise SystemExit('refusing to overwrite existing preparation record')
    result=prepare()
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))
