"""Wave 41 base static primitive lemmas (SOLVER SIDE; NOT LOCKED). Given IDENTICALLY to every arm (Flat and hierarchical).

Abstract domain: the CHARACTER CONTENT of a value = every character of every string in it, including record keys (recursive).
Lemma (per tool, from the w39_lang semantics): for every input x on which tool t does not error,
        chars(t(x))  subset of  chars(x) | intro(t) | NUM,      NUM = digits and '-'
where intro(t) is computed syntactically from the tool spec (string constants, join/fill/pad characters, record keys the op
creates, case-mapping closure, decimal / shape alphabets). Ints can always be rendered by `str`, so NUM is treated as
always available. Unknown ops / lambdas -> ANY (no pruning). Soundness is tested by differential execution on every declared
v5 scope of the internal domains and PROSE-dev (tests/test_w41_lemmas.py), and the pruned search is tested to recover exactly
the brute-force fitting set.

Use in search (w41_search): a value state v with r steps left can produce public target y only if the characters y needs
beyond chars(v) | NUM can be introduced by r tools. For r = 1 this is checked per child tool BEFORE it is executed (the last
layer dominates every exhaustive sweep); for r >= 2 against the union of the scope's intros.
Composition (assume-guarantee): intro(t1 ; t2) = intro(t1) | intro(t2); a decomposition's summary is the union over its
stages, so a decomposition is excluded in O(1) when a public example needs a character none of its stages can introduce."""
from __future__ import annotations

import string

NUM = frozenset(string.digits + "-")
LETTERS = frozenset(string.ascii_letters)


class Intro:
    __slots__ = ("chars", "nonascii", "any")

    def __init__(self, chars=frozenset(), nonascii=False, any_=False):
        self.chars, self.nonascii, self.any = frozenset(chars), nonascii, any_

    def __or__(self, o):
        return Intro(self.chars | o.chars, self.nonascii or o.nonascii, self.any or o.any)

    def covers(self, need):
        if self.any or not need:
            return True
        rest = need - self.chars
        return not rest or (self.nonascii and all(ord(c) > 127 for c in rest))


EMPTY, ANY = Intro(), Intro(any_=True)
CASE = Intro(LETTERS, nonascii=True)          # lower / upper / cap (Python case mapping can leave ASCII)


def chars_of(v, acc=None, d=0):
    acc = set() if acc is None else acc
    if d > 8:
        return acc
    if isinstance(v, str):
        acc.update(v)
    elif isinstance(v, list):
        for e in v:
            chars_of(e, acc, d + 1)
    elif isinstance(v, dict):
        for k, e in v.items():
            acc.update(k)
            chars_of(e, acc, d + 1)
    return acc


def _const(v):
    return Intro(chars_of(v))


def lam_intro(e):
    if not isinstance(e, list) or not e:
        return ANY
    op = e[0]
    if op in ("x", "f"):
        return EMPTY
    if op == "c":
        return _const(e[1])
    if op in ("len", "int", "str", "even", "isdig", "not", "fst", "lst"):
        return lam_intro(e[1]) if op in ("fst", "lst", "str", "int") else EMPTY
    if op in ("low", "up", "cap"):
        return lam_intro(e[1]) | CASE
    if op in ("bef", "aft", "at", "sl"):
        return lam_intro(e[1])
    if op == "shape":
        return lam_intro(e[1]) | Intro("9Aa")
    if op == "pad":
        return lam_intro(e[1]) | _const(e[3])
    if op in ("dsh", "drnd"):
        return Intro(".")
    if op == "if":
        return lam_intro(e[2]) | lam_intro(e[3])
    if op in ("and", "or", "eq", "ne", "gt", "lt"):
        return EMPTY
    if op == "cat":
        return lam_intro(e[1]) | lam_intro(e[2])
    if op in ("add", "sub", "mul", "mod", "max", "min"):
        return EMPTY
    return ANY


KEYS = {"groupby": "keyitems", "countby": "keycount", "enum": "iv", "pairs": "ab", "objs": "colorsizecells"}


def intro(t):
    """Characters tool t may introduce beyond its input's characters and NUM (sound over-approximation)."""
    op = t.get("op")
    if op in ("map", "fn"):
        return lam_intro(t["f"])
    if op in ("filter", "sortby", "best", "take", "drop", "rev", "uniq", "flat", "split", "chars", "words", "strip", "get",
              "proj", "tjoin", "toks", "len"):
        return EMPTY
    if op in ("groupby", "countby"):
        return Intro(KEYS[op]) | lam_intro(t["f"])
    if op in ("enum", "pairs", "objs"):
        return Intro(KEYS[op])
    if op in ("fold", "scan"):
        return _const(t.get("init"))
    if op == "join":
        return _const(t.get("d", ""))
    if op in ("first", "dflt"):
        return _const(t.get("v"))
    if op == "fill":
        return _const(t.get("k", "")) | _const(t.get("v"))
    return ANY                                    # grids / graphs / anything unlisted: no pruning


class TaskLemmas:
    """Per-task lemma tables (built once per task; the cost is metered with the search)."""

    def __init__(self, public, tools):
        self.n = len(public)
        self.tchars = [frozenset(chars_of(y)) for _, y in public]
        self.intro = [intro(t) for t in tools]
        u = EMPTY
        for i in self.intro:
            u = u | i
        self.union = u
        self.skips = 0

    def need(self, vals):
        return [self.tchars[i] - chars_of(vals[i]) - NUM for i in range(self.n)]

    def tool_ok(self, t, need):
        it = self.intro[t]
        return all(it.covers(nd) for nd in need)

    def reachable(self, need, r):
        if r <= 0:
            return not any(need)
        return all(self.union.covers(nd) for nd in need)
