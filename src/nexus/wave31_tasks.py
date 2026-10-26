"""Wave 31 increment 2 task generation: EVALUATOR SIDE ONLY (development, NOT LOCKED). The solver process never
imports this module. It never sees a teacher, an answer or a transfer label.

Leave-one-domain-out (LODO) rotation over the 4 domains. In fold h, source tasks come from the 3 other domains and
use the source core set S. Target tasks on the held-out domain h are teacher = LEAF[h] + core, in three
evaluator-only categories:
  * familiar_exact: a core seen verbatim in source, on the new surface (an exact mechanism clone);
  * compositional: a core NOT seen in source, but an instance of a skeleton that two source cores anti-unify to
    ([Sort, ?], [rotate, ?], [?, diff], [?, prefix_sum]); its new leaf is the held-out surface adapter;
  * held_out: a core with no skeleton support (no two source cores share its head or its tail).
Strings carry characters, so only the non-numeric cores apply there.
Adversarial set (built AFTER an arm's library is frozen, by an adversary that knows that library): teachers inside
the matched scope (leaf + 2 G_P ops) whose passive demos are fit by programs in the macro scope (G_P + library,
depth 2), all of which give the same WRONG query answer.
"""
from __future__ import annotations

import random

from nexus import checker_kernel_v2 as V
from nexus import wave31_grammar as G

S_CORES = (("Sort", "RUNH"), ("Sort", "diff"), ("Sort", "prefix_sum"), ("rotate", "diff"), ("rotate", "prefix_sum"),
           ("RUNH", "rotate"))
TARGET = {"familiar_exact": (("Sort", "RUNH"), ("rotate", "diff")),
          "compositional": (("Sort", "running_max"), ("rotate", "running_max"), ("RUNH", "diff"), ("RUNH", "prefix_sum")),
          "held_out": (("running_max", "rotate"), ("diff", "Sort"))}
STRING_TARGET = {"familiar_exact": (("Sort", "RUNH"), ("RUNH", "rotate")),
                 "compositional": (("Sort", "rotate"), ("rotate", "RUNH")),
                 "held_out": (("RUNH", "Sort"),)}
NUMERIC = {"prefix_sum", "diff", "running_max"}


def sample(domain, rng):
    if domain == "records":
        return [{"a": rng.randrange(6), "b": rng.randrange(6)} for _ in range(rng.randint(5, 7))]
    if domain == "strings":
        return "".join(rng.choice("abcd") for _ in range(rng.randint(5, 8)))
    if domain == "grids":
        n = rng.choice((3, 4))
        return [[rng.choice((0, 1, 1, 2, 3)) for _ in range(n)] for _ in range(n)]
    edges = sorted({(rng.randrange(7), rng.randrange(7)) for _ in range(9)} - {(i, i) for i in range(7)})
    return {"nodes": list(range(7)), "edges": [list(e) for e in edges]}


def teacher(domain, core):
    return [dict(t) for t in G.LEAF[domain]] + [dict(G.CORE_OPS[c]) for c in core]


def _task(domain, prog, rng, n_public, **labels):
    for _ in range(60):
        xs = [sample(domain, rng) for _ in range(n_public + 1)]
        ys = [V.run(prog, x)[0] for x in xs]
        if any(y == V.ERROR for y in ys) or len({V.key(y) for y in ys[:n_public]}) < 2:
            continue
        return dict(domain=domain, public=[[x, y] for x, y in zip(xs[:n_public], ys[:n_public])], query=xs[-1],
                    answer=ys[-1], teacher=prog, **labels)
    return None


def source_stream(split_seed, held_out, n_per=2):
    rng = random.Random(f"w31b-src:{split_seed}:{held_out}")
    out = []
    for d in G.DOMAINS:
        if d == held_out:
            continue
        for core in S_CORES:
            if d == "strings" and NUMERIC & set(core):
                continue
            for _ in range(n_per):
                t = _task(d, teacher(d, core), rng, 4, core=list(core), category="source")
                if t:
                    out.append(t)
    return out


def target_stream(split_seed, held_out, n_per=2):
    rng = random.Random(f"w31b-tgt:{split_seed}:{held_out}")
    out = []
    for cat, cores in (STRING_TARGET if held_out == "strings" else TARGET).items():
        for core in cores:
            for _ in range(n_per):
                t = _task(held_out, teacher(held_out, core), rng, 4, core=list(core), category=cat)
                if t:
                    out.append(t)
    return out


def adversarial_stream(split_seed, held_out, library, n_max=4, draws=4):
    """Adversary with full knowledge of the frozen library: every depth-3 teacher LEAF + [a, b] (a, b non-adapter
    G_P ops, in a seeded random order), `draws` passive-demo draws each. Two predeclared tiers, up to n_max each:
      adversarial_strict: every macro-scope program that fits the passive demos gives the same WRONG answer;
      adversarial_weak: some fitting macro-scope program gives a wrong (non-error) answer, but not strict.
    Returns (tasks, generation_steps)."""
    rng = random.Random(f"w31b-adv:{split_seed}:{held_out}")
    tools = [dict(t) for t in G.G_P] + list(library)
    body = [t for t in G.G_P if t["op"] not in G.ADAPTER_OPS]
    plan = [(a, b) for a in body for b in body for _ in range(draws)]
    rng.shuffle(plan)
    out, steps, got = [], 0, {"adversarial_strict": 0, "adversarial_weak": 0}
    for a_op, b_op in plan:
        if min(got.values()) >= n_max:
            break
        prog = [dict(t) for t in G.LEAF[held_out]] + [dict(a_op), dict(b_op)]
        t = _task(held_out, prog, rng, 3, core=[s["op"] for s in prog[1:]], category="adversarial")
        if t is None:
            continue
        xs = [x for x, _ in t["public"]]
        targets = [V.key(y) for _, y in t["public"]]
        answers = set()
        for a in tools:
            for b in [None] + tools:
                chain = [a] if b is None else [a, b]
                ok = True
                for x, tk in zip(xs, targets):
                    o, s = V.run(chain, x)
                    steps += s + 1
                    if o == V.ERROR or V.key(o) != tk:
                        ok = False
                        break
                if ok:
                    o, s = V.run(chain, t["query"])
                    steps += s + 1
                    answers.add(V.ERROR if o == V.ERROR else V.key(o))
        wrong = answers - {V.key(t["answer"]), V.ERROR}
        tier = ("adversarial_strict" if len(answers) == 1 and wrong else "adversarial_weak" if wrong else None)
        if tier and got[tier] < n_max:
            got[tier] += 1
            out.append(dict(t, category=tier))
    return out, steps
