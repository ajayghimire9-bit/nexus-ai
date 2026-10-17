#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from nexus.world import mcc_native_rms as m
from nexus.world.terminal_value_execution import save

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--execute', action='store_true')
    g.add_argument('--results-audit', action='store_true')
    args = parser.parse_args()
    if args.execute:
        p = m.execute(); out = {k: p.get(k) for k in ('complete', 'label', 'wall_clock_s', 'counts', 'failure')}
        if not p.get('complete'):
            print(json.dumps(out, indent=2, default=float)); raise SystemExit(1)
        print(json.dumps(out, indent=2, default=float))
    elif args.results_audit:
        print(json.dumps(m.audit_results(), indent=2, default=float))
    else:
        report = m.prep()
        save(Path('artifacts/mcc_native_rms_prep.json'), report)
        print(json.dumps(report, indent=2, default=float))
