"""Fresh widening/coding development pilot. Never a live-agent promotion."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import time
from pathlib import Path
import tempfile

from .capability_evidence import (
    EventMeter, SharedLedger, catalogue, digest, make_task, parameters, train_public,
)
from .combined_investigation_engine import (
    EqualizedControllerConfig, EqualizedInvestigationEngineV2, execute_pipeline,
)
from .symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
from .agent_loop_worker import run_worker_subprocess


METHOD_BASE = {
    "no_widening": "boundary_first",
    "boundary_first_widening": "boundary_first",
    "cost_aware_widening": "cost_aware",
    "learned_widening": "learned",
    "capsules_reset_widening": "capsules_reset",
}


def controller(config, enable_widening):
    raw = dict(config["controller"])
    raw["enable_widening"] = enable_widening
    allowed = EqualizedControllerConfig.__dataclass_fields__
    return EqualizedControllerConfig(**{k: v for k, v in raw.items() if k in allowed})


def out_of_grammar_task(config, seed, meter):
    """Target uses square, which is outside the locked 6-operator catalogue."""
    public, _ops, rows = make_task(config, seed, "assessment", 99, meter)
    hidden = lambda xs: [int(v) * int(v) for v in xs]
    support = [(x, hidden(x)) for x, _old in public.support_examples]
    from .capability_evidence import PublicInvestigation
    task = PublicInvestigation(
        f"{seed}:assessment:oog",
        "assessment",
        "sequence_pipeline",
        "Infer the observed list transform.",
        support,
        public.probe_pool_inputs,
        public.candidate_pool,
    )
    return task, ("square",), [[3], [4], [0]]


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
                scope = f"{seed}:{method}:{task.task_id}"
                engine = EqualizedInvestigationEngineV2(
                    ledger_factory=lambda: SharedLedger(meter, scope),
                    strict_controller_bounds=True,
                )
                base = METHOD_BASE[method]
                params, mode = parameters(base, learned, task, seed)
                engine.set_strategy_params(params)
                keep_caps = method in ("learned_widening",)
                if keep_caps:
                    engine.knowledge.skills.capsules = {c.capsule_id: deepcopy(c) for c in learned[3]}
                class Answers:
                    def request_answer(self, tid, x):
                        if family == "oog":
                            return [int(v) * int(v) for v in x]
                        return execute_pipeline(ops, x)
                started = time.perf_counter()
                episode = engine.investigate_v2(
                    task, Answers(), controller(config, method != "no_widening"),
                    mode, allow_compositional_capsules=keep_caps,
                    consolidate_on_solve=keep_caps,
                )
                lock = dict(kind="choice", scope=scope, selected=episode["selected_candidate_id"],
                            selected_ops=episode["selected_ops"],
                            stopping_reason=episode.get("stopping_reason"),
                            certainty_claimed=episode.get("certainty_claimed"),
                            family=family)
                emit(lock)
                refs, outs = [], []
                for j, x in enumerate(rows):
                    expected = Answers().request_answer(task.task_id, x)
                    refs.append(expected)
                    meter.call(scope, "assessment_reference", str(j), lambda _: expected, x)
                    actual = episode["selected_fn"](deepcopy(x))
                    outs.append(actual)
                    meter.call(scope, "assessment_candidate", episode["selected_candidate_id"],
                               lambda _: actual, x)
                identified = bool(episode.get("certainty_claimed")) and refs == outs
                false_certainty = bool(episode.get("certainty_claimed")) and (
                    refs != outs or bool(episode.get("unresolved_alternatives"))
                )
                emit(dict(kind="episode", scope=scope, seed=seed, method=method,
                          task=task.task_id, family=family, identified=identified,
                          assessment_match=refs == outs,
                          certainty_claimed=bool(episode.get("certainty_claimed")),
                          false_certainty=false_certainty,
                          stopping_reason=episode.get("stopping_reason"),
                          n_candidate_calls=episode["n_candidate_calls"],
                          n_questions=episode["n_questions"],
                          wall_s=round(time.perf_counter() - started, 6),
                          widening_expansions=len((episode.get("widening") or {}).get("expansions", [])),
                          training_cost_charged_separately=True))


def run_coding(config, emit, meter, live_runtime=None):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmp:
        source_capsule_registry = None
        later = config.get("coding_source_then_later") or {}
        for spec in config["coding"]:
            for method in config["coding_methods"]:
                if method == "persistent_reuse" and spec["id"] not in {
                    later.get("source_id"), later.get("later_id"),
                }:
                    continue
                sources = {
                    "deterministic_ast": ("ast",),
                    "local_model_no_memory": ("local_model",),
                    "hybrid": ("ast", "local_model"),
                    "persistent_reuse": ("ast", "local_model"),
                }[method]
                allow_mem = method == "persistent_reuse"
                runtime = None if method == "deterministic_ast" else live_runtime
                task = AgentTaskPublicView(
                    spec["id"] + ":" + method, "development", spec["domain"], spec["language"],
                    spec["request"], spec["files"], spec["public"], spec.get("docs", []),
                    budget_steps=int(config.get("coding_budget_steps", 8)),
                )
                scope = f"coding:{method}:{spec['id']}"
                registry = source_capsule_registry if allow_mem else None
                loop = SymbioticAgentLoop(
                    Path(tmp) / method / spec["id"],
                    capsule_registry=registry,
                    local_runtime=runtime,
                    allow_acquired_memory=allow_mem,
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
                emit(dict(kind="choice", scope=scope, selected=result.get("applied_operator"),
                          files_sha=result.get("final_files_sha256"),
                          outcome=result.get("outcome_category")))
                private = meter.call(scope, "assessment_worker", spec["id"],
                                     lambda payload: run_worker_subprocess(payload, 10),
                                     dict(language=spec["language"], files=result["final_files"],
                                          cases=spec["assessment"]))
                emit(dict(kind="capability", id=spec["id"], method=method, category="coding",
                          family=spec["family"], outcome=result.get("outcome_category"),
                          public_passed=result.get("public_tests_passed"),
                          private=private, model_trace=result.get("model_trace"),
                          attempts=len(result.get("patch_attempts", [])),
                          complete_correctness=False,
                          final_files=result.get("final_files"),
                          inference_ran=any(
                              (row or {}).get("inference_ran") for row in (result.get("model_trace") or [])
                          )))
                if method == "deterministic_ast" and spec["id"] == later.get("source_id"):
                    source_capsule_registry = loop.capsule_registry


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
            emit(dict(kind="capability", id=spec["id"], category="language",
                      response=result, follow_up=follow, rubric=spec["rubric"],
                      conversation_kind=spec["kind"],
                      scoring="subjective_rubric_review; no keyword accuracy score"))


def run(config, emit, live_runtime=None, include_coding=True, include_conversation=True):
    meter = EventMeter(emit)
    emit(dict(kind="audit_manifest", config_hash=digest(config),
              catalogue_hash=digest([(cid, ops) for cid, ops, _ in catalogue(config)]),
              gemini=config.get("gemini", "NOT_RUN"),
              result_label="authored_source_development_pilot_not_confirmation",
              historical_replay_is_not_confirmation=True))
    run_investigation(config, emit, meter)
    if include_coding:
        run_coding(config, emit, meter, live_runtime)
    if include_conversation:
        run_conversation(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    episodes = [r for r in records if r.get("kind") == "episode"]
    expected_methods = set(config["methods"])
    by_method = {}
    for method in config["methods"]:
        rows = [r for r in episodes if r["method"] == method]
        in_g = [r for r in rows if r.get("family") != "oog"]
        oog = [r for r in rows if r.get("family") == "oog"]
        by_method[method] = dict(
            tasks=len(rows),
            identified=sum(1 for r in in_g if r.get("identified")),
            assessment_match=sum(1 for r in in_g if r.get("assessment_match")),
            in_grammar=len(in_g),
            false_certainty=sum(1 for r in rows if r.get("false_certainty")),
            unresolved=sum(1 for r in rows if str(r.get("stopping_reason", "")).startswith("unresolved")
                           or r.get("stopping_reason") in ("no_answer_source", "budget_exhausted")),
            questions=sum(r.get("n_questions", 0) for r in rows),
            candidate_calls=sum(r.get("n_candidate_calls", 0) for r in rows),
            wall_s=round(sum(r.get("wall_s", 0) for r in rows), 6),
            widening_expansions=sum(r.get("widening_expansions", 0) for r in rows),
            oog_uncertain=sum(1 for r in oog if not r.get("certainty_claimed")),
        )
    if "no_widening" in by_method:
        base_calls = by_method["no_widening"]["candidate_calls"]
        for method, row in by_method.items():
            row["widening_overhead_calls"] = row["candidate_calls"] - base_calls
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    language = [r for r in records if r.get("kind") == "capability" and r.get("category") == "language"]
    return dict(
        declared_complete=len({(r["seed"], r["method"], r["task"]) for r in episodes}) == len(episodes),
        methods=by_method,
        expected_methods=sorted(expected_methods),
        coding=[{
            "id": r["id"], "method": r.get("method"), "outcome": r.get("outcome"),
            "public_passed": r.get("public_passed"),
            "private_passed": (r.get("private") or {}).get("all_passed"),
            "inference_ran": r.get("inference_ran"),
            "complete_correctness": False,
        } for r in coding],
        language=[{"id": r["id"], "kind": r.get("conversation_kind"), "rubric": r.get("rubric")} for r in language],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )


def historical_artifact_fingerprints(root: Path) -> dict[str, str]:
    files = [
        "artifacts/seed_capability_audit.json",
        "artifacts/seed_capability_audit_verified_v2.json",
        "artifacts/seed_capability_audit_raw.jsonl",
    ]
    out = {}
    for rel in files:
        path = root / rel
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return out
