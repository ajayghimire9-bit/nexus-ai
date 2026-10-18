"""Read-only real-planner binding audit. No Gymnasium. No new fits."""
from __future__ import annotations

from nexus.evolution1.catalogue import catalogue
from nexus.evolution2 import evaluator_dry_run as dry
from nexus.evolution2 import evaluator_readiness as ready
from nexus.evolution2.bindings import fixture_checkpoint, reviewed_binding
from nexus.evolution2.planner_adapter import twelve_arm_scientific_dispatch


def action_semantics() -> dict:
    rows = {}
    pendulum = reviewed_binding("pendulum")
    acrobot = reviewed_binding("acrobot")
    if pendulum.action_kind != "continuous_scalar" or pendulum.action_values != (-2.0, 0.0, 2.0):
        raise RuntimeError("pendulum_action_semantics_changed")
    if acrobot.action_kind != "native_discrete_index" or acrobot.action_values != (0, 1, 2):
        raise RuntimeError("acrobot_action_semantics_changed")
    if dry.decode_action(pendulum, 0) != -2.0 or dry.decode_action(pendulum, 2) != 2.0:
        raise RuntimeError("pendulum_decode_mismatch")
    if dry.decode_action(acrobot, 0) != 0 or dry.decode_action(acrobot, 2) != 2:
        raise RuntimeError("acrobot_decode_mismatch")
    rows["pendulum"] = {
        "space": pendulum.action_kind,
        "values": list(pendulum.action_values),
        "checkpoint": pendulum.checkpoint_id == fixture_checkpoint("pendulum"),
    }
    rows["acrobot"] = {
        "space": acrobot.action_kind,
        "values": list(acrobot.action_values),
        "checkpoint": acrobot.checkpoint_id == fixture_checkpoint("acrobot"),
    }
    return rows


def audit_real_planner() -> dict:
    bindings = ready.development_bindings()
    if bindings["n"] != 24 or bindings["all_bound"] is not True:
        raise RuntimeError("twelve_arm_real_binding_incomplete")
    if any(row["scientific"] is not False for row in bindings["rows"]):
        raise RuntimeError("scientific_binding_leaked")
    if len(catalogue()) != 12:
        raise RuntimeError("catalogue_size_mismatch")
    payload = dry.run_dry_run()
    if payload["n_planner_configs"] != 12:
        raise RuntimeError("real_planner_catalogue_incomplete")
    if payload["n_family_rows"] != 24:
        raise RuntimeError("real_planner_family_rows_incomplete")
    if payload["physical_vs_logical"]["physical_decisions"] != 24:
        raise RuntimeError("physical_metering_mismatch")
    if payload["physical_vs_logical"]["cached_replays"] != 2:
        raise RuntimeError("cached_identity_mismatch")
    if payload["scientific"] is not False or payload["enabled_dispatch"] is not False:
        raise RuntimeError("real_planner_audit_must_not_enable_science")
    scientific = twelve_arm_scientific_dispatch()
    return {
        "status": "PASS",
        "scientific_dispatch": scientific["status"],
        "n_bound": bindings["n"],
        "n_real_planner_rows": payload["n_family_rows"],
        "physical_decisions": payload["physical_vs_logical"]["physical_decisions"],
        "cached_replays": payload["physical_vs_logical"]["cached_replays"],
        "action_semantics": action_semantics(),
        "checkpoint_compatible": True,
        "gymnasium": False,
        "new_fits": False,
        "enabled_dispatch": False,
    }
