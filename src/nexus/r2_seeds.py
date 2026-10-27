"""Seed ranges for R2 (NOT LOCKED), namespace de4. Registered at import WITHOUT editing seed_registry.py; one-use claims go to
the same spent ledger.  src library learning | dev development | val one-use gate | val_b one-use, only after ONE disclosed
revision | test one-use sealed confirmation (withheld X3 on even seeds, X4 on odd seeds)."""
from nexus import r1_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("de4", "src"): range(961, 967), ("de4", "dev"): range(971, 979), ("de4", "val"): range(7961, 7965),
          ("de4", "val_b"): range(7965, 7969), ("de4", "test"): range(7971, 7979)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("de4", "val"), ("de4", "val_b"), ("de4", "test")}
R._check_disjoint()
