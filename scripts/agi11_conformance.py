"""Phase 11 Stage 1 conformance (NOT LOCKED; DEVELOPMENT FIXTURES ONLY - hand-written programs exercising every operator and edge
case; never a task, never visible to the learner as a template).  python scripts/agi11_conformance.py OUT.json
Every fixture program runs on the reference interpreter, DuckDB and SQLite over fixture relations with NULLs, empty input, duplicate
keys and order ties; per (fixture, engine): generate native code -> execute -> semantic conformance (bag equality with the reference)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase11 import core11 as C, sql11 as Q  # noqa: E402

I, N, S, B = C.INT, C.NUM, C.STR, C.BOOL
R = C.Rel(["k", "a", "s", "x", "j"], [I, I, S, N, S], [
    (1, 5, "p", 1.5, '{"a": 5, "b": "x"}'), (1, None, "q", 2.0, '{"a": 1.50}'), (2, -7, None, -1.0, '{"b": {"c": 1}}'),
    (2, 3, "p", 0.0, "{bad"), (None, 4, "p", 3.25, '{"a": 1e3}'), (3, 0, "12", None, None), (3, 0, "x9", 4.0, '{"a": true}'), (4, 9, "-3", 2.0, '{"a": null}')])
Sx = C.Rel(["k", "v"], [I, I], [(1, 10), (1, 11), (2, 20), (None, 30), (5, 50)])
E = C.Rel(R.cols, R.types, [])
col, const = (lambda n: ("col", n)), (lambda v, t: ("const", v, t))
SCALARS = {
    "arith": ("arith", "add", col("a"), const(2, I)), "div0": ("arith", "div", col("a"), col("a")), "mod_neg": ("arith", "mod", col("a"), const(4, I)),
    "mul_num": ("arith", "mul", col("x"), col("a")), "cmp3vl": ("cmp", "gt", col("a"), const(3, I)),
    "and3vl": ("and", ("cmp", "gt", col("a"), const(0, I)), ("cmp", "eq", col("s"), const("p", S))),
    "or3vl": ("or", ("cmp", "gt", col("a"), const(0, I)), ("cmp", "eq", col("s"), const("p", S))), "not3vl": ("not", ("cmp", "eq", col("s"), const("p", S))),
    "isnull": ("isnull", col("a")), "branch": ("branch", ("cmp", "gt", col("a"), const(0, I)), col("a"), const(0, I)),
    "coalesce_shape": ("branch", ("isnull", col("a")), const(-1, I), col("a")), "cast_str_int": ("cast", col("s"), I),
    "cast_int_str": ("cast", col("a"), S), "cast_int_num": ("cast", col("a"), N),
    "json_a": ("json", col("j"), ("a",)), "json_b": ("json", col("j"), ("b",)), "json_cast": ("cast", ("json", col("j"), ("a",)), I)}
PROGS = {f"map_{k}": ("map", ("rel", "R"), (("k", col("k")), ("y", e))) for k, e in SCALARS.items()}
PROGS.update({
    "filter_null_pred": ("filter", ("rel", "R"), ("cmp", "gt", col("a"), const(0, I))),
    "fold_keys_null": ("fold", ("rel", "R"), ("k",), (("n", "count_star", None), ("c", "count", col("a")), ("s", "sum", col("a")), ("lo", "min", col("s")),
                                                       ("hi", "max", col("x")))),
    "fold_nokey": ("fold", ("rel", "R"), (), (("n", "count_star", None), ("s", "sum", col("a")))),
    "fold_condsum": ("fold", ("rel", "R"), ("k",), (("s", "sum", ("branch", ("cmp", "eq", col("s"), const("p", S)), col("a"), const(0, I))),)),
    "rank_desc_ties": ("rank", ("rel", "R"), ("k",), ((col("a"), True),), 1), "rank_asc_k2": ("rank", ("rel", "R"), ("k",), ((col("x"), False),), 2),
    "rank_nokey": ("rank", ("rel", "R"), (), ((col("a"), True),), 3),
    "join_inner_dup_null": ("join", "inner", ("rel", "R"), ("rel", "S"), ("k",), ("k",)), "join_left": ("join", "left", ("rel", "R"), ("rel", "S"), ("k",), ("k",)),
    "join_semi": ("join", "semi", ("rel", "R"), ("rel", "S"), ("k",), ("k",)), "join_anti": ("join", "anti", ("rel", "R"), ("rel", "S"), ("k",), ("k",)),
    "union_all": ("union", ("rel", "R"), ("filter", ("rel", "R"), ("cmp", "eq", col("s"), const("p", S)))),
    "upsert_shape": ("union", ("join", "anti", ("rel", "S"), ("filter", ("rel", "S"), ("cmp", "gt", col("v"), const(15, I))), ("k",), ("k",)),
                     ("filter", ("rel", "S"), ("cmp", "gt", col("v"), const(15, I)))),
})


def same(a, b):
    if a is C.ERR or b is C.ERR:
        return a is b
    return list(a.cols) == list(b.cols) and C.same_bag(a, b)


def main(out):
    res, envs = {}, {"full": {"R": R, "S": Sx}, "empty": {"R": E, "S": C.Rel(Sx.cols, Sx.types, [])}}
    for name, prog in PROGS.items():
        for en, env in envs.items():
            ref = C.evaluate(prog, env)
            row = {}
            for d in Q.ENGINES:
                try:
                    got = Q.execute(prog, env, d)
                    row[d] = dict(native=got is not C.ERR, conform=same(got, ref))
                except C.Unsupported as e:
                    row[d] = dict(native=False, conform=False, unsupported=str(e)[:80])
            for d in Q.NOT_IMPLEMENTED:
                row[d] = dict(native=False, conform=False, unsupported="adapter not implemented in Phase 11")
            res[f"{name}/{en}"] = row
    summ = {d: dict(conform=sum(r[d]["conform"] for r in res.values()), total=len(res),
                    mismatches=sorted(k for k, r in res.items() if not r[d]["conform"])) for d in list(Q.ENGINES) + list(Q.NOT_IMPLEMENTED)}
    Path(out).write_text(json.dumps(dict(summary=summ, fixtures=res), indent=1))
    print(json.dumps({d: (v["conform"], v["total"], v["mismatches"][:12]) for d, v in summ.items()}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
