"""Recorded-result verification needs JSON/provenance, not local model binaries."""
import hashlib
import json
from pathlib import Path
import pytest

from nexus.world.terminal_value import load_config
from nexus.world.terminal_value_execution import validate_capture


def test_locked_terminal_value_evidence_without_checkpoint_binaries(monkeypatch):
    import nexus.world.checkpoint_integrity as checkpoints
    def forbidden(*args,**kwargs):raise AssertionError('repository evidence verification must not require local .pt files')
    monkeypatch.setattr(checkpoints,'verify_checkpoint_integrity',forbidden)
    result_path=Path('artifacts/terminal_value.json');fit_path=Path('artifacts/terminal_value_source_fit.json')
    p=json.loads(result_path.read_text());fit=json.loads(fit_path.read_text());audit=json.loads(Path('artifacts/terminal_value_audit.json').read_text())
    assert p['complete'] is True and audit['audit_passed'] is True
    assert p['fit_sha256']==hashlib.sha256(fit_path.read_bytes()).hexdigest()
    assert audit['source_sha256']==hashlib.sha256(result_path.read_bytes()).hexdigest()
    recomputed=validate_capture(p,load_config(),fit)
    assert recomputed['label']==p['label']=='local_first_action_inconclusive'
    assert recomputed['comparisons']==p['comparisons']
    for key in ('mean','lo','hi'):
        assert audit['interval'][key]==pytest.approx(recomputed['comparisons']['primary']['interval'][key],abs=1e-9)
    assert audit['new_environment_steps']==0
