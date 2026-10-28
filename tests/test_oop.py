"""OOP-track unit tests (toy data only; no experiment runs, no sealed data)."""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus import oop_synthesizer as S  # noqa: E402


def _net_examples(n=60, seed=1):
    r = random.Random(seed)
    fx = {"USD": 1.0, "EUR": 1.1, "GBP": 1.27}
    ex, out = [], []
    for _ in range(n):
        p = {"amount": round(r.uniform(10, 500), 2), "discount": r.choice([0, 5, 12.5, 20]), "currency": r.choice(list(fx))}
        ex.append({"p": p, "fx": fx})
        out.append(round(p["amount"] * (1 - p["discount"] / 100) * fx[p["currency"]], 2))
    return ex, out


def test_numeric_decomposition_finds_net_formula():
    ex, out = _net_examples()
    n, st = S.synthesize_scalar(ex, out, tol=lambda t: 0.011)
    assert n is not None
    ex2, out2 = _net_examples(40, seed=7)                 # generalises to unseen inputs
    assert all(abs(S.ev(n, e) - y) <= 0.011 for e, y in zip(ex2, out2))


def test_decision_list_classifier_and_source_compiles():
    r = random.Random(3)
    fx = {"USD": 1.0, "EUR": 1.1}
    ex, out = [], []
    for i in range(120):
        tp = "m" if i % 3 == 0 else "o"
        w = r.choice([1.5, 2.0, "n/a"]) if tp == "m" else None
        cur = r.choice(["USD", "EUR", "XXX"]) if tp == "o" else None
        ex.append({"topic": tp, "rec": {"weight": w} if tp == "m" else {"k": 1}, "row": {"currency": cur} if cur else None, "fx": fx})
        out.append("q:bad_weight" if w == "n/a" else "q:bad_ccy" if cur == "XXX" else "ok")
    n, _ = S.synthesize_scalar(ex, out)
    assert n is not None
    src = S.function_source("fn_t", ["topic", "rec", "row", "fx"], n)
    ns = {}
    exec(src, ns)                                          # noqa: S102  (generated code under test)
    fx2 = {"USD": 1.0, "EUR": 1.1}
    assert ns["fn_t"]("o", {"k": 1}, {"currency": "JPY"}, fx2) == "q:bad_ccy"     # membership, not the literal XXX
    assert ns["fn_t"]("m", {"weight": "?"}, None, fx2) == "q:bad_weight"
    assert ns["fn_t"]("m", {"weight": 3.0}, None, fx2) == "ok"


def test_markov_violation_triggers_class_synthesis():
    r = random.Random(5)
    seqs, wants = [], []
    for s in range(3):
        seq, best = [], {}
        for j in range(30):
            k, sv = r.randint(1, 6), r.randint(1, 5)
            rec = {"msg_id": f"{s}-{j}", "key": k, "sv": sv, "op": r.choice(["c", "u", "d"]), "seq": j}
            seq.append(rec)
            if k not in best or sv > best[k]["sv"]:
                best[k] = rec
        seqs.append(seq)
        wants.append({(x["key"], x["sv"]) for x in best.values() if x["op"] != "d"})
    spec = S.synthesize_organelle(seqs, (wants, lambda x: (x["key"], x["sv"])), ignore=("msg_id", "seq"))
    assert spec["kind"] == "organelle" and spec["witness"] is not None
    ns = {}
    exec(S.organelle_source("t", spec), ns)                # noqa: S102
    org = ns["StreamOrganelle_t"]()
    for x in seqs[0]:
        org.ingest(x)
    assert {(x["key"], x["sv"]) for x in org.flush()} == wants[0]


def test_pure_filter_when_no_markov_violation():
    seqs = [[{"id": i, "v": i % 3} for i in range(12)]]
    wants = [{i for i in range(12) if i % 3 != 0}]
    spec = S.synthesize_organelle(seqs, (wants, lambda x: x["id"]), ignore=("id",))
    assert spec["kind"] == "pure_filter"


def test_anti_unification_admits_saving_def_only():
    g = lambda k: ("u", "float", ("b", "get", ("var", "a"), ("b", "get", ("var", "f"), ("const", k))))  # noqa: E731
    progs = {"x": g("amount"), "y": g("discount"), "z": g("weight"), "w": g("qty")}   # 4 uses: the def saves nodes
    rw, defs = S.anti_unify(progs)
    assert len(defs) == 1
    fid, params, body = defs[0]
    ns = {}
    exec(S.def_source(fid, params, body), ns)              # noqa: S102
    env = {"a": {"amt": "3.5"}, "f": {"amount": "amt"}}
    assert S.ev(rw["x"], env) == 3.5
    small = {"x": ("b", "get", ("var", "a"), ("const", "p")), "y": ("b", "get", ("var", "a"), ("const", "q"))}
    assert S.anti_unify(small)[1] == []                    # no saving -> no def


def test_fold_synthesis_bounded_loop():
    ex = [{"xs": [1, 2, 3]}, {"xs": [5]}, {"xs": [2, 2, 2, 2]}]
    f = S.synthesize_fold(ex, [6, 5, 8], "xs")
    assert f is not None
    ns = {}
    exec(S.fold_source("fn_f", ["xs"], f), ns)            # noqa: S102
    assert ns["fn_f"]([4, 4]) == 8


def test_observational_equivalence_collapses():
    ins = [{"x": 1}, {"x": 2}, {"x": 3}]
    b = S.Bank(ins, max_size=5)
    sigs = [tuple(S._canon(v) for v in e[1]) for e in b.entries]
    assert len(sigs) == len(set(sigs))


def test_template_emits_compilable_pipeline_without_removed_switches():
    from nexus import oop_template as T
    T.reset()
    fields = {f: ("b", "get", ("var", "a"), ("const", f)) for f in T.ROW_FIELDS}
    ch = {d: o[0] for d, o in T.DECISIONS.items() if d not in T.SYNTH_HOLES}
    ch["syn_decode"] = T.register("syn_decode", dict(kind="record", fields=fields))
    ch["syn_net"] = T.register("syn_net", dict(kind="function", node=("b", "get", ("var", "p"), ("const", "amount"))))
    ch["syn_status"] = T.register("syn_status", dict(kind="function", node=("const", "accepted")))
    ch["syn_silver"] = T.register("syn_silver", dict(kind="class", spec=dict(kind="organelle", key="key", order="sv", cmp=">",
                                                                              mode="tombstone", drop=("const", False), witness=None)))
    code = T.emit(ch)
    compile(code, "pipeline.py", "exec")
    for d in T.REMOVED:
        assert f'DEC["{d}"]' not in code
    snap = T.snapshot()
    T.register("syn_net", dict(kind="function", node=("const", 0.0)))
    T.restore(snap)
    assert T.DECISIONS["syn_net"] == [ch["syn_net"]]


def test_monitor_never_crashes_on_malformed_pipeline_value():
    from nexus import oop_reconcile as R
    assert R._numeq(None, 1.0) is False and R._numeq("1.0", 1.0) is True


def test_grant_recorded_once_and_budget_includes_all_debits():
    g = json.loads((ROOT / "artifacts/de_oop_grant.json").read_text())
    assert g["id"] == "GRANT-NEXUS-DE-OOP-36000S" and g["available_s"] == 34139 and g["cumulative_s"] == 53990
    src = (ROOT / "scripts/oop_budget.py").read_text()
    for p in ('"w41"', '"de-"', '"de2-"', '"r1-"', '"r2-"', '"oop-"'):
        assert p in src
