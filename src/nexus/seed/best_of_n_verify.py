"""Best-of-N public-test selection for code and grounded sentences.

Reuses ``assemble_format_proposal``, ``evaluate_python_payload``, and
``verify_composed_response``. Does not edit ``local_model_runtime.py``.
The pinned runtime is temperature=0 with a fixed seed, so four live
``complete`` calls would be identical. This module therefore scores
supplied candidates in the existing CPU sandbox. Metal sampling is
refused until a GPU enforcement backend exists.

Best-of-N is test-time selection. It is not learning-to-learn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_loop_worker import evaluate_python_payload
from .function_format import assemble_format_proposal
from .lexicon_vault import FactSnippet, LexicalCapsule, verify_composed_response


GPU_REFUSED = "gpu_memory_enforcement_backend_unavailable_no_execution"
MAX_CANDIDATES = 4


@dataclass(frozen=True)
class CandidateScore:
    index: int
    raw: str
    public_passed: bool
    public_pass_count: int
    public_n: int
    structurally_valid: bool
    sentence_passed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class BestOfNResult:
    selected: CandidateScore | None
    scores: tuple[CandidateScore, ...]
    first_turn_public_all_passed: bool
    backend: str
    learning_to_learn: bool = False


def metal_sampler_status() -> dict[str, Any]:
    return dict(
        available=False,
        device="cpu",
        reason=GPU_REFUSED,
        pinned_runtime_temperature=0,
        parallel_samples_supported=False,
    )


def sample_metal_candidates(prompt: str, n: int = 4, temperature: float = 0.7) -> list[str]:
    """Reserved Metal path. This host refuses GPU execution."""
    del prompt, n, temperature
    raise ValueError(GPU_REFUSED)


def _public_payload(spec: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return dict(language=spec.get("language") or "python", files=files, cases=spec.get("public") or [])


def score_code_candidates(
    candidates: list[str],
    spec: dict[str, Any],
    plan,
    *,
    fmt: str = "json_body",
) -> BestOfNResult:
    if not candidates or len(candidates) > MAX_CANDIDATES:
        raise ValueError("best_of_n_width")
    scores: list[CandidateScore] = []
    selected: CandidateScore | None = None
    for index, raw in enumerate(candidates):
        assembled = assemble_format_proposal(
            fmt, raw, spec.get("request") or "", spec.get("files") or {}, spec.get("public") or [], plan=plan,
        )
        files = assembled.get("patched_files") or spec.get("files") or {}
        public = {"all_passed": False, "results": []}
        if assembled.get("structurally_valid") and files:
            public = evaluate_python_payload(_public_payload(spec, files))
        results = list(public.get("results") or [])
        passed_n = sum(1 for row in results if row.get("passed"))
        score = CandidateScore(
            index=index,
            raw=raw,
            public_passed=bool(public.get("all_passed")),
            public_pass_count=passed_n,
            public_n=len(results),
            structurally_valid=bool(assembled.get("structurally_valid")),
            sentence_passed=False,
            reasons=(assembled.get("placeholder") or assembled.get("raw_reason") or public.get("reason") or "",),
        )
        scores.append(score)
        if selected is None and score.public_passed:
            selected = score
    return BestOfNResult(
        selected=selected,
        scores=tuple(scores),
        first_turn_public_all_passed=selected is not None,
        backend="cpu_sandbox",
    )


def score_sentence_candidates(
    drafts: list[str],
    *,
    targeted_capsule: LexicalCapsule | None = None,
    retrieved_facts: list[FactSnippet] | None = None,
) -> BestOfNResult:
    if not drafts or len(drafts) > MAX_CANDIDATES:
        raise ValueError("best_of_n_width")
    scores: list[CandidateScore] = []
    selected: CandidateScore | None = None
    for index, draft in enumerate(drafts):
        checked = verify_composed_response(
            draft, targeted_capsule=targeted_capsule, retrieved_facts=retrieved_facts,
        )
        score = CandidateScore(
            index=index,
            raw=draft,
            public_passed=checked.passed,
            public_pass_count=int(checked.passed),
            public_n=1,
            structurally_valid=checked.passed,
            sentence_passed=checked.passed,
            reasons=checked.reasons,
        )
        scores.append(score)
        if selected is None and checked.passed:
            selected = score
    return BestOfNResult(
        selected=selected,
        scores=tuple(scores),
        first_turn_public_all_passed=selected is not None,
        backend="cpu_verifier",
    )
