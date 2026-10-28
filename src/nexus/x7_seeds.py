"""Seed ranges for the x7 track (expression mapping, held-out schema transformations) (NOT LOCKED); registered at import;
one-use claims in the same ledger.
  dev      x7 development projects (split 'x7_dev': declared compositional dev family XD1 / XD2 / XD3 + distractor churn XR)
  pcheck   platform check of the held-out X7 generator / oracle / simulated human ONLY (no NEXUS arm ever runs on it)
  val / val_b   one-use validation (8: known classes + dev families; NO X7) / post-revision validation (same design)
  test     one-use confirmation (16: X7a x4, X7b x4, X6-family x4, X3 x2, X5 x2; every group of 4 covers the 4 domains)"""
from nexus import sc_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("x7", "dev"): range(13401, 13433), ("x7", "pcheck"): range(13451, 13459), ("x7", "val"): range(13461, 13469),
          ("x7", "val_b"): range(13471, 13479), ("x7", "test"): range(13481, 13497)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("x7", "val"), ("x7", "val_b"), ("x7", "test")}
R._check_disjoint()
