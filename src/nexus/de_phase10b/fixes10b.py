"""Phase 10B shared fixes (NOT LOCKED; HUMAN repairs given identically to every arm; not counted as NEXUS learning).

1 ROUND primitive (Phase 10 Stage 1A audit, P7 77303): no operator could replace an integer truncation of a real-valued
  output by rounding (the truth is round2(x / y) where the legacy is cast_int(x / y); the existing round2 wraps the WHOLE
  expression). New operator `round_uncast`: for an output of the form cast_int(E) with a real division inside E, produce
  round2(E). Registered into engines6.OPS / STAGE / candidates at import (Phase 4 / 6 files unchanged).
2 IDEMPOTENT coverage application (the Phase 10 wrong repair, C1@N60 on 84005): procedure8.chosen_specs applied a coverage
  obligation's choice as a RELATIVE flip after the repair-closure rebinding, so two consistent decisions on the same
  boundary (closure: 'ge'; coverage: 'kept') flipped it back to 'gt'. chosen_specs10b enforces the chosen boundary EFFECT
  as a target predicate: after rebinding, the final pipeline is probed on the obligation's own probe row and flipped only if
  the effect differs (and kept only if the flip establishes it); applying the same requirement twice is idempotent."""
from __future__ import annotations

import copy

from nexus.de_phase4 import ir
from nexus.de_phase6 import engines6 as E, pipeline6 as P6, procedure6 as PR, world6 as W6
from nexus.de_phase7 import ops7  # noqa: F401
from nexus.de_phase8 import accept8 as AC8, procedure8 as PR8

if "round_uncast" not in E.OPS:
    E.OPS = E.OPS + ("round_uncast",)
    E.STAGE = dict(E.STAGE, round_uncast=3)
_PREV = E.candidates


def candidates(op, spec, dom):
    if op != "round_uncast":
        return _PREV(op, spec, dom)
    out = []
    for i, (n, x) in enumerate(spec.get("outputs", [])):
        if x and x[0] == "cast_int" and any(m and m[0] in ("div", "div_real") for m in ir.walk(x[1])):
            s = copy.deepcopy(spec)
            s["outputs"][i] = [n, ["round2", x[1]]]
            out.append((s, n))
    return out


if not getattr(E.candidates, "_phase10b", False):
    candidates._phase10b = True
    E.candidates = candidates


def chosen_specs(st):
    cov = [d for d in st.dps if str(d["pos"]).startswith("cov8:")]
    rest = [d for d in st.dps if not str(d["pos"]).startswith("cov8:")]
    saved, st.dps = st.dps, rest
    specs = copy.deepcopy(PR.chosen_specs(st))
    st.dps = saved
    if not cov:
        return specs
    inv = P6.Inv6(st.p)
    for d in cov:
        ch = st.decision["choices"][f"{d['stage']}:{d['pos']}"]
        if not d["options"] or d.get("probe") is None:
            continue
        target = d["effects"][d["options"].index(ch)]
        cur = AC8._kept(inv, specs, d["probe"])
        if cur is None or ("kept" if cur else "excluded") == target:
            continue
        flipped = list(specs)
        flipped[d["stage"]] = W6._flip(specs[d["stage"]], d["ref"])
        f2 = AC8._kept(inv, flipped, d["probe"])
        if f2 is not None and ("kept" if f2 else "excluded") == target:
            specs = flipped
    return specs


chosen_specs._phase10b = True
PR8.chosen_specs = chosen_specs                              # procedure8.outcome resolves chosen_specs at call time
