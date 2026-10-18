"""Source-fitting inventory and feasibility. No collection. No env steps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import residual_timing_probe as timing
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_source_fitting_benchmark.json"
RECIPE_FILE = ROOT / "configs" / "acrobot_lookahead.yaml"

STATUS = "SOURCE_FITTING_UNAVAILABLE"
SEARCHED = (
    "artifacts/**/*.npz",
    "artifacts/**/*.npy",
    "data/**/*.npz",
    "data/**/*.npy",
    "datasets/**/*.npz",
    "datasets/**/*.npy",
    "runs/**/*.npz",
    "runs/**/*.npy",
    "checkpoints/**/*.npz",
    "checkpoints/**/*.npy",
)
EXCLUDED_PREFIXES = (
    "artifacts/evolution2_source_arrays/",
    "artifacts/evolution2_fit_clock_disposable/",
)
CLOSED_TOKENS = (
    "confirm",
    "confirmation",
    "holdout",
    "h14",
    "h15",
    "h16",
    "h17",
    "development",
    "unused",
)
RECIPE = {
    "module": "nexus.world.train.train_world_model",
    "kind": "residual",
    "hidden": [64, 64],
    "epochs": 20,
    "n_train": 1024,
    "n_val": 256,
    "optimizer": "Adam",
    "lr": 0.001,
    "recipe_file": "configs/acrobot_lookahead.yaml",
    "persists_transitions": False,
    "persists_weights_only": True,
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_permitted_source_file(path: Path) -> bool:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    name = path.name.lower()
    if any(token in name for token in CLOSED_TOKENS):
        return False
    return path.suffix.lower() in {".npz", ".npy"}


def _existing(pattern: str) -> list[str]:
    return [
        str(path.relative_to(ROOT))
        for path in ROOT.glob(pattern)
        if path.is_file() and _is_permitted_source_file(path)
    ]


def checkpoint_provenance() -> list[dict]:
    return timing.checkpoint_status()


def source_data_status() -> dict:
    found: list[str] = []
    for item in SEARCHED:
        found.extend(_existing(item))
    recipe = dict(RECIPE)
    recipe["recipe_sha256"] = file_sha256(RECIPE_FILE) if RECIPE_FILE.is_file() else None
    return {
        "status": STATUS,
        "found": found,
        "searched": list(SEARCHED),
        "recipe": recipe,
        "checkpoints": checkpoint_provenance(),
        "collection": False,
        "scientific": False,
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "note": (
            "Lookahead recipes collect 1024/256 transitions in memory and save "
            "only residual weights. E2.8 persist arrays are excluded from this "
            "historical inventory; they do not close the twenty-fit v2 clock. "
            "Closed confirmation/H17 files are not source data."
        ),
    }


def require_fitting_benchmark() -> None:
    raise RuntimeError(
        "SOURCE_FITTING_UNAVAILABLE: no stored Pendulum/Acrobot training "
        "transitions; collection is forbidden"
    )


def remaining_blockers() -> list[str]:
    return [
        "SOURCE_FITTING_UNAVAILABLE",
        "holdout_unnamed",
        "twelve_arm_scientific_dispatch_blocked",
        "full_v2_no_go_under_900s",
        "v2_pilot_unknown_without_fitting_cost",
        "scientific_dispatch_unauthorized",
        "h17_blocked",
    ]


def combined_feasibility() -> dict:
    fit = source_data_status()
    infer = timing.feasibility_from_measured()
    v2_plan = float(infer.get("v2_conservative_planning_s") or 0.0)
    pilot_plan = float(infer.get("pilot_conservative_planning_s") or 0.0)
    return {
        "fitting": fit["status"],
        "inference": infer.get("status"),
        "v2_real_steps": v2.worksheet()["first_screen_total_steps"],
        "v2_imagined": v2.worksheet()["first_screen_imagined_upper_bound"],
        "pilot_real_steps": pilot.worksheet()["first_screen_total_steps"],
        "pilot_imagined": pilot.worksheet()["first_screen_imagined_upper_bound"],
        "v2_conservative_planning_s": v2_plan,
        "pilot_conservative_planning_s": pilot_plan,
        "source_fitting_s": None,
        "ten_bundle_two_family_expected_fitting_s": None,
        "v2_feasibility": "NO-GO",
        "pilot_feasibility": "UNKNOWN",
        "reason": (
            "conservative planning already exceeds 0.75 of 900 s for full v2; "
            "source fitting is unavailable so the remaining 20 residual fits "
            "cannot be added; v2-pilot planning is ~340 s with unknown fitting"
        ),
        "blockers": remaining_blockers(),
        "scientific": False,
        "new_ledger_debit": False,
        "next_action": (
            "Do not collect replacements. Keep dispatch blocked. Next allowed "
            "step is a separately authorized persist of source-only train/val "
            "arrays for a disposable residual-MLP fit clock, or a smaller "
            "worksheet that does not require twenty unmeasured fits."
        ),
    }


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "source_data": source_data_status(),
        "feasibility": combined_feasibility(),
        "trusted_cache": "TrustedEvaluator",
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
