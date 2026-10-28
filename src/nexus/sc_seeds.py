"""Seed ranges for the schema-contract track (sc) (NOT LOCKED); registered at import; one-use claims in the same ledger.
  ep_held3        FRESH held-out micro-episodes for the separate growth-rule comparison (fallback disabled)
  dev             schema-contract development projects (split 'sc_dev': known dev conditions X6, X6P, X6D, X6M, LM, X3, X5)
  val / val_b     one-use validation (8: X6 x4, X3 x2, X5 x2; 2 per domain) / post-revision validation (same design)
  test            one-use confirmation (16: X6 x8, X3 x4, X5 x4; balanced across the four domains)"""
from nexus import ba_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("sc", "ep_held3"): range(23000, 23300), ("sc", "dev"): range(13301, 13349), ("sc", "val"): range(13361, 13369),
          ("sc", "val_b"): range(13371, 13379), ("sc", "test"): range(13381, 13397)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("sc", "val"), ("sc", "val_b"), ("sc", "test")}
R._check_disjoint()
