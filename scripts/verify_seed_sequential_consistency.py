"""Stdlib-only frozen-state and saved-trajectory verification; never refits."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.sequential_consistency import validate,source_pack


def main():
    path=ROOT/'artifacts/seed_sequential_consistency.json';r=json.loads(path.read_text())
    c=json.loads((ROOT/'configs/seed_sequential_consistency.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_sequential_execution')
    validate(r,c,source_pack(ROOT,c))
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_screen_pass=r['analysis']['source_screen_pass'],frozen_state_preserved=True,scientific_execution=False),indent=2))


if __name__=='__main__':main()
