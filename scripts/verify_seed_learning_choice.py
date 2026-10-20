"""Stdlib-only saved-state verification; no fitting, worlds or inference."""
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.learning_choice import validate,source_pack

def main():
    p=ROOT/'artifacts/seed_learning_choice.json';r=json.loads(p.read_text());c=json.loads((ROOT/'configs/seed_learning_choice.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_choice_execution')
    validate(r,c,source_pack(ROOT,c))
    print(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),analysis=r['analysis'],scientific_execution=False),indent=2))

if __name__=='__main__':main()
