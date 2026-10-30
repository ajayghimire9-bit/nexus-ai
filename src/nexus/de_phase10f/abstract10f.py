"""Phase 10F abstraction rules (NOT LOCKED).

Abs_current   de_phase7.skills7.invent7 unchanged (Phase 10E): demonstrations are clustered by operator skeleton + literals and every
              role slot of the candidate is the INTERSECTION over the WHOLE cluster. One disagreeing demonstration therefore
              strips a role from the macro for everyone: in Phase 10E rep0 (and rep1 at step 100) 2 dream witnesses that partitioned
              by the arrival column instead of the key removed `ckey` from add_partition's key slot, and the weakened macro
              failed admission (no modular progress), while 6-7 wake repairs agreed on (ckey, arrival).
Abs_subgroup  Abs_current's candidates PLUS role-consistent SUBGROUP candidates, proposed alongside (never instead of) the broader
              generalisation; the unchanged admission gate decides between them. Generic (no operator, role or family is named):
                for every skeleton cluster, each distinct per-demonstration role signature s (the tuple of role sets over the
                cluster's role slots) seeds the subgroup G(s) = every demonstration whose signature contains s slot-wise (the
                maximal compatible subset); its candidate takes the slot-wise intersection over G(s) only.
              A subgroup candidate is kept iff
                - its support has >= K_MIN distinct VERIFIED source projects (wake repairs, valley bridges, contract-guarded dream
                  witnesses; '#partial' best-partials do not count),
                - it is strictly more specific than the whole-cluster candidate (some slot keeps a role the global intersection
                  lost), with no empty role slot,
                - Delta MDL > 0 (de_phase10.memory10.delta_mdl, the learner's existing gate, re-checked at admission).
Candidates are ordered as invent7 orders them (support desc, length desc; a subgroup follows its broader parent at equal support)."""
from __future__ import annotations

import json

from nexus.de_phase6 import skills6 as SK
from nexus.de_phase7 import skills7 as SK7
from nexus.de_phase10 import memory10 as MEM

K_MIN = 3


def clusters(lib_src, max_len=3):
    """invent7's clustering, exposed: (shape, literals) -> [(record, sub-sequence)]."""
    out = {}
    for rec in lib_src:
        seq = [SK._tup(e) for e in rec["edits"]]
        for L in range(1, min(max_len, len(seq)) + 1):
            for i in range(len(seq) - L + 1):
                sub = tuple(seq[i:i + L])
                shape = json.dumps([[e[0]] + [x[0] for x in e[1:]] for e in sub])
                literals = json.dumps([[x[1] for x in e[1:] if not isinstance(x[1], tuple)] for e in sub])
                out.setdefault((shape, literals), []).append((rec, sub))
    return out


def slots(sub):
    return [(j, s) for j, e in enumerate(sub) for s, x in enumerate(e[1:]) if isinstance(x[1], tuple)]


def signature(sub):
    return tuple(frozenset(sub[j][1 + s][1]) for j, s in slots(sub))


def unify(items):
    sub0 = items[0][1]
    unified = []
    for j, e in enumerate(sub0):
        sl = []
        for s_i, x in enumerate(e[1:]):
            if isinstance(x[1], tuple):
                inter = set(x[1])
                for _, sub in items[1:]:
                    inter &= set(sub[j][1 + s_i][1])
                sl.append((x[0], tuple(sorted(inter))))
            else:
                sl.append((x[0], x[1]))
        unified.append([e[0]] + [list(v) for v in sl])
    return unified


def verified_projects(items):
    return {r["project"].split("#")[0] for r, _ in items if "#partial" not in r["project"]}


def subgroup_candidates(lib_src, max_len=3, k_min=K_MIN, n_library=0):
    out, seen = [], set()
    for (shape, lits), items in clusters(lib_src, max_len).items():
        if len(items[0][1]) < 2 or len({r["project"].split("#")[0] for r, _ in items}) < 2:
            continue
        whole = SK7.canonical(unify(items))
        for s in sorted({signature(sub) for _, sub in items}, key=lambda x: json.dumps([sorted(v) for v in x])):
            grp = [(r, sub) for r, sub in items if all(a >= b for a, b in zip(signature(sub), s))]
            vp = verified_projects(grp)
            if len(vp) < k_min:
                continue
            unified = unify(grp)
            can = SK7.canonical(unified)
            if can == whole or can in seen or any(isinstance(x[1], list) and not x[1] for e in unified for x in e[1:]):
                continue
            projects = {r["project"].split("#")[0] for r, _ in grp}
            if MEM.delta_mdl(len(unified), len(projects), n_library) <= 0:
                continue
            seen.add(can)
            pre = set(grp[0][0]["stage_features"])
            for r, _ in grp[1:]:
                pre &= set(r["stage_features"])
            sk = dict(edits=unified, pre=sorted(pre), support=sorted(projects), canonical=can, uses=0,
                      from_partial=any("#partial" in r["project"] for r, _ in grp), subgroup=True, parent=whole,
                      origin=f"invented (Abs_subgroup): role-consistent subgroup of {len(grp)} of {len(items)} instances, {len(vp)} verified source projects")
            sk["novelty"] = SK7.novelty_class(sk)
            out.append(sk)
    return out


def invent(lib_src, min_support=2, max_len=3, rule="current", n_library=0):
    base = SK7.invent7(lib_src, min_support, max_len)
    if rule == "current":
        return base
    known = {c["canonical"] for c in base}
    extra = [c for c in subgroup_candidates(lib_src, max_len, n_library=n_library) if c["canonical"] not in known]
    out = base + extra
    out.sort(key=lambda s: (-len(s["support"]), -len(s["edits"])))          # stable: a parent precedes its subgroup at equal support
    return out
