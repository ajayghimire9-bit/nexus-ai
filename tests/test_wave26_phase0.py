"""Wave 26 Phase 0: seed hygiene, blind-vault firewall, standing gates."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_seed_ranges_are_disjoint_and_dev_confirm_separated(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_SEED_LEDGER", str(tmp_path / "spent.jsonl"))
    import importlib
    import nexus.seed_registry as R
    R = importlib.reload(R)
    R.claim("phase1", "dev", [701, 702], run_id="t")
    R.claim("phase1", "dev", [701], run_id="t2")                       # dev seeds may be reused in dev
    with pytest.raises(R.SeedHygieneError):
        R.claim("phase1", "dev", [1001], run_id="t")                    # confirmation seed in a dev run
    with pytest.raises(R.SeedHygieneError):
        R.claim("phase1", "confirm", [1001, 1002], run_id="t")          # must claim the whole range
    R.claim("phase1", "confirm", range(1001, 1006), run_id="c1")
    with pytest.raises(R.SeedHygieneError):
        R.claim("phase1", "confirm", range(1001, 1006), run_id="c2")    # one-use
    with pytest.raises(R.SeedHygieneError):
        R.assert_dev_seed("phase2", 701)


def test_blind_vault_firewall_blocks_reads_outside_the_harness(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "task.json").write_text("{}")
    log = tmp_path / "audit.jsonl"
    code = ("import sys; sys.path.insert(0, %r); from nexus.standing_gates import install_vault_audit_hook as h; "
            "h(log_path=%r); open(%r).read()") % (str(ROOT / "src"), str(log), str(vault / "task.json"))
    env = dict(os.environ, NEXUS_SEALED_VAULT_DIR=str(vault))
    env.pop("NEXUS_SEALED_HARNESS_TOKEN", None)
    blocked = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert blocked.returncode != 0 and "blind-vault firewall" in blocked.stderr
    env["NEXUS_SEALED_HARNESS_TOKEN"] = "locked-runner"
    ok = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert ok.returncode == 0
    rows = [json.loads(l) for l in log.read_text().splitlines()]
    assert [r["allowed"] for r in rows] == [False, True]


def test_standing_gate_helpers():
    from nexus.standing_gates import g_soundness, g_tycho, json_digest
    assert g_soundness([{"false_certificate": False}])["passed"]
    assert not g_soundness([{"false_certificate": True}])["passed"]
    assert g_tycho([{"work": 5, "work_by": {"a": 2, "b": 3}}])["passed"]
    assert not g_tycho([{"work": 6, "work_by": {"a": 2, "b": 3}}])["passed"]
    assert json_digest({"a": 1}) == json_digest({"a": 1})


def test_agents_md_carries_rule_1():
    assert "RULE 1 (BLIND VAULT FIREWALL)" in (ROOT / "AGENTS.md").read_text()


def test_owner_override_allows_exactly_one_more_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_SEED_LEDGER", str(tmp_path / "spent.jsonl"))
    import importlib
    import nexus.seed_registry as R
    R = importlib.reload(R)
    R.claim("phase1", "confirm", range(1001, 1006), run_id="c1")
    R.owner_override("phase1", "confirm", reason="outcome never written", approved_by="owner")
    R.claim("phase1", "confirm", range(1001, 1006), run_id="c2")
    with pytest.raises(R.SeedHygieneError):
        R.claim("phase1", "confirm", range(1001, 1006), run_id="c3")
