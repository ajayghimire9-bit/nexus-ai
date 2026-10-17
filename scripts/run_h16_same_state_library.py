#!/usr/bin/env python3
"""H16 guarded-runner prep. Collection remains unauthorized."""
import argparse
import json
from nexus.world import h16_same_state_library_runner as runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        runner.execute()
        return
    print(json.dumps(runner.prep(), indent=2, default=float))


if __name__ == '__main__':
    main()
