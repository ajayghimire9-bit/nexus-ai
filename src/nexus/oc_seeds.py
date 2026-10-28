"""Seed ranges for the ocean / meta-learning track (oc) (NOT LOCKED); registered at import; one-use claims in the same ledger.
  ep_train / ep_val / ep_held   micro-episode seeds: meta-training / meta-selection / held-out evaluation (>= 300)
  ep_xfer                       second-domain transfer episodes (Part 3)
  edev                          full energy build projects (dev) for Part 2; pdev end-to-end dev
  val / val_b / test            one-use end-to-end validation / revision / sealed confirmation (test includes X5)"""
from nexus import t7_seeds  # noqa: F401
from nexus import seed_registry as R

RANGES = {("oc", "ep_train"): range(20000, 20600), ("oc", "ep_val"): range(20600, 20800), ("oc", "ep_held"): range(21000, 21400),
          ("oc", "ep_xfer"): range(21500, 21900), ("oc", "edev"): range(13001, 13049), ("oc", "pdev"): range(13101, 13109),
          ("oc", "val"): range(13121, 13129), ("oc", "val_b"): range(13131, 13139), ("oc", "test"): range(13141, 13157)}
R.REGISTRY.update(RANGES)
R.ONE_USE |= {("oc", "val"), ("oc", "val_b"), ("oc", "test")}
R._check_disjoint()
