"""Phase 10E shared verifier fixes for the Phase 6-10C procedure substrate (NOT LOCKED; a HUMAN repair given identically to
every arm that imports it; not NEXUS learning). Installed on top of de_phase10c.fixes10c.

DEFECT (Phase 10C Draw C target 96088, H1; scripts/agi10e_c96088.py on the consumed target, fixed specifications only): the
submission was wrong on hidden batch 2. The Phase 10C report attributed it to the window-end filter sitting BEFORE the CDC
dedup. That attribution was WRONG: the Phase 4 IR applies a stage's dedup before its filter, and moving the predicate to the
window stage leaves the hidden outputs identical (V0 = V1). The actual cause: the workspace declares the window as
batch.json {start, end}; the candidate implements `evt_time < end` but references `start` nowhere, and no visible row lies
before `start`, so no check could fail. Adding the window-start predicate alone makes the hidden batches verify (V2).
FIX 1  UNREFERENCED STATE PARAMETER: a candidate that reads some key of a workspace state file but leaves a sibling key of the
       SAME file unreferenced by every stage is not submitted (abstain: 'state parameter untested'). A declared parameter that a
       partial implementation ignores is an untested requirement; the visible batch cannot tell.
FIX 2  SHADOW-SEQUENCE WITNESS across stages (the owner's requested check, generalised to the stage form): whenever a stage j
       filters rows and a LATER stage k keeps the latest row per key (dedup with an ORDER BY), a boundary key with two versions
       (r_old, r_new) is synthesised from the visible header such that r_new is the latest and fails the predicate while r_old
       satisfies it. If filtering in stage j and filtering after stage k's dedup disagree on it (r_old resurrected), the
       candidate is not submitted. Within one stage the Phase 4 IR already filters AFTER the dedup, so the check concerns stage
       boundaries only.
Both fixes can cost completions (conservative); both are counted in every arm that uses them."""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

from nexus.de_phase4 import ir as IR4, world as W4
from nexus.de_phase8 import procedure8 as PR8
from nexus.de_phase10c import fixes10c  # noqa: F401  (installs the Phase 10C barrier first)

_PREV = PR8.ACTIONS["submit_or_abstain"]


def state_refs(specs):
    out = set()
    for s in specs:
        for slot in ("outputs", "filter", "quarantine", "group", "dedup"):
            v = s.get(slot)
            if v is None:
                continue
            for n in IR4.walk(v if isinstance(v, list) else [v.get("order")] if isinstance(v, dict) else []):
                if n and n[0] == "file":
                    out.add((n[1], n[2]))
    return out


def unreferenced_state(state, specs):
    """Sibling keys of a referenced state file that no stage references: [(file, key)]."""
    refs = state_refs(specs)
    files = {f for f, _ in refs}
    return sorted((f, k) for f in files for k in (state.get(f) or {}) if (f, k) not in refs)


def _boundary_values(cond, state):
    """Values a predicate distinguishes: its literals and the state values it reads, each -1 / 0 / +1 when numeric."""
    out = []
    for n in IR4.walk(cond):
        v = n[1] if n and n[0] == "lit" else (state.get(n[1]) or {}).get(n[2]) if n and n[0] == "file" else None
        if v is None:
            continue
        out.append(str(v))
        if isinstance(v, int) or (isinstance(v, str) and v.lstrip("-").isdigit()):
            out += [str(int(v) - 1), str(int(v) + 1)]
    return out


def _assign(cond, cols, state, want, pool):
    cs = sorted(set(IR4.cols_in(cond)))
    vals = [pool.get(c, []) + _boundary_values(cond, state) + ["", "__w__"] for c in cs]
    for combo in itertools.islice(itertools.product(*vals), 600):
        r = dict(zip(cs, combo))
        try:
            ok = IR4.ev(cond, dict(r, __rowid=0), state) is True
        except Exception:                                         # noqa: BLE001
            continue
        if ok == want:
            return r
    return None


def _run(specs, rows, state):
    cur = rows
    for s in specs:
        cur = [{c: ("" if v is None else str(v)) for c, v in r.items() if c != "__rowid"} for r in IR4.interpret(s, cur, state)["clean"]]
    return sorted(json.dumps(r, sort_keys=True) for r in cur)


def stale_witness(specs, header, state, pool=None):
    """[(j, k)] stage pairs where stage j's filter resurrects an older version through stage k's latest-per-key dedup."""
    pool = pool or {}
    bad = []
    for j, sj in enumerate(specs):
        if not sj.get("filter"):
            continue
        for k in range(j + 1, len(specs)):
            dd = specs[k].get("dedup")
            if not dd or dd.get("order") is None:
                continue
            key, ocs = dd["key"], sorted(set(IR4.cols_in(dd["order"])))
            if not ocs or set(IR4.cols_in(sj["filter"])) & ({key} | set(ocs)):
                continue
            new_v, old_v = _assign(sj["filter"], header, state, False, pool), _assign(sj["filter"], header, state, True, pool)
            if new_v is None or old_v is None:
                continue
            base = {c: (pool.get(c) or ["1"])[0] for c in header}
            r_old, r_new = dict(base, **old_v), dict(base, **new_v)
            r_old[ocs[0]], r_new[ocs[0]] = "1", "2"
            moved = copy.deepcopy(specs[: k + 1])
            f = moved[j].pop("filter")
            moved[k]["filter"] = f if not moved[k].get("filter") else ["and", moved[k]["filter"], f]
            try:
                a, b = _run(specs[j: k + 1], [r_old, r_new], state), _run(moved[j: k + 1], [r_old, r_new], state)
            except Exception:                                     # noqa: BLE001
                continue
            if a != b:
                bad.append((j, k))
    return bad


def check(project, specs):
    """-> abstain reason or None."""
    state = W4.state_of(project["ws"])
    un = unreferenced_state(state, specs)
    if un:
        return f"state parameter untested: {un} declared but referenced by no stage"
    header, rows = W4.read_csv(sorted((Path(project["ws"]) / "data").glob("*.csv"))[0])
    pool = {c: sorted({r[c] for r in rows if r.get(c) not in (None, "")})[:5] for c in header}
    sw = stale_witness(specs, header, state, pool)
    if sw:
        return f"latest-state witness: a filter resurrects an older version through a later dedup at stages {sw}"
    return None


def a_submit(st):
    _PREV(st)
    if st.decision and st.decision.get("kind") == "submit":
        why = check(st.p, PR8.chosen_specs(st))
        if why:
            st.decision = dict(kind="abstain", reason=why)
            st.log("decide", dict(fixes10e=why), st.decision)


a_submit._phase8_original = getattr(_PREV, "_phase8_original", _PREV)
PR8.ACTIONS["submit_or_abstain"] = a_submit
