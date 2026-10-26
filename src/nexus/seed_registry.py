"""Wave 26 seed registry: pre-allocated, non-overlapping seed ranges per phase (Phase 0 ground rules).

Rules enforced in code:
  * every seed a run uses must belong to the declared (phase, kind) range;
  * a confirmation / vault seed can never be used by a dev run (and vice versa);
  * a confirmation / vault seed range is one-use: claiming it a second time raises (persisted ledger);
  * ranges never overlap (checked at import).
Violations raise SeedHygieneError.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPENT_LEDGER = Path(os.environ.get("NEXUS_SEED_LEDGER", ROOT / "runs" / "experimental" / "seed_registry_spent.jsonl"))


class SeedHygieneError(RuntimeError):
    pass


REGISTRY = {
    ("phase1", "dev"): range(701, 706), ("phase1", "confirm"): range(1001, 1006),
    ("phase2", "dev"): range(711, 716), ("phase2", "confirm"): range(2001, 2006),
    # owner-approved (2026-10-26, Phase 2 option 2): re-run at a higher oracle cost on a fresh range
    ("phase2", "confirm_b"): range(2006, 2011),
    ("phase3", "vault_group_a"): range(3001, 3011), ("phase3", "vault_group_b"): range(3011, 3021),
    ("phase3", "vault_external"): range(3021, 3031),
    ("phase4", "dev"): range(721, 726), ("phase4", "confirm"): range(4001, 4006),
    ("phase5", "dev"): range(731, 736), ("phase5", "confirm"): range(5001, 5006),     # dev 731-735 (owner, 2026-10-26)
    ("phase6", "dev"): range(741, 746), ("phase6", "orderings_confirm"): range(6001, 6006),   # dev 741-745
    # Wave 27 robust architecture (owner, 2026-10-26): fresh one-use confirmation ranges; dev reuses the
    # Wave 26 Phase 4 / 5 / 6 dev ranges
    ("wave27_p4", "confirm"): range(4011, 4016), ("wave27_p5", "confirm"): range(5011, 5016),
    ("wave27_p6", "confirm"): range(6011, 6016),
    # Wave 28 postcondition core filter (owner, 2026-10-26)
    ("wave28_p4", "confirm"): range(4016, 4021), ("wave28_p5", "confirm"): range(5016, 5021),
    ("wave28_p6", "confirm"): range(6016, 6021),
    # Wave 29 Occam margin + x_verify (owner, 2026-10-26)
    ("wave29_p4", "confirm"): range(4021, 4026), ("wave29_p5", "confirm"): range(5021, 5026),
    ("wave29_p6", "confirm"): range(6021, 6026),
    # Wave 30 three-way split (owner, 2026-10-26): dev; admission_val (used only to ADMIT representations /
    # skeletons, never for final claims; reusable for admission decisions); final_sealed is generated later
    ("wave30", "dev"): range(751, 756), ("wave30", "admission_val"): range(7001, 7006),
    # final_sealed: counterfactual-world instances drawn ONLY by a locked runner after the generator
    # (src/nexus/wave30_alien.py) and models are frozen; never drawn during development or admission
    ("wave30", "final_sealed"): range(9301, 9311),
}
ONE_USE = {k for k in REGISTRY if k[1] not in ("dev", "admission_val")}


def _check_disjoint():
    seen = {}
    for key, r in REGISTRY.items():
        for s in r:
            if s in seen:
                raise SeedHygieneError(f"seed {s} allocated to both {seen[s]} and {key}")
            seen[s] = key


_check_disjoint()


def owner_of(seed):
    for key, r in REGISTRY.items():
        if seed in r:
            return key
    return None


def _spent():
    if not SPENT_LEDGER.exists():
        return []
    return [json.loads(l) for l in SPENT_LEDGER.read_text().splitlines() if l.strip()]


def claim(phase, kind, seeds, *, run_id, record=True):
    """Validate and (for one-use ranges) persistently consume `seeds` for (phase, kind)."""
    key = (phase, kind)
    if key not in REGISTRY:
        raise SeedHygieneError(f"unknown seed range {key}")
    seeds = list(seeds)
    for s in seeds:
        own = owner_of(s)
        if own != key:
            raise SeedHygieneError(f"seed {s} belongs to {own}, not {key}")
    if key in ONE_USE:
        if sorted(seeds) != list(REGISTRY[key]):
            raise SeedHygieneError(f"{key} must be claimed whole and once: {list(REGISTRY[key])}")
        rows = _spent()
        spent = sum(1 for r in rows if "override" not in r and tuple(r["key"]) == key)
        overrides = sum(1 for r in rows if r.get("override") and tuple(r["key"]) == key)
        if spent > overrides:
            raise SeedHygieneError(f"{key} already spent ({spent} claim(s), {overrides} owner override(s))")
        if record:
            SPENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with SPENT_LEDGER.open("a") as f:
                f.write(json.dumps(dict(key=list(key), seeds=seeds, run_id=run_id)) + "\n")
    return seeds


def owner_override(phase, kind, *, reason, approved_by):
    """Record a one-time owner authorisation to claim a spent one-use range once more (auditable)."""
    key = (phase, kind)
    if key not in ONE_USE:
        raise SeedHygieneError(f"{key} is not a one-use range")
    SPENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with SPENT_LEDGER.open("a") as f:
        f.write(json.dumps(dict(key=list(key), override=True, reason=reason, approved_by=approved_by)) + "\n")


def assert_dev_seed(phase, seed):
    if owner_of(seed) != (phase, "dev"):
        raise SeedHygieneError(f"seed {seed} is not a {phase} dev seed (owner {owner_of(seed)})")
