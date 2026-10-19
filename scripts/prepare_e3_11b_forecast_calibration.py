"""Source-only E3.11B checks. Deliberately no scientific execution path."""
import argparse
import hashlib
import json
from pathlib import Path
from nexus.evolution2.forecast_calibration import validate_config, training_means, require_execution_authority

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='fails closed; not an execution grant')
    args = parser.parse_args()
    c = json.loads((ROOT/'configs/e3_11b_forecast_calibration.json').read_text())
    if args.execute:
        require_execution_authority(c)
    validate_config(c)
    inventory = ROOT/c['checkpoint_inventory']
    if hashlib.sha256(inventory.read_bytes()).hexdigest() != c['checkpoint_inventory_sha256']:
        raise ValueError('checkpoint_inventory_hash')
    means = training_means(ROOT/c['training_prior'], c['training_prior_sha256'], c)
    print(json.dumps(dict(status='PREPARED_NOT_AUTHORIZED_NOT_RUNTIME_BOUND',
        training_means=means, real_steps=0, imagined_transitions=0,
        model_inference=0, numerical_seeds_registered=False), sort_keys=True))


if __name__ == '__main__':
    main()
