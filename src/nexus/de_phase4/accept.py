"""de_accept_v2 (NOT LOCKED): the anti-overfitting acceptance gate applied by EVERY evaluated arm. Same philosophy as
mi3_accept (accept only what was tested within stated limits; never a universal certificate), for data pipelines.

  1 HELD-BACK VISIBLE SPLIT  the stakeholder's golden rows (and quarantine ids) of the visible batch are split into 5 folds
                             of 20 % per project (seeded by the project id); a search sees only the 80 % synthesis split; a
                             candidate must also reproduce the 20 % held-back rows / ids it never saw (the row count is the
                             stated total). If the found candidate fails its held-back fold, the search RESTARTS from scratch
                             with the next fold held back (K-fold rotation: the evidence of a fault may sit in one fold).
  2 INVARIANT PROBES         the candidate runs on (a) the visible batch in reverse landing order (order invariance), (b) a
                             STRESS batch = visible + fresh-keyed rows with dirty numeric strings in columns already seen
                             dirty, zero in every divisor column, empty text in non-key text columns and a non-terminating
                             ratio, (c) a MIRROR batch = visible + the whole visible batch with its identity columns (id, high-
                             cardinality text, a raw unique key) consistently relabelled v -> 'z' + v (relabelling
                             invariance: the output must be the visible output plus its relabelled copy - or doubled sums
                             when grouping by a non-identity column; a dedup / key that only fits the visible batch by chance,
                             e.g. a measure column or a log offset used as an event key, collapses mirror rows), (d) EMPTY.
                             Invariants: no runtime error (ANSI no-crash), contract column types, unique key, non-corruption
                             (rows / groups of visible keys unchanged by fresh-keyed rows), relabelling invariance.
  3 AMBIGUITY CLOSURE        competing repairs at edit distance 1 from the candidate's edit path (every other parameter of
                             each edit, each edit dropped, one edit inserted); those that also pass 1 and 2 are run against X
                             on a BOUNDARY batch (rows at T-1, T, T+1 of every threshold T a candidate's filters compare to)
                             and on the STRESS rows - separate batches, never appended to the visible rows.
                             If any competitor disagrees, the visible evidence under-determines the repair: the gate submits
                             only if a LEARNED preference (memory 'prefs', from verified / refuted source submissions)
                             separates the choice by the improver's margin; otherwise UNDER_SPECIFIED_WARNING (abstain).
Scope record: alternatives enumerated, visible-consistent competitors, probes run; nothing outside those is claimed."""
from __future__ import annotations

import random

from nexus.de_phase4 import ir, ops as O
from nexus.de_phase4 import world as W

MAX_ALTS, MAX_COMPETITORS, N_FOLDS = 400, 60, 5      # reaching either cap = an incomplete closure = abstain


def folds(golden_rows, ids, seed_key):
    """K-fold held-back splits [(synth rows, held rows, synth ids, held ids)]: up to 5 folds of ~20 %; outputs with fewer
    than 4 golden rows cannot spare a held-back row (one fold, nothing held back - the probes still apply)."""
    rng = random.Random(f"accept_v2|{seed_key}")
    idx = list(range(len(golden_rows)))
    rng.shuffle(idx)
    qi = sorted(ids or [])
    rng.shuffle(qi)
    if len(idx) < 4:
        return [(list(golden_rows), [], sorted(qi), [])]
    k = min(N_FOLDS, len(idx))
    out = []
    for f in range(k):
        held = set(idx[f::k])
        hq = set(qi[f::k]) if len(qi) >= 3 else set()
        out.append(([r for i, r in enumerate(golden_rows) if i not in held], [r for i, r in enumerate(golden_rows) if i in held],
                    sorted(set(qi) - hq), sorted(hq)))
    return out


# ------------------------------------------------------------------ probe batches
def _fresh_cols(dom):
    """Identity columns given fresh values in probe rows: id, the unique key and high-cardinality text columns."""
    out = {c for c in dom.text_cols if len(dom.domain[c]) >= 0.6 * max(1, len(dom.rows))} | {"id"}
    if dom.contract.get("unique_key") in dom.header:
        out.add(dom.contract["unique_key"])
    return out


def _template(dom, j, fresh):
    """A probe row: a visible row with fresh identity values and VALID integers in every already-dirty column (a probe
    varies one thing; a row that a correct quarantine drops for an unrelated reason probes nothing)."""
    r = dict(dom.rows[j % len(dom.rows)])
    for c in dom.dirty_cols:
        if not ir._is_int(r[c]):
            r[c] = "5"
    for c in fresh:
        r[c] = f"PZ{j}"
    return r


def stress_rows(dom, spec):
    fresh = _fresh_cols(dom)
    rows, j = [], 0
    divisors = {c for _, _, x in ir.exprs(spec) for n in ir.walk(x) if n[0] in ("div", "div_real") for c in ir.cols_in(n[2])}
    for c in sorted(dom.dirty_cols):
        for v in ("n/a", "12x", ""):
            r = _template(dom, j, fresh)
            r[c] = v
            rows.append(r)
            j += 1
    for c in sorted(divisors):
        r = _template(dom, j, fresh)
        r[c] = "0"
        rows.append(r)
        j += 1
    for c in sorted(set(dom.text_cols) - fresh):
        r = _template(dom, j, fresh)
        r[c] = ""
        rows.append(r)
        j += 1
    used = {c for _, _, x in ir.exprs(spec) for c in ir.cols_in(x)} & dom.int_like - dom.dirty_cols
    if used:                                           # a non-terminating ratio / generic magnitude row
        r = _template(dom, j, fresh)
        for c in used:
            r[c] = "3" if c in divisors else "7"
        rows.append(r)
    return rows


def thresholds(spec, state):
    out = []
    for n in ir.walk(spec.get("filter") or ["lit", None]):
        if n[0] in ("gt", "ge", "lt", "eq") and n[1][0] == "cast_int" and n[1][1][0] == "col":
            try:
                out.append((n[1][1][1], ir.ev(n[2], {}, state)))
            except Exception:                           # noqa: BLE001
                pass
    return out


def boundary_rows(dom, specs):
    fresh = _fresh_cols(dom)
    rows, j = [], 1000
    for c, t in sorted({x for s in specs for x in thresholds(s, dom.state)}, key=repr):
        for v in (t - 1, t, t + 1):
            r = _template(dom, j - 1000, fresh)
            r[c] = str(v)
            rows.append(r)
            j += 1
    return rows


def _result_key(res, cols):
    return (W.table_key(res["clean"], cols), sorted(str(r.get("id")) for r in res["rejects"]) if res["rejects"] is not None else None)


def mirror_check(inv, spec, base, engine=None):
    """Relabelling invariance on visible + a relabelled copy of the visible batch. -> True / False / None (not applicable)."""
    cols, uk = inv.contract["output_cols"], inv.contract.get("unique_key")
    key_expr = spec["group"][1] if spec.get("group") and spec["group"][0] == uk else next((x for n, x in spec["outputs"] if n == uk), None)
    ren = {c for c in inv.text_cols if len(inv.domain[c]) >= 0.6 * max(1, len(inv.rows))} | {"id"}
    if key_expr == ["col", uk] and uk in inv.header:
        ren.add(uk)
    elif not spec.get("group"):
        return None
    mirror = [{c: ("z" + v if c in ren and v.strip() else v) for c, v in r.items()} for r in inv.rows]
    res = inv.exec(spec, inv.rows + mirror, engine)
    if uk in ren:
        exp = base["clean"] + [{c: ("z" + v if c == uk else v) for c, v in r.items()} for r in base["clean"]]
    else:                                              # grouped by a non-identity key: every SUM doubles
        exp = [{c: (2 * v if c != uk and isinstance(v, (int, float)) and not isinstance(v, bool) else v) for c, v in r.items()}
               for r in base["clean"]]
    if W.table_key(res["clean"], cols) != W.table_key(exp, cols):
        return False
    if base["rejects"] is not None:
        want = sorted([str(r.get("id")) for r in base["rejects"]] + ["z" + str(r.get("id")) for r in base["rejects"]])
        if sorted(str(r.get("id")) for r in (res["rejects"] or [])) != want:
            return False
    return True


def invariants(inv, spec, engine=None):
    """Probe invariants of a candidate on the project engine (or `engine`) -> list of violations (empty = pass)."""
    dom, cols, types = inv, inv.contract["output_cols"], inv.contract.get("output_types", {})
    uk = inv.contract.get("unique_key")
    viol = []
    try:
        base = inv.exec(spec, inv.rows, engine)
        rev = inv.exec(spec, inv.rows[::-1], engine)
        if _result_key(rev, cols) != _result_key(base, cols):
            viol.append("order_dependence")
        st = inv.exec(spec, inv.rows + stress_rows(dom, spec), engine)
        inv.exec(spec, [], engine)
        if mirror_check(inv, spec, base, engine) is False:
            viol.append("relabelling")
    except W.RunError as e:
        return [f"crash:{e.cls}"]
    for r in st["clean"]:
        for c, t in types.items():
            v = r.get(c)
            if v is None:
                continue
            if (t == "int" and not (isinstance(v, int) and not isinstance(v, bool))) or \
                    (t == "real" and not isinstance(v, (int, float))) or (t == "text" and not isinstance(v, str)):
                viol.append(f"type:{c}")
                break
    if uk and uk in cols:
        ks = [r.get(uk) for r in st["clean"]]
        if len(ks) != len(set(ks)):
            viol.append("unique")
        b = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in base["clean"]}
        s_ = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in st["clean"]}
        if any(k in s_ and s_[k] != v for k, v in b.items()) or any(k not in s_ for k in b):
            viol.append("corruption")
    return sorted(set(viol))


def alternatives(inv, path):
    """Competing repairs at edit distance 1 from the path [(op, prm)]: each edit's other parameters, each edit dropped,
    and one more edit inserted at the end."""
    out, seen = [], set()
    x = O.replay(inv.legacy, path, inv)
    seen.add(ir.canon(x))
    for op in O.OPS:
        for y, p in O.candidates(op, x, inv):
            k = ir.canon(y)
            if k not in seen:
                seen.add(k)
                out.append(dict(spec=y, pos=len(path), op=op, prm_x=None, prm_y=p))
    for i, (op, prm) in enumerate(path):
        before = O.replay(inv.legacy, path[:i], inv)
        variants = [(s, p) for s, p in O.candidates(op, before, inv) if p != prm] + [(before, None)]
        for s, p in variants:
            y = O.replay(s, path[i + 1:], inv)
            k = ir.canon(y)
            if k in seen:
                continue
            seen.add(k)
            out.append(dict(spec=y, pos=i, op=op, prm_x=prm, prm_y=p))
    subs = [a for a in out if a["pos"] < len(path)]
    ins = [a for a in out if a["pos"] == len(path)]
    return subs + ins


def choice_class(op, prm):
    return f"{op}:{O.pclass(op, prm)}" if prm is not None else f"{op}:absent"


def closure(inv, spec, path, prefs, margin, explore=False, deadline=None):
    """-> dict(status in {unique, resolved, ambiguous, explore}, spec (chosen), scope record, choice)."""
    import time
    # competitors of a Spark candidate are screened and compared on SQLite (business semantics; cheap): this can only add
    # competitors (more abstention), never hide one that disagrees; X's own invariants ran on the project engine
    eng = inv.sq if inv.sq is not inv.rt else None
    alts = alternatives(inv, path)
    if len(alts) > MAX_ALTS:
        return dict(status="ambiguous", spec=None, scope=dict(alternatives=len(alts), note="closure scope exceeds MAX_ALTS"))
    comp, n_vis = [], 0
    for a in alts:
        if deadline and time.time() > deadline:
            return dict(status="ambiguous", spec=None, scope=dict(alternatives=len(alts), visible_consistent=n_vis,
                                                                  competitors=len(comp), note="closure cut by the budget"))
        if not inv.visible_ok(a["spec"], engine=eng):
            continue
        n_vis += 1
        if invariants(inv, a["spec"], eng):
            continue
        comp.append(a)
        if len(comp) >= MAX_COMPETITORS:
            return dict(status="ambiguous", spec=None, scope=dict(alternatives=len(alts), visible_consistent=n_vis,
                                                                  competitors=len(comp), note="closure cut at MAX_COMPETITORS"))
    scope = dict(alternatives=len(alts), visible_consistent=n_vis, competitors=len(comp))
    if not comp:
        return dict(status="unique", spec=spec, scope=scope)
    # compared on separate probe batches (never appended to the visible rows: that would fabricate impossible replays)
    batches = [b for b in (boundary_rows(inv, [spec] + [a["spec"] for a in comp]), stress_rows(inv, spec)) if b]
    cols = inv.contract["output_cols"]
    try:
        kx = [_result_key(inv.exec(spec, b, eng), cols) for b in batches]
    except W.RunError:
        return dict(status="ambiguous", spec=None, scope=dict(scope, note="candidate crashed on a probe batch"))
    dis = []
    for a in comp:
        try:
            if [_result_key(inv.exec(a["spec"], b, eng), cols) for b in batches] != kx:
                dis.append(a)
        except W.RunError:
            pass
    scope["disagreeing"] = len(dis)
    scope["disagreeing_edits"] = [[a["pos"], a["op"], a["prm_x"], a["prm_y"]] for a in dis[:12]]
    if not dis:
        return dict(status="unique", spec=spec, scope=scope)
    # resolution by a learned preference: all disagreeing competitors differ from X at ONE edit (same position and operator)
    where = {(a["pos"], a["op"]) for a in dis}
    members = None
    if len(where) == 1:
        i, op = where.pop()
        prm_x = path[i][1] if i < len(path) else None
        members = [(choice_class(op, prm_x), spec)] + [(choice_class(a["op"], a["prm_y"]), a["spec"]) for a in dis]
    choice = None
    if members and len({c for c, _ in members}) == len(members):
        sc = sorted(((prefs.get(c, 0.0), c, s) for c, s in members), key=lambda t: -t[0])
        best = sc[0]
        if best[0] - sc[1][0] >= margin:
            choice = dict(chosen=best[1], rejected=[c for _, c, _ in sc[1:]], resolved=True)
            return dict(status="resolved", spec=best[2], scope=scope, choice=choice)
        if explore:
            choice = dict(chosen=best[1], rejected=[c for _, c, _ in sc[1:]], resolved=False)
            return dict(status="explore", spec=best[2], scope=scope, choice=choice)
    elif explore:
        return dict(status="explore", spec=spec, scope=scope, choice=None)
    return dict(status="ambiguous", spec=None, scope=scope,
                classes=[c for c, _ in members] if members else None)
