"""R2 build agents (NOT LOCKED). The R1 agent code (r1_agent, unchanged) is loaded as a SEPARATE module and rebound to the
R2 template (18 decisions); every arm keeps the Stage 4 proposer, localisation and caps, the R1 suite (r1_checks: Stage 4
checks + replay_conformance + ack_durability + chunk_invariance over grow_obs), scoped evidence and outcome labels.
Fixed_Policy keeps R1's src-majority options and its full-suite check (no repair search)."""
from __future__ import annotations

import importlib.util

from nexus import r1_agent as _R1A
from nexus import r2_template as RT2

_spec = importlib.util.spec_from_file_location("nexus._r2_agent_core", _R1A.__file__)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
M.RT = RT2
M.A.T = RT2


def fixed_policy(ws, profile=None, library=None, counts=None):
    """R2 Fixed_Policy build (baseline development before the freeze): R1's src-majority configuration and full-suite check;
    if a check FAILs, ONE fixed fallback - the decisions that check implicates move to their second most frequent src option
    (when src has one) - and one more full-suite check; abstain if it still fails. No search."""
    rec = _fixed_r1(ws, profile, library)
    if rec["submitted"] or not counts:
        return rec
    import json
    from pathlib import Path
    from nexus import r1_checks as RC
    ws = Path(ws)
    spec = json.loads((ws / "docs/spec.json").read_text())
    failed = rec["history"][0]["failed"]
    ch = dict(rec["final_choice"])
    moved = {}
    for d in RC.IMPLICATE.get(failed, []):
        opts = sorted(counts.get(d, {}).items(), key=lambda x: -x[1])
        nxt = next((o for o, n in opts if o != ch[d]), None)
        if nxt:
            ch[d] = moved[d] = nxt
    if not moved:
        return rec
    runner = RC.Runner(profile)
    c0 = M.A._cpu()
    (ws / "bundle/pipeline.py").write_text(RT2.emit(ch))
    res = RC.verify(ws / "bundle", spec, ws / "visible" / "log", ws / "scratch" / "v1", runner, suite=RC.NEXUS)
    ok = all(r["ok"] for r in res)
    rec["history"].append(dict(k=1, choice=ch, failed=next((r["check"] for r in res if not r["ok"]), None), fallback=moved))
    cost = rec["cost"]
    extra = M.A._cpu() - c0 + runner.cpu_s
    cost.update(proposals=2, pipeline_runs=cost["pipeline_runs"] + runner.runs, check_runs=cost["check_runs"] + runner.runs,
                total_cpu_s=round(cost["total_cpu_s"] + extra, 3), exec_cpu_s=round(cost["exec_cpu_s"] + runner.cpu_s, 3))
    if ok:
        rec.update(final_choice=ch, submitted=True, outcome="COMPLETED_VERIFIED")
        rec = M._label(rec, "Fixed_Policy")
    else:
        (ws / "bundle/pipeline.py").write_text(RT2.emit(rec["final_choice"]))
    return rec


_fixed_r1 = M.fixed_policy
COUNTS = {}


def _fixed(ws, profile=None, library=None):
    return fixed_policy(ws, profile, library, COUNTS)


M.fixed_policy = _fixed
build = M.build
