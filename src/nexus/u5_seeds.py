"""Seed ranges for the u5 (unified 5-pillar) track (NOT LOCKED). Registered at import WITHOUT editing seed_registry.py;
one-use claims go to the same spent ledger.
  tsrc / tadm / tdev / theld   synthesis-task seeds (per family): src = learning material (policies, libraries, curricula,
                               meta-training); adm = library admission validation; dev = pillar selection; held = dev-level
                               held-out evaluation for Pillars 3-5 (never used for selection or training)
  psmoke                       platform smoke checks only (never reported as evidence)
  pdev                         end-to-end development projects
  val / val_b                  one-use end-to-end validation (val_b only after ONE disclosed revision)
  test                         one-use sealed confirmation (X3 on even seeds, X4 on odd seeds; all three domains)"""
from nexus import oop_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("u5", "tsrc"): range(10000, 10010), ("u5", "tadm"): range(10600, 10605), ("u5", "tdev"): range(10800, 10805),
          ("u5", "theld"): range(11000, 11005), ("u5", "psmoke"): range(8090, 8092), ("u5", "pdev"): range(8001, 8013),
          ("u5", "val"): range(8021, 8027), ("u5", "val_b"): range(8027, 8033), ("u5", "test"): range(8041, 8053)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("u5", "val"), ("u5", "val_b"), ("u5", "test")}
R._check_disjoint()
