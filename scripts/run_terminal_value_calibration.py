#!/usr/bin/env python3
"""Preparation is read-only; collection additionally requires a new approval record."""
import argparse
import json
import torch
from nexus.world.terminal_value_calibration import prepare,verify_inputs,execute,load_config,parent_evidence,validate,OUTPUT

if __name__=='__main__':
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group()
    group.add_argument('--verify-inputs',action='store_true')
    group.add_argument('--audit',action='store_true')
    group.add_argument('--approved-config-sha256')
    args=p.parse_args();torch.set_num_threads(1)
    if args.verify_inputs:result=verify_inputs()
    elif args.audit:
        parent,stage=parent_evidence();capture=json.loads(OUTPUT.read_text())
        if capture.get('complete') is not True:raise RuntimeError('incomplete execution cannot pass a completed-result audit')
        result=validate(capture,load_config(),parent,stage)
    elif args.approved_config_sha256:
        result=execute(args.approved_config_sha256)
        if not result['complete']:raise SystemExit(1)
    else:result=prepare()
    print(json.dumps(result,indent=2))
