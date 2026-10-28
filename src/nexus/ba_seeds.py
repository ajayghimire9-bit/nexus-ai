"""Seed ranges for the bounded-acceptance track (ba) (NOT LOCKED); registered at import; one-use claims in the same ledger.
  ep_held2   FRESH held-out micro-episodes for the Part 2 rerun (never run by any arm before this track)
  edev2      FRESH energy build projects for the Part 2 rerun (energy = seed % 4 == 3; 12 projects)
  val / val_b / test   one-use end-to-end validation (8), post-revision validation (8; only after one disclosed revision),
             sealed confirmation (16; includes the fresh unseen class X6)
Diagnosis (Step 1) uses DEV only: oc/ep_train explore episodes, oc/edev energy builds, and the spent oc projects
13127 (oc/val, energy), 13143 / 13155 (oc/test, energy) regenerated in memory from the generator (never from the vault)."""
from nexus import oc_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("ba", "ep_held2"): range(22000, 22300), ("ba", "edev2"): range(13201, 13249),
          ("ba", "val"): range(13261, 13269), ("ba", "val_b"): range(13271, 13279), ("ba", "test"): range(13281, 13297)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("ba", "val"), ("ba", "val_b"), ("ba", "test")}
R._check_disjoint()
