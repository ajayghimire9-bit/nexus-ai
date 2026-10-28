"""Seed ranges for the OOP track (NOT LOCKED), namespace de5. Registered at import WITHOUT editing seed_registry.py; one-use
claims go to the same spent ledger.  src (reserved for Phase 2 library learning) | dev development | val one-use gate |
val_b one-use, only after ONE disclosed revision | test one-use sealed confirmation (X3 on even seeds, X4 on odd seeds)."""
from nexus import r2_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("de5", "src"): range(981, 987), ("de5", "dev"): range(991, 999), ("de5", "val"): range(7981, 7985),
          ("de5", "val_b"): range(7985, 7989), ("de5", "test"): range(7991, 7999)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("de5", "val"), ("de5", "val_b"), ("de5", "test")}
R._check_disjoint()
