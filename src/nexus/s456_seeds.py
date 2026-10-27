"""Seed ranges for Stages 4-6 (NOT LOCKED). Registered at import into the existing seed registry WITHOUT editing
src/nexus/seed_registry.py (a locked Stages 1-3 file); claims go to the same spent ledger.
  src     reusable source projects (the Stage 6 library is learned only from these)
  dev     reusable development projects
  val     one-use admission validation (val_b only if val fails its gate and is reclassified as dev)
  test    one-use sealed final test (Stages 4, 5 and 6 are all scored on these same projects)"""
from nexus import seed_registry as R

RANGES = {("de2", "src"): range(921, 927), ("de2", "dev"): range(931, 937), ("de2", "val"): range(7921, 7925),
          ("de2", "val_b"): range(7925, 7929), ("de2", "test"): range(7931, 7939)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("de2", "val"), ("de2", "val_b"), ("de2", "test")}
R._check_disjoint()
