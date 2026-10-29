"""MI-3 acceptance check (NOT LOCKED; new versioned module - ba_accept, t7_repair, mi_learner, mi2_learner, the pinned checkers
v1-v5 and the evaluator are unchanged).

Diagnosed gap (exposed MI-2 episode 26801, ADDC): the learned register update (acc + 3 on (0, RELEASE)) was CORRECT. The
training stream (120 events) happened never to contain the declared kind ADD, so the learner's alphabet - and therefore every
probe of the old check (coverage_cex + ba_accept.bounded_cex, whose scope states "only kinds observed at build time") - lacked
it. On the held-out stream ADD occurs; the reference answers q:invalid, the accepted machine emits its unknown-symbol signal, and
31 of 641 held-out rows differ. Mechanism: the hypothesis is not total over the declared input interface, and the old check
certifies behaviour only on the observed sub-alphabet. Any arm that can fit the observed registers accepts it (arms that could
not express acc + 3 failed register search instead, which is why A0 had no silent error).

Repair (general, not syntactic): an INTERFACE-CLOSURE tier runs before the old tiers. The declared event-kind interface of the
source (Episode3.interface: the kinds the stream can carry - a schema, no outputs or behaviour) is compared with the hypothesis
alphabet; for every declared kind the hypothesis never observed, the kind is probed through the counted oracle after every
hypothesis mode's access path and after each register-loading prefix (ba_accept.loaded_prefixes), so a missing kind is caught
whatever the mode or register contents. A probe whose oracle rows differ from the hypothesis is a counterexample of class
"interface_gap". The learner cannot extend its alphabet, so in full_space3 an interface_gap is a REJECTION (outcome
"interface_gap", no answer) rather than a relearning round. The old tiers then run unchanged. Same check for every MI-3 arm.

  new_check(L, interface, seed)  -> (counterexamples, record)   the frozen MI-3 acceptance check (interface tier + old tiers)
  old_check(L, seed)             -> (counterexamples, record)   the MI-2 check (coverage_cex, then bounded_cex), for comparison
  full_space3(ep, dom, seed, ...)                               mi2_learner.full_space with new_check as the acceptance check"""
from __future__ import annotations

import signal
import time

from nexus import ba_accept as BA
from nexus import mi_ocean as M
from nexus import mi2_learner as M2
from nexus import t7_repair as TR
from nexus import u5_statesplit as SP


class Episode3(M.Episode):
    """mi_ocean episode plus its declared input interface (event kinds the source can emit). Learners and acceptance checks
    read only `interface`, never `machine` (the evaluator's reference)."""

    def __init__(self, seed, family, **kw):
        super().__init__(seed, family, **kw)
        self.interface = sorted(self.machine["base"])


def interface_cex(L, interface):
    m, alpha = L.machine, list(L.alpha)
    missing = [k for k in interface if k not in alpha]
    if not missing:
        return [], dict(missing=[], queries=0)
    pre = {(): None}
    for q, acc in sorted(L.hyp["access"].items()):
        pre[tuple(acc)] = None
    for w in BA.loaded_prefixes(m, alpha).values():
        pre[tuple(w)] = None
    out, n = [], 0
    for k in missing:
        for p in pre:
            evs = L.make_events(p + (k,), fresh_values=True)
            rows, bad = BA._mismatch(L, evs)
            n += 1
            if bad:
                out.append((evs, rows, p + (k,)))
                break                                                # one witness per missing kind suffices
    return out, dict(missing=missing, queries=n, prefixes=len(pre))


def old_check(L, seed=0):
    cex = TR.coverage_cex(L)
    rec = dict(tier="coverage" if cex else None)
    if not cex:
        cex, scope = BA.bounded_cex(L, seed=seed)
        rec.update(tier="bounded" if cex else None, scope_queries=scope.get("queries"))
    return cex, rec


def new_check(L, interface, seed=0):
    cex, rec = interface_cex(L, interface)
    if cex:
        return cex, dict(tier="interface_gap", interface=rec)
    cex, r2 = old_check(L, seed)
    return cex, dict(r2, interface=rec)


def full_space3(ep, domain_fn, seed, max_s=60.0, rounds=6, cap_s=None):
    """mi2_learner.full_space with new_check as the acceptance check (code path otherwise identical)."""
    t1 = time.process_time()
    q0 = ep.n_queries
    L = M2.LearnerMI2(ep.train, ep.y_train, ep.query, seed=seed, max_s=max_s)
    L.domain_fn = domain_fn
    stats = dict(queries=0)
    if cap_s:
        signal.signal(signal.SIGPROF, M2._raise)
        signal.setitimer(signal.ITIMER_PROF, cap_s)
    ok, m, scope = False, None, None
    try:
        if L.key is None or L.ctrl is None:
            outcome = "no_fields"
        else:
            m = L.learn()
            outcome = None
            for r in range(rounds):
                if m is None or time.process_time() - t1 > 4 * max_s:
                    break
                cex, scope = new_check(L, ep.interface, seed=seed + r)
                if not cex:
                    ok = True
                    break
                if scope["tier"] == "interface_gap":
                    outcome = "interface_gap"
                    break
                relabel = False
                for evs, rows, word in cex:
                    if L._run_labels(L.hyp, word) != tuple(SP._labels(x) for x in rows):
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
            outcome = outcome or ("accepted" if ok and m is not None else
                                  ("register_search_failed" if m is None else "acceptance_failed"))
    except M2.EpisodeTimeout:
        ok, m, outcome, scope = False, None, "cap_timeout", None
    finally:
        if cap_s:
            signal.setitimer(signal.ITIMER_PROF, 0)
    log = getattr(L, "mi2_log", [])
    stats.update(outcome=outcome, cpu_s=round(time.process_time() - t1, 3), queries=ep.n_queries - q0,
                 domain_sizes=[s.get("size") for s in getattr(L, "mi_stats", [])][:6], searches=log,
                 explained=(log.count("solved") / len(log)) if log else 0.0)
    if not ok or m is None:
        return None, stats
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, scope=scope, learner="full_space3"), stats
