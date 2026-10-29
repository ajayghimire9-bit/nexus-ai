"""Phase 3 seed ranges and panels (NOT LOCKED). Fresh ranges 44100-53599, above every registered range and spent seed
(checked at import). World-task ranges (agi3/*) and data-engineering project ranges (agi3de/*) are separate.
  agi3: dev 44100-44999, source 45000-47999 (1000 / repetition), admission 48000-48999 (300 / repetition; Stage 3 +200),
        rollout 49000-49999, source_meta 50000-50999, placebo 53500-53599
  agi3de: dev 51000-51499 (Stage 1 development incl. the operating-cycle trace), source 51500-52999 (source learning and
          DE admission projects)
  ONE-USE: agi3/eval_worlds 53000-53199, agi3/eval_untouched 53200-53299, agi3de/eval 53300-53399,
           agi3/improver_panel 53400-53499"""
from nexus.campaign2 import seeds as S2                    # noqa: F401  (registers Phase 1 / 2 ranges first)
from nexus import seed_registry as R
from nexus.campaign.worlds import SOURCE_WORLDS, HELDOUT_WORLDS
from nexus.campaign3.worlds3 import UNTOUCHED3, PHASE2_COMPARISON

RANGES = {("agi3", "dev"): range(44100, 45000), ("agi3", "source"): range(45000, 48000),
          ("agi3", "admission"): range(48000, 49000), ("agi3", "rollout"): range(49000, 50000),
          ("agi3", "source_meta"): range(50000, 51000), ("agi3de", "dev"): range(51000, 51500),
          ("agi3de", "source"): range(51500, 53000), ("agi3", "eval_worlds"): range(53000, 53200),
          ("agi3", "eval_untouched"): range(53200, 53300), ("agi3de", "eval"): range(53300, 53400),
          ("agi3", "improver_panel"): range(53400, 53500), ("agi3", "placebo"): range(53500, 53600)}
ONE_USE = {("agi3", "eval_worlds"), ("agi3", "eval_untouched"), ("agi3de", "eval"), ("agi3", "improver_panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

SPLIT, LEARN, ADMIT, WITHHELD = S2.SPLIT, S2.LEARN, S2.ADMIT, S2.WITHHELD
DE_SOURCE = ("G1", "G2", "G3", "G4")
DE_HOLDOUT = ("G5", "G6")


def role_of(world, family):
    if (world, family) in UNTOUCHED3:
        return "untouched3"
    if (world, family) in PHASE2_COMPARISON:
        return "phase2_comparison"
    return S2.role_of(world, family)


def partners_for(world, family, role):
    return S2.partners_for(world, family, role)


def panels():
    st = {k: RANGES[("agi3", k)].start for k in ("eval_worlds", "eval_untouched", "improver_panel")}
    ev = st["eval_worlds"]
    ret = [(w, f, lv, ev + i, "retention") for i, ((w, f), lv) in enumerate(zip(LEARN[0::2], (1, 2, 3, 4)))]
    wh = [(w, f, lv, ev + 10 + i, "withheld") for i, ((w, f), lv) in enumerate(zip(WITHHELD, (1, 2, 3, 4)))]
    ce = [(w, f"{w}{k}", lv, ev + 20 + i, "ce_instance") for i, (w, k, lv) in
          enumerate([("C", 1, 1), ("C", 2, 2), ("C", 3, 3), ("C", 4, 4), ("E", 1, 2), ("E", 2, 1), ("E", 3, 4), ("E", 4, 3)])]
    p2 = [(w, f, lv, ev + 40 + i, "phase2_comparison") for i, ((w, f), lv) in enumerate(zip(PHASE2_COMPARISON, (1, 2, 1, 2)))]
    un = [(w, f, lv, st["eval_untouched"] + 4 * i + lv - 1, "untouched3") for i, (w, f) in enumerate(UNTOUCHED3) for lv in (1, 2, 3)]
    pan, k = [], 0
    for w in SOURCE_WORLDS + HELDOUT_WORLDS:
        fams = [SPLIT[w]["learn"][0], SPLIT[w]["withheld"]] if w in SOURCE_WORLDS else [w + "1", w + "2"]
        for f in fams:
            pan.append((w, f, k % 4 + 1, st["improver_panel"] + k, "improver_panel"))
            k += 1
    return dict(retention=ret, withheld=wh, ce_instance=ce, phase2_comparison=p2, untouched3=un, improver_panel=pan)


def de_panel(n_per_cell):
    """Unseen DE projects: new instances of source families G1-G4 and the untouched holdout families G5, G6, on both
    runtimes, level 1 and 2 alternating. n_per_cell projects per (family, runtime)."""
    base = RANGES[("agi3de", "eval")].start
    out, k = [], 0
    for fam in DE_SOURCE + DE_HOLDOUT:
        for rt in ("sqlite", "spark"):
            for j in range(n_per_cell):
                out.append((fam, (k + j) % 2 + 1, base + k, rt, "de_holdout" if fam in DE_HOLDOUT else "de_instance"))
                k += 1
    return out


def worlds_main(n):
    """Balanced world main suite: 36 = all panels except improver (4 retention + 4 withheld + 8 ce + 4 phase-2 + 12
    untouched3 + ... ); reductions keep every untouched3 task."""
    p = panels()
    full = p["retention"] + p["withheld"] + p["ce_instance"] + p["phase2_comparison"] + p["untouched3"]
    if n >= len(full):
        return full
    keep = p["untouched3"]
    rest = [t for t in full if t[4] != "untouched3"]
    return rest[0::max(1, len(rest) // max(1, n - len(keep)))][:n - len(keep)] + keep
