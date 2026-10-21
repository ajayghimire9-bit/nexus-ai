"""Saved arithmetic/provenance verification; no collection or fitting."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from nexus.seed import query_context as q

ROOT=Path(__file__).resolve().parents[1]


def test_saved_raw_cells_and_host_resource_accounting():
    r=json.loads((ROOT/'artifacts/seed_query_context.json').read_text())
    q.validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=0))
    assert r['execution_sha']=='071fe025d4f0d1a1de68ddc35b5fbf07cfa88d37'
    assert r['execution_debit_s']==3
    assert r['session_used_s']==1999.6321034559958


def test_independent_audit_receipt_and_gui():
    spec=importlib.util.spec_from_file_location('query_context_verifier',ROOT/'scripts/verify_seed_query_context.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    receipt=module.verify(ROOT)
    assert receipt==json.loads((ROOT/'artifacts/seed_query_context_audit.json').read_text())
    view=q.saved_replay(ROOT)
    assert view['query_context']['verdict']=='query_information_missing'
    assert view['resources']['real_steps']==0


def test_saved_grid_cannot_shrink():
    r=json.loads((ROOT/'artifacts/seed_query_context.json').read_text())
    for modified in ([x for x in r['rows'] if x['block']!=r['rows'][0]['block']],
                     [x for x in r['rows'] if x['task']!=r['rows'][0]['task']],
                     [x for x in r['rows'] if x['prefix']!=0]):
        with pytest.raises(ValueError,match='complete_context_grid'):q.validate_cells(modified,r['config'],[])
