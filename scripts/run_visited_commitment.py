#!/usr/bin/env python3
"""Default verifies protocol, hashes and budgets without collecting data."""
import argparse
import json
import torch
from nexus.world import visited_commitment as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--execute',action='store_true');group.add_argument('--audit',action='store_true');args=parser.parse_args();torch.set_num_threads(1)
    if args.execute:
        result=m.execute();print(json.dumps({k:result.get(k) for k in ('complete','label','wall_clock_s','counts','failure')},indent=2))
        if not result['complete']:raise SystemExit(1)
    elif args.audit:
        p=json.loads(m.OUTPUT.read_text());parent,stage=m.prior.parent_evidence()
        if p.get('complete') is not True:raise RuntimeError('incomplete/invalid run')
        result=m.validate(p,m.load_config(),parent,stage)
        if any(result[k]!=p[k] for k in result):raise ValueError('saved summary mismatch')
        print(json.dumps(dict(audit_passed=True,label=result['label'],primary=result['comparisons']['interaction']['interval']),indent=2))
    else:print(json.dumps(dict(config_sha256=m.prior.sha(m.CONFIG),counts=m.budget(m.load_config()),new_environment_steps=0),indent=2))
