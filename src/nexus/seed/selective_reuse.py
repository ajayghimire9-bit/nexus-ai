"""Selective reuse: retrieved repairs are proposals, not automatic decisions."""
from __future__ import annotations

from collections import Counter
import tempfile
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .interrupt_transfer import classify_coding_failure, _assess, _view
from .repair_schema_memory import (
    OrdinaryExactCache, RepairSchemaStore, capture_from_success,
    ordinary_template_apply, propose_retrieved_repair, transfer_success_rate,
)
from .scoped_id_staging import trace_costs
from .symbiotic_agent_loop import SymbioticAgentLoop


def valid_edit_stats(traces: list[dict]) -> dict:
    structural = [row for row in traces if row.get("status") in {"proposed", "invalid_proposal"}]
    valid = [row for row in structural if row.get("status") == "proposed"]
    return {
        "proposals": len(structural),
        "structurally_valid": len(valid),
        "invalid": len(structural) - len(valid),
        "valid_edit_rate": None if not structural else valid.__len__() / len(structural),
        "functional_correctness_separate": True,
    }


def reuse_label(role: str, decision: str, applied: bool, private_passed: bool | None) -> str:
    if role == "same_repair":
        if applied and private_passed:
            return "correct_reuse"
        if not applied:
            return "unnecessary_abstention"
        return "incorrect_apply"
    if applied:
        return "harmful_reuse"
    return "correct_hold"


def run_coding(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 4))
    with tempfile.TemporaryDirectory() as tmp:
        for spec in config["coding"]:
            scope = f"coding:{spec['id']}"
            task = _view(spec, ":edit", budget=budget)
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
                row = dict(
                    outcome=result.get("outcome_category"),
                    public_passed=result.get("public_tests_passed"),
                    private=private, model_trace=result.get("model_trace"),
                    attempts=len(result.get("patch_attempts") or []),
                    revised=any(str(item.get("operator_name", "")).startswith("local_model_revise")
                                for item in result.get("patch_attempts") or []),
                    final_files=result.get("final_files"), **trace_costs(result),
                )
            traces = row.get("model_trace") or []
            row["failure_class"] = classify_coding_failure(row)
            row["edit_stats"] = valid_edit_stats(traces)
            emit(dict(kind="capability", area="unfamiliar_coding", id=spec["id"],
                      method="model_tools", category="coding", family=spec.get("family"),
                      complete_correctness=False, **row))


def run_selective_reuse(config, emit, meter, live_runtime=None):
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
        schema = None
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
            retrieved = store.lookup(later["family"], later["request"])
            proposal = propose_retrieved_repair(
                retrieved, later["request"], later["files"], later.get("public") or [],
            )
            template_files = ordinary_template_apply(later["family"], later["files"])
            cache_files = cache.get(later["request"], later["files"])
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
            variants = (
                ("memory", proposal.files if proposal.decision == "apply" else None,
                 proposal.decision, proposal.reason, proposal.requirement, proposal.question),
                ("template", template_files,
                 "apply" if template_files is not None else "miss",
                 "ordinary_template", later.get("family"), None),
                ("model_scratch", scratch.get("final_files"),
                 "scratch", "model_from_scratch", None, None),
            )
            for name, files, decision, reason, requirement, question in variants:
                private = None if files is None else _assess(
                    meter, f"transfer:{later['id']}:{name}", later, files,
                )
                applied = files is not None and name != "model_scratch"
                if name == "model_scratch":
                    applied = bool(scratch.get("public_tests_passed"))
                    label = "scratch_solved" if (private or {}).get("all_passed") else "scratch_failed"
                else:
                    label = reuse_label(
                        later["reuse_role"], decision, files is not None,
                        (private or {}).get("all_passed") if private is not None else None,
                    )
                emit(dict(
                    kind="capability", area="knowledge_reuse", id=later["id"],
                    method=name, category="transfer", family=later["family"],
                    reuse_role=later["reuse_role"],
                    reuse_appropriate=later.get("reuse_appropriate"),
                    decision=decision, reason=reason, requirement=requirement,
                    question=question, used_private_tests=False,
                    private=private, applied=files is not None if name != "model_scratch" else applied,
                    label=label, path=name, complete_correctness=False,
                    **(trace_costs(scratch) if name == "model_scratch" else {}),
                ))
            emit(dict(
                kind="capability", area="knowledge_reuse", id=later["id"],
                method="exact_cache", category="transfer_aux",
                cache_hit=cache_files is not None,
            ))


def run(config, emit, live_runtime=None):
    meter = EventMeter(emit)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
    ))
    run_coding(config, emit, meter, live_runtime)
    run_selective_reuse(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    coding = [row for row in records if row.get("category") == "coding"]
    transfer = [row for row in records if row.get("category") == "transfer"]
    memory = [row for row in transfer if row.get("method") == "memory"]
    template = [row for row in transfer if row.get("method") == "template"]
    scratch = [row for row in transfer if row.get("method") == "model_scratch"]
    labels = Counter(row.get("label") for row in memory)
    template_labels = Counter(row.get("label") for row in template)
    edit = {
        "proposals": 0, "structurally_valid": 0, "invalid": 0,
        "functional_passes": 0, "functional_correctness_separate": True,
    }
    for row in coding:
        stats = row.get("edit_stats") or valid_edit_stats(row.get("model_trace") or [])
        edit["proposals"] += int(stats.get("proposals") or 0)
        edit["structurally_valid"] += int(stats.get("structurally_valid") or 0)
        edit["invalid"] += int(stats.get("invalid") or 0)
        if (row.get("private") or {}).get("all_passed"):
            edit["functional_passes"] += 1
    edit["valid_edit_rate"] = (
        None if not edit["proposals"] else edit["structurally_valid"] / edit["proposals"]
    )
    edit["private_pass_rate"] = None if not coding else edit["functional_passes"] / len(coding)
    costs = {
        "scratch_completions": sum(int(row.get("completions") or 0) for row in scratch),
        "coding_completions": sum(int(row.get("completions") or 0) for row in coding),
        "scratch_input_tokens": sum(int(row.get("input_tokens") or 0) for row in scratch),
        "coding_input_tokens": sum(int(row.get("input_tokens") or 0) for row in coding),
        "scratch_generated_tokens": sum(int(row.get("generated_tokens") or 0) for row in scratch),
        "coding_generated_tokens": sum(int(row.get("generated_tokens") or 0) for row in coding),
    }
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        edit=edit,
        coding=[{
            "id": row["id"], "outcome": row.get("outcome"),
            "public_passed": row.get("public_passed"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "failure_class": row.get("failure_class"),
            "valid_edit_rate": (row.get("edit_stats") or {}).get("valid_edit_rate"),
            "complete_correctness": False,
        } for row in coding],
        memory_counts=dict(
            correct_reuse=labels.get("correct_reuse", 0),
            harmful_reuse=labels.get("harmful_reuse", 0),
            unnecessary_abstention=labels.get("unnecessary_abstention", 0),
            correct_hold=labels.get("correct_hold", 0),
            incorrect_apply=labels.get("incorrect_apply", 0),
        ),
        template_counts=dict(
            correct_reuse=template_labels.get("correct_reuse", 0),
            harmful_reuse=template_labels.get("harmful_reuse", 0),
            unnecessary_abstention=template_labels.get("unnecessary_abstention", 0),
            correct_hold=template_labels.get("correct_hold", 0),
        ),
        transfer=[{
            "id": row["id"], "method": row.get("method"),
            "reuse_role": row.get("reuse_role"),
            "decision": row.get("decision"),
            "requirement": row.get("requirement"),
            "applied": row.get("applied"),
            "label": row.get("label"),
            "private_passed": (row.get("private") or {}).get("all_passed"),
            "question": row.get("question"),
        } for row in transfer],
        scratch_private_passes=sum(1 for row in scratch if (row.get("private") or {}).get("all_passed")),
        costs=costs,
        transfer_rates=transfer_success_rate([
            bool((row.get("private") or {}).get("all_passed"))
            for row in memory if row.get("reuse_role") == "same_repair"
        ]),
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
