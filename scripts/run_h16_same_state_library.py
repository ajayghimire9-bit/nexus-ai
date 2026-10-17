#!/usr/bin/env python3
"""H16 lock prep. Collection remains unauthorized."""
import argparse
import json
from nexus.world import h16_same_state_library as m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        m.execute()
        return
    print(json.dumps(m.prep(), indent=2, default=float))


if __name__ == '__main__':
    main()
