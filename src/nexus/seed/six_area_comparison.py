"""Six-area development comparison. Never confirmation or learning-to-learn promotion.

Pipeline: request → language → memory retrieval → proposal → sandbox → tests
→ explanation. Procedure/repair memory and learned investigation policy are
scored as separate improvements against ordinary caching and reset/shuffle.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import (
    EventMeter, SharedLedger, catalogue, digest, make_task, parameters, train_public,
)
from .capability_widening_coding import out_of_grammar_task
from .combined_investigation_engine import (
    EqualizedControllerConfig, EqualizedInvestigationEngineV2, execute_pipeline,
)
from .repair_schema_memory import (
    PREDECLARED_FAMILIES, OrdinaryExactCache, RepairSchemaStore,
    capture_from_success, transfer_success_rate,
)
from .scoped_id_staging import trace_costs
from .symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
from .workspace_conversation import score_workspace_reply, workspace_context_header


INVESTIGATION_BASE = {
    "fixed_boundary": "boundary_first",
    "learned": "learned",
    "capsules_reset": "capsules_reset",
    "shuffled": "shuffled",
}

CODING_SETUP = {
    "model_tools": {"sources": ("local_model",), "repair": False, "cache": False},
    "model_tools_cache": {"sources": ("local_model",), "repair": False, "cache": True},
    "nexus_repair_memory": {"sources": ("ast", "local_model"), "repair": True, "cache": False},
}


def controller(config):
    raw = dict(config["controller"])
    allowed = EqualizedControllerConfig.__dataclass_fields__
    return EqualizedControllerConfig(**{k: v for k, v in raw.items() if k in allowed})


def _view(spec, suffix="", budget=4):
    return AgentTaskPublicView(
        spec["id"] + suffix, "development", spec["domain"], spec["language"],
        spec["request"], spec["files"], spec.get("public") or spec.get("cases") or [],
        spec.get("docs", []),
        budget_steps=int(budget),
    )


def _assess(meter, scope, spec, files):
    return meter.call(scope, "assessment_worker", spec["id"],
                      lambda payload: run_worker_subprocess(payload, 10),
                      dict(language=spec["language"], files=files, cases=spec["assessment"]))


def run_investigation(config, emit, meter):
    ctrl = controller(config)
    for seed in config["seeds"]:
        source = [make_task(config, seed, "source", i, meter) for i in range(config["source_tasks"])]
        answers = {t.task_id: (lambda x, ops=ops: execute_pipeline(ops, x)) for t, ops, _ in source}
        learned = train_public([t for t, _, _ in source], answers, meter, seed, config)
        emit(dict(kind="learned_state", seed=seed, area="learning_to_learn",
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
                scope = f"{seed}:{method}:{task.task_id}"
                engine = EqualizedInvestigationEngineV2(
                    ledger_factory=lambda: SharedLedger(meter, scope),
                    strict_controller_bounds=True,
                )
                params, mode = parameters(INVESTIGATION_BASE[method], learned, task, seed)
                engine.set_strategy_params(params)
                keep_caps = method == "learned"
                if keep_caps:
                    engine.knowledge.skills.capsules = {c.capsule_id: deepcopy(c) for c in learned[3]}
                class Answers:
                    def request_answer(self, tid, x):
                        if family == "oog":
                            return [int(v) * int(v) for v in x]
                        return execute_pipeline(ops, x)
                started = time.perf_counter()
                episode = engine.investigate_v2(
                    task, Answers(), ctrl, mode,
                    allow_compositional_capsules=keep_caps,
                    consolidate_on_solve=keep_caps,
                )
                emit(dict(kind="choice", scope=scope, selected=episode["selected_candidate_id"],
                          selected_ops=episode["selected_ops"],
                          identification_status=episode.get("identification_status"),
                          certainty_claimed=episode.get("certainty_claimed"),
                          family=family, method=method, capsules_kept=keep_caps))
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
                emit(dict(kind="episode", area="learning_to_learn", scope=scope, seed=seed,
                          method=method, task=task.task_id, family=family,
                          unseen_level="L3" if family == "oog" else "L2",
                          identified=identified, assessment_match=refs == outs,
                          identification_status=episode.get("identification_status"),
                          unchecked_remaining=episode.get("unchecked_remaining"),
                          certainty_claimed=bool(episode.get("certainty_claimed")),
                          false_certainty=bool(episode.get("certainty_claimed")) and (
                              refs != outs or bool(episode.get("unresolved_alternatives"))
                          ),
                          stopping_reason=episode.get("stopping_reason"),
                          n_candidate_calls=episode["n_candidate_calls"],
                          n_questions=episode["n_questions"],
                          wall_s=round(time.perf_counter() - started, 6),
                          capsules_kept=keep_caps,
                          policy_reset=method == "capsules_reset",
                          policy_shuffled=method == "shuffled",
                          training_cost_charged_separately=True))


def _solve_coding(spec, condition, live_runtime, store, cache, meter, tmp, budget):
    setup = CODING_SETUP[condition]
    scope = f"coding:{condition}:{spec['id']}"
    started = time.perf_counter()
    reused = None
    cache_hit = False
    if setup["cache"]:
        cached = cache.get(spec["request"], spec["files"])
        cache_hit = cached is not None
        if cached is not None:
            public = meter.call(scope, "worker", spec["id"],
                                lambda payload: run_worker_subprocess(payload, 10),
                                dict(language=spec["language"], files=cached, cases=spec["public"]))
            return dict(
                outcome_category="solved" if public.get("all_passed") else "failed",
                public_tests_passed=bool(public.get("all_passed")),
                final_files=cached, model_trace=[], patch_attempts=[],
                published_after_validation=bool(public.get("all_passed")),
                cache_hit=True, reused=False, path="ordinary_cache",
                wall_s=round(time.perf_counter() - started, 6),
            )
    if setup["repair"]:
        schema = store.lookup(spec.get("family") or "", spec["request"])
        reused = store.apply(schema, spec["files"]) if schema is not None else None
        if reused is not None:
            public = meter.call(scope, "worker", spec["id"],
                                lambda payload: run_worker_subprocess(payload, 10),
                                dict(language=spec["language"], files=reused, cases=spec["public"]))
            if public.get("all_passed"):
                return dict(
                    outcome_category="solved", public_tests_passed=True,
                    final_files=reused, model_trace=[], patch_attempts=[],
                    published_after_validation=True, cache_hit=False, reused=True,
                    path="repair_schema", wall_s=round(time.perf_counter() - started, 6),
                )
    task = _view(spec, ":" + condition, budget=budget)
    loop = SymbioticAgentLoop(
        Path(tmp) / condition / spec["id"],
        local_runtime=live_runtime,
        allow_acquired_memory=setup["repair"],
        proposal_sources=setup["sources"],
        model_revision_budget=2,
    )
    if setup["repair"]:
        loop.repair_schema_store = store
    def worker(payload, timeout_s=10):
        return meter.call(scope, "worker", spec["id"],
                          lambda data: run_worker_subprocess(data, timeout_s), payload)
    with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
        result = meter.call(scope, "agent", spec["id"], lambda _: loop.solve(task), None)
    if type(result) is not dict:
        return dict(outcome_category="failed", reason="non_dict_result", final_files=spec["files"],
                    model_trace=[], cache_hit=cache_hit, reused=reused is not None, path="loop")
    result = dict(result)
    if result.get("public_tests_passed"):
        if setup["cache"]:
            cache.put(spec["request"], spec["files"], result["final_files"])
        if setup["repair"] and spec.get("family") in PREDECLARED_FAMILIES:
            schema = capture_from_success(
                spec.get("family") or "", spec["request"], spec["files"], result["final_files"],
                spec["public"], {"wall_s": result.get("total_wall_s", 0), "phase": "genuine_source"},
            )
            if schema is not None:
                store.remember(schema)
    result["cache_hit"] = cache_hit
    result["reused"] = False
    result["path"] = "loop"
    return result


def run_coding(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 4))
    with tempfile.TemporaryDirectory() as tmp:
        store = RepairSchemaStore()
        cache = OrdinaryExactCache()
        for spec in config["coding"]:
            if spec["id"] in config["closed_coding_ids_excluded"]:
                raise ValueError("closed_coding_id_reused:" + spec["id"])
            for condition in config["coding_conditions"]:
                scope = f"coding:{condition}:{spec['id']}"
                result = _solve_coding(spec, condition, live_runtime, store, cache, meter, tmp, budget)
                private = _assess(meter, scope, spec, result.get("final_files") or spec["files"])
                costs = trace_costs(result)
                emit(dict(kind="capability", area="unfamiliar_coding", id=spec["id"],
                          method=condition, category="coding", family=spec["family"],
                          role=spec.get("role", "assessment"), unseen_level="L2",
                          outcome=result.get("outcome_category"),
                          public_passed=result.get("public_tests_passed"),
                          private=private, model_trace=result.get("model_trace"),
                          attempts=len(result.get("patch_attempts") or []),
                          cache_hit=result.get("cache_hit"), reused=result.get("reused"),
                          path=result.get("path"), final_files=result.get("final_files"),
                          complete_correctness=False, **costs))
        later = dict(config["reuse"]["assessment"])
        source_id = config["reuse"]["source_id"]
        for condition in config["coding_conditions"]:
            scope = f"reuse:{condition}:{later['id']}"
            result = _solve_coding(later, condition, live_runtime, store, cache, meter, tmp, budget)
            private = _assess(meter, scope, later, result.get("final_files") or later["files"])
            none = _assess(meter, scope + ":none", later, later["files"])
            emit(dict(kind="capability", area="knowledge_reuse", id=later["id"],
                      method=condition, category="reuse", family=later["family"],
                      source_id=source_id, unseen_level="L2",
                      outcome=result.get("outcome_category"),
                      public_passed=result.get("public_tests_passed"),
                      private=private, none_private=none,
                      cache_hit=result.get("cache_hit"), reused=result.get("reused"),
                      path=result.get("path"), final_files=result.get("final_files"),
                      model_trace=result.get("model_trace"),
                      complete_correctness=False, **trace_costs(result)))
        source = next(s for s in config["coding"] if s["id"] == source_id)
        for condition, files, name in (
            ("model_tools", source["files"], "none"),
            ("model_tools_cache", cache.get(source["request"], source["files"]) or source["files"], "cache"),
            ("nexus_repair_memory", (store.apply(store.lookup(source["family"], source["request"]), source["files"])
                                     or source["files"]), "memory"),
        ):
            private = _assess(meter, f"retention:{condition}", source, files)
            emit(dict(kind="capability", area="retention", id=source["id"], method=condition,
                      category="retention", family=source["family"],
                      private=private, retained_via=name,
                      store_size=len(store.schemas), cache_size=len(cache.store),
                      complete_correctness=False))
        emit(dict(kind="repair_store", persisted=len(store.schemas),
                  cache_hits=cache.hits, cache_misses=cache.misses,
                  acquisition_events=len(store.acquisition_events)))


def run_reasoning(config, emit, meter):
    for spec in config["reasoning"]:
        started = time.perf_counter()
        executed = meter.call("reason:" + spec["id"], "assessment_worker", spec["id"],
                              lambda payload: run_worker_subprocess(payload, 10),
                              dict(language=spec["language"], files=spec["files"], cases=spec["cases"]))
        emit(dict(kind="capability", area="reasoning", id=spec["id"], category="reasoning",
                  method="sandbox_execution", reasoning_kind=spec["kind"],
                  private=executed, execution_backed=True,
                  all_passed=bool(executed.get("all_passed")),
                  wall_s=round(time.perf_counter() - started, 6),
                  complete_correctness=False))


def run_conversation(config, emit, meter, live_runtime=None):
    from .lab import SeedWorkspace
    from .conversation_capability import send
    with tempfile.TemporaryDirectory() as tmp:
        ws = SeedWorkspace(Path(tmp) / "chat", local_runtime=live_runtime, attach_local_runtime=False)
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
            emit(dict(kind="capability", area="language", id=spec["id"], category="language",
                      response=result, follow_up=follow, rubric=spec["rubric"],
                      conversation_kind=spec["kind"], workspace_score=scored,
                      header_input_token_estimate=meta["input_token_estimate"],
                      scoring="real_state_and_needed_question; not_header_keyword"))


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(kind="audit_manifest", config_hash=digest(config),
              catalogue_hash=digest([(cid, ops) for cid, ops, _ in catalogue(config)]),
              gemini=config.get("gemini", "NOT_RUN"),
              result_label="authored_source_development_pilot_not_confirmation",
              identified_only_if="identified_within_catalogue",
              separate_improvements=["procedure_or_repair_memory", "learned_investigation_policy"],
              learning_to_learn_established=False))
    run_investigation(config, emit, meter)
    run_coding(config, emit, meter, live_runtime)
    run_reasoning(config, emit, meter)
    run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    from .capability_widening_coding import summarize as base
    out = base(records, config)
    episodes = [r for r in records if r.get("kind") == "episode"]
    learned = [r for r in episodes if r.get("method") == "learned"]
    reset = [r for r in episodes if r.get("method") == "capsules_reset"]
    shuffled = [r for r in episodes if r.get("method") == "shuffled"]
    fixed = [r for r in episodes if r.get("method") == "fixed_boundary"]
    def pack(rows):
        return dict(
            n=len(rows),
            identified=sum(1 for r in rows if r.get("identified")),
            assessment_match=sum(1 for r in rows if r.get("assessment_match") and r.get("family") != "oog"),
            calls=sum(int(r.get("n_candidate_calls") or 0) for r in rows),
            false_certainty=sum(1 for r in rows if r.get("false_certainty")),
        )
    learned_pack, reset_pack, shuffled_pack, fixed_pack = map(pack, (learned, reset, shuffled, fixed))
    advantage_vs_fixed = (
        learned_pack["assessment_match"] >= fixed_pack["assessment_match"]
        and learned_pack["calls"] < fixed_pack["calls"]
        if learned_pack["n"] and fixed_pack["n"] else False
    )
    remains_after_reset = (
        reset_pack["assessment_match"] == learned_pack["assessment_match"]
        and reset_pack["calls"] <= learned_pack["calls"] + max(4, learned_pack["calls"] // 10)
        if reset_pack["n"] and learned_pack["n"] else False
    )
    disappears_when_shuffled = (
        shuffled_pack["calls"] > learned_pack["calls"]
        or shuffled_pack["assessment_match"] < learned_pack["assessment_match"]
        if shuffled_pack["n"] and learned_pack["n"] else False
    )
    out["learning_to_learn"] = {
        "learned": learned_pack, "capsules_reset": reset_pack,
        "shuffled": shuffled_pack, "fixed_boundary": fixed_pack,
        "advantage_vs_fixed": advantage_vs_fixed,
        "remains_after_capsule_reset": remains_after_reset,
        "disappears_when_shuffled": disappears_when_shuffled,
        "established": bool(advantage_vs_fixed and remains_after_reset and disappears_when_shuffled),
    }
    coding = [r for r in records if r.get("category") == "coding"]
    reuse = [r for r in records if r.get("category") == "reuse"]
    retention = [r for r in records if r.get("category") == "retention"]
    reasoning = [r for r in records if r.get("category") == "reasoning"]
    out["coding_by_condition"] = {
        cond: {
            "n": sum(1 for r in coding if r.get("method") == cond),
            "private_pass": sum(1 for r in coding if r.get("method") == cond and (r.get("private") or {}).get("all_passed")),
            "cache_hits": sum(1 for r in coding if r.get("method") == cond and r.get("cache_hit")),
            "reused": sum(1 for r in coding if r.get("method") == cond and r.get("reused")),
        } for cond in config["coding_conditions"]
    }
    reuse_outcomes = [bool((r.get("private") or {}).get("all_passed")) for r in reuse
                      if r.get("method") == "nexus_repair_memory"]
    out["knowledge_reuse"] = {
        "n": len(reuse),
        "by_condition": {
            r["method"]: {
                "private_pass": bool((r.get("private") or {}).get("all_passed")),
                "none_pass": bool((r.get("none_private") or {}).get("all_passed")),
                "cache_hit": bool(r.get("cache_hit")),
                "reused": bool(r.get("reused")),
                "path": r.get("path"),
            } for r in reuse
        },
        "rates": transfer_success_rate(reuse_outcomes),
    }
    out["retention"] = {
        r["method"]: bool((r.get("private") or {}).get("all_passed")) for r in retention
    }
    out["reasoning"] = {
        r["id"]: bool(r.get("all_passed")) for r in reasoning
    }
    model_rows = [r for r in coding + reuse if r.get("method") in set(config["coding_conditions"])]
    out["reconstructed_costs"] = {
        "completions": sum(int(r.get("completions") or 0) for r in model_rows),
        "generated_tokens": sum(int(r.get("generated_tokens") or 0) for r in model_rows),
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in model_rows),
        "request_wall_s": round(sum(float(r.get("request_wall_s") or 0) for r in model_rows), 6),
    }
    out["learning_to_learn_established"] = False
    return out
