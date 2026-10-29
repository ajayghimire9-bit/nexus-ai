"""Multi-world campaign seed ranges, family splits, role partners and the pre-committed evaluation panels (NOT LOCKED).

Seed ranges are fresh: above every registered range (max registered stop 30000 = mi3/winner_eval) and above every spent
seed (max 29999); disjointness is checked at import by seed_registry._check_disjoint. The four target panels are ONE-USE
and are claimed whole by the frozen evaluation runner on first use.

Family split (source worlds A, B, D, F): a seeded permutation per world, random.Random(f"agi-split-{world}"), fixed here
before any experiment: positions 0-1 = source learning, 2 = development / source-admission, 3 = withheld target family.
Worlds C and E are wholly held out: none of their 8 families is used for learning, development or admission.

Partners (which mechanisms a composed task may contain), by role:
  source / retention   target = a learning family; partners = learning families only (same world; other source worlds)
  admission            target = the admission family; partners = learning families
  withheld             target = the withheld family; partners = learning families
  heldout (C, E)       target = a C / E family; same-world partners = that held-out world's families; cross = learning
So no source or admission task ever contains a withheld-family or a C / E mechanism."""
import random

from nexus import mi3_seeds  # noqa: F401  (registers every earlier range first)
from nexus import seed_registry as R
from nexus.campaign.worlds import FAMILIES, SOURCE_WORLDS, HELDOUT_WORLDS

RANGES = {("agi", "dev"): range(30000, 31000), ("agi", "source"): range(31000, 34000),
          ("agi", "admission"): range(34000, 35000), ("agi", "source_meta"): range(35000, 36000),
          ("agi", "eval_withheld"): range(36000, 36100), ("agi", "eval_heldout"): range(36100, 36300),
          ("agi", "eval_retention"): range(36300, 36400), ("agi", "improver_panel"): range(36400, 36500),
          ("agi", "placebo"): range(36500, 36600)}
ONE_USE = {("agi", "eval_withheld"), ("agi", "eval_heldout"), ("agi", "eval_retention"), ("agi", "improver_panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()


def split():
    out = {}
    for w in SOURCE_WORLDS:
        fams = list(FAMILIES[w])
        random.Random(f"agi-split-{w}").shuffle(fams)
        out[w] = dict(learn=tuple(sorted(fams[:2])), admit=fams[2], withheld=fams[3])
    return out


SPLIT = split()
LEARN = [(w, f) for w in SOURCE_WORLDS for f in SPLIT[w]["learn"]]
ADMIT = [(w, SPLIT[w]["admit"]) for w in SOURCE_WORLDS]
WITHHELD = [(w, SPLIT[w]["withheld"]) for w in SOURCE_WORLDS]
HELDOUT = [(w, f) for w in HELDOUT_WORLDS for f in FAMILIES[w]]


def partners_for(world, family, role):
    if world in HELDOUT_WORLDS:
        same = list(FAMILIES[world])
    else:
        same = list(SPLIT[world]["learn"])
    cross = [(w, f) for (w, f) in LEARN if w != world]
    return dict(same=same, cross=cross)


def role_of(world, family):
    if world in HELDOUT_WORLDS:
        return "heldout"
    s = SPLIT[world]
    return "learn" if family in s["learn"] else "admit" if family == s["admit"] else "withheld"


def _latin(fams, start):
    """16 (family, level) cells ordered so every prefix of 4 covers the 4 families at 4 different levels."""
    return [(fams[k % 4], (k // 4 + k % 4) % 4 + 1, start + k) for k in range(16)]


def panels():
    """The pre-committed target panels: lists of (world, family, level, seed, panel)."""
    wh = []
    for i, (w, f) in enumerate(WITHHELD):
        for j in range(4):
            wh.append((w, f, (i + j) % 4 + 1, RANGES[("agi", "eval_withheld")].start + 4 * i + j, "withheld"))
    ho = []
    for i, w in enumerate(HELDOUT_WORLDS):
        ho += [(w, f, lv, s, "heldout") for f, lv, s in _latin(list(FAMILIES[w]), RANGES[("agi", "eval_heldout")].start + 16 * i)]
    ret = []
    for i, (w, f) in enumerate(LEARN):
        ret.append((w, f, i % 4 + 1, RANGES[("agi", "eval_retention")].start + i, "retention"))
    pan = []
    k = 0
    for w in SOURCE_WORLDS + HELDOUT_WORLDS:
        fams = ([SPLIT[w]["learn"][0], SPLIT[w]["withheld"]] if w in SOURCE_WORLDS else list(FAMILIES[w])[:2])
        for f in fams:
            pan.append((w, f, k % 4 + 1, RANGES[("agi", "improver_panel")].start + k, "improver_panel"))
            k += 1
    return dict(withheld=wh, heldout=ho, retention=ret, improver_panel=pan)


def reduced(n_main):
    """Balanced reductions of the 56-task main suite (16 withheld + 32 held-out + 8 retention), all 6 worlds kept:
    56 = everything; 36 = 8 withheld (2 per source world) + 20 held-out (10 per world) + 8 retention;
    24 = 8 withheld + 12 held-out (6 per world) + 4 retention (1 per source world). Fixed before any target outcome."""
    p = panels()
    if n_main == 56:
        return p["withheld"] + p["heldout"] + p["retention"]
    nh, nr = {36: (10, 8), 24: (6, 4)}[n_main]
    wh = [t for i, t in enumerate(p["withheld"]) if i % 4 in (0, 2)]
    ho = p["heldout"][:nh] + p["heldout"][16:16 + nh]
    ret = p["retention"] if nr == 8 else p["retention"][0::2]
    return wh + ho + ret
