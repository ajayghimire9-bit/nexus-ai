"""Seed ranges for MI-2 (method invention, round 2; NOT LOCKED). Fresh ranges, disjoint from every earlier phase. MI-1's
ranges are untouched by MI-2: mi/val is spent; mi/test (MI-1's confirmation) stays closed with MI-1 and is never used here.
  diag     SUBH / headroom diagnosis, runtime calibration (dev families only; witness programs allowed here only)
  disc     discovery pool (dev families only)
  sel      selection pool inside each discovery lineage (dev families only)
  val      one-use Milestone A validation (K + dev-unfamiliar families, fresh instances)
  test     one-use Milestone A confirmation (K, dev-unfamiliar fresh, WITHHELD families SCL / AVG / MAX)
  bdev     Milestone B development (call-site tests; dev families only)
  btest    one-use Milestone B final evaluation (untouched; never used by A)"""
from nexus import mi_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("mi2", "diag"): range(25400, 25600), ("mi2", "disc"): range(25600, 26400), ("mi2", "sel"): range(26400, 26800),
          ("mi2", "val"): range(26800, 27100), ("mi2", "test"): range(27100, 27600), ("mi2", "bdev"): range(27600, 28000),
          ("mi2", "btest"): range(28000, 28400)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("mi2", "val"), ("mi2", "test"), ("mi2", "btest")}
R._check_disjoint()
