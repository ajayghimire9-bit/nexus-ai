"""R1 build agents (NOT LOCKED). The Stage 4 agent code (s4_agent, unchanged) is loaded as a SEPARATE module object whose
template / checks references are bound to r1_template / r1_checks, so every arm keeps the Stage 4 proposer, attribution,
localisation and caps over the R1 decision space and the observation-driven replay. Arms:
  Conventional_Checked  STANDARD checks (s4_agent behaviour)
  NEXUS_*               the R1 suite (Stage 4 checks + replay_conformance + ack_durability + chunk_invariance)
  Fixed_Policy          one configuration (src-majority option per decision, proposer order otherwise), the R1 suite once,
                        no repair search: submits unless a property FAILs
Every submitted build gets scoped evidence records (r1_checks.evidence) and an outcome-contract label from them."""
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path

from nexus import r1_checks as RC
from nexus import r1_template as RT
from nexus import s4_agent as _S4A

_spec = importlib.util.spec_from_file_location("nexus._r1_agent_core", _S4A.__file__)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
A.T, A.C = RT, RC


def _label(rec, arm):
    ev = RC.evidence(RC.LAST.get("results", []), RC.LAST.get("conformance", {}), RC.LAST.get("suite", []))
    rec["evidence"] = ev
    rec["evidence_outcome"] = RC.outcome(ev)
    if rec["submitted"]:
        rec["s4_outcome"] = rec["outcome"]
        rec["outcome"] = "COMPLETED_UNVERIFIED" if rec["evidence_outcome"] == "ABSTAIN_UNSUPPORTED" else rec["evidence_outcome"]
        rec["unknown_properties"] = [e["property"] for e in ev if e["result"] == "UNKNOWN"]
    rec["conformance"] = {k: v for k, v in RC.LAST.get("conformance", {}).items() if k != "violations"}
    return rec


def build(arm, ws, profile=None, library=None):
    RC.LAST.clear()
    if arm == "Fixed_Policy":
        return fixed_policy(ws, profile, library)
    rec = A.build(arm, ws, profile=profile, library=library)
    return _label(rec, arm)


def fixed_policy(ws, profile=None, library=None):
    """A strong fixed policy: no search. The library's per-decision options (src majority) where it has one, else the
    proposer's first option; the full R1 suite once; abstain on any FAIL."""
    t0, c0 = time.perf_counter(), A._cpu()
    ws = Path(ws)
    spec = json.loads((ws / "docs/spec.json").read_text())
    full = ws / "visible" / "log"
    bundle, scratch = ws / "bundle", ws / "scratch"
    bundle.mkdir(exist_ok=True); scratch.mkdir(exist_ok=True)
    runner = RC.Runner(profile)
    prior = {p["decision"]: p["option"] for p in (library.retrieve("build") if library else [])}
    prop = A.Proposer(spec["project"], prior)
    choice = prop.choice()
    (bundle / "pipeline.py").write_text(RT.emit(choice))
    (bundle / "config.json").write_text(json.dumps(RT.config_from_spec(spec), indent=1, sort_keys=True))
    res = RC.verify(bundle, spec, full, scratch / "v0", runner, suite=RC.NEXUS)
    ok = all(r["ok"] for r in res)
    shutil.copy(Path(RC.__file__), bundle / "checks.py")
    (bundle / "BUILD.md").write_text(f"# {spec['project']} (Fixed_Policy)\n\nDecisions: {json.dumps(choice, sort_keys=True)}\n"
                                     f"\nChecks: {[(r['check'], r['ok']) for r in res]}\n")
    agent_cpu = A._cpu() - c0
    rec = dict(arm="Fixed_Policy", project=spec["project"], outcome="COMPLETED_VERIFIED" if ok else "ABSTAIN_UNSUPPORTED",
               final_choice=choice, history=[dict(k=0, choice=choice, failed=next((r["check"] for r in res if not r["ok"]), None))],
               library_used=sorted(prior), features=[], failed_reuse=0, failed_reuse_cpu_s=0.0, submitted=ok,
               cost=dict(proposals=1, pipeline_runs=runner.runs, check_runs=runner.runs, final_check_runs=runner.runs,
                         final_check_cpu_s=round(runner.cpu_s, 3), rejected_and_search_runs=0, rejected_cpu_s=0.0,
                         exec_cpu_s=round(runner.cpu_s, 3), agent_cpu_s=round(agent_cpu, 3),
                         total_cpu_s=round(agent_cpu + runner.cpu_s, 3), wall_s=round(time.perf_counter() - t0, 3),
                         retrieval_cpu_s=0.0, applicability_cpu_s=0.0),
               human=dict(clarifications=0, engineering_repairs=0, operational_interventions=0))
    return _label(rec, "Fixed_Policy")
