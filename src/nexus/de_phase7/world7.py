"""Phase 7 projects (NOT LOCKED): the Phase 6 arena (de_phase6.world6, unchanged) plus ONE generic transform.

legacy_flip  "legacy behaviour contradicts an authoritative requirement": the legacy pipeline already contains the
             documented boundary filter (that mechanism is NOT a fault), but with the opposite comparison; the
             requirement documents state the intended boundary explicitly. The visible batch has no boundary row (any mode
             but 'visible'), so only a requirement-coverage check against the WHOLE pipeline - including unedited stages -
             can find it. This is the Phase 6 failure case generalised; nothing in it names a paradigm or an operator.
The stage file is re-written in its own legacy language, and its semantics are re-lifted (world6 convention)."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.de_phase6 import ir6, world6 as W6


def make_project7(spec, seed, root):
    spec6 = {k: v for k, v in spec.items() if k not in ("legacy_flip",)}
    for bump in range(12):
        p = W6.make_project6(spec6, seed, root) if bump == 0 else W6.make_project6(dict(spec6, _v=bump), seed, root)
        if not spec.get("legacy_flip"):
            p["legacy_flip"] = None
            return p
        target = _flip_target(p)
        if target is None:
            continue
        k, dp = target
        st = p["stages"][k]
        ws = Path(p["ws"])
        legacy = ir6.lift((ws / st["file"]).read_text(), st["legacy_lang"])
        flipped = W6._flip(legacy, W6.dp_ref(dp, p["names"])[1])
        if flipped == legacy:
            continue
        (ws / st["file"]).write_text(ir6.lower(flipped, st["legacy_lang"]))
        p["legacy_flip"] = dict(stage=k, dp=dp)
        return p
    raise RuntimeError(f"no legacy_flip-able decision point for {spec} seed {seed}")


def _flip_target(p):
    """A documented decision point whose mechanism the legacy pipeline already implements (not a fault), with an
    explicit, unconflicted requirement claim."""
    for d, mode in p["dps"].items():
        if mode != "explicit":
            continue
        for k, st in enumerate(p["stages"]):
            mech = next((m for m in st["mechs"] if W6.DP_MECH.get(m) == d), None)
            if mech and mech not in st["faults"]:
                return k, d
    return None
