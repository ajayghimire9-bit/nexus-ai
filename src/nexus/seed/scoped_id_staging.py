"""Scoped-identification / staging development runner. Never confirmation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import tempfile
import time
from pathlib import Path

from .capability_evidence import (
    EventMeter, SharedLedger, catalogue, digest, make_task, parameters, train_public,
)
from .capability_widening_coding import historical_artifact_fingerprints, out_of_grammar_task
from .combined_investigation_engine import (
    EqualizedControllerConfig, EqualizedInvestigationEngineV2, execute_pipeline,
)
from .repair_schema_memory import (
    OrdinaryExactCache, RepairSchemaStore, capture_from_success, transfer_success_rate,
)
from .symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
from .agent_loop_worker import run_worker_subprocess
from .workspace_conversation import score_workspace_reply, workspace_context_header


METHOD_STRATEGY = {
    "no_widening": ("ranked", False),
    "ranked_widening": ("ranked", True),
    "stratified_widening": ("stratified", True),
}


def controller(config, enable_widening, strategy="ranked"):
    raw = dict(config["controller"])
    raw["enable_widening"] = enable_widening
    raw["widen_strategy"] = strategy
    allowed = EqualizedControllerConfig.__dataclass_fields__
    return EqualizedControllerConfig(**{k: v for k, v in raw.items() if k in allowed})


def run_investigation(config, emit, meter):
    for seed in config["seeds"]:
        source = [make_task(config, seed, "source", i, meter) for i in range(config["source_tasks"])]
        answers = {t.task_id: (lambda x, ops=ops: execute_pipeline(ops, x)) for t, ops, _ in source}
        learned = train_public([t for t, _, _ in source], answers, meter, seed, config)
        emit(dict(kind="learned_state", seed=seed,
                  capsules=len(learned[3]), state_hash=digest(asdict(learned[3][0]) if learned[3] else {})))
        assessments = [make_task(config, seed, "assessment", i, meter)
                       for i in range(config["assessment_tasks"])]
        if config.get("out_of_grammar_tasks"):
            assessments.append(out_of_grammar_task(config, seed, meter) + ("oog",))
        for item in assessments:
            if len(item) == 4:
                task, ops, rows, family = item
            else:
                task, ops, rows = item
                family = "in_grammar"
            for method in config["methods"]:
                strategy, enable = METHOD_STRATEGY[method]
                scope = f"{seed}:{method}:{task.task_id}"
                engine = EqualizedInvestigationEngineV2(
                    ledger_factory=lambda: SharedLedger(meter, scope),
                    strict_controller_bounds=True,
                )
                params, mode = parameters("boundary_first", learned, task, seed)
                engine.set_strategy_params(params)
                class Answers:
                    def request_answer(self, tid, x):
                        if family == "oog":
                            return [int(v) * int(v) for v in x]
                        return execute_pipeline(ops, x)
                started = time.perf_counter()
                episode = engine.investigate_v2(
                    task, Answers(), controller(config, enable, strategy), mode,
                    allow_compositional_capsules=False, consolidate_on_solve=False,
                )
                emit(dict(kind="choice", scope=scope, selected=episode["selected_candidate_id"],
                          selected_ops=episode["selected_ops"],
                          stopping_reason=episode.get("stopping_reason"),
                          identification_status=episode.get("identification_status"),
                          halt_cause=(episode.get("widening") or {}).get("halt_cause"),
                          unchecked_remaining=episode.get("unchecked_remaining"),
                          catalogue_exhausted=episode.get("catalogue_exhausted"),
                          widen_strategy=strategy,
                          certainty_claimed=episode.get("certainty_claimed"),
                          family=family))
                refs, outs = [], []
                for j, x in enumerate(rows):
                    expected = Answers().request_answer(task.task_id, x)
                    refs.append(expected)
                    meter.call(scope, "assessment_reference", str(j), lambda _: expected, x)
                    actual = episode["selected_fn"](deepcopy(x))
                    outs.append(actual)
                    meter.call(scope, "assessment_candidate", episode["selected_candidate_id"],
                               lambda _: actual, x)
                identified = (
                    episode.get("identification_status") == "identified_within_catalogue"
                    and refs == outs
                )
                emit(dict(kind="episode", scope=scope, seed=seed, method=method,
                          task=task.task_id, family=family, identified=identified,
                          assessment_match=refs == outs,
                          identification_status=episode.get("identification_status"),
                          halt_cause=(episode.get("widening") or {}).get("halt_cause"),
                          unchecked_remaining=episode.get("unchecked_remaining"),
                          unique_among_checked_not_identified=(
                              episode.get("identification_status") == "unique_among_checked"
                          ),
                          certainty_claimed=bool(episode.get("certainty_claimed")),
                          false_certainty=bool(episode.get("certainty_claimed")) and (
                              refs != outs or bool(episode.get("unresolved_alternatives"))
                          ),
                          stopping_reason=episode.get("stopping_reason"),
                          n_candidate_calls=episode["n_candidate_calls"],
                          n_questions=episode["n_questions"],
                          index_events=(episode.get("widening") or {}).get("index_events", 0),
                          wall_s=round(time.perf_counter() - started, 6),
                          widening_expansions=len((episode.get("widening") or {}).get("expansions", [])),
                          training_cost_charged_separately=True))


def _sources(method):
    return {
        "deterministic_ast": ("ast",),
        "local_model_single": ("local_model",),
        "local_model_per_file": ("local_model_per_file",),
        "hybrid": ("ast", "local_model"),
        "repair_schema_transfer": ("ast",),
    }[method]


def run_coding(config, emit, meter, live_runtime=None):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmp:
        store = RepairSchemaStore()
        cache = OrdinaryExactCache()
        for spec in config["coding"]:
            for method in config["coding_methods"]:
                if method == "repair_schema_transfer":
                    continue
                sources = _sources(method)
                runtime = None if method == "deterministic_ast" else live_runtime
                task = AgentTaskPublicView(
                    spec["id"] + ":" + method, "development", spec["domain"], spec["language"],
                    spec["request"], spec["files"], spec["public"], spec.get("docs", []),
                    budget_steps=int(config.get("coding_budget_steps", 8)),
                )
                scope = f"coding:{method}:{spec['id']}"
                loop = SymbioticAgentLoop(
                    Path(tmp) / method / spec["id"],
                    local_runtime=runtime,
                    allow_acquired_memory=False,
                    proposal_sources=sources,
                )
                def worker(payload, timeout_s=10):
                    return meter.call(scope, "worker", spec["id"],
                                      lambda data: run_worker_subprocess(data, timeout_s), payload)
                with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
                    result = meter.call(scope, "agent", spec["id"], lambda _: loop.solve(task), None)
                if type(result) is not dict:
                    emit(dict(kind="capability", id=spec["id"], method=method, category="coding",
                              outcome="failed", reason="non_dict_result"))
                    continue
                private = meter.call(scope, "assessment_worker", spec["id"],
                                     lambda payload: run_worker_subprocess(payload, 10),
                                     dict(language=spec["language"], files=result["final_files"],
                                          cases=spec["assessment"]))
                revised = any(
                    str(att.get("operator_name", "")).startswith("local_model_revise")
                    for att in result.get("patch_attempts", [])
                )
                emit(dict(kind="capability", id=spec["id"], method=method, category="coding",
                          family=spec["family"], role=spec.get("role", "assessment"),
                          outcome=result.get("outcome_category"),
                          public_passed=result.get("public_tests_passed"),
                          private=private, model_trace=result.get("model_trace"),
                          attempts=len(result.get("patch_attempts", [])),
                          revised=revised,
                          published_after_validation=result.get("published_after_validation"),
                          model_generated_per_file=method == "local_model_per_file",
                          complete_correctness=False,
                          final_files=result.get("final_files"),
                          inference_ran=any(
                              (row or {}).get("inference_ran") for row in (result.get("model_trace") or [])
                          )))
        run_repair_transfer(config, emit, meter, store, cache, Path(tmp) / "repair")


def run_repair_transfer(config, emit, meter, store, cache, persist_dir):
    for spec in config.get("repair_transfer", []):
        family = spec["family"]
        source = spec["source"]
        assess = spec["assessment"]
        started = time.perf_counter()
        schema = capture_from_success(
            family, source["request"], source["files"], source["patched"],
            source["public"], {"wall_s": 0.0, "phase": "acquisition"},
        )
        if schema is not None:
            store.remember(schema)
            cache.put(source["request"], source["files"], source["patched"])
        acquired = time.perf_counter() - started
        reused = store.apply(schema, assess["files"]) if schema is not None else None
        cached = cache.get(assess["request"], assess["files"])
        private = None
        if reused is not None:
            private = meter.call("repair:" + spec["id"], "assessment_worker", spec["id"],
                                 lambda payload: run_worker_subprocess(payload, 10),
                                 dict(language="python", files=reused, cases=assess["assessment"]))
        emit(dict(kind="capability", id=spec["id"], method="repair_schema_transfer",
                  category="coding", family=family, role="transfer",
                  transformation=getattr(schema, "transformation", None),
                  cache_hit=cached is not None,
                  reused=reused is not None,
                  private=private,
                  acquisition_charged=True,
                  acquisition_wall_s=round(acquired, 6),
                  one_success_is_not_100_percent=True,
                  complete_correctness=False))
    store.save(persist_dir)
    loaded = RepairSchemaStore.load(persist_dir)
    emit(dict(kind="repair_store", persisted=len(store.schemas), reloaded=len(loaded.schemas),
              acquisition_events=len(store.acquisition_events)))


def run_conversation(config, emit, meter, live_runtime=None):
    from .lab import SeedWorkspace
    from .conversation_capability import send
    with tempfile.TemporaryDirectory() as tmp:
        ws = SeedWorkspace(Path(tmp) / "chat", local_runtime=live_runtime,
                           attach_local_runtime=False)
        sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
        for spec in config["conversation"]:
            result = meter.call("chat:" + spec["id"], "chat", spec["id"],
                                lambda text: send(ws, sid, text), spec["text"])
            follow = None
            if spec.get("follow_up"):
                follow = meter.call("chat:" + spec["id"] + ":follow", "chat", spec["id"],
                                    lambda text: send(ws, sid, text), spec["follow_up"])
            ctx = result["chat"]["context"]["workspace"]
            header, meta = workspace_context_header(ws, ctx)
            scored = score_workspace_reply(result.get("text", ""), ctx, meta)
            emit(dict(kind="capability", id=spec["id"], category="language",
                      response=result, follow_up=follow, rubric=spec["rubric"],
                      conversation_kind=spec["kind"],
                      workspace_score=scored,
                      header_input_token_estimate=meta["input_token_estimate"],
                      scoring="real_state_and_needed_question; not_header_keyword"))


def run(config, emit, live_runtime=None, include_coding=True, include_conversation=True):
    meter = EventMeter(emit)
    emit(dict(kind="audit_manifest", config_hash=digest(config),
              catalogue_hash=digest([(cid, ops) for cid, ops, _ in catalogue(config)]),
              gemini=config.get("gemini", "NOT_RUN"),
              result_label="authored_source_development_pilot_not_confirmation",
              historical_replay_is_not_confirmation=True,
              identified_only_if="identified_within_catalogue"))
    run_investigation(config, emit, meter)
    if include_coding:
        run_coding(config, emit, meter, live_runtime)
    if include_conversation:
        run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    from .capability_widening_coding import summarize as base
    out = base(records, config)
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    transfer = [r for r in coding if r.get("method") == "repair_schema_transfer"]
    out["repair_transfer"] = {
        "n": len(transfer),
        "reused": sum(1 for r in transfer if r.get("reused")),
        "cache_hits": sum(1 for r in transfer if r.get("cache_hit")),
        "rates": transfer_success_rate([bool((r.get("private") or {}).get("all_passed")) for r in transfer]),
        "acquisition_charged": all(r.get("acquisition_charged") for r in transfer) if transfer else True,
    }
    out["per_file_generation"] = [
        {"id": r["id"], "completions_recorded": r.get("model_generated_per_file")}
        for r in coding if r.get("method") == "local_model_per_file"
    ]
    out["learning_to_learn_established"] = False
    return out
