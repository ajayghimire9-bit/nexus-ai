"""Source-only reservation closure, with exclusive-create output."""
import argparse
import json
from pathlib import Path
from nexus.h17_reservation_closure import review

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = review(Path(__file__).resolve().parents[1])
    with args.output.open('x') as file:
        json.dump(result,file,indent=2,allow_nan=False)
        file.write('\n')
    print(json.dumps(dict(verdict=result['verdict'],certificates=len(result['historical_seed_certificates']),
                         unsupported=len(result['unsupported_seed_functions']),
                         artifact_versions=len(result['artifact_metadata']),
                         novel_physics=result['novel_metadata_physics']),indent=2))
