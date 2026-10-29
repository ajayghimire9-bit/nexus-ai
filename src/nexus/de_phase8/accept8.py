"""Phase 8 shared acceptance repair (NOT LOCKED; a HUMAN repair to the experiment, given identically to every arm; it is
not counted as autonomous NEXUS improvement). de_phase7.accept7 (coverage v7, invariants v7) and every checker kernel are
unchanged; this module adds coverage v8.

Phase 7 matched documented subjects to filters SYNTACTICALLY and treated a subject with no matching filter as
'uncovered' without blocking (the one Phase 7 wrong project: a spurious column comparison stood in for a missing
documented threshold). coverage8 is SEMANTIC and obligation-based:

  probe       for every documented subject (a state-reference threshold t, from Inv6.claim_refs - which subjects exist,
              not what the documents say), single-row probes are run through the WHOLE candidate pipeline: base rows that
              the pipeline keeps, with one integer-like input column set to t-1, t, t+1 (t evaluated per row, so a
              column-relative threshold works). A column whose crossing of t changes the kept / excluded outcome
              CONSISTENTLY (the same cut on every evaluable base row, >= 2 when available) is a DEPENDENT column; the
              kept / excluded outcome at exactly t is the implemented boundary effect.
  absent      no input column depends on t: no part of the pipeline implements the documented requirement (a syntactic
              step that does not change behaviour at t - e.g. a misleading column comparison - is NOT coverage). The
              obligation has no satisfiable option and BLOCKS (abstain); a question cannot repair it (probe=None).
  implemented the pipeline (any stage, any expression shape) implements a boundary at t. Options: the current pipeline,
              plus - when a comparison on the subject exists syntactically in some stage - that comparison reversed,
              kept only if the probe confirms the reversal flips the boundary effect. The procedure discharges the
              obligation by matching documented claims (unanimous / calibrated trust) or the single clarification.
  status      (reported at submission) satisfied | refuted | conflict | insufficient, from the attached claims and the
              chosen option: legacy behaviour is evidence of existing behaviour, never authority; drafts, ambiguous or
              'undetermined' answers and absent evidence never become approved requirements.
No rule names a paradigm, an operator, a column, a seed or a document order."""
from __future__ import annotations

import copy
import json

from nexus.de_phase4 import ir
from nexus.de_phase6 import pipeline6 as P6
from nexus.de_phase7 import accept7 as AC7

N_BASE = 3


def _kept(inv, specs, row):
    k = P6.okey(inv, specs, [row])
    if k == "error":
        return None
    return bool(json.loads(k)[0])


def _refs_cols(ref):
    return {n[1] for n in ir.walk(ref) if n and n[0] == "col"}


def profile(inv, specs, ref, cost):
    """-> dict(dependent=[(col, base_row, effect_at_t)], tried=[cols]) for the documented threshold ref."""
    d0 = inv.dom(0, inv.legacy)
    fresh = P6._fresh(inv, inv.rows)
    syn = [n[1][1][1] for sp in specs for n in AC7._filters_on(sp, ref)]
    cols = [c for c in syn if c in inv.header] + sorted(c for c in d0.int_like if c not in syn and c not in _refs_cols(ref))
    base = []
    for j, r in enumerate(inv.rows):
        q = dict(r)
        for c in fresh:
            q[c] = f"PV{j}_{q[c]}"
        cost["probe_runs"] = cost.get("probe_runs", 0) + len(specs)
        if _kept(inv, specs, q):
            base.append(q)
        if len(base) == N_BASE:
            break
    dep = []
    for c in dict.fromkeys(cols):
        pats = []
        for q in base:
            try:
                t = int(ir.ev(ref, q, inv.state))
            except Exception:                                   # noqa: BLE001  (threshold not evaluable on this row)
                continue
            outs = []
            for delta in (-1, 0, 1):
                x = dict(q)
                x[c] = str(t + delta)
                cost["probe_runs"] = cost.get("probe_runs", 0) + len(specs)
                outs.append(_kept(inv, specs, x))
            if None in outs:
                continue
            pats.append((tuple(outs), q, t))
            if len(set(outs)) == 1:                             # one evaluable row without a cut at t: not this column
                break
        # a CONSISTENT cut at t on every evaluable base row (>= 2 when available): a comparison with another column that
        # crosses t only by coincidence on one row is not an implementation of the documented threshold
        need = min(2, len(base))
        if len(pats) >= need and pats and all(len(set(o)) > 1 for o, _, _ in pats) and len({o for o, _, _ in pats}) == 1:
            o, q, t = pats[0]
            x = dict(q)
            x[c] = str(t)
            dep.append((c, x, "kept" if o[1] else "excluded"))
            break
    return dict(dependent=dep, tried=list(dict.fromkeys(cols)), base_rows=len(base))


def coverage8(inv, specs, cost=None, skip_refs=()):
    cost = {} if cost is None else cost
    skip = {json.dumps(r) for r in skip_refs if r is not None}
    obligations, equiv, absent = [], [], []
    for key, ref in AC7.documented_subjects(inv).items():
        if key in skip:
            continue
        pr = profile(inv, specs, ref, cost)
        if not pr["dependent"]:
            absent.append(ref)
            obligations.append(dict(stage=0, pos=f"cov8:{key}", op="requirement_absent", options=[], specs=[], probe=None, ref=ref, col=None,
                                    resolved=None, via=None, conflict=False, undecided=False, claims=[], option_keys=[], effects=[], kind="absent",
                                    evidence=dict(tried=pr["tried"], base_rows=pr["base_rows"]), origin="coverage v8: no input column depends on the threshold"))
            continue
        col, row, eff = pr["dependent"][0]
        options, alts, effects = ["current pipeline"], [specs], [eff]
        hits = [(k, n) for k, sp in enumerate(specs) for n in AC7._filters_on(sp, ref)]
        for k, node in hits[:1]:
            alt = list(specs)
            alt[k] = AC7._reverse(specs[k], node)
            ka = _kept(inv, alt, row)
            cost["probe_runs"] = cost.get("probe_runs", 0) + len(specs)
            if ka is not None and ("kept" if ka else "excluded") != eff:
                options.append(f"reverse {node[1][1][1]} {node[0]} at stage {k}")
                alts.append(alt)
                effects.append("kept" if ka else "excluded")
        keys = [P6.okey(inv, s, [row]) for s in alts]
        obligations.append(dict(stage=hits[0][0] if hits else 0, pos=f"cov8:{key}", op="requirement_boundary", options=options, specs=alts, probe=row,
                                ref=ref, col=col, resolved=None, via=None, conflict=False, undecided=False, claims=[], option_keys=keys, effects=effects,
                                kind="implemented", reversible=len(options) > 1, origin="coverage v8: behaviour at the documented threshold"))
    return dict(obligations=obligations, equivalences=equiv, uncovered=absent, probe_runs=cost.get("probe_runs", 0))


def status(dp):
    """satisfied | refuted | conflict | insufficient for one coverage obligation after the procedure ran."""
    effs = {c["effect_at_boundary"] for c in dp.get("claims") or []}
    if dp.get("kind") == "absent":
        return "insufficient" if not effs else "refuted"
    if dp.get("undecided") or (len(effs) > 1 and dp["resolved"] is None):
        return "conflict"
    if dp["resolved"] is None:
        return "insufficient"
    chosen = dp["effects"][dp["options"].index(dp["resolved"])]
    return "satisfied" if dp["via"] in ("claim", "trust:calibrated", "clarification") and (dp["via"] == "clarification" or chosen in effs) else "insufficient"


def apply(specs, dp, choice):
    """The pipeline selected for a coverage obligation (the option's full pipeline)."""
    return copy.deepcopy(dp["specs"][dp["options"].index(choice)])
