"""ba end-to-end platform (NOT LOCKED): the u5 platform source with the t7 patches and the oc patches (unchanged) PLUS the
pre-registered FRESH unseen fault class X6, applied as exact, asserted text patches (no earlier platform file is edited).
X6 (declared in the ba pre-registration before any dev run; never executed on dev or val): UNDECLARED VALUE-FIELD RENAME in
the lifecycle stream - from tick 9 the producer emits each lifecycle event's numeric value under a new field name
(<val>_amount) and stops sending the old field; semantics unchanged; nothing is declared.
Split 'ba_test': fault = ('X6', 'X3', 'X6', 'X5')[(seed // 4) % 4]; domain = DOMAINS4[seed % 4] (4 per domain; X6 on 8 = 2 per
domain; X3 = the 13143 energy failure class; X5 = the oc unseen class, now known).
Arms: NexusArmStrong (f45da4e priority-A behaviour), NexusArmBounded (= Strong, but every (re)learned lifecycle class must pass
the bounded acceptance check ba_accept - coverage, then exhaustive + structural tiers, <= 6 relearning rounds - or the
learner ABSTAINS (no machine is returned; c84fc76's certified path returned the last machine even when a counterexample
remained); optional growth rule (hypothesis-space growth from H0 under a policy) when the Step 4 rule promotes one."""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from nexus import oc_platform as OCP
from nexus import t7_platform as T7
from nexus import u5_platform as _U5

BA_PATCHES = [
    ('    if split == "oc_test":\n',
     '    if split == "ba_test":\n        return ("X6", "X3", "X6", "X5")[(seed // 4) % 4]\n    if split == "oc_test":\n'),
    ('                e = {self.schema.key: k, self.schema.kind: kn, self.schema.val: v, self.schema.seq: t * 1000 + len(evs)}\n',
     '                vf = self.schema.val + "_amount" if (late and self.fault == "X6") else self.schema.val\n'
     '                e = {self.schema.key: k, self.schema.kind: kn, vf: v, self.schema.seq: t * 1000 + len(evs)}\n'),
    ('        return SF.reference(self.sfam, events, self.schema, self.x3)\n',
     '        if getattr(self, "fault", None) == "X6":\n'
     '            vf = self.schema.val\n'
     '            events = [dict({a: b for a, b in e.items() if a != vf + "_amount"}, **{vf: e[vf + "_amount"]}) if vf + "_amount" in e else e\n'
     '                      for e in events]\n'
     '        return SF.reference(self.sfam, events, self.schema, self.x3)\n'),
]


def _load():
    s = Path(_U5.__file__).read_text()
    for a, b in T7.PATCHES + OCP.OC_PATCHES + BA_PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"ba platform patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._ba_platform_core", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _U5.__file__
    exec(compile(s, _U5.__file__ + "[ba-patched]", "exec"), mod.__dict__)
    return mod


PL = _load()
Project, NexusArm, FixedArm, run_project = PL.Project, PL.NexusArm, PL.FixedArm, PL.run_project


class NexusArmStrong(PL.NexusArm):
    """f45da4e NEXUS_Tournament_Winner behaviour on this platform copy (same three components as t7_platform)."""
    boost = True
    _learn_b = T7.NexusArmStrong._learn_b
    _probe = T7.NexusArmStrong._probe
    _probe_sample = T7.NexusArmStrong._probe_sample


class _Ep:
    """A build / repair learning task as an episode for ba_learn (no scoring: the platform evaluates independently)."""

    def __init__(self, events, outputs, query):
        self.train, self.y_train, self._q, self.n_queries, self.contract, self.seed = events, outputs, query, 0, None, 0

    def query(self, evs):
        self.n_queries += 1
        return self._q(evs)


def learn_class_bounded(events, outputs, query, seed=0, max_s=60.0, rounds=6, growth=None, cfg=None):
    """Lifecycle learner with the bounded acceptance check. growth=None: Learner2 over the full space (the priority-A learner);
    growth=policy: hypothesis-space growth from oc_learner.H0 under that policy (ba_learn.attempt per step, <= 6 steps); if no
    machine is accepted, the full-space learner runs as the fallback (decided on dev, 13143 replay; disclosed in the report).
    Returns the accepted machine with its TESTED_WITHIN_STATED_LIMITS scope record, or None (abstain)."""
    from nexus import ba_accept as BA
    from nexus import ba_learn as BL
    from nexus import oc_learner as OL
    from nexus import t7_repair as TR
    from nexus import u5_statesplit as SP
    t0 = time.process_time()
    if growth is not None:                                       # first line: the promoted growth rule from H0
        ep = _Ep(events, outputs, query)
        H, cache, rnd = dict(OL.H0), {}, __import__("random").Random(seed)
        ok = L = scope = None
        for _ in range(6):
            ok, L, cex, scope = BL.attempt(ep, H, "bounded", None, cache, seed, cfg=cfg)
            if ok or time.process_time() - t0 > 4 * max_s:
                break
            H, _ = OL.apply(growth(OL.signature(L, cex), H, rnd), H)
        if ok and L is not None and L.machine:
            src, name = SP.class_source(L.machine, witnesses=L.witnesses)
            return dict(source=src, name=name, machine=L.machine, witnesses=L.witnesses, queries=L.n_mq, scope=scope, learner="growth")
        # fallback (integration decision on dev, ba §3): nothing accepted -> the priority-A full-space learner, same check
    t1 = time.process_time()
    L = TR.Learner2(events, outputs, query, seed=seed, max_s=max_s)
    if L.key is None or L.ctrl is None:
        return None
    m = L.learn()
    ok, scope = False, None
    for r in range(rounds):
        if m is None or time.process_time() - t1 > 4 * max_s:
            break
        cex = TR.coverage_cex(L)
        if not cex:
            cex, scope = BA.bounded_cex(L, seed=seed + r, **(cfg or {}))
        if not cex:
            ok = True
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
    if not ok or m is None:
        return None
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, witnesses=L.witnesses, queries=L.n_mq, scope=scope, learner="full_space")


class NexusArmBounded(NexusArmStrong):
    """NexusArmStrong + the bounded acceptance check on every (re)learned lifecycle class (+ optional growth rule)."""
    growth = None

    def _learn_b(self, events, outputs, query, mode, seed=0):
        if mode != "statesplit":
            return PL.learn_b(events, outputs, query, mode, seed)
        r = learn_class_bounded(events, outputs, query, seed=seed, growth=self.growth)
        if not r or r["source"] is None:
            return None
        return ("class", dict(source=r["source"], name=r["name"], witnesses=r["witnesses"], n_modes=r["machine"]["n"],
                              n_regs=len(r["machine"]["regs"]), queries=r["queries"], label="TESTED_WITHIN_STATED_LIMITS",
                              scope=r["scope"]))
