"""Part 3 - distinguishing experiments as a transferable meta-skill (NOT LOCKED).

State invention by continuation splitting is active experiment design: after a hypothesis is formed, NEXUS must choose
continuations that expose hidden state. Structural continuation CLASSES (name-free; instantiated from the hypothesis):
  loop_then_probe   reach mode q, repeat one of q's self-loop kinds 1-3 times, then a kind, then an emitting suffix
  suspend_resume    leave q by a and come back by b (q -a-> q' -b-> q), then a kind
  repeat_twice      the same kind twice from q
  reverse_two       two kinds that are both valid from q, in the reverse of their usual order
  gap_repeat        kind, another kind, the first kind again
  boundary_flush    a long run (5) of a self-loop kind, then an emitting kind
  random_word       generic L*-style random word of length 2-10 (the generic baseline)
Selectors: meta (class weights learned on source episodes: counterexamples found per query; task memory reset - no
machine, program or example is carried), generic (random_word only), info_gain (memoryless: among candidate words from all
classes pick one on which the version-space candidates disagree most), random_class (uniform over classes).
Measure: membership queries until the hypothesis is EXACT on the held-out stream (scored offline after every round)."""
from __future__ import annotations

import random
import time

from nexus import oc_learner as OL
from nexus import u5_statesplit as SP

CLASSES = ("loop_then_probe", "suspend_resume", "repeat_twice", "reverse_two", "gap_repeat", "boundary_flush", "random_word")


def _emit_kinds(hyp, alpha):
    return [a for a in alpha if any(hyp["lam"].get((q, a)) not in ((), ("q:invalid",), None) for q in range(hyp["n"]))]


def make_word(cls, L, rnd):
    hyp, alpha = L.hyp, L.alpha
    q = rnd.randrange(hyp["n"])
    acc = tuple(hyp["access"].get(q, ()))
    valid = [a for a in alpha if hyp["lam"].get((q, a)) != ("q:invalid",)]
    loops = [a for a in valid if hyp["delta"].get((q, a)) == q]
    emit = _emit_kinds(hyp, alpha) or alpha
    tail = (rnd.choice(emit),)
    if cls == "loop_then_probe" and loops:
        return acc + (rnd.choice(loops),) * rnd.randint(1, 3) + (rnd.choice(alpha),) + tail
    if cls == "suspend_resume":
        pairs = [(a, b) for a in valid for b in alpha if hyp["delta"].get((q, a), q) != q and hyp["delta"].get((hyp["delta"][(q, a)], b)) == q]
        if pairs:
            a, b = rnd.choice(pairs)
            return acc + (a, b, rnd.choice(alpha)) + tail
    if cls == "repeat_twice" and valid:
        a = rnd.choice(valid)
        return acc + (a, a) + tail
    if cls == "reverse_two" and len(valid) >= 2:
        a, b = rnd.sample(valid, 2)
        return acc + (b, a) + tail
    if cls == "gap_repeat" and valid:
        a, b = rnd.choice(valid), rnd.choice(alpha)
        return acc + (a, b, a) + tail
    if cls == "boundary_flush" and loops:
        return acc + (rnd.choice(loops),) * 5 + tail
    return tuple(rnd.choice(alpha) for _ in range(rnd.randint(2, 10)))


def _disagree(cands, evs):
    outs = [SP.run_machine(m, evs) for m in cands]
    return sum(not all(SP._rows_eq(a, b) for a, b in zip(outs[0], o)) for o in outs[1:])


def candidates(L, k=8):
    """Version-space candidates: the current machine + single-update variants consistent with all evidence."""
    hist = L.histories() + L.extra_hist
    cands = [L.machine]
    for i, rg in enumerate(L.machine["regs"]):
        for t in list(rg["upd"]) + [t for t in L.hyp["delta"] if t not in rg["upd"]][:6]:
            for g in L._domain(t)[:10]:
                if rg["upd"].get(t) == g:
                    continue
                m2 = dict(L.machine, regs=[dict(r, upd=dict(r["upd"])) for r in L.machine["regs"]])
                m2["regs"][i]["upd"][t] = g
                if all(SP._rows_eq(a, b) for (evs, outs) in hist for a, b in zip(SP.run_machine(m2, evs), outs)):
                    cands.append(m2)
                    if len(cands) >= k:
                        return cands
    return cands


def find_cex(L, selector, weights, rnd, budget=30):
    """Query continuations chosen by the selector until one disagrees with the hypothesis (or the budget is spent)."""
    cands = candidates(L) if selector == "info_gain" else None
    for _ in range(budget):
        if selector == "generic":
            word = make_word("random_word", L, rnd)
        elif selector == "random_class":
            word = make_word(rnd.choice(CLASSES[:-1]), L, rnd)
        elif selector == "meta":
            cls = rnd.choices(list(weights), weights=list(weights.values()))[0]
            word = make_word(cls, L, rnd)
        else:                                                       # info_gain over version-space candidates
            best, bw = -1, None
            for _ in range(12):
                w = make_word(rnd.choice(CLASSES), L, rnd)
                evs = L.make_events(w, fresh_values=True)
                d = _disagree(cands, evs) if len(cands) > 1 else 0
                if d > best:
                    best, bw = d, (w, evs)
            word = bw[0]
        evs = L.make_events(word, fresh_values=True)
        L.n_mq += 1
        rows = L._query(evs)
        if not all(SP._rows_eq(g, w) for g, w in zip(SP.run_machine(L.machine, evs), rows)):
            return (evs, rows, word)
    return None


def episode(ep, selector, weights=None, H=None, rounds=8, budget=30, seed=0, log_classes=None, short_suffixes=False):
    """Learn with experiment-driven counterexample search; returns queries-to-correct and the learning curve."""
    t0 = time.process_time()
    rnd = random.Random(seed)
    H = H or dict(max_regs=2, depth=5, merge=True, max_states=8)
    L = OL.Learner3(ep.train, ep.y_train, ep.query, H, seed=seed)
    q0 = ep.n_queries
    curve = []
    if L.key is None or L.ctrl is None:
        return dict(correct=False, q_to_correct=None, curve=curve, cpu_s=0.0, queries=0)
    L.hyp = L.learn_control()
    if L.learn_registers(L.hyp) is None:
        return dict(correct=False, q_to_correct=None, curve=curve, cpu_s=round(time.process_time() - t0, 3), queries=ep.n_queries - q0)
    L.machine = L._machine(L.hyp)
    qtc = None
    for _ in range(rounds):
        src, name = SP.class_source(L.machine)
        sc = ep.score(lambda evs: SP.run_class(SP.compile_class(src, name), evs))
        curve.append((ep.n_queries - q0, sc["exact"]))
        if sc["exact"] and qtc is None:
            qtc = ep.n_queries - q0
        c = find_cex(L, selector, weights, rnd, budget)
        if c is None:
            break
        evs, rows, word = c
        if L._run_labels(L.hyp, word) != tuple(SP._labels(r) for r in rows):
            for i in range(len(word)):
                if tuple(word[i:]) not in L.E and (not short_suffixes or len(word) - i <= 3):
                    L.E.append(tuple(word[i:]))
            L.hyp = L.learn_control_continue()
        else:
            L.extra_hist.append((evs, rows))
        if L.learn_registers(L.hyp) is None:
            break
        L.machine = L._machine(L.hyp)
    if qtc is None and L.machine:
        src, name = SP.class_source(L.machine)
        sc = ep.score(lambda evs: SP.run_class(SP.compile_class(src, name), evs))
        curve.append((ep.n_queries - q0, sc["exact"]))
        if sc["exact"]:
            qtc = ep.n_queries - q0
    upd = [repr(g) for r in (L.machine or {}).get("regs", []) for g in r["upd"].values()] if L.machine else []
    return dict(correct=qtc is not None, q_to_correct=qtc, curve=curve, cpu_s=round(time.process_time() - t0, 3), queries=ep.n_queries - q0,
                updates=upd)


def learn_weights(eps, seed=0, per_class=6):
    """Meta-training: for each source episode, try each class `per_class` times against the first hypothesis and count
    the counterexamples it finds per query (no machine or program is kept)."""
    from collections import Counter
    hit, tries = Counter(), Counter()
    rnd = random.Random(seed)
    for ep in eps:
        L = OL.Learner3(ep.train, ep.y_train, ep.query, dict(max_regs=2, depth=5, merge=True, max_states=8), seed=seed)
        if L.key is None or L.ctrl is None:
            continue
        L.hyp = L.learn_control()
        if L.learn_registers(L.hyp) is None:
            continue
        L.machine = L._machine(L.hyp)
        for cls in CLASSES:
            for _ in range(per_class):
                w = make_word(cls, L, rnd)
                evs = L.make_events(w, fresh_values=True)
                rows = L._query(evs)
                tries[cls] += 1
                hit[cls] += not all(SP._rows_eq(g, x) for g, x in zip(SP.run_machine(L.machine, evs), rows))
    return {c: (hit[c] + 0.5) / (tries[c] + 1) for c in CLASSES}
