"""Phase 8 partitions (NOT LOCKED), fixed before any Phase 8 learner outcome. Fresh ranges, disjoint at import:
  agi8de/dev     72000-73999  development (every Phase 6 / 7 project, including the inspected Phase 7 targets, is development data)
  agi8de/source  74000-75999  repetition r block 74000 + 1000 r:
                   train   0-399  main-lineage exogenous stream (paired across cohorts)
                   admit 400-549  method admission (applicable + retention projects)
                   pool  550-599  procedure-proposal SCREEN pool (replay caches)
                   roll  600-799  future-learning rollout streams (common to the incumbent and candidate clones)
                   down  800-899  downstream evaluation of frozen clone memories
                   conf  900-999  confirmation of an adopted edit (disjoint downstream set)
  ONE-USE agi8de/target 76000-76199 (72 targets), agi8de/panel 76200-76299 (improver panel: NOT opened, Stage 3 = 0 s)
Source / admission / pool / rollout / downstream / confirmation use Tiers 1-2 only (+ composites X1, X2); Tier 3 (P8, P9)
appears only in agi8de/target."""
from nexus.de_phase7 import seeds7 as S7                   # noqa: F401  (registers Phase 1-7 ranges first)
from nexus import seed_registry as R

RANGES = {("agi8de", "dev"): range(72000, 74000), ("agi8de", "source"): range(74000, 76000),
          ("agi8de", "target"): range(76000, 76200), ("agi8de", "panel"): range(76200, 76300)}
ONE_USE = {("agi8de", "target"), ("agi8de", "panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
COHORTS = ("Full", "FixedLearner")


def block(rep):
    b = RANGES[("agi8de", "source")].start + 1000 * rep
    return dict(train=range(b, b + 400), admit=range(b + 400, b + 550), pool=range(b + 550, b + 600), roll=range(b + 600, b + 800),
                down=range(b + 800, b + 900), conf=range(b + 900, b + 1000))


def target_manifest():
    """Same frozen structure as Phase 7 (8 per paradigm; 24 / 32 / 16 by tier), fresh seeds; mechanism family = paradigm
    (Tier 3: P8 lift-of family / P9 hybrid letter, recorded per row after generation)."""
    T = []
    for t in S7.target_manifest():
        t = dict(t)
        t["seed"] = t["seed"] - S7.RANGES[("agi7de", "target")].start + RANGES[("agi8de", "target")].start
        t["family"] = t["paradigm"] + (("." + t["hybrid"]) if t.get("hybrid") else "")
        t["answerable"] = t.get("dp_mode") != "undecided"
        T.append(t)
    return T
