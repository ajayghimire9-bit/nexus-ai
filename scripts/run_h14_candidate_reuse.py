#!/usr/bin/env python3
import argparse
import json
from nexus.world import h14_candidate_reuse as m

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='H14 candidate-reuse protocol lock')
    parser.add_argument('--execute', action='store_true',
                        help='refused until a later authorized one-run allocation exists')
    args = parser.parse_args()
    if args.execute:
        m.execute()
    report = m.prep()
    print(json.dumps(report, indent=2, default=float))
