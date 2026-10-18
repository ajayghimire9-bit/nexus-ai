"""Source-only documentation and index integrity. No scientific stack."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "artifacts" / "research_session_h16_same_state_library_usage.json"
REGISTRY = ROOT / "artifacts" / "nexus_research_registry.json"
INVENTORY = ROOT / "artifacts" / "nexus_branch_inventory.json"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_ledger_is_unchanged():
    payload = json.loads(LEDGER.read_text())
    assert payload["ledger"]["consumed_total_s"] == 305.842
    assert payload["remaining_session_allowance_s"] == 3294.158
    digest = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    assert digest == "ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117"


def test_registry_forbids_science_and_keeps_h17_blocked():
    registry = json.loads(REGISTRY.read_text())
    assert registry["scientific"] is False
    assert registry["h17"] == "blocked"
    assert registry["ledger_s"] == [306.954, 3293.046]
    ids = {row["id"] for row in registry["experiments"]}
    assert {
        "V0.1",
        "H1",
        "H8",
        "H14",
        "H15",
        "H16",
        "H17",
        "E1-feasibility",
        "E2-pendulum-acrobot-v1",
        "E2-pendulum-acrobot-v2",
        "E2-pendulum-acrobot-v2-pilot",
        "E2-pendulum-acrobot-holdout-review",
        "E2-pendulum-acrobot-instance-rules",
        "E2-residual-timing-probe",
        "E2.2-adapter-correctness",
        "E2.3-source-fitting",
        "E2.4-nofit-inventory",
        "E2.5-n3-micro",
        "E2.6-execution-blockers",
        "E2.7-source-persist-request",
        "E2.8-source-persist-7680",
        "E2.9-fit-clock",
        "E2.10-evaluator-readiness",
    } <= ids
    h17 = next(row for row in registry["experiments"] if row["id"] == "H17")
    assert h17["status"] == "blocked"
    v1 = next(row for row in registry["experiments"] if row["id"] == "E2-pendulum-acrobot-v1")
    assert "superseded" in v1["status"]
    assert any(row["coverage"] == "incomplete" for row in registry["experiments"])


def test_inventory_has_ancestry_and_forbids_deletion():
    payload = json.loads(INVENTORY.read_text())
    assert payload["scientific"] is False
    assert payload["cleanup_policy"]["delete_now"] is False
    assert payload["counts"]["branches"] >= 140
    assert payload["counts"]["delete"] == 0
    assert payload["main"].startswith("d36b49f")
    assert payload["remote_sha_mismatch"] == []
    for row in payload["branches"]:
        assert row["delete"] is False
        assert row["ancestry"]["coverage"] == "source_verified"
        assert "cleanup_proposal" in row
        assert not row["cleanup_proposal"].startswith("delete")


def test_future_agents_must_consult_canonical_reuse_and_registry():
    agents = AGENTS.read_text()
    readme = README.read_text()
    for required in (
        "docs/NEXUS_CANONICAL_CURRENT_STATE.md",
        "docs/NEXUS_CODE_REUSE_MAP.md",
        "docs/NEXUS_FULL_RESEARCH_REGISTRY.md",
    ):
        assert required in agents
        assert required in readme
    assert "NOT_READY" in (ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_READINESS.md").read_text()
    v2 = (ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md").read_text()
    assert "COLLECTION UNAUTHORIZED" in v2
    assert "No crossover" in v2


def test_index_scripts_remain_source_only():
    for rel in (
        "scripts/nexus_branch_inventory.py",
        "scripts/nexus_research_registry.py",
    ):
        imported = _imports(ROOT / rel)
        assert imported.isdisjoint({"torch", "gymnasium", "numpy", "optuna"})
        source = (ROOT / rel).read_text()
        assert "git checkout" not in source
        assert "git branch -D" not in source
        assert "push --force" not in source
