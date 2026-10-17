#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from nexus.world import mcc_planning_ranking as m
from nexus.world.terminal_value_execution import save

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        m.execute()
    else:
        report = m.prep()
        save(Path('artifacts/mcc_planning_ranking_prep.json'), report)
        print(json.dumps(report, indent=2, default=float))
