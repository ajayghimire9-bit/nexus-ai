"""H16 recorded-data diagnosis. No simulator, checkpoint or neural imports."""
import argparse
import json
from pathlib import Path

from nexus.h16_selection_mechanism_diagnosis import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New derived artifact; refuses overwrite')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = analyze(root)
    if args.output:
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps(dict(primary=result['primary'], positive_seeds=result['positive_seeds'],
                          label=result['registered_label'], grid=result['grid']), indent=2))


if __name__ == '__main__':
    main()
