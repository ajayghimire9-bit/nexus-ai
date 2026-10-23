"""Development diagnostic: current local coder vs a stronger local coder.

Same corrected interface on four small families: field access, missing
values, aggregation, and simple composition. Compare task success,
assistant-cost latency, and process RSS. Parameter count is not the
metric. A missing stronger GGUF is BLOCKED, not a win for the 1.5B.

Vault storage is not an acquired-knowledge benefit. That comparison is
a later study: relevant vs none vs irrelevant stored facts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .constrained_edit import plan_constrained_edit
from .function_format import assemble_format_proposal
from .metal_best_of_4_smoke import LOCAL_RUNTIME_SHA256
from .metal_live_compare import AssistantCost
from .metal_model_runtime import local_runtime_sha256
from .agent_loop_worker import evaluate_python_payload


FAMILIES = ("field_access", "missing_values", "aggregation", "composition")


def load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_task(task: dict[str, Any], raw: str, fmt: str = "json_body") -> dict[str, Any]:
    plan = plan_constrained_edit(task["request"], task["files"], task["public"])
    assembled = assemble_format_proposal(
        fmt, raw, task["request"], task["files"], task["public"], plan=plan,
    )
    files = assembled.get("patched_files") or task["files"]
    public = {"all_passed": False, "results": []}
    private = {"all_passed": False, "results": []}
    if assembled.get("structurally_valid") and files:
        public = evaluate_python_payload(dict(language="python", files=files, cases=task["public"]))
        private = evaluate_python_payload(dict(language="python", files=files, cases=task["private"]))
    return dict(
        family=task["family"],
        structurally_valid=bool(assembled.get("structurally_valid")),
        public_passed=bool(public.get("all_passed")),
        private_passed=bool(private.get("all_passed")),
        raw=raw,
    )


def summarize(records: list[dict[str, Any]], clock: AssistantCost, *, stronger_blocked: bool) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        by_model.setdefault(row["model"], []).append(row)
    models = {}
    for name, rows in by_model.items():
        models[name] = dict(
            n=len(rows),
            public_passed=sum(int(row["public_passed"]) for row in rows),
            private_passed=sum(int(row["private_passed"]) for row in rows),
            families=[row["family"] for row in rows],
        )
    return dict(
        models=models,
        stronger_blocked=stronger_blocked,
        comparison_established=bool(models) and not stronger_blocked and len(models) == 2,
        assistant_cost=clock.as_dict(),
        local_model_runtime_unchanged=local_runtime_sha256() == LOCAL_RUNTIME_SHA256,
        metric_is_not_parameter_count=True,
        vault_retention_is_not_acquired_knowledge=True,
        knowledge_conditions_later=("relevant", "none", "irrelevant"),
        learning_to_learn=False,
    )


def run_supplied(
    config: dict[str, Any],
    proposals: dict[str, dict[str, str]],
    clock: AssistantCost | None = None,
) -> list[dict[str, Any]]:
    """Offline path: score supplied bodies. Live sampling is a later runner."""
    del clock
    records = []
    for model, bodies in proposals.items():
        for task in config["tasks"]:
            raw = bodies[task["family"]]
            scored = score_task(task, raw, config.get("format") or "json_body")
            scored["model"] = model
            records.append(scored)
    return records
