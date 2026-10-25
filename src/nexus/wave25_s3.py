"""Wave 25 spike S3: answer-directed factored probing (dev seeds only).

Hypotheses H = every program of the certificate's minimal size consistent with the observations (exact
enumeration, charged), each h = (C = role sequence, B = slot bindings); uniform weight per program.
All arms share: the S1-Auto certifier (learned, admitted contracts), the oracle cost, the probe budget and
the stop rule (stop as soon as the certificate is UNIQUE, i.e. |Y^_q| = 1, whatever (C, B) ambiguity is
left). They differ only in how the next probe is chosen:

  s3              union(standard perturbations, factored disagreement edits), objective I(Y_q ; Y_x | H),
                  ties broken by H(Y_x)                               (answer-directed, no staging)
  flat_eig        standard perturbations, objective I(H ; Y_x) = H(Y_x)  (flat hypothesis EIG)
  flat_eig_union  union candidates, I(H ; Y_x)                         (ablation: generator vs objective)
  b_first         union candidates, I(B ; Y_x) while H(B) > 0, then I(C ; Y_x) (hard-coded staging)
  v4              propose_refinement over class representatives (v4 designed probes)
  random          samples from the world's input distribution
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, candidate_probes, meter, propose_refinement
from nexus.wave25_contracts import certify_with
from nexus.wave25_factored import ORACLE_COST, PROBE_BUDGET, Order, Pred, run, task_grammar

S3_ARMS = ("s3", "flat_eig", "flat_eig_union", "b_first", "v4", "random")
CAND_CAP = 300
_RAISE = ("__raise__",)


def _apply(mech, x, m):
    m.charge("hypothesis_work_units", 1)
    try:
        return mech(x)
    except Exception:
        return _RAISE


def enumerate_H(public, mechs, size, m):
    """All chains of length `size` (1 or 2) fitting every public pair; grouped by first-step outputs."""
    xs = [x for x, _ in public]
    ys = [vkey(y) for _, y in public]
    if size == 1:
        out = []
        for a in mechs:
            if all(vkey(_apply(a, x, m)) == y for x, y in zip(xs, ys)):
                out.append((a,))
        return out
    groups = defaultdict(list)
    for a in mechs:
        vals = tuple(_apply(a, x, m) for x in xs)
        if any(v is _RAISE or not isinstance(v, list) for v in vals):
            continue
        groups[tuple(vkey(v) for v in vals)].append((a, vals))
    out = []
    for key, members in groups.items():
        vals = members[0][1]
        for b in mechs:
            if all(vkey(_apply(b, v, m)) == y for v, y in zip(vals, ys)):
                out.extend((a, b) for a, _ in members)
    return out


def outputs(H, x, m):
    """h(x) for every h, sharing first-step results."""
    first = {}
    res = []
    for h in H:
        a = h[0]
        if a not in first:
            first[a] = _apply(a, x, m)
        v = first[a]
        if len(h) == 2:
            if v is _RAISE:
                res.append(_RAISE)
                continue
            res.append(_apply(h[1], v, m))
        else:
            res.append(v)
    return [vkey(o) for o in res]


def _H(counts):
    n = sum(counts.values())
    return -sum(c / n * math.log2(c / n) for c in counts.values() if c) if n else 0.0


def cond_info(target, ys):
    """I(T ; Y) for uniform weights: H(T) - sum_y P(y) H(T | y)."""
    by = defaultdict(Counter)
    for t, y in zip(target, ys):
        by[y][t] += 1
    n = len(ys)
    return _H(Counter(target)) - sum(sum(c.values()) / n * _H(c) for c in by.values())


def factors(h):
    return tuple(m.role for m in h), tuple(m.slots for m in h)


def _paths_of_slot(slot):
    out = set()
    for v in (slot if isinstance(slot, tuple) else (slot,)):
        if isinstance(v, (Pred, Order)) and v.path not in ("#",):
            out.add(v.path)
    return out


def _thresholds(h):
    return {(s.path, s.val) for m in h for s in m.slots if isinstance(s, Pred)}


def factored_candidates(H, yq, public, query, rng, m, *, max_pairs=6, labels=False):
    """Disagreement edits from competing answer clusters H_y1 vs H_y2 (binding and composition)."""
    clusters = defaultdict(list)
    for h, y in zip(H, yq):
        clusters[y].append(h)
    keys = sorted(clusters, key=repr)
    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = rng.choice(clusters[keys[i]]), rng.choice(clusters[keys[j]])
            pairs.append((a, b))
    rng.shuffle(pairs)
    pairs = pairs[:max_pairs]
    bases = [x for x, _ in public] + [query]
    out = []
    for h1, h2 in pairs:
        m.charge("probe_design_work_units", 1)
        f1 = set().union(*(_paths_of_slot(s.slots) for s in h1))
        f2 = set().union(*(_paths_of_slot(s.slots) for s in h2))
        fields = (f1 | f2) or {"."}
        th = _thresholds(h1) | _thresholds(h2)
        comp_differs = factors(h1)[0] != factors(h2)[0] or \
            {s.slots[0] for s in h1 if s.role == "S"} != {s.slots[0] for s in h2 if s.role == "S"}
        for b in bases:
            if not isinstance(b, list) or not b:
                continue
            rec = isinstance(b[0], dict)
            # binding-disagreement edits: decorrelate competing fields by swapping one field's values between
            # two items (relative rank inverted, the other field kept), toggling booleans, boundary thresholds
            if rec:
                for f in sorted(fields):
                    if f == ".":
                        continue
                    for i in range(len(b)):
                        for j in range(i + 1, len(b)):
                            x = [dict(r) for r in b]
                            x[i][f], x[j][f] = x[j][f], x[i][f]
                            out.append(("field_swap", x))
                        if isinstance(b[i][f], bool):
                            x = [dict(r) for r in b]
                            x[i][f] = not x[i][f]
                            out.append(("bool_toggle", x))
            for path, val in sorted(th, key=repr):
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue
                for i in range(len(b)):
                    for v in (val - 1, val, val + 1):
                        x = [dict(r) if rec else r for r in b]
                        if rec:
                            x[i][path] = v
                        else:
                            x[i] = v
                        out.append(("threshold_boundary", x))
            # composition-disagreement edits: boundary perturbations around k
            if comp_differs:
                for i in range(len(b)):
                    out.append(("drop_item", [it for j, it in enumerate(b) if j != i]))
                    out.append(("move_front", [b[i]] + [it for j, it in enumerate(b) if j != i]))
                    dup = dict(b[i]) if rec else b[i]
                    if rec:
                        for f in sorted(fields):
                            if f != "." and isinstance(dup.get(f), bool):
                                dup[f] = not dup[f]
                    out.append(("dup_toggle", list(b) + [dup]))
    return out if labels else [x for _, x in out]


def _dedup(cands, seen):
    out, ks = [], set(seen)
    for x in cands:
        k = vkey(x)
        if k not in ks:
            ks.add(k)
            out.append(x)
    return out


def choose_probe(arm, H, public, query, world, rng, m, reps):
    seen = {vkey(x) for x, _ in public} | {vkey(query)}
    if arm == "random":
        for _ in range(10):
            x = world["sample"](rng)
            if vkey(x) not in seen:
                return x, "random"
        return None, "none"
    if arm == "v4":
        hyps = [(tuple(t.name for t in p), None, p) for p in reps]
        plan = propose_refinement(hyps, dict(public=public, query=query), dict(tools=[]), "disambiguate",
                                  10**9, m=m)
        return (plan.distinguishing_test[1], "v4") if plan.distinguishing_test else (None, "none")
    yq = outputs(H, query, m)
    bases = [x for x, _ in public] + [query]
    std = [x for _, x, _ in candidate_probes(bases, [(None, None, p) for p in reps], query)]
    if arm == "flat_eig":
        cands = std
    else:
        cands = factored_candidates(H, yq, public, query, rng, m) + std
    cands = _dedup(cands, seen)[:CAND_CAP]
    Bs = [factors(h)[1] for h in H]
    Cs = [factors(h)[0] for h in H]
    stage = None
    if arm == "b_first":
        stage = "B" if _H(Counter(Bs)) > 1e-12 else "C"
    best, best_key = None, (0.0, 0.0)
    # the largest value each objective can reach; a candidate attaining it cannot be beaten on the primary
    # objective, so the scan stops there (exact optimum, not a heuristic cut)
    cap = {"s3": _H(Counter(yq)), "flat_eig": math.log2(max(1, len(H))), "flat_eig_union": math.log2(max(1, len(H))),
           "b_first": _H(Counter(Bs if stage == "B" else Cs))}[arm]
    for x in cands:
        ys = outputs(H, x, m)
        flat = _H(Counter(ys))
        if arm == "s3":
            key = (cond_info(yq, ys), flat)
        elif arm in ("flat_eig", "flat_eig_union"):
            key = (flat, 0.0)
        else:
            key = (cond_info(Bs if stage == "B" else Cs, ys), flat)
        if key > best_key:
            best, best_key = x, key
            if key[0] >= cap - 1e-12:
                break
    if best is None and arm == "b_first":
        # staged objective has nothing left to learn; fall back to the answer objective (declared)
        for x in cands:
            ys = outputs(H, x, m)
            key = (cond_info(yq, ys), 0.0)
            if key > best_key:
                best, best_key = x, key
    return (best, arm if stage is None else f"b_first:{stage}") if best is not None else (None, "none")


def _reps(res):
    s = res.searcher
    cls = s.graph.classes.get(tuple(s.targets), {})
    return [prog for rest, (prog, vals) in cls.items() if len(prog) == res.size]


def _entropies(H, query):
    Bs = Counter(factors(h)[1] for h in H)
    Cs = Counter(factors(h)[0] for h in H)
    return _H(Bs), _H(Cs)


def solve_s3(task, world, arm, props, *, seed=0):
    m = meter(10**9)
    public = list(task.public)
    tools = task_grammar(task, world)
    mechs = [t.fn for t in tools]
    rng = random.Random(f"w25-s3:{seed}:{arm}:{vkey(task.query)}")
    probes, labels, trace = 0, [], []
    try:
        res = certify_with(task, world, props, public=public, tools=tools)
        m.charge("certify_work_units", res.work)
        while res.status == AMBIGUOUS and probes < PROBE_BUDGET:
            H = enumerate_H(public, mechs, res.size, m) if res.size in (1, 2) else [tuple(t.fn for t in p) for p in _reps(res)]
            hb, hc = _entropies(H, task.query)
            trace.append(dict(H=len(H), HB=hb, HC=hc))
            reps = _reps(res)
            x, label = choose_probe(arm, H, public, task.query, world, rng, m, reps)
            labels.append(label)
            if x is None:
                break
            probes += 1
            m.charge("oracle_work_units", ORACLE_COST)
            try:
                y = run(task.teacher, x)
            except Exception:
                continue
            public.append((x, y))
            res = certify_with(task, world, props, public=public, tools=tools)
            m.charge("certify_work_units", res.work)
    except WorkExhausted:
        return dict(arm=arm, solved=False, false_certificate=False, status="EXHAUSTED", probes=probes,
                    work=m.total, labels=labels, trace=trace)
    # reporting only (uncharged): residual (C, B) ambiguity among programs fitting all observations
    rm = meter(10**9)
    final_H = enumerate_H(public, mechs, res.size, rm) if res.size in (1, 2) else []
    hb, hc = _entropies(final_H, task.query) if final_H else (0.0, 0.0)
    solved = res.status == UNIQUE and vkey(res.answer) == vkey(task.answer)
    false = res.status == UNIQUE and vkey(res.answer) != vkey(task.answer)
    return dict(arm=arm, solved=solved, false_certificate=false, status=res.status, probes=probes, work=m.total,
                work_by=dict(m.counts), labels=labels, trace=trace, residual_HB=hb, residual_HC=hc,
                final_H=len(final_H))


def run_s3_seed(seed, *, n_val=15, n_s1=30, n_s3=30):
    """One dev seed: learn contracts, cheap Tycho admission, S1-Auto measurement, S3 arms on active tasks of
    both worlds (generator salts disjoint from S1/S2: seed+700 validation, +200 S1, +500 S3)."""
    from nexus.wave25_contracts import default_props, learn_contracts, tycho_admit_contracts
    from nexus.wave25_factored import ints_world, make_tasks, records_world
    lib = learn_contracts()
    src, tgt = ints_world(seed), records_world(seed)
    worlds = {"INT_LIST": src, "RECORDS": tgt}
    val = make_tasks(src, seed + 700, n_val, active=False, max_depth=3) + \
        make_tasks(tgt, seed + 700, n_val, active=False, max_depth=3)
    tycho = tycho_admit_contracts(lib, val, worlds)
    s1, s3 = [], []
    for name, w in worlds.items():
        roles = {"F", "S", "Sort", "Agg"} | ({"Map"} if w["maps"] else set())
        props = default_props(lib, roles)
        for i, t in enumerate(make_tasks(w, seed + 200, n_s1, active=False, max_depth=3)):
            a = certify_with(t, w, None)
            b = certify_with(t, w, props)
            s1.append(dict(world=name, task=i, work_plain=a.work, work_auto=b.work, evals_plain=a.evaluations,
                           evals_auto=b.evaluations, same=a.status == b.status and
                           {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}))
        for i, t in enumerate(make_tasks(w, seed + 500, n_s3, active=True)):
            for arm in S3_ARMS:
                r = solve_s3(t, w, arm, props, seed=seed)
                r.update(world=name, task=i, seed=seed)
                s3.append(r)
            r = solve_s3(t, w, "flat_eig", None, seed=seed)       # no-contract reference for full loading
            r.update(world=name, task=i, seed=seed, arm="flat_eig_plain")
            s3.append(r)
    return dict(seed=seed, contracts=[dict(prop=c.prop, role=c.role, relation=c.relation, status=c.status,
                                           checks=c.checks) for c in lib.contracts],
                role_classes=lib.role_classes, learning_work=dict(lib.work), tycho=tycho,
                props={n: default_props(lib, {"F", "S", "Sort", "Agg"} | ({"Map"} if w["maps"] else set()))
                       for n, w in worlds.items()}, s1=s1, s3=s3)
