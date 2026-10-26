"""Wave 32 (bounded, NOT LOCKED): empty-library procedure evolution with a stepping-stone archive.

Editable scope: a typed, bounded POLICY GENOME, not arbitrary code. It covers search ordering, lemma policy,
active-probe policy, anti-unification heuristics and the online library-update policy. Frozen: Checker v2, the
sandbox, the external evaluator_work meter, certificate definitions (matched G_P depth 3), the splits and the
detectors. Unknown genes are rejected, and the frozen keys are forced by the runner.

An episode is an online stream, starting from an EMPTY library. After each task that the evaluator's checker labels
exhaustive_UNIQUE (label only), the child adds the candidate to its certified set and rebuilds its library with the
genome's anti-unification heuristics. That is the learning procedure under test. Every rebuild is metered (child
instructions).
"""
from __future__ import annotations

import random

GENES = {
    "order": ("canonical", "reverse", "macros_last", "short_first"),
    "lemmas": ("none", "all"),
    "macro_first": (True, False),
    "macro_depth": (1, 2),
    "probe_mut": (1, 2, 3),
    "probe_tries": (50, 150, 300),
    "max_holes": (0, 1),
    "min_support": (1, 2, 3),
    "cap": (10, 40, 200),
    "online": (True, False),
}
GEN0 = {"order": "canonical", "lemmas": "all", "macro_first": True, "macro_depth": 2, "probe_mut": 2,
        "probe_tries": 300, "max_holes": 1, "min_support": 1, "cap": 200, "online": True}
FROZEN = {"matched_depth": 3}


def validate(g):
    if set(g) != set(GENES) or any(g[k] not in GENES[k] for k in GENES):
        raise ValueError(f"genome outside the editable scope: {g}")
    return g


def mutate(g, rng, n=None):
    g = dict(g)
    for k in rng.sample(sorted(GENES), n or rng.choice((1, 2))):
        g[k] = rng.choice([v for v in GENES[k] if v != g[k]])
    return validate(g)


def gkey(g):
    return "|".join(f"{k}={g[k]}" for k in sorted(g))


def episode(ev, child, tasks, genome, tag):
    """One online stream from an empty library. Returns the rows plus learning cost (external meter only)."""
    from nexus import wave31_evaluator as E
    validate(genome)
    pol = dict({k: genome[k] for k in ("order", "lemmas", "macro_first", "macro_depth", "probe_mut", "probe_tries")},
               **FROZEN)
    lib, progs, rows, learn_instr = [], [], [], 0
    for k, t in enumerate(tasks):
        r = ev.solve(child, t, "Useful", "matched", lib, f"{tag}:{k}", pol)
        r["library_size"] = len(lib)
        rows.append(r)
        if genome["online"] and r["label"] == "exhaustive_UNIQUE":
            progs.append(r["candidate"])
            c0 = E.instructions(child.p.pid)
            lib = ev.library(child, progs, tag, max_holes=genome["max_holes"], depth=3,
                             min_support=genome["min_support"], cap=genome["cap"])["useful"]
            learn_instr += E.instructions(child.p.pid) - c0
    return rows, learn_instr


def fitness(rows, learn_instr):
    """Lexicographic: (wrong == 0 and no detector flag) first; then max correct; then min evaluator_work."""
    work = sum(r["ext"]["evaluator_work"] for r in rows) + learn_instr
    return dict(correct=sum(r["correct"] for r in rows), wrong=sum(r["wrong"] is not None for r in rows),
                exhaustive=sum(r["label"] == "exhaustive_UNIQUE" for r in rows), work=work,
                oracle=sum(r["ext"]["oracle_calls"] for r in rows), learn_instr=learn_instr)


def better(a, b):
    return (a["wrong"], -a["correct"], a["work"]) < (b["wrong"], -b["correct"], b["work"])


def pick_parent(archive, rng):
    """Stepping-stone selection: 2-way tournament on fitness among ALL admitted archive members (not just elites)."""
    a, b = rng.sample(archive, 2) if len(archive) > 1 else (archive[0], archive[0])
    return a if better(a["fit"], b["fit"]) else b
