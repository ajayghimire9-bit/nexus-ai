"""Engineering receipt provenance; no science runner, collection or fitting."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def test_phase_receipt_source_tree_and_scope():
    record=json.loads((ROOT/'artifacts/seed_phase1_7_engineering.json').read_text())
    for path,sha in record['source_hashes'].items():
        body=subprocess.check_output(['git','show',record['implementation_revision']+':'+path],cwd=ROOT)
        assert hashlib.sha256(body).hexdigest()==sha,path
    assert record['scientific']['additional_experiments']==0
    assert record['scientific']['associated_scientific_screen']=='failed'
    assert record['fixtures']['phase_count']==7 and record['fixtures']['inspection_unchanged']
    assert record['fixtures']['rollback_disables_phrase']
    assert record['fixtures']['phrase_result']['value']==2


def test_storage_benefit_does_not_claim_execution_speedup():
    record=json.loads((ROOT/'artifacts/seed_phase1_7_engineering.json').read_text())
    reviewed=record['fixtures']['review']
    assert reviewed['accepted'] and reviewed['stored_node_savings']==2
    assert reviewed['macro_instructions']==20 and reviewed['original_instructions']==16
    for path,sha in record['screenshots'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
