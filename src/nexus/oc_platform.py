"""oc end-to-end platform (NOT LOCKED): the u5 platform source with the t7 patches (t7_platform.PATCHES, unchanged) PLUS the
pre-registered unseen fault class X5, applied as exact, asserted text patches (u5_platform.py and t7_platform.py are not
edited).
X5 (declared in the oc pre-registration before any dev run; never executed on dev or val): UNDECLARED EVENT-KIND
VOCABULARY MIGRATION - from tick 9 the lifecycle producer emits two of its event kinds under new names (<KIND>_V2) and stops
using the old names; semantics are unchanged; nothing is declared.
Split 'oc_test': fault = ('X5', 'X3', 'X5', 'X4')[(seed // 4) % 4]; domain = DOMAINS4[seed % 4] (4 per domain, X5 on 8)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from nexus import t7_platform as T7
from nexus import u5_platform as _U5

OC_PATCHES = [
    ('    return ("D1", "D2")[seed % 2] if split != "test" else ("X3", "X4")[seed % 2]\n',
     '    if split == "oc_test":\n        return ("X5", "X3", "X5", "X4")[(seed // 4) % 4]\n'
     '    return ("D1", "D2")[seed % 2] if split != "test" else ("X3", "X4")[seed % 2]\n'),
    ('                e = {self.schema.key: k, self.schema.kind: kd, self.schema.val: v, self.schema.seq: t * 1000 + len(evs)}\n',
     '                kn = kd + "_V2" if (late and self.fault == "X5" and kd in SF.FAM_KINDS[self.sfam][1:3]) else kd\n'
     '                e = {self.schema.key: k, self.schema.kind: kn, self.schema.val: v, self.schema.seq: t * 1000 + len(evs)}\n'),
    ('        return SF.reference(self.sfam, events, self.schema, self.x3)\n',
     '        if getattr(self, "fault", None) == "X5":\n'
     '            kf = self.schema.kind\n'
     '            events = [dict(e, **{kf: e[kf][:-3]}) if isinstance(e.get(kf), str) and e[kf].endswith("_V2") else e for e in events]\n'
     '        return SF.reference(self.sfam, events, self.schema, self.x3)\n'),
]


def _load():
    s = Path(_U5.__file__).read_text()
    for a, b in T7.PATCHES + OC_PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"oc platform patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._oc_platform_core", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _U5.__file__
    exec(compile(s, _U5.__file__ + "[oc-patched]", "exec"), mod.__dict__)
    return mod


PL = _load()
Project, NexusArm, FixedArm, run_project = PL.Project, PL.NexusArm, PL.FixedArm, PL.run_project


class NexusArmStrong(PL.NexusArm):
    """f45da4e NEXUS_Tournament_Winner behaviour on this platform copy (same three components as t7_platform)."""
    boost = True
    _learn_b = T7.NexusArmStrong._learn_b
    _probe = T7.NexusArmStrong._probe
    _probe_sample = T7.NexusArmStrong._probe_sample
