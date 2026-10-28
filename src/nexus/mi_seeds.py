"""Seed ranges for the method-invention track (mi) (NOT LOCKED); one-use claims in the same ledger.
  profile   baseline profiling / headroom check (dev families only)
  disc      discovery episodes (dev families only; fitness for candidate learning procedures)
  sel       selection episodes (dev families; choosing the frozen candidate inside each search arm)
  val       one-use validation (dev families, fresh)
  test      one-use confirmation (known, dev-unfamiliar fresh, WITHHELD families)"""
from nexus import x7_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("mi", "profile"): range(24000, 24200), ("mi", "disc"): range(24200, 24600), ("mi", "sel"): range(24600, 24800),
          ("mi", "val"): range(24800, 25000), ("mi", "test"): range(25000, 25400)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("mi", "val"), ("mi", "test")}
R._check_disjoint()
