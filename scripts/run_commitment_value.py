#!/usr/bin/env python3
"""Default preparation is read-only; research collection needs new exact approval."""
import argparse
import json
import torch
from nexus.world.commitment_value import prepare,verify_inputs,execute,load_config,parent_evidence,validate,OUTPUT

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group();g.add_argument('--verify-inputs',action='store_true');g.add_argument('--audit',action='store_true');g.add_argument('--approved-config-sha256');args=p.parse_args();torch.set_num_threads(1)
    if args.verify_inputs:result=verify_inputs()
    elif args.audit:
        capture=json.loads(OUTPUT.read_text())
        if capture.get('complete') is not True:raise RuntimeError('incomplete or invalid execution')
        parent,stage=parent_evidence();result=validate(capture,load_config(),parent,stage)
    elif args.approved_config_sha256:
        result=execute(args.approved_config_sha256)
        if not result['complete']:raise SystemExit(1)
        result={k:result[k] for k in ('complete','label','wall_clock_s','counts')}
    else:result=prepare()
    print(json.dumps(result,indent=2))
