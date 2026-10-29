"""Phase 4 seed ranges, curriculum cells and frozen target manifests (NOT LOCKED). Fresh ranges 53600-56399, above every
registered range (checked at import by seed_registry._check_disjoint).
  agi4de/dev          53600-54099  Stage 1 development (adapter / gate / calibration / operating-cycle trace)
  agi4de/source       54100-55599  Stage 2 source learning: repetition r uses 54100 + 500 r +   0..249 (learning stream)
                                                                                         + 250..349 (skill admission)
                                                                                         + 350..499 (meta-rollout learning + rollout evaluation)
  agi4de/source_meta  55600-56099  Stage 3 improver-clone trajectories: 55600 + 150 r + 0..99 learning, + 100..149 admission
  agi4de/placebo      56300-56399  placebo RNG keys
  ONE-USE: agi4de/eval 56100-56199 (the 24 Stage 4 targets), agi4de/panel 56200-56299 (the 12-project improver panel)
Untouched mechanism families F7 (normalize) and F8 (tombstone) appear ONLY in agi4de/eval targets."""
from nexus.campaign3 import seeds as S3                    # noqa: F401  (registers Phase 1-3 ranges first)
from nexus import seed_registry as R
from nexus.de_phase4.world import SOURCE_FAMS, UNTOUCHED_FAMS

RANGES = {("agi4de", "dev"): range(53600, 54100), ("agi4de", "source"): range(54100, 55600),
          ("agi4de", "source_meta"): range(55600, 56100), ("agi4de", "eval"): range(56100, 56200),
          ("agi4de", "panel"): range(56200, 56300), ("agi4de", "placebo"): range(56300, 56400)}
ONE_USE = {("agi4de", "eval"), ("agi4de", "panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

EVAL_SOURCE_FAMS = ("F1", "F3", "F4", "F6")       # new instances of 4 source mechanisms
EVAL_FAMS = EVAL_SOURCE_FAMS + UNTOUCHED_FAMS
CELLS = [(f, k, rt) for f in SOURCE_FAMS for k in (1, 2, 3, 4) for rt in ("sqlite", "spark")]


def src_block(rep):
    b = RANGES[("agi4de", "source")].start + 500 * rep
    return dict(learn=range(b, b + 250), admit=range(b + 250, b + 350), roll=range(b + 350, b + 500))


def meta_block(rep):
    b = RANGES[("agi4de", "source_meta")].start + 150 * rep
    return dict(learn=range(b, b + 100), admit=range(b + 100, b + 150))


def eval_manifest():
    """The 24 frozen Stage 4 targets: 6 families x (SQLite k=1, SQLite k=3, Spark k=1, Spark k=3); seeds 56100.."""
    base, out = RANGES[("agi4de", "eval")].start, []
    for i, fam in enumerate(EVAL_FAMS):
        for j, (rt, k) in enumerate((("sqlite", 1), ("sqlite", 3), ("spark", 1), ("spark", 3))):
            out.append(dict(family=fam, k=k, runtime=rt, seed=base + 4 * i + j,
                            panel="de_untouched" if fam in UNTOUCHED_FAMS else "de_instance"))
    return out


def panel_manifest():
    """The 12-project improver panel: the 6 source mechanisms x (SQLite k=2, Spark k=2); seeds 56200.."""
    base, out = RANGES[("agi4de", "panel")].start, []
    for i, fam in enumerate(SOURCE_FAMS):
        for j, rt in enumerate(("sqlite", "spark")):
            out.append(dict(family=fam, k=2, runtime=rt, seed=base + 2 * i + j, panel="improver_panel"))
    return out
