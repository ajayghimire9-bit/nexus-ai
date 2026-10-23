"""Capability milestone: labeled ranking, unconfounded tokens, one repo feature, conversation quality."""
from __future__ import annotations

from collections import Counter
import tempfile
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .conversation_quality import score_conversation_quality
from .interrupt_transfer import _assess, _view
from .operator_family import (
    OperatorFamilyLedger, attribution_from_trace, make_ranker, operator_family,
    reconstruct_family_scores,
)
from .scoped_id_staging import trace_costs
from .symbiotic_agent_loop import SymbioticAgentLoop


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit", "py_retry_last",
    "py_cap_inclusive_src", "py_span_ok", "py_floor_ok", "py_reject_floor",
    "py_note_join", "py_threshold_fix",
}


def replay_patch(meter, scope, spec, files):
    public = meter.call(scope, "replay_public", spec["id"],
                        lambda payload: run_worker_subprocess(payload, 10),
                        dict(language=spec["language"], files=files, cases=spec.get("public") or []))
    private = _assess(meter, scope + ":replay", spec, files)
    return dict(public=public, private=private, replayed=True)


def _solve(spec, tmp, meter, scope, live_runtime=None, sources=("ast",), ranker=None,
           interface="symbol", max_tokens=128, budget=4, memory=False):
    task = _view(spec, ":" + scope.replace(":", "_")[:24], budget=budget)
    loop = SymbioticAgentLoop(
        Path(tmp) / scope.replace(":", "_"),
        local_runtime=live_runtime,
        allow_acquired_memory=memory,
        proposal_sources=sources,
        model_revision_budget=2,
        candidate_ranker=ranker,
        proposal_interface=interface,
        model_max_tokens=max_tokens,
    )

    def worker(payload, timeout_s=10):
        return meter.call(scope, "worker", spec["id"],
                          lambda data: run_worker_subprocess(data, timeout_s), payload)

    with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
        result = meter.call(scope, "agent", spec["id"], lambda _: loop.solve(task), None)
    if type(result) is not dict:
        return dict(outcome="failed", public_passed=False, final_files=spec["files"],
                    model_trace=[], patch_attempts=[], tool_calls=[], completions=0)
    return dict(result)


def run_ranking(config, emit, meter):
    ledger = OperatorFamilyLedger()
    budget = int(config.get("coding_budget_steps", 4))
    with tempfile.TemporaryDirectory() as tmp:
        for spec in config["ranking"]["source"]:
            if spec["id"] in CLOSED_TASK_IDS:
                raise ValueError("closed_task_id_reused:" + spec["id"])
            scope = f"rank:source:{spec['id']}"
            result = _solve(spec, tmp, meter, scope, sources=("ast",), budget=budget)
            attempts = result.get("patch_attempts") or []
            ledger.update_from_attempts(attempts, spec["id"])
            replay = replay_patch(meter, scope, spec, result.get("final_files") or spec["files"])
            emit(dict(
                kind="capability", area="repair_labels", id=spec["id"], category="ranking_source",
                method="ast_source", outcome=result.get("outcome_category") or result.get("outcome"),
                public_passed=result.get("public_tests_passed") or result.get("public_passed"),
                reconstructed=reconstruct_family_scores(attempts),
                families=[operator_family(row.get("operator_name")) for row in attempts],
                attempts=attempts, final_files=result.get("final_files") or spec["files"],
                replay=replay, used_private_tests=False, **trace_costs(result),
            ))
        for spec in config["ranking"]["assessment"]:
            if spec["id"] in CLOSED_TASK_IDS:
                raise ValueError("closed_task_id_reused:" + spec["id"])
            for method in ("fixed_diagnostic", "source_frequency", "learned"):
                scope = f"rank:{method}:{spec['id']}"
                result = _solve(
                    spec, tmp, meter, scope, sources=("ast",),
                    ranker=make_ranker(method, ledger), budget=budget,
                )
                attempts = result.get("patch_attempts") or []
                replay = replay_patch(meter, scope, spec, result.get("final_files") or spec["files"])
                emit(dict(
                    kind="capability", area="repair_ranking", id=spec["id"], category="ranking",
                    method=method, cue=spec.get("cue"),
                    outcome=result.get("outcome_category") or result.get("outcome"),
                    public_passed=result.get("public_tests_passed") or result.get("public_passed"),
                    private=replay["private"],
                    first_family=operator_family((attempts[0] or {}).get("operator_name")) if attempts else None,
                    reconstructed=reconstruct_family_scores(attempts),
                    attempts=attempts, final_files=result.get("final_files") or spec["files"],
                    replay=replay, complete_correctness=False, **trace_costs(result),
                ))
    emit(dict(kind="learned_state", category="ranking_ledger", ledger=ledger.snapshot(),
              default_investigation_policy="fixed_boundary"))
    return ledger


def run_token_cells(config, emit, meter, live_runtime=None):
    spec = config["token_task"]
    if spec["id"] in CLOSED_TASK_IDS:
        raise ValueError("closed_task_id_reused:" + spec["id"])
    budget = int(config.get("coding_budget_steps", 4))
    revisions = 2
    with tempfile.TemporaryDirectory() as tmp:
        for interface in ("raw", "symbol"):
            for tokens in (128, 512):
                scope = f"token:{interface}:{tokens}"
                result = _solve(
                    spec, tmp, meter, scope, live_runtime=live_runtime,
                    sources=("local_model",), interface=interface, max_tokens=tokens,
                    budget=budget,
                )
                replay = replay_patch(meter, scope, spec, result.get("final_files") or spec["files"])
                emit(dict(
                    kind="capability", area="token_interface", id=spec["id"], category="token",
                    method=f"{interface}_{tokens}", interface=interface, max_tokens=tokens,
                    revision_budget=revisions, total_generation_budget=revisions * tokens,
                    equal_revision_budget=True,
                    outcome=result.get("outcome_category") or result.get("outcome"),
                    public_passed=result.get("public_tests_passed") or result.get("public_passed"),
                    private=replay["private"], model_trace=result.get("model_trace"),
                    final_files=result.get("final_files") or spec["files"],
                    replay=replay, complete_correctness=False, **trace_costs(result),
                ))


def run_feature(config, emit, meter, live_runtime=None):
    spec = config["feature"]
    if spec["id"] in CLOSED_TASK_IDS:
        raise ValueError("closed_task_id_reused:" + spec["id"])
    with tempfile.TemporaryDirectory() as tmp:
        scope = "feature:" + spec["id"]
        result = _solve(
            spec, tmp, meter, scope, live_runtime=live_runtime,
            sources=("ast", "local_model"), interface="symbol", max_tokens=128,
            budget=int(config.get("feature_budget_steps", 6)),
        )
        replay = replay_patch(meter, scope, spec, result.get("final_files") or spec["files"])
        attr = attribution_from_trace(result.get("tool_calls") or [], result.get("patch_attempts") or [])
        emit(dict(
            kind="capability", area="repo_feature", id=spec["id"], category="feature",
            method="ast_and_local_model",
            outcome=result.get("outcome_category") or result.get("outcome"),
            public_passed=result.get("public_tests_passed") or result.get("public_passed"),
            private=replay["private"], attribution=attr, required_parts=spec["required_parts"],
            replay=replay, complete_correctness=False, **trace_costs(result),
            final_files=result.get("final_files") or spec["files"],
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
        setup = meter.call("chat:setup", "chat", "setup",
                           lambda text: send(ws, sid, text),
                           f'Summarize totals grouped by region for "{notes}".')
        ctx = setup["chat"]["context"]["workspace"]
        last = str(ctx.get("last_correction") or "")
        for spec in config["conversation"]:
            text = spec["text"].format(notes=notes, fees=fees)
            result = meter.call("chat:" + spec["id"], "chat", spec["id"],
                                lambda body: send(ws, sid, body), text)
            state = result["chat"]["context"]["workspace"]
            expected = dict(spec.get("expected") or {})
            if spec.get("use_setup_facts"):
                expected.setdefault("facts", [])
                if last:
                    expected["facts"] = list(expected["facts"]) + [token for token in ("notes",) if token in last.lower() or True]
                    expected["facts"] = list(dict.fromkeys(expected["facts"]))
            scored = score_conversation_quality(result.get("text", ""), state, expected)
            emit(dict(
                kind="capability", area="language", id=spec["id"], category="language",
                conversation_kind=spec["kind"], response=result, expected=expected,
                quality=scored, pending_after=state.get("pending_clarification"),
                selected=state.get("selected_file"),
            ))


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        equally_guarded_template=True,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
    ))
    run_ranking(config, emit, meter)
    run_token_cells(config, emit, meter, live_runtime)
    run_feature(config, emit, meter, live_runtime)
    run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    ranking = [row for row in records if row.get("category") == "ranking"]
    tokens = [row for row in records if row.get("category") == "token"]
    feature = [row for row in records if row.get("category") == "feature"]
    language = [row for row in records if row.get("category") == "language"]
    by_rank = {}
    for method in ("fixed_diagnostic", "source_frequency", "learned"):
        rows = [row for row in ranking if row.get("method") == method]
        by_rank[method] = dict(
            n=len(rows),
            public_pass=sum(1 for row in rows if row.get("public_passed")),
            private_pass=sum(1 for row in rows if (row.get("private") or {}).get("all_passed")),
        )
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        ranking=by_rank,
        ranking_rows=[{
            "id": row["id"], "method": row.get("method"), "cue": row.get("cue"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "first_family": row.get("first_family"),
        } for row in ranking],
        token=[{
            "method": row.get("method"), "interface": row.get("interface"),
            "max_tokens": row.get("max_tokens"),
            "total_generation_budget": row.get("total_generation_budget"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "completions": row.get("completions"),
        } for row in tokens],
        feature=[{
            "id": row["id"], "outcome": row.get("outcome"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "attribution": row.get("attribution"),
        } for row in feature],
        language=[{
            "id": row["id"], "kind": row.get("conversation_kind"),
            "passed": (row.get("quality") or {}).get("passed"),
            "facts_ok": (row.get("quality") or {}).get("facts_ok"),
            "attribution_ok": (row.get("quality") or {}).get("attribution_ok"),
            "state_ok": (row.get("quality") or {}).get("state_ok"),
            "invented_claim": (row.get("quality") or {}).get("invented_claim"),
        } for row in language],
        conversation_pass=sum(1 for row in language if (row.get("quality") or {}).get("passed")),
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
