#!/usr/bin/env python3
import argparse
import json
from nexus.world import h15_candidate_reuse_confirm as m

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='H15 candidate-reuse confirmation lock')
    parser.add_argument('--execute', action='store_true',
                        help='refused until a later authorized one-run allocation exists')
    args = parser.parse_args()
    if args.execute:
        m.execute()
    report = m.prep()
    print(json.dumps(report, indent=2, default=float))
