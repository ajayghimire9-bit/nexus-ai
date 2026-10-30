"""Phase 10C partitions, composition families and the frozen 48-target manifest (NOT LOCKED).

RANGES (disjoint at import): agi10cde/dev 91000-91999, agi10cde/train 92000-95999 (repetition r block 92000 + 2000 r: wake
0-199, dreams 200-599, admission 600-999), ONE-USE agi10cde/eval 96000-96099 (48 targets). Every earlier project, incl. all
Phase 10 / 10B targets, is development data.
FAMILIES. A family is the ORDERED tuple of stage paradigms of a pipeline (world6 stages, each with its own fault mechanisms).
  TRAIN  single-stage P1-P7 and the two training pairs X1 = (P3, P2), X2 = (P7, P6)
  HELD-OUT COMPOSITIONS (registered here as world6 composites; never generated for wake, dreams or admission):
    H1 (P2, P1)  H2 (P3, P7)  H3 (P5, P6)  H4 (P1, P4)  H5 (P1, P3, P6)  H6 (P5, P4, P7)
  No unordered paradigm pair of a held-out family occurs in any training family ({P2,P3} and {P6,P7} are the only training
  pairs); manifest10c.leakage() checks this over every training seed of both repetitions.
STREAM. Each training cycle is a numeric-seeded shuffle of the nine training families (rng10c.rng(rep, cycle, 0)); P1 / P5 /
P7 rotate the requirement condition; engines rotate SQLite / DuckDB (Spark is excluded from Phase 10C training and evaluation
for cost; disclosed). All 48 targets use held-out schema names and documented ('explicit') requirements, so the comparison
isolates repair search (trust, procedure and question policy are identical in every arm)."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase6 import world6 as W6
from nexus.de_phase9 import blocks9 as B9
from nexus.de_phase10b import manifest10b as MB             # noqa: F401  (registers Phase 1-10B ranges first)
from nexus.de_phase10c.rng10c import rng

RANGES = {("agi10cde", "dev"): range(91000, 92000), ("agi10cde", "train"): range(92000, 96000), ("agi10cde", "eval"): range(96000, 96100)}
ONE_USE = {("agi10cde", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

TRAIN_FAMILIES = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "X1", "X2")
HELD = {"H1": [("P2", "sqlite"), ("P1", "duckdb")], "H2": [("P3", "sqlite"), ("P7", "duckdb")], "H3": [("P5", "duckdb"), ("P6", "sqlite")],
        "H4": [("P1", "duckdb"), ("P4", "sqlite")], "H5": [("P1", "sqlite"), ("P3", "duckdb"), ("P6", "sqlite")],
        "H6": [("P5", "duckdb"), ("P4", "duckdb"), ("P7", "sqlite")]}
for _k, _v in HELD.items():
    W6.COMPOSITES.setdefault(_k, _v)
    W6.TIER.setdefault(_k, 3)
CHECKPOINTS = (15, 30, 60)                                  # revised Phase 10C budget: N0 = 0, N1 = 15, N2 = 30, N3 = 60 (or tasks reached)
MECHS = {p: tuple(v["mech"]) for p, v in W6.PARADIGMS.items()}
TRAIN_MECH_PAIRS = sorted({tuple(sorted((a, b))) for f in TRAIN_FAMILIES for m in [sorted({x for st in [f] for p in (
    [q for q, _ in W6.COMPOSITES[f]] if f in W6.COMPOSITES else [f]) for x in MECHS[p]})] for i, a in enumerate(m) for b in m[i + 1:]})
ENGINES = ("sqlite", "duckdb")


def stages_of(paradigm):
    return [p for p, _ in W6.COMPOSITES[paradigm]] if paradigm in W6.COMPOSITES else [paradigm]


def train(rep):
    b = RANGES[("agi10cde", "train")].start + 2000 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 600), admit=range(b + 600, b + 1000))


def train_spec(rep, i):
    """Task i of repetition rep's balanced training stream (numeric seeding only)."""
    c, j = divmod(i, len(TRAIN_FAMILIES))
    fams = list(TRAIN_FAMILIES)
    rng(rep, c, 0).shuffle(fams)
    f = fams[j]
    sp = dict(paradigm=f, names="base")
    if f.startswith("P"):
        sp["engine"] = ENGINES[(c + TRAIN_FAMILIES.index(f)) % 2]
    if f in ("P1", "P5", "P7"):
        cond = B9.CONDITIONS[(c + TRAIN_FAMILIES.index(f)) % len(B9.CONDITIONS)]
        sp.update(B9.LF if cond == "legacy" else dict(dp_mode=cond))
    return sp


def eval_manifest(base=None):
    """48 targets: 24 ORDINARY (training families on held-out-name repositories) + 24 HELD-OUT compositions (4 per family)."""
    base = RANGES[("agi10cde", "eval")].start if base is None else base
    ordinary = [dict(paradigm=p, engine=ENGINES[j]) for p in TRAIN_FAMILIES[:7] for j in range(2)]
    ordinary += [dict(paradigm="X1") for _ in range(5)] + [dict(paradigm="X2") for _ in range(5)]
    held = [dict(paradigm=h) for h in HELD for _ in range(4)]
    out = []
    for i, t in enumerate([dict(t, group="ordinary") for t in ordinary] + [dict(t, group="heldout") for t in held]):
        out.append(dict(t, names="heldout", dp_mode="explicit", seed=base + i, family=t["paradigm"]))
    return out


def dev_manifest(n_per=1, offset=900):
    """Development targets with the evaluation structure (agi10cde/dev; never evaluation data)."""
    return eval_manifest(base=RANGES[("agi10cde", "dev")].start + offset)


DRAW_ORDINARY = [dict(paradigm="P1", engine="sqlite"), dict(paradigm="P2", engine="duckdb"), dict(paradigm="P5", engine="sqlite"),
                 dict(paradigm="P7", engine="duckdb"), dict(paradigm="X1"), dict(paradigm="X2")]
DRAW_WITHHELD = ["H1", "H2", "H3", "H4", "H1", "H2", "H3", "H4", "H5", "H6"]
DRAWS = {"A": 96000, "B": 96050}


def draw_manifest(draw, base=None):
    """REVISED Phase 10C: one of two SEPARATE one-use target draws (A: 96000-96015, B: 96050-96065): 6 ordinary repairs
    (training families, held-out-name repositories) + 10 deliberately withheld compositions. Stream r is evaluated on draw
    ('A', 'B')[r]; the shared fixed arm A1 runs on both."""
    base = DRAWS[draw] if base is None else base
    ts = [dict(t, group="ordinary") for t in DRAW_ORDINARY] + [dict(paradigm=h, group="heldout") for h in DRAW_WITHHELD]
    return [dict(t, names="heldout", dp_mode="explicit", seed=base + i, family=t["paradigm"], draw=draw) for i, t in enumerate(ts)]


def dev_draw(draw):
    return draw_manifest(draw, base=RANGES[("agi10cde", "dev")].start + (900 if draw == "A" else 950))


def withheld_pairs(stage_faults):
    """Fault-mechanism pairs (F_i, F_j) of a built project that co-occur in NO training family (F_i, F_j each occur in training)."""
    allf = sorted({(k, f) for k, fs in enumerate(stage_faults) for f in fs})
    return sorted({tuple(sorted((a[1], b[1]))) for i, a in enumerate(allf) for b in allf[i + 1:] if a[1] != b[1]} - set(TRAIN_MECH_PAIRS))


def leakage(reps=(0, 1)):
    """Every training / dream / admission spec of both repetitions: family must be a training family and no held-out paradigm
    pair may co-occur in it. Returns the violations (expected: [])."""
    held_pairs = {frozenset((a, b)) for h in HELD for i, a in enumerate(stages_of(h)) for b in stages_of(h)[i + 1:]}
    bad, n = [], 0
    for rep in reps:
        T = train(rep)
        for kind, seeds in T.items():
            for i in range(len(seeds)):
                sp = train_spec(rep, i)
                n += 1
                st = stages_of(sp["paradigm"])
                pairs = {frozenset((a, b)) for j, a in enumerate(st) for b in st[j + 1:]}
                if sp["paradigm"] not in TRAIN_FAMILIES or sp["paradigm"] in HELD or pairs & held_pairs:
                    bad.append((rep, kind, i, sp["paradigm"]))
    return dict(specs_checked=n, violations=bad, held_pairs=sorted(sorted(p) for p in held_pairs))
