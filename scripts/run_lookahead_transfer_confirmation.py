#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from nexus.world import lookahead_transfer_confirmation as m
from nexus.world.terminal_value_execution import save

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group()
    g.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if args.execute:
        p=m.execute();out={k:p.get(k) for k in ('complete','label','wall_clock_s','counts','failure')}
        if not p.get('complete'):print(json.dumps(out,indent=2,default=float));raise SystemExit(1)
        print(json.dumps(out,indent=2,default=float))
    else:
        report=m.prep()
        save(Path('artifacts/lookahead_transfer_confirmation_prep.json'),report)
        print(json.dumps(report,indent=2,default=float))
