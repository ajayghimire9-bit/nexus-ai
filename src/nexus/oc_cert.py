"""oc revision 1 (NOT LOCKED; after the failed oc validation gate; diagnosed on DEV only): EXTENDED CERTIFICATION.
Part 1 / Part 2 showed that coverage agreement certifies wrong machines on ~11-15 % of random mechanisms. After the covered
learner (t7_repair.learn_class_covered) certifies, up to 150 extra membership queries on random LONG words (length 6-16)
with fresh values are spent; any disagreement is a counterexample: it is added and the machine relearned (<= 6 rounds)."""
from __future__ import annotations

import random

from nexus import t7_repair as TR
from nexus import u5_statesplit as SP


def extended_cex(L, n=150, lo=6, hi=16, seed=0):
    rnd = random.Random(seed)
    for _ in range(n):
        word = tuple(rnd.choice(L.alpha) for _ in range(rnd.randint(lo, hi)))
        evs = L.make_events(word, fresh_values=True)
        L.n_mq += 1
        rows = L._query(evs)
        if not all(SP._rows_eq(g, w) for g, w in zip(SP.run_machine(L.machine, evs), rows)):
            return [(evs, rows, word)]
    return []


def learn_class_certified(events, outputs, query, seed=0, max_s=60.0, rounds=6):
    L = TR.Learner2(events, outputs, query, seed=seed, max_s=max_s)
    if L.key is None or L.ctrl is None:
        return None
    m = L.learn()
    cov = dict(rounds=0, cex=0, extended_cex=0)
    for _ in range(rounds):
        if m is None:
            break
        cex = TR.coverage_cex(L)
        if not cex:
            cex = extended_cex(L, seed=seed + cov["rounds"])
            cov["extended_cex"] += len(cex)
        cov["rounds"] += 1
        if not cex:
            break
        cov["cex"] += len(cex)
        relabel = False
        for evs, rows, word in cex:
            if L._run_labels(L.hyp, word) != tuple(SP._labels(r) for r in rows):
                relabel = True
                for i in range(len(word)):
                    if tuple(word[i:]) not in L.E:
                        L.E.append(tuple(word[i:]))
            else:
                L.extra_hist.append((evs, rows))
        hyp = L.learn_control_continue() if relabel else L.hyp
        if L.learn_registers(hyp) is None:
            m = None
            break
        L.machine = m = L._machine(hyp)
    if m is None:
        return None
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, witnesses=L.witnesses, queries=L.n_mq, fields=L.f, coverage=cov)
