"""Phase 7 requirement-coverage and behavioural-consistency barrier (NOT LOCKED; separately versioned - de_accept_v3 in
de_phase6.pipeline6 and the checker kernels are unchanged; the same barrier applies to EVERY arm).

Phase 6's gate derived decision points only from disagreement among REPAIR alternatives, so a documented requirement on an
UNEDITED stage was never checked (erratum; the P7 failures). coverage(inv, specs, claims):
  1 every documented SUBJECT (a claim's state-reference / compared-column expression) is matched against every filter of
    every stage - edited or not - that compares a column to that subject
  2 the pipeline's actual behaviour at that boundary is OBSERVED with a distinguishing single-row probe, against the same
    pipeline with that comparison's inclusivity reversed (the generic alternative behaviour at the documented boundary)
  3 if the two behaviours are materially different (they disagree on the probe) the subject becomes an OBLIGATION
    (a decision point: options = current / reversed, their probe outputs, the claims). If they provably agree on every
    probe, a LIMITED EQUIVALENCE is recorded (no question needed).
  4 obligations are discharged only by the investigation procedure: unanimous stated claims, calibrated trust, or the
    single clarification. Legacy behaviour is an observation, never an authority; an 'undetermined' answer leaves the
    obligation unresolved. submit_or_abstain (every arm) abstains while any obligation is open.
The barrier gathers evidence (it reads the requirement documents to know which subjects exist, and runs probes); all of it
is charged to the arm and reported as SHARED-BARRIER work, separately from what NEXUS learned. It never resolves an
obligation itself. No rule names <=, >=, a paradigm, a column or a timestamp.

GATE REPAIR (de_accept_v7 invariants, Stage 1 development finding): de_accept_v3's 'corruption' invariant appends stress
rows that keep the visible rows' group-key values, so in every pipeline that aggregates by a non-identity key the stress
rows legitimately change existing groups' totals and EVERY candidate - legacy and correct repairs alike (dev check: a
hidden-verified dedup-on-id repair) - is rejected; pipeline6.closure used the same check to discard competitors.
invariants7 is pipeline6.invariants with one change: stress rows also receive fresh values in the group-key columns, so
they form new groups. Registered at import as pipeline6.invariants (Phase 6 file unchanged; every arm shares it)."""
from __future__ import annotations

import copy
import json

from nexus.de_phase4 import ir, world as W
from nexus.de_phase6 import pipeline6 as P6, world6 as W6

SWAP = {"ge": "gt", "gt": "ge", "le": "lt", "lt": "le"}


# ------------------------------------------------------------------ de_accept_v7 invariants (versioned gate repair)
def group_cols(specs):
    return {n[1] for sp in specs if sp.get("group") for n in ir.walk(sp["group"][1]) if n and n[0] == "col"}


def invariants7(inv, specs):
    cols, types = inv.cols, inv.contract.get("output_types", {})
    d0 = inv.dom(0, specs)
    fresh = P6._fresh(inv, inv.rows)
    sfresh = fresh | (group_cols(specs) & set(inv.header))     # stress rows form NEW groups (the v7 repair)
    viol = []
    try:
        base = inv.exec(specs, prescreen=False)
        if W6.key_of(inv.exec(specs, inv.rows[::-1], prescreen=False), cols) != W6.key_of(base, cols):
            viol.append("order_dependence")
        stress = []
        for j, c in enumerate(sorted(d0.dirty_cols)):
            for v in ("n/a", "12x", ""):
                r = P6._probe(inv, 100 + 3 * j + len(stress), sfresh)
                r[c] = v
                stress.append(r)
        for c in sorted(d0.int_like - d0.dirty_cols)[:3]:
            r = P6._probe(inv, 200 + len(stress), sfresh)
            r[c] = "0"
            stress.append(r)
        for c in sorted(d0.text_cols - sfresh)[:3]:
            r = P6._probe(inv, 300 + len(stress), sfresh)
            r[c] = ""
            stress.append(r)
        st = inv.exec(specs, inv.rows + stress, prescreen=False)
        inv.exec(specs, inv.rows[:0], prescreen=False)
        last = specs[-1]
        uk = inv.ukey
        key_expr = last["group"][1] if last.get("group") and last["group"][0] == uk else next((x for n, x in last["outputs"] if n == uk), None)
        ren = set(fresh) | ({uk} if uk in inv.header and key_expr == ["col", uk] else set())
        mirror = [{c: ("z" + v if c in ren and v.strip() else v) for c, v in r.items()} for r in inv.rows]
        mres = inv.exec(specs, inv.rows + mirror, prescreen=False)
    except W.RunError as e:
        return [f"crash:{e.cls}"]
    for r in st["clean"]:
        for c, t in types.items():
            v = r.get(c)
            if v is not None and ((t == "int" and not (isinstance(v, int) and not isinstance(v, bool))) or
                                  (t == "real" and not isinstance(v, (int, float))) or (t == "text" and not isinstance(v, str))):
                viol.append(f"type:{c}")
                break
    uk = inv.ukey
    if uk and uk in cols:
        ks = [r.get(uk) for r in st["clean"]]
        if len(ks) != len(set(ks)):
            viol.append("unique")
        b = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in base["clean"]}
        s_ = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in st["clean"]}
        if any(k in s_ and s_[k] != v for k, v in b.items()) or any(k not in s_ for k in b):
            viol.append("corruption")
        if uk in ren:
            exp_ = base["clean"] + [{c: ("z" + str(v) if c == uk else v) for c, v in r.items()} for r in base["clean"]]
        else:
            exp_ = [{c: (2 * v if c != uk and isinstance(v, (int, float)) and not isinstance(v, bool) else v) for c, v in r.items()} for r in base["clean"]]
        if W.table_key(mres["clean"], cols) != W.table_key(exp_, cols):
            viol.append("relabelling")
    return sorted(set(viol))


_P6_INVARIANTS = getattr(P6.invariants, "_phase6_original", P6.invariants)
invariants7._phase6_original = _P6_INVARIANTS
P6.invariants = invariants7                              # every caller (search7, pipeline6.closure) resolves it at call time


def documented_subjects(inv):
    """Subjects named by ANY requirement document (Inv6.claim_refs: contract, runbook, ticket). Knowing that a subject is
    documented is not knowing what the documents say about it: the claims themselves reach the procedure only by reading."""
    return {k: json.loads(k) for k in sorted(inv.claim_refs)}


def _filters_on(spec, ref):
    out = []
    for n in ir.walk(spec.get("filter") or ["lit", None]):
        if n and n[0] in SWAP and len(n) == 3 and n[2] == ref and n[1][0] == "cast_int" and n[1][1][0] == "col":
            out.append(n)
    return out


def _reverse(spec, node):
    s = copy.deepcopy(spec)

    def rw(e):
        if isinstance(e, list):
            if e == node:
                return [SWAP[e[0]], e[1], e[2]]
            return [e[0]] + [rw(x) for x in e[1:]]
        return e
    s["filter"] = rw(s.get("filter"))
    return s


def coverage(inv, specs, cost=None, skip_refs=()):
    """-> dict(obligations=[decision points], equivalences=[...], uncovered=[subjects with no implementing filter])."""
    obligations, equiv, uncovered = [], [], []
    skip = {json.dumps(r) for r in skip_refs if r is not None}
    for key, ref in documented_subjects(inv).items():
        if key in skip:                                  # already a decision point of the repair closure
            continue
        hits = [(k, n) for k, sp in enumerate(specs) for n in _filters_on(sp, ref)]
        if not hits:
            uncovered.append(ref)
            continue
        for k, node in hits:
            alt = list(specs)
            alt[k] = _reverse(specs[k], node)
            probes = P6.probe_rows(inv, [specs, alt])
            row = None
            for q in probes[:80]:
                if cost is not None:
                    cost["probe_runs"] = cost.get("probe_runs", 0) + 2 * len(specs)
                if P6.okey(inv, specs, [q]) != P6.okey(inv, alt, [q]):
                    row = q
                    break
            col = node[1][1][1]
            if row is None:
                equiv.append(dict(stage=k, subject=ref, column=col, note="current and reversed boundary agree on every probe"))
                continue
            cur, rev = f"{col} {node[0]} {json.dumps(ref)}", f"{col} {SWAP[node[0]]} {json.dumps(ref)}"
            keys = [P6.okey(inv, specs, [row]), P6.okey(inv, alt, [row])]
            obligations.append(dict(stage=k, pos=f"cov:{key}", op="requirement_boundary", options=[cur, rev], specs=[specs, alt], probe=row,
                                    ref=ref, col=col, resolved=None, via=None, conflict=False, undecided=False, claims=[],
                                    option_keys=keys, effects=["kept" if k_ != "error" and json.loads(k_)[0] else "excluded" for k_ in keys],
                                    origin="coverage barrier (unedited or edited stage)"))
    return dict(obligations=obligations, equivalences=equiv, uncovered=uncovered)
