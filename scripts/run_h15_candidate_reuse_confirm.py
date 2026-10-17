#!/usr/bin/env python3
import argparse
import json
from nexus.world import h15_candidate_reuse_confirm_runner as runner

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='H15 candidate-reuse confirmation guarded runner')
    parser.add_argument('--execute', action='store_true',
                        help='refused until a later authorized one-run allocation exists')
    args = parser.parse_args()
    if args.execute:
        runner.execute()
    report = runner.prep()
    print(json.dumps(report, indent=2, default=float))
