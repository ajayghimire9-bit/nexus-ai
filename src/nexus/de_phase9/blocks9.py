"""Phase 9 partitions, evidence-stratified blocks and balanced streams (NOT LOCKED; human evaluation infrastructure).

Ranges (disjoint at import): agi9de/dev 77000-78999 (development + sensitivity controls), agi9de/source 79000-79999
(parent p block 79000 + 500 p: screen pool 0-19, Stage 2 stream 20-79, selection block 80-139, Stage 3 stream 140-199,
method admission 200-499), ONE-USE agi9de/confirm 80000-80099 (18 used). Every earlier project - including all Phase 6/7/8
targets - is development data.

STRATA (3 projects each, 18 per block): the evidence conditions a procedure can change and the future value of acquired
knowledge can depend on. 'benign' projects have no documented boundary (reading is wasted work there); 'multi' are
composites / all-faults pipelines whose repair needs several steps. Half the projects use held-out names (a changed schema
interface). No stratum makes 'read everything' or 'trust one label' a planted winner: conflicts resolve only through
provenance that must be EARNED (trust records) or one question; undecided intent must not be submitted; benign projects
penalise investigation cost. Source-reliability changes are not supported by the generator (recorded, not simulated).

BALANCED STREAM: each cycle contains one project of each of P1-P7, X1, X2 in a frozen shuffled order; P1 / P5 / P7 rotate
the requirement condition (explicit, conflict, missing, undecided, legacy disagreement) and P1-P7 rotate engines."""
from __future__ import annotations

import random

from nexus import seed_registry as R
from nexus.de_phase8 import seeds8 as S8                   # noqa: F401  (registers Phase 1-8 ranges first)

RANGES = {("agi9de", "dev"): range(77000, 79000), ("agi9de", "source"): range(79000, 80000), ("agi9de", "confirm"): range(80000, 80100)}
ONE_USE = {("agi9de", "confirm")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

LF = dict(dp_mode="explicit", legacy_flip=True, fault_p=0.4)
STRATA = {
    "conflict": [dict(paradigm="P5", engine="sqlite", dp_mode="conflict_approved"), dict(paradigm="P7", engine="duckdb", dp_mode="conflict_approved"),
                 dict(paradigm="P1", engine="duckdb", dp_mode="conflict_approved")],
    "missing": [dict(paradigm="P1", engine="sqlite", dp_mode="missing"), dict(paradigm="P5", engine="duckdb", dp_mode="missing"),
                dict(paradigm="P7", engine="sqlite", dp_mode="missing")],
    "legacy_disagreement": [dict(paradigm="P7", engine="duckdb", **LF), dict(paradigm="P1", engine="sqlite", **LF), dict(paradigm="P5", engine="sqlite", **LF)],
    "undecided": [dict(paradigm="P1", engine="duckdb", dp_mode="undecided"), dict(paradigm="P5", engine="sqlite", dp_mode="undecided"),
                  dict(paradigm="P7", engine="duckdb", dp_mode="undecided")],
    "benign": [dict(paradigm="P2", engine="duckdb"), dict(paradigm="P3", engine="sqlite"), dict(paradigm="P6", engine="duckdb")],
    "multi": [dict(paradigm="X1"), dict(paradigm="X2"), dict(paradigm="P4", engine="duckdb", fault_p=1.0)],
}
FAMILIES = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "X1", "X2")
CONDITIONS = ("explicit", "conflict_approved", "missing", "undecided", "legacy")
ENGINES = ("sqlite", "duckdb", "spark")


def block_specs(seeds):
    """18 (stratum, spec, seed) - 3 per stratum, alternating base / held-out names."""
    out, i = [], 0
    for name, specs in STRATA.items():
        for sp in specs:
            out.append((name, dict(sp, names="heldout" if i % 2 else "base"), seeds[i]))
            i += 1
    return out


def balanced_stream(seeds, n_cycles, key):
    rng = random.Random(f"agi9-stream|{key}")
    out, i = [], 0
    for c in range(n_cycles):
        fams = list(FAMILIES)
        rng.shuffle(fams)
        for f in fams:
            sp = dict(paradigm=f)
            if f.startswith("P"):
                sp["engine"] = ENGINES[(c + FAMILIES.index(f)) % 3]
            if f in ("P1", "P5", "P7"):
                cond = CONDITIONS[(c + FAMILIES.index(f)) % len(CONDITIONS)]
                sp.update(LF if cond == "legacy" else dict(dp_mode=cond))
            out.append((c, sp, seeds[i]))
            i += 1
    return out


def parent_block(p):
    b = RANGES[("agi9de", "source")].start + 500 * p
    return dict(pool=range(b, b + 20), stream2=range(b + 20, b + 80), select=range(b + 80, b + 140), stream3=range(b + 140, b + 200),
                admit=range(b + 200, b + 500))


def confirm_manifest():
    seeds = list(RANGES[("agi9de", "confirm")])[:18]
    return [dict(stratum=s, spec=sp, seed=sd, family=sp["paradigm"], answerable=s != "undecided") for s, sp, sd in block_specs(seeds)]
