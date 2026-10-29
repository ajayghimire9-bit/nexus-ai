"""Phase 2 seed ranges, roles and the pre-committed Phase 2 target panels (NOT LOCKED).

Fresh ranges 36600-44099, above every registered range (max stop 36600 = agi/placebo) and every spent seed; disjointness
is checked at import. The family split, roles and partner rules are Phase 1's (campaign/seeds.py), unchanged; the
untouched families C5, C6, E5, E6 are held-out-world families that appear ONLY in the eval_untouched panel.
  dev 36600-37599 (development, audit, calibration)   source 37600-40599 (1000 per repetition)
  admission 40600-41599 (300 per repetition; +200.. for Stage 3)   rollout 41600-42599 (in-lineage M' rollout streams and
  their held-out rollout-evaluation tasks; 300 per repetition)   source_meta 42600-43599 (Stage 3, 300 per repetition)
  ONE-USE: eval_withheld 43600-43699, eval_ce_fresh 43700-43799, eval_untouched 43800-43899, improver_panel 43900-43999
  placebo 44000-44099 (placebo generation only)."""
from nexus.campaign import seeds as S1
from nexus import seed_registry as R
from nexus.campaign.worlds import SOURCE_WORLDS, HELDOUT_WORLDS
from nexus.campaign2.worlds2 import FAMILIES, UNTOUCHED

RANGES = {("agi2", "dev"): range(36600, 37600), ("agi2", "source"): range(37600, 40600),
          ("agi2", "admission"): range(40600, 41600), ("agi2", "rollout"): range(41600, 42600),
          ("agi2", "source_meta"): range(42600, 43600), ("agi2", "eval_withheld"): range(43600, 43700),
          ("agi2", "eval_ce_fresh"): range(43700, 43800), ("agi2", "eval_untouched"): range(43800, 43900),
          ("agi2", "improver_panel"): range(43900, 44000), ("agi2", "placebo"): range(44000, 44100)}
ONE_USE = {("agi2", "eval_withheld"), ("agi2", "eval_ce_fresh"), ("agi2", "eval_untouched"), ("agi2", "improver_panel")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()

SPLIT, LEARN, ADMIT, WITHHELD = S1.SPLIT, S1.LEARN, S1.ADMIT, S1.WITHHELD
CE_OLD = [(w, f"{w}{i}") for w in HELDOUT_WORLDS for i in (1, 2, 3, 4)]


def role_of(world, family):
    if (world, family) in UNTOUCHED:
        return "untouched"
    return S1.role_of(world, family)


def partners_for(world, family, role):
    return S1.partners_for(world, family, role)


# protocol-check replacements (scripts/agi2_protocol.py, before any target outcome): a target that is a behavioural copy
# of a possible source task is replaced by the reserve seed +50 in the same one-use range
REPLACED = {43614: 43664}


def panels():
    """withheld 16 (4 per source world, L1-L4); ce_fresh 16 (C1-C4, E1-E4 x 2 levels); untouched 16 (C5, C6, E5, E6 x
    L1-L4); improver_panel 12 (2 per world: source worlds learning + withheld family; C / E: C1, C2 / E1, E2)."""
    st = {k: RANGES[("agi2", k)].start for k in ("eval_withheld", "eval_ce_fresh", "eval_untouched", "improver_panel")}
    wh = [(w, f, (i + j) % 4 + 1, st["eval_withheld"] + 4 * i + j, "withheld") for i, (w, f) in enumerate(WITHHELD)
          for j in range(4)]
    ce = [(w, f, (i + j) % 4 + 1, st["eval_ce_fresh"] + 2 * i + j, "ce_fresh") for i, (w, f) in enumerate(CE_OLD)
          for j in (0, 2)]
    un = [(w, f, lv, st["eval_untouched"] + 4 * i + lv - 1, "untouched") for i, (w, f) in enumerate(UNTOUCHED)
          for lv in (1, 2, 3, 4)]
    pan, k = [], 0
    for w in SOURCE_WORLDS + HELDOUT_WORLDS:
        fams = [SPLIT[w]["learn"][0], SPLIT[w]["withheld"]] if w in SOURCE_WORLDS else [w + "1", w + "2"]
        for f in fams:
            pan.append((w, f, k % 4 + 1, st["improver_panel"] + k, "improver_panel"))
            k += 1
    fix = lambda lst: [(w, f, lv, REPLACED.get(s, s), p) for (w, f, lv, s, p) in lst]      # noqa: E731
    return dict(withheld=fix(wh), ce_fresh=fix(ce), untouched=fix(un), improver_panel=fix(pan))


def reduced(n_main):
    """Main suite = withheld + ce_fresh + untouched (48). Balanced reductions fixed before any outcome:
    48 = all; 32 = 8 withheld (2 per world, levels differing by 2) + 8 ce_fresh (one per family) + 16 untouched (all);
    24 = 4 withheld (1 per world) + 4 ce_fresh (C1, C3, E1, E3... one per 2 families) + 16 untouched."""
    p = panels()
    if n_main == 48:
        return p["withheld"] + p["ce_fresh"] + p["untouched"]
    if n_main == 32:
        return [t for i, t in enumerate(p["withheld"]) if i % 4 in (0, 2)] + p["ce_fresh"][0::2] + p["untouched"]
    return [t for i, t in enumerate(p["withheld"]) if i % 4 == 0] + p["ce_fresh"][0::4] + p["untouched"]
