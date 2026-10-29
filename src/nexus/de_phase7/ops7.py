"""Phase 7 operator extension (NOT LOCKED; a disclosed HUMAN addition given to every arm and control).

The Stage 1 reachability diagnostic found that de_phase4.ops.candidates excludes the identity column 'id' from every
parameter list, so `dedup_first` can never deduplicate exact re-deliveries of the same row identity - yet that is the
intended repair of the generator's duplicate-id and fan-out mechanisms (world6 build_stage: dedup key 'id'). Projects
whose legacy pipeline lacks that step were unrepairable in Phase 6. This module adds the one missing parameterisation:
dedup_first on 'id' when 'id' is not unique in the stage input. It is a general primitive (drop exact re-deliveries of a
row identity), not a paradigm solution. Registered at import by wrapping engines6.candidates (the module attribute every
caller - pipeline6, search7, skills6.bind - resolves at call time); Phase 4 / 6 files are unchanged."""
from __future__ import annotations

import copy

from nexus.de_phase6 import engines6 as E

_ORIG = getattr(E.candidates, "_phase6_original", E.candidates)


def candidates(op, spec, dom):
    out = _ORIG(op, spec, dom)
    if op == "dedup_first" and not spec.get("dedup") and "id" in dom.header and "id" not in dom.unique_cols:
        s = copy.deepcopy(spec)
        s["dedup"] = dict(key="id")
        out.insert(0, (s, "id"))                                  # header order: 'id' is the first column
    return out


candidates._phase6_original = _ORIG
E.candidates = candidates
