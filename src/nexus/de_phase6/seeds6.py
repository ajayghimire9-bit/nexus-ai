"""Phase 6 partitions (NOT LOCKED), fixed before any Phase 6 learner outcome. Fresh ranges, disjoint at import:
  agi6de/dev      60000-61999  development (generator checks and dev sweeps already used 61000-61799)
  agi6de/source   62000-64999  cohort lineage blocks of 250 (train stream, skill admission, M rollouts)
  agi6de/meta     65000-65999  Stage 3 improver-clone trajectories
  agi6de/placebo  66300-66399
  ONE-USE agi6de/target 66000-66199 (72 targets), agi6de/panel 66200-66299 (18-project improver panel)
Source and admission projects use Tier 1-2 paradigms only (P1-P7); Tier 3 (P8 lift-and-refactor, P9 hybrids) appears
ONLY in agi6de/target (tests). The panel is Tier 2 (single-stage; disclosed: the multi-stage compositions are Tier 3)."""
from nexus.de_phase5 import seeds5 as S5                   # noqa: F401  (registers Phase 1-5 ranges first)
from nexus import seed_registry as R

RANGES = {("agi6de", "dev"): range(60000, 62000), ("agi6de", "source"): range(62000, 65000), ("agi6de", "meta"): range(65000, 66000),
          ("agi6de", "target"): range(66000, 66200), ("agi6de", "panel"): range(66200, 66300), ("agi6de", "placebo"): range(66300, 66400)}
ONE_USE = {("agi6de", "target"), ("agi6de", "panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
COHORTS = ("Full", "SolvedOnly", "Fixed", "Scrambled")


def lineage_block(cohort, rep):
    b = RANGES[("agi6de", "source")].start + 250 * (COHORTS.index(cohort) * 3 + rep)
    # every cohort of a repetition sees the SAME exogenous stream (paired environment randomness)
    b0 = RANGES[("agi6de", "source")].start + 250 * rep
    return dict(train=range(b0, b0 + 150), admit=range(b0 + 150, b0 + 200), roll=range(b0 + 200, b0 + 250), private=b)


def meta_block(rep):
    b = RANGES[("agi6de", "meta")].start + 300 * rep
    return dict(train=range(b, b + 200), admit=range(b + 200, b + 250), val=range(b + 250, b + 300))


def target_manifest():
    T = []
    modes = ["explicit", "missing", "conflict_approved", "undecided", "visible", "undecided", "missing", "conflict_approved"]
    engines = ["sqlite", "duckdb", "spark", "duckdb", "sqlite", "duckdb", "spark", "duckdb"]
    for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        for j in range(8):
            t = dict(paradigm=p, engine=engines[j], names="heldout" if j % 2 else "base", tier=1 if p in ("P1", "P2", "P3") else 2)
            if p in ("P1", "P5", "P7"):
                t["dp_mode"] = modes[j]
            T.append(t)
    for j in range(8):
        T.append(dict(paradigm="P8", names="heldout" if j % 2 else "base", tier=3, dp_mode=modes[j]))
    for j, h in enumerate("ABCABCAB"):
        T.append(dict(paradigm="P9", hybrid=h, names="heldout" if j % 2 else "base", tier=3, dp_mode=modes[(j + 3) % 8]))
    base = RANGES[("agi6de", "target")].start
    for i, t in enumerate(T):
        t["seed"] = base + i
    return T


def panel_manifest():
    base = RANGES[("agi6de", "panel")].start
    out = []
    for i, (p, e) in enumerate([(p, e) for p in ("P4", "P5", "P6", "P7") for e in ("sqlite", "duckdb", "spark", "duckdb")][:16] + [("P5", "sqlite"), ("P7", "duckdb")]):
        out.append(dict(paradigm=p, engine=e, tier=2, seed=base + i, dp_mode=["missing", "explicit", "conflict_approved", "visible"][i % 4]
                        if p in ("P5", "P7") else None))
    return out
