"""Equal-budget independent samples versus error-guided revision.

Both arms may use at most four generation calls. Revision feedback may
name undefined identifiers and public input keys. It must not plant
``.get`` or a finished function body.

This is test-time search, not learning-to-learn.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any, Callable

from .best_of_n_verify import score_code_candidates, score_sentence_candidates
from .chat_template import render_prompt
from .function_format import assemble_format_proposal, prompt_for_format
from .lexicon_vault import verify_composed_response
from .metal_model_runtime import metal_candidate_schedule
from .agent_loop_worker import evaluate_python_payload


NAMEERROR = re.compile(r"NameError:\s*name '([^']+)' is not defined")
PLANTED = (".get",)


def public_input_keys(spec: dict[str, Any]) -> list[str]:
    keys: set[str] = set()
    for case in spec.get("public") or []:
        payload = case.get("input") or {}
        if isinstance(payload, dict):
            keys.update(payload)
    return sorted(keys)


def undefined_names(public_eval: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for row in public_eval.get("results") or []:
        error = str(row.get("error") or "")
        found.extend(NAMEERROR.findall(error))
    return sorted(set(found))


def bare_loaded_names(raw: str) -> set[str]:
    try:
        payload = json.loads(raw)
        body = payload.get("body") if isinstance(payload, dict) else raw
        tree = ast.parse(body or "")
    except (json.JSONDecodeError, SyntaxError, TypeError, ValueError):
        return set()
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def code_error_feedback(
    public_eval: dict[str, Any],
    spec: dict[str, Any],
    raw: str | None = None,
) -> dict[str, Any]:
    """Explain the failure without supplying the completed function."""
    raised = set(undefined_names(public_eval))
    keys = public_input_keys(spec)
    if raw:
        raised |= bare_loaded_names(raw) & set(keys)
    raised.discard("item")
    feedback = dict(
        undefined_names=sorted(raised),
        public_input_keys=keys,
        instruction=(
            "Those undefined names are not bare variables. They are keys on "
            "the public input mapping passed as item."
        ),
    )
    _reject_planted(json.dumps(feedback, allow_nan=False), spec)
    return feedback


def _reject_planted(text: str, spec: dict[str, Any] | None = None) -> None:
    if any(token in text for token in PLANTED):
        raise ValueError("planted_solution_in_feedback")
    if spec is None:
        return
    for key in public_input_keys(spec):
        if f"if '{key}' in item" in text or f'if "{key}" in item' in text:
            raise ValueError("planted_solution_in_feedback")


def evaluate_code_raw(raw: str, spec: dict[str, Any], plan, fmt: str = "json_body") -> dict[str, Any]:
    assembled = assemble_format_proposal(
        fmt, raw, spec.get("request") or "", spec.get("files") or {}, spec.get("public") or [], plan=plan,
    )
    files = assembled.get("patched_files") or spec.get("files") or {}
    if not assembled.get("structurally_valid") or not files:
        return dict(all_passed=False, results=[], reason=assembled.get("placeholder") or "structurally_invalid")
    return evaluate_python_payload(dict(language="python", files=files, cases=spec.get("public") or []))


def revision_code_prompt(task, plan, feedback: dict[str, Any], style: str = "chatml") -> str:
    user = prompt_for_format("json_body", task, plan, feedback)
    _reject_planted(user, spec=None)
    if ".get" in user:
        raise ValueError("planted_get_in_prompt")
    rendered, _meta = render_prompt(style, user)
    return rendered


def run_independent_code(
    sampler: Callable,
    prompt: str,
    spec: dict[str, Any],
    plan,
    *,
    seed: int = 42,
    k: int = 4,
):
    schedules = metal_candidate_schedule(k, seed)
    raws = [sampler(prompt, row) for row in schedules]
    scored = score_code_candidates(raws, spec, plan)
    return dict(
        arm="independent",
        n_calls=len(raws),
        budget=k,
        candidates=raws,
        selected_index=None if scored.selected is None else scored.selected.index,
        public_passed=bool(scored.selected and scored.selected.public_passed),
        unique_outputs=len(set(raws)),
        schedule=[dict(index=row.index, temperature=row.temperature, seed=row.seed) for row in schedules],
    )


def run_revision_code(
    sampler: Callable,
    initial_prompt: str,
    spec: dict[str, Any],
    plan,
    task,
    *,
    seed: int = 42,
    k: int = 4,
    style: str = "chatml",
):
    schedules = metal_candidate_schedule(k, seed)
    raws: list[str] = []
    feedbacks: list[dict[str, Any]] = []
    prompt = initial_prompt
    selected_index = None
    for row in schedules:
        raw = sampler(prompt, row)
        raws.append(raw)
        public = evaluate_code_raw(raw, spec, plan)
        if public.get("all_passed"):
            selected_index = row.index
            break
        feedback = code_error_feedback(public, spec, raw)
        feedbacks.append(feedback)
        prompt = revision_code_prompt(task, plan, feedback, style=style)
    scored = score_code_candidates(raws, spec, plan)
    return dict(
        arm="revision",
        n_calls=len(raws),
        budget=k,
        candidates=raws,
        feedbacks=feedbacks,
        selected_index=None if scored.selected is None else scored.selected.index,
        public_passed=bool(scored.selected and scored.selected.public_passed),
        schedule=[dict(index=row.index, temperature=row.temperature, seed=row.seed) for row in schedules[: len(raws)]],
        planted_solution=False,
        unique_outputs=len(set(raws)),
    )


def sentence_error_feedback(checked) -> dict[str, Any]:
    return dict(reasons=list(checked.reasons), instruction="Keep the required term, required tokens, and [doc_id] citation.")


def run_revision_sentence(
    sampler: Callable,
    initial_prompt: str,
    *,
    targeted_capsule,
    retrieved_facts,
    vault=None,
    seed: int = 42,
    k: int = 4,
):
    schedules = metal_candidate_schedule(k, seed)
    drafts: list[str] = []
    prompt = initial_prompt
    for row in schedules:
        draft = sampler(prompt, row)
        drafts.append(draft)
        checked = verify_composed_response(
            draft, targeted_capsule=targeted_capsule, retrieved_facts=retrieved_facts, vault=vault,
        )
        if checked.passed:
            break
        extra = json.dumps(sentence_error_feedback(checked), allow_nan=False)
        prompt = initial_prompt + "\nVerifier feedback:\n" + extra + "\n"
    scored = score_sentence_candidates(
        drafts, targeted_capsule=targeted_capsule, retrieved_facts=retrieved_facts, vault=vault,
    )
    return dict(
        arm="revision",
        n_calls=len(drafts),
        budget=k,
        candidates=drafts,
        selected_index=None if scored.selected is None else scored.selected.index,
        sentence_passed=bool(scored.selected and scored.selected.sentence_passed),
        unique_outputs=len(set(drafts)),
    )


def run_independent_sentence(
    sampler: Callable,
    prompt: str,
    *,
    targeted_capsule,
    retrieved_facts,
    vault=None,
    seed: int = 42,
    k: int = 4,
):
    schedules = metal_candidate_schedule(k, seed)
    drafts = [sampler(prompt, row) for row in schedules]
    scored = score_sentence_candidates(
        drafts, targeted_capsule=targeted_capsule, retrieved_facts=retrieved_facts, vault=vault,
    )
    return dict(
        arm="independent",
        n_calls=len(drafts),
        budget=k,
        candidates=drafts,
        selected_index=None if scored.selected is None else scored.selected.index,
        sentence_passed=bool(scored.selected and scored.selected.sentence_passed),
        unique_outputs=len(set(drafts)),
        schedule=[dict(index=row.index, temperature=row.temperature, seed=row.seed) for row in schedules],
    )
