"""Conversation-interrupt, coding-bottleneck and fresh repair-transfer development study."""
from __future__ import annotations

from collections import Counter
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
from .combined_investigation_engine import (
    EqualizedControllerConfig, EqualizedInvestigationEngineV2, execute_pipeline,
)
from .repair_schema_memory import (
    OrdinaryExactCache, RepairSchemaStore, capture_from_success,
    ordinary_template_apply, transfer_success_rate,
)
from .scoped_id_staging import trace_costs
from .symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
from .workspace_conversation import score_workspace_reply, workspace_context_header


def classify_coding_failure(row: dict) -> str:
    traces = row.get("model_trace") or []
    if row.get("reason") == "non_dict_result" or (not traces and not row.get("public_passed")
                                                   and not row.get("completions")):
        return "missing_inference"
    invalid = [t for t in traces if t.get("status") == "invalid_proposal"]
    proposed = [t for t in traces if t.get("status") == "proposed"]
    if invalid and not proposed:
        reasons = " ".join(str(t.get("reason") or "") for t in invalid)
        if "old_text_not_unique" in reasons:
            return "invalid_edits"
        return "invalid_edits"
    if proposed and not row.get("public_passed"):
        if row.get("revised"):
            return "failed_revision"
        return "incorrect_implementation"
    if row.get("public_passed") and not (row.get("private") or {}).get("all_passed"):
        return "public_not_private"
    return "none"


def controller(config):
    raw = dict(config["controller"])
    raw.setdefault("enable_widening", False)
    allowed = EqualizedControllerConfig.__dataclass_fields__
    return EqualizedControllerConfig(**{k: v for k, v in raw.items() if k in allowed})


def _view(spec, suffix="", budget=4):
    return AgentTaskPublicView(
        spec["id"] + suffix, "development", spec["domain"], spec["language"],
        spec["request"], spec["files"], spec.get("public") or [],
        spec.get("docs", []), budget_steps=int(budget),
    )


def _assess(meter, scope, spec, files):
    return meter.call(scope, "assessment_worker", spec["id"],
                      lambda payload: run_worker_subprocess(payload, 10),
                      dict(language=spec["language"], files=files, cases=spec["assessment"]))


def run_conversation(config, emit, meter, live_runtime=None):
    from .lab import SeedWorkspace
    from .conversation_capability import send
    with tempfile.TemporaryDirectory() as tmp:
        ws = SeedWorkspace(Path(tmp) / "chat", local_runtime=live_runtime, attach_local_runtime=False)
        sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
        pending_was = None
        for spec in config["conversation"]:
            result = meter.call("chat:" + spec["id"], "chat", spec["id"],
                                lambda text: send(ws, sid, text), spec["text"])
            ctx = result["chat"]["context"]["workspace"]
            header, meta = workspace_context_header(ws, ctx)
            scored = score_workspace_reply(result.get("text", ""), ctx, meta)
            pending = ctx.get("pending_clarification")
            emit(dict(kind="capability", area="language", id=spec["id"], category="language",
                      response=result, rubric=spec["rubric"], conversation_kind=spec["kind"],
                      workspace_score=scored,
                      pending_before=pending_was, pending_after=pending,
                      superseded=pending_was is not None and pending is None,
                      header_input_token_estimate=meta["input_token_estimate"]))
            pending_was = pending


def run_coding_diagnose(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 4))
    with tempfile.TemporaryDirectory() as tmp:
        for spec in config["diagnose_coding"]:
            scope = f"diagnose:{spec['id']}"
            task = _view(spec, ":diag", budget=budget)
            loop = SymbioticAgentLoop(
                Path(tmp) / spec["id"], local_runtime=live_runtime,
                allow_acquired_memory=False, proposal_sources=("local_model",),
                model_revision_budget=2,
            )
            def worker(payload, timeout_s=10):
                return meter.call(scope, "worker", spec["id"],
                                  lambda data: run_worker_subprocess(data, timeout_s), payload)
            with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
                result = meter.call(scope, "agent", spec["id"], lambda _: loop.solve(task), None)
            if type(result) is not dict:
                row = dict(outcome="failed", reason="non_dict_result", public_passed=False,
                           model_trace=[], final_files=spec["files"], completions=0)
            else:
                result = dict(result)
                private = _assess(meter, scope, spec, result.get("final_files") or spec["files"])
                row = dict(outcome=result.get("outcome_category"),
                           public_passed=result.get("public_tests_passed"),
                           private=private, model_trace=result.get("model_trace"),
                           attempts=len(result.get("patch_attempts") or []),
                           revised=any(str(a.get("operator_name", "")).startswith("local_model_revise")
                                       for a in result.get("patch_attempts") or []),
                           final_files=result.get("final_files"), **trace_costs(result))
            row["failure_class"] = classify_coding_failure(row)
            emit(dict(kind="capability", area="unfamiliar_coding", id=spec["id"],
                      method="model_tools", category="coding", family=spec.get("family"),
                      complete_correctness=False, **row))


def run_transfer(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 4))
    with tempfile.TemporaryDirectory() as tmp:
        store = RepairSchemaStore()
        cache = OrdinaryExactCache()
        source = config["transfer"]["source"]
        task = _view(source, ":src", budget=budget)
        loop = SymbioticAgentLoop(
            Path(tmp) / "source", local_runtime=None,
            allow_acquired_memory=False, proposal_sources=("ast",),
        )
        def worker(payload, timeout_s=10):
            return meter.call("transfer:source", "worker", source["id"],
                              lambda data: run_worker_subprocess(data, timeout_s), payload)
        with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", worker):
            solved = meter.call("transfer:source", "agent", source["id"], lambda _: loop.solve(task), None)
        if type(solved) is dict and solved.get("public_tests_passed"):
            schema = capture_from_success(
                source["family"], source["request"], source["files"], solved["final_files"],
                source["public"], {"wall_s": 0.0, "phase": "genuine_source"},
            )
            if schema is not None:
                store.remember(schema)
            cache.put(source["request"], source["files"], solved["final_files"])
            emit(dict(kind="capability", area="knowledge_reuse", id=source["id"],
                      method="source_ast", category="transfer_source",
                      public_passed=True, genuine_source_acquisition=schema is not None,
                      transformation=getattr(schema, "transformation", None)))
        else:
            emit(dict(kind="capability", area="knowledge_reuse", id=source["id"],
                      method="source_ast", category="transfer_source",
                      public_passed=False, genuine_source_acquisition=False))
        for later in config["transfer"]["later"]:
            schema = store.lookup(later["family"], later["request"])
            memory_files = store.apply(schema, later["files"]) if schema is not None else None
            cache_files = cache.get(later["request"], later["files"])
            template_files = ordinary_template_apply(later["family"], later["files"])
            scratch = None
            task = _view(later, ":scratch", budget=budget)
            loop = SymbioticAgentLoop(
                Path(tmp) / later["id"], local_runtime=live_runtime,
                allow_acquired_memory=False, proposal_sources=("local_model",),
            )
            def sworker(payload, timeout_s=10, spec_id=later["id"]):
                return meter.call("scratch:" + spec_id, "worker", spec_id,
                                  lambda data: run_worker_subprocess(data, timeout_s), payload)
            with patch("nexus.seed.symbiotic_agent_loop.run_worker_subprocess", sworker):
                scratch = meter.call("scratch:" + later["id"], "agent", later["id"],
                                     lambda _: loop.solve(task), None)
            if type(scratch) is not dict:
                scratch = dict(final_files=later["files"], public_tests_passed=False, model_trace=[])
            else:
                scratch = dict(scratch)
            variants = {
                "memory": memory_files,
                "exact_cache": cache_files,
                "template": template_files,
                "model_scratch": scratch.get("final_files"),
                "none": later["files"],
            }
            for name, files in variants.items():
                private = None if files is None else _assess(meter, f"transfer:{later['id']}:{name}", later, files)
                emit(dict(kind="capability", area="knowledge_reuse", id=later["id"],
                          method=name, category="transfer", family=later["family"],
                          reuse_appropriate=later["reuse_appropriate"],
                          private=private, applied=files is not None,
                          path=name, complete_correctness=False,
                          **(trace_costs(scratch) if name == "model_scratch" else {})))


def run_policy_diagnostic(config, emit, meter):
    """Fixed policy stays the default. Learned is measured, not promoted."""
    ctrl = controller(config)
    seed = config["seeds"][0]
    source = [make_task(config, seed, "source", i, meter) for i in range(config["source_tasks"])]
    answers = {t.task_id: (lambda x, ops=ops: execute_pipeline(ops, x)) for t, ops, _ in source}
    learned = train_public([t for t, _, _ in source], answers, meter, seed, config)
    emit(dict(kind="learned_state", seed=seed, capsules=len(learned[3]),
              state_hash=digest(asdict(learned[3][0]) if learned[3] else {}),
              default_policy="fixed_boundary"))
    assessments = [make_task(config, seed, "assessment", i, meter)
                   for i in range(config["assessment_tasks"])]
    before = meter.index
    for task, ops, rows in assessments:
        for method in ("fixed_boundary", "learned"):
            scope = f"{seed}:{method}:{task.task_id}"
            engine = EqualizedInvestigationEngineV2(
                ledger_factory=lambda: SharedLedger(meter, scope),
                strict_controller_bounds=True,
            )
            base = "boundary_first" if method == "fixed_boundary" else "learned"
            params, mode = parameters(base, learned, task, seed)
            engine.set_strategy_params(params)
            if method == "learned":
                engine.knowledge.skills.capsules = {c.capsule_id: deepcopy(c) for c in learned[3]}
            class Answers:
                def request_answer(self, tid, x):
                    return execute_pipeline(ops, x)
            started = time.perf_counter()
            episode = engine.investigate_v2(
                task, Answers(), ctrl, mode,
                allow_compositional_capsules=method == "learned",
                consolidate_on_solve=False,
            )
            emit(dict(kind="choice", scope=scope, selected=episode["selected_candidate_id"],
                      method=method, default_policy=method == "fixed_boundary"))
            refs, outs = [], []
            for j, x in enumerate(rows):
                expected = Answers().request_answer(task.task_id, x)
                refs.append(expected)
                meter.call(scope, "assessment_reference", str(j), lambda _: expected, x)
                actual = episode["selected_fn"](deepcopy(x))
                outs.append(actual)
                meter.call(scope, "assessment_candidate", episode["selected_candidate_id"],
                           lambda _: actual, x)
            emit(dict(kind="episode", area="learning_to_learn", scope=scope, seed=seed,
                      method=method, task=task.task_id,
                      identified=episode.get("identification_status") == "identified_within_catalogue" and refs == outs,
                      assessment_match=refs == outs,
                      identification_status=episode.get("identification_status"),
                      n_candidate_calls=episode["n_candidate_calls"],
                      n_questions=episode["n_questions"],
                      wall_s=round(time.perf_counter() - started, 6),
                      promoted=False))
    return before


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(kind="audit_manifest", config_hash=digest(config),
              catalogue_hash=digest([(cid, ops) for cid, ops, _ in catalogue(config)]),
              default_investigation_policy="fixed_boundary",
              learned_policy_promoted=False,
              gemini=config.get("gemini", "NOT_RUN"),
              result_label="authored_source_development_pilot_not_confirmation"))
    run_policy_diagnostic(config, emit, meter)
    run_coding_diagnose(config, emit, meter, live_runtime)
    run_transfer(config, emit, meter, live_runtime)
    run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    episodes = [r for r in records if r.get("kind") == "episode"]
    events = [r for r in records if r.get("kind") == "execution"]
    by_method = {}
    for method in ("fixed_boundary", "learned"):
        rows = [r for r in episodes if r.get("method") == method]
        scopes = {r["scope"] for r in rows}
        support = sum(1 for e in events if e.get("scope") in scopes and e.get("operation") == "support_check")
        probes = sum(1 for e in events if e.get("scope") in scopes and e.get("operation") == "probe_construction")
        by_method[method] = dict(
            n=len(rows),
            assessment_match=sum(1 for r in rows if r.get("assessment_match")),
            calls=sum(int(r.get("n_candidate_calls") or 0) for r in rows),
            questions=sum(int(r.get("n_questions") or 0) for r in rows),
            support_checks=support,
            probe_constructions=probes,
            promoted=False,
        )
    extra = by_method["learned"]["calls"] - by_method["fixed_boundary"]["calls"]
    extra_support = by_method["learned"]["support_checks"] - by_method["fixed_boundary"]["support_checks"]
    coding = [r for r in records if r.get("category") == "coding"]
    transfer = [r for r in records if r.get("category") == "transfer"]
    language = [r for r in records if r.get("category") == "language"]
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        methods=by_method,
        learned_extra_calls=extra,
        learned_extra_support_checks=extra_support,
        learned_more_expensive=extra > 0,
        coding_failure_classes=dict(Counter(r.get("failure_class") or "none" for r in coding)),
        coding=[{
            "id": r["id"], "outcome": r.get("outcome"),
            "public_passed": r.get("public_passed"),
            "private_passed": (r.get("private") or {}).get("all_passed"),
            "failure_class": r.get("failure_class"),
            "complete_correctness": False,
        } for r in coding],
        transfer=[{
            "id": r["id"], "method": r.get("method"),
            "reuse_appropriate": r.get("reuse_appropriate"),
            "private_passed": (r.get("private") or {}).get("all_passed"),
            "applied": r.get("applied"),
        } for r in transfer],
        transfer_rates=transfer_success_rate([
            bool((r.get("private") or {}).get("all_passed"))
            for r in transfer if r.get("method") == "memory" and r.get("reuse_appropriate")
        ]),
        language=[{"id": r["id"], "kind": r.get("conversation_kind"),
                   "superseded": r.get("superseded")} for r in language],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
