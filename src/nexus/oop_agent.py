"""OOP-track build agent NEXUS_Synth (NOT LOCKED). The R1 agent code (r1_agent, unchanged) loaded as a SEPARATE module and
rebound to oop_template, so the Stage 4 proposer, localisation, caps, the R1 check suite, scoped evidence and outcome labels
are unchanged; the 8 removed switches are synthesised holes:
  1. examples from the visible log (ticks 1-8) through the spec monitor (oop_examples); every hole synthesised from
     primitives (oop_synthesizer); all synthesis CPU is charged to the build
  2. a hole that cannot be synthesised -> ABSTAIN_UNSUPPORTED (no template fallback)
  3. the Stage 4 build search over the 10 remaining switches with the synthesised programs fixed; the full R1 suite decides
Check implications naming removed switches are mapped to their holes (oop_template.OLD2HOLE)."""
from __future__ import annotations

import importlib.util
import json
import time
import types
from pathlib import Path

from nexus import oop_examples as X
from nexus import oop_template as OT
from nexus import r1_agent as _R1A
from nexus import r1_checks as RC

_spec = importlib.util.spec_from_file_location("nexus._oop_agent_core", _R1A.__file__)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

CS = types.ModuleType("nexus._oop_checks_shim")
CS.__dict__.update({k: v for k, v in RC.__dict__.items() if not k.startswith("__")})
CS.IMPLICATE = {k: OT.remap(v) for k, v in RC.IMPLICATE.items()}


def _verify(*a, **k):
    res = RC.verify(*a, **k)
    for r in res:
        r["implicate"] = OT.remap(r.get("implicate", []))
    return res


CS.verify = _verify
CS.__file__ = RC.__file__
M.RT, M.A.T, M.A.C = OT, OT, CS
SYNTH_MAX_S = 400.0


def build(arm, ws, profile=None, library=None):
    t0, c0 = time.perf_counter(), M.A._cpu()
    ws = Path(ws)
    spec = json.loads((ws / "docs/spec.json").read_text())
    OT.reset()
    arch = X.read_log(ws / "visible" / "log", spec)
    X.BUILD_ARCH[spec["project"]] = arch
    pids, stats, _ = X.synth_all(spec, arch, max_s=SYNTH_MAX_S)
    synth_cpu = M.A._cpu() - c0
    if not all(pids.values()):
        rec = dict(arm=arm, project=spec["project"], outcome="ABSTAIN_UNSUPPORTED", final_choice=None, history=[],
                   library_used=[], features=[], failed_reuse=0, failed_reuse_cpu_s=0.0, submitted=False,
                   cost=dict(proposals=0, pipeline_runs=0, check_runs=0, final_check_runs=0, final_check_cpu_s=0.0,
                             rejected_and_search_runs=0, rejected_cpu_s=0.0, exec_cpu_s=0.0, agent_cpu_s=round(synth_cpu, 3),
                             total_cpu_s=round(synth_cpu, 3), wall_s=round(time.perf_counter() - t0, 3), synthesis_cpu_s=round(synth_cpu, 3),
                             retrieval_cpu_s=0.0, applicability_cpu_s=0.0),
                   human=dict(clarifications=0, engineering_repairs=0, operational_interventions=0),
                   synthesis=dict(stats=stats, unsolved=[h for h, p in pids.items() if not p]))
        return rec
    RC.LAST.clear()
    rec = M.A.build(arm, ws, profile=profile, library=None)
    rec = M._label(rec, arm)
    c = rec["cost"]
    c["synthesis_cpu_s"] = round(synth_cpu, 3)
    c["agent_cpu_s"] = round(c["agent_cpu_s"] + synth_cpu, 3)
    c["total_cpu_s"] = round(c["total_cpu_s"] + synth_cpu, 3)
    c["wall_s"] = round(time.perf_counter() - t0, 3)
    rec["synthesis"] = dict(stats=stats, programs={h: pids[h] for h in OT.SYNTH_HOLES},
                            code=OT.synth_code(rec["final_choice"]) if rec.get("final_choice") else None)
    return rec


def programs_json():
    """The synthesised programs of the current project (for artifacts / later reuse)."""
    return json.loads(json.dumps({h: dict(v) for h, v in OT.PROG.items()}, default=str))
