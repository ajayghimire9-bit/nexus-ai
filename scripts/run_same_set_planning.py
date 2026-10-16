#!/usr/bin/env python3
import argparse
import json
from nexus.world import same_set_planning as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group()
    g.add_argument('--execute',action='store_true');g.add_argument('--audit',action='store_true')
    g.add_argument('--feasibility',action='store_true');g.add_argument('--retrospective',action='store_true')
    args=parser.parse_args()
    if args.execute:
        p=m.execute();out={k:p.get(k) for k in ('complete','label','wall_clock_s','failure')}
        if not p.get('complete'):print(json.dumps(out,indent=2));raise SystemExit(1)
    elif args.audit:
        out=m.audit()
    elif args.feasibility:
        out=m.feasibility()
    elif args.retrospective:
        out=m.retrospective_audit()
    else:
        cfg=m.load_config();record=m.load_allocation()
        out=dict(config_sha256=m.sha(m.CONFIG),protocol_sha256=m.sha(m.PROTOCOL),allocation_sha256=m.sha(m.ALLOCATION),
                 time_cap_s=cfg['time_cap_s'],env_cap=cfg['env_cap'],model_cap=cfg['model_cap'],
                 authorized=bool(record.get('authorized')),runs=int(record.get('runs',0)),
                 primary='gain_same_fresh',new_environment_steps=0)
    print(json.dumps(out,indent=2,default=float))
