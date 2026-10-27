"""Checker v5 validation (docs/NEXUS_CHECKER_V5_SPEC.md). Two independent implementations of the Wave 39 semantics are
cross-checked (checker_kernel_v5 vs the prover's w39_lang) on > 50,000 tool-value pairs; verdicts, per-extra-query answer
counts and leave-one-out sets are compared with brute-force enumeration; adversarial edge cases; pins. No experiment runs.
PROSE-dev (quarantined development data) supplies realistic values; PROSE-confirm is never read here."""
import glob
import hashlib
import itertools
import json
import random
from pathlib import Path

from nexus import checker_kernel_v5 as V5
from nexus import w38_domains as D
from nexus import w39_lang as L
from nexus import w39_scope as S

ROOT = Path(__file__).resolve().parents[1]
X = ["x"]


def test_pins_and_isolation():
    for f in ("checker_kernel.py", "checker_kernel_v2.py", "checker_kernel_v3.py", "checker_kernel_v4.py", "checker_kernel_v5.py"):
        pin = (ROOT / "src/nexus" / f.replace(".py", ".sha256")).read_text().split()[0]
        assert hashlib.sha256((ROOT / "src/nexus" / f).read_bytes()).hexdigest() == pin, f
    imports = [l for l in (ROOT / "src/nexus/checker_kernel_v5.py").read_text().splitlines() if l.startswith(("import ", "from "))]
    assert imports == ["import json"]


def _prose_dev():
    out = []
    for f in sorted(glob.glob(str(ROOT / "artifacts/external/prose/*.json"))):
        ex = json.load(open(f))["Examples"]
        if len(ex) < 4:
            continue
        conv = (lambda e: list(e["Input"])) if any(len(e["Input"]) != 1 for e in ex) else (lambda e: e["Input"][0])
        out.append({"public": [[conv(e), e["Output"]] for e in ex[:3]], "query": conv(ex[3]),
                    "heldout": [[conv(e), e["Output"]] for e in ex[3:12]]})
    return out


def _values():
    r = random.Random(5)
    vals = []
    for t in D.stream("v5diff", n_per=1):
        vals += [p[0] for p in t["public"]] + [p[1] for p in t["public"]] + [t["query"]]
    for t in _prose_dev():
        vals += [p[0] for p in t["public"]] + [p[1] for p in t["public"]] + [t["query"]] + [p[0] for p in t["heldout"][:3]]
    for _ in range(40):
        s = r.choice(["", "-"]) + "".join(r.choice("0123456789") for _ in range(r.randint(1, 6)))
        if r.random() < 0.6:
            s += "." + "".join(r.choice("0123456789") for _ in range(r.randint(1, 7)))
        vals.append(s)
    vals += ["-0", "-0.000", "0.5", "-0.5", "2.5", "-2.5", "999.95", "0", "00012", "1.", ".5", "-", "1.2.3", "١٢", "1e3"]
    vals += ["".join(r.choice("aZ09 -.,$:/xYé") for _ in range(r.randint(0, 14))) for _ in range(40)]
    vals += [[r.choice(["ab", "12", "", "X9", "3.5"]) for _ in range(r.randint(0, 4))] for _ in range(20)]
    return vals


def _tools():
    tools = {}
    for t in D.stream("v5diff", n_per=1):
        for tl in S.scope(t["public"], t["query"], 2)["tools"]:
            tools[L.key(tl)] = tl
    for t in _prose_dev():
        for tl in S.scope(t["public"], t["query"], 2)["tools"]:
            tools[L.key(tl)] = tl
    grid = [{"op": "fn", "f": ["drnd", X, k, m, s]} for k in range(-3, 4) for m in "hfc" for s in (1, 2, 5)]
    grid += [{"op": "fn", "f": ["dsh", X, e]} for e in range(-6, 7)]
    grid += [{"op": "fn", "f": ["at", X, i]} for i in range(-8, 9)]
    grid += [{"op": "fn", "f": ["sl", X, a, b]} for a in (None, -8, -3, -1, 0, 2, 8) for b in (None, -8, -2, 0, 1, 5, 8)]
    grid += [{"op": "fn", "f": ["pad", X, n, c]} for n in (1, 3, 8) for c in ("0", " ")]
    grid += [{"op": "fn", "f": [h, X]} for h in ("cap", "shape")] + [{"op": "toks", "c": c} for c in "dawsn"]
    grid += [{"op": "dflt", "v": "NA"}, {"op": "first", "p": ["eq", ["shape", X], ["c", "99"]], "v": "none"},
             {"op": "first", "p": ["isdig", X], "v": None},     # legitimate None result (v4 kernel conflated it with ERROR) {"op": "fn", "f": ["len", ["at", X, -1]]},
             {"op": "map", "f": ["drnd", ["sl", X, 0, 4], 1, "h", 1]}]
    for tl in grid:
        tools[L.key(tl)] = tl
    return list(tools.values())


def test_differential_interpreters_on_every_scope_tool():
    vals, tools = _values(), _tools()
    assert len(tools) > 900
    n = 0
    for tl in tools:
        assert V5.known(tl), tl
        for v in vals:
            a, b = L.run([tl], v), V5.apply_chain([tl], v)
            assert (a == L.ERROR and b is V5.ERRK) or (a != L.ERROR and b is not V5.ERRK and L.key(a) == V5.ck(b)), (tl, v, a, b)
            n += 1
    assert n > 50000


def _brute(pub, q, extra, tools, d):
    answers, xans, loo = {}, [set() for _ in extra], [set() for _ in pub]
    for k in range(1, d + 1):
        for ch in itertools.product(range(len(tools)), repeat=k):
            c = [tools[i] for i in ch]
            miss = [j for j, (x, y) in enumerate(pub) if L.key(L.run(c, x)) != L.key(y)]
            qa = L.key(L.run(c, q)) if L.run(c, q) != L.ERROR else "<ERROR>"
            if len(miss) == 1:
                loo[miss[0]].add(qa)
            if miss:
                continue
            for j in range(len(pub)):
                loo[j].add(qa)
            answers.setdefault(qa, list(ch))
            for i, x in enumerate(extra):
                o = L.run(c, x)
                xans[i].add("<ERROR>" if o == L.ERROR else L.key(o))
    return answers, xans, loo


def test_verdicts_extras_and_loo_match_brute_force():
    from nexus import w38_learn as K
    from nexus import w39_search as Q
    r = random.Random(9)
    cases = [(t["public"], t["query"], [x for x, _ in t["heldout"][1:5]]) for t in _prose_dev()]
    cases += [(t["public"], t["query"], [L.run(t["teacher"], t["public"][0][0])]) for t in D.stream("v5brute", n_per=1)
              if len(t["teacher"]) <= 2]
    checked = 0
    for pub, q, extra in cases:
        full = S.scope(pub, q, 2)["tools"]
        found = Q.search(pub, q, full, 2, K.cost_matrix(None, full), budget=200000)
        if found is None or L.run(found, q) == L.ERROR:
            continue
        keys = {L.key(x) for x in found}
        sub = [x for x in full if L.key(x) in keys] + r.sample([x for x in full if L.key(x) not in keys], 16)
        v = V5.check({"checker_version": 5, "public": pub, "query": q, "claimed_answer": L.run(found, q), "candidate": found,
                      "scope": {"kind": "exhaustive", "tools": sub, "max_depth": 2}, "extra_queries": extra})
        b, xans, loo = _brute(pub, q, extra, sub, 2)
        assert v["answers"] == len(b)
        assert [e["answers"] for e in v["extra"]] == [len(s) for s in xans]
        assert v["warning_reasons"]["loo_fragile"] == [j for j in range(len(loo)) if len(loo[j]) > 1]
        assert (v["label"] == "SCOPE_UNIQUE") == (len(b) == 1)
        if v["label"] == "AMBIGUOUS":
            assert sorted(b)[:2] == [w["answer"] for w in v["witnesses"]]
        assert v["warnings"] == (["UNDER_SPECIFIED_WARNING"] if any(len(s) > 1 for s in xans) else [])
        checked += 1
    assert checked >= 20


def test_type_pruning_is_sound():
    # the target is a string: list-valued final tools are skipped, yet every fitting chain is still counted
    pub = [["a b", "a"], ["c d", "c"]]
    tools = [{"op": "words"}, {"op": "fn", "f": ["at", X, 0]}, {"op": "fn", "f": ["fst", X]}, {"op": "chars"},
             {"op": "fn", "f": ["sl", X, 0, 1]}, {"op": "rev"}]
    v = V5.check({"checker_version": 5, "public": pub, "query": "e f", "claimed_answer": "e", "candidate": [tools[0], tools[1]],
                  "scope": {"kind": "exhaustive", "tools": tools, "max_depth": 2}})
    b, _, _ = _brute(pub, "e f", [], tools, 2)
    assert v["label"] == "SCOPE_UNIQUE" and len(b) == 1
    assert v["fitting"] == sum(1 for k in (1, 2) for ch in itertools.product(range(6), repeat=k)
                               if all(L.key(L.run([tools[i] for i in ch], x)) == L.key(y) for x, y in pub))


def test_adversarial_decimal_and_index_cases():
    f = lambda e, x: V5.apply_chain([{"op": "fn", "f": e}], x)
    assert f(["drnd", X, 0, "h", 1], "2.5") == "3" and f(["drnd", X, 0, "h", 1], "-2.5") == "-3"
    assert f(["drnd", X, 1, "h", 1], "-0.04") == "0.0"                          # no negative zero
    assert f(["drnd", X, 0, "f", 1], "-0.5") == "-1" and f(["drnd", X, 0, "c", 1], "-0.5") == "0"
    assert f(["drnd", X, -2, "h", 1], "949.99") == "900" and f(["drnd", X, 1, "h", 5], "2342.35") == "2342.5"
    assert f(["dsh", X, -3], "-12.5") == "-0.0125" and f(["dsh", X, 2], "0.0150") == "1.5" and f(["dsh", X, 0], "-0.000") == "0"
    for bad in ("1.", ".5", "-", "1.2.3", "١٢", "1e3", "", " 1"):
        assert f(["dsh", X, 1], bad) is V5.ERRK and L.run([{"op": "fn", "f": ["dsh", X, 1]}], bad) == L.ERROR
    assert f(["at", X, -3], "ab") is V5.ERRK and f(["at", X, -2], "ab") == "a" and f(["sl", X, 5, None], "ab") == ""
    assert V5.apply_chain([{"op": "toks", "c": "n"}], "$2,488.51.") == ["2", "488.51"]
    assert V5.apply_chain([{"op": "fn", "f": X}], "x" * 257) is V5.ERRK


def test_rejections_and_contract():
    t = _prose_dev()[0]
    sc = S.scope(t["public"], t["query"], 2)
    c = [{"op": "toks", "c": "n"}, {"op": "fold", "o": "cat", "init": ""}]
    ev = {"checker_version": 5, "public": t["public"], "query": t["query"], "claimed_answer": L.run(c, t["query"]),
          "candidate": c, "scope": sc}
    v = V5.check(ev)
    assert v["label"] in ("SCOPE_UNIQUE", "AMBIGUOUS") and v["scope_relative"] is True
    assert V5.check(dict(ev, checker_version=4))["reason"] == "wrong_checker_version"
    assert V5.check(dict(ev, claimed_answer="nope"))["reason"] == "candidate_fails"
    assert V5.check(dict(ev, candidate=[{"op": "exec", "code": "x"}]))["reason"] == "unsupported"
    assert V5.check(dict(ev, proofs=[{"axiom": "x"}]))["reason"] == "lemmas_or_proofs_not_accepted_in_v5"
    assert V5.check(dict(ev, extra_queries=["1"] * 17))["reason"] == "malformed"
