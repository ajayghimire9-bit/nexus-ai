#!/usr/bin/env python3
"""Execute exactly one approved long-continuation protocol, never auto-repeat."""
import argparse
import torch
from nexus.world.long_continuation_execution import execute

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-config-sha256',required=True)
    args=parser.parse_args()
    torch.set_num_threads(1)
    result=execute(args.approved_config_sha256)
    if not result['diagnostic_complete']: raise SystemExit(1)
