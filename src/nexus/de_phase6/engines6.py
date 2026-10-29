"""Phase 6 engines and operators (NOT LOCKED).
Engines execute pipeline TEXT: SQLite 3 and PySpark 4.0.1 (de_phase4.world.SQLiteCode / SparkCode: 127.0.0.1 driver bind,
ANSI on) and DuckDB 1.1.3 (DuckDBCode, in-process). Raw input tables are text; state files become state_* tables / a dict.
Operators: the Phase 4 operator set (de_phase4.ops) plus three generic ones - filter_cmp (state-threshold filters with
lt / le, completing ops.filter_file's gt / ge), col_compare (cast(a) le / lt cast(b) for integer-like column pairs: point-
in-time cut-offs) and require_nonempty (quarantine rows whose text column is empty). The stage tag of each operator is
used by stage-wise search."""
from __future__ import annotations

import copy
import itertools
import json

import duckdb

from nexus.de_phase4 import ir, ops as O, world as W
from nexus.de_phase6 import ir6  # noqa: F401  (registers le / nonempty)


class DuckDBCode:
    """One in-process DuckDB connection per worker; every run starts from a clean catalog (its objects are dropped)."""
    name, lang = "duckdb", "duckdb"
    _con = None

    @classmethod
    def con(cls):
        if cls._con is None:
            cls._con = duckdb.connect()
        return cls._con

    def run(self, code, header, rows, state):
        con = self.con()
        for (n, t) in con.execute("SELECT table_name, table_type FROM information_schema.tables").fetchall():
            con.execute(f'DROP {"VIEW" if t == "VIEW" else "TABLE"} IF EXISTS "{n}"')
        try:
            con.execute("CREATE TABLE raw (" + ", ".join(f'"{h}" TEXT' for h in header) + ', "__rowid" INTEGER)')
            if rows:
                vals = [x for i, r in enumerate(rows) for x in (tuple(r[h] for h in header) + (i,))]
                one = "(" + ",".join("?" * (len(header) + 1)) + ")"
                con.execute("INSERT INTO raw VALUES " + ",".join([one] * len(rows)), vals)
            for fname, d in state.items():
                ks = list(d)
                t = f'"state_{fname.rsplit(".", 1)[0]}"'
                con.execute(f"CREATE TABLE {t} (" + ", ".join(f'"{k}" INTEGER' for k in ks) + ")")
                con.execute(f"INSERT INTO {t} VALUES ({','.join('?' * len(ks))})", [d[k] for k in ks])
            try:
                for st in [s for s in code.split(";\n") if s.strip() and not s.strip().startswith("--")]:
                    con.execute(st.strip().rstrip(";"))
                cur = con.execute("SELECT * FROM clean")
                names = [c[0] for c in cur.description]
                clean = [dict(zip(names, r)) for r in cur.fetchall()]
                rejects = None
                if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'rejects'").fetchone()[0]:
                    cur = con.execute("SELECT * FROM rejects")
                    names = [c[0] for c in cur.description]
                    rejects = [dict(zip(names, r)) for r in cur.fetchall()]
            except duckdb.Error as e:
                raise W.RunError(type(e).__name__, str(e).split("\n")[0][:200])
            return dict(clean=clean, rejects=rejects)
        finally:
            pass


ENGINES = {"sqlite": W.SQLiteCode, "duckdb": DuckDBCode, "spark": W.SparkCode}
EXEC_LANG = {"sqlite": "sql", "duckdb": "duckdb", "spark": "py"}
OPS = O.OPS + ("filter_cmp", "col_compare", "require_nonempty")
STAGE = dict(O.STAGE, filter_cmp=2, col_compare=2, require_nonempty=2)


def candidates(op, spec, dom):
    if op in O.OPS:
        return O.candidates(op, spec, dom)
    out = []
    cols = [c for c in dom.header if c != "id"]
    if op == "filter_cmp":
        vals = [["file", f, k] for (f, k) in dom.files]
        vals += [["sub", ["file", f1, k1], ["file", f2, k2]] for (f1, k1), (f2, k2) in itertools.permutations(dom.files, 2) if f1 == f2]
        for c in cols:
            if c not in dom.int_like or c not in dom.num_range:
                continue
            lo, hi = dom.num_range[c]
            for v in vals:
                t = ir.ev(v, {}, dom.state)
                if not (lo - 1 <= t <= hi + 1):
                    continue
                for cmp in ("lt", "le"):
                    out.append((O._add_filter(spec, [cmp, ["cast_int", ["col", c]], v]), f"{c} {cmp} {json.dumps(v)}"))
    elif op == "col_compare":
        for a, b in itertools.permutations([c for c in cols if c in dom.int_like and c not in dom.dirty_cols], 2):
            for cmp in ("le", "lt"):
                out.append((O._add_filter(spec, [cmp, ["cast_int", ["col", a]], ["cast_int", ["col", b]]]), f"{a} {cmp} {b}"))
    elif op == "require_nonempty":
        for c in cols:
            if c in dom.text_cols and any(not (r.get(c) or "").strip() for r in dom.rows):
                q = ["nonempty", ["col", c]]
                s = copy.deepcopy(spec)
                old = s.get("quarantine")
                s["quarantine"] = ["not", q] if not old else ["not", ["and", ["not", old], q]]
                out.append((s, c))
    return out


def pclass(op, prm):
    if op in ("filter_file", "filter_cmp"):
        _, cmp, val = prm.split(" ", 2)
        return cmp + (":sub" if json.loads(val)[0] == "sub" else ":file")
    if op == "col_compare":
        return prm.split(" ")[1]
    return O.pclass(op, prm)
