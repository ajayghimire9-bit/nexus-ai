"""Stdlib-only recorded predictor/feature audit; never fits or imports Torch."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.prefix_consistency import validate,source_pack


def main():
    path=ROOT/'artifacts/seed_prefix_consistency.json';r=json.loads(path.read_text())
    c=json.loads((ROOT/'configs/seed_prefix_consistency.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_prefix_audit')
    validate(r,c,source_pack(ROOT,c))
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        signal_screen_pass=r['analysis']['signal_screen_pass'],scientific_execution=False),indent=2))


if __name__=='__main__':main()
