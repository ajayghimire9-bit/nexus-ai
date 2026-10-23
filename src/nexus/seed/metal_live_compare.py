"""Frozen live independent-vs-revision comparison with full assistant cost.

Stubbed call-2 versus call-4 results prove control flow only. Live
success is independently rechecked from saved candidates. Does not
edit ``local_model_runtime.py``. Does not debit the frozen CPU ledger.
Not learning-to-learn.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .function_format import prompt_for_format
from .lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from .metal_best_of_4_smoke import (
    CODER15_SHA256, LOCAL_RUNTIME_SHA256, SmokeTask, private_eval,
)
from .metal_model_runtime import (
    CPU_LEDGER_USED_S,
    ExplicitMetalGrant,
    MetalGrantEnforcer,
    PersistentMetalRuntime,
    bind_live_metal_sampler,
    load_metal_ledger,
    local_runtime_sha256,
)
from .metal_revision_compare import (
    run_independent_code, run_independent_sentence, run_revision_code,
    run_revision_sentence,
)
from .local_model_runtime import RuntimeConfig, file_hash


@dataclass
class AssistantCost:
    """User-facing cost. Grant accounting stays guarded_call only."""

    startup_s: float = 0.0
    inference_s: float = 0.0
    retrieval_s: float = 0.0
    execution_s: float = 0.0
    verification_s: float = 0.0
    teardown_s: float = 0.0
    grant_charged_s: float = 0.0
    input_tokens: int = 0
    generated_tokens: int = 0

    def accounted_s(self) -> float:
        return (
            self.startup_s + self.inference_s + self.retrieval_s
            + self.execution_s + self.verification_s + self.teardown_s
        )

    def as_dict(self, runner_wall_s: float | None = None) -> dict[str, Any]:
        data = asdict(self)
        accounted = self.accounted_s()
        data["accounted_s"] = round(accounted, 6)
        data["user_total_s"] = round(runner_wall_s if runner_wall_s is not None else accounted, 6)
        if runner_wall_s is not None:
            data["unallocated_s"] = round(max(0.0, runner_wall_s - accounted), 6)
        data["grant_includes"] = "MetalGrantEnforcer.guarded_call wall only"
        data["process_rss_is_not_metal_heap"] = True
        data["user_total_is_complete_assistant_cost"] = True
        return data


def load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def grant_from_config(config: dict[str, Any], *, ledger_path: str) -> ExplicitMetalGrant:
    data = dict(config["metal_grant"])
    data["ledger_path"] = ledger_path
    return ExplicitMetalGrant.from_config(data, env={})


def code_spec(config: dict[str, Any]) -> dict[str, Any]:
    cell = config["code"]
    return dict(
        id=cell["id"],
        language="python",
        request=cell["request"],
        files=dict(cell["files"]),
        public=list(cell["public"]),
        private=list(cell["private"]),
    )


def code_prompt(config: dict[str, Any]) -> tuple[str, Any, SmokeTask]:
    spec = code_spec(config)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    task = SmokeTask(spec["request"], spec["public"], [])
    user = prompt_for_format(config["format"], task, plan, None)
    if ".get" in user:
        raise ValueError("planted_get_in_prompt")
    rendered, _meta = render_prompt(config["prompt_style"], user)
    return rendered, plan, task


def sentence_prompt(config: dict[str, Any]) -> str:
    cell = config["sentence"]
    user = (
        f"Write one complete English sentence that uses the word {cell['term']}, "
        f"includes the tokens {', '.join(cell['required_tokens'])}, ends with a period, "
        f"and cites [{cell['doc_id']}]. Use only numbers that appear in the fact. "
        f"Reply with the sentence only.\n"
        f"Fact [{cell['doc_id']}]: {cell['fact']}\n"
        f"Term: {cell['term']} — {cell['definition']}\n"
    )
    if ".get" in user:
        raise ValueError("planted_get_in_prompt")
    rendered, _meta = render_prompt(config["prompt_style"], user)
    return rendered


def timed(clock: AssistantCost, field: str, fn: Callable):
    started = time.perf_counter()
    try:
        return fn()
    finally:
        setattr(clock, field, getattr(clock, field) + (time.perf_counter() - started))


def recording_sampler(inner: Callable, clock: AssistantCost) -> Callable:
    def sampler(prompt, plan):
        started = time.perf_counter()
        try:
            return inner(prompt, plan)
        finally:
            clock.inference_s += time.perf_counter() - started

    sampler.runtime = getattr(inner, "runtime", None)
    return sampler


def pull_token_counts(runtime) -> tuple[int, int]:
    logs = list(getattr(runtime, "request_log", []) or [])
    inp = sum(int((row.get("telemetry") or {}).get("input_tokens") or 0) for row in logs)
    gen = sum(int((row.get("telemetry") or {}).get("generated_tokens") or 0) for row in logs)
    return inp, gen


def run_comparison(
    config: dict[str, Any],
    directory: Path,
    *,
    grant: ExplicitMetalGrant,
    code_sampler: Callable,
    sentence_sampler: Callable,
    enforcer: MetalGrantEnforcer,
    clock: AssistantCost,
) -> list[dict[str, Any]]:
    spec = code_spec(config)
    rendered, plan, task = code_prompt(config)
    k = int(config["k"])
    seed = grant.seed
    code_rec = recording_sampler(code_sampler, clock)
    sent_rec = recording_sampler(sentence_sampler, clock)

    def independent_code():
        return run_independent_code(code_rec, rendered, spec, plan, seed=seed, k=k)

    def revision_code():
        return run_revision_code(code_rec, rendered, spec, plan, task, seed=seed, k=k)

    ind_code = enforcer.guarded_call(independent_code)
    rev_code = enforcer.guarded_call(revision_code)
    merged = dict(config)
    merged["cell1"] = config["code"]
    for row in (ind_code, rev_code):
        if row.get("public_passed") and row.get("selected_index") is not None:
            raw = row["candidates"][row["selected_index"]]
            row["private"] = timed(clock, "execution_s", lambda r=raw: private_eval(merged, r, plan))
        else:
            row["private"] = None

    cell = config["sentence"]
    vault = KnowledgeVault(directory / "vault.sqlite")
    store = LexicalCapsuleStore(directory / "capsules.sqlite")

    def ingest_and_retrieve():
        vault.ingest_document(cell["doc_id"], cell["title"], cell["fact"])
        capsule = store.ingest_new_term(
            cell["term"], cell["definition"], cell["pos_or_frame"],
            required_tokens=cell["required_tokens"],
        )
        facts = vault.retrieve_grounded_facts(cell["retrieve_query"])
        return capsule, facts

    capsule, facts = timed(clock, "retrieval_s", ingest_and_retrieve)
    prompt = sentence_prompt(config)

    def independent_sentence():
        return run_independent_sentence(
            sent_rec, prompt, targeted_capsule=capsule, retrieved_facts=facts, vault=vault, seed=seed, k=k,
        )

    def revision_sentence():
        return run_revision_sentence(
            sent_rec, prompt, targeted_capsule=capsule, retrieved_facts=facts, vault=vault, seed=seed, k=k,
        )

    ind_sent = enforcer.guarded_call(independent_sentence)
    rev_sent = enforcer.guarded_call(revision_sentence)
    vault.close()
    store.close()
    return [
        dict(kind="code_independent", prompt=rendered, **ind_code),
        dict(kind="code_revision", prompt=rendered, **rev_code),
        dict(kind="sentence_independent", prompt=prompt, doc_id=cell["doc_id"], **ind_sent),
        dict(kind="sentence_revision", prompt=prompt, doc_id=cell["doc_id"], **rev_sent),
    ]


def summarize(
    records: list[dict[str, Any]],
    ledger: dict[str, Any],
    clock: AssistantCost,
    runner_wall_s: float = 0.0,
) -> dict[str, Any]:
    by_kind = {row["kind"]: row for row in records}
    return dict(
        code_independent_calls=by_kind["code_independent"]["n_calls"],
        code_revision_calls=by_kind["code_revision"]["n_calls"],
        code_independent_unique=by_kind["code_independent"]["unique_outputs"],
        code_revision_unique=by_kind["code_revision"]["unique_outputs"],
        code_independent_public=by_kind["code_independent"]["public_passed"],
        code_revision_public=by_kind["code_revision"]["public_passed"],
        code_independent_private=bool((by_kind["code_independent"].get("private") or {}).get("all_passed")),
        code_revision_private=bool((by_kind["code_revision"].get("private") or {}).get("all_passed")),
        sentence_independent_calls=by_kind["sentence_independent"]["n_calls"],
        sentence_revision_calls=by_kind["sentence_revision"]["n_calls"],
        sentence_independent_unique=by_kind["sentence_independent"]["unique_outputs"],
        sentence_revision_unique=by_kind["sentence_revision"]["unique_outputs"],
        sentence_independent_passed=by_kind["sentence_independent"]["sentence_passed"],
        sentence_revision_passed=by_kind["sentence_revision"]["sentence_passed"],
        stubbed_call2_vs_call4_is_not_live_advantage=True,
        live_advantage_claimed=False,
        metal_used_s=ledger.get("used_s"),
        metal_peak_rss_mib=ledger.get("peak_rss_mib"),
        assistant_cost=clock.as_dict(runner_wall_s),
        cpu_ledger_used_s=CPU_LEDGER_USED_S,
        cpu_ledger_debit_s=0,
        local_model_runtime_unchanged=local_runtime_sha256() == LOCAL_RUNTIME_SHA256,
        learning_to_learn=False,
        confirmation=False,
    )


def start_live_runtime(config: dict[str, Any], grant: ExplicitMetalGrant):
    spec = config["model"]
    model = Path(spec["path"])
    if not model.is_file():
        return None, "BLOCKED_MISSING_MODEL", None
    if file_hash(model) != spec["sha256"]:
        raise ValueError("frozen_model_hash_mismatch:" + spec["label"])
    if spec["sha256"] != CODER15_SHA256:
        raise ValueError("unexpected_coder_hash")
    runtime = PersistentMetalRuntime(
        RuntimeConfig(
            str(model),
            max_tokens=int(config.get("max_tokens") or 128),
            application_cache=False,
            prompt_cache=False,
            request_timeout_s=float(config.get("request_timeout_s") or 8),
            startup_timeout_s=float(config.get("startup_timeout_s") or 25),
            threads=int(config.get("threads") or 2),
        ),
        grant,
    )
    return runtime, None, runtime.start()
