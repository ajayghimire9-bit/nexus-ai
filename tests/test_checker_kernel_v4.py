"""Checker v4 validation (docs/NEXUS_CHECKER_V4_SPEC.md). Two independent implementations of the Wave 38 semantics are
cross-checked (checker_kernel_v4 vs the prover's w38_lang); verdicts are compared with brute-force enumeration; targeted
adversarial cases; pins. No experiment runs."""
import hashlib
import itertools
import random
from pathlib import Path

from nexus import checker_kernel_v4 as V4
from nexus import w38_domains as D
from nexus import w38_lang as L
from nexus import w38_scope as S

ROOT = Path(__file__).resolve().parents[1]


def test_pins_and_isolation():
    for f in ("checker_kernel.py", "checker_kernel_v2.py", "checker_kernel_v3.py", "checker_kernel_v4.py"):
        pin = (ROOT / "src/nexus" / f.replace(".py", ".sha256")).read_text().split()[0]
        assert hashlib.sha256((ROOT / "src/nexus" / f).read_bytes()).hexdigest() == pin, f
    imports = [l for l in (ROOT / "src/nexus/checker_kernel_v4.py").read_text().splitlines() if l.startswith(("import ", "from "))]
    assert imports == ["import json"]


def _values(n=60):
    r = random.Random(1)
    vals = []
    for t in D.stream("v4diff", n_per=2):
        vals += [p[0] for p in t["public"]] + [p[1] for p in t["public"]] + [t["query"]]
    vals += [[r.randint(-3, 9) for _ in range(r.randint(0, 6))] for _ in range(n)]
    vals += ["".join(r.choice("ab,;=|9 ") for _ in range(r.randint(0, 10))) for _ in range(n)]
    vals += [[r.choice(["a", "b", "12", ""]) for _ in range(r.randint(0, 4))] for _ in range(n)]
    return vals


def test_differential_interpreters_on_every_scope_tool():
    """Every tool of every declared scope, applied to a broad value pool, by both implementations."""
    vals = _values()
    tools = {}
    for t in D.stream("v4diff", n_per=1):
        for tl in S.scope(t["public"], t["query"], 2)["tools"]:
            tools[L.key(tl)] = tl
    assert len(tools) > 400
    n = 0
    for tl in tools.values():
        assert V4.known(tl), tl
        for v in vals:
            a, b = L.run([tl], v), V4.apply_chain([tl], v)
            assert (a == L.ERROR and b is None) or (a != L.ERROR and b is not None and L.key(a) == V4.ck(b)), (tl, v, a, b)
            n += 1
    assert n > 50000


def _brute(pub, q, tools, d):
    answers = {}
    for k in range(1, d + 1):
        for ch in itertools.product(range(len(tools)), repeat=k):
            c = [tools[i] for i in ch]
            if all(L.key(L.run(c, x)) == L.key(y) for x, y in pub):
                a = L.run(c, q)
                answers.setdefault("<ERROR>" if a == L.ERROR else L.key(a), list(ch))
    return answers


def test_verdicts_match_brute_force_on_small_scopes():
    r = random.Random(4)
    checked = 0
    for t in D.stream("v4brute", n_per=1):
        full = S.scope(t["public"], t["query"], 2)["tools"]
        keys = {L.key(x) for x in t["teacher"]}
        sub = [x for x in full if L.key(x) in keys] + r.sample(full, 14)
        if len(t["teacher"]) > 2:
            continue
        sc = {"kind": "exhaustive", "tools": sub, "max_depth": 2}
        ans = L.run(t["teacher"], t["query"])
        v = V4.check({"checker_version": 4, "public": t["public"], "query": t["query"], "claimed_answer": ans,
                      "candidate": t["teacher"], "scope": sc})
        b = _brute(t["public"], t["query"], sub, 2)
        assert v.get("answers", 1 if v["label"] == "exhaustive_UNIQUE" else None) == len(b) or v["label"] == "ABSTAIN"
        if v["label"] == "AMBIGUOUS":
            assert sorted(b)[:2] == [w["answer"] for w in v["witnesses"]]
            assert [b[a] for a in sorted(b)[:2]] == [w["chain"] for w in v["witnesses"]]
        checked += 1
    assert checked >= 4


def test_agree_on_demos_diverge_on_query_inside_parent():
    # filter(x > 0) and filter(x > 1) agree on demos with no 1s; they diverge on a query containing 1, seen only after fold
    pub = [[[0, 2, 3], 5], [[4, 0, 5], 9]]
    q = [1, 2]
    tools = [{"op": "filter", "p": ["gt", ["x"], ["c", 0]]}, {"op": "filter", "p": ["gt", ["x"], ["c", 1]]},
             {"op": "fold", "o": "add", "init": 0}]
    cand = [tools[0], tools[2]]
    v = V4.check({"checker_version": 4, "public": pub, "query": q, "claimed_answer": L.run(cand, q), "candidate": cand,
                  "scope": {"kind": "exhaustive", "tools": tools, "max_depth": 2}})
    assert v["label"] == "AMBIGUOUS" and v["k"] == 2


def test_rejections():
    t = D.stream("v4rej", n_per=1)[0]
    sc = S.scope(t["public"], t["query"], len(t["teacher"]))
    ev = {"checker_version": 4, "public": t["public"], "query": t["query"], "claimed_answer": t["answer"],
          "candidate": t["teacher"], "scope": sc}
    assert V4.check(dict(ev, checker_version=3))["reason"] == "wrong_checker_version"
    assert V4.check(dict(ev, claimed_answer="nope"))["reason"] == "candidate_fails"
    assert V4.check(dict(ev, candidate=[{"op": "exec", "code": "x"}]))["reason"] == "unsupported"
    assert V4.check(dict(ev, proofs=[{"axiom": "x"}]))["reason"] == "lemmas_or_proofs_not_accepted_in_v4"
