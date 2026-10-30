"""Phase 11 seed namespaces and frozen manifests (NOT LOCKED). Ranges registered disjoint at import:
  agi11/dev      110000-110999   development fixtures, conformance, timing (never a target)
  agi11/sourceA  111000-111999   Stage A source learning: stream r tasks 111000 + 500 r + i (i < 60), validation / evidence inside each task
  agi11/stageB   112000-112999   Stage B transfer training: stream r tasks 112000 + 500 r + i (i < 80)
  agi11/suite1   113000-113099   ONE-USE: Suite 1, 24 withheld compositions (W1-W8 x 3, held-out name pool)
Suite 2 = the existing 16 Phase 10C / 10E external DEVELOPMENT tasks (scripts/agi10c_external.py TASKS); Suite 3 = External_Holdout_24:
NOT READY (artifacts/agi11_suite3_provenance.json). Families are drawn by index with numeric rng10c seeds; family names never reach
the learner (tasks carry anonymous ids)."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase10g import manifest10g as MG               # noqa: F401  (registers Phase 1-10G ranges first)
from nexus.de_phase10c.rng10c import rng
from nexus.de_phase11 import tasks11 as T

RANGES = {("agi11", "dev"): range(110000, 111000), ("agi11", "sourceA"): range(111000, 112000), ("agi11", "stageB"): range(112000, 113000),
          ("agi11", "suite1"): range(113000, 113100)}
ONE_USE = {("agi11", "suite1")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
N_A, N_B = 60, 80


def source_stream(rep):
    """60 Stage A tasks: the 8 source families in a numeric-seeded shuffled cycle (7-8 tasks per family)."""
    b = RANGES[("agi11", "sourceA")].start + 500 * rep
    out = []
    for c in range(0, N_A, len(T.SOURCE)):
        fams = list(T.SOURCE)
        rng(rep, c, 21).shuffle(fams)
        out += fams
    return [(f, b + i) for i, f in enumerate(out[:N_A])]


def stageB_stream(rep):
    b = RANGES[("agi11", "stageB")].start + 500 * rep
    out = []
    for c in range(0, N_B, len(T.COMPOSE)):
        fams = list(T.COMPOSE)
        rng(rep, c, 22).shuffle(fams)
        out += fams
    return [(f, b + i) for i, f in enumerate(out[:N_B])]


def suite1():
    """24 one-use withheld compositions (W1-W8 x 3), held-out name pool, interleaved order."""
    b = RANGES[("agi11", "suite1")].start
    return [dict(kind=w, seed=b + 8 * j + i, pool="heldout") for j in range(3) for i, w in enumerate(T.WITHHELD)]


def dev_tasks(n_each=2, base=None):
    b = base or RANGES[("agi11", "dev")].start
    kinds = list(T.SOURCE) + list(T.COMPOSE) + list(T.WITHHELD)
    return [(k, b + 10 * i + j) for i, k in enumerate(kinds) for j in range(n_each)]
