"""Seed ranges for the self-repair increment R1 (NOT LOCKED), namespace de3. Registered at import into the existing seed
registry WITHOUT editing src/nexus/seed_registry.py (a locked Stages 1-3 file); one-use claims go to the same spent ledger.
  src    library learning only        dev    reusable development
  val    one-use admission gate       val_b  used once only if val is spent by an implementation change
  test   one-use sealed confirmation (withheld X1 on even seeds, X2 on odd seeds)"""
from nexus import s456_seeds  # noqa: F401  (keeps the de2 ranges registered for the disjointness check)
from nexus import seed_registry as R

RANGES = {("de3", "src"): range(941, 947), ("de3", "dev"): range(951, 959), ("de3", "val"): range(7941, 7945),
          ("de3", "val_b"): range(7945, 7949), ("de3", "test"): range(7951, 7959)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("de3", "val"), ("de3", "val_b"), ("de3", "test")}
R._check_disjoint()
