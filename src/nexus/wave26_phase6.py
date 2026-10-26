"""Wave 26 Phase 6: learning-to-learn test - Experienced vs Fresh vs compute-matched Placebo.

Statistical unit = an independent random ORDERING of N source worlds (seeds 6001-6005 in confirmation,
741-745 in dev). For each ordering:
  * Experienced: solves the N source worlds in that order with the Phase 4 router + synthesizer, accumulating
    the slot-level schema library (invented mechanisms, verified classes);
  * Fresh: no source experience (empty library);
  * Placebo: the same number of solve calls on NOISE worlds (each public output replaced by another example's
    output, so no consistent mechanism exists); whatever it admits is kept, but no valid structure is learnable.
  Then all three solve the SAME evaluation stream (the sealed Group B + external ARC tasks in confirmation;
  held-out synthetic worlds in dev), each arm continuing to learn online.
Metrics per ordering and arm: total evaluation cost, cost per evaluation world, learning slope (least-squares
slope of per-task cost over the stream position; more negative = gets cheaper faster), solved, false
certificates. Source-phase compute is reported (fully loaded) separately.
"""
from __future__ import annotations

import copy
import random

from nexus.wave24_domains import vkey
from nexus.wave25_factored import run
from nexus.wave26_phase4 import HIDDEN, Library, make_fault_task, solve
from nexus.wave26_phase5 import world_of

N_SOURCE = 10
TASKS_PER_SOURCE = 2


def source_worlds(seed):
    rng = random.Random(f"w26-p6-src:{seed}")
    out = []
    for i in range(N_SOURCE):
        out.append(dict(wid=i, domain=rng.choice(("ints", "records")), fseed=900_000 + i,
                        hidden=HIDDEN[i % len(HIDDEN)], corr=1, drift=False, lag=5))
    return out


def ordering(seed):
    ws = source_worlds(0)                      # the same N source worlds; only their ORDER is random per seed
    random.Random(f"w26-p6-order:{seed}").shuffle(ws)
    return ws


def source_tasks(b, seed):
    w = world_of(b)
    rng = random.Random(f"w26-p6-task:{b['wid']}")
    out = []
    for _ in range(TASKS_PER_SOURCE * 4):
        if len(out) == TASKS_PER_SOURCE:
            break
        t = make_fault_task(w, rng, "dM", hidden_choice=b["hidden"])
        if t is not None:
            out.append(t)
    return w, out


def noise(t, rng):
    """Placebo task: public outputs permuted across examples (no consistent mechanism)."""
    ys = [y for _, y in t["public"]]
    rng.shuffle(ys)
    return dict(t, public=tuple((x, y) for (x, _), y in zip(t["public"], ys)))


def train(arm, seed, *, work_target=None):
    """Experienced: one pass over the ordered source worlds. Placebo: noise versions of the same tasks, cycled
    until its source work reaches `work_target` (Experienced's source work; capped at 4 passes)."""
    lib, work, calls = Library(), 0, 0
    if arm == "fresh":
        return lib, dict(work=0, calls=0, library=[])
    rng = random.Random(f"w26-p6-placebo:{seed}")
    passes = 0
    while True:
        for b in ordering(seed):
            w, tasks = source_tasks(b, seed)
            for i, t in enumerate(tasks):
                if arm == "placebo":
                    t = noise(t, rng)
                r = solve(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib, world_like=w,
                          seed=seed, label=f"src:{arm}:{passes}:{b['wid']}:{i}")
                work += r["work"]
                calls += 1
                if arm == "placebo" and work_target is not None and work >= work_target:
                    return lib, dict(work=work, calls=calls, passes=passes + 1,
                                     library=sorted("/".join(s) for s in lib.schemas))
        passes += 1
        if arm == "experienced" or work_target is None or passes >= 4:
            return lib, dict(work=work, calls=calls, passes=passes, library=sorted("/".join(s) for s in lib.schemas))


def slope(costs):
    n = len(costs)
    if n < 2:
        return 0.0
    mx, my = (n - 1) / 2, sum(costs) / n
    den = sum((i - mx) ** 2 for i in range(n))
    return sum((i - mx) * (c - my) for i, c in enumerate(costs)) / den


def evaluate(lib, stream, seed, arm):
    """stream: list of dict(public, queries, oracle, truths_fn, world_like, group). truths only for grading."""
    rows = []
    for i, t in enumerate(stream):
        try:
            r = solve(list(t["public"]), list(t["queries"]), t["oracle"], lib, world_like=t["world_like"],
                      seed=seed, label=f"eval:{arm}:{i}")
            truths = t["truths"]()
            sol = [a is not None and vkey(a) == vkey(y) for a, y in zip(r["answers"], truths)]
            fc = [a is not None and vkey(a) != vkey(y) for a, y in zip(r["answers"], truths)]
            rows.append(dict(i=i, group=t["group"], route=r["route"], solved=all(sol), false_certificates=sum(fc),
                             work=r["work"], work_by=r["work_by"]))
        except Exception as exc:                       # type only (RULE 1 for sealed tasks)
            rows.append(dict(i=i, group=t["group"], route="error", error=type(exc).__name__, solved=False,
                             false_certificates=0, work=0))
    return rows


def run_ordering(seed, stream_factory, *, fresh_cache=None):
    """fresh_cache (dict): Fresh has no source experience, so its evaluation does not depend on the ordering; it
    is evaluated once with the fixed seed 0 and reused for every ordering (declared)."""
    out = dict(seed=seed, arms={})
    target = None
    for arm in ("experienced", "fresh", "placebo"):
        if arm == "fresh" and fresh_cache is not None and "fresh" in fresh_cache:
            out["arms"]["fresh"] = fresh_cache["fresh"]
            continue
        lib, src = train(arm, seed, work_target=target)
        if arm == "experienced":
            target = src["work"]
        rows = evaluate(lib, stream_factory(), 0 if arm == "fresh" else seed, arm)
        costs = [r["work"] for r in rows]
        out["arms"][arm] = dict(source=src, rows=rows, eval_cost=sum(costs), slope=slope(costs),
                                solved=sum(r["solved"] for r in rows),
                                false_certificates=sum(r["false_certificates"] for r in rows),
                                errors=sum(r["route"] == "error" for r in rows))
        if arm == "fresh" and fresh_cache is not None:
            fresh_cache["fresh"] = out["arms"]["fresh"]
    return out


def dev_stream_factory(dev_seed):
    """Held-out synthetic evaluation worlds (dev only): hidden mechanisms in fresh field-name worlds."""
    def make():
        rng = random.Random(f"w26-p6-devstream:{dev_seed}")
        stream = []
        for j in range(8):
            b = dict(wid=100 + j, domain=rng.choice(("ints", "records")), fseed=800_000 + dev_seed * 100 + j,
                     hidden=rng.choice(HIDDEN), corr=1, drift=False, lag=5)
            w = world_of(b)
            for _ in range(4):
                t = make_fault_task(w, rng, "dM", hidden_choice=b["hidden"])
                if t is not None:
                    stream.append(dict(public=t["public"], queries=[t["query"]],
                                       oracle=lambda x, c=t["teacher"]: run(c, x),
                                       truths=lambda t=t: [t["answer"]], world_like=w, group=f"w{j}"))
                    break
        return stream
    return make


TASKS_PER_SEALED_SEED = 2      # owner (2026-10-26): reduced subset, first 2 tasks by index per sealed seed


def sealed_stream_factory(splits):
    """Sealed Group B + external ARC through the token-gated loader (harness only); truths via oracle_fn."""
    from nexus.sealed_vault_loader import load_split
    cache = {}

    def make():
        if "tasks" not in cache:
            tasks = []
            for split, seeds in splits:
                for s in seeds:
                    for idx, t in enumerate(load_split(split, s)[:TASKS_PER_SEALED_SEED]):
                        tasks.append((split, s, idx, t))
            cache["tasks"] = tasks
        stream = []
        for split, s, idx, t in cache["tasks"]:
            public = [tuple(p) if not isinstance(p, dict) else (p.get("input"), p.get("output")) for p in t.train_examples]
            queries = list(t.query_inputs)
            stream.append(dict(public=public, queries=queries, oracle=t.oracle_fn,
                               truths=lambda t=t, q=queries: [t.oracle_fn(x) for x in q],
                               world_like=dict(name="sealed", fields=(), sample=lambda r, n=None: None),
                               group=split))
        return stream
    return make
