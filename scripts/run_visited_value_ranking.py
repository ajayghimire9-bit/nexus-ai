#!/usr/bin/env python3
import argparse
import json
from nexus.world import visited_value_ranking as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--execute',action='store_true');group.add_argument('--audit',action='store_true');args=parser.parse_args()
    if args.execute:
        p=m.execute();print(json.dumps({k:p.get(k) for k in ('complete','label','wall_clock_s','failure')},indent=2))
        if not p['complete']:raise SystemExit(1)
    elif args.audit:
        cfg=m.load_config();source,stage=m.inputs(cfg);p=json.loads(m.OUTPUT.read_text())
        if p.get('complete') is not True:raise RuntimeError('incomplete analysis')
        result=m.validate(p,cfg,source,stage)
        if any(result[k]!=p[k] for k in result):raise ValueError('saved summary differs')
        print(json.dumps(dict(audit_passed=True,label=result['label']),indent=2))
    else:
        cfg=m.load_config();print(json.dumps(dict(config_sha256=m.sha(m.CONFIG),time_cap_s=cfg['time_cap_s'],new_environment_steps=0,new_imagined_transitions=0),indent=2))
