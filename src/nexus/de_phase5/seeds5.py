"""Phase 5 partitions (NOT LOCKED), fixed before any Phase 5 learner outcome. Every Phase 4 project and every scratch build
is development data. Fresh ranges, checked disjoint at import:
  agi5de/dev      59000-59999  development (the generator self-checks already used 59000-59299)
  agi5de/source   57400-58399  lineage r: 57400 + 300 r + 0..99 training, +100..199 validation, +200..299 skill admission
  agi5de/placebo  58600-58699  placebo RNG keys
  ONE-USE agi5de/target 58400-58599: the frozen target manifest below
Source projects have ONE decision point (watermark or checkpoint) in every requirement mode, base column-name pools and
SQLite only. Targets hold out: requirement COMBINATIONS (two decision points in one project - never in source), SCHEMA
names (held-out column-name pools), multi-step repairs with more extra faults, and the Spark engine (engine transfer)."""
from nexus.de_phase4 import seeds as S4                     # noqa: F401  (registers Phase 1-4 ranges first)
from nexus import seed_registry as R
from nexus.de_phase5.world5 import MODES

RANGES = {("agi5de", "dev"): range(59000, 60000), ("agi5de", "source"): range(57400, 58400),
          ("agi5de", "target"): range(58400, 58600), ("agi5de", "placebo"): range(58600, 58700)}
ONE_USE = {("agi5de", "target")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
DPS = ("watermark", "checkpoint")


def source_specs(n):
    """n single-decision-point source specs cycling (dp, mode, extra faults 0..1)."""
    base = [dict(dps={d: m}, runtime="sqlite", k_extra=k) for k in (0, 1) for d in DPS for m in MODES]
    return [dict(base[i % len(base)]) for i in range(n)]


def lineage_block(rep):
    b = RANGES[("agi5de", "source")].start + 300 * rep
    return dict(train=range(b, b + 100), val=range(b + 100, b + 200), admit=range(b + 200, b + 300))


def target_manifest():
    """72 one-use targets (36 types x 2 instances). `kind` is for analysis only (never visible to a learner)."""
    T = []
    for d in DPS:                                                        # seen combination, new instance (base names)
        for m in MODES:
            T.append(dict(dps={d: m}, runtime="sqlite", k_extra=0, kind="single_seen"))
    for d, m in [("watermark", "missing"), ("checkpoint", "conflict_approved"), ("watermark", "undecided"),
                 ("checkpoint", "explicit"), ("watermark", "conflict_approved"), ("checkpoint", "missing")]:
        T.append(dict(dps={d: m}, runtime="sqlite", k_extra=0, names="heldout", kind="single_heldout_schema"))
    for a, b in [("conflict_approved", "missing"), ("missing", "conflict_approved"), ("explicit", "missing"), ("missing", "explicit"),
                 ("conflict_approved", "explicit"), ("explicit", "conflict_approved"), ("undecided", "missing"), ("missing", "undecided"),
                 ("missing", "missing"), ("conflict_approved", "conflict_approved"), ("explicit", "explicit"), ("visible", "missing")]:
        T.append(dict(dps={"watermark": a, "checkpoint": b}, runtime="sqlite", k_extra=0, kind="two_dp_heldout_combo"))
    for d, m in [("watermark", "missing"), ("checkpoint", "conflict_approved"), ("watermark", "explicit"), ("checkpoint", "undecided")]:
        T.append(dict(dps={d: m}, runtime="sqlite", k_extra=2, kind="multistep"))
    for dps in [{"watermark": "conflict_approved", "checkpoint": "missing"}, {"watermark": "missing"}, {"checkpoint": "conflict_approved"},
                {"watermark": "explicit"}]:
        T.append(dict(dps=dps, runtime="spark", k_extra=0, names="heldout", kind="spark_engine"))
    T = [dict(t, instance=j) for j in range(2) for t in T]          # 2 independent instances of every target type (72)
    base = RANGES[("agi5de", "target")].start
    for i, t in enumerate(T):
        t["seed"] = base + i
    return T


def expected_outcome(t):
    """Analysis label from the requirement modes only: 'abstain' when abstention is the appropriate outcome (an undecided
    requirement, or more decision points needing a clarification than the single allowed question); else 'complete'
    (conflict_approved counts as resolvable without a question only through learned trust)."""
    modes = list(t["dps"].values())
    if "undecided" in modes:
        return "abstain"
    need_q = sum(m == "missing" for m in modes)
    return "abstain" if need_q > 1 else "complete"
