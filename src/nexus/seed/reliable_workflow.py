"""Teacher-labeled boundary evidence, conversation state, and one reliable workflow."""
from __future__ import annotations

from collections import Counter
import tempfile
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .boundary_evidence import competing_boundary_resolved
from .capability_evidence import EventMeter, digest
from .conversation_quality import score_conversation_quality
from .interrupt_transfer import _assess, _view
from .proposal_trace import proposal_lifecycle
from .scoped_id_staging import trace_costs
from .symbiotic_agent_loop import SymbioticAgentLoop


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit", "py_retry_last",
    "py_cap_inclusive_src", "py_span_ok", "py_floor_ok", "py_reject_floor",
    "py_note_join", "py_threshold_fix", "py_mix_span", "py_doc_lie", "py_two_bugs",
    "py_src_cap_ok", "py_src_title_ok", "py_mark_join", "py_invoice_slug_feature",
}

WORKFLOW_STAGES = (
    "file_discovery", "proposed_edits", "execution", "failure_feedback",
    "revision", "accurate_explanation",
)


def workflow_stages(result: dict) -> dict[str, bool]:
    tools = [row.get("tool_name") for row in result.get("tool_calls") or []]
    attempts = result.get("patch_attempts") or []
    failed_then = any(not row.get("public_passed") for row in attempts[:-1] or [])
    later_ok = bool(attempts) and bool(attempts[-1].get("public_passed"))
    message = str(result.get("summary_message") or "")
    return {
        "file_discovery": "index_repository" in tools,
        "proposed_edits": "propose_candidate_edits" in tools or "local_model_propose" in tools,
        "execution": "evaluate_patch_in_worker" in tools,
        "failure_feedback": failed_then or any(
            (row.get("lifecycle") or {}).get("verdict") == "no_usable_edit"
            for row in result.get("model_trace") or []
        ),
        "revision": (
            "local_model_revise" in tools
            or (failed_then and later_ok)
            or sum(1 for name in tools if name == "local_model_propose") > 1
        ),
        "accurate_explanation": bool(result.get("applied_operator")) and "public" in message.lower(),
    }


def _solve(spec, tmp, meter, scope, live_runtime=None, sources=("ast",), budget=4):
    task = _view(spec, ":" + scope.replace(":", "_")[:24], budget=budget)
    loop = SymbioticAgentLoop(
        Path(tmp) / scope.replace(":", "_"),
        local_runtime=live_runtime,
        allow_acquired_memory=False,
        proposal_sources=sources,
        model_revision_budget=2,
        proposal_interface="symbol",
        model_max_tokens=128,
    )

    def worker(payload, timeout_s=10):
        return meter.call(scope, "worker", spec["id"],
                          lambda data: run_worker_subprocess(data, timeout_s), payload)

    with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
        result = meter.call(scope, "agent", spec["id"], lambda _: loop.solve(task), None)
    if type(result) is not dict:
        return dict(outcome="failed", public_tests_passed=False, final_files=spec["files"],
                    model_trace=[], patch_attempts=[], tool_calls=[])
    return dict(result)


def run_boundary(config, emit, meter):
    budget = int(config.get("coding_budget_steps", 6))
    with tempfile.TemporaryDirectory() as tmp:
        for spec in config["boundary"]:
            if spec["id"] in CLOSED_TASK_IDS:
                raise ValueError("closed_task_id_reused:" + spec["id"])
            scope = "boundary:" + spec["id"]
            result = _solve(spec, tmp, meter, scope, sources=("ast",), budget=budget)
            evidence = competing_boundary_resolved(spec["request"], spec.get("public") or [])
            private = _assess(meter, scope, spec, result.get("final_files") or spec["files"])
            emit(dict(
                kind="capability", area="boundary_evidence", id=spec["id"], category="boundary",
                method="ast", role=spec.get("role"),
                evidence=evidence, accepted=bool(result.get("public_tests_passed")),
                outcome=result.get("outcome_category"),
                public_passed=result.get("public_tests_passed"),
                private=private, used_private_to_accept=False,
                used_candidate_disagreement=False,
                complete_correctness=False,
                final_files=result.get("final_files") or spec["files"],
                **trace_costs(result),
            ))


def run_workflow(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 6))
    with tempfile.TemporaryDirectory() as tmp:
        dev = config["workflow"]["development"]
        fresh = config["workflow"]["fresh"]
        for spec, role, sources in (
            (dev, "development", ("ast", "local_model")),
            (fresh, "fresh", ("ast", "local_model")),
        ):
            if spec["id"] in CLOSED_TASK_IDS:
                raise ValueError("closed_task_id_reused:" + spec["id"])
            scope = f"workflow:{role}:{spec['id']}"
            result = _solve(spec, tmp, meter, scope, live_runtime=live_runtime,
                            sources=sources, budget=budget)
            stages = workflow_stages(result)
            lives = []
            for row in result.get("model_trace") or []:
                life = row.get("lifecycle") or proposal_lifecycle(row, queued=row.get("status") == "proposed")
                lives.append(life)
            private = _assess(meter, scope, spec, result.get("final_files") or spec["files"])
            emit(dict(
                kind="capability", area="repo_workflow", id=spec["id"], category="workflow",
                method="ast_and_local_model", role=role, stages=stages,
                stage_count=sum(1 for ok in stages.values() if ok),
                proposal_lifecycle=lives,
                model_no_usable_edit=any(item.get("verdict") == "no_usable_edit" for item in lives),
                model_usable_discarded=any(item.get("verdict") == "usable_but_discarded" for item in lives),
                model_queued=any(item.get("queued") for item in lives),
                outcome=result.get("outcome_category"),
                public_passed=result.get("public_tests_passed"),
                private=private,
                structurally_valid=any(item.get("validation_ok") for item in lives) or bool(result.get("patch_attempts")),
                functional_correctness=bool((private or {}).get("all_passed")),
                applied_operator=result.get("applied_operator"),
                model_trace=result.get("model_trace"),
                frozen_after_development=role == "fresh",
                complete_correctness=False,
                final_files=result.get("final_files") or spec["files"],
                **trace_costs(result),
            ))


def run_conversation(config, emit, meter, live_runtime=None):
    from .lab import SeedWorkspace
    from .conversation_capability import send, write_files
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = write_files(root, config["conversation_files"])
        ws = SeedWorkspace(root / "chat", local_runtime=live_runtime, attach_local_runtime=False)
        sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
        notes = str(paths["notes"])
        fees = str(paths["fees"])
        send(ws, sid, f'Use file "{notes}".')
        meter.call("chat:setup", "chat", "setup",
                   lambda text: send(ws, sid, text),
                   f'Summarize totals grouped by region for "{notes}".')
        for spec in config["conversation"]:
            text = spec["text"].format(notes=notes, fees=fees)
            result = meter.call("chat:" + spec["id"], "chat", spec["id"],
                                lambda body: send(ws, sid, body), text)
            state = result["chat"]["context"]["workspace"]
            scored = score_conversation_quality(result.get("text", ""), state, spec.get("expected") or {})
            emit(dict(
                kind="capability", area="language", id=spec["id"], category="language",
                conversation_kind=spec["kind"], response=result,
                quality=scored, selected=state.get("selected_file"),
                pending_after=state.get("pending_clarification"),
            ))


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
    ))
    run_boundary(config, emit, meter)
    run_workflow(config, emit, meter, live_runtime)
    run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    boundary = [row for row in records if row.get("category") == "boundary"]
    workflow = [row for row in records if row.get("category") == "workflow"]
    language = [row for row in records if row.get("category") == "language"]
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        boundary=[{
            "id": row["id"], "role": row.get("role"),
            "evidence_resolved": (row.get("evidence") or {}).get("resolved"),
            "accepted": row.get("accepted"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
        } for row in boundary],
        workflow=[{
            "id": row["id"], "role": row.get("role"),
            "stages": row.get("stages"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "model_queued": row.get("model_queued"),
            "model_no_usable_edit": row.get("model_no_usable_edit"),
            "model_usable_discarded": row.get("model_usable_discarded"),
            "structurally_valid": row.get("structurally_valid"),
            "functional_correctness": row.get("functional_correctness"),
        } for row in workflow],
        language=[{
            "id": row["id"], "kind": row.get("conversation_kind"),
            "passed": (row.get("quality") or {}).get("passed"),
            "facts_ok": (row.get("quality") or {}).get("facts_ok"),
            "attribution_ok": (row.get("quality") or {}).get("attribution_ok"),
            "state_ok": (row.get("quality") or {}).get("state_ok"),
        } for row in language],
        conversation_pass=sum(1 for row in language if (row.get("quality") or {}).get("passed")),
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
