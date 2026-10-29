"""Phase 6 skill INVENTION (NOT LOCKED): NEXUS builds its own repair methods from experience.

1 ABSTRACT  every verified source repair path [(stage, op, parameter)] is rewritten into ROLE form: each column parameter
            becomes the set of observable roles that column plays in that stage's input (integer-like, dirty, text,
            low-cardinality, unique, has duplicates, compared to a state value, an output column); constants and state-file
            references stay literal (file / key names are part of the operational interface, e.g. watermark.json)
2 INVENT    stage-local sub-sequences (length 1..max_len) that recur in >= min_support DIFFERENT solved projects are
            anti-unified into a SKILL: the shared operator sequence, the intersection of the parameter roles, and the
            stage evidence that preceded them (precondition = features shared by all supporting projects)
3 ADMIT     a candidate skill is admitted only by the corrected rule (admission5) on separate admission projects
4 BIND      at use time a skill is grounded in an UNSEEN project: for each abstract edit, the concrete candidates of that
            operator whose columns play the same roles in that stage are enumerated (rebinding to a new schema); skills
            whose precondition matches a stage's evidence are CHAINED across the stages of a multi-stage pipeline
No rule in this module mentions a paradigm, a family or a column name: what a skill does is learned."""
from __future__ import annotations

import itertools
import json

from nexus.de_phase4 import ir
from nexus.de_phase6 import engines6 as E


def roles(dom, col, fine=True):
    if col not in dom.header:
        return ("absent",)
    r = {"int" if col in dom.int_like else "text"}
    if col in dom.dirty_cols:
        r.add("dirty")
    vals = [x.get(col, "") for x in dom.rows]
    if col in dom.unique_cols:
        r.add("unique")
    elif len(set(vals)) < len(vals):
        r.add("dupes")
    if fine:
        if col in dom.text_cols and 1 < len(set(vals)) <= 4:
            r.add("lowcard")
        if col in dom.num_range and dom.files:
            lo, hi = dom.num_range[col]
            if any(lo <= ir.ev(["file", f, k], {}, dom.state) <= hi for f, k in dom.files):
                r.add("state_range")
        if any(not str(v).strip() for v in vals):
            r.add("blanks")
    return tuple(sorted(r))


def abstract_edit(op, prm, dom, fine=True):
    """(op, abstract parameter) for one concrete edit."""
    if op in ("dedup_latest",):
        k, o = prm.split(" by ")
        return (op, ("key", roles(dom, k, fine)), ("order", roles(dom, o, fine)))
    if op in ("filter_file", "filter_cmp"):
        c, cmp, v = prm.split(" ", 2)
        return (op, ("col", roles(dom, c, fine)), ("cmp", cmp), ("ref", v))
    if op == "col_compare":
        a, cmp, b = prm.split(" ")
        return (op, ("a", roles(dom, a, fine)), ("cmp", cmp), ("b", roles(dom, b, fine)))
    if op == "exclude_value":
        c, v = prm.split("<>")
        return (op, ("col", roles(dom, c, fine)), ("value", v))
    if op == "default_fill":
        c, v = prm.split("=", 1)
        return (op, ("col", roles(dom, c, fine)), ("value", v))
    if prm in ("", None):
        return (op,)
    return (op, ("col", roles(dom, prm, fine)))


def _matches(a_abs, cand_abs):
    if a_abs[0] != cand_abs[0] or len(a_abs) != len(cand_abs):
        return False
    for x, y in zip(a_abs[1:], cand_abs[1:]):
        if x[0] != y[0]:
            return False
        if isinstance(x[1], tuple):
            if not set(x[1]) <= set(y[1]):
                return False
        elif x[1] != y[1]:
            return False
    return True


def record(lib_src, project_id, inv, path, start_features, fine=True):
    """Remember a VERIFIED repair in role form (stage evidence + abstract edits per stage)."""
    from nexus.de_phase6 import pipeline6 as P6
    specs = [s for s in inv.legacy]
    per_stage = {}
    for k, op, prm in path:
        dom = inv.dom(k, specs)
        per_stage.setdefault(k, []).append(abstract_edit(op, prm, dom, fine))
        specs = P6.replay(inv, [(k, op, prm)], specs)
    for k, seq in per_stage.items():
        lib_src.append(dict(project=project_id, stage_features=sorted(start_features), edits=seq))


def invent(lib_src, min_support=2, max_len=2):
    """Anti-unify recurring stage-local edit sub-sequences across >= min_support DIFFERENT projects into candidate skills."""
    groups = {}
    for rec in lib_src:
        seq = [_tup(e) for e in rec["edits"]]             # memory re-loaded from JSON stores tuples as lists
        for L in range(1, min(max_len, len(seq)) + 1):
            for i in range(len(seq) - L + 1):
                sub = tuple(seq[i:i + L])
                key = json.dumps([[e[0]] + [list(x) if isinstance(x, tuple) else x for x in e[1:]] for e in sub], default=list)
                key = json.dumps([[e[0]] + [[x[0]] for x in e[1:]] for e in sub])                  # operator / slot shape
                groups.setdefault(key, []).append((rec, sub))
    out = []
    for key, items in groups.items():
        projects = {r["project"] for r, _ in items}
        if len(projects) < min_support:
            continue
        sub0 = items[0][1]
        unified = []
        for j, e in enumerate(sub0):
            slots = []
            for s_i, x in enumerate(e[1:]):
                vals = [it[1][j][1 + s_i] for it in items]
                if isinstance(x[1], tuple):
                    inter = set(vals[0][1])
                    for v in vals[1:]:
                        inter &= set(v[1])
                    slots.append((x[0], tuple(sorted(inter))))
                else:
                    common = {v[1] for v in vals}
                    if len(common) > 1:
                        break
                    slots.append((x[0], x[1]))
            else:
                unified.append(tuple([e[0]] + slots))
                continue
            unified = None
            break
        if not unified:
            continue
        pre = set(items[0][0]["stage_features"])
        for r, _ in items[1:]:
            pre &= set(r["stage_features"])
        out.append(dict(edits=[list(e) for e in unified], pre=sorted(pre), support=sorted(projects), origin="invented: anti-unified from "
                        f"{len(projects)} verified source repairs", uses=0))
    out.sort(key=lambda s: (-len(s["support"]), -len(s["edits"])))
    return out


def _tup(e):
    return tuple([e[0]] + [tuple([x[0], tuple(x[1]) if isinstance(x[1], list) else x[1]]) for x in e[1:]])


def bind(skill, inv, specs, k, cap=6):
    """Concrete edit paths for stage k that ground the skill in THIS project's schema (rebinding)."""
    from nexus.de_phase6 import pipeline6 as P6
    paths = [([], specs)]
    for e in skill["edits"]:
        e = _tup(e)
        nxt = []
        for path, sp in paths:
            dom = inv.dom(k, sp)
            for s2, prm in E.candidates(e[0], sp[k], dom):
                if _matches(e, abstract_edit(e[0], prm, dom)):
                    sp2 = list(sp)
                    sp2[k] = s2
                    nxt.append((path + [(k, e[0], prm)], sp2))
                    if len(nxt) >= cap:
                        break
        paths = nxt[:cap]
        if not paths:
            return []
    return [p for p, _ in paths]


class SkillProposer:
    """skills_mod for pipeline6.search: retrieved skills are bound per stage and chained across stages."""

    def __init__(self, match=0.5, chain=True):
        self.match, self.chain = match, chain

    def proposals(self, skills, inv, root, ev0, cap=12):
        feats = set(ev0["features"])
        out, chained = [], []
        for k in range(len(inv.stages)):
            stage_paths = []
            for sk in skills.values():
                pre = set(sk["pre"])
                if pre and len(pre & feats) / len(pre) < self.match:
                    continue
                for p in bind(sk, inv, root["specs"], k):
                    stage_paths.append(p)
                    sk["uses"] = sk.get("uses", 0) + 1
            out += stage_paths[:4]
            if stage_paths:
                chained.append(stage_paths[0])
        if self.chain and len(chained) > 1:                  # chain_library_skills: one bound skill per stage, composed
            out.insert(0, [e for p in chained for e in p])
        return out[:cap]
