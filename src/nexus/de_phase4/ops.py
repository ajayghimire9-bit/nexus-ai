"""Phase 4 generic pipeline edit operators on the stage IR (NOT LOCKED). The Phase 3 operator set (campaign3.de_learner:
try_parse, quarantine_invalid, default_fill, real_div, zero_guard, round2, dedup_latest, dedup_first, filter_file) ported to
the staged spec, plus two generic operators: normalize_text (UPPER(TRIM(text column))) and exclude_value (drop rows whose
low-cardinality text column equals a value seen in the visible batch). Parameters are enumerated from the schema, the
visible value domain, the state files and constants mined from the golden rows; no rule maps a contract kind or an error
class to an operator (that is what the learned policy does). Every operator has a stage tag (1 identity, 2 selection,
3 typed outputs) used by stage-wise search and stage skills."""
from __future__ import annotations

import copy
import itertools
import json

from nexus.de_phase4 import ir

OPS = ("try_parse", "quarantine_invalid", "default_fill", "real_div", "zero_guard", "round2", "dedup_latest", "dedup_first",
       "filter_file", "normalize_text", "exclude_value")
STAGE = dict(dedup_latest=1, dedup_first=1, filter_file=2, exclude_value=2, quarantine_invalid=2, try_parse=3, default_fill=3,
             real_div=3, zero_guard=3, round2=3, normalize_text=3)
# the strong conventional baseline's fixed engineer-sensible order (Phase 3 BASELINE_ORDER + the two new operators last)
BASELINE_ORDER = ("try_parse", "quarantine_invalid", "dedup_latest", "filter_file", "zero_guard", "real_div", "round2",
                  "dedup_first", "default_fill", "normalize_text", "exclude_value")


def _replace(e, pred, fn):
    if isinstance(e, list):
        if pred(e):
            return fn(e)
        return [e[0]] + [_replace(x, pred, fn) for x in e[1:]]
    return e


def map_exprs(spec, fn):
    """Apply fn to every output / group-key expression (the stage-3 slots)."""
    s = copy.deepcopy(spec)
    s["outputs"] = [[n, fn(x)] for n, x in s["outputs"]]
    if s.get("group"):
        s["group"] = [s["group"][0], fn(s["group"][1])]
    return s


def used_cols(spec):
    out = []
    for slot, _, x in ir.exprs(spec):
        if slot in ("outputs", "group"):
            for c in ir.cols_in(x):
                if c not in out:
                    out.append(c)
    return out


def _add_filter(spec, f):
    s = copy.deepcopy(spec)
    s["filter"] = f if not s.get("filter") else ["and", s["filter"], f]
    return s


def pclass(op, prm):
    """The parameter CLASS of an edit (what an ambiguity choice is about, independent of column names)."""
    if op == "filter_file":
        _, cmp, val = prm.split(" ", 2)
        return cmp + (":sub" if json.loads(val)[0] == "sub" else ":file")
    if op == "default_fill":
        return "str" if "='" in prm else "num"
    return "-"


def candidates(op, spec, dom):
    """All parameterisations of `op` on `spec` -> [(spec', param description)]. dom: the investigation's value domain."""
    out = []
    used = used_cols(spec)
    cols = [c for c in dom.header if c != "id"]
    if op == "try_parse":
        for c in used:
            s = map_exprs(spec, lambda x: _replace(x, lambda e: e[0] == "cast_int" and e[1] == ["col", c], lambda e: ["try_int", e[1]]))
            if s != spec:
                out.append((s, c))
    elif op == "quarantine_invalid":
        for c in used:
            if c not in dom.int_like:
                continue
            q = ["valid_int", ["col", c]]
            s = copy.deepcopy(spec)
            old = s.get("quarantine")
            s["quarantine"] = ["not", q] if not old else ["not", ["and", ["not", old], q]]
            out.append((s, c))
    elif op == "default_fill":
        for c in used:
            if c in dom.int_like:
                for v in dom.consts_num:
                    s = map_exprs(spec, lambda x: _replace(x, lambda e: e[0] in ("cast_int", "try_int") and e[1] == ["col", c],
                                                           lambda e: ["coalesce", ["try_int", e[1]], ["lit", v]]))
                    if s != spec:
                        out.append((s, f"{c}={v}"))
            elif c in dom.text_cols:
                for v in dom.consts_str:
                    s = map_exprs(spec, lambda x: _replace(x, lambda e: e[0] in ("col", "norm_text") and ir.cols_in(e) == [c],
                                                           lambda e: ["coalesce", ["nullif_empty", e], ["lit", v]]))
                    if s != spec:
                        out.append((s, f"{c}='{v}'"))
    elif op == "real_div":
        s = map_exprs(spec, lambda x: _replace(x, lambda e: e[0] == "div", lambda e: ["div_real"] + e[1:]))
        if s != spec:
            out.append((s, ""))
    elif op == "zero_guard":
        s = map_exprs(spec, lambda x: _replace(x, lambda e: e[0] in ("div", "div_real") and e[2][0] != "nullif_zero",
                                               lambda e: [e[0], e[1], ["nullif_zero", e[2]]]))
        if s != spec:
            out.append((s, ""))
    elif op == "round2":
        for i, (n, x) in enumerate(spec["outputs"]):
            if x[0] != "round2" and any(m[0] in ("div", "div_real") for m in ir.walk(x)):
                s = copy.deepcopy(spec)
                s["outputs"][i] = [n, ["round2", x]]
                out.append((s, n))
    elif op == "dedup_latest" and not spec.get("dedup"):
        for k, o in itertools.permutations(cols, 2):
            if o in dom.int_like and k not in dom.unique_cols:
                s = copy.deepcopy(spec)
                s["dedup"] = dict(key=k, order=["cast_int", ["col", o]])
                out.append((s, f"{k} by {o}"))
    elif op == "dedup_first" and not spec.get("dedup"):
        for k in cols:
            if k not in dom.unique_cols:
                s = copy.deepcopy(spec)
                s["dedup"] = dict(key=k)
                out.append((s, k))
    elif op == "filter_file":
        vals = [["file", f, k] for (f, k) in dom.files]
        vals += [["sub", ["file", f1, k1], ["file", f2, k2]] for (f1, k1), (f2, k2) in itertools.permutations(dom.files, 2)
                 if f1 == f2]
        for c in cols:
            if c not in dom.int_like or c not in dom.num_range:
                continue
            lo, hi = dom.num_range[c]
            for v in vals:
                t = ir.ev(v, {}, dom.state)
                if not (lo - 1 <= t <= hi + 1):          # a threshold outside the observed range is vacuous on the evidence
                    continue
                for cmp in ("gt", "ge"):
                    out.append((_add_filter(spec, [cmp, ["cast_int", ["col", c]], v]), f"{c} {cmp} {json.dumps(v)}"))
    elif op == "normalize_text":
        for c in used:
            if c in dom.text_cols:
                if any(m[0] == "norm_text" and ir.cols_in(m) == [c] for _, _, x in ir.exprs(spec) for m in ir.walk(x)):
                    continue
                s = map_exprs(spec, lambda x: _replace(x, lambda e: e == ["col", c], lambda e: ["norm_text", e]))
                if s != spec:
                    out.append((s, c))
    elif op == "exclude_value":
        for c in cols:
            if c in dom.text_cols and 1 < len(dom.domain[c]) <= 4:
                for v in sorted(dom.domain[c]):
                    out.append((_add_filter(spec, ["ne", ["col", c], ["lit", v]]), f"{c}<>'{v}'"))
    return out


def replay(spec, edits, dom):
    """Re-apply an edit list [(op, prm)] by parameter description; an edit that no longer applies is skipped."""
    for op, prm in edits:
        nxt = next((s for s, p in candidates(op, spec, dom) if p == prm), None)
        if nxt is not None:
            spec = nxt
    return spec
