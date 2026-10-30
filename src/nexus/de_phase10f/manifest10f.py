"""Phase 10F partitions and the frozen 48-target manifest (NOT LOCKED).

RANGES (disjoint at import): agi10fde/dev 103000-103999 (design checks), agi10fde/train 104000-104999 (repetition r block
104000 + 500 r: wake 0-199, dreams 200-349, admission 350-499), ONE-USE agi10fde/eval 105000-105099 (48 targets, a FRESH draw;
the Phase 10D / 10E one-use ranges 99000-99099 / 102000-102099 are never reused).
FAMILIES: exactly Phase 10E's (manifest10e): training = every single mechanism (incl. S_replay) + the within-node pairs except
dirty+replay; HELD-OUT = the 8 replay compositions R1-R8 (3 targets each), none in training, dreams or admission.
Projects come from world10f (quantity independent of the arrival sequence). Training stops at N = 100 with checkpoints at 50 and
100 (acquisition / retention are read at both). All randomness: rng10c numeric tuples (rep, step, task)."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase10e import manifest10e as ME               # noqa: F401  (registers Phase 1-10E ranges first)
from nexus.de_phase10c.rng10c import rng

RANGES = {("agi10fde", "dev"): range(103000, 104000), ("agi10fde", "train"): range(104000, 105000), ("agi10fde", "eval"): range(105000, 105100)}
ONE_USE = {("agi10fde", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

MECHS, TRAIN_PAIRS, TRAIN_FAMILIES, HELD = ME.MECHS, ME.TRAIN_PAIRS, ME.TRAIN_FAMILIES, ME.HELD
ENGINES, LEGACY, legacy_for = ME.ENGINES, ME.LEGACY, ME.legacy_for
N_MAX, CHECKPOINTS = 100, (50, 100)


def train(rep):
    b = RANGES[("agi10fde", "train")].start + 500 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 350), admit=range(b + 350, b + 500))


def train_spec(rep, i, engines=("duckdb", "sqlite", "polars")):
    """manifest10e.train_spec (same numeric-seeded family shuffle per cycle; Spark reserved for evaluation)."""
    fams = sorted(TRAIN_FAMILIES)
    c, j = divmod(i, len(fams))
    order = list(fams)
    rng(rep, c, 11).shuffle(order)
    f = order[j]
    return dict(family=f, faults=list(TRAIN_FAMILIES[f]), engine=engines[(i + rep) % len(engines)], legacy=legacy_for(TRAIN_FAMILIES[f], i + 2 * rep), names="base")


def eval_manifest(base=None):
    """manifest10e.eval_manifest on the fresh one-use range: 24 ORDINARY (training families, held-out schema names) + 24 HELD-OUT
    replay compositions (3 per family); engines and legacy languages rotate."""
    base = RANGES[("agi10fde", "eval")].start if base is None else base
    return ME.eval_manifest(base=base)


def dev_manifest(offset=900):
    return eval_manifest(base=RANGES[("agi10fde", "dev")].start + offset)


def leakage(reps=(0, 1)):
    return ME.leakage(reps)              # the family stream is manifest10e's (seeds differ only), so the 10E leakage audit applies
