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
    ("phase3", "vault_group_a"): range(3001, 3011), ("phase3", "vault_group_b"): range(3011, 3021),
    ("phase3", "vault_external"): range(3021, 3031),
    ("phase4", "dev"): range(721, 726), ("phase4", "confirm"): range(4001, 4006),
    ("phase5", "dev"): range(731, 734), ("phase5", "confirm"): range(5001, 5006),
    ("phase6", "dev"): range(741, 744), ("phase6", "orderings_confirm"): range(6001, 6006),
}
ONE_USE = {k for k in REGISTRY if k[1] != "dev"}


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
        for row in _spent():
            if tuple(row["key"]) == key:
                raise SeedHygieneError(f"{key} already spent by run {row['run_id']}")
        if record:
            SPENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with SPENT_LEDGER.open("a") as f:
                f.write(json.dumps(dict(key=list(key), seeds=seeds, run_id=run_id)) + "\n")
    return seeds


def assert_dev_seed(phase, seed):
    if owner_of(seed) != (phase, "dev"):
        raise SeedHygieneError(f"seed {seed} is not a {phase} dev seed (owner {owner_of(seed)})")
