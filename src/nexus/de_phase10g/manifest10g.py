"""Phase 10G partitions and the frozen 48-target manifest (NOT LOCKED).

RANGES (disjoint at import): agi10gde/dev 106000-106999, agi10gde/train 107000-107999 (repetition r block 107000 + 500 r: wake 0-199,
dreams 200-349, admission 350-499), ONE-USE agi10gde/eval 108000-108099 (48 targets, a FRESH draw).
TRAINING  manifest10e's family stream (single mechanisms + within-node pairs, replay only as S_replay), N = 120 per stream; a family
          holding the fault a mechanism needs gets that designed ambiguity with probability 0.75 (rng10c (rep, i, 13)):
          replay -> seq, qualify_order -> time, fanout -> grain.
WITHHELD COMPOSITIONS (24 = 8 cross-node families x 3; none occurs in training, dreams or admission):
          W1 replay+fanout / seq     W2 replay+keycast / seq      W3 qualify_order+fanout / time    W4 qualify_order+merge_update / time
          W5 fanout+merge_delete / grain   W6 fanout+merge_update / grain   W7 replay+merge_update / none   W8 qualify_order+inner / none
ORDINARY  (24, training families, held-out schema names): 6 S_replay / seq, 3 S_qualify_order + 3 T_tombstone+qualify_order / time,
          2 S_fanout + 2 T_fanout+inner + 2 T_keycast+fanout / grain, 6 without a designed ambiguity.
Engines and legacy languages rotate by index. All randomness: rng10c numeric tuples."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase10f import manifest10f as MF               # noqa: F401  (registers Phase 1-10F ranges first)
from nexus.de_phase10e import manifest10e as ME
from nexus.de_phase10c.rng10c import rng

RANGES = {("agi10gde", "dev"): range(106000, 107000), ("agi10gde", "train"): range(107000, 108000), ("agi10gde", "eval"): range(108000, 108100)}
ONE_USE = {("agi10gde", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

TRAIN_FAMILIES, ENGINES, LEGACY, legacy_for = ME.TRAIN_FAMILIES, ME.ENGINES, ME.LEGACY, ME.legacy_for
AMB_FOR = (("replay", "seq"), ("qualify_order", "time"), ("fanout", "grain"))
P_AMB, N_MAX, CHECKPOINTS = 0.75, 120, (60, 120)
WITHHELD = {"W1": (("replay", "fanout"), "seq"), "W2": (("replay", "keycast"), "seq"), "W3": (("qualify_order", "fanout"), "time"),
            "W4": (("qualify_order", "merge_update"), "time"), "W5": (("fanout", "merge_delete"), "grain"), "W6": (("fanout", "merge_update"), "grain"),
            "W7": (("replay", "merge_update"), None), "W8": (("qualify_order", "inner"), None)}
ORDINARY = [("S_replay", "seq")] * 6 + [("S_qualify_order", "time")] * 3 + [("T_tombstone+qualify_order", "time")] * 3 + \
           [("S_fanout", "grain")] * 2 + [("T_fanout+inner", "grain")] * 2 + [("T_keycast+fanout", "grain")] * 2 + \
           [(f, None) for f in ("S_dirty", "S_cdc_key", "S_merge_delete", "S_tombstone", "S_asof_dir", "T_merge_delete+merge_update")]


def train(rep):
    b = RANGES[("agi10gde", "train")].start + 500 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 350), admit=range(b + 350, b + 500))


def train_spec(rep, i):
    s = ME.train_spec(rep, i)
    amb = next((a for f, a in AMB_FOR if f in s["faults"]), None)
    return dict(s, amb=amb if amb and rng(rep, i, 13).random() < P_AMB else None)


def eval_manifest(base=None):
    base = RANGES[("agi10gde", "eval")].start if base is None else base
    ordinary = [dict(family=f, faults=list(TRAIN_FAMILIES[f]), amb=a, group="ordinary") for f, a in ORDINARY]
    held = [dict(family=w, faults=list(WITHHELD[w][0]), amb=WITHHELD[w][1], group="heldout") for w in sorted(WITHHELD) for _ in range(3)]
    return [dict(t, engine=ENGINES[i % 4], legacy=legacy_for(t["faults"], i), names="heldout", seed=base + i) for i, t in enumerate(ordinary + held)]


def dev_manifest(offset=900):
    return eval_manifest(base=RANGES[("agi10gde", "dev")].start + offset)


def leakage(reps=(0, 1)):
    """No training / dream / admission spec is a withheld fault combination (training families are single-node)."""
    held = {frozenset(f) for f, _ in WITHHELD.values()}
    bad, n = [], 0
    for rep in reps:
        for kind, seeds in train(rep).items():
            for i in range(len(seeds)):
                sp = train_spec(rep, i)
                n += 1
                if frozenset(sp["faults"]) in held or sp["family"] in WITHHELD:
                    bad.append((rep, kind, i, sp["family"]))
    return dict(specs_checked=n, violations=bad, base=ME.leakage(reps)["violations"])
