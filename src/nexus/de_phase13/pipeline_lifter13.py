"""Phase 13 out-of-sandbox SQL pipeline localisation and Sub-AST Localize-and-Lift repair (NOT LOCKED; engineering machinery).

WHAT THIS MODULE DOES
  1  SQL FRONT END          a tokenizer + recursive-descent parser for a documented SQL subset (SQLite dialect) -> core11 relational
                            ASTs: SELECT items | * FROM t [AS a] | (subquery) a, [INNER|LEFT|RIGHT|FULL] JOIN ... ON equi-keys (AND ...),
                            WHERE, GROUP BY with COUNT(*) / COUNT(e) / SUM / MIN / MAX, COALESCE / IFNULL, CASE WHEN .. ELSE .. END,
                            CAST(e AS type), JSON_EXTRACT(e, '$.k'), arithmetic, comparisons, IS [NOT] NULL, AND / OR / NOT, UNION ALL.
                            Scripts of `CREATE [TEMP] TABLE|VIEW name AS <query>;` statements become pipeline stages. Anything outside
                            the subset raises SqlUnsupported (never silently approximated; NVL is rejected: SQLite does not provide it).
                            QUALIFIED IDENTITY: core11 column references are unqualified, so every column reference (SELECT / WHERE /
                            GROUP BY) is RESOLVED against the FROM scope: over one relation the qualifier must name it; over a join the
                            column lists must be resolvable (cols_of / sample inputs) and the reference must name exactly ONE joined
                            relation that has the column, which must appear exactly once in the core11 join output. Ambiguous,
                            unresolvable or renamed references are REJECTED (never collapsed onto a same-named column). ON keys must
                            compare one column of each side.
  2  PARSE FIDELITY         sql_fidelity executes each stage's ORIGINAL SQL text natively on SQLite and compares it with core11 execution
                            of the parsed AST (one metered full check per comparison). FAIL-CLOSED: faithful only when at least one
                            comparison ran and EVERY required comparison agreed. 'disagree' / 'core_error' -> the parse provably differs
                            (repair_pipeline status 'unfaithful_parse'); 'native_error' / 'load_error' / 'unchecked' (budget refusal) ->
                            fidelity could not be established (status 'fidelity_unverified'). Either way the pipeline is NOT lifted.
  3  LOCALIZE               every stage is executed on its OBSERVED upstream outputs where they exist (observed outputs of working
                            stages are preserved ground truth), so each observed stage is independently 'verified' or 'broken'. The
                            first broken stage is localised; its unobserved ancestors form the suspect SPAN. Every comparison is one
                            metered full check; a localisation cut short by the budget is reported complete=False (never a pass).
  4  LIFT                   the broken stage (attempt 'stage'), then the stage with its suspect span inlined ('span'), then the span
                            with every available upstream relation offered ('widen') becomes a lifted task over only the relations it
                            reads. Working relational sub-ASTs of the stage are PRESERVED as pre-materialised inputs (nx_keepK) so the
                            atomic synthesizer can reuse them. Candidate repairs: generic single structural edits (the proposals13
                            shadow edges; no repair templates), then the synth12 atomic synthesizer (budget fork, 70 % of remaining).
                            Synthesized programs are COMPILED back by inlining the preserved sub-ASTs. repair_pipeline reports the
                            method of every repaired stage (repair_methods; edit_only / synthesized counts) so edit-menu successes are
                            never conflated with synthesis or learned-state-dependent successes.
  5  INVESTIGATE            candidates enter a proposals13 VersionSpace with shadow alternatives (no passthrough / COUNT(*) lock).
                            With an optional budgeted reference oracle, proposals that split the live members are queried. The QUERY
                            menu is the arm's (program-aware by default; `menu` injectable, e.g. an AST-blind static control) and so is
                            the choice rule. When every member is falsified, synthesis resumes once with the answered queries as
                            observations.
  6  EPISTEMIC SAFETY       with require_unique (default) the lift ABSTAINS while admissible members still disagree after the query
                            budget. The final resolution test uses ONE COMMON MENU FOR EVERY ARM, independent of the injected query
                            menu: the union of proposals13.program_aware_proposals and the static generic_proposals (identical to
                            runner13.investigate). So a static-menu arm cannot accept alternatives that AST-derived boundary / NULL /
                            unmatched-key probes would separate. An INCOMPLETE final scoring (probe cap / budget refusal: an unscored
                            proposal could still separate the members) also abstains (reason 'incomplete_scoring'). A held-out observed
                            batch (when >= 3 exist) must be reproduced before acceptance. Agreement on bounded probes is recorded as
                            agreement_unproven, never as proof.
  7  NATIVE GATE            with require_native (default = native) a member is accepted only if it COMPILES to SQL and the compiled SQL,
                            executed natively on SQLite, reproduces the expected output of EVERY observation the core11 repair was
                            verified on: every fit batch, the held-out batch AND every answered investigation query (one metered full
                            check each). A repaired pipeline counts as 'repaired' only when core11 end-to-end checks AND the native
                            pipeline check agree.
  8  METERING               repair_pipeline holds ONE strict synth12 Budget per pipeline row (full checks <= fc_cap <= 5000;
                            CappedCounter raises at the exact increment; the wall cap refuses further charges) and ONE query allowance,
                            shared by fidelity, localisation, lift, end-to-end and native checks. Each lift runs in a fork limited to
                            LIFT_SHARE of the remaining wall whose counters are merged back.

ATTRIBUTION  everything here is general machinery written by the engineering team. What NEXUS contributes autonomously in a lift
is only learned state passed in (library functions `lib`, learned production costs `costs`, a trained chooser / leader prior),
reported via each repair's provenance. Polars / PySpark / DuckDB front ends are NOT implemented in this module."""
from __future__ import annotations

import math
import re
import sqlite3
import time
from collections import Counter

from nexus.de_phase11 import core11 as C
from nexus.de_phase12 import synth12 as S
from nexus.de_phase13 import proposals13 as P

MAX_KEEP, MAX_FAULTS, SYNTH_SHARE, EDIT_CAP, QUERY_BUDGET, WIDEN_MAX = 2, 3, 0.7, 64, 2, 6
LIFT_WALL_S, LIFT_SHARE = 10.0, 0.85
ENGINES = ("core11", "sqlite")
RESOLUTION_MENU = "program_aware+static"
_EXEC_ERRORS = P._EXEC_ERRORS
_SQL_ERRORS = (sqlite3.Error, ValueError, OverflowError)
_UNFAITHFUL = ("disagree", "core_error")                           # the parsed AST provably does not mean what the SQL means


class SqlUnsupported(Exception):
    """A SQL construct outside the supported subset (or not compilable back to SQL)."""


class SqlParseError(SqlUnsupported):
    """Malformed SQL text."""


# ------------------------------------------------------------------ small helpers
def _run(ast, env):
    try:
        return C.run(ast, env)
    except _EXEC_ERRORS:
        return None


def _same(R, E):
    if R is None or E is None:
        return False
    try:
        if set(R.cols) != set(E.cols) or len(R.cols) != len(E.cols):
            return False
        return bool(C.same_bag(C.project_like(R, list(E.cols)), E))
    except _EXEC_ERRORS:
        return False


def _size(ast):
    try:
        return C.size(ast)
    except _EXEC_ERRORS:
        return None


def _charge(budget, key, n=1):
    """Charge n units to a strict synth12 budget; False (exhaustion recorded) when refused by a cap or the passed wall cap."""
    if budget is None:
        return True
    if budget.wall_bound():
        budget.exhausted = budget.exhausted or "wall"
        return False
    try:
        budget.c[key] += n
        return True
    except S.WorkExhausted as e:
        budget.exhausted = str(e)
        return False


def _merge(parent, child):
    """Merge a fork's counters back into its parent (forks start from the parent's counters, so max = parent + fork work)."""
    for k, v in child.c.items():
        if v > parent.c.get(k, 0):
            Counter.__setitem__(parent.c, k, v)


def _cols_fn(env):
    """cols_of(ast) -> output column names of ast on env (None when it does not run)."""
    cache = {}

    def cols_of(ast):
        try:
            if ast in cache:
                return cache[ast]
        except TypeError:
            pass
        R = _run(ast, env)
        out = list(R.cols) if R is not None else None
        try:
            cache[ast] = out
        except TypeError:
            pass
        return out
    return cols_of


def _inline(x, defs, depth=0):
    """Replace every ('rel', name) with name in defs by its (recursively inlined) definition."""
    if depth > 64:
        raise ValueError("inlining too deep (cyclic stage definitions?)")
    if isinstance(x, tuple) and x:
        if x[0] == "rel" and len(x) == 2 and isinstance(x[1], str):
            return _inline(defs[x[1]], defs, depth + 1) if x[1] in defs else x
        return tuple(_inline(y, defs, depth) for y in x)
    return x


def _rel_children(x):
    h = x[0]
    if h in ("map", "filter", "rank", "fold") and len(x) >= 2:
        return [x[1]]
    if h == "join" and len(x) == 6:
        return [x[2], x[3]]
    if h == "union":
        return list(x[1:])
    return []


def _sub_asts(region):
    """Relational sub-ASTs strictly below the root (base relations excluded), shallowest first."""
    out, seen, frontier, depth = [], set(), [region], 0
    while frontier:
        nxt = []
        for x in frontier:
            if not isinstance(x, tuple) or not x or x[0] not in P.REL_HEADS:
                continue
            if depth > 0 and x[0] != "rel" and x not in seen:
                seen.add(x)
                out.append((depth, x))
            nxt.extend(_rel_children(x))
        frontier, depth = nxt, depth + 1
    return out


# ------------------------------------------------------------------ SQL tokenizer / parser (subset -> core11 AST)
_TOKEN = re.compile(r"""(?P<ws>\s+|--[^\n]*)|(?P<str>'(?:[^']|'')*')|(?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)"""
                    r"""|(?P<qid>"(?:[^"]|"")*")|(?P<id>[A-Za-z_][A-Za-z_0-9]*)|(?P<op><=|>=|<>|!=|\|\||[=<>+\-*/%(),.;])""")
_KEYWORDS = {"SELECT", "FROM", "WHERE", "GROUP", "BY", "JOIN", "LEFT", "RIGHT", "FULL", "INNER", "OUTER", "ON", "AS", "UNION",
             "ALL", "AND", "OR", "NOT", "IS", "NULL", "CASE", "WHEN", "THEN", "ELSE", "END", "CAST", "TRUE", "FALSE", "ORDER",
             "LIMIT", "HAVING", "DISTINCT", "IN", "BETWEEN", "LIKE", "OVER", "WITH", "CROSS"}
_CMP_PARSE = {"=": "eq", "<>": "ne", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
_CMP_SQL = {"eq": "=", "ne": "<>", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
_ARITH_CANDS = {"+": ("add", "plus", "+"), "-": ("sub", "minus", "-"), "*": ("mul", "times", "mult", "*"), "/": ("div", "/"),
                "%": ("mod", "%")}
_TYPE_WORDS = {"INT": C.INT, "INTEGER": C.INT, "BIGINT": C.INT, "SMALLINT": C.INT, "REAL": C.NUM, "DOUBLE": C.NUM, "FLOAT": C.NUM,
               "NUMERIC": C.NUM, "DECIMAL": C.NUM, "TEXT": C.STR, "VARCHAR": C.STR, "STRING": C.STR, "CHAR": C.STR,
               "BOOLEAN": C.BOOL, "BOOL": C.BOOL}
_SQL_TYPE = {C.INT: "INTEGER", C.NUM: "REAL", C.STR: "TEXT", C.BOOL: "INTEGER"}
_JOIN_SQL = {"inner": "INNER JOIN", "left": "LEFT JOIN", "right": "RIGHT JOIN", "full": "FULL OUTER JOIN", "outer": "FULL OUTER JOIN"}


def _arith_name(sym):
    ops = tuple(C.ARITH_OPS)
    for n in _ARITH_CANDS.get(sym, ()):
        if n in ops:
            return n
    raise SqlUnsupported(f"arithmetic operator {sym!r} has no core11 counterpart")


def _arith_sym(name):
    for sym, cands in _ARITH_CANDS.items():
        if name in cands:
            return sym
    raise SqlUnsupported(f"arithmetic operator {name!r} not compilable to SQL")


def tokenize(sql):
    out, pos = [], 0
    while pos < len(sql):
        m = _TOKEN.match(sql, pos)
        if not m:
            raise SqlParseError(f"unexpected character {sql[pos]!r} at offset {pos}")
        pos, k = m.end(), m.lastgroup
        if k == "ws":
            continue
        v = m.group(k)
        if k == "str":
            v = v[1:-1].replace("''", "'")
        elif k == "qid":
            v = v[1:-1].replace('""', '"')
        out.append((k, v))
    return out


def _has_agg(e):
    return isinstance(e, tuple) and bool(e) and (e[0] == "__agg" or any(_has_agg(y) for y in e[1:] if isinstance(y, tuple)))


class _Parser:
    def __init__(self, sql, cols_of=None):
        self.toks, self.i, self.cols_of = tokenize(sql), 0, cols_of
        self.refs = []                                     # (qualifier | None, column) references of the current SELECT scope

    # ---- token plumbing
    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else ("eof", None)

    def is_kw(self, w, k=0):
        t = self.peek(k)
        return t[0] == "id" and t[1].upper() == w

    def accept_kw(self, w):
        if self.is_kw(w):
            self.i += 1
            return True
        return False

    def expect_kw(self, w):
        if not self.accept_kw(w):
            raise SqlParseError(f"expected {w}, got {self.peek()[1]!r}")

    def is_op(self, o, k=0):
        t = self.peek(k)
        return t[0] == "op" and t[1] == o

    def accept_op(self, o):
        if self.is_op(o):
            self.i += 1
            return True
        return False

    def expect_op(self, o):
        if not self.accept_op(o):
            raise SqlParseError(f"expected {o!r}, got {self.peek()[1]!r}")

    def is_ident(self, k=0):
        t = self.peek(k)
        return t[0] == "qid" or (t[0] == "id" and t[1].upper() not in _KEYWORDS)

    def ident(self):
        if self.is_ident():
            v = self.peek()[1]
            self.i += 1
            return v
        raise SqlParseError(f"expected identifier, got {self.peek()[1]!r}")

    # ---- statements
    def parse(self):
        if self.is_kw("WITH"):
            raise SqlUnsupported("WITH (CTE): split the CTEs into pipeline stages instead")
        q = self.query()
        self.accept_op(";")
        if self.peek()[0] != "eof":
            raise SqlParseError(f"unexpected trailing token {self.peek()[1]!r}")
        return q

    def query(self):
        q = self.select()
        while self.accept_kw("UNION"):
            if not self.accept_kw("ALL"):
                raise SqlUnsupported("UNION without ALL (set semantics)")
            q = ("union", q, self.select())
        return q

    def select(self):
        outer, self.refs = self.refs, []
        self.expect_kw("SELECT")
        if self.is_kw("DISTINCT"):
            raise SqlUnsupported("SELECT DISTINCT")
        items = self.select_list()
        self.expect_kw("FROM")
        src, scope = self.from_clause()
        base = src
        if self.accept_kw("WHERE"):
            p = self.expr()
            if _has_agg(p):
                raise SqlUnsupported("aggregate in WHERE")
            base = ("filter", base, p)
        keys = None
        if self.accept_kw("GROUP"):
            self.expect_kw("BY")
            keys = [self.keyref()]
            while self.accept_op(","):
                keys.append(self.keyref())
        for w in ("HAVING", "ORDER", "LIMIT", "OVER"):
            if self.is_kw(w):
                raise SqlUnsupported(w)
        self.resolve(self.refs, src, scope)
        self.refs = outer
        return self.build(items, base, keys)

    def resolve(self, refs, src, scope):
        """Check every column reference of this SELECT against its FROM scope (qualified identity is never silently dropped)."""
        if len(scope) == 1:
            alias = scope[0][0]
            for q, c in refs:
                if q is not None and q != alias:
                    raise SqlParseError(f"unknown relation qualifier {q!r} in {q}.{c}")
            return
        if not refs:
            return
        cols = {a: (self.cols_of(x) if self.cols_of else None) for a, x in scope}
        out = self.cols_of(src) if self.cols_of else None
        if out is None or any(v is None for v in cols.values()):
            raise SqlUnsupported("column references over a join need column resolution (sample inputs); qualifiers cannot be verified")
        for q, c in refs:
            ref = c if q is None else f"{q}.{c}"
            if q is not None:
                if q not in cols:
                    raise SqlParseError(f"unknown relation qualifier {q!r} in {ref}")
                if c not in cols[q]:
                    raise SqlParseError(f"{ref}: relation {q!r} has no column {c!r}")
            owners = [a for a, _ in scope if c in cols[a]]
            if not owners:
                raise SqlParseError(f"unknown column {ref!r}")
            if len(owners) > 1:
                raise SqlUnsupported(f"column {ref!r}: {c!r} exists in several joined relations {owners}; core11 joins do not keep "
                                     "qualified column identity")
            if list(out).count(c) != 1:
                raise SqlUnsupported(f"column {ref!r} is renamed or duplicated by the core11 join output")

    def select_list(self):
        if self.accept_op("*"):
            return "*"
        items = [self.item()]
        while self.accept_op(","):
            items.append(self.item())
        return items

    def item(self):
        e = self.expr()
        if self.accept_kw("AS"):
            a = self.ident()
        elif self.is_ident():
            a = self.ident()
        elif e[0] == "col":
            a = e[1]
        elif e[0] == "__agg" and e[1] == "count_star":
            a = "count"
        else:
            raise SqlParseError("select expression needs an alias (AS name)")
        return e, a

    def build(self, items, base, keys):
        if items == "*":
            if keys is not None:
                raise SqlUnsupported("SELECT * with GROUP BY")
            return base
        names = [a for _, a in items]
        if len(set(names)) != len(names):
            raise SqlParseError("duplicate output column name")
        if keys is None:
            if any(_has_agg(e) for e, _ in items):
                raise SqlUnsupported("aggregate without GROUP BY")
            return ("map", base, tuple((a, e) for e, a in items))
        meas, out = [], []
        for e, a in items:
            if e[0] == "__agg":
                if a in keys:
                    raise SqlUnsupported("measure alias equals a group key")
                if e[2] is not None and _has_agg(e[2]):
                    raise SqlUnsupported("nested aggregate")
                meas.append((a, e[1], e[2]))
                out.append((a, ("col", a)))
            elif e[0] == "col" and e[1] in keys:
                out.append((a, e))
            else:
                raise SqlUnsupported("select item is neither a GROUP BY key nor a top-level aggregate")
        return ("map", ("fold", base, tuple(keys), tuple(meas)), tuple(out))

    def from_clause(self):
        left, la = self.from_item()
        scope, lal = [(la, left)], {la}
        while True:
            if self.accept_kw("INNER"):
                self.expect_kw("JOIN")
                kind = "inner"
            elif self.is_kw("LEFT") or self.is_kw("RIGHT") or self.is_kw("FULL"):
                kind = self.peek()[1].lower()
                self.i += 1
                self.accept_kw("OUTER")
                self.expect_kw("JOIN")
            elif self.accept_kw("JOIN"):
                kind = "inner"
            elif self.is_op(",") or self.is_kw("CROSS"):
                raise SqlUnsupported("comma / cross join")
            else:
                break
            if kind not in tuple(C.JOIN_KINDS):
                raise SqlUnsupported(f"join kind {kind!r} not in core11")
            right, ra = self.from_item()
            if ra is None or any(a is None for a, _ in scope):
                raise SqlUnsupported("a derived table in a join needs an alias")
            if ra in lal:
                raise SqlParseError(f"duplicate relation alias {ra!r}")
            self.expect_kw("ON")
            lk, rk = [], []
            while True:
                a = self.colref()
                self.expect_op("=")
                b = self.colref()
                sa, sb = self._side(a, lal, ra, left, right), self._side(b, lal, ra, left, right)
                if sa == "r" or sb == "l":
                    a, b, sa, sb = b, a, sb, sa
                if sa != "l" or sb != "r":
                    raise SqlUnsupported("ON keys must compare one column of each join side (ambiguous, unresolvable or same-side "
                                         "reference)")
                lk.append(a[1])
                rk.append(b[1])
                if not self.accept_kw("AND"):
                    break
            left = ("join", kind, left, right, tuple(lk), tuple(rk))
            lal.add(ra)
            scope.append((ra, right))
        return left, scope

    def _side(self, ref, lal, ra, left, right):
        qual, col = ref
        lc = self.cols_of(left) if self.cols_of else None
        rc = self.cols_of(right) if self.cols_of else None
        if qual is not None:
            if qual == ra:
                side, cols = "r", rc
            elif qual in lal:
                side, cols = "l", lc
            else:
                raise SqlParseError(f"unknown relation qualifier {qual!r} in ON")
            if cols is not None and col not in cols:
                raise SqlParseError(f"{qual}.{col}: no such column")
            return side
        inl, inr = lc is not None and col in lc, rc is not None and col in rc
        if inl and not inr:
            return "l"
        if inr and not inl:
            return "r"
        return None

    def from_item(self):
        if self.accept_op("("):
            q = self.query()
            self.expect_op(")")
            self.accept_kw("AS")
            return q, (self.ident() if self.is_ident() else None)
        n = self.ident()
        if self.accept_kw("AS"):
            return ("rel", n), self.ident()
        if self.is_ident():
            return ("rel", n), self.ident()
        return ("rel", n), n

    def colref(self):
        a = self.ident()
        if self.accept_op("."):
            return a, self.ident()
        return None, a

    def keyref(self):
        ref = self.colref()
        self.refs.append(ref)
        return ref[1]

    # ---- expressions
    def expr(self):
        return self.or_()

    def or_(self):
        a = self.and_()
        while self.accept_kw("OR"):
            a = ("or", a, self.and_())
        return a

    def and_(self):
        a = self.not_()
        while self.accept_kw("AND"):
            a = ("and", a, self.not_())
        return a

    def not_(self):
        if self.accept_kw("NOT"):
            return ("not", self.not_())
        return self.cmp()

    def cmp(self):
        a = self.add()
        if self.accept_kw("IS"):
            neg = self.accept_kw("NOT")
            self.expect_kw("NULL")
            r = ("isnull", a)
            return ("not", r) if neg else r
        for w in ("IN", "BETWEEN", "LIKE"):
            if self.is_kw(w) or (self.is_kw("NOT") and self.is_kw(w, 1)):
                raise SqlUnsupported(w)
        t = self.peek()
        if t[0] == "op" and t[1] in _CMP_PARSE:
            self.i += 1
            return ("cmp", _CMP_PARSE[t[1]], a, self.add())
        return a

    def add(self):
        a = self.mul()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            sym = self.peek()[1]
            self.i += 1
            a = ("arith", _arith_name(sym), a, self.mul())
        return a

    def mul(self):
        a = self.unary()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/", "%"):
            sym = self.peek()[1]
            self.i += 1
            a = ("arith", _arith_name(sym), a, self.unary())
        return a

    def unary(self):
        if self.accept_op("-"):
            e = self.unary()
            if e[0] == "const" and isinstance(e[1], (int, float)) and not isinstance(e[1], bool):
                return ("const", -e[1], e[2])
            return ("arith", _arith_name("-"), ("const", 0, C.INT), e)
        if self.accept_op("+"):
            return self.unary()
        return self.primary()

    def primary(self):
        t = self.peek()
        if t[0] == "num":
            self.i += 1
            v = t[1]
            return ("const", float(v), C.NUM) if any(ch in v for ch in ".eE") else ("const", int(v), C.INT)
        if t[0] == "str":
            self.i += 1
            return ("const", t[1], C.STR)
        if self.accept_kw("TRUE"):
            return ("const", True, C.BOOL)
        if self.accept_kw("FALSE"):
            return ("const", False, C.BOOL)
        if self.is_kw("NULL"):
            raise SqlUnsupported("untyped NULL literal (use CAST(NULL AS type))")
        if self.accept_kw("CASE"):
            return self.case()
        if self.accept_kw("CAST"):
            return self.cast()
        if self.accept_op("("):
            if self.is_kw("SELECT"):
                raise SqlUnsupported("scalar subquery")
            e = self.expr()
            self.expect_op(")")
            return e
        if self.is_ident():
            if self.is_op("(", 1):
                return self.call()
            ref = self.colref()
            self.refs.append(ref)
            return ("col", ref[1])
        raise SqlParseError(f"unexpected token {t[1]!r}")

    def call(self):
        fn = self.ident().upper()
        self.expect_op("(")
        if fn == "COUNT":
            if self.accept_op("*"):
                self.expect_op(")")
                return ("__agg", "count_star", None)
            if self.is_kw("DISTINCT"):
                raise SqlUnsupported("COUNT(DISTINCT ...)")
            a = self.expr()
            self.expect_op(")")
            return ("__agg", "count", a)
        args = []
        if not self.is_op(")"):
            args.append(self.expr())
            while self.accept_op(","):
                args.append(self.expr())
        self.expect_op(")")
        if fn in ("SUM", "MIN", "MAX") and len(args) == 1:
            return ("__agg", fn.lower(), args[0])
        if (fn == "COALESCE" and len(args) >= 2) or (fn == "IFNULL" and len(args) == 2):
            out = args[-1]
            for a in reversed(args[:-1]):
                out = ("branch", ("isnull", a), out, a)
            return out
        if (fn == "JSON_EXTRACT" and len(args) == 2 and args[1][0] == "const" and isinstance(args[1][1], str)
                and args[1][1].startswith("$.")):
            return ("json", args[0], tuple(args[1][1][2:].split(".")))
        raise SqlUnsupported(f"function {fn}")

    def case(self):
        if not self.is_kw("WHEN"):
            raise SqlUnsupported("simple CASE (CASE x WHEN ...)")
        arms = []
        while self.accept_kw("WHEN"):
            c = self.expr()
            self.expect_kw("THEN")
            arms.append((c, self.expr()))
        if not self.accept_kw("ELSE"):
            raise SqlUnsupported("CASE without ELSE (untyped NULL)")
        out = self.expr()
        self.expect_kw("END")
        for c, v in reversed(arms):
            out = ("branch", c, v, out)
        return out

    def cast(self):
        self.expect_op("(")
        e = None if self.accept_kw("NULL") else self.expr()
        self.expect_kw("AS")
        tw = self.peek()
        if tw[0] != "id":
            raise SqlParseError("expected a type name in CAST")
        self.i += 1
        T = _TYPE_WORDS.get(tw[1].upper())
        if self.peek()[0] == "id" and self.peek()[1].upper() == "PRECISION":
            self.i += 1
        if self.accept_op("("):
            while not self.accept_op(")"):
                if self.peek()[0] == "eof":
                    raise SqlParseError("unterminated type parameters")
                self.i += 1
        self.expect_op(")")
        if T is None:
            raise SqlUnsupported(f"CAST target type {tw[1]!r}")
        return ("const", None, T) if e is None else ("cast", e, T)


def parse_sql(sql, cols_of=None):
    """SQL text (supported subset) -> core11 relational AST. cols_of(ast) -> column names resolves join keys and verifies column
    references over joins (required for any column reference over a join)."""
    return _Parser(sql, cols_of).parse()


def _split_statements(text):
    out, buf, i, q = [], [], 0, None
    while i < len(text):
        ch = text[i]
        if q:
            buf.append(ch)
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
            buf.append(ch)
        elif text.startswith("--", i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        elif ch == ";":
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
        else:
            buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


_CREATE = re.compile(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?'
                     r'("(?:[^"]|"")+"|[A-Za-z_][A-Za-z_0-9]*)\s+AS\s+(.*)$', re.S | re.I)


def split_script(text):
    """A SQL script of `CREATE [TEMP] TABLE|VIEW name AS <query>;` statements -> [(name, query_sql)]."""
    out = []
    for s in _split_statements(text):
        m = _CREATE.match(s)
        if not m:
            raise SqlParseError(f"not a CREATE TABLE|VIEW ... AS statement: {s[:60]!r}")
        name = m.group(1)
        if name.startswith('"'):
            name = name[1:-1].replace('""', '"')
        out.append((name, m.group(2).strip()))
    return out


# ------------------------------------------------------------------ core11 AST -> SQL (compile back to a native engine)
def _q(n):
    return '"' + str(n).replace('"', '""') + '"'


def _lit(v, t):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        f = float(v)
        if not math.isfinite(f):
            raise SqlUnsupported("non-finite literal")
        return repr(f) if (t == C.NUM or isinstance(v, float)) else repr(int(v))
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    raise SqlUnsupported(f"literal {v!r}")


class _SqlGen:
    def __init__(self, cols_of):
        self.cols_of, self.n = cols_of, 0

    def alias(self):
        self.n += 1
        return f"nx_t{self.n}"

    def cols(self, x):
        c = self.cols_of(x) if self.cols_of else None
        if not c:
            raise SqlUnsupported("column list needed (rank / join / union) but unavailable")
        return list(c)

    def rel(self, x):
        if not isinstance(x, tuple) or not x:
            raise SqlUnsupported(f"not a relational AST: {x!r}")
        h = x[0]
        if h == "rel" and len(x) == 2:
            return f"SELECT * FROM {_q(x[1])}"
        if h == "filter" and len(x) == 3:
            return f"SELECT * FROM ({self.rel(x[1])}) AS {self.alias()} WHERE {self.sc(x[2])}"
        if h == "map" and len(x) == 3:
            items = ", ".join(f"{self.sc(e)} AS {_q(o)}" for o, e in x[2])
            return f"SELECT {items} FROM ({self.rel(x[1])}) AS {self.alias()}"
        if h == "fold" and len(x) == 4:
            keys = [_q(k) for k in x[2]]
            sel = ", ".join(keys + [self.agg(m) for m in x[3]])
            grp = f" GROUP BY {', '.join(keys)}" if keys else ""
            return f"SELECT {sel} FROM ({self.rel(x[1])}) AS {self.alias()}{grp}"
        if h == "rank" and len(x) >= 4:
            cl = ", ".join(_q(c) for c in self.cols(x[1]))
            n = x[4] if len(x) > 4 else 1
            part = f"PARTITION BY {', '.join(_q(k) for k in x[2])} " if x[2] else ""
            order = ", ".join(f"{self.sc(e)} {'DESC' if d else 'ASC'}" for e, d in x[3])
            over = f"{part}ORDER BY {order}" if order else part.strip()
            rk = _q("nx_rk")
            inner, t1, t2 = self.rel(x[1]), self.alias(), self.alias()
            return f"SELECT {cl} FROM (SELECT *, RANK() OVER ({over}) AS {rk} FROM ({inner}) AS {t1}) AS {t2} WHERE {rk} <= {int(n)}"
        if h == "join" and len(x) == 6:
            kind, l, r, lk, rk = x[1:6]
            L, R, ta, tb = self.rel(l), self.rel(r), self.alias(), self.alias()
            on = " AND ".join(f"{ta}.{_q(a)} = {tb}.{_q(b)}" for a, b in zip(lk, rk))
            if kind in ("semi", "anti"):
                neg = "NOT " if kind == "anti" else ""
                return f"SELECT {ta}.* FROM ({L}) AS {ta} WHERE {neg}EXISTS (SELECT 1 FROM ({R}) AS {tb} WHERE {on})"
            jk = _JOIN_SQL.get(kind)
            if jk is None:
                raise SqlUnsupported(f"join kind {kind!r}")
            lc, rc, oc = self.cols(l), self.cols(r), self.cols(x)
            sel = []
            for c in oc:
                if c in lc:
                    sel.append(f"{ta}.{_q(c)} AS {_q(c)}")
                elif c in rc:
                    sel.append(f"{tb}.{_q(c)} AS {_q(c)}")
                else:
                    raise SqlUnsupported(f"join output column {c!r} renamed by core11")
            return f"SELECT {', '.join(sel)} FROM ({L}) AS {ta} {jk} ({R}) AS {tb} ON {on}"
        if h == "union" and len(x) == 3:
            cl = ", ".join(_q(c) for c in self.cols(x[1]))
            return f"SELECT {cl} FROM ({self.rel(x[1])}) AS {self.alias()} UNION ALL SELECT {cl} FROM ({self.rel(x[2])}) AS {self.alias()}"
        raise SqlUnsupported(f"relational head {h!r}")

    def agg(self, m):
        name, kind = m[0], m[1]
        e = m[2] if len(m) > 2 else None
        if kind == "count_star":
            return f"COUNT(*) AS {_q(name)}"
        if kind in ("count", "sum", "min", "max", "avg") and e is not None:
            return f"{kind.upper()}({self.sc(e)}) AS {_q(name)}"
        raise SqlUnsupported(f"aggregate {kind!r}")

    def sc(self, e):
        if not isinstance(e, tuple) or not e:
            raise SqlUnsupported(f"not a scalar AST: {e!r}")
        h = e[0]
        if h == "col":
            return _q(e[1])
        if h == "const":
            return _lit(e[1], e[2] if len(e) > 2 else None)
        if h == "isnull":
            return f"({self.sc(e[1])} IS NULL)"
        if h == "not":
            return f"(NOT {self.sc(e[1])})"
        if h == "cmp":
            op = _CMP_SQL.get(e[1])
            if op is None:
                raise SqlUnsupported(f"comparison {e[1]!r}")
            return f"({self.sc(e[2])} {op} {self.sc(e[3])})"
        if h == "arith":
            sym = _arith_sym(e[1])
            if sym == "/":
                return f"(CAST({self.sc(e[2])} AS REAL) / {self.sc(e[3])})"
            return f"({self.sc(e[2])} {sym} {self.sc(e[3])})"
        if h in ("and", "or"):
            return f"({self.sc(e[1])} {h.upper()} {self.sc(e[2])})"
        if h == "branch":
            return f"(CASE WHEN {self.sc(e[1])} THEN {self.sc(e[2])} ELSE {self.sc(e[3])} END)"
        if h == "cast":
            t = _SQL_TYPE.get(e[2])
            if t is None:
                raise SqlUnsupported(f"cast target {e[2]!r}")
            return f"CAST({self.sc(e[1])} AS {t})"
        if h == "json":
            return f"json_extract({self.sc(e[1])}, {_lit('$' + ''.join('.' + str(k) for k in e[2]), C.STR)})"
        raise SqlUnsupported(f"scalar head {h!r}")


def to_sql(ast, cols_of=None, lib=None):
    """Compile a core11 relational AST to SQL (SQLite dialect). cols_of(ast) supplies column lists for rank / join / union."""
    if lib:
        try:
            ast = C.expand(ast, lib)
        except (KeyError, IndexError) as e:
            raise SqlUnsupported(f"cannot expand library call: {e}") from e
    return _SqlGen(cols_of).rel(ast)


# ------------------------------------------------------------------ SQLite native execution
def _py(v):
    if isinstance(v, bool):
        return int(v)
    if v is None or isinstance(v, (int, float, str)):
        return v
    return str(v)


def _norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        f = float(v)
        return round(f, 9) if math.isfinite(f) else repr(f)
    return str(v)


def _load(con, env):
    for name, R in env.items():
        defs = ", ".join(f"{_q(c)} {_SQL_TYPE.get(t, '')}".strip() for c, t in zip(R.cols, R.types))
        con.execute(f"CREATE TABLE {_q(name)} ({defs})")
        if R.rows:
            marks = ", ".join("?" for _ in R.cols)
            con.executemany(f"INSERT INTO {_q(name)} VALUES ({marks})", [tuple(_py(v) for v in r) for r in R.rows])


def _bag_equal(names, rows, E):
    ec = list(E.cols)
    if len(names) != len(ec) or sorted(names) != sorted(ec):
        return False
    idx = [names.index(c) for c in ec]
    got = Counter(tuple(_norm(r[j]) for j in idx) for r in rows)
    want = Counter(tuple(_norm(v) for v in r) for r in E.rows)
    return got == want


def native_check(ast, env, expected=None, lib=None):
    """Run the compiled SQL of ast on SQLite over env and compare with `expected` (default: the core11 output)."""
    try:
        sql = to_sql(ast, _cols_fn(env), lib=lib)
    except SqlUnsupported as e:
        return dict(engine="sqlite", status="unsupported", detail=str(e)[:200], sql=None)
    if expected is None:
        expected = _run(ast, env)
        if expected is None:
            return dict(engine="sqlite", status="core_error", detail="core11 run failed", sql=sql)
    con = sqlite3.connect(":memory:")
    try:
        _load(con, env)
        cur = con.execute(sql)
        names, rows = [d[0] for d in cur.description], cur.fetchall()
    except _SQL_ERRORS as e:
        return dict(engine="sqlite", status="error", detail=str(e)[:200], sql=sql)
    finally:
        con.close()
    return dict(engine="sqlite", status="agree" if _bag_equal(names, rows, expected) else "disagree", detail=None, sql=sql)


# ------------------------------------------------------------------ pipelines
def _batches(batches):
    out = []
    for n, b in enumerate(batches or []):
        if isinstance(b, dict):
            out.append(dict(name=str(b.get("name", f"b{n}")), inputs=dict(b["inputs"]), observed=dict(b.get("observed") or {})))
        else:
            name, inputs, observed = b
            out.append(dict(name=str(name), inputs=dict(inputs), observed=dict(observed or {})))
    return out


class Pipeline:
    """An ordered multi-stage pipeline: each stage is a named core11 relational AST reading base relations or earlier stages."""

    def __init__(self, stages):
        self.stages = []
        for s in stages:
            d = dict(s) if isinstance(s, dict) else dict(name=s[0], ast=s[1])
            d.setdefault("sql", None)
            d.setdefault("origin", "given")
            self.stages.append(d)
        names = self.names()
        if len(set(names)) != len(names):
            raise ValueError("duplicate stage names")

    @classmethod
    def from_sql(cls, stages, sample_inputs=None):
        """stages: [(name, sql)]. sample_inputs (one batch's base relations) resolves join keys and column references."""
        env, out = dict(sample_inputs or {}), []
        for name, sql in stages:
            ast = parse_sql(sql, _cols_fn(dict(env)) if env else None)
            out.append(dict(name=name, ast=ast, sql=sql, origin="sql"))
            if env:
                R = _run(ast, env)
                if R is not None:
                    env[name] = R
        return cls(out)

    @classmethod
    def from_script(cls, text, sample_inputs=None):
        return cls.from_sql(split_script(text), sample_inputs)

    def names(self):
        return [s["name"] for s in self.stages]

    def index(self, name):
        return self.names().index(name)

    def deps(self, i):
        return sorted(P._base_rels(self.stages[i]["ast"]) & set(self.names()))

    def replace(self, i, ast, origin, sql=None):
        new = Pipeline([dict(s) for s in self.stages])
        new.stages[i].update(ast=ast, origin=origin, sql=sql)
        return new

    def run(self, inputs):
        """Execute every stage in order -> (outputs {stage: Rel | None}, errors {stage: exception name})."""
        env, outs, errs = dict(inputs), {}, {}
        for st in self.stages:
            try:
                R = C.run(st["ast"], env)
            except _EXEC_ERRORS as e:
                outs[st["name"]], errs[st["name"]] = None, type(e).__name__
                continue
            outs[st["name"]] = env[st["name"]] = R
        return outs, errs

    def describe(self):
        return [dict(name=s["name"], origin=s["origin"], sql=s["sql"], size=_size(s["ast"])) for s in self.stages]


def sql_fidelity(pipeline, batches, budget=None):
    """Parse fidelity, FAIL-CLOSED. For every stage parsed from SQL text (origin 'sql'), execute the ORIGINAL SQL natively on SQLite
    (upstream SQL stages executed natively, non-SQL stages materialised from core11) and compare it with core11 execution of the
    parsed AST on the same inputs (one metered full check per comparison). faithful=True only when at least one comparison ran and
    EVERY required comparison is 'agree'. Any 'disagree' / 'core_error' (the parse provably differs: reason 'unfaithful') or
    'native_error' / 'load_error' / 'unchecked' (fidelity not established: reason 'unverified') makes faithful=False.
    Pipelines with no SQL-origin stage are not checked (checked=False, faithful=True: there is no parse to be unfaithful to)."""
    rows, tally = [], Counter()
    if not any(st.get("origin") == "sql" and st.get("sql") for st in pipeline.stages):
        return dict(engine="sqlite", checked=False, tally={}, rows=[], faithful=True, all_agree=False, verified=False, failures={},
                    reason="no_sql_stage")
    for b in _batches(batches):
        outs, _ = pipeline.run(b["inputs"])
        con = sqlite3.connect(":memory:")
        try:
            _load(con, b["inputs"])
            for st in pipeline.stages:
                R = outs.get(st["name"])
                if not (st.get("origin") == "sql" and st.get("sql")):
                    if R is not None:
                        _load(con, {st["name"]: R})
                    continue
                try:
                    con.execute(f"CREATE TABLE {_q(st['name'])} AS {st['sql'].strip().rstrip(';')}")
                    if R is None:
                        status = "core_error"
                    elif not _charge(budget, "full_checks"):
                        status = "unchecked"
                    else:
                        cur = con.execute(f"SELECT * FROM {_q(st['name'])}")
                        status = "agree" if _bag_equal([d[0] for d in cur.description], cur.fetchall(), R) else "disagree"
                except _SQL_ERRORS:
                    status = "native_error"
                tally[status] += 1
                rows.append(dict(batch=b["name"], stage=st["name"], status=status))
        except _SQL_ERRORS:
            tally["load_error"] += 1
            rows.append(dict(batch=b["name"], stage=None, status="load_error"))
        finally:
            con.close()
    failures = {k: v for k, v in tally.items() if k != "agree"}
    faithful = bool(tally.get("agree")) and not failures
    if faithful:
        reason = None
    elif any(tally.get(k) for k in _UNFAITHFUL):
        reason = "unfaithful"
    else:
        reason = "unverified"
    return dict(engine="sqlite", checked=True, tally=dict(tally), rows=rows, faithful=faithful, all_agree=faithful, verified=faithful,
                failures=failures, reason=reason)


def _upstream_env(pipeline, b, i):
    """Base inputs + outputs of stages before i: OBSERVED outputs when available (preserved ground truth), else computed."""
    env = dict(b["inputs"])
    for st in pipeline.stages[:i]:
        E = b["observed"].get(st["name"])
        if E is not None:
            env[st["name"]] = E
        else:
            R = _run(st["ast"], env)
            if R is not None:
                env[st["name"]] = R
    return env


def _span(pipeline, statuses, i):
    """Unobserved (transitive) ancestors of stage i: the suspect span when an observed stage mismatches."""
    idx = {s["name"]: j for j, s in enumerate(pipeline.stages)}
    out, todo = set(), list(pipeline.deps(i))
    while todo:
        j = idx.get(todo.pop())
        if j is None or j >= i or j in out or statuses[j] not in ("unobserved", "unobserved_error"):
            continue
        out.add(j)
        todo.extend(pipeline.deps(j))
    return sorted(out)


def localize(pipeline, batches, budget=None):
    """Per-stage status on observed outputs (each stage fed its observed upstream outputs); first broken stage + suspect span.
    complete=False when the budget refused a comparison (the localisation is then NOT evidence of a working pipeline)."""
    B = _batches(batches)
    budget = budget if budget is not None else S.Budget(wall=LIFT_WALL_S)
    recs = [dict(index=i, name=s["name"], deps=pipeline.deps(i), observed=0, matched=0, mismatched=[], errors=[])
            for i, s in enumerate(pipeline.stages)]
    stop = False
    for b in B:
        env = dict(b["inputs"])
        for i, st in enumerate(pipeline.stages):
            rec = recs[i]
            R = _run(st["ast"], env)
            if R is None:
                rec["errors"].append(b["name"])
            E = b["observed"].get(st["name"])
            if E is not None:
                if not stop and _charge(budget, "full_checks"):
                    rec["observed"] += 1
                    if _same(R, E):
                        rec["matched"] += 1
                    else:
                        rec["mismatched"].append(b["name"])
                else:
                    stop = True
                env[st["name"]] = E
            elif R is not None:
                env[st["name"]] = R
    for rec in recs:
        rec["status"] = ("broken" if rec["mismatched"] else "verified" if rec["observed"] else
                         "unobserved_error" if rec["errors"] else "unobserved")
    statuses = [r["status"] for r in recs]
    broken = next((r["index"] for r in recs if r["status"] == "broken"), None)
    span = _span(pipeline, statuses, broken) if broken is not None else []
    return dict(stages=recs, statuses=statuses, broken=broken, broken_name=None if broken is None else recs[broken]["name"],
                span=span, span_names=[recs[j]["name"] for j in span], complete=not stop, work=dict(budget.c),
                exhausted=budget.exhausted)


def _loc_brief(loc):
    return dict(broken=loc["broken_name"], span=loc["span_names"], statuses={s["name"]: s["status"] for s in loc["stages"]},
                mismatched={s["name"]: s["mismatched"] for s in loc["stages"] if s["mismatched"]}, complete=loc["complete"],
                exhausted=loc["exhausted"])


def end_to_end(pipeline, batches, budget=None):
    """Run the pipeline on every batch with COMPUTED stage outputs; every observed stage must match (one metered full check each)."""
    checks, mism, errs, complete = 0, [], {}, True
    for b in _batches(batches):
        outs, e = pipeline.run(b["inputs"])
        if e:
            errs[b["name"]] = e
        for st in pipeline.stages:
            E = b["observed"].get(st["name"])
            if E is None:
                continue
            if not _charge(budget, "full_checks"):
                complete = False
                break
            checks += 1
            if not _same(outs.get(st["name"]), E):
                mism.append((b["name"], st["name"]))
        if not complete:
            break
    return dict(ok=complete and checks > 0 and not mism, checks=checks, mismatches=mism, errors=errs, complete=complete)


def compile_pipeline_sql(pipeline, sample_inputs, lib=None):
    """Every stage compiled to `CREATE TABLE stage AS <sql>;` (column lists resolved on sample_inputs)."""
    env, out = dict(sample_inputs), []
    for st in pipeline.stages:
        try:
            sql, err = to_sql(st["ast"], _cols_fn(dict(env)), lib=lib), None
        except SqlUnsupported as e:
            sql, err = None, str(e)[:200]
        out.append(dict(name=st["name"], sql=sql, error=err, statement=f"CREATE TABLE {_q(st['name'])} AS {sql};" if sql else None))
        R = _run(st["ast"], env)
        if R is not None:
            env[st["name"]] = R
    return out


def native_pipeline_check(pipeline, batches, lib=None, budget=None):
    """Run the compiled pipeline natively on SQLite per batch and compare every observed stage with its observation (one metered
    full check per comparison; 'unchecked' when the budget refuses). all_agree requires every observed stage to agree."""
    rows, tally = [], Counter()
    for b in _batches(batches):
        comp = compile_pipeline_sql(pipeline, b["inputs"], lib)
        con = sqlite3.connect(":memory:")
        try:
            _load(con, b["inputs"])
            for c in comp:
                E = b["observed"].get(c["name"])
                if c["statement"] is None:
                    status = "unsupported"
                else:
                    try:
                        con.execute(c["statement"])
                        if E is None:
                            status = "ran"
                        elif not _charge(budget, "full_checks"):
                            status = "unchecked"
                        else:
                            cur = con.execute(f"SELECT * FROM {_q(c['name'])}")
                            status = "agree" if _bag_equal([d[0] for d in cur.description], cur.fetchall(), E) else "disagree"
                    except _SQL_ERRORS:
                        status = "error"
                if E is not None:
                    tally[status] += 1
                rows.append(dict(batch=b["name"], stage=c["name"], status=status))
        except _SQL_ERRORS:
            tally["load_error"] += 1
        finally:
            con.close()
    return dict(engine="sqlite", sqlite_version=sqlite3.sqlite_version, tally=dict(tally), rows=rows,
                all_agree=bool(tally) and set(tally) == {"agree"})


def pipeline_oracle(reference):
    """A budgeted reference oracle backed by a reference Pipeline: answers oracle(stage, env) by running the reference stages on
    env (relations already in env are taken as given). Used ONLY as the external reference the protocol allows to be queried."""
    def oracle(stage, env):
        env2 = dict(env)
        for st in reference.stages:
            if st["name"] == stage:
                return _run(st["ast"], env2)
            if st["name"] not in env2:
                R = _run(st["ast"], env2)
                if R is not None:
                    env2[st["name"]] = R
        return None
    return oracle


# ------------------------------------------------------------------ localize-and-lift
def _task(obs, schema):
    a = obs[0]
    b = obs[1] if len(obs) > 1 else obs[0]
    return dict(inputs={"vis_a": a[1], "vis_b": b[1]}, expected={"vis_a": a[2], "vis_b": b[2]}, out_schema=schema,
                extra_obs=[(f"fit:{n}", env, E) for n, env, E in obs[2:]])


def _keeps(region, obs):
    """Preserved working sub-ASTs (closest to the root first) that run on every observation env."""
    names = {r for _, env, _ in obs for r in env}
    out = []
    for _, sa in _sub_asts(region):
        if all(_run(sa, env) is not None for _, env, _ in obs):
            k = f"nx_keep{len(out)}"
            while k in names:
                k += "_"
            out.append((k, sa))
            if len(out) >= MAX_KEEP:
                break
    return out


def _synthesize(obs, keeps, schema, o, budget):
    """Atomic synthesis on the lifted task (preserved sub-ASTs offered as inputs) inside a budget fork; candidates compiled back."""
    valid = [(k, a) for k, a in keeps if all(_run(a, env) is not None for _, env, _ in obs)]
    sobs = []
    for n, env, E in obs:
        kenv = dict(env)
        for k, a in valid:
            kenv[k] = _run(a, env)
        sobs.append((n, kenv, E))
    fc_now = budget.c["full_checks"]
    el = time.time() - budget.t0
    sb = budget.fork(fc_cap=fc_now + max(1, int(SYNTH_SHARE * (budget.fc_cap - fc_now))),
                     wall=el + SYNTH_SHARE * max(0.0, budget.wall - el))
    log = dict(keeps=[k for k, _ in valid], candidates=0, exhausted=None, error=None)
    try:
        res = S.collect(_task(sobs, schema), o["lib"], o["costs"], sb)
    except _EXEC_ERRORS + (S.WorkExhausted,) as e:
        res = None
        log["error"] = type(e).__name__
    _merge(budget, sb)
    if res is None:
        return [], log
    defs = dict(valid)
    out = []
    for c in res["candidates"]:
        try:
            out.append(dict(compiled=_inline(c["expanded"], defs), program=c["program"], provenance=c.get("provenance")))
        except (ValueError, KeyError):
            continue
    log.update(candidates=len(out), exhausted=res.get("exhausted"), counters=res.get("counters"), wall=res.get("wall"))
    return out, log


def _order(vs, prior):
    return sorted(vs.alive(), key=lambda m: (-(prior(m) if prior else 0.0), m["origin"] != "candidate", _size(m["ast"]) or 0, m["id"]))


def _scored(vs, o):
    """Score the arm's QUERY menu (program-aware by default; o['menu'](vs) when injected). Used only to choose queries."""
    props = o["menu"](vs) if o.get("menu") else P.program_aware_proposals(vs)
    return P.score_proposals(vs, props, leader=vs.leader(o["prior"]))


def resolution_menu(vs):
    """The COMMON final-resolution menu of every arm (independent of the arm's query menu): program-aware proposals from the live
    members' ASTs plus the AST-blind static menu - identical to runner13.investigate's submission check."""
    return list(P.program_aware_proposals(vs)) + list(P.generic_proposals(P.base_envs(vs.task)))


def _resolution_scored(vs, o):
    return P.score_proposals(vs, resolution_menu(vs), leader=vs.leader(o["prior"]))


def _members(vs, cap=64):
    return [dict(id=m["id"], origin=m["origin"], edge=m["edge"], status=m["status"], falsified_by=m["falsified_by"], tags=m["tags"],
                 size=_size(m["ast"]), native_rejected=bool(m.get("native_rejected"))) for m in vs.members[:cap]]


def _result(status, reason, **kw):
    d = dict(status=status, reason=reason, method=None, repaired_ast=None, sql=None, sql_error=None, native=[], native_agree=0,
             native_rejected=[], native_checked=[], native_query_checks=0, queries=[], members=[], unresolved=False,
             agreement_unproven=False, leader_tags=[], alternative_tags=[], provenance=dict(relational=[], scalar=[]), pipeline=None,
             keeps=[], synth=None, vs=None, resumed=0, scoring_complete=None, resolution_menu=RESOLUTION_MENU)
    d.update(kw)
    return d


def _native_obs(work_obs, hold):
    """Every observation the core11 repair was verified on: fit batches, answered queries (work_obs) and held-out batches."""
    out, seen = [], set()
    for n, env, E in list(work_obs) + list(hold):
        if n in seen:
            continue
        seen.add(n)
        out.append((n, env, E))
    return out


def _attempt(pipeline, B, i, span, mode, o, budget, queries_left):
    st = pipeline.stages[i]
    name = st["name"]
    span_names = [pipeline.stages[j]["name"] for j in span]
    region = _inline(st["ast"], {pipeline.stages[j]["name"]: pipeline.stages[j]["ast"] for j in span}) if span else st["ast"]
    reads = sorted(P._base_rels(region))
    obs = []
    for b in B:
        E = b["observed"].get(name)
        if E is None:
            continue
        env = _upstream_env(pipeline, b, i)
        avail = sorted((set(env) - set(span_names)) | set(reads)) if mode == "widen" else reads
        if any(r not in env for r in avail):
            continue
        obs.append((b["name"], {r: env[r] for r in avail}, E))
    base = dict(mode=mode, span=span_names, reads=reads)
    if not obs:
        return _result("failed", "no_observed_batch", **base)
    if mode == "widen" and len(obs[0][1]) > WIDEN_MAX:
        return _result("skipped", "too_many_relations_to_widen", **base)
    fit, hold = (obs[:-1], obs[-1:]) if o["holdout"] and len(obs) >= 3 else (obs, [])
    E0 = obs[0][2]
    schema = tuple(zip(E0.cols, E0.types))
    keeps = _keeps(region, fit)
    base.update(keeps=[(k, a) for k, a in keeps], holdout=[h[0] for h in hold])
    work_obs, queries, method, synth_log, vs, resumed = list(fit), [], None, None, None, 0
    for _rnd in range(2):
        vs = P.VersionSpace(_task(work_obs, schema), [], budget=budget, shadows=o["shadows"])
        if o["edit_first"] and mode != "widen":
            ctx = dict(out_types=vs.out_types, consts=vs._consts(), cols=vs._cols, join_kinds=tuple(C.JOIN_KINDS))
            for ne, ed in P._rel_edits(region, ctx)[:EDIT_CAP]:
                if vs.exhausted:
                    break
                try:
                    C.rel_schema(ne, vs.es)
                except (C.TypeErr, C.Unsupported, KeyError, ValueError, IndexError, TypeError):
                    continue
                vs._add(ne, ne, "candidate", edge=f"edit:{ed}")
            if vs.alive("candidate"):
                method = "edit"
        if not vs.alive("candidate") and not vs.exhausted and not budget.out():
            cands, synth_log = _synthesize(work_obs, keeps, schema, o, budget)
            for c in cands:
                vs._add(c["compiled"], c["program"], "candidate", provenance=c["provenance"])
            if vs.alive("candidate"):
                method = "synth"
        if vs.shadows_enabled and vs.alive("candidate") and not vs.exhausted:
            vs._expand_shadows()
        new_q = 0
        while queries_left[0] > 0 and o["oracle"] is not None and len(vs.alive()) > 1 and not vs.exhausted and not budget.out():
            scored = _scored(vs, o)
            split = [s for s in scored if len(s["partition"]) > 1]
            if not split:
                break
            ch = o["chooser"](split) if o["chooser"] else P.choose(split, "weighted")
            if ch is None:
                break
            try:
                E = o["oracle"](name, ch["env"])
            except Exception:                                          # noqa: BLE001 - an external oracle failure ends querying
                E = None
            if E is None:
                break
            if o["observer"] is not None:
                o["observer"](dict(stage=name, scored=scored, splitting=split, chosen=ch, answer=E, vs=vs))
            queries_left[0] -= 1
            new_q += 1
            qn = f"q{len(queries)}"
            rep = vs.observe(qn, ch["env"], E)
            queries.append(dict(name=qn, kind=ch["kind"], detail=ch["detail"], base=ch["base"], rel=ch["rel"], scored=len(scored),
                                splitting=len(split), falsified=len(rep["falsified"]), survivors=len(rep["survivors"]),
                                falsified_tags=rep["falsified_tags"], falsified_edges=rep["falsified_edges"]))
            work_obs.append((qn, ch["env"], E))
        if vs.alive() or not new_q or budget.out():
            break
        resumed += 1
    base.update(method=method, queries=queries, synth=synth_log, resumed=resumed)
    alive = _order(vs, o["prior"])
    if not alive:
        reason = "budget" if vs.exhausted or budget.exhausted else ("all_falsified" if vs.members else "no_candidate")
        return _result("failed", reason, members=_members(vs), vs=vs.summary(), **base)
    unresolved, unresolved_reason, complete = bool(vs.exhausted), "budget" if vs.exhausted else None, None
    if len(alive) > 1 and not unresolved:
        scored = _resolution_scored(vs, o)                             # COMMON menu for every arm (not the arm's query menu)
        complete = bool(getattr(scored, "complete", True)) and not vs.exhausted
        split = any(len(s["partition"]) > 1 for s in scored)
        if vs.exhausted:
            unresolved, unresolved_reason = True, "budget"
        elif split:
            unresolved, unresolved_reason = True, "unresolved_alternatives"
        elif not complete:                                             # an unscored proposal could still separate the members
            unresolved, unresolved_reason = True, "incomplete_scoring"
        alive = _order(vs, o["prior"])
    base["scoring_complete"] = complete
    if unresolved and o["require_unique"]:
        return _result("abstained", unresolved_reason, unresolved=True, members=_members(vs), vs=vs.summary(), **base)
    nobs = _native_obs(work_obs, hold)
    qnames = {q["name"] for q in queries}
    base.update(native_checked=[n for n, _, _ in nobs] if o["native"] else [],
                native_query_checks=sum(n in qnames for n, _, _ in nobs) if o["native"] else 0)
    accepted, rejected, acc_sql, acc_err, acc_native = None, [], None, None, []
    cols_of = _cols_fn(obs[0][1])
    for m in alive:
        ok = True
        for hn, henv, hE in hold:
            if not _charge(budget, "full_checks"):
                return _result("abstained", "budget", members=_members(vs), vs=vs.summary(), native_rejected=rejected, **base)
            if not _same(_run(m["ast"], henv), hE):
                m["status"], m["falsified_by"], ok = "falsified", f"holdout:{hn}", False
                break
        if not ok:
            continue
        try:
            sql, sql_err = to_sql(m["ast"], cols_of), None
        except SqlUnsupported as e:
            sql, sql_err = None, str(e)[:200]
        native = []
        if o["native"]:
            for n, env, E in nobs:                                     # fit batches + held-out + every answered query
                if not _charge(budget, "full_checks"):
                    return _result("abstained", "budget", members=_members(vs), vs=vs.summary(), native_rejected=rejected, **base)
                r = native_check(m["ast"], env, E)
                native.append(dict(batch=n, query=n in qnames, **r))
                if r["status"] != "agree" and o["require_native"]:
                    break                                              # one native disagreement rejects the member
        if o["require_native"] and (sql is None or not native or any(r["status"] != "agree" for r in native)):
            m["native_rejected"] = True
            rejected.append(dict(id=m["id"], origin=m["origin"], edge=m["edge"], sql_error=sql_err,
                                 statuses=[r["status"] for r in native],
                                 failed_on=[r["batch"] for r in native if r["status"] != "agree"],
                                 failed_on_query=any(r["query"] and r["status"] != "agree" for r in native),
                                 detail=[r.get("detail") for r in native if r.get("detail")][:2]))
            continue
        accepted, acc_sql, acc_err, acc_native = m, sql, sql_err, native
        break
    if accepted is None:
        reason = "native_rejected_all" if rejected else "holdout_falsified_all"
        return _result("failed", reason, members=_members(vs), vs=vs.summary(), native_rejected=rejected, **base)
    ast = accepted["ast"]
    others = [m for m in vs.alive() if m["id"] != accepted["id"]]
    prov = accepted.get("provenance") or {}
    return _result("repaired", None, repaired_ast=ast, sql=acc_sql, sql_error=acc_err, native=acc_native,
                   native_agree=sum(r["status"] == "agree" for r in acc_native), native_rejected=rejected, unresolved=unresolved,
                   agreement_unproven=len(alive) > 1 and not unresolved, leader_tags=list(accepted["tags"]),
                   alternative_tags=sorted({t for m in others for t in m["tags"]}), accepted_origin=accepted["origin"],
                   accepted_edge=accepted["edge"],
                   provenance=dict(relational=sorted(prov.get("relational", [])), scalar=sorted(prov.get("scalar", []))),
                   members=_members(vs), vs=vs.summary(), pipeline=pipeline.replace(i, ast, origin=f"lift:{method}:{mode}", sql=acc_sql),
                   **base)


_STOP_REASONS = ("unresolved_alternatives", "incomplete_scoring")


def lift_stage(pipeline, batches, index=None, span=None, *, lib=None, costs=None, oracle=None, chooser=None, prior=None, observer=None,
               menu=None, query_budget=QUERY_BUDGET, require_unique=True, holdout=True, shadows=True, edit_first=True, widen=True,
               wall=LIFT_WALL_S, fc_cap=S.FC_CAP, native=True, require_native=None, budget=None, queries_left=None):
    """Localize-and-lift repair of one broken stage (localised automatically when index is None). Attempts: the stage alone, the
    stage with its suspect span inlined, then widened inputs. One strict budget across all attempts: `budget` when given (shared
    row budget; wall / fc_cap ignored), else a fresh Budget(wall, fc_cap). `queries_left` ([n]) shares a query allowance.
    `menu(vs)` replaces the program-aware QUERY menu (e.g. an AST-blind static control); the final resolution test always uses the
    common program-aware + static menu (resolution_menu), whatever the arm."""
    t0 = time.time()
    B = _batches(batches)
    budget = budget if budget is not None else S.Budget(wall=wall, fc_cap=fc_cap)
    if queries_left is None:
        queries_left = [int(query_budget) if oracle is not None else 0]
    q_start = queries_left[0]
    if index is None or span is None:
        loc = localize(pipeline, B, budget)
        if index is None:
            index = loc["broken"]
        if index is None:
            st = "no_fault" if loc["complete"] else "abstained"
            return _result(st, None if loc["complete"] else "budget", stage=None, index=None, attempts=[], work=dict(budget.c),
                           exhausted=budget.exhausted, queries_used=0, wall=round(time.time() - t0, 3))
        if span is None:
            span = _span(pipeline, loc["statuses"], index)
    o = dict(lib=lib or {}, costs=costs or S.Costs(), oracle=oracle, chooser=chooser, prior=prior, observer=observer, menu=menu,
             require_unique=require_unique, holdout=holdout, shadows=shadows, edit_first=edit_first, native=native,
             require_native=native if require_native is None else bool(require_native))
    plan = [("stage", [])] + ([("span", list(span))] if span else []) + ([("widen", list(span))] if widen else [])
    attempts, res = [], None
    for mode, sp in plan:
        if budget.out():
            break
        r = _attempt(pipeline, B, index, sp, mode, o, budget, queries_left)
        attempts.append(dict(mode=mode, status=r["status"], reason=r["reason"], method=r.get("method"), queries=len(r.get("queries", [])),
                             native_rejected=len(r.get("native_rejected", [])), scoring_complete=r.get("scoring_complete"),
                             native_query_checks=r.get("native_query_checks", 0)))
        if r["status"] != "skipped" or res is None:
            res = r
        if r["status"] == "repaired" or (r["status"] == "abstained" and r["reason"] in _STOP_REASONS):
            break
    if res is None or (res["status"] == "skipped"):
        res = _result("abstained", "budget")
    res.update(stage=pipeline.stages[index]["name"], index=index, attempts=attempts, work=dict(budget.c), exhausted=budget.exhausted,
               queries_used=q_start - queries_left[0], wall=round(time.time() - t0, 3),
               query_menu="injected" if menu is not None else "program_aware", resolution_menu=RESOLUTION_MENU,
               attribution=dict(machinery="pipeline_lifter13 + synth12 + proposals13 (engineering team)",
                                learned=dict(library_functions=res.get("provenance"), guide_costs=bool(getattr(o["costs"], "t", None)),
                                             trained_chooser=chooser is not None, leader_prior=prior is not None)))
    return res


def _fidelity_stop(fidelity):
    """None when lifting may proceed; else the stop status ('unfaithful_parse' / 'fidelity_unverified')."""
    if fidelity.get("faithful"):
        return None
    return "unfaithful_parse" if fidelity.get("reason") == "unfaithful" else "fidelity_unverified"


def repair_pipeline(pipeline, batches, *, max_faults=MAX_FAULTS, native=True, lib=None, wall=LIFT_WALL_S, fc_cap=S.FC_CAP,
                    query_budget=QUERY_BUDGET, oracle=None, lift_share=LIFT_SHARE, **kw):
    """Parse-fidelity check -> localize -> lift -> re-localize until no observed stage is broken (at most max_faults lifts), then
    verify end to end and compile the repaired pipeline to native SQL with a SQLite check. ONE strict row budget (wall, fc_cap) and
    ONE query allowance cover every check. 'repaired' requires complete core11 verification AND (when native) native agreement on
    every observed stage (each accepted lift already agreed natively on its fit, held-out AND answered-query observations). Lifting
    requires ESTABLISHED parse fidelity (fail-closed): a parse that provably disagrees with its own SQL stops as 'unfaithful_parse';
    one whose fidelity could not be established (native error, load error, budget-refused comparison) stops as
    'fidelity_unverified'. repair_methods records, per repaired stage, whether the accepted repair came from the single-edit menu
    ('edit') or the atomic synthesizer ('synth')."""
    t0 = time.time()
    B = _batches(batches)
    budget = S.Budget(wall=wall, fc_cap=fc_cap)
    ql = [int(query_budget) if oracle is not None else 0]
    q0 = ql[0]
    cur, steps, stop = pipeline, [], None
    fidelity = sql_fidelity(pipeline, B, budget) if B else dict(checked=False, faithful=True, tally={}, rows=[], reason="no_batches")
    stop = _fidelity_stop(fidelity)
    for _ in range(0 if stop else max_faults):
        loc = localize(cur, B, budget)
        if not loc["complete"]:
            stop = "budget"
            break
        if loc["broken"] is None:
            break
        el = time.time() - budget.t0
        lb = budget.fork(wall=el + lift_share * max(0.0, budget.wall - el))
        res = lift_stage(cur, B, loc["broken"], span=loc["span"], lib=lib, native=native, oracle=oracle, query_budget=query_budget,
                         budget=lb, queries_left=ql, **kw)
        _merge(budget, lb)
        steps.append(dict(localization=_loc_brief(loc), lift={k: v for k, v in res.items() if k != "pipeline"}))
        if res["status"] != "repaired":
            stop = res["status"]
            break
        cur = res["pipeline"]
    final = localize(cur, B, budget)
    e2e = end_to_end(cur, B, budget)
    nat = native_pipeline_check(cur, B, lib, budget) if native and B else None
    repaired_lifts = [s["lift"] for s in steps if s["lift"]["status"] == "repaired"]
    n_rep = len(repaired_lifts)
    methods = [dict(stage=lf.get("stage"), method=lf.get("method"), mode=lf.get("mode"), accepted_origin=lf.get("accepted_origin"),
                    accepted_edge=lf.get("accepted_edge"), provenance=lf.get("provenance"),
                    native_query_checks=lf.get("native_query_checks", 0)) for lf in repaired_lifts]
    core_ok = e2e["ok"] and final["complete"] and final["broken"] is None
    native_ok = (not native) or bool(nat and nat["all_agree"])
    reason = None
    if stop is not None:
        status, reason = ("partial" if n_rep else stop), stop
    elif not final["complete"] or not e2e["complete"]:
        status, reason = ("budget" if steps else "abstained"), "budget_exhausted_during_verification"
    elif not steps:
        status = "no_fault" if e2e["ok"] else "unlocalized"
    elif core_ok and native_ok:
        status = "repaired"
    elif core_ok:
        status, reason = "native_disagree", "native_pipeline_check_failed"
    else:
        status, reason = "partial", "end_to_end_failed"
    work = dict(budget.c)
    over = sorted(k for k, cap in (("full_checks", budget.fc_cap), ("rel_evals", budget.rel_cap), ("micro_evals", budget.sc_cap),
                                   ("constructed_asts", budget.ast_cap)) if work.get(k, 0) > cap)
    return dict(status=status, reason=reason, pipeline=cur, repaired_stages=n_rep, steps=steps, localization=_loc_brief(final),
                end_to_end=e2e, sql=compile_pipeline_sql(cur, B[0]["inputs"], lib) if B else [], native=nat, native_ok=native_ok,
                source_fidelity={k: v for k, v in fidelity.items() if k != "rows"}, work=work, over_cap=over,
                repair_methods=methods, edit_only=sum(m["method"] == "edit" for m in methods),
                synthesized=sum(m["method"] == "synth" for m in methods), resolution_menu=RESOLUTION_MENU,
                exhausted=budget.exhausted, queries_used=q0 - ql[0], query_budget=q0, wall=round(time.time() - t0, 3),
                attribution=dict(machinery="pipeline_lifter13 (engineering team)",
                                 learned=[lf.get("provenance") for lf in repaired_lifts]))


__all__ = ["Pipeline", "SqlUnsupported", "SqlParseError", "tokenize", "parse_sql", "split_script", "to_sql", "native_check",
           "compile_pipeline_sql", "native_pipeline_check", "sql_fidelity", "localize", "lift_stage", "repair_pipeline", "end_to_end",
           "pipeline_oracle", "resolution_menu", "RESOLUTION_MENU", "ENGINES"]
