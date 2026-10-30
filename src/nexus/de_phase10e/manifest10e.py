"""Phase 10E partitions, families and the frozen 48-target manifest (NOT LOCKED).

RANGES (disjoint at import): agi10ede/dev 100000-100999 (design checks), agi10ede/train 101000-101999 (repetition r block
101000 + 500 r: wake 0-199, dreams 200-349, admission 350-499), ONE-USE agi10ede/eval 102000-102099 (48 targets, a FRESH draw;
the Phase 10D one-use range 99000-99099 is never reused).
FAMILIES (Phase 10D fault mechanisms, world10d.MECH_NODE):
  TRAIN  every single mechanism (incl. S_replay) + the Phase 10D within-node pairs EXCEPT dirty+replay: replay is seen in
         training, dreams and admission ONLY as a single-mechanism source task
  HELD-OUT REPLAY COMPOSITIONS (every one contains replay plus faults in at least one OTHER node; none occurs in training, dreams
         or admission): R1 replay+fanout, R2 replay+keycast, R3 replay+merge_update, R4 replay+merge_delete,
         R5 replay+fanout+merge_update, R6 replay+keycast+merge_delete, R7 replay+inner+merge_update, R8 replay+dirty+keycast
All randomness: rng10c numeric tuples (rep, step, task); engines / legacy languages rotate by index, never by name."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase10d import manifest10d as MDD               # noqa: F401  (registers Phase 1-10D ranges first)
from nexus.de_phase10c.rng10c import rng

RANGES = {("agi10ede", "dev"): range(100000, 101000), ("agi10ede", "train"): range(101000, 102000), ("agi10ede", "eval"): range(102000, 102100)}
ONE_USE = {("agi10ede", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

MECHS = MDD.MECHS
TRAIN_PAIRS = tuple(p for p in MDD.TRAIN_PAIRS if "replay" not in p)
TRAIN_FAMILIES = {f"S_{m}": (m,) for m in MECHS} | {f"T_{a}+{b}": (a, b) for a, b in TRAIN_PAIRS}
HELD = {"R1": ("replay", "fanout"), "R2": ("replay", "keycast"), "R3": ("replay", "merge_update"), "R4": ("replay", "merge_delete"),
        "R5": ("replay", "fanout", "merge_update"), "R6": ("replay", "keycast", "merge_delete"), "R7": ("replay", "inner", "merge_update"),
        "R8": ("replay", "dirty", "keycast")}
ENGINES, LEGACY, legacy_for = MDD.ENGINES, MDD.LEGACY, MDD.legacy_for
CHECKPOINTS = (30, 60, 120)


def train(rep):
    b = RANGES[("agi10ede", "train")].start + 500 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 350), admit=range(b + 350, b + 500))


def train_spec(rep, i, engines=("duckdb", "sqlite", "polars")):
    """Task i of repetition rep: a numeric-seeded shuffle of the training families per cycle (Spark is reserved for evaluation
    for cost, as in Phase 10D)."""
    fams = sorted(TRAIN_FAMILIES)
    c, j = divmod(i, len(fams))
    order = list(fams)
    rng(rep, c, 11).shuffle(order)
    f = order[j]
    return dict(family=f, faults=list(TRAIN_FAMILIES[f]), engine=engines[(i + rep) % len(engines)], legacy=legacy_for(TRAIN_FAMILIES[f], i + 2 * rep), names="base")


def eval_manifest(base=None):
    """48 one-use targets: 24 ORDINARY (training families, held-out schema names) + 24 HELD-OUT replay compositions (3 per
    family); engines and legacy languages rotate so every engine and language is represented in both groups."""
    base = RANGES[("agi10ede", "eval")].start if base is None else base
    fams = sorted(TRAIN_FAMILIES)
    ordinary = [dict(family=fams[(5 * i) % len(fams)], faults=list(TRAIN_FAMILIES[fams[(5 * i) % len(fams)]]), group="ordinary") for i in range(24)]
    held = [dict(family=h, faults=list(HELD[h]), group="heldout") for h in sorted(HELD) for _ in range(3)]
    return [dict(t, engine=ENGINES[i % 4], legacy=legacy_for(t["faults"], i), names="heldout", seed=base + i) for i, t in enumerate(ordinary + held)]


def dev_manifest(offset=900):
    return eval_manifest(base=RANGES[("agi10ede", "dev")].start + offset)


def leakage(reps=(0, 1)):
    """No training / dream / admission spec is a held-out family, contains a held-out fault pair, spans two nodes, or combines
    replay with any other fault."""
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
                if sp["family"] in HELD or pairs & held_pairs or len({W.MECH_NODE[f] for f in fs}) > 1 or ("replay" in fs and len(fs) > 1):
                    bad.append((rep, kind, i, sp["family"]))
    return dict(specs_checked=n, violations=bad)
