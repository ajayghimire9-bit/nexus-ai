"""No-fit residual inventory. Read-only hashes. No collection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot
from nexus.evolution2 import residual_timing_probe as timing
from nexus.evolution2 import source_fitting_benchmark as fitting

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_nofit_inventory.json"

STATUS = "NO_FIT_TEN_BUNDLE_UNAVAILABLE"
REQUIRED_PER_FAMILY = v2.N_BUNDLES
EXCLUDED_DIRS = (
    "checkpoints/acrobot_lookahead_confirm_h16",
    "artifacts/latent_generalization_confirmation_checkpoints",
    "artifacts/control_replication_checkpoints",
)

ELIGIBLE = (
    {
        "id": "pendulum_mlp_u1000_seed0",
        "family": "pendulum",
        "role": "context_optimization_residual_mlp",
        "path": "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt",
        "sha256": "4f4db2ca0ade8d2e19cb37971cf7343959edcdc17befe73e1aa9169e19c21cc2",
    },
    {
        "id": "pendulum_mlp_u1000_seed1",
        "family": "pendulum",
        "role": "context_optimization_residual_mlp",
        "path": "artifacts/context_optimization_checkpoints/seed1_mlp_u1000.pt",
        "sha256": "eb72c8c9f41d6e53a123e9f9b9aa86ce0540117e33a97c5617c164ff4456526f",
    },
    {
        "id": "pendulum_mlp_u1000_seed2",
        "family": "pendulum",
        "role": "context_optimization_residual_mlp",
        "path": "artifacts/context_optimization_checkpoints/seed2_mlp_u1000.pt",
        "sha256": "58dc9209c1435543b33cb48878785a30705bc9909090510631e40f7e95b466a1",
    },
    {
        "id": "acrobot_lookahead_seed0",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed0.pt",
        "sha256": "bcd7fbb61231c314d83cf96d73e49e29f19d9dd10e299bc69b7fe3811ca05c2f",
    },
    {
        "id": "acrobot_lookahead_seed1",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed1.pt",
        "sha256": "ca37b1edb9c97dcf91ceb50efc2536b54d30d7d94e81677d1e9cfb52c8c1a556",
    },
    {
        "id": "acrobot_lookahead_seed2",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed2.pt",
        "sha256": "846d0e9f1597b7b8aac85fa4a5d1fc7313e9077f0382e779de8cd4d2192dec3b",
    },
    {
        "id": "acrobot_lookahead_seed3",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed3.pt",
        "sha256": "abd0e6d0e24f0a2564281853cf627f18146d8f65013a1313ec3355a3d77f70b7",
    },
    {
        "id": "acrobot_lookahead_seed4",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed4.pt",
        "sha256": "4f13c13af7c1f59860bdfcc27ba5e0d58111464abc58bb4fff6c3b0053c827aa",
    },
    {
        "id": "acrobot_lookahead_seed5",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed5.pt",
        "sha256": "40177d4424c1e644eb0026609441b07adf669a961c5364c367443eb7f6b5516f",
    },
    {
        "id": "acrobot_lookahead_seed6",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed6.pt",
        "sha256": "9960fe4efd40e81993d2c13061ebf2e248b23e5e80a7e8da6fa38f83ffd88055",
    },
    {
        "id": "acrobot_lookahead_seed7",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed7.pt",
        "sha256": "37e6055fa7ffe16e0c75aafcd2bdfae3f15853487535ad88d12fb95ee262c54f",
    },
    {
        "id": "acrobot_lookahead_seed8",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed8.pt",
        "sha256": "f37ad2738d5a76cbb91c823f8597c4250c4d03432de3b3eb5cf6296ed8936fa9",
    },
    {
        "id": "acrobot_lookahead_seed9",
        "family": "acrobot",
        "role": "historical_lookahead_development",
        "path": "checkpoints/acrobot_lookahead_h16/seed9.pt",
        "sha256": "72009a34fbbd7d585ce5ce8d8cb6de542d043caf9333fa44a7f4944a24209692",
    },
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "no-fit reuse is unauthorized: n=10 residuals are unavailable, "
        "v2 hashes stay frozen, collection remains forbidden"
    )


def inventory() -> list[dict]:
    rows = []
    for spec in ELIGIBLE:
        path = ROOT / spec["path"]
        present = path.is_file()
        digest = file_sha256(path) if present else None
        rows.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "role": spec["role"],
                "path": spec["path"],
                "expected_sha256": spec["sha256"],
                "present": present,
                "matches": bool(present and digest == spec["sha256"]),
            }
        )
    return rows


def family_counts() -> dict[str, int]:
    counts = {"pendulum": 0, "acrobot": 0}
    for row in inventory():
        if row["matches"]:
            counts[row["family"]] += 1
    return counts


def nofit_status() -> dict:
    counts = family_counts()
    shortfall = {
        family: max(0, REQUIRED_PER_FAMILY - counts[family])
        for family in ("pendulum", "acrobot")
    }
    return {
        "status": STATUS,
        "required_per_family": REQUIRED_PER_FAMILY,
        "counts": counts,
        "shortfall": shortfall,
        "excluded": list(EXCLUDED_DIRS),
        "recipe_matched": False,
        "pendulum_role": "context_optimization_residual_mlp",
        "acrobot_role": "historical_lookahead_development",
        "note": (
            "Pendulum has three u1000 residual MLPs from context optimization. "
            "Acrobot has ten historical lookahead development weights. Those "
            "are not a matched 10x10 residual recipe and confirmation files "
            "stay excluded."
        ),
    }


def nofit_worksheets() -> dict:
    infer = timing.feasibility_from_measured()
    conservative = float(infer.get("conservative_s") or 0.0)
    sheet_pilot = pilot.worksheet()
    full = v2.worksheet()
    pilot_real = (
        sheet_pilot["revealed_training_steps"]
        + sheet_pilot["development_evaluation_steps"]
    )
    v2_real = full["training_matrix_steps"] + full["development_evaluation_steps"]
    micro_real = 3 * (
        pilot.REVEALED_VARIANTS_PER_FAMILY + pilot.DEVELOPMENT_CONDITIONS
    ) * 2 * v2.EPISODE_STEPS
    micro_imagined = micro_real * v2.IMAGINED_CAP_PER_DECISION
    return {
        "v2_nofit_real_steps": v2_real,
        "v2_nofit_imagined": full["first_screen_imagined_upper_bound"],
        "v2_nofit_planning_s": conservative * full["first_screen_imagined_upper_bound"],
        "v2_nofit_feasibility": "NO-GO",
        "pilot_nofit_real_steps": pilot_real,
        "pilot_nofit_imagined": sheet_pilot["first_screen_imagined_upper_bound"],
        "pilot_nofit_planning_s": conservative
        * sheet_pilot["first_screen_imagined_upper_bound"],
        "pilot_nofit_feasibility": "BLOCKED",
        "micro_n": 3,
        "micro_real_steps": micro_real,
        "micro_imagined": micro_imagined,
        "micro_planning_s": conservative * micro_imagined,
        "micro_feasibility": "NOT_V2",
        "source_fitting_s": 0,
        "fitting_status": fitting.STATUS,
        "rewrites_v2": False,
    }


def remaining_blockers() -> list[str]:
    return [
        STATUS,
        fitting.STATUS,
        "holdout_unnamed",
        "twelve_arm_scientific_dispatch_blocked",
        "full_v2_no_go_under_900s",
        "v2_pilot_blocked_without_ten_matched_residuals",
        "scientific_dispatch_unauthorized",
        "h17_blocked",
    ]


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "modifies_checkpoints": False,
        "status": nofit_status(),
        "inventory": inventory(),
        "worksheets": nofit_worksheets(),
        "blockers": remaining_blockers(),
        "v2_hashes_frozen": pilot.v2_hashes_frozen(),
        "pilot_hashes_frozen": (
            pilot.file_sha256(pilot.CONFIG) == pilot.LOCKED_CONFIG
            and pilot.file_sha256(pilot.PROTOCOL) == pilot.LOCKED_PROTOCOL
            and pilot.file_sha256(pilot.ALLOCATION) == pilot.LOCKED_ALLOCATION
        ),
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "next_action": (
            "Do not collect replacements and do not reuse closed confirmation "
            "weights. A ten-bundle no-fit screen is unavailable. Next allowed "
            "step remains a separately authorized persist of matched "
            "Pendulum/Acrobot source arrays, or an explicit non-v2 n=3 lock."
        ),
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
