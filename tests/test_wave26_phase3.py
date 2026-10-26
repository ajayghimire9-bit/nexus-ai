"""Wave 26 Phase 3: sealed vault loader, tested ONLY on a mock vault (the real vault is never touched)."""
import hashlib
import json
import os

import pytest

from nexus import sealed_vault_loader as L
from nexus.seed_registry import SeedHygieneError

MOCK_API = '''
def load_sealed_split(split_name, seed):
    return [([([1, 2], [2, 1])], [[3, 4]], lambda x: list(reversed(x)), {"split": split_name, "seed": seed})]
'''


def _mock_vault(tmp_path):
    v = tmp_path / "mock_vault"
    v.mkdir()
    (v / "api.py").write_text(MOCK_API)
    (v / "data.txt").write_text("payload")
    lines = [f"{hashlib.sha256((v / n).read_bytes()).hexdigest()}  {n}" for n in ("api.py", "data.txt")]
    manifest = "\n".join(lines) + "\n"
    (v / "vault_manifest.sha256").write_text(manifest)
    committed = tmp_path / "committed.sha256"
    committed.write_text(manifest)
    return v, committed


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "AUDIT_LOG", tmp_path / "access.jsonl")
    return tmp_path


def test_refuses_without_harness_token(env, monkeypatch):
    v, committed = _mock_vault(env)
    monkeypatch.delenv("NEXUS_SEALED_HARNESS_TOKEN", raising=False)
    with pytest.raises(L.SealedVaultError):
        L.load_split("group_a", 3001, vault_dir=v, committed=committed)
    assert json.loads((env / "access.jsonl").read_text().splitlines()[-1])["event"] == "refused"


def test_loads_with_token_and_matching_hashes(env, monkeypatch):
    v, committed = _mock_vault(env)
    monkeypatch.setenv("NEXUS_SEALED_HARNESS_TOKEN", "locked")
    tasks = L.load_split("group_a", 3001, vault_dir=v, committed=committed)
    assert isinstance(tasks[0], L.SealedTask) and tasks[0].oracle_fn([1, 2, 3]) == [3, 2, 1]
    events = [json.loads(l)["event"] for l in (env / "access.jsonl").read_text().splitlines()]
    assert events == ["verified", "loaded"]


def test_refuses_on_tampered_file_or_manifest(env, monkeypatch):
    v, committed = _mock_vault(env)
    monkeypatch.setenv("NEXUS_SEALED_HARNESS_TOKEN", "locked")
    (v / "data.txt").write_text("tampered")
    with pytest.raises(L.SealedVaultError):
        L.load_split("group_b", 3011, vault_dir=v, committed=committed)
    v2, committed2 = _mock_vault(env / "second") if (env / "second").mkdir() is None else (None, None)
    committed2.write_text(committed2.read_text() + "0" * 64 + "  extra.py\n")
    with pytest.raises(L.SealedVaultError):
        L.load_split("group_a", 3001, vault_dir=v2, committed=committed2)


def test_split_seed_binding_is_enforced(env, monkeypatch):
    v, committed = _mock_vault(env)
    monkeypatch.setenv("NEXUS_SEALED_HARNESS_TOKEN", "locked")
    with pytest.raises(SeedHygieneError):
        L.load_split("group_a", 3011, vault_dir=v, committed=committed)      # group_b seed
    with pytest.raises(SeedHygieneError):
        L.load_split("external_arc_1d_grid", 1001, vault_dir=v, committed=committed)


def test_committed_manifest_is_present_and_well_formed():
    entries = L.parse_manifest(L.COMMITTED_MANIFEST.read_text())
    assert len(entries) == 39 and all(len(h) == 64 for h, _ in entries)


def test_driver_verifies_vault_before_claiming_seeds():
    src = (L.ROOT / "scripts" / "phase4_invent.py").read_text()
    assert src.index("verify_vault()") < src.index('R.claim("phase3", "vault_group_a"')
