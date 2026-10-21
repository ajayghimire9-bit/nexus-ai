"""Fail-closed readiness, not an authorization record or scientific result."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = "8d62ce23722bafea9c355cde4f306ca23dad3584"
LEGACY_KERNEL_SHA256 = "c4f3f999d29196b7da2b6d24f750b9ec8591bcc56b67d9cd913859bd08ee923b"
REQUIRED_CAPABILITIES = frozenset({
    "strict_json_roles", "bounded_ast_execution", "message_only_processes",
    "public_rule_patch_fixture", "independent_receipt_reconstruction",
    "aggregate_actor_resource_host", "one_use_authorization_binding",
    "source_ast_rule_evolution", "disjoint_four_partition_generator",
    "post_freeze_private_final_generator", "private_proposal_retention_mdl_lifecycle",
    "all_executable_equal_budget_baselines", "grounded_cross_lab_assessment",
    "renamed_shuffled_full_replay", "complete_17_gate_verifier",
})
# Intentionally not loaded from owner-editable JSON booleans. There is no path
# from changing authorized:false to generating final targets in this revision.
IMPLEMENTED_CAPABILITIES = frozenset({
    "strict_json_roles", "bounded_ast_execution", "message_only_processes",
    "public_rule_patch_fixture", "independent_receipt_reconstruction",
})


def review(root):
    root = Path(root)
    config = json.loads((root / "configs/seed_open_primitive_transfer_v2.json").read_text())
    legacy = hashlib.sha256((root / "src/nexus/seed/open_primitive_transfer.py").read_bytes()).hexdigest()
    missing = sorted(REQUIRED_CAPABILITIES - IMPLEMENTED_CAPABILITIES)
    if legacy != LEGACY_KERNEL_SHA256:
        raise ValueError("historical kernel changed")
    if config["authorized"] is not False:
        raise ValueError("no scientific authorization path exists in this incomplete revision")
    if len(config["seeds"]) != 8 or len(set(config["seeds"])) != 8:
        raise ValueError("exact eight independent seeds required")
    return {"schema": "primitive_transfer_v2_readiness_v1", "base": BASE,
            "status": "BLOCKED_INCOMPLETE_IMPLEMENTATION", "scientific_execution_enabled": False,
            "missing_capabilities": missing, "kernel_preserved": True,
            "generated_final_tasks": 0, "session_used_s": config["carried_used_s"],
            "session_remaining_s": config["carried_remaining_s"]}


def require_execution_ready(root):
    result = review(root)
    if result["missing_capabilities"]:
        raise RuntimeError("scientific run blocked: " + ", ".join(result["missing_capabilities"]))
    raise RuntimeError("controlled authorization not implemented; execution refused")
