"""Audit fetched-ref configuration metadata only. Never chooses a new holdout."""
import argparse
import json
from pathlib import Path

from nexus.h17_exclusion_registry_audit import inventory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='New inventory JSON; refuses overwrite')
    args = parser.parse_args()
    result = inventory(Path(__file__).resolve().parents[1])
    if args.output:
        with args.output.open('x') as stream:
            json.dump(result,stream,indent=2,allow_nan=False)
            stream.write('\n')
    print(json.dumps({k:len(result[k]) if k in ('ref_snapshot','excluded_physics','ambiguous_only_exclusions','inputs') else result[k]
                      for k in ('status','ref_snapshot','unique_commits','inputs','input_config_blob_count',
                                'excluded_physics','ambiguous_only_exclusions','parsing_issues',
                                'globally_complete_closed_registry')},indent=2))
