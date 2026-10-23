"""Sleep-consolidation export for a future Metal LoRA pass.

Reuses ``export_lora_sleep_dataset``. Does not edit
``local_model_runtime.py``. Does not replace RepairSchemaStore.
Baking verified episodes into weights is not learning-to-learn until
an independent holdout beats a frozen baseline.

Metal LoRA runs only under ``ExplicitMetalGrant(authorized=True)`` and
``MetalGrantEnforcer``. Without that grant the host stays fail-closed.
The Metal ledger is separate from the frozen CPU 3564.568 s ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

from .lexicon_vault import export_lora_sleep_dataset
from .metal_model_runtime import (
    GPU_REFUSED,
    ExplicitMetalGrant,
    MetalGrantEnforcer,
    metal_runtime_status,
    run_metal_lora as execute_metal_lora,
)


def metal_lora_status(grant: ExplicitMetalGrant | None = None) -> dict[str, Any]:
    status = metal_runtime_status(grant)
    status["trainer"] = "mlx-lm"
    status["learning_to_learn"] = False
    return status


def collect_sleep_triples(
    *,
    coding_episodes: Iterable[dict[str, Any]] = (),
    lexicon_episodes: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    triples: list[dict[str, Any]] = []
    for row in coding_episodes:
        if not row.get("passed") and not row.get("public_passed"):
            continue
        triples.append(dict(
            passed=True,
            prompt=row.get("prompt") or row.get("request") or "",
            grounded_context=row.get("grounded_context") or json.dumps(row.get("public") or [], allow_nan=False),
            verified_response=row.get("verified_response") or row.get("body") or "",
        ))
    for row in lexicon_episodes:
        if not row.get("passed"):
            continue
        triples.append(dict(
            passed=True,
            prompt=row["prompt"],
            grounded_context=row["grounded_context"],
            verified_response=row["verified_response"],
        ))
    return triples


def write_sleep_jsonl(path: str | Path, triples: Iterable[dict[str, Any]]) -> int:
    """Write verifier-passing triples only. Failed local drafts stay out."""
    return export_lora_sleep_dataset(path, triples)


def run_metal_lora(
    dataset_path: str | Path,
    *,
    output_dir: str | Path,
    steps: int = 50,
    grant: ExplicitMetalGrant | None = None,
    trainer: Callable[..., dict[str, Any]] | None = None,
    enforcer: MetalGrantEnforcer | None = None,
) -> dict[str, Any]:
    """mlx-lm Metal trainer. Fail-closed unless an explicit grant is passed."""
    return execute_metal_lora(
        dataset_path,
        output_dir=output_dir,
        steps=steps,
        grant=grant,
        trainer=trainer,
        enforcer=enforcer,
    )
