#!/usr/bin/env python3
import argparse
import json
import torch
from nexus.world import source_scalar_calibration as m

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group();g.add_argument('--fit-source',action='store_true');g.add_argument('--execute',action='store_true');g.add_argument('--audit',action='store_true');args=parser.parse_args();torch.set_num_threads(1)
    if args.fit_source:
        p=m.fit_source();out={k:p.get(k) for k in ('complete','beta','beta_raw','source_examples','wall_clock_s','failure')}
        if not p['complete']:print(json.dumps(out,indent=2));raise SystemExit(1)
    elif args.execute:
        p=m.execute();out={k:p.get(k) for k in ('complete','label','beta','wall_clock_s','counts','failure')}
        if not p['complete']:print(json.dumps(out,indent=2));raise SystemExit(1)
    elif args.audit:
        p=m.audit();out={k:p[k] for k in ('audit_passed','label','beta','raw_sha256')}
    else:
        cfg=m.load_config();out=dict(config_sha256=m.sha(m.CONFIG),time_cap_s=cfg['time_cap_s'],counts=m.visited.budget(cfg),new_environment_steps=0)
    print(json.dumps(out,indent=2))
