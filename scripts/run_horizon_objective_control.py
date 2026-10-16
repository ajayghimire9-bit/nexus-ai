#!/usr/bin/env python3
import argparse
import json
from nexus.world import horizon_objective_control as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    cfg=m.load_config();record=m.load_allocation()
    out=dict(config_sha256=m.sha(m.CONFIG),protocol_sha256=m.sha(m.PROTOCOL),
             allocation_sha256=m.sha(m.ALLOCATION),time_cap_s=cfg['time_cap_s'],
             env_cap=cfg['env_cap'],model_cap=cfg['model_cap'],
             authorized=bool(record.get('authorized')),runs=int(record.get('runs',0)),
             primary=m.PRIMARY,new_environment_steps=0,score_horizon=m.SCORE_H)
    if args.execute:
        m.require_allocation(cfg)
        raise RuntimeError('execute path is not opened without a bound one-run allocation')
    print(json.dumps(out,indent=2,default=float))
