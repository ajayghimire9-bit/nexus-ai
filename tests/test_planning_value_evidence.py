"""Repository-only recorded evidence checks; never require checkpoint binaries."""
import hashlib
import json
from pathlib import Path

from nexus.world.planning_value import load_config, validate_and_summarize


def test_preserved_capture_recovery_and_all_saved_statistics(monkeypatch):
    import nexus.world.checkpoint_integrity as checkpoints
    def forbidden(*args, **kwargs):
        raise AssertionError('repository-only audit must not read local checkpoint files')
    monkeypatch.setattr(checkpoints,'verify_checkpoint_integrity',forbidden)
    path=Path('artifacts/planning_value.json')
    raw=json.loads(path.read_text())
    validation=json.loads(Path('artifacts/planning_value_validation.json').read_text())
    audit=json.loads(Path('artifacts/planning_value_audit.json').read_text())
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert raw['complete'] is False
    assert raw['failure']=={'type':'ValueError','message':'invalid support hash'}
    assert validation['raw_capture_sha256']==audit['artifact_sha256']==digest
    recomputed=validate_and_summarize(raw,load_config())
    for key in ('label','comparisons','per_task','valid'):
        assert recomputed[key]==validation[key]
    assert validation['new_environment_steps']==audit['new_environment_steps']==0
    assert audit['decisions_verified']==raw['counts']['suffix']==61440
    assert audit['interval']==recomputed['comparisons']['primary']['interval']
