"""Locked source / development / assessment mechanism splits.

C is a new mechanism in a source family, not a renamed seed of a source task.
D compositions are in the language and absent from source.
E is outside the language. Names and input rows alone are not the split.
"""
from __future__ import annotations

from typing import Any

from .mechanism_world import EXCLUDED, LANGUAGE, OUTSIDE_LANGUAGE

# A source, B development, C within-family, D composition, E excluded family.
DECLARED = (
    dict(task_id="src_add1_a", split="source", family="stateless", mechanism="add1", instance_seed=11),
    dict(task_id="src_add1_b", split="source", family="stateless", mechanism="add1", instance_seed=12),
    dict(task_id="src_add2_a", split="source", family="stateless", mechanism="add2", instance_seed=21),
    dict(task_id="src_add2_b", split="source", family="stateless", mechanism="add2", instance_seed=22),
    dict(task_id="src_mul2_a", split="source", family="stateless", mechanism="mul2", instance_seed=31),
    dict(task_id="src_mul2_b", split="source", family="stateless", mechanism="mul2", instance_seed=32),
    dict(task_id="src_count_a", split="source", family="stateful", mechanism="count", instance_seed=41),
    dict(task_id="src_count_b", split="source", family="stateful", mechanism="count", instance_seed=42),
    dict(task_id="src_sum_a", split="source", family="stateful", mechanism="sum", instance_seed=51),
    dict(task_id="src_sum_b", split="source", family="stateful", mechanism="sum", instance_seed=52),
    dict(task_id="src_noisy_a", split="source", family="noisy", mechanism="noisy_add1", instance_seed=61),
    dict(task_id="src_noisy_b", split="source", family="noisy", mechanism="noisy_add1", instance_seed=62),
    dict(task_id="src_const7", split="source", family="unresolved", mechanism="const7", instance_seed=65),
    dict(task_id="src_const0", split="source", family="unresolved", mechanism="const0", instance_seed=66),
    dict(task_id="dev_add3", split="development", family="stateless", mechanism="add3", instance_seed=71),
    dict(task_id="dev_neg", split="development", family="stateless", mechanism="neg", instance_seed=72),
    dict(task_id="dev_toggle", split="development", family="stateful", mechanism="toggle", instance_seed=73),
    dict(task_id="dev_sum", split="development", family="stateful", mechanism="sum", instance_seed=74),
    dict(task_id="dev_noisy", split="development", family="noisy", mechanism="noisy_add1", instance_seed=75),
    dict(task_id="dev_add2", split="development", family="stateless", mechanism="add2", instance_seed=76),
    dict(task_id="dev_const7", split="development", family="unresolved", mechanism="const7", instance_seed=77),
    dict(task_id="c_add4", split="within_family", family="stateless", mechanism="add4", instance_seed=81),
    dict(task_id="c_count2", split="within_family", family="stateful", mechanism="count2", instance_seed=82),
    dict(task_id="d_add_mul", split="composition", family="composition", mechanism="add1_then_mul2", instance_seed=91),
    dict(task_id="d_count_add", split="composition", family="composition", mechanism="count_then_add1", instance_seed=92),
    dict(task_id="e_delay", split="excluded_family", family="excluded", mechanism="delay", instance_seed=101),
    dict(task_id="e_threshold", split="excluded_family", family="excluded", mechanism="threshold", instance_seed=102),
)


def catalogue() -> list[dict[str, Any]]:
    rows = []
    for raw in DECLARED:
        if raw["mechanism"] in LANGUAGE:
            if raw["split"] == "excluded_family":
                raise ValueError("excluded_must_be_outside:" + raw["task_id"])
        elif raw["mechanism"] not in OUTSIDE_LANGUAGE:
            raise ValueError("unknown_mechanism:" + raw["task_id"])
        elif raw["split"] == "excluded_family" and raw["mechanism"] not in EXCLUDED:
            raise ValueError("excluded_must_be_declared:" + raw["task_id"])
        elif raw["split"] in ("within_family", "composition") and raw["mechanism"] not in LANGUAGE:
            raise ValueError("heldout_in_family_must_be_in_language:" + raw["task_id"])
        rows.append(dict(raw, origin="authored_mechanism"))
    return rows


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] == split]


def assessment_tasks() -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] in ("within_family", "composition", "excluded_family")]


def split_lock() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in catalogue():
        out.setdefault(row["split"], []).append(row["task_id"])
    return out
