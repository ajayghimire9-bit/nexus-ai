"""Growth-rule learning loop with a PLUGGABLE acceptance check (NOT LOCKED).

Identical to oc_learner.attempt / learn_episode (same Learner3, same hypothesis-space growth, same policies, task memory reset
per episode) except that acceptance is a parameter:
  accept="coverage"  the c84fc76 behaviour: coverage_cex agreement = accepted
  accept="bounded"   coverage first (cheap inner loop), then ba_accept.bounded_cex; any counterexample from the bounded
                     check is fed back exactly like a coverage counterexample; acceptance = both pass; the accepted machine is
                     labelled TESTED_WITHIN_STATED_LIMITS with the scope record of the last bounded check
A run that ends without acceptance ABSTAINS (no machine is deployed / claimed)."""
from __future__ import annotations

import random
import time

from nexus import ba_accept as BA
from nexus import oc_learner as OL
from nexus import t7_repair as TR
from nexus import u5_statesplit as SP


def _feed(L, cex):
    relabel = False
    for evs, rows, word in cex:
        if L._run_labels(L.hyp, word) != tuple(SP._labels(r) for r in rows):
            relabel = True
            for i in range(len(word)):
                if tuple(word[i:]) not in L.E:
                    L.E.append(tuple(word[i:]))
        else:
            L.extra_hist.append((evs, rows))
    if relabel:
        L.hyp = L.learn_control_continue()
    if L.learn_registers(L.hyp) is None:
        L.machine = None
        return False
    L.machine = L._machine(L.hyp)
    return True


def attempt(ep, H, accept="coverage", contract=None, cache=None, seed=0, rounds=4, bounded_rounds=4, cfg=None):
    """One learning attempt with hypothesis space H. Returns (accepted, learner, cex, scope)."""
    L = OL.Learner3(ep.train, ep.y_train, ep.query, H, contract=contract, seed=seed, cache=cache)
    if L.key is None or L.ctrl is None:
        return False, L, [], None
    L.hyp = L.learn_control()
    if L.learn_registers(L.hyp) is None:
        L.machine = None
        return False, L, [], None
    L.machine = L._machine(L.hyp)
    scope = None
    for _ in range(rounds + (bounded_rounds if accept == "bounded" else 0)):
        cex = TR.coverage_cex(L)
        if not cex and accept == "bounded":
            cex, scope = BA.bounded_cex(L, seed=seed + len(L.extra_hist), **(cfg or {}))
        if not cex:
            return True, L, [], scope
        if not _feed(L, cex):
            return False, L, cex, scope
    cex = TR.coverage_cex(L)
    if not cex and accept == "bounded":
        cex, scope = BA.bounded_cex(L, seed=seed + 7919, **(cfg or {}))
    return not cex, L, cex, scope


def learn_episode(ep, policy, H0_=None, max_steps=6, accept="coverage", contract=False, seed=0, log=None, cfg=None, keep=False):
    """Grow the hypothesis space under `policy(signature, H, rnd) -> action` until accepted or max_steps.
    Returns dict(accepted, exact, silent, abstain, queries, cpu_s, steps, actions, label, scope) (+ learner if keep)."""
    t0 = time.process_time()
    rnd = random.Random(seed)
    H = dict(H0_ or OL.H0)
    cache, actions = {}, []
    q0 = ep.n_queries
    L, ok, scope = None, False, None
    for step in range(max_steps):
        ok, L, cex, scope = attempt(ep, H, accept, ep.contract if contract else None, cache, seed, cfg=cfg)
        if ok:
            break
        sig = OL.signature(L, cex)
        a = policy(sig, H, rnd)
        actions.append((sig, a))
        if log is not None:
            log.append(dict(seed=ep.seed, step=step, sig=list(sig), action=a))
        H, _ = OL.apply(a, H)
    accepted = bool(L and L.machine) and ok
    sc = dict(exact=False, key_acc=0.0)
    if L is not None and L.machine:
        src, name = SP.class_source(L.machine, witnesses=L.witnesses)
        cls = SP.compile_class(src, name)
        sc = ep.score(lambda evs: SP.run_class(cls, evs))
    label = ("TESTED_WITHIN_STATED_LIMITS" if accept == "bounded" else "COVERAGE_AGREEMENT") if accepted else "ABSTAIN"
    out = dict(accepted=accepted, exact=bool(accepted and sc["exact"]), unaccepted_exact=bool(not accepted and sc["exact"]),
               silent=accepted and not sc["exact"], abstain=not accepted, key_acc=round(sc["key_acc"], 4),
               queries=ep.n_queries - q0, cpu_s=round(time.process_time() - t0, 3), steps=len(actions),
               actions=[a for _, a in actions], H=H, label=label, scope=scope)
    if keep:
        out["learner"] = L
    return out
