"""Frozen eligible-always-extract path for the coding workspace.

Acquisition is programmed inspection, not a learned method. Uncertain
contracts ask for clarification. Optional or nullable contracts stay on
the existing coding loop.
"""
from __future__ import annotations

import time
from typing import Any

from .extraction_acquire import acquire_public_contract
from .extraction_contract import (
    extraction_eligible, preview_extraction, yes_no_assembly_eligible,
)
from .extraction_path import generate_extract, with_output_docs
from .extraction_pipelines import generate_extract_assemble
from .constrained_edit import plan_constrained_edit

FROZEN_BASELINE = "eligible_always_extract"


def decide_workspace_extraction(request: str, files: dict[str, str],
                                public_tests: list[dict[str, Any]],
                                docs: list[dict[str, Any]] | None,
                                language: str) -> dict[str, Any]:
    if language != "python":
        return dict(action="delegate", reason="non_python")
    if not public_tests:
        return dict(action="delegate", reason="no_public_tests")
    acquired = acquire_public_contract(request, files, public_tests, docs)
    if acquired.get("asked") or not acquired.get("contract"):
        return dict(
            action="clarify",
            reason="uncertain_contract",
            question=acquired.get("question") or (
                "I need field paths, types and presence before I can extract inputs."
            ),
            acquisition=acquired,
            learned_acquisition=False,
        )
    contract = acquired["contract"]
    if not extraction_eligible(contract):
        return dict(
            action="delegate",
            reason="ineligible_optional_or_nullable",
            acquisition=acquired,
            contract=contract,
            learned_acquisition=False,
        )
    return dict(
        action="extract",
        reason=FROZEN_BASELINE,
        acquisition=acquired,
        contract=contract,
        assemble=yes_no_assembly_eligible(request, contract),
        learned_acquisition=False,
    )


def run_workspace_extraction(runtime, request: str, files: dict[str, str],
                             public_tests: list[dict[str, Any]],
                             docs: list[dict[str, Any]] | None,
                             decision: dict[str, Any]) -> dict[str, Any]:
    if decision.get("action") != "extract":
        raise ValueError("workspace_extraction_not_selected")
    contract = decision["contract"]
    task = dict(
        request=request,
        files=files,
        public=public_tests,
        private=[],
        contract=contract,
        docs=list(docs or []),
    )
    task = with_output_docs(task)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    if decision.get("assemble"):
        result = generate_extract_assemble(runtime, task, clock)
    else:
        result = generate_extract(runtime, task, clock)
    plan = plan_constrained_edit(request, files, public_tests)
    preview = result.get("preview") or preview_extraction(
        plan, "", contract, result.get("current_function") or "",
    )
    mapping = (preview.get("extraction") or {}).get("mapping") or []
    public_passed = bool(result.get("public_passed"))
    return dict(
        outcome_category="solved" if public_passed else "failed",
        public_tests_passed=public_passed,
        complete_correctness=False,
        applied_operator="extract_wrap" if not decision.get("assemble") else "extract_assemble",
        final_diff={plan.path: result.get("current_function") or ""},
        tool_calls=[dict(
            tool_name="local_model_extract",
            outcome_summary=dict(
                status="completed",
                inference_ran=bool(clock["inference_ran"]),
                assumptions=[
                    "Contract acquisition is programmed inspection, not learned.",
                    "Passing public tests is not complete correctness.",
                ],
            ),
        )],
        patch_attempts=[dict(path=result.get("path"))],
        summary_message=(
            "Eligible contract used frozen extraction. "
            + ("Output labels applied by the trusted host wrapper. " if decision.get("assemble") else "")
            + ("Public tests passed." if public_passed else "Public tests failed.")
        ),
        unverified_assumptions=[
            "Passing public tests is not proof of complete correctness.",
            "Contract acquisition is programmed inspection, not learned schema understanding.",
        ],
        preview=preview,
        mapping=mapping,
        generation_path=result.get("path"),
        acquisition=decision.get("acquisition"),
        programmer_supplied_extraction=True,
        learned_schema_understanding=False,
        result=result,
        usage=dict(model_calls=clock["calls"], inference_ran=clock["inference_ran"]),
    )


def present_extraction_coding(card, payload: dict[str, Any]):
    card("Inferred input mapping", dict(
        source="extraction",
        executed=False,
        programmer_supplied=True,
        learned_schema_understanding=False,
        generation_path=payload.get("generation_path"),
        mapping=payload.get("mapping") or [],
        learned_acquisition=False,
    ))
    card("Model proposal", dict(
        source="extraction",
        executed=False,
        status="completed",
        inference_ran=bool((payload.get("usage") or {}).get("inference_ran")),
        assumptions=payload.get("unverified_assumptions") or [],
    ))
    card("Applied workspace edit", dict(
        source="extraction",
        executed=bool(payload.get("final_diff")),
        operator=payload.get("applied_operator"),
        files=sorted(payload.get("final_diff") or {}),
    ))
    card("Public-test outcome", dict(
        source="extraction",
        executed=True,
        outcome=payload.get("outcome_category"),
        public_tests_passed=bool(payload.get("public_tests_passed")),
        complete_correctness=False,
        attempts=len(payload.get("patch_attempts") or []),
        summary=str(payload.get("summary_message") or "")[:400],
    ))
    card("Unverified assumptions", dict(
        assumptions=payload.get("unverified_assumptions") or [],
        executed=False,
    ))
    diffs = payload.get("final_diff") or {}
    card("Final diff", dict(
        executed=bool(diffs),
        files=sorted(diffs),
        diff={key: str(value)[:800] for key, value in list(diffs.items())[:4]},
    ))
    status = "success" if payload.get("outcome_category") == "solved" else "error"
    return (
        f"Extraction finished with `{payload.get('outcome_category')}`: "
        f"{payload.get('summary_message', '')} "
        "Public tests are not a private-test proof.",
        status,
        False,
    )
