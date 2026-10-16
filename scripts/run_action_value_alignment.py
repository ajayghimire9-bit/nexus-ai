#!/usr/bin/env python3
import argparse
import json
from nexus.world import action_value_alignment as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group();g.add_argument('--execute',action='store_true');g.add_argument('--audit',action='store_true');args=parser.parse_args()
    if args.execute:
        p=m.execute();out={k:p.get(k) for k in ('complete','label','wall_clock_s','failure')}
        if not p['complete']:print(json.dumps(out,indent=2));raise SystemExit(1)
    elif args.audit:
        cfg=m.load_config();capture,stage=m.inputs();p=json.loads(m.OUTPUT.read_text())
        if p.get('complete') is not True:raise RuntimeError('incomplete analysis')
        result=m.validate(p,cfg,capture,stage)
        if any(result[k]!=p[k] for k in result):raise ValueError('saved summary differs')
        out=dict(audit_passed=True,label=result['label'])
    else:
        cfg=m.load_config();out=dict(config_sha256=m.source.sha(m.CONFIG),time_cap_s=cfg['time_cap_s'],new_environment_steps=0,new_imagined_transitions=0)
    print(json.dumps(out,indent=2))
