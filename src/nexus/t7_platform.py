"""t7 end-to-end platform (NOT LOCKED): the u5 platform loaded as a SEPARATE module copy with exact, asserted patches
(u5_platform.py itself is unchanged and stays the frozen u5 record):
  * a fourth project domain (energy: E formula families + the E.meter lifecycle); domain = DOMAINS4[seed % 4]
  * hook points on NexusArm (_learn_b, _probe, _probe_sample, boost) - defaults reproduce u5 behaviour exactly
  * post-repair heightened monitoring (10 records / 6 keys for 2 ticks after a repair) for arms with boost = True
  * spot-check randomness seeded by project only (paired schedules across arms; u5 seeded it by arm name)
NexusArmStrong = priority A: covered lifecycle relearning + condition-crossing status probes + heightened monitoring."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from nexus import t7_world  # noqa: F401  (registers the energy domain)
from nexus import t7_repair as TR
from nexus import u5_platform as _U5

PATCHES = [
    ('NUMERIC = {d: [f for f in W.FAMILIES if W.domain_of(f) == d and W.FAMILIES[f]["out"] == "num"] for d in DOMAINS}\n',
     'NUMERIC = {d: [f for f in W.FAMILIES if W.domain_of(f) == d and W.FAMILIES[f]["out"] == "num"] for d in DOMAINS4}\n'),
    ('DOMAINS = W.DOMAINS\n', 'DOMAINS = W.DOMAINS\nDOMAINS4 = W.DOMAINS + ("energy",)\n'),
    ('STATEFUL_OF = {"logistics": "L.barrier", "clearing": "C.clearing", "iot": "I.session"}\n',
     'STATEFUL_OF = {"logistics": "L.barrier", "clearing": "C.clearing", "iot": "I.session", "energy": "E.meter"}\n'),
    ('        self.domain = DOMAINS[seed % 3]\n', '        self.domain = DOMAINS4[seed % 4]\n'),
    ('        status, sst = synth_status(envs, [s for s, _ in labs], self.status_s, self.learner["cfg"])\n',
     '        envs, labs = self._probe(P, envs, labs)\n        status, sst = synth_status(envs, [s for s, _ in labs], self.status_s, self.learner["cfg"])\n'),
    ('        b = learn_b(evs, outs, lambda x: P.oracle_B(x), self.b_mode, seed=P.seed)\n',
     '        b = self._learn_b(evs, outs, lambda x: P.oracle_B(x), self.b_mode, seed=P.seed)\n'),
    ('        b = learn_b(archive_events, archive_rows, lambda x: P.oracle_B(x), self.b_mode, seed=len(archive_events))\n',
     '        b = self._learn_b(archive_events, archive_rows, lambda x: P.oracle_B(x), self.b_mode, seed=len(archive_events))\n'),
    ('        n_hold = max(4, len(sample) // 4)\n',
     '        sample, labs = self._probe_sample(P, tick, sample, labs)\n        envs = [{"r": r, "t": reg} for r in sample]\n'
     '        n_hold = max(4, len(sample) // 4)\n'),
    ('    def __init__(self, name, learner, b_mode="statesplit", value_s=40.0, status_s=30.0):\n',
     '    boost = False\n\n    def _learn_b(self, *a, **k):\n        return learn_b(*a, **k)\n\n    def _probe(self, P, envs, labs):\n'
     '        return envs, labs\n\n    def _probe_sample(self, P, tick, sample, labs):\n        return sample, labs\n\n'
     '    def __init__(self, name, learner, b_mode="statesplit", value_s=40.0, status_s=30.0):\n'),
    ('    crash_ok = None\n    repairs = 0\n', '    crash_ok = None\n    repairs = 0\n    boost_until = 0\n'),
    ('    rnd = random.Random(f"ops-{P.seed}-{arm.name}")\n', '    rnd = random.Random(f"ops-{P.seed}")                 # paired spot-check schedule across arms\n'),
    ('            idx = rnd.sample(range(len(tk["A"])), 3)\n',
     '            hot = getattr(arm, "boost", False) and t <= boost_until\n            idx = rnd.sample(range(len(tk["A"])), 10 if hot else 3)\n'),
    ('            for k in rnd.sample(keys, min(2, len(keys))):\n', '            for k in rnd.sample(keys, min(6 if hot else 2, len(keys))):\n'),
    ('                        ledger.append(dict(tick=t, kind="repair_A", version=prog.version))\n',
     '                        ledger.append(dict(tick=t, kind="repair_A", version=prog.version))\n                        boost_until = t + 2\n'),
    ('                            ledger.append(dict(tick=t, kind="repair_B", version=prog.version))\n',
     '                            ledger.append(dict(tick=t, kind="repair_B", version=prog.version))\n                            boost_until = t + 2\n'),
]


def _load():
    s = Path(_U5.__file__).read_text()
    for a, b in PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"t7 platform patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._t7_platform_core", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _U5.__file__
    exec(compile(s, _U5.__file__ + "[t7-patched]", "exec"), mod.__dict__)
    return mod


PL = _load()
Project, NexusArm, FixedArm, run_project, tuplify = PL.Project, PL.NexusArm, PL.FixedArm, PL.run_project, PL.tuplify


def _learn_b_covered(events, outputs, query, mode, seed=0):
    if mode != "statesplit":
        return PL.learn_b(events, outputs, query, mode, seed)
    r = TR.learn_class_covered(events, outputs, query, seed=seed)
    if not r or r["source"] is None:
        return None
    return ("class", dict(source=r["source"], name=r["name"], witnesses=r["witnesses"], n_modes=r["machine"]["n"],
                          n_regs=len(r["machine"]["regs"]), queries=r["queries"], coverage=r["coverage"]))


class NexusArmStrong(PL.NexusArm):
    boost = True

    def _learn_b(self, *a, **k):
        return _learn_b_covered(*a, **k)

    def _probe(self, P, envs, labs):
        hy = TR.crossing_records(envs, [s for s, _ in labs], seed=P.seed)
        if not hy:
            return envs, labs
        by_tick = {}
        for e in hy:
            by_tick.setdefault(int(str(e["r"][P.id_field])[:2]), []).append(e)
        new_e, new_l = [], []
        for t, es in by_tick.items():
            new_e += es
            new_l += P.oracle_A([e["r"] for e in es], t, "build_labels")
        return envs + new_e, labs + new_l

    def _probe_sample(self, P, tick, sample, labs):
        reg = P.ticks[tick]["registry"]
        hy = TR.crossing_records([{"r": r, "t": reg} for r in sample], [s for s, _ in labs], seed=tick)
        if not hy:
            return sample, labs
        rs = [e["r"] for e in hy]
        return rs + list(sample), P.oracle_A(rs, tick, "incident") + list(labs)          # probes first (held-out stays real)
