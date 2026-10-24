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
    dict(task_id="mm_abs", split="mismatch", family="mismatch", mechanism="abs_val", instance_seed=201),
    dict(task_id="mm_mod3", split="mismatch", family="mismatch", mechanism="mod3", instance_seed=202),
    dict(task_id="mm_clip0", split="mismatch", family="mismatch", mechanism="clip0", instance_seed=203),
    dict(task_id="mm_prev", split="mismatch", family="mismatch", mechanism="prev_plus", instance_seed=204),
    dict(task_id="ctl_neg", split="mismatch_control", family="stateless", mechanism="neg", instance_seed=211),
    dict(task_id="ctl_toggle", split="mismatch_control", family="stateful", mechanism="toggle", instance_seed=212),
    dict(task_id="vp_id0", split="varied_measure", family="measure_exposed", mechanism="id_exact0", instance_seed=301),
    dict(task_id="vp_mod2", split="varied_sequence", family="sequence_exposed", mechanism="mod2", instance_seed=302),
    dict(task_id="vp_plus", split="varied_sequence", family="sequence_exposed", mechanism="plus_prev", instance_seed=303),
    dict(task_id="vp_twin", split="varied_indistinct", family="indistinguishable", mechanism="add1_twin", instance_seed=304),
    dict(task_id="vp_add2", split="varied_ordinary", family="stateless", mechanism="add2", instance_seed=311),
    dict(task_id="vp_neg", split="varied_ordinary", family="stateless", mechanism="neg", instance_seed=312),
    dict(task_id="vp_count", split="varied_ordinary", family="stateful", mechanism="count", instance_seed=313),
    dict(task_id="acq_src_add1", split="synthesis_source", family="primitive", mechanism="add1", instance_seed=401),
    dict(task_id="acq_src_add2", split="synthesis_source", family="primitive", mechanism="add2", instance_seed=402),
    dict(task_id="acq_src_mul2", split="synthesis_source", family="primitive", mechanism="mul2", instance_seed=403),
    dict(task_id="acq_src_neg", split="synthesis_source", family="primitive", mechanism="neg", instance_seed=404),
    dict(task_id="acq_gate_mul_add", split="synthesis_gate", family="unstored", mechanism="mul2_then_add1", instance_seed=411),
    dict(task_id="acq_gate_add_neg", split="synthesis_gate", family="unstored", mechanism="add1_then_neg", instance_seed=412),
    dict(task_id="acq_gate_neg_add", split="synthesis_gate", family="unstored", mechanism="neg_then_add1", instance_seed=413),
    dict(task_id="acq_hold_add2_mul", split="synthesis_holdout", family="unstored", mechanism="add2_then_mul2", instance_seed=421),
    dict(task_id="acq_hold_neg_add2", split="synthesis_holdout", family="unstored", mechanism="neg_then_add2", instance_seed=422),
    dict(task_id="acq_hold_mul_neg", split="synthesis_holdout", family="unstored", mechanism="mul2_then_neg", instance_seed=423),
    dict(task_id="w1_add1", split="wave1_source", family="affine", mechanism="add1", instance_seed=501, role="acquire"),
    dict(task_id="w1_mul2", split="wave1_source", family="affine", mechanism="mul2", instance_seed=502, role="acquire"),
    dict(task_id="w1_if_pos", split="wave1_source", family="gate", mechanism="if_pos", instance_seed=503, role="acquire"),
    dict(task_id="w1_sat_inc", split="wave1_source", family="state", mechanism="sat_inc", instance_seed=504, role="acquire"),
    dict(task_id="w1d_add2", split="wave1_dev", family="affine", mechanism="add2", instance_seed=511, role="acquire"),
    dict(task_id="w1d_neg", split="wave1_dev", family="affine", mechanism="neg", instance_seed=512, role="acquire"),
    dict(task_id="w1d_if_neg", split="wave1_dev", family="gate", mechanism="if_neg", instance_seed=513, role="acquire"),
    dict(task_id="w1d_sat_dec", split="wave1_dev", family="state", mechanism="sat_dec", instance_seed=514, role="acquire"),
    dict(task_id="w2_if_pos_add1", split="wave2_target", family="gate_transform", mechanism="if_pos_add1", instance_seed=521, role="acquire"),
    dict(task_id="w2_sat_inc_mul2", split="wave2_target", family="state_transform", mechanism="sat_inc_mul2", instance_seed=522, role="acquire"),
    dict(task_id="w2_if_neg_neg", split="wave2_target", family="gate_transform", mechanism="if_neg_neg", instance_seed=523, role="acquire"),
    dict(task_id="w2_sign_pos", split="wave2_reject", family="cross_rep", mechanism="sign_pos", instance_seed=524, role="reject"),
    dict(task_id="w3_add1_if_pos", split="wave3_compose", family="transform_gate", mechanism="add1_if_pos", instance_seed=531, role="acquire"),
    dict(task_id="w3r_add1", split="wave3_retain", family="affine", mechanism="add1", instance_seed=541, role="acquire"),
    dict(task_id="w3r_if_pos", split="wave3_retain", family="gate", mechanism="if_pos", instance_seed=542, role="acquire"),
    dict(task_id="w3r_sat_inc", split="wave3_retain", family="state", mechanism="sat_inc", instance_seed=543, role="acquire"),
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
        elif raw["split"] in (
            "within_family", "composition", "mismatch_control", "varied_ordinary",
            "synthesis_source",
        ) and raw["mechanism"] not in LANGUAGE:
            raise ValueError("heldout_in_family_must_be_in_language:" + raw["task_id"])
        elif raw["split"] in (
            "mismatch", "varied_measure", "varied_sequence", "varied_indistinct",
            "synthesis_gate", "synthesis_holdout", "wave2_target", "wave2_reject",
            "wave3_compose",
        ) and raw["mechanism"] in LANGUAGE:
            raise ValueError("mismatch_must_be_outside:" + raw["task_id"])
        rows.append(dict(raw, origin="authored_mechanism"))
    return rows


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] == split]


def assessment_tasks() -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] in ("within_family", "composition", "excluded_family")]


def mismatch_tasks() -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] in ("mismatch", "mismatch_control")]


def varied_tasks() -> list[dict[str, Any]]:
    return [
        row for row in catalogue()
        if row["split"] in (
            "varied_measure", "varied_sequence", "varied_indistinct", "varied_ordinary",
        )
    ]


def synthesis_source_tasks() -> list[dict[str, Any]]:
    return tasks_for("synthesis_source")


def synthesis_gate_tasks() -> list[dict[str, Any]]:
    return tasks_for("synthesis_gate")


def synthesis_holdout_tasks() -> list[dict[str, Any]]:
    return tasks_for("synthesis_holdout")


def wave_tasks(*splits: str) -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] in splits]


def split_lock() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in catalogue():
        out.setdefault(row["split"], []).append(row["task_id"])
    return out
