#!/usr/bin/env python3
"""Print the Evolution-2 synthetic illustration. Not a scientific experiment."""
import argparse
import json
from nexus.evolution2.screen import future_protocol, run_screen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--protocol', action='store_true')
    args = parser.parse_args()
    if args.protocol:
        print(json.dumps(future_protocol(), indent=2, default=float))
        return
    if args.demo:
        payload = run_screen(seed=7, local_updates=False)
        print(json.dumps(payload, indent=2, default=float))
        return
    parser.error('use --demo or --protocol; this script does not run a scientific experiment')


if __name__ == '__main__':
    main()
