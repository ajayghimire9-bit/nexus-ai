"""Read-only historical arithmetic analysis; output is exclusive-create."""
import argparse
import json
from pathlib import Path
from nexus.h17_seed_dependency_closure import review

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=review(Path(__file__).resolve().parents[1])
    with args.output.open('x') as file:
        json.dump(result,file,indent=2,allow_nan=False);file.write('\n')
    print(json.dumps(dict(verdict=result['verdict'],certificates=len(result['certificates']),
                         unresolved=len(result['unresolved']),wall_clock_s=result['wall_clock_s']),indent=2))
