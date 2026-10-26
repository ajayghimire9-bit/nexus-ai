"""Wave 30 A4 / lineage interfaces (NOT evaluated yet).

* Typed skeletons come from AST anti-unification of kernel-certified programs (lists of op specs). Two programs
  with the same op shape generalise to a skeleton whose differing constants become typed holes. A skeleton is a
  representation proposal only. Round-trip and leave-one-demonstration-out (LODO) checks on it are empirical
  evidence; they do not prove task sufficiency, general correctness or pruning soundness. The kernel only
  certifies concrete instantiations, and ABSTAINs on any semantics it does not support.
* Lineage: every archive item records its parents. The ablation removes a skeleton's ancestors, without breaking
  the dependencies of the remaining items, and compares against a size-matched removal of non-ancestors. The
  metrics are the rediscovery rate and the number of semantically equivalent solutions (equal outputs on a probe
  set), not whether one exact string disappears.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hole:
    type: str

    def __repr__(self):
        return f"?{self.type}"


def _au(a, b):
    if type(a) is not type(b):
        return Hole(type(a).__name__ + "|" + type(b).__name__)
    if isinstance(a, dict):
        if set(a) != set(b):
            return Hole("dict")
        return {k: (a[k] if k == "op" and a[k] == b[k] else _au(a[k], b[k])) for k in sorted(a)} \
            if a.get("op") == b.get("op") else Hole("op")
    if isinstance(a, list):
        return [_au(x, y) for x, y in zip(a, b)] if len(a) == len(b) else Hole("list")
    return a if a == b else Hole(type(a).__name__)


def anti_unify(p, q):
    """Least general generalisation of two programs (lists of op specs); None if their op shapes differ."""
    if len(p) != len(q) or [s.get("op") for s in p] != [s.get("op") for s in q]:
        return None
    return [_au(a, b) for a, b in zip(p, q)]


def holes(sk):
    if isinstance(sk, Hole):
        return 1
    if isinstance(sk, dict):
        return sum(holes(v) for v in sk.values())
    if isinstance(sk, list):
        return sum(holes(v) for v in sk)
    return 0


@dataclass
class Item:
    id: str
    program: list
    parents: tuple = ()


@dataclass
class Archive:
    items: dict = field(default_factory=dict)

    def add(self, item):
        missing = [p for p in item.parents if p not in self.items]
        if missing:
            raise ValueError(f"unknown parents {missing}")
        self.items[item.id] = item

    def ancestors(self, iid):
        out, todo = set(), list(self.items[iid].parents)
        while todo:
            p = todo.pop()
            if p not in out:
                out.add(p)
                todo += list(self.items[p].parents)
        return out

    def without(self, remove):
        """Remove `remove` and re-attach orphaned children to the removed items' surviving ancestors, so the
        remaining items' dependencies stay well-formed."""
        a = Archive()
        for iid, it in self.items.items():
            if iid in remove:
                continue
            ps, todo = [], list(it.parents)
            while todo:
                p = todo.pop()
                if p in remove:
                    todo += list(self.items[p].parents)
                elif p not in ps:
                    ps.append(p)
            a.items[iid] = Item(iid, it.program, tuple(ps))
        return a

    def skeletons(self):
        progs = list(self.items.values())
        out = []
        for i in range(len(progs)):
            for j in range(i + 1, len(progs)):
                sk = anti_unify(progs[i].program, progs[j].program)
                if sk is not None and holes(sk) > 0:
                    out.append(sk)
        return out


def lineage_ablation(archive, target_id, rng=None):
    """Return (ancestor-ablated archive, size-matched control archive)."""
    rng = rng or random.Random(0)
    anc = archive.ancestors(target_id)
    others = [i for i in archive.items if i not in anc and i != target_id]
    ctrl = set(rng.sample(others, min(len(anc), len(others))))
    return archive.without(anc), archive.without(ctrl)
