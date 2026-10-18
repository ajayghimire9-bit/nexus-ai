"""One-run science grant. Does not collect or rewrite frozen hashes."""
from __future__ import annotations

import json

import pytest

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_runner as runner
from nexus.evolution2.pendulum_acrobot_instance_rules import ROLE_DIGESTS


def test_human_approval_is_text_complete_and_matches_locked_roles():
    parsed = grant.verify_approval(grant.HUMAN_APPROVAL)
    assert parsed["status"] == "COMPLETE_TEXT_ONLY"
    assert parsed["four_role_valid"] is True
    assert parsed["env_cap"] == 17280
    report = grant.verify_roles()
    assert report["status"] == "PASS"
    assert report["digests"] == dict(ROLE_DIGESTS)
    assert report["historical_exclusion_clean"] is True
    hashes = grant.verify_frozen_hashes()
    assert all(hashes.values())
    assert lock.allocation_record()["authorized"] is False
    assert lock.allocation_record()["env_cap"] == 0


def test_markdown_approval_extracts_the_four_locked_roles():
    text = (
        f"Config SHA256: `{lock.LOCKED_CONFIG}` env_cap=17280 "
        "`acrobot_development` = `(0.8, 0.7, 1.15)` "
        "`acrobot_source` = `(0.85, 1.3, 0.85)` "
        "`pendulum_source` = `(7.5, 1.35, 1.4)` "
        "`pendulum_development` = `(12.5, 1.15, 0.65)`"
    )
    parsed = grant.verify_approval(text)
    assert parsed["four_role_valid"] is True


def test_grant_is_one_shot_and_does_not_rewrite_frozen_hashes(tmp_path, monkeypatch):
    path = tmp_path / "grant.json"
    monkeypatch.setattr(grant, "GRANT", path)
    record = grant.write_grant(grant.HUMAN_APPROVAL, source_commit_sha=grant.REQUIRED_COMMIT)
    assert record["authorized"] is True
    assert record["consumed"] is False
    assert record["env_cap"] == 17280
    assert record["source_commit"] == grant.REQUIRED_COMMIT
    assert grant.grant_unused() is True
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.file_sha256(lock.ALLOCATION) == lock.LOCKED_ALLOCATION
    consumed = grant.consume_grant()
    assert consumed["consumed"] is True
    assert consumed["runs"] == 1
    with pytest.raises(RuntimeError, match="already_consumed"):
        grant.consume_grant()
    with pytest.raises(Exception, match="unnamed|holdout"):
        grant.require_unused_grant(17280, grant.HUMAN_APPROVAL)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)


def test_grant_refuses_wrong_commit_and_7680(tmp_path, monkeypatch):
    monkeypatch.setattr(grant, "GRANT", tmp_path / "grant.json")
    with pytest.raises(RuntimeError, match="required_source_commit"):
        grant.write_grant(grant.HUMAN_APPROVAL, source_commit_sha="0" * 40)
    with pytest.raises(RuntimeError, match="occupied_default"):
        grant.require_unused_grant(7680, grant.HUMAN_APPROVAL)
