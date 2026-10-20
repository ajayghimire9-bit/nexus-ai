"""Repository-only receipt audit: no world construction, fitting or inference."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_foundation_receipt_sources_and_claim_boundaries():
    record=json.loads((ROOT/'artifacts/seed_foundation_engineering.json').read_text())
    assert record['label']=='authored_engineering_verification_not_scientific_evidence'
    for path,sha in record['source_hashes'].items():
        recorded=subprocess.check_output(['git','show',record['implementation_revision']+':'+path],cwd=ROOT)
        assert hashlib.sha256(recorded).hexdigest()==sha,path
    assert record['resources']['scientific_runs']==0
    assert record['resources']['scientific_debit_seconds']==0
    assert abs(record['resources']['carried_used_seconds']+record['resources']['carried_remaining_seconds']-3600)<1e-9
    for row in record['fixtures']['review']['search_checks']:
        assert row['without_library']['status']==row['with_library']['status']=='solved'
        assert row['with_library']['instructions']<row['without_library']['instructions']
    assert all(r['correct'] for r in record['fixtures']['review']['outcomes'])
    assert record['preservation']['changed']==[]
