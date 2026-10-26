"""NEXUS read-only Checker Kernel (Wave 30). DO NOT MODIFY without explicit owner approval (AGENTS.md, Wave 30
rule; pinned by tests/test_checker_kernel.py against src/nexus/checker_kernel.sha256).

Standard library only; shares no code with the prover. It re-derives everything it relies on:

  * its own interpreter for the declared mechanism language (`OPS` below);
  * its own table of postconditions and of which mechanisms preserve them;
  * its own exhaustive enumeration of the declared finite scope.

Input: an Evidence Object (a JSON-serialisable dict):
    {"version": 1,
     "public": [[x, y], ...],            # passive pairs + any charged active pairs (observations, trusted)
     "query": q, "claimed_answer": a,
     "candidate": [spec, ...],           # the prover's program (a chain of mechanism specs)
     "scope": {"kind": "exhaustive" | "proposal", "tools": [spec, ...], "max_depth": d},
     "lemmas": [{"tool": i, "post": [...], "public_index": j}, ...],   # pruning lemmas the prover used
     "trace": {...}}                     # prover's residual enumeration statistics (recorded, not trusted)

Labels:
  * exhaustive_UNIQUE: every program of size <= d over the declared tools that fits every public pair gives the
    claimed answer on the query, and the scope is the declared full grammar. This is a stronger notion than a
    minimal-size certificate.
  * proposal_relative_UNIQUE: the same, but the scope is a proposal (a subset chosen by a proposer).
  * AMBIGUOUS(k): fitting programs give k > 1 distinct query answers. A program that fits but raises on the
    query counts as its own answer.
  * ABSTAIN: the evidence is malformed, uses unknown mechanisms, the candidate does not fit or does not give the
    claimed answer, a lemma is not verified, the scope exceeds the kernel's enumeration cap, or the claimed
    answer is not the unique one.

Pruning lemmas are re-verified, never trusted. Lemma (t, P, j) says: postcondition P of tool t is violated by
public output j. The kernel checks that P is one of t's own postconditions (from the kernel's table) and that
output j violates it. A chain is then skipped only if it cannot fit: some pruned tool is followed only by tools
that preserve all of its verified violated postconditions, or a pruned tool comes last.

What the kernel buys is a small, independent trusted base. Checking finite-scope uniqueness costs about as much
as the enumeration itself, so it is not faster than proving.
"""
import itertools
import json

KERNEL_VERSION = 1
MAX_CHAINS = 3_000_000
RAISED = "<raised>"


# --------------------------------------------------------------------------- values
def key(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def get(item, path):
    if path == ".":
        return item
    if isinstance(item, dict) and path in item:
        return item[path]
    raise KeyError(path)


# --------------------------------------------------------------------------- interpreter
def _pred(spec, item):
    v = get(item, spec["path"])
    if spec["cmp"] == "eq":
        return v == spec["val"]
    if not _num(v):
        return False
    return v >= spec["val"] if spec["cmp"] == "ge" else v <= spec["val"]


def _order(xs, path, desc):
    idx = list(range(len(xs)))
    if path == "#":
        return idx[::-1] if desc else idx
    def k(i):
        v = get(xs[i], path)
        if desc:
            if not _num(v):
                raise TypeError("desc order on non-number")
            return (-v, i)
        return (v, i)
    return sorted(idx, key=k)


def _need_list(xs):
    if not isinstance(xs, list):
        raise TypeError("list mechanism on a non-list")


def _need_nums(xs):
    if not all(_num(v) for v in xs):
        raise TypeError("numeric mechanism on non-numbers")


def apply(spec, xs):
    op = spec["op"]
    _need_list(xs)
    if op == "F":
        return [x for x in xs if _pred(spec["pred"], x)]
    if op == "S":
        return [xs[i] for i in _order(xs, spec["path"], spec["desc"])][: spec["k"]]
    if op == "Sort":
        return [xs[i] for i in _order(xs, spec["path"], spec["desc"])]
    if op == "comp":
        n = len(xs)
        out, seen = [], set()
        for pos, i in enumerate(_order(xs, spec["path"], spec["desc"])):
            x = xs[i]
            c = spec["cond"]
            if c == "all":
                ok = True
            elif c == "head":
                ok = pos < spec["cparam"]
            elif c == "tail":
                ok = pos >= n - spec["cparam"]
            elif c == "first_occ":
                kk = key(get(x, spec["cparam"]))
                ok = kk not in seen
                seen.add(kk)
            elif c == "pred":
                ok = _pred(spec["cparam"], x)
            else:
                raise ValueError(c)
            if ok:
                out.append(get(x, spec["tparam"]) if spec["transform"] == "proj" else x)
        return out
    # ---- Wave 30 A1 extensions (fixed DSL: arithmetic maps, accumulators, objects, bounded loops)
    if op == "proj":
        return [get(x, spec["path"]) for x in xs]
    if op == "map_add":
        _need_nums(xs)
        return [x + spec["c"] for x in xs]
    if op == "map_mul":
        _need_nums(xs)
        return [x * spec["c"] for x in xs]
    if op == "map_mod":
        _need_nums(xs)
        return [x % spec["c"] for x in xs]
    if op == "prefix_sum":
        _need_nums(xs)
        out, acc = [], 0
        for x in xs:
            acc += x
            out.append(acc)
        return out
    if op == "running_max":
        _need_nums(xs)
        out = []
        for x in xs:
            out.append(x if not out else max(out[-1], x))
        return out
    if op == "diff":
        _need_nums(xs)
        return [b - a for a, b in zip(xs, xs[1:])]
    if op == "rotate":
        if not xs:
            return []
        k = spec["k"] % len(xs)
        return xs[k:] + xs[:k]
    if op == "run_heads":
        out = []
        for x in xs:
            if not out or key(out[-1]) != key(x):
                out.append(x)
        return out
    if op == "group_count":
        order, cnt = [], {}
        for x in xs:
            kk = key(get(x, spec["path"]))
            if kk not in cnt:
                order.append(kk)
                cnt[kk] = 0
            cnt[kk] += 1
        return [cnt[kk] for kk in order]
    if op == "repeat":
        for _ in range(spec["n"]):
            xs = apply(spec["body"], xs)
            _need_list(xs)
        return xs
    raise ValueError(f"unknown op {op}")


def run(chain, x):
    for spec in chain:
        x = apply(spec, x)
    return x


def known(spec):
    try:
        op = spec["op"]
    except Exception:
        return False
    if op == "repeat":
        return isinstance(spec.get("n"), int) and 0 < spec["n"] <= 4 and known(spec.get("body"))
    return op in {"F", "S", "Sort", "comp", "proj", "map_add", "map_mul", "map_mod", "prefix_sum", "running_max",
                  "diff", "rotate", "run_heads", "group_count"}


# --------------------------------------------------------------------------- postconditions (kernel's own table)
def posts(spec):
    """Postconditions of a mechanism's output, closed under the preservation rules below."""
    op = spec["op"]
    out = []
    if op == "F":
        out.append(["all", spec["pred"]])
    if op == "S":
        out.append(["len_le", spec["k"]])
    if op == "comp" and spec["transform"] == "id":
        c = spec["cond"]
        if c in ("head", "tail"):
            out.append(["len_le", spec["cparam"]])
        if c == "pred":
            out.append(["all", spec["cparam"]])
        if c == "first_occ":
            out.append(["distinct", spec["cparam"]])
    if op in ("S", "Sort") or (op == "comp" and spec["transform"] == "id"):
        if spec["path"] != "#":
            out.append(["sorted", spec["path"], bool(spec["desc"])])
    return out


def item_preserving(spec):
    """Output is a sub-multiset of the input's items (proved by construction for these ops)."""
    op = spec["op"]
    return op in ("F", "S", "Sort", "rotate", "run_heads") or (op == "comp" and spec["transform"] == "id")


def subsequence(spec):
    """Output is a subsequence of the input (order kept)."""
    op = spec["op"]
    if op in ("F", "run_heads"):
        return True
    if op == "S":
        return spec["path"] == "#" and not spec["desc"]
    if op == "comp":
        return spec["transform"] == "id" and spec["path"] == "#" and not spec["desc"]
    return False


def preserves(g, post):
    if post[0] == "sorted":
        return subsequence(g)
    if post[0] == "len_le":
        return item_preserving(g) or g["op"] in ("proj", "map_add", "map_mul", "map_mod", "prefix_sum",
                                                 "running_max", "diff", "group_count")
    return item_preserving(g)


def violates(post, y):
    if not isinstance(y, list):
        return False
    kind = post[0]
    try:
        if kind == "len_le":
            return len(y) > post[1]
        if kind == "all":
            return not all(_pred(post[1], it) for it in y)
        if kind == "distinct":
            ks = [key(get(it, post[1])) for it in y]
            return len(ks) != len(set(ks))
        if kind == "sorted":
            vals = [get(it, post[1]) for it in y]
            if not all(_num(v) for v in vals):
                return False
            return any((a < b) if post[2] else (a > b) for a, b in zip(vals, vals[1:]))
    except Exception:
        return False
    return False


# --------------------------------------------------------------------------- check
def _abstain(reason, **kw):
    return dict(label="ABSTAIN", reason=reason, **kw)


def check(evidence):
    """Verify an Evidence Object; return {label, k?, reason?, fitting, answers, chains_checked}."""
    try:
        pub = [(p[0], p[1]) for p in evidence["public"]]
        q = evidence["query"]
        claimed = evidence["claimed_answer"]
        cand = list(evidence["candidate"])
        scope = evidence["scope"]
        tools = list(scope["tools"])
        d = int(scope["max_depth"])
        kind = scope["kind"]
        lemmas = list(evidence.get("lemmas", []))
    except Exception:
        return _abstain("malformed")
    if kind not in ("exhaustive", "proposal") or d < 1 or not pub:
        return _abstain("malformed")
    if not all(known(s) for s in tools + cand):
        return _abstain("unknown_mechanism")
    tk = [key(s) for s in tools]
    if not all(key(s) in set(tk) for s in cand) or not 1 <= len(cand) <= d:
        return _abstain("candidate_outside_scope")
    try:
        if not all(key(run(cand, x)) == key(y) for x, y in pub) or key(run(cand, q)) != key(claimed):
            return _abstain("candidate_fails")
    except Exception:
        return _abstain("candidate_fails")
    # verify lemmas
    viol = {}
    for lm in lemmas:
        try:
            i, post, j = int(lm["tool"]), lm["post"], int(lm["public_index"])
            if key(post) not in {key(p) for p in posts(tools[i])} or not violates(post, pub[j][1]):
                return _abstain("bad_lemma", lemma=lm)
        except Exception:
            return _abstain("bad_lemma", lemma=lm)
        viol.setdefault(i, []).append(post)
    n_chains = sum(len(tools) ** k for k in range(1, d + 1))
    if n_chains > MAX_CHAINS:
        return _abstain("scope_too_large", chains=n_chains)
    xs = [x for x, _ in pub] + [q]
    targets = [key(y) for _, y in pub]
    answers, fitting, checked = {}, 0, 0

    def can_fit(chain):
        if chain[-1] in viol:
            return False
        for a, i in enumerate(chain):
            if i in viol and all(all(preserves(tools[g], p) for p in viol[i]) for g in chain[a + 1:]):
                return False
        return True

    for k in range(1, d + 1):
        for chain in itertools.product(range(len(tools)), repeat=k):
            if not can_fit(chain):
                continue
            checked += 1
            ok = True
            outs = []
            for v, t in zip(xs[:-1], targets):
                try:
                    o = run([tools[i] for i in chain], v)
                except Exception:
                    ok = False
                    break
                if key(o) != t:
                    ok = False
                    break
            if not ok:
                continue
            fitting += 1
            try:
                a = key(run([tools[i] for i in chain], q))
            except Exception:
                a = RAISED
            answers[a] = answers.get(a, 0) + 1
    res = dict(fitting=fitting, answers=len(answers), chains_checked=checked, chains_total=n_chains)
    if len(answers) > 1:
        return dict(label="AMBIGUOUS", k=len(answers), **res)
    if len(answers) != 1 or next(iter(answers)) != key(claimed):
        return dict(label="ABSTAIN", reason="claimed_not_unique", **res)
    return dict(label="exhaustive_UNIQUE" if kind == "exhaustive" else "proposal_relative_UNIQUE", **res)
