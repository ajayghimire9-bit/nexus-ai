"""Client-side Metal sampling audit. Not a new capability benchmark.

Records the posted /completion fields. Identical model texts do not
prove that temperature or seed were dropped.
"""
from __future__ import annotations

from typing import Any

from .local_model_runtime import RuntimeConfig
from .metal_model_runtime import (
    ExplicitMetalGrant,
    PersistentMetalRuntime,
    audit_request_log,
    bind_live_metal_sampler,
    metal_candidate_schedule,
    sample_metal_candidates,
)


AUDIT_PROMPT = "Reply with exactly one color word: red, blue, green, or gold."


def build_audit_runtime(model_path: str, grant: ExplicitMetalGrant) -> PersistentMetalRuntime:
    return PersistentMetalRuntime(
        RuntimeConfig(
            model_path,
            max_tokens=16,
            application_cache=False,
            prompt_cache=False,
            request_timeout_s=8,
            startup_timeout_s=25,
            threads=2,
        ),
        grant,
    )


def run_sampling_audit(
    *,
    grant: ExplicitMetalGrant,
    sampler,
    enforcer,
    prompt: str = AUDIT_PROMPT,
    k: int = 4,
) -> dict[str, Any]:
    texts = sample_metal_candidates(prompt, n=k, grant=grant, sampler=sampler, enforcer=enforcer)
    runtime = getattr(sampler, "runtime", None)
    records = list(getattr(runtime, "request_log", []) or [])
    if not records:
        records = [
            dict(
                temperature=plan.temperature,
                seed=plan.seed,
                content=text,
                payload_sha256=f"{plan.temperature}:{plan.seed}",
                application_cache_consulted=False,
                cache_prompt=False,
                n_gpu_layers=plan.n_gpu_layers,
            )
            for plan, text in zip(metal_candidate_schedule(k, grant.seed), texts)
        ]
    audit = audit_request_log(records)
    return dict(
        prompt=prompt,
        texts=texts,
        requests=records,
        audit=audit,
        application_cache=False,
        grant_includes="MetalGrantEnforcer.guarded_call wall only",
        process_rss_is_not_metal_heap=True,
        identical_drafts_do_not_prove_sampler_bug=True,
        learning_to_learn=False,
    )


def bind_audited_sampler(runtime: PersistentMetalRuntime, schema=None):
    sampler = bind_live_metal_sampler(runtime, schema)
    sampler.runtime = runtime
    return sampler
