#!/usr/bin/env python3
"""Offline teacher-forced rollout audit. Never steps a simulator."""
import json
from nexus.world.multistep_rollout_control_audit import run

if __name__=='__main__':
    report=run()
    out={k:report.get(k) for k in (
        'complete','new_environment_steps','new_imagined_transitions','authorized','training',
        'wall_clock_s','recommendation')}
    print(json.dumps(out,indent=2,default=float))
    if report.get('new_environment_steps')!=0 or report.get('complete') is not True:
        raise SystemExit(1)
