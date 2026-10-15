#!/usr/bin/env python3
"""Default is a no-data preparation view. Execution requires a human-approved hash."""
import argparse
import json
import torch
from nexus.world.terminal_value import prepare
from nexus.world.terminal_value_execution import execute

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--approved-config-sha256')
    args=parser.parse_args();torch.set_num_threads(1)
    if args.approved_config_sha256 is None:
        print(json.dumps(prepare(),indent=2))
    elif not execute(args.approved_config_sha256)['complete']:
        raise SystemExit(1)
