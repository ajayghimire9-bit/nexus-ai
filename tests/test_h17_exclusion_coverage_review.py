"""Source-only coverage failures; no scientific stack or H17 registration."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

from nexus import h17_exclusion_coverage_review as m
from nexus.h17_protocol_readiness import seed_keys, validate_draft

ROOT = Path(__file__).resolve().parents[1]


def test_validated_exclusions_and_budget_unchanged():
    raw = (ROOT/m.REGISTRY).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == m.REGISTRY_SHA
    old = json.loads(raw)
    assert len(old['excluded_physics']) == 29
    assert len(old['ambiguous_only_exclusions']) == 6
    counts = validate_draft(m.load_json(ROOT/'configs/h17_occupancy_draft.json'))
    assert (counts['total_real'],counts['total_imagined']) == (62360,174080)
    assert len(seed_keys()) == 480
    assert m.load_json(ROOT/'configs/h17_occupancy_draft.json')['proposed_time_cap_s'] == 300


def test_implicit_source_constants_and_dynamic_seed_functions_detected_without_execution():
    text = '''
raise RuntimeError('not executed')
CLOSED_TARGET = (0.0034,0.001,0.055)
OTHER_BRANCH_BLOCKS = inherited + (64000000,)
def check_seeds(cfg):
 return {cfg['base']+1000*s for s in range(10)}
'''
    out = m.literal_source_evidence(text)
    assert out['physics'][0]['physics'] == [0.0034,0.001,0.055]
    assert out['seed_block_literals'][0]['value'] == 64000000
    assert out['seed_registry_functions'][0]['function'] == 'check_seeds'


def test_flat_result_metadata_is_not_lost_and_metrics_are_not_traversed():
    data = dict(target_physics=[0.0034,0.001,0.055],
                cells=[dict(target_physics=[0.009,0.009,0.09])],
                results=dict(physics=[0.008,0.008,0.08]),
                metadata=dict(source_physics=[[0.0025,0.0015,0.07]]))
    rows = m.artifact_metadata(data)
    assert {tuple(r['physics']) for r in rows} == {(0.0034,0.001,0.055),(0.0025,0.0015,0.07)}


def test_manual_reserved_tuple_and_unbounded_seed_line_detected():
    out = m.document_evidence('Uncommitted MCC holdout (0.0034, 0.001, 0.055)\nSeeds 64,000,000+ reserved manually.')
    assert out['physics'][0]['physics'] == [0.0034,0.001,0.055]
    assert '64,000,000+' in out['manual_seed_lines'][0]['text']


@pytest.mark.parametrize('gap', ['new_physics','parse_issues','unresolved_seed_functions','unversioned_manual_files'])
def test_any_coverage_gap_blocks_registration(gap):
    args = dict(provenance_ok=True,new_physics=[],parse_issues=[],
                unresolved_seed_functions=[],unversioned_manual_files=[],closure_attested=True)
    args[gap] = ['missing evidence']
    assert m.coverage_verdict(**args) == 'BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE'


def test_provenance_failure_precedes_coverage_and_complete_parse_is_not_enough():
    args = dict(provenance_ok=False,new_physics=[],parse_issues=[],
                unresolved_seed_functions=[],unversioned_manual_files=[])
    assert m.coverage_verdict(**args) == 'BLOCKED_PROVENANCE_MISMATCH'
    args['provenance_ok'] = True
    assert m.coverage_verdict(**args) == 'BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE'
    assert m.coverage_verdict(**args,closure_attested=True) == 'READY_FOR_SEPARATE_TARGET_SEED_REGISTRATION'


def test_seed_range_endpoints_do_not_certify_offsets_outside_them():
    intervals = [[64000000,64010000]]
    assert m.contains(intervals,64000000)
    assert m.contains(intervals,64010000)
    assert not m.contains(intervals,64010001)
    assert not m.contains(intervals,63999999)


def test_no_execution_import_or_selector():
    tree = ast.parse(Path(m.__file__).read_text())
    imports = {n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert not any(n.startswith(('numpy','torch','gym','nexus.world','nexus.tasks')) for n in imports)
    assert not {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)} & {'holdout_from_rule','execute','train','make_env'}
