"""Read-only pilot accounting and checkpoint audit. Never runs a model/world."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.grounded_audit import validate

if __name__=='__main__':
    result=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text())
    if result['declared_complete'] is not True:raise ValueError('incomplete_pilot')
    if result['config_sha256']!=hashlib.sha256((ROOT/'configs/seed_grounded_pilot.json').read_bytes()).hexdigest():raise ValueError('configuration_hash')
    for key,name in [('source_data_sha256','source_episodes'),('query_data_sha256','prediction_episodes')]:
        if result[key]!=hashlib.sha256(json.dumps(result[name],sort_keys=True).encode()).hexdigest():raise ValueError('dataset_hash')
    print(json.dumps(validate(result,ROOT),sort_keys=True))
