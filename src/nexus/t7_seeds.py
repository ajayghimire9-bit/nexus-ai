"""Seed ranges for the 7-trial tournament (t7) (NOT LOCKED); registered at import, one-use claims in the same ledger.
  tsrc / tdev / theld   synthesis-task seeds (per family) - learning / selection / held-out report (all fresh vs u5)
  ddev / dval           de5-world operations projects for Trial 1's state-monitor arm (dev calibration / 4 fresh one-use)
  pdev / val / test     t7 end-to-end projects (val, val_b, test one-use; test = X3 / X4 incl. the unseen energy domain)"""
from nexus import u5_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("t7", "tsrc"): range(12000, 12010), ("t7", "tdev"): range(12100, 12105), ("t7", "theld"): range(12200, 12205),
          ("t7", "ddev"): range(12301, 12307), ("t7", "dval"): range(12311, 12315),
          ("t7", "pdev"): range(12401, 12409), ("t7", "val"): range(12421, 12429), ("t7", "val_b"): range(12431, 12439),
          ("t7", "test"): range(12441, 12457)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("t7", "dval"), ("t7", "val"), ("t7", "val_b"), ("t7", "test")}
R._check_disjoint()
