"""Source-only H17 exclusion coverage; never registers or executes H17."""
import argparse
import json
from pathlib import Path

from nexus.h17_exclusion_coverage_review import review


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = review(Path(__file__).resolve().parents[1])
    if args.output:
        with args.output.open('x') as file:
            json.dump(result,file,indent=2,allow_nan=False)
            file.write('\n')
    print(json.dumps({key:result[key] for key in ('verdict','reachable_commits','counts',
                     'literal_or_metadata_physics_not_in_registry','symbolic_seed_keys',
                     'numerical_registration_safe','proposed_cap_s','blockers')},indent=2))
