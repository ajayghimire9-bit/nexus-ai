"""Manifest and parser checks only. Does not score the locked evaluation."""
from copy import deepcopy
from pathlib import Path

from nexus.seed.conversation_capability import load_manifest
from nexus.seed.workspace_conversation import parse_request


def test_manifest_is_locked_and_unweighted():
    root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(root / 'configs/seed_conversation_capability_v1.json')
    assert manifest['aggregate_score'] is False
    assert manifest['weighting'] is None
    assert [task['id'] for task in manifest['csv_tasks']] == [
        'csv_easy_sum', 'csv_missing_values', 'csv_unfamiliar_names', 'csv_transfer_same',
        'csv_inappropriate', 'csv_unsupported_below', 'csv_fresh_no_inherit']
    assert manifest['methods'] == ['tools', 'ordinary_cache', 'nexus_procedures']


def test_parser_rejects_below_and_does_not_inherit_on_fresh():
    prior = dict(op='sum', min=5.0, order='asc')
    blocked = parse_request('Summarize amounts below 10 using data.csv', prior)
    assert blocked.grain == 'sum' and blocked.unsupported and not blocked.understood
    fresh = parse_request('Summarize amounts by region using data.csv', prior)
    assert fresh.relation == 'fresh' and fresh.understood and not fresh.minimum_stated
    repeat = parse_request('Now do the same for other.csv', prior)
    assert repeat.relation == 'repeat'


def test_parser_flags_conflict_and_two_files():
    clash = parse_request('Summarize amounts smallest first and largest first using a.csv')
    assert 'conflicting_order' in clash.conflicts
    both = parse_request('Summarize amounts by region using a.csv and b.csv')
    assert 'multiple_files' in both.conflicts


def test_verifier_reconstructs_reference_and_rejects_tampering(tmp_path):
    import json
    from scripts.verify_seed_conversation_capability import verify
    root = Path(__file__).resolve().parents[1]
    artifact = root / 'artifacts/seed_conversation_capability_v1/seed_conversation_capability_v1.json'
    report = verify(artifact)
    assert report['valid'] is True
    assert report['independent_reference_reconstructed'] is True

    # Tamper with both output and reference_output so they still equal each other
    payload = json.loads(artifact.read_text(encoding='utf-8'))
    for row in payload['records']:
        if row.get('kind') == 'csv_trial' and row['task_id'] == 'csv_easy_sum':
            row['scored']['output'] = [{'region': 'tampered', 'total': 999999.0}]
            row['scored']['reference_output'] = [{'region': 'tampered', 'total': 999999.0}]
            break
    tampered_path = tmp_path / 'tampered.json'
    tampered_path.write_text(json.dumps(payload), encoding='utf-8')
    try:
        verify(tampered_path)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError('expected verifier to reject tampered output')

