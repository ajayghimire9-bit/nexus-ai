"""Phase 13 program-aware input proposals and Shadow-Edge Version Spaces (NOT LOCKED; engineering machinery, not NEXUS learning).

WHY (Phase 12 report, section 6): active disambiguation can only choose among candidates the synthesizer produced, and the frozen
Phase 12 rule spent no query when a single candidate (typically the passthrough or COUNT(*) shape) remained. Phase 13 therefore:

  1  PROGRAM-AWARE PROPOSALS  inputs are synthesised directly from the candidate ASTs (program_facts): boundary constants of every
                              column/constant comparison (the constant itself and +-1 nudges, or a fresh non-matching string), NULLs in
                              every column the programs read / group / partition / order / join on (in place and in an appended copy
                              row), unmatched join keys on each join side (a fresh key and a NULL key), multi-row duplicate keys (copies
                              of a row keeping the COMPLETE key tuple - every group / partition / join key column - and altering the
                              other numerics) and ordering ties. This goes beyond resampling observed rows: every proposal edits a
                              visible batch exactly where the candidate programs are sensitive.
  2  SHADOW-EDGE VERSION SPACE  every synthesized candidate contributes single-edit SHADOW neighbours along structural edges:
                              passthrough <-> coalesce(col, k), COUNT(*) <-> COUNT(col) (col ranges over EVERY column of the fold's base,
                              group keys included: COUNT(*) and COUNT(g) differ on a NULL group), join-kind swaps, strict <-> loose
                              comparisons and rank-direction flips. A shadow is admitted iff it reproduces every observation so far and
                              is falsified only by an executed observation. There is NO permanent lock: a passthrough or COUNT(*) fit
                              never suppresses its coalesce / COUNT(col) alternatives, so a lone candidate can still be challenged.
  3  WORK METERING            every consistency check is one full check and every proposal execution one probe evaluation, charged to
                              the synth12 strict Budget (CappedCounter raises at the exact cap increment). A member that could not be
                              checked because the budget ran out is marked 'unchecked' and is never treated as consistent.
  4  FEATURES                 score_proposals emits task-conditioned Delta-State features (FEATURE_NAMES, fixed order) for selector13;
                              shortcut_tags exposes the shortcut shapes (passthrough, count_star, join kinds, comparison strictness) used
                              by counterfactual regret auditing.
  5  COMPLETENESS             score_proposals returns a ScoredList whose .complete is False when PROBE_CAP or a budget refusal stopped
                              it before the whole requested menu was evaluated (reason 'probe_cap' / 'budget'; every incomplete scoring
                              is also recorded on the version space). disagreement_check treats an incomplete scoring as UNRESOLVED:
                              an unscored proposal could still separate the live members, so it is never evidence of resolution and
                              submission must abstain.

The learner's view only: visible batches, answered queries, the output schema and the candidates' own executions. Never reference
programs, generator paths, family labels or hidden batches."""
from __future__ import annotations

import copy
import dataclasses
import random
from collections import Counter

from nexus.de_phase11 import core11 as C
from nexus.de_phase12 import synth12 as S

SHADOW_CAP, PROP_CAP, PROBE_CAP = 48, 64, 4000
PROPOSAL_KINDS = ("null", "boundary", "unmatched", "dupkey", "tie", "generic")
TASK_FLAGS = ("t_join", "t_fold", "t_rank", "t_filter", "t_count_star", "t_passthrough")
BASE_FEATURES = ("bias",) + tuple(f"k_{k}" for k in PROPOSAL_KINDS) + (
    "splits", "n_classes_norm", "exp_elim", "leader_isolation", "cand_split", "shadow_split", "err_frac",
    "d_rows", "d_nulls", "d_cells") + TASK_FLAGS + ("t_single", "t_nshadow")
CROSS_FEATURES = tuple(f"k_{k}*{t}" for k in PROPOSAL_KINDS for t in TASK_FLAGS)
FEATURE_NAMES = BASE_FEATURES + CROSS_FEATURES

REL_HEADS = {"rel", "filter", "rank", "fold", "join", "union", "map"}
SC_HEADS = {"col", "const", "isnull", "not", "cmp", "arith", "and", "or", "branch", "cast", "json", "call"}
STRICT_FLIP = {"lt": "le", "le": "lt", "gt": "ge", "ge": "gt"}
_EXEC_ERRORS = (C.RelErr, C.TypeErr, C.Unsupported, TypeError, KeyError, IndexError, ValueError, ArithmeticError, AttributeError)


# ------------------------------------------------------------------ relation helpers (core11 Rel built defensively)
def _rows(R):
    return [tuple(r) for r in R.rows]


def _ci(R, c):
    cols = list(R.cols)
    return cols.index(c) if c in cols else None


def _set(row, i, v):
    return row[:i] + (v,) + row[i + 1:]


def _with_rows(R, rows):
    """A relation with R's columns / types and the given rows (constructor first; copies only as a last resort)."""
    rows = list(rows) if isinstance(R.rows, list) else tuple(rows)
    if hasattr(R, "_replace"):
        return R._replace(rows=rows)
    if dataclasses.is_dataclass(R):
        try:
            return dataclasses.replace(R, rows=rows)
        except (TypeError, ValueError):
            pass
    for make in (lambda: type(R)(R.cols, R.types, rows), lambda: type(R)(cols=R.cols, types=R.types, rows=rows)):
        try:
            new = make()
        except Exception:                                          # noqa: BLE001 - unknown constructor signature, try the next
            continue
        if tuple(new.cols) == tuple(R.cols) and [tuple(r) for r in new.rows] == [tuple(r) for r in rows]:
            return new
    new = copy.copy(R)
    for k in list(getattr(new, "__dict__", {})):
        if "bag" in k or "cache" in k:
            delattr(new, k)
    new.rows = rows
    return new


def env_key(env):
    return tuple((rn, tuple(env[rn].cols), tuple(sorted(tuple(C.enc(v) for v in r) for r in env[rn].rows))) for rn in sorted(env))


def _fresh(env, t, salt):
    """A value of type t absent from every column of type t in env (so a fresh join key matches nothing)."""
    vals = {r[i] for R in env.values() for i, ct in enumerate(R.types) if ct == t for r in R.rows if r[i] is not None}
    if t == C.INT:
        nums = [v for v in vals if isinstance(v, int) and not isinstance(v, bool)]
        return (max(nums) if nums else 9000) + 97 + salt
    if t == C.NUM:
        nums = [float(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return (max(nums) if nums else 9000.0) + 97.5 + salt
    if t == C.STR:
        s = f"nx_fresh_{salt}"
        while s in vals:
            s += "_"
        return s
    return None


def _alter(row, R, keep):
    """Copy of row with every non-kept numeric value shifted (keeps every key column; makes duplicate-key rows distinguishable)."""
    out = list(row)
    for j, (c, t) in enumerate(zip(R.cols, R.types)):
        if c in keep or out[j] is None or isinstance(out[j], bool):
            continue
        if t == C.INT and isinstance(out[j], int):
            out[j] = out[j] + 7
        elif t == C.NUM and isinstance(out[j], (int, float)):
            out[j] = float(out[j]) + 7.25
    return tuple(out)


# ------------------------------------------------------------------ program facts read from candidate ASTs
def _is_col(e):
    return isinstance(e, tuple) and len(e) == 2 and e[0] == "col" and isinstance(e[1], str)


def _is_const(e):
    return isinstance(e, tuple) and len(e) == 3 and e[0] == "const"


def _coalesced(e):
    """The column of a coalesce shape branch(isnull(col), const, col), else None."""
    if (isinstance(e, tuple) and len(e) == 4 and e[0] == "branch" and isinstance(e[1], tuple) and len(e[1]) == 2
            and e[1][0] == "isnull" and _is_col(e[1][1]) and _is_const(e[2]) and e[3] == e[1][1]):
        return e[3]
    return None


def _base_rels(x, out=None):
    out = set() if out is None else out
    if isinstance(x, tuple) and x:
        if x[0] == "rel" and len(x) == 2 and isinstance(x[1], str):
            out.add(x[1])
        else:
            for y in x:
                _base_rels(y, out)
    return out


def empty_facts():
    """groups: flat set of every group column (task flags / NULL proposals); group_keys: the COMPLETE group-key tuples."""
    return dict(reads=set(), nullchk=set(), bounds=set(), joins=set(), groups=set(), group_keys=set(), ranks=set(), rels=set(),
                passthrough=set(), count_star=False, filters=0)


def program_facts(ast, facts=None):
    """Structural edge facts of one expanded program (merged into `facts` when given)."""
    f = empty_facts() if facts is None else facts
    f.setdefault("group_keys", set())

    def sc(e):
        if not isinstance(e, tuple) or not e or not isinstance(e[0], str):
            return
        h = e[0]
        if _is_col(e):
            f["reads"].add(e[1])
            return
        if h == "const":
            return
        if h == "cmp" and len(e) == 4:
            a, b = e[2], e[3]
            if _is_col(a) and _is_const(b):
                f["bounds"].add((a[1], e[1], b[1], b[2]))
            elif _is_col(b) and _is_const(a):
                f["bounds"].add((b[1], e[1], a[1], a[2]))
        if h == "isnull" and len(e) == 2 and _is_col(e[1]):
            f["nullchk"].add(e[1][1])
        for y in e[1:]:
            if isinstance(y, tuple) and y and y[0] in SC_HEADS:
                sc(y)

    def rel(x):
        if not isinstance(x, tuple) or not x or x[0] not in REL_HEADS:
            return
        h = x[0]
        if h == "rel":
            f["rels"].add(x[1])
        elif h == "map" and len(x) == 3:
            rel(x[1])
            for o, e in x[2]:
                if _is_col(e):
                    f["passthrough"].add(e[1])
                sc(e)
        elif h == "fold" and len(x) == 4:
            rel(x[1])
            f["groups"] |= set(x[2])
            if x[2]:
                f["group_keys"].add(tuple(x[2]))
            for meas in x[3]:
                if meas[1] == "count_star":
                    f["count_star"] = True
                if len(meas) > 2 and meas[2] is not None:
                    sc(meas[2])
        elif h == "rank" and len(x) >= 4:
            rel(x[1])
            orders = tuple(e[1] for e, _ in x[3] if _is_col(e))
            f["ranks"].add((tuple(x[2]), orders))
            for e, _ in x[3]:
                sc(e)
        elif h == "join" and len(x) == 6:
            rel(x[2])
            rel(x[3])
            f["joins"].add((x[1], tuple(x[4]), tuple(x[5]), tuple(sorted(_base_rels(x[2]))), tuple(sorted(_base_rels(x[3])))))
            f["reads"] |= set(x[4]) | set(x[5])
        elif h == "filter" and len(x) == 3:
            f["filters"] += 1
            rel(x[1])
            sc(x[2])
        elif h == "union":
            for y in x[1:]:
                rel(y)
    rel(ast)
    return f


def task_flags(facts):
    return dict(t_join=float(bool(facts["joins"])), t_fold=float(bool(facts["groups"]) or facts["count_star"]),
                t_rank=float(bool(facts["ranks"])), t_filter=float(facts["filters"] > 0), t_count_star=float(facts["count_star"]),
                t_passthrough=float(bool(facts["passthrough"])))


def shortcut_tags(ast):
    """Shortcut shapes a program commits to (regret auditing demotes the ones whose acceptance was later falsified)."""
    tags = set()

    def walk(x):
        if not isinstance(x, tuple) or not x:
            return
        h = x[0]
        if h == "map" and len(x) == 3:
            for _, e in x[2]:
                if _is_col(e):
                    tags.add("passthrough")
                elif _coalesced(e) is not None:
                    tags.add("coalesce")
        elif h == "fold" and len(x) == 4:
            for meas in x[3]:
                tags.add("count_star" if meas[1] == "count_star" else f"agg:{meas[1]}")
        elif h == "join" and len(x) == 6:
            tags.add(f"join:{x[1]}")
        elif h == "cmp" and len(x) == 4 and x[1] in STRICT_FLIP:
            tags.add("strict_cmp" if x[1] in ("lt", "gt") else "loose_cmp")
        for y in x:
            walk(y)
    walk(ast)
    return tags


# ------------------------------------------------------------------ shadow edges (single structural edits)
def _sc_edits(e):
    out = []
    if not isinstance(e, tuple) or not e or e[0] not in SC_HEADS:
        return out
    if e[0] == "cmp" and len(e) == 4 and e[1] in STRICT_FLIP:
        out.append((("cmp", STRICT_FLIP[e[1]], e[2], e[3]), f"cmp:{e[1]}->{STRICT_FLIP[e[1]]}"))
    for j, y in enumerate(e):
        if j and isinstance(y, tuple) and y and y[0] in SC_HEADS:
            for ny, edge in _sc_edits(y):
                out.append((e[:j] + (ny,) + e[j + 1:], edge))
    return out


def _count_cols(base, keys, ctx):
    """COUNT(col) alternatives of a COUNT(*): every column of the fold's base, non-key columns first, then the group keys
    (COUNT(*) and COUNT(key) differ exactly on a NULL key, so the keys are admissible alternatives too)."""
    cols = list(ctx["cols"](base) or [])
    return [c for c in cols if c not in keys] + [c for c in cols if c in keys]


def _rel_edits(x, ctx):
    out = []
    if not isinstance(x, tuple) or not x or x[0] not in REL_HEADS:
        return out
    h = x[0]
    if h == "map" and len(x) == 3:
        base, items = x[1], x[2]
        for i, (o, e) in enumerate(items):
            t, alts = ctx["out_types"].get(o), []
            if _is_col(e) and t is not None:
                for k in ctx["consts"].get(t, ()):
                    alts.append((("branch", ("isnull", e), ("const", k, t), e), "passthrough->coalesce"))
            col = _coalesced(e)
            if col is not None:
                alts.append((col, "coalesce->passthrough"))
            alts += _sc_edits(e)
            for ne, edge in alts:
                out.append((("map", base, items[:i] + ((o, ne),) + items[i + 1:]), edge))
        out += [(("map", nb, items), edge) for nb, edge in _rel_edits(base, ctx)]
    elif h == "fold" and len(x) == 4:
        base, keys, meas = x[1], x[2], x[3]
        for i, m in enumerate(meas):
            alts = []
            if m[1] == "count_star":
                alts += [((m[0], "count", ("col", c)), "count_star->count_col") for c in _count_cols(base, keys, ctx)]
            elif m[1] == "count":
                alts.append(((m[0], "count_star", None), "count_col->count_star"))
            if len(m) > 2 and m[2] is not None:
                alts += [((m[0], m[1], ne), edge) for ne, edge in _sc_edits(m[2])]
            for nm, edge in alts:
                out.append((("fold", base, keys, meas[:i] + (nm,) + meas[i + 1:]), edge))
        out += [(("fold", nb, keys, meas), edge) for nb, edge in _rel_edits(base, ctx)]
    elif h == "join" and len(x) == 6:
        for k in ctx["join_kinds"]:
            if k != x[1]:
                out.append((("join", k) + x[2:], f"join:{x[1]}->{k}"))
        out += [(("join", x[1], nb) + x[3:], edge) for nb, edge in _rel_edits(x[2], ctx)]
        out += [(("join", x[1], x[2], nb) + x[4:], edge) for nb, edge in _rel_edits(x[3], ctx)]
    elif h == "rank" and len(x) >= 4:
        for i, (e, desc) in enumerate(x[3]):
            oe = x[3][:i] + ((e, not desc),) + x[3][i + 1:]
            out.append((("rank", x[1], x[2], oe) + x[4:], "rank:direction_flip"))
        out += [(("rank", nb) + x[2:], edge) for nb, edge in _rel_edits(x[1], ctx)]
    elif h == "filter" and len(x) == 3:
        out += [(("filter", x[1], np_), edge) for np_, edge in _sc_edits(x[2])]
        out += [(("filter", nb, x[2]), edge) for nb, edge in _rel_edits(x[1], ctx)]
    elif h == "union" and len(x) == 3:
        out += [(("union", nb, x[2]), edge) for nb, edge in _rel_edits(x[1], ctx)]
        out += [(("union", x[1], nb), edge) for nb, edge in _rel_edits(x[2], ctx)]
    return out


# ------------------------------------------------------------------ version space
class VersionSpace:
    """Synthesized candidates plus their admissible shadow neighbours, falsified only by executed observations."""

    def __init__(self, task, candidates, lib=None, budget=None, shadows=True, shadow_cap=SHADOW_CAP):
        self.task, self.lib, self.budget = task, dict(lib or {}), budget
        self.out_schema = tuple(task["out_schema"])
        self.outn = [n for n, _ in self.out_schema]
        self.out_types = dict(self.out_schema)
        self.obs = [(k, task["inputs"][k], task["expected"][k]) for k in S.VIS] + list(task.get("extra_obs", []))
        self.es = {k: v.schema() for k, v in self.obs[0][1].items()}
        self.shadows_enabled, self.shadow_cap = shadows, shadow_cap
        self.members, self.keys, self.work, self.exhausted, self.history = [], set(), Counter(), None, []
        self.last_scoring, self.incomplete_scorings = None, []
        self._colcache = {}
        self.add_candidates(candidates)

    # ---- metering
    def _charge(self, key):
        """Charge one unit; False (and exhausted recorded) when the strict budget refuses it."""
        if self.exhausted:
            return False
        try:
            if self.budget is not None:
                self.budget.c[key] += 1
        except S.WorkExhausted as e:
            self.exhausted = str(e)
            if self.budget is not None:
                self.budget.exhausted = str(e)
            return False
        self.work[key] += 1
        return True

    def scoring_complete(self):
        """True when the latest score_proposals call evaluated every requested proposal (None before any scoring)."""
        return None if self.last_scoring is None else bool(self.last_scoring["complete"])

    # ---- execution
    def run(self, ast, env):
        """Projected output bag fingerprint of ast on env ('ERR' / 'SCHEMA' on failure)."""
        try:
            got = C.run(ast, env)
            if set(got.cols) != set(self.outn) or len(got.cols) != len(self.outn):
                return ("SCHEMA",)
            P = C.project_like(got, self.outn)
            return frozenset(Counter(tuple(C.enc(v) for v in r) for r in P.rows).items())
        except _EXEC_ERRORS:
            return ("ERR",)

    def _matches(self, ast, env, exp):
        try:
            got = C.run(ast, env)
            if set(got.cols) != set(self.outn) or len(got.cols) != len(self.outn):
                return False
            return bool(C.same_bag(C.project_like(got, self.outn), exp))
        except _EXEC_ERRORS:
            return False

    def _verify(self, ast):
        """('ok' | 'falsified' | 'unchecked', failing observation name). One full check covers every observation."""
        if not self._charge("full_checks"):
            return "unchecked", None
        for name, env, exp in self.obs:
            if not self._matches(ast, env, exp):
                return "falsified", name
        return "ok", None

    def _cols(self, base):
        if base not in self._colcache:
            try:
                self._colcache[base] = list(C.run(base, self.obs[0][1]).cols)
            except _EXEC_ERRORS:
                self._colcache[base] = []
        return self._colcache[base]

    def _consts(self):
        """Coalesce defaults per output type: 0 / 0.0 and the small (<= 4) value sets of each output column observed."""
        out = {C.INT: {0}, C.NUM: {0.0}, C.STR: set(), C.BOOL: set()}
        for j, (o, t) in enumerate(self.out_schema):
            vals = {r[j] for _, _, E in self.obs for r in C.project_like(E, self.outn).rows if r[j] is not None}
            if len(vals) <= 4 and t in out:
                out[t] |= vals
        return {t: sorted(v, key=repr) for t, v in out.items() if v}

    # ---- membership
    def _add(self, ast, program, origin, edge=None, parent=None, provenance=None):
        if ast in self.keys:
            return None
        self.keys.add(ast)
        status, by = self._verify(ast)
        m = dict(id=len(self.members), ast=ast, program=program, origin=origin, edge=edge, parent=parent, provenance=provenance,
                 status="alive" if status == "ok" else status, falsified_by=by, tags=sorted(shortcut_tags(ast)))
        self.members.append(m)
        return m

    def add_candidates(self, candidates):
        """Add synthesized candidates (synth12 candidate dicts or programs), re-verified on every current observation."""
        for c in candidates or []:
            if isinstance(c, dict):
                prog, ast, prov = c.get("program"), c.get("expanded"), c.get("provenance")
                ast = ast if ast is not None else C.expand(prog, self.lib)
            else:
                prog, prov = c, None
                try:
                    ast = C.expand(c, self.lib)
                except (KeyError, IndexError):
                    continue
            self._add(ast, prog, "candidate", provenance=prov)
        if self.shadows_enabled:
            self._expand_shadows()

    def _expand_shadows(self):
        ctx = dict(out_types=self.out_types, consts=self._consts(), cols=self._cols,
                   join_kinds=tuple(getattr(C, "JOIN_KINDS", ("inner", "left"))))
        n = sum(1 for m in self.members if m["origin"] == "shadow")
        for m in [m for m in self.members if m["origin"] == "candidate" and m["status"] == "alive"]:
            for ast, edge in _rel_edits(m["ast"], ctx):
                if n >= self.shadow_cap or self.exhausted:
                    return
                if ast in self.keys:
                    continue
                try:
                    C.rel_schema(ast, self.es)
                    if C.size(ast) > S.SIZE_LIMIT:
                        continue
                except (C.TypeErr, C.Unsupported, KeyError, ValueError, IndexError, TypeError):
                    continue
                if self._add(ast, ast, "shadow", edge=edge, parent=m["id"]) is not None:
                    n += 1

    def alive(self, origin=None):
        return [m for m in self.members if m["status"] == "alive" and (origin is None or m["origin"] == origin)]

    def leader(self, prior=None):
        """Preferred live member: highest prior (if given), then synthesized before shadow, then smaller size, then id."""
        live = self.alive()
        if not live:
            return None
        return min(live, key=lambda m: (-(prior(m) if prior else 0.0), m["origin"] != "candidate", C.size(m["ast"]), m["id"]))

    def facts(self):
        f = empty_facts()
        for m in self.alive():
            program_facts(m["ast"], f)
        return f

    def observe(self, name, env, expected):
        """Record an answered query; falsify every live member that does not reproduce it (one full check each)."""
        self.obs.append((name, env, expected))
        falsified, survivors = [], []
        for m in self.alive():
            if not self._charge("full_checks"):
                m["status"] = "unchecked"
                continue
            if self._matches(m["ast"], env, expected):
                survivors.append(m["id"])
            else:
                m["status"], m["falsified_by"] = "falsified", name
                falsified.append(m["id"])
        rep = dict(name=name, falsified=falsified, survivors=survivors,
                   falsified_edges=sorted({self.members[i]["edge"] for i in falsified if self.members[i]["edge"]}),
                   falsified_tags=sorted({t for i in falsified for t in self.members[i]["tags"]}))
        self.history.append(rep)
        return rep

    def extra_obs(self):
        """Answered queries in synth12's task['extra_obs'] format (for resumed synthesis)."""
        return [o for o in self.obs if o[0] not in S.VIS]

    def summary(self):
        return dict(members=len(self.members), alive=len(self.alive()), alive_candidates=len(self.alive("candidate")),
                    alive_shadows=len(self.alive("shadow")), falsified=sum(m["status"] == "falsified" for m in self.members),
                    unchecked=sum(m["status"] == "unchecked" for m in self.members), work=dict(self.work), exhausted=self.exhausted,
                    scoring_incomplete=len(self.incomplete_scorings), last_scoring=self.last_scoring)


# ------------------------------------------------------------------ proposals
def _mk(kind, base, env, rn, new_rows, detail):
    R = env[rn]
    old = _rows(R)
    new_env = dict(env)
    new_env[rn] = _with_rows(R, new_rows)
    changed = sum(1 for a, b in zip(old, new_rows) for u, v in zip(a, b) if C.enc(u) != C.enc(v))
    added = new_rows[len(old):]
    nulls_old = sum(v is None for r in old for v in r)
    nulls_new = sum(v is None for r in new_rows for v in r)
    return dict(kind=kind, base=base, rel=rn, detail=detail, env=new_env,
                delta=dict(rows_added=len(new_rows) - len(old), cells_changed=changed + sum(len(r) for r in added),
                           nulls_added=max(0, nulls_new - nulls_old), base_rows=len(old)))


def _group_key_tuples(f):
    """Complete group-key tuples (falls back to single-column tuples for facts built without group_keys)."""
    gk = f.get("group_keys")
    if gk:
        return sorted({tuple(k) for k in gk}, key=repr)
    return [(k,) for k in sorted(f.get("groups", ()))]


def _props_for_base(base, env, f):
    out, salt = [], 0
    rels_with = lambda c: [rn for rn in sorted(env) if _ci(env[rn], c) is not None and env[rn].rows]   # noqa: E731
    rels_with_all = lambda cs: [rn for rn in sorted(env) if env[rn].rows and all(_ci(env[rn], c) is not None for c in cs)]  # noqa: E731
    # boundary constants of every comparison
    for c, op, v, t in sorted(f["bounds"], key=repr):
        for rn in rels_with(c):
            R, i = env[rn], _ci(env[rn], c)
            rows = _rows(R)
            if t == C.INT and isinstance(v, int) and not isinstance(v, bool):
                vals = [v, v - 1, v + 1]
            elif t == C.NUM and isinstance(v, (int, float)):
                vals = [v, float(v) - 0.5, float(v) + 0.5]
            elif t == C.STR:
                salt += 1
                vals = [v, _fresh(env, C.STR, salt)]
            else:
                vals = [v]
            if R.types[i] != t and not (C.num_like(R.types[i]) and C.num_like(t)):
                continue
            for val in vals:
                out.append(_mk("boundary", base, env, rn, [_set(rows[0], i, val)] + rows[1:], dict(col=c, op=op, value=val)))
    # NULLs in every column the programs touch
    touched = set(f["reads"]) | f["nullchk"] | f["groups"] | f["passthrough"] | {c for ks, os in f["ranks"] for c in ks + os}
    for c in sorted(touched):
        for rn in rels_with(c):
            R, i = env[rn], _ci(env[rn], c)
            rows = _rows(R)
            j = next((n for n, r in enumerate(rows) if r[i] is not None), None)
            if j is None:
                continue
            out.append(_mk("null", base, env, rn, rows[:j] + [_set(rows[j], i, None)] + rows[j + 1:], dict(col=c, mode="in_place")))
            out.append(_mk("null", base, env, rn, rows + [_set(rows[j], i, None)], dict(col=c, mode="appended_copy")))
    # unmatched join keys on each side; multi-row duplicate join keys
    for kind, lk, rk, lrels, rrels in sorted(f["joins"], key=repr):
        for side, keys, rels in (("left", lk, lrels), ("right", rk, rrels)):
            if not keys:
                continue
            for rn in [r for r in rels if r in env and env[r].rows and _ci(env[r], keys[0]) is not None]:
                R, i = env[rn], _ci(env[rn], keys[0])
                rows = _rows(R)
                salt += 1
                fv = _fresh(env, R.types[i], salt)
                if fv is not None:
                    out.append(_mk("unmatched", base, env, rn, rows + [_set(_alter(rows[0], R, set(keys)), i, fv)],
                                   dict(side=side, key=keys[0], value=fv)))
                out.append(_mk("unmatched", base, env, rn, rows + [_set(rows[0], i, None)], dict(side=side, key=keys[0], value=None)))
                out.append(_mk("dupkey", base, env, rn, rows + [_alter(rows[0], R, set(keys))], dict(side=side, key=keys[0])))
    # duplicate group keys: the COMPLETE key tuple is preserved (altered measures, and an exact copy)
    for keys in _group_key_tuples(f):
        kd = keys[0] if len(keys) == 1 else keys
        for rn in rels_with_all(keys):
            R = env[rn]
            rows = _rows(R)
            out.append(_mk("dupkey", base, env, rn, rows + [_alter(rows[0], R, set(keys))], dict(key=kd, mode="altered")))
            out.append(_mk("dupkey", base, env, rn, rows + [rows[0]], dict(key=kd, mode="exact")))
    # partition duplicates and ordering ties
    for keys, orders in sorted(f["ranks"], key=repr):
        for rn in rels_with_all(keys):
            R = env[rn]
            rows = _rows(R)
            out.append(_mk("dupkey", base, env, rn, rows + [_alter(rows[0], R, set(keys))], dict(key=keys, mode="partition")))
            if orders and all(_ci(R, c) is not None for c in orders):
                out.append(_mk("tie", base, env, rn, rows + [_alter(rows[0], R, set(keys) | set(orders))], dict(key=keys, order=orders)))
    return out


def _dedupe(lists, cap, bases):
    """Round-robin across bases, dropping proposals identical to a base batch or to an earlier proposal."""
    seen, out = {env_key(e) for _, e in bases}, []
    for i in range(max((len(x) for x in lists), default=0)):
        for lst in lists:
            if i < len(lst):
                k = env_key(lst[i]["env"])
                if k not in seen:
                    seen.add(k)
                    lst[i]["id"] = len(out)
                    out.append(lst[i])
                    if len(out) >= cap:
                        return out
    return out


def base_envs(task):
    return [(k, task["inputs"][k]) for k in S.VIS]


def program_aware_proposals(vs, bases=None, cap=PROP_CAP):
    """Inputs synthesised from the live members' ASTs (candidates and shadows), on every base batch."""
    bases = bases or base_envs(vs.task)
    f = vs.facts()
    return _dedupe([_props_for_base(b, env, f) for b, env in bases], cap, bases)


def generic_proposals(bases, cap=PROP_CAP):
    """Static AST-blind menu (Fixed / Random controls): duplicate the first row; NULL / zero / fresh value in the first row's columns."""
    lists = []
    for b, env in bases:
        out = []
        for rn in sorted(env):
            R = env[rn]
            rows = _rows(R)
            if not rows:
                continue
            out.append(_mk("generic", b, env, rn, rows + [rows[0]], dict(op="dup_first")))
            for i, (c, t) in enumerate(zip(R.cols, R.types)):
                if rows[0][i] is not None:
                    out.append(_mk("generic", b, env, rn, [_set(rows[0], i, None)] + rows[1:], dict(op="null_first", col=c)))
                if t in (C.INT, C.NUM):
                    out.append(_mk("generic", b, env, rn, [_set(rows[0], i, 0 if t == C.INT else 0.0)] + rows[1:], dict(op="zero_first", col=c)))
        lists.append(out)
    return _dedupe(lists, cap, bases)


# ------------------------------------------------------------------ scoring and choice
class ScoredList(list):
    """Scored proposals plus completeness metadata. complete=False means the requested menu was NOT fully evaluated (reason
    'probe_cap' or 'budget'); the missing proposals were dropped, never guessed, and could still separate the live members."""

    def __init__(self, items=(), requested=0, complete=True, reason=None, probes=0):
        super().__init__(items)
        self.requested, self.complete, self.reason, self.probes = int(requested), bool(complete), reason, int(probes)

    @property
    def dropped(self):
        return max(0, self.requested - len(self))


def _record_scoring(vs, out, requested, reason, used):
    res = ScoredList(out, requested=requested, complete=reason is None, reason=reason, probes=used)
    vs.last_scoring = dict(requested=requested, scored=len(out), complete=res.complete, reason=reason, probes=used)
    if not res.complete:
        vs.incomplete_scorings.append(dict(vs.last_scoring))
        vs.work["scoring_incomplete"] += 1                         # bookkeeping only (not a charged work unit)
    return res


def score_proposals(vs, props, leader=None, probe_cap=PROBE_CAP):
    """Execute every live member on every proposal (one probe evaluation each, strictly metered) and attach the output partition and
    the Delta-State / task-conditioned features. Proposals not evaluated before a cap are dropped (never guessed); the returned
    ScoredList records whether the whole menu was scored (.complete / .reason) and the version space records every incomplete run."""
    props = list(props or [])
    live = vs.alive()
    leader = leader or vs.leader()
    flags = task_flags(vs.facts())
    n_shadow = sum(m["origin"] == "shadow" for m in live)
    single = float(sum(m["origin"] == "candidate" for m in live) <= 1)
    out, used = [], 0
    if vs.exhausted and props:
        return _record_scoring(vs, out, len(props), "budget", used)
    for p in props:
        if used + len(live) > probe_cap:
            return _record_scoring(vs, out, len(props), "probe_cap", used)
        outs = {}
        for m in live:
            if not vs._charge("probe_evals"):
                return _record_scoring(vs, out, len(props), "budget", used)
            used += 1
            outs[m["id"]] = vs.run(m["ast"], p["env"])
        classes = {}
        for mid, fp in outs.items():
            classes.setdefault(fp, []).append(mid)
        n = max(1, len(live))
        sizes = [len(v) for v in classes.values()]
        lfp = outs.get(leader["id"]) if leader else None
        lsize = len(classes.get(lfp, [])) if lfp is not None else n
        origin = {m["id"]: m["origin"] for m in live}
        cand_fps = {fp for mid, fp in outs.items() if origin[mid] == "candidate"}
        shadow_split = float(lfp is not None and any(origin[mid] == "shadow" and fp != lfp for mid, fp in outs.items()))
        d = p["delta"]
        feats = dict(bias=1.0, splits=float(len(classes) > 1), n_classes_norm=(len(classes) - 1) / n,
                     exp_elim=sum((s / n) * (1 - s / n) for s in sizes), leader_isolation=1.0 - lsize / n,
                     cand_split=float(len(cand_fps) > 1), shadow_split=shadow_split,
                     err_frac=sum(fp in (("ERR",), ("SCHEMA",)) for fp in outs.values()) / n,
                     d_rows=d["rows_added"] / (1 + d["base_rows"]), d_nulls=d["nulls_added"] / (1 + d["base_rows"]),
                     d_cells=d["cells_changed"] / (1 + d["base_rows"]), t_single=single, t_nshadow=min(1.0, n_shadow / 16), **flags)
        for k in PROPOSAL_KINDS:
            feats[f"k_{k}"] = float(p["kind"] == k)
            for t in TASK_FLAGS:
                feats[f"k_{k}*{t}"] = feats[f"k_{k}"] * flags[t]
        out.append(dict(p, outputs=outs, partition=sorted(classes.values()), features=feats))
    return _record_scoring(vs, out, len(props), None, used)


def disagreement_check(vs, props, leader=None, probe_cap=PROBE_CAP):
    """Submission-time resolution test over a proposal menu. unresolved=True when some scored proposal splits the live members OR
    the scoring was incomplete (probe cap / budget refusal / exhausted version space): an unscored proposal is never evidence that
    the admissible alternatives agree, so the caller must abstain. With <= 1 live member there is nothing to disagree with."""
    live = vs.alive()
    if len(live) <= 1:
        return dict(unresolved=bool(vs.exhausted), complete=not vs.exhausted, reason="budget" if vs.exhausted else None,
                    splitting=0, scored=0, requested=len(props or []), live=len(live), exhausted=vs.exhausted, scored_list=ScoredList())
    scored = score_proposals(vs, props, leader=leader, probe_cap=probe_cap)
    split = sum(len(s["partition"]) > 1 for s in scored)
    complete = scored.complete and not vs.exhausted
    reason = None if complete else (scored.reason or "budget")
    return dict(unresolved=bool(split) or not complete, complete=complete, reason=reason, splitting=split, scored=len(scored),
                requested=scored.requested, live=len(live), exhausted=vs.exhausted, scored_list=scored)


def feature_vector(features):
    return [float(features.get(k, 0.0)) for k in FEATURE_NAMES]


def uniform_weights():
    return {k: 1.0 for k in FEATURE_NAMES}


def choose(scored, mode="weighted", weights=None, rng=None):
    """fixed: first in menu order; random: uniform draw (seeded rng); weighted: argmax w . features (uniform weights = Untrained),
    ties broken by menu order. None when nothing was scored."""
    if not scored:
        return None
    if mode == "fixed":
        return scored[0]
    if mode == "random":
        return (rng or random.Random(0)).choice(scored)
    w = weights or uniform_weights()
    return max(enumerate(scored), key=lambda ip: (sum(w.get(k, 0.0) * v for k, v in ip[1]["features"].items()), -ip[0]))[1]


__all__ = ["FEATURE_NAMES", "PROPOSAL_KINDS", "TASK_FLAGS", "VersionSpace", "ScoredList", "program_facts", "task_flags",
           "shortcut_tags", "program_aware_proposals", "generic_proposals", "base_envs", "score_proposals", "disagreement_check",
           "feature_vector", "uniform_weights", "choose", "env_key", "empty_facts"]
