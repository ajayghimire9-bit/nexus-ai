"""Sleep-consolidation export for a future Metal LoRA pass.

Reuses ``export_lora_sleep_dataset``. Does not edit
``local_model_runtime.py``. Does not replace RepairSchemaStore.
Baking verified episodes into weights is not learning-to-learn until
an independent holdout beats a frozen baseline.

This host refuses GPU execution: there is no memory-enforcement
backend, and the standing grant is CPU-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .best_of_n_verify import GPU_REFUSED
from .lexicon_vault import export_lora_sleep_dataset


def metal_lora_status() -> dict[str, Any]:
    return dict(
        available=False,
        trainer="mlx-lm",
        device="cpu",
        reason=GPU_REFUSED,
        learning_to_learn=False,
    )


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
    return export_lora_sleep_dataset(path, triples)


def run_metal_lora(
    dataset_path: str | Path,
    *,
    output_dir: str | Path,
    steps: int = 50,
) -> dict[str, Any]:
    """Reserved mlx-lm Metal trainer. This host refuses GPU execution."""
    del dataset_path, output_dir, steps
    raise ValueError(GPU_REFUSED)
