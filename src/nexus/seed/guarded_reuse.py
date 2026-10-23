"""Fresh-case repair reuse against an equally guarded ordinary template."""
from __future__ import annotations

from collections import Counter
import tempfile
from pathlib import Path
from unittest.mock import patch

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .interrupt_transfer import _assess, _view
from .repair_schema_memory import (
    RepairSchemaStore, capture_from_success, propose_guarded_template,
    propose_retrieved_repair, transfer_success_rate,
)
from .scoped_id_staging import trace_costs
from .selective_reuse import reuse_label
from .symbiotic_agent_loop import SymbioticAgentLoop


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit",
}


def run_guarded_reuse(config, emit, meter, live_runtime=None):
    budget = int(config.get("coding_budget_steps", 4))
    later_ids = {row["id"] for row in config["transfer"]["later"]}
    if later_ids & CLOSED_TASK_IDS or config["transfer"]["source"]["id"] in CLOSED_TASK_IDS:
        raise ValueError("closed_task_id_reused")
    with tempfile.TemporaryDirectory() as tmp:
        store = RepairSchemaStore()
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
            emit(dict(kind="capability", area="knowledge_reuse", id=source["id"],
                      method="source_ast", category="transfer_source",
                      public_passed=True, genuine_source_acquisition=schema is not None,
                      transformation=getattr(schema, "transformation", None),
                      from_op=getattr(schema, "applicability", {}).get("from_op") if schema else None,
                      to_op=getattr(schema, "applicability", {}).get("to_op") if schema else None))
        else:
            emit(dict(kind="capability", area="knowledge_reuse", id=source["id"],
                      method="source_ast", category="transfer_source",
                      public_passed=False, genuine_source_acquisition=False))
        for later in config["transfer"]["later"]:
            retrieved = store.lookup(later["family"], later["request"])
            memory = propose_retrieved_repair(
                retrieved, later["request"], later["files"], later.get("public") or [],
            )
            template = propose_guarded_template(
                later["family"], later["request"], later["files"], later.get("public") or [],
            )
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
                ("memory", memory),
                ("template", template),
            )
            for name, proposal in variants:
                files = proposal.files if proposal.decision == "apply" else None
                private = None if files is None else _assess(
                    meter, f"transfer:{later['id']}:{name}", later, files,
                )
                emit(dict(
                    kind="capability", area="knowledge_reuse", id=later["id"],
                    method=name, category="transfer", family=later["family"],
                    reuse_role=later["reuse_role"],
                    reuse_appropriate=later.get("reuse_appropriate"),
                    decision=proposal.decision, reason=proposal.reason,
                    requirement=proposal.requirement, question=proposal.question,
                    used_private_tests=False, private=private,
                    applied=files is not None, path=name, complete_correctness=False,
                    label=reuse_label(
                        later["reuse_role"], proposal.decision, files is not None,
                        (private or {}).get("all_passed") if private is not None else None,
                    ),
                    equally_guarded=True,
                ))
            private = _assess(
                meter, f"transfer:{later['id']}:model_scratch", later,
                scratch.get("final_files") or later["files"],
            )
            emit(dict(
                kind="capability", area="knowledge_reuse", id=later["id"],
                method="model_scratch", category="transfer", family=later["family"],
                reuse_role=later["reuse_role"],
                reuse_appropriate=later.get("reuse_appropriate"),
                decision="scratch", reason="model_from_scratch",
                requirement=None, question=None, used_private_tests=False,
                private=private, applied=bool(scratch.get("public_tests_passed")),
                path="model_scratch", complete_correctness=False,
                label="scratch_solved" if (private or {}).get("all_passed") else "scratch_failed",
                equally_guarded=True, **trace_costs(scratch),
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
    run_guarded_reuse(config, emit, meter, live_runtime)
    return meter


def summarize(records, config):
    transfer = [row for row in records if row.get("category") == "transfer"]
    memory = [row for row in transfer if row.get("method") == "memory"]
    template = [row for row in transfer if row.get("method") == "template"]
    scratch = [row for row in transfer if row.get("method") == "model_scratch"]
    memory_labels = Counter(row.get("label") for row in memory)
    template_labels = Counter(row.get("label") for row in template)
    same = [row for row in memory if row.get("reuse_role") == "same_repair"]
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_policy_promoted=False,
        equally_guarded_template=True,
        memory_counts=dict(
            correct_reuse=memory_labels.get("correct_reuse", 0),
            harmful_reuse=memory_labels.get("harmful_reuse", 0),
            unnecessary_abstention=memory_labels.get("unnecessary_abstention", 0),
            correct_hold=memory_labels.get("correct_hold", 0),
            incorrect_apply=memory_labels.get("incorrect_apply", 0),
        ),
        template_counts=dict(
            correct_reuse=template_labels.get("correct_reuse", 0),
            harmful_reuse=template_labels.get("harmful_reuse", 0),
            unnecessary_abstention=template_labels.get("unnecessary_abstention", 0),
            correct_hold=template_labels.get("correct_hold", 0),
            incorrect_apply=template_labels.get("incorrect_apply", 0),
        ),
        memory_advantage_correct_reuse=(
            memory_labels.get("correct_reuse", 0) - template_labels.get("correct_reuse", 0)
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
        costs=dict(
            scratch_completions=sum(int(row.get("completions") or 0) for row in scratch),
            scratch_input_tokens=sum(int(row.get("input_tokens") or 0) for row in scratch),
            scratch_generated_tokens=sum(int(row.get("generated_tokens") or 0) for row in scratch),
        ),
        transfer_rates=transfer_success_rate([
            bool((row.get("private") or {}).get("all_passed")) for row in same
        ]),
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
