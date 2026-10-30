"""Phase 10D partitions, fault-mechanism families and the frozen 48-target manifest (NOT LOCKED).

RANGES (disjoint at import): agi10dde/dev 97000-97999 (Gate 0, rehearsal), agi10dde/train 98000-98999 (repetition r block
98000 + 500 r: wake 0-199, dreams 200-349, admission 350-499), ONE-USE agi10dde/eval 99000-99099 (48 targets).
FAMILIES (fault mechanisms, world10d.MECH_NODE):
  TRAIN  every single mechanism + designated WITHIN-NODE pairs (stg: tombstone+qualify_order, dirty+replay, cdc_key+dirty;
         int: fanout+inner, keycast+fanout; fct: merge_delete+merge_update)
  HELD-OUT COMPOSITIONS (multi-stage, multi-fault DAGs: faults in >= 2 DIFFERENT nodes; no cross-node pair ever occurs in
         training, dreams or admission): C1 tombstone+fanout, C2 replay+keycast, C3 cdc_key+merge_delete, C4 fanout+merge_update,
         C5 qualify_order+inner+merge_delete, C6 dirty+keycast+overwrite, C7 tomb_early+fanout, C8 replay+inner+merge_update
All randomness: rng10c-style numeric tuples (rep, step, task); engines / legacy languages rotate by index, never by name."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase10c import manifest10c as MC                # noqa: F401  (registers Phase 1-10C ranges first)
from nexus.de_phase10c.rng10c import rng

RANGES = {("agi10dde", "dev"): range(97000, 98000), ("agi10dde", "train"): range(98000, 99000), ("agi10dde", "eval"): range(99000, 99100)}
ONE_USE = {("agi10dde", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

MECHS = ("qualify_order", "tombstone", "tomb_early", "cdc_key", "dirty", "replay", "fanout", "inner", "keycast", "asof_dir", "merge_delete", "merge_update", "overwrite")
TRAIN_PAIRS = (("tombstone", "qualify_order"), ("dirty", "replay"), ("cdc_key", "dirty"), ("fanout", "inner"), ("keycast", "fanout"), ("merge_delete", "merge_update"))
TRAIN_FAMILIES = {f"S_{m}": (m,) for m in MECHS} | {f"T_{a}+{b}": (a, b) for a, b in TRAIN_PAIRS}
HELD = {"C1": ("tombstone", "fanout"), "C2": ("replay", "keycast"), "C3": ("cdc_key", "merge_delete"), "C4": ("fanout", "merge_update"),
        "C5": ("qualify_order", "inner", "merge_delete"), "C6": ("dirty", "keycast", "overwrite"), "C7": ("tomb_early", "fanout"),
        "C8": ("replay", "inner", "merge_update")}
ENGINES = ("duckdb", "sqlite", "polars", "spark")
LEGACY = ("snowflake", "postgres", "hive", "dbt", "scala")
CHECKPOINTS = (30, 60, 120)


def train(rep):
    b = RANGES[("agi10dde", "train")].start + 500 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 350), admit=range(b + 350, b + 500))


def train_spec(rep, i, engines=("duckdb", "sqlite", "polars")):
    """Task i of repetition rep: a numeric-seeded shuffle of the training families per cycle (Spark is reserved for evaluation
    and Gate 0 for cost; disclosed)."""
    fams = sorted(TRAIN_FAMILIES)
    c, j = divmod(i, len(fams))
    order = list(fams)
    rng(rep, c, 10).shuffle(order)
    f = order[j]
    return dict(family=f, faults=list(TRAIN_FAMILIES[f]), engine=engines[(i + rep) % len(engines)], legacy=legacy_for(TRAIN_FAMILIES[f], i + 2 * rep), names="base")


def legacy_for(faults, i):
    """Legacy language by index; an as-of fault needs the 5-table workspace, which the Scala lifter cannot express -> Snowflake."""
    lang = LEGACY[i % len(LEGACY)]
    return "snowflake" if lang == "scala" and "asof_dir" in faults else lang


def eval_manifest(base=None):
    """48 one-use targets: 24 ORDINARY (training families, held-out schema names) + 24 HELD-OUT compositions (3 per family);
    engines and legacy languages rotate so every engine and language is represented in both groups."""
    base = RANGES[("agi10dde", "eval")].start if base is None else base
    fams = sorted(TRAIN_FAMILIES)
    ordinary = [dict(family=fams[(5 * i) % len(fams)], faults=list(TRAIN_FAMILIES[fams[(5 * i) % len(fams)]]), group="ordinary") for i in range(24)]
    held = [dict(family=h, faults=list(HELD[h]), group="heldout") for h in sorted(HELD) for _ in range(3)]
    out = []
    for i, t in enumerate(ordinary + held):
        out.append(dict(t, engine=ENGINES[i % 4], legacy=legacy_for(t["faults"], i), names="heldout", seed=base + i))
    return out


def dev_manifest(offset=900):
    return eval_manifest(base=RANGES[("agi10dde", "dev")].start + offset)


def leakage(reps=(0, 1)):
    from nexus.de_phase10d import world10d as W
    held_pairs = {frozenset((a, b)) for fs in HELD.values() for i, a in enumerate(fs) for b in fs[i + 1:]}
    bad, n = [], 0
    for rep in reps:
        for kind, seeds in train(rep).items():
            for i in range(len(seeds)):
                sp = train_spec(rep, i)
                n += 1
                fs = sp["faults"]
                pairs = {frozenset((a, b)) for k, a in enumerate(fs) for b in fs[k + 1:]}
                if sp["family"] in HELD or pairs & held_pairs or len({W.MECH_NODE[f] for f in fs}) > 1:
                    bad.append((rep, kind, i, sp["family"]))
    return dict(specs_checked=n, violations=bad)
