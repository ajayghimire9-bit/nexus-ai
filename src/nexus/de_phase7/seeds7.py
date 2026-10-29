"""Phase 7 partitions (NOT LOCKED), fixed before any Phase 7 learner outcome. Fresh ranges, disjoint at import:
  agi7de/dev      67000-68999  development (every Phase 6 project is development data too)
  agi7de/source   69000-70999  lineage r: 69000 + 1000 r: train stream 0-599, skill admission 600-799, procedure admission pool
                               (proposal selection) 800-899, untouched confirmation 900-999
  ONE-USE agi7de/target 71000-71199 (72 targets), agi7de/panel 71200-71299 (18-project improver panel)
Source / admission / pools use Tier 1-2 only; Tier 3 (P8, P9) appears only in agi7de/target and the panel. Both cohorts of
a repetition see the same exogenous opportunities."""
from nexus.de_phase6 import seeds6 as S6                   # noqa: F401  (registers Phase 1-6 ranges first)
from nexus import seed_registry as R

RANGES = {("agi7de", "dev"): range(67000, 69000), ("agi7de", "source"): range(69000, 71000),
          ("agi7de", "target"): range(71000, 71200), ("agi7de", "panel"): range(71200, 71300)}
ONE_USE = {("agi7de", "target"), ("agi7de", "panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
COHORTS = ("Full", "FixedLearner")
SOURCE_PARADIGMS = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "X1", "X2")


def block(rep):
    b = RANGES[("agi7de", "source")].start + 1000 * rep
    return dict(train=range(b, b + 600), admit=range(b + 600, b + 800), pool=range(b + 800, b + 900), confirm=range(b + 900, b + 1000))


def pool_specs():
    """Procedure-admission pool: covers multiple document locations, explicit / missing / conflicting / undecided
    requirements, legacy-contract disagreement, benign documents and multi-stage failures, so that 'read one file',
    'always trust old code', 'always ask' and 'always abstain' are each testable shortcuts (coverage of these specified
    conflict types - not a claim of universal conflict coverage)."""
    return [dict(paradigm="P5", engine="sqlite", dp_mode="conflict_approved"), dict(paradigm="P7", engine="duckdb", dp_mode="explicit", legacy_flip=True, fault_p=0.4),
            dict(paradigm="P1", engine="duckdb", dp_mode="undecided"), dict(paradigm="P7", engine="sqlite", dp_mode="missing"),
            dict(paradigm="P2", engine="duckdb"), dict(paradigm="X1"), dict(paradigm="P5", engine="duckdb", dp_mode="explicit"),
            dict(paradigm="P1", engine="sqlite", dp_mode="explicit", legacy_flip=True, fault_p=0.4), dict(paradigm="P3", engine="sqlite"),
            dict(paradigm="X2", dp_mode="conflict_approved")]


def target_manifest():
    T = []
    modes = ["explicit", "missing", "conflict_approved", "undecided", "visible", "explicit", "missing", "conflict_approved"]
    engines = ["sqlite", "duckdb", "spark", "duckdb", "sqlite", "duckdb", "spark", "duckdb"]
    for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        for j in range(8):
            t = dict(paradigm=p, engine=engines[j], names="heldout" if j % 2 else "base", tier=1 if p in ("P1", "P2", "P3") else 2)
            if p in ("P1", "P5", "P7"):
                t["dp_mode"] = modes[j]
                if j == 5:                                           # legacy contradicts the authoritative requirement
                    t.update(legacy_flip=True, fault_p=0.4)
            T.append(t)
    for j in range(8):
        T.append(dict(paradigm="P8", names="heldout" if j % 2 else "base", tier=3, dp_mode=modes[j]))
    for j, h in enumerate("ABCABCAB"):
        T.append(dict(paradigm="P9", hybrid=h, names="heldout" if j % 2 else "base", tier=3, dp_mode=modes[(j + 3) % 8]))
    base = RANGES[("agi7de", "target")].start
    for i, t in enumerate(T):
        t["seed"] = base + i
    return T


def panel_manifest():
    base = RANGES[("agi7de", "panel")].start
    out = []
    for i, p in enumerate([p for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9") for _ in range(2)]):
        t = dict(paradigm=p, tier=1 if p in ("P1", "P2", "P3") else 2 if p not in ("P8", "P9") else 3, seed=base + i)
        if p not in ("P8", "P9"):
            t["engine"] = ("sqlite", "duckdb")[i % 2]
        if p in ("P1", "P5", "P7", "P8", "P9"):
            t["dp_mode"] = ("explicit", "missing")[i % 2]
        out.append(t)
    return out


def frozen_counts():
    """Answerable vs unresolved-intent target counts from the manifest modes (decision points exist only where the
    paradigm has a boundary mechanism; 'undecided' = unresolved intent; every other mode is answerable in principle)."""
    T = target_manifest()
    return dict(total=len(T), undecided=sum(t.get("dp_mode") == "undecided" for t in T), legacy_flip=sum(bool(t.get("legacy_flip")) for t in T),
                with_requirement_modes=sum("dp_mode" in t for t in T))
