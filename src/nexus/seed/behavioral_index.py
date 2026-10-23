"""Behavioral indexing for investigation search. Not zero-cost pruning.

Static properties may soundly eliminate a candidate without executing it on the
current input. Empirical fingerprints from previous executions may reorder
candidates. They do not establish behavior on a new input and must not discard
a potentially correct program.

Index construction and maintenance are charged. This is measured against
simple enumeration; it is not a claim of cheaper search until compared.
"""
from __future__ import annotations

from typing import Any, Callable

from .combined_investigation_engine import apply_primitive_op


# Sound length effects of primitive operators. Unknown ops are treated as open.
LENGTH_PRESERVING = frozenset({
    "reverse", "increment", "decrement", "double", "abs_val", "clamp_zero",
    "square", "sort_asc", "running_sum",
})
MAY_SHRINK = frozenset({"filter_positive", "filter_even", "unique_stable"})


def length_effect(ops: tuple[str, ...]) -> str:
    if not ops:
        return "preserve"
    if any(op not in LENGTH_PRESERVING | MAY_SHRINK for op in ops):
        return "unknown"
    if any(op in MAY_SHRINK for op in ops):
        return "may_shrink"
    return "preserve"


def support_requires_shrink(support_examples: list) -> bool:
    for inp, out in support_examples:
        if isinstance(inp, list) and isinstance(out, list) and len(out) < len(inp):
            return True
    return False


def produces_sorted_list(support_examples: list) -> bool:
    """Observed I/O property: every support output happens to be a sorted list."""
    rows = [out for _inp, out in support_examples if isinstance(out, list)]
    return bool(rows) and all(out == sorted(out) for out in rows)


def appears_monotonic_on_support(support_examples: list) -> bool:
    """Different from produces_sorted_list: pairwise input order vs output order.

    For equal-length list pairs, checks whether componentwise x<=y implies f(x)<=f(y)
    on the observed support only. This is not a sound program-level theorem.
    """
    pairs = [(inp, out) for inp, out in support_examples
             if isinstance(inp, list) and isinstance(out, list) and len(inp) == len(out)]
    if len(pairs) < 2:
        return False
    for i, (xa, ya) in enumerate(pairs):
        for xb, yb in pairs[i + 1:]:
            if len(xa) != len(xb):
                continue
            if all(a <= b for a, b in zip(xa, xb)) and any(c > d for c, d in zip(ya, yb)):
                return False
            if all(a <= b for a, b in zip(xb, xa)) and any(c > d for c, d in zip(yb, ya)):
                return False
    return True


def sound_static_elimination(ops: tuple[str, ...], support_examples: list) -> tuple[bool, str | None]:
    """Eliminate only when a static length theorem contradicts observed support.

    A length-preserving pipeline cannot produce a shorter list. This does not
    use empirical fingerprints and does not execute the candidate.
    """
    if support_requires_shrink(support_examples) and length_effect(ops) == "preserve":
        return True, "length_preserving_cannot_produce_shorter_output"
    return False, None


def input_key(value: Any) -> str:
    import json
    return json.dumps(value, sort_keys=True, default=str)


class BehavioralIndex:
    """Empirical fingerprints plus charged static notes. Never a discard rule."""

    def __init__(self) -> None:
        self.fingerprints: dict[str, dict[str, Any]] = {}
        self.construction_events = 0

    def remember_execution(self, candidate_id: str, inp: Any, output: Any) -> None:
        self.fingerprints.setdefault(candidate_id, {})[input_key(inp)] = output
        self.construction_events += 1

    def prioritize(self, candidates: list, support_examples: list) -> list:
        """Reorder by how many remembered support keys match. Do not drop."""
        def score(item):
            cid = item[0]
            known = self.fingerprints.get(cid, {})
            hits = 0
            for inp, expected in support_examples:
                token = input_key(inp)
                if token in known and known[token] == expected:
                    hits += 1
            return -hits
        return sorted(candidates, key=score)


def family_key(ops: tuple[str, ...]) -> str:
    return ops[0] if ops else ""


def stratified_representatives(remaining: list, batch_size: int) -> tuple[list, dict[str, Any]]:
    """One unchecked program per leading-operator family, then fill the batch.

    Checking a representative does not eliminate siblings in that family.
    """
    seen: set[str] = set()
    batch = []
    for item in remaining:
        fam = family_key(item[1])
        if fam in seen:
            continue
        seen.add(fam)
        batch.append(item)
        if len(batch) >= batch_size:
            break
    if len(batch) < batch_size:
        chosen = {item[0] for item in batch}
        for item in remaining:
            if item[0] in chosen:
                continue
            batch.append(item)
            if len(batch) >= batch_size:
                break
    note = {
        "strategy": "stratified",
        "families_represented": sorted(seen),
        "family_representative_eliminates_siblings": False,
    }
    return batch, note
