#!/usr/bin/env python3
"""Default: read-only preparation. Execution is frozen inference, not simulation."""
import argparse
import json
import torch
from nexus.world.value_candidate_discrimination import prepare,execute,inputs,validate_result,OUTPUT

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group();g.add_argument('--execute',action='store_true');g.add_argument('--audit',action='store_true');args=p.parse_args();torch.set_num_threads(1)
    if args.execute:
        r=execute()
        if not r['complete']:raise SystemExit(1)
        print(json.dumps({'complete':True,'label':r['label'],'wall_clock_s':r['wall_clock_s'],'model_states':r['model_states']},indent=2))
    elif args.audit:
        cfg,parent,stage,capture=inputs();r=json.loads(OUTPUT.read_text())
        if r.get('complete') is not True:raise RuntimeError('incomplete analysis')
        result=validate_result(r,cfg,parent,stage,capture);print(json.dumps(result,indent=2))
    else:print(json.dumps(prepare(),indent=2))
