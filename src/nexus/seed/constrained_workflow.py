"""Constrained function edits, semantic measurement, and one generated-code feature."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .boundary_evidence import competing_boundary_resolved
from .capability_evidence import EventMeter, digest
from .constrained_edit import catalogue_cannot_complete
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
    "py_span_three_point", "py_span_equal_only", "py_width_three_point_dev",
    "py_height_three_point_fresh",
}


def _solve(spec, tmp, meter, scope, live_runtime=None, sources=("ast",),
           interface="constrained", budget=6):
    task = _view(spec, ":" + scope.replace(":", "_")[:24], budget=budget)
    loop = SymbioticAgentLoop(
        Path(tmp) / scope.replace(":", "_"),
        local_runtime=live_runtime,
        allow_acquired_memory=False,
        proposal_sources=sources,
        model_revision_budget=2,
        proposal_interface=interface,
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


def _trace_quality(result):
    lives = []
    raw_valid = []
    normalized = []
    for row in result.get("model_trace") or []:
        life = row.get("lifecycle") or proposal_lifecycle(row, queued=row.get("status") == "proposed")
        lives.append(life)
        raw_valid.append(bool(row.get("raw_valid")))
        normalized.extend(row.get("normalized") or [])
    return dict(
        proposal_lifecycle=lives,
        model_queued=any(item.get("queued") for item in lives),
        model_no_usable_edit=any(item.get("verdict") == "no_usable_edit" for item in lives),
        model_usable_discarded=any(item.get("verdict") == "usable_but_discarded" for item in lives),
        raw_valid=any(raw_valid) if raw_valid else False,
        normalized=normalized,
        preview=(result.get("model_trace") or [{}])[-1].get("preview") if result.get("model_trace") else None,
        plan=(result.get("model_trace") or [{}])[0].get("plan") if result.get("model_trace") else None,
    )


def run_semantic(config, emit, meter, live_runtime=None):
    spec = config["semantic"]
    if spec["id"] in CLOSED_TASK_IDS:
        raise ValueError("closed_task_id_reused:" + spec["id"])
    budget = int(config.get("coding_budget_steps", 6))
    with tempfile.TemporaryDirectory() as tmp:
        result = _solve(
            spec, tmp, meter, "semantic:" + spec["id"], live_runtime=live_runtime,
            sources=("local_model",), interface="constrained", budget=budget,
        )
        evidence = competing_boundary_resolved(spec["request"], spec.get("public") or [])
        private = _assess(meter, "semantic:" + spec["id"], spec, result.get("final_files") or spec["files"])
        quality = _trace_quality(result)
        emit(dict(
            kind="capability", area="semantic_replace", id=spec["id"], category="semantic",
            method="constrained_replace",
            evidence=evidence,
            outcome=result.get("outcome_category"),
            public_passed=result.get("public_tests_passed"),
            private=private,
            semantic_correct=bool((private or {}).get("all_passed")),
            structurally_valid=quality["model_queued"] or bool(result.get("applied_operator")),
            applied_operator=result.get("applied_operator"),
            used_private_to_accept=False,
            complete_correctness=False,
            model_trace=result.get("model_trace"),
            final_files=result.get("final_files") or spec["files"],
            **quality,
            **trace_costs(result),
        ))


def run_feature(config, emit, meter, live_runtime=None):
    spec = config["feature"]
    if spec["id"] in CLOSED_TASK_IDS:
        raise ValueError("closed_task_id_reused:" + spec["id"])
    catalogue = catalogue_cannot_complete(spec)
    if not catalogue.get("cannot_complete"):
        raise ValueError("catalogue_can_complete_feature:" + ",".join(catalogue.get("passing_operators") or []))
    emit(dict(kind="catalogue_check", category="catalogue", id=spec["id"], **catalogue))
    budget = int(config.get("feature_budget_steps", 6))
    with tempfile.TemporaryDirectory() as tmp:
        for method, sources, interface in (
            ("ast", ("ast",), "constrained"),
            ("ast_and_constrained", ("ast", "local_model"), "constrained"),
        ):
            scope = f"feature:{method}:{spec['id']}"
            result = _solve(
                spec, tmp, meter, scope, live_runtime=live_runtime if "local_model" in sources else None,
                sources=sources, interface=interface, budget=budget,
            )
            private = _assess(meter, scope, spec, result.get("final_files") or spec["files"])
            quality = _trace_quality(result)
            emit(dict(
                kind="capability", area="generated_feature", id=spec["id"], category="feature",
                method=method, catalogue=catalogue,
                outcome=result.get("outcome_category"),
                public_passed=result.get("public_tests_passed"),
                private=private,
                semantic_correct=bool((private or {}).get("all_passed")),
                structurally_valid=quality["model_queued"] or bool(result.get("applied_operator")),
                applied_operator=result.get("applied_operator"),
                model_trace=result.get("model_trace"),
                complete_correctness=False,
                final_files=result.get("final_files") or spec["files"],
                **quality,
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
        send(ws, sid, f'Use file "{fees}".')
        meter.call("chat:setup", "chat", "setup",
                   lambda text: send(ws, sid, text),
                   f'Summarize totals grouped by region for "{fees}".')
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
                last_op=(state.get("last_intent") or {}).get("op") if isinstance(state.get("last_intent"), dict) else None,
                pending_after=state.get("pending_clarification"),
            ))


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
    ))
    run_semantic(config, emit, meter, live_runtime)
    run_feature(config, emit, meter, live_runtime)
    run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    semantic = [row for row in records if row.get("category") == "semantic"]
    feature = [row for row in records if row.get("category") == "feature"]
    language = [row for row in records if row.get("category") == "language"]
    catalogue = [row for row in records if row.get("category") == "catalogue"]
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        catalogue=[{
            "id": row["id"], "cannot_complete": row.get("cannot_complete"),
            "candidate_count": row.get("candidate_count"),
            "passing_operators": row.get("passing_operators"),
        } for row in catalogue],
        semantic=[{
            "id": row["id"], "raw_valid": row.get("raw_valid"),
            "normalized": row.get("normalized"),
            "structurally_valid": row.get("structurally_valid"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "model_queued": row.get("model_queued"),
            "applied_operator": row.get("applied_operator"),
        } for row in semantic],
        feature=[{
            "id": row["id"], "method": row.get("method"),
            "raw_valid": row.get("raw_valid"),
            "normalized": row.get("normalized"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "model_queued": row.get("model_queued"),
            "applied_operator": row.get("applied_operator"),
        } for row in feature],
        language=[{
            "id": row["id"], "kind": row.get("conversation_kind"),
            "passed": (row.get("quality") or {}).get("passed"),
            "facts_ok": (row.get("quality") or {}).get("facts_ok"),
            "attribution_ok": (row.get("quality") or {}).get("attribution_ok"),
            "state_ok": (row.get("quality") or {}).get("state_ok"),
            "op_ok": (row.get("quality") or {}).get("op_ok"),
        } for row in language],
        conversation_pass=sum(1 for row in language if (row.get("quality") or {}).get("passed")),
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
