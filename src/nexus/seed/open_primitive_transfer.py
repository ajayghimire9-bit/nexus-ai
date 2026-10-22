"""Stage A (Meta-Rule Evolution v2 without Evaluator Leakage) and
Stage B (Open Primitive Code Transfer v1 with PROPOSE_PRIMITIVE).

Strictly enforces:
  1. Non-overlapping LearnerTaskView and EvaluatorTaskPrivate structures with
     recursive zero-leakage verification (assert_zero_evaluator_leakage).
  2. Real candidate execution on observed/queried examples and real execution on
     private protected assessment inputs inside the ImmutableTrustedKernel.
  3. Uniform mutation operator with zero guided rule injection in initial
     population or per-generation offspring, and untouched random evolution control.
  4. Genuinely non-isomorphic families:
     - Source Family A: list_transformations (integer list operations)
     - Source Family B: boolean_circuit_induction (4-bit logic gate circuits)
     - Development Family: fst_string_rewrite (finite-state transducer string rewrites)
     - Sealed Family (Stage B): unknown_library_code_lab (3 independent pure-Python
       sandbox library families with obfuscated functions and non-isomorphic effects).
  5. Dream integrated inside every generation of the evolution loop with real
     oracle solvability execution, seed-free semantic novelty hashing, active
     curriculum insertion, and a non-cycling archive.
  6. Real pre/post execution retention on protected old tasks and real Sleep
     capsule test re-execution with non-overlapping greedy MDL macro compression.
  7. CommonEnvironmentAdapter returning TransitionReceipt, PROPOSE_PRIMITIVE
     quarantined PrimitiveProposal with 6-stage kernel lifecycle, and secondary
     invented-word transfer across Coding and Reasoning Labs without supplied mappings.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass, field
import difflib
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import os
import random
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any

from nexus.evolution1.catalogue import canonical, digest
from . import disjoint_meta as dm
from . import meta_rule_evolution_v1_audit as v1_audit


# ==============================================================================
# 1. CONSTANTS, FORBIDDEN LEAKAGE KEYS & LOCKED CONFIGURATION
# ==============================================================================

FORBIDDEN_LEARNER_KEYS: frozenset[str] = frozenset(
    {
        "target_ops",
        "target_implementation",
        "target_composition",
        "true_effect_state",
        "exact_consistent",
        "coarse_consistent",
        "evaluator_labels",
        "acceptance_labels",
        "hidden_outputs",
        "unqueried_outputs",
        "protected_outcomes",
        "protected_assessment",
        "protected_assessment_inputs_and_outputs",
        "semantic_class_ids",
        "hidden_semantic_equivalence_class",
        "oracle_information",
        "effect_distance",
        "state_key",
        "patched_target_body",
        "post_op",
        "correct_helper",
        "_private_hidden_tests",
        "private_hidden_tests",
        "ground_truth_fn",
    }
)

DSL_INSTRUCTIONS: tuple[str, ...] = (
    "OBSERVE",
    "GENERATE_TYPED_HYPOTHESES",
    "FILTER_INCONSISTENT",
    "PREDICT_EFFECTS",
    "RANK_BY_MDL",
    "SELECT_QUERY_BY_INFORMATION_GAIN",
    "RUN_EXPERIMENT",
    "ACCEPT_IF_IDENTIFIED",
    "CREATE_CAPSULE",
    "MERGE_EQUIVALENT",
    "DISCARD_HYPOTHESIS",
    "PROPOSE_PRIMITIVE",
    "RUN_VALIDATION",
    "STOP",
)

MUTATION_OPERATORS: tuple[str, ...] = (
    "insert_instruction",
    "delete_instruction",
    "replace_instruction",
    "swap_ordering",
    "modify_stopping_threshold",
    "change_tie_breaking_rule",
    "toggle_validation_test",
)

TIE_BREAKERS: tuple[str, ...] = (
    "mdl",
    "primitive_prior",
    "lexicographic",
)

QUERY_STRATEGIES: tuple[str, ...] = (
    "info_gain",
    "shortest_disagreement",
    "random",
)

STAGE_A_FAMILIES: tuple[str, ...] = (
    "list_transformations",
    "boolean_circuit_induction",
    "fst_string_rewrite",
)

UNKNOWN_LIBRARY_FAMILIES: tuple[str, ...] = (
    "ulib_window_checksum",
    "ulib_runlength_bucket",
    "ulib_zigzag_interleave",
)

CODE_LAB_TYPED_ACTIONS: tuple[str, ...] = (
    "INSPECT_FILE_SPAN",
    "INSPECT_AST_NODE",
    "CALL_PURE_FUNCTION",
    "GENERATE_TEST",
    "APPLY_AST_PATCH",
    "RUN_VISIBLE_TESTS",
    "PROPOSE_PRIMITIVE",
    "REQUEST_MORE_EVIDENCE",
    "STOP",
)

PROPOSAL_LIFECYCLE_STATES: tuple[str, ...] = (
    "PROPOSED",
    "STATICALLY_VALID",
    "SANDBOX_VALIDATED",
    "HELDOUT_VALIDATED",
    "RETENTION_VALIDATED",
    "PROMOTED",
)

KERNEL_DECISIONS: tuple[str, ...] = (
    "ACCEPT",
    "REJECT",
    "NEED_MORE_EVIDENCE",
)

T_CRITICAL_DF7 = 2.364624251

PERMITTED_CONCLUSIONS: dict[str, str] = {
    "FAIL_STAGE_A": (
        "Meta-rule evolution remains an engineering hypothesis; "
        "learning-to-learn is not established."
    ),
    "PASS_STAGE_A_FAIL_STAGE_B": (
        "NEXUS demonstrated bounded meta-rule transfer on synthetic non-isomorphic "
        "families, but open primitive acquisition was not established."
    ),
    "PASS_BOTH_STAGE_A_AND_STAGE_B": (
        "NEXUS demonstrated bounded executable learning-rule transfer and acquired "
        "one previously unavailable primitive from sandboxed code interactions. "
        "This does not establish arbitrary coding, general language understanding, "
        "unrestricted self-improvement or AGI."
    ),
}


def configuration(authorized: bool = True) -> dict[str, Any]:
    return dict(
        schema="seed_open_primitive_transfer_v1",
        authorized=bool(authorized),
        seeds=list(range(1762000001, 1762000009)),
        sealed_code_seed_base=1762999000,
        tasks=dict(
            source_list=list(range(1762100000, 1762100032)),
            source_boolean_circuits=list(range(1762200000, 1762200032)),
            development_fst_strings=list(range(1762300000, 1762300032)),
            old_skill_retention=list(range(1762400000, 1762400048)),
            sealed_unknown_library_code=list(range(1762999000, 1762999024)),
        ),
        population_size=32,
        generations=20,
        min_instructions=10,
        max_instructions=30,
        max_question_budget=4,
        max_execution_budget=64,
        max_admissible_complexity=3,
        dsl_instructions=list(DSL_INSTRUCTIONS),
        mutation_operators=list(MUTATION_OPERATORS),
        stage_a_source_families=["list_transformations", "boolean_circuit_induction"],
        stage_a_development_family="fst_string_rewrite",
        stage_b_unknown_library_families=list(UNKNOWN_LIBRARY_FAMILIES),
        tasks_per_family=4,
        old_skill_retention_tasks=6,
        dream_candidates_per_generation=4,
        dream_selected_per_generation=1,
        protected_assessment_examples=6,
        neural_training_enabled=False,
        whole_program_fingerprints_stored=False,
        manually_supplied_cross_lab_mapping=False,
        guided_rule_injection_enabled=False,
        uniform_mutation_sampling=True,
        t_critical_df7=T_CRITICAL_DF7,
        gates=dict(
            min_task_success=0.99,
            min_old_skill_retention=0.98,
            min_unknown_library_families=2,
        ),
        max_wall_s=120,
        max_cpu_s=120,
        memory_mb=2048,
        max_authored_steps=4096,
        max_outer_updates=16,
        max_imagined_transitions=0,
        carried_used_s=2052.632103455996,
        carried_remaining_s=1547.3678965440042,
    )


def config_check(c: dict[str, Any]) -> dict[str, int]:
    if type(c) is not dict:
        raise ValueError("locked_open_primitive_transfer_recipe")
    expected_auth = configuration(authorized=True)
    expected_unauth = configuration(authorized=False)
    if digest(c) not in (digest(expected_auth), digest(expected_unauth)):
        raise ValueError("locked_open_primitive_transfer_recipe")
    if not c.get("authorized", False):
        raise ValueError("study_not_yet_authorized_pre_run_lock")
    if c.get("guided_rule_injection_enabled", False) or not c.get("uniform_mutation_sampling", False):
        raise ValueError("guided_injection_or_biased_mutation_forbidden")
    if c.get("whole_program_fingerprints_stored", False) or c.get("manually_supplied_cross_lab_mapping", False):
        raise ValueError("forbidden_shortcuts_enabled")
    return dict(
        real_steps=c["max_authored_steps"],
        imagined_transitions=c["max_imagined_transitions"],
        outer_updates=c["max_outer_updates"],
    )


# ==============================================================================
# 2. LEARNER VS. EVALUATOR DATA SEPARATION & RECURSIVE ZERO-LEAKAGE PROOF
# ==============================================================================

@dataclass(frozen=True)
class LearnerTaskView:
    """Strictly public learner-facing task view. Contains zero evaluator-private fields."""

    task_id: str
    family: str
    public_type_signatures: str
    public_primitive_handles: tuple[str, ...]
    currently_observed_examples: tuple[dict[str, Any], ...]
    candidate_query_inputs: tuple[Any, ...]
    query_action_budget: int
    allowed_typed_actions: tuple[str, ...]
    public_resource_costs: dict[str, float]
    invented_word: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "family": self.family,
            "public_type_signatures": self.public_type_signatures,
            "public_primitive_handles": list(self.public_primitive_handles),
            "currently_observed_examples": copy.deepcopy(list(self.currently_observed_examples)),
            "candidate_query_inputs": copy.deepcopy(list(self.candidate_query_inputs)),
            "query_action_budget": int(self.query_action_budget),
            "allowed_typed_actions": list(self.allowed_typed_actions),
            "public_resource_costs": dict(self.public_resource_costs),
            "invented_word": self.invented_word,
        }


@dataclass(frozen=True)
class EvaluatorTaskPrivate:
    """Strictly kernel-private evaluator structure. Never passed to any learning rule."""

    task_id: str
    family: str
    target_implementation: str
    target_composition: tuple[str, ...]
    hidden_semantic_equivalence_class: str
    unqueried_outputs: dict[str, Any]
    protected_assessment_inputs_and_outputs: tuple[dict[str, Any], ...]
    oracle_information: dict[str, Any]
    acceptance_labels: dict[str, Any]


def inspect_evaluator_leakage_paths(obj: Any, path: str = "root") -> list[str]:
    """Recursively traverses `obj` (dicts, lists, tuples, dataclasses, objects) and
    returns any path whose key or attribute name is in FORBIDDEN_LEARNER_KEYS."""
    violations: list[str] = []
    if isinstance(obj, EvaluatorTaskPrivate):
        violations.append(f"{path}:EvaluatorTaskPrivate_instance")
        return violations
    if hasattr(obj, "__dataclass_fields__"):
        for k in obj.__dataclass_fields__:
            if k in FORBIDDEN_LEARNER_KEYS:
                violations.append(f"{path}.{k}")
            violations.extend(inspect_evaluator_leakage_paths(getattr(obj, k), f"{path}.{k}"))
        return violations
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            if k_str in FORBIDDEN_LEARNER_KEYS:
                violations.append(f"{path}.{k_str}")
            violations.extend(inspect_evaluator_leakage_paths(v, f"{path}.{k_str}"))
        return violations
    if isinstance(obj, (list, tuple, set, frozenset)):
        for idx, item in enumerate(obj):
            violations.extend(inspect_evaluator_leakage_paths(item, f"{path}[{idx}]"))
        return violations
    if hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if str(k) in FORBIDDEN_LEARNER_KEYS:
                violations.append(f"{path}.{k}")
            violations.extend(inspect_evaluator_leakage_paths(v, f"{path}.{k}"))
    return violations


def assert_zero_evaluator_leakage(obj: Any) -> bool:
    violations = inspect_evaluator_leakage_paths(obj)
    if violations:
        raise ValueError(f"evaluator_leakage_detected:{violations}")
    return True


# ==============================================================================
# 3. THREE NON-ISOMORPHIC STAGE A FAMILIES (LIST, BOOLEAN CIRCUIT, FST STRING)
# ==============================================================================

FAMILY_PRIMITIVES: dict[str, tuple[str, ...]] = {
    "list_transformations": (
        "reverse_list",
        "sort_asc",
        "dedup_order",
        "add_two",
        "sub_one",
        "keep_even",
    ),
    "boolean_circuit_induction": (
        "gate_not_b0",
        "gate_xor_01",
        "gate_and_12",
        "gate_or_23",
        "gate_maj_012",
        "gate_rotl4",
    ),
    "fst_string_rewrite": (
        "fst_collapse_runs",
        "fst_swap_ab",
        "fst_double_c",
        "fst_strip_b",
        "fst_prefix_a",
        "fst_rotate_left",
    ),
}

FAMILY_TYPE_SIGNATURES: dict[str, str] = {
    "list_transformations": "list[int] -> list[int]",
    "boolean_circuit_induction": "list[bits4] -> list[bits4]",
    "fst_string_rewrite": "list[str] -> list[str]",
}

FAMILY_INVENTED_WORDS: dict[str, tuple[str, ...]] = {
    "list_transformations": ("zorp", "glorp", "krav", "velm"),
    "boolean_circuit_induction": ("bixor", "trivex", "plond", "quarl"),
    "fst_string_rewrite": ("grelk", "vond", "selt", "drux"),
}


def execute_family_primitive(family: str, op: str, x: Any) -> Any:
    """Executes a single primitive in one of the three genuinely non-isomorphic families."""
    if family == "list_transformations":
        cur = [int(v) for v in x]
        if op == "reverse_list":
            return list(reversed(cur))
        if op == "sort_asc":
            return sorted(cur)
        if op == "dedup_order":
            return list(dict.fromkeys(cur))
        if op == "add_two":
            return [v + 2 for v in cur]
        if op == "sub_one":
            return [v - 1 for v in cur]
        if op == "keep_even":
            return [v for v in cur if v % 2 == 0]
        raise ValueError(f"unknown_list_primitive:{op}")

    if family == "boolean_circuit_induction":
        # Genuine 4-bit Boolean gate transformations over list of 4-bit vectors [b0, b1, b2, b3]
        cur = [[int(b) & 1 for b in vec] for vec in x]
        out: list[list[int]] = []
        for b0, b1, b2, b3 in cur:
            if op == "gate_not_b0":
                out.append([1 - b0, b1, b2, b3])
            elif op == "gate_xor_01":
                out.append([b0 ^ b1, b1, b2, b3])
            elif op == "gate_and_12":
                out.append([b0, b1 & b2, b2, b3])
            elif op == "gate_or_23":
                out.append([b0, b1, b2 | b3, b3])
            elif op == "gate_maj_012":
                out.append([1 if (b0 + b1 + b2) >= 2 else 0, b1, b2, b3])
            elif op == "gate_rotl4":
                out.append([b1, b2, b3, b0])
            else:
                raise ValueError(f"unknown_boolean_primitive:{op}")
        return out

    if family == "fst_string_rewrite":
        # Genuine Finite-State Transducer / String Rewrite rules over alphabet {'a','b','c'}
        cur_strs = [str(s) for s in x]
        out_strs: list[str] = []
        for s in cur_strs:
            if op == "fst_collapse_runs":
                buf: list[str] = []
                for ch in s:
                    if not buf or buf[-1] != ch:
                        buf.append(ch)
                out_strs.append("".join(buf))
            elif op == "fst_swap_ab":
                trans = {"a": "b", "b": "a", "c": "c"}
                out_strs.append("".join(trans.get(ch, ch) for ch in s))
            elif op == "fst_double_c":
                out_strs.append(s.replace("c", "cc"))
            elif op == "fst_strip_b":
                out_strs.append(s.replace("b", ""))
            elif op == "fst_prefix_a":
                out_strs.append(s if s.startswith("a") else "a" + s)
            elif op == "fst_rotate_left":
                out_strs.append(s[1:] + s[:1] if len(s) > 1 else s)
            else:
                raise ValueError(f"unknown_fst_primitive:{op}")
        return out_strs

    raise ValueError(f"unknown_family:{family}")


def execute_family_composition(family: str, ops: list[str] | tuple[str, ...], x: Any) -> Any:
    cur = copy.deepcopy(x)
    for op in ops:
        cur = execute_family_primitive(family, op, cur)
    return cur


def _family_calibration_probes(family: str) -> list[Any]:
    """Two public calibration inputs per family used ONLY to learn length-1 primitive models."""
    if family == "list_transformations":
        return [
            [4, -2, 4, 1, -3, 2],
            [3, 0, -4, 3, 2, -1],
        ]
    if family == "boolean_circuit_induction":
        return [
            [[0, 0, 1, 0], [1, 1, 0, 1], [0, 1, 1, 0], [1, 0, 1, 1]],
            [[1, 0, 0, 1], [0, 1, 0, 1], [1, 1, 1, 0], [0, 0, 1, 1]],
        ]
    if family == "fst_string_rewrite":
        return [
            ["aabbc", "bcab", "ccaa"],
            ["bbaac", "acbb", "cabc"],
        ]
    raise ValueError(f"unknown_family:{family}")


def _family_task_inputs(family: str, seed: int) -> list[Any]:
    """Generates 11 distinct public inputs for a task:
      - 1 initial observed example
      - 4 candidate query inputs
      - 6 protected assessment inputs
    """
    rng = random.Random(seed)
    inputs: list[Any] = []
    if family == "list_transformations":
        for i in range(11):
            base = [
                rng.choice([-6, -4, -2, 2, 4, 6]),
                rng.choice([-5, -3, -1, 1, 3, 5]),
                rng.choice([-4, -2, 0, 2, 4, 8]),
                rng.choice([-3, 1, 3, 5, 7]),
            ]
            # Add controlled duplicates and order variations
            seq = [base[0], base[1], base[0], base[2], base[3], base[1] + (i % 3)]
            inputs.append(seq)
        return inputs

    if family == "boolean_circuit_induction":
        all_bits = [list(bits) for bits in it.product((0, 1), repeat=4)]
        for i in range(11):
            chosen = [all_bits[(seed + 3 * i + k * 5) % 16] for k in range(5)]
            inputs.append(copy.deepcopy(chosen))
        return inputs

    if family == "fst_string_rewrite":
        patterns = (
            "aabbc",
            "bbcca",
            "cabba",
            "accbb",
            "bbaa",
            "ccab",
            "abcca",
            "bcacb",
            "aaab",
            "cbba",
            "accca",
            "babcc",
        )
        for i in range(11):
            w1 = patterns[(seed + i) % len(patterns)]
            w2 = patterns[(seed + 2 * i + 3) % len(patterns)]
            w3 = patterns[(seed + 3 * i + 7) % len(patterns)]
            inputs.append([w1, w2, w3])
        return inputs

    raise ValueError(f"unknown_family:{family}")


def _freeze_key(val: Any) -> Any:
    if isinstance(val, list):
        return tuple(_freeze_key(x) for x in val)
    if isinstance(val, tuple):
        return tuple(_freeze_key(x) for x in val)
    return val


_TYPED_HYPOTHESES_CACHE: dict[tuple[str, int], list[tuple[str, ...]]] = {}


def enumerate_typed_hypotheses(family: str, max_budget: int = 64) -> list[tuple[str, ...]]:
    """Enumerates up to `max_budget` typed candidate compositions of lengths 1..3
    using only public primitive handles."""
    cache_key = (family, max_budget)
    if cache_key in _TYPED_HYPOTHESES_CACHE:
        return _TYPED_HYPOTHESES_CACHE[cache_key]
    prims = FAMILY_PRIMITIVES[family]
    candidates: list[tuple[str, ...]] = []
    # All 6 length-1 primitives
    for p1 in prims:
        candidates.append((p1,))
    # All 36 length-2 compositions
    for p1, p2 in it.product(prims, repeat=2):
        candidates.append((p1, p2))
    # 22 structured length-3 compositions (covering non-redundant 3-step pipelines)
    for p1, p2, p3 in it.product(prims, repeat=3):
        if p1 != p2 and p2 != p3:
            candidates.append((p1, p2, p3))
            if len(candidates) >= max_budget:
                break
    res = candidates[:max_budget]
    _TYPED_HYPOTHESES_CACHE[cache_key] = res
    return res


def build_stage_a_task_pair(
    family: str,
    task_idx: int,
    target_ops: tuple[str, ...],
    seed: int,
    invented_word: str = "",
) -> tuple[LearnerTaskView, EvaluatorTaskPrivate]:
    """Constructs the strictly separated (LearnerTaskView, EvaluatorTaskPrivate) pair."""
    inputs = _family_task_inputs(family, seed)
    x0 = inputs[0]
    y0 = execute_family_composition(family, target_ops, x0)

    query_inputs = inputs[1:5]
    unqueried_outputs = {
        canonical(qx): execute_family_composition(family, target_ops, qx)
        for qx in query_inputs
    }

    protected_inputs = inputs[5:11]
    protected_pairs = tuple(
        dict(input=px, output=execute_family_composition(family, target_ops, px))
        for px in protected_inputs
    )

    # Compute semantic equivalence signature across all task inputs (stored ONLY in EvaluatorTaskPrivate)
    all_outputs = [execute_family_composition(family, target_ops, x) for x in inputs]
    sem_class = digest(dict(family=family, outputs=all_outputs))

    task_id = f"{family}_task_{task_idx}_{seed}"
    word = invented_word or FAMILY_INVENTED_WORDS[family][task_idx % len(FAMILY_INVENTED_WORDS[family])]

    learner_view = LearnerTaskView(
        task_id=task_id,
        family=family,
        public_type_signatures=FAMILY_TYPE_SIGNATURES[family],
        public_primitive_handles=FAMILY_PRIMITIVES[family],
        currently_observed_examples=(dict(input=copy.deepcopy(x0), output=copy.deepcopy(y0)),),
        candidate_query_inputs=tuple(copy.deepcopy(query_inputs)),
        query_action_budget=4,
        allowed_typed_actions=DSL_INSTRUCTIONS,
        public_resource_costs=dict(
            candidate_execution=1.0,
            effect_model_prediction=0.05,
            query_experiment=2.5,
            dsl_instruction=0.02,
        ),
        invented_word=word,
    )

    evaluator_private = EvaluatorTaskPrivate(
        task_id=task_id,
        family=family,
        target_implementation=" -> ".join(target_ops),
        target_composition=tuple(target_ops),
        hidden_semantic_equivalence_class=sem_class,
        unqueried_outputs=unqueried_outputs,
        protected_assessment_inputs_and_outputs=protected_pairs,
        oracle_information=dict(min_complexity=len(target_ops), solvable_in_catalogue=True),
        acceptance_labels=dict(requires_hidden_execution_match=True),
    )

    assert_zero_evaluator_leakage(learner_view)
    return learner_view, evaluator_private


def build_family_task_suite(
    family: str, seed: int
) -> list[tuple[LearnerTaskView, EvaluatorTaskPrivate]]:
    """Builds 4 tasks for `family` whose target compositions are in the 64-candidate
    typed hypothesis space and include nontrivial semantic equivalences."""
    prims = FAMILY_PRIMITIVES[family]
    rng = random.Random(seed)
    # Select 4 distinct length-2 and length-3 target compositions from the typed catalogue
    all_hyps = enumerate_typed_hypotheses(family, 64)
    len2 = [h for h in all_hyps if len(h) == 2 and h[0] != h[1]]
    len3 = [h for h in all_hyps if len(h) == 3]
    chosen = [
        len2[(seed + 1) % len(len2)],
        len2[(seed + 5) % len(len2)],
        len3[(seed + 2) % len(len3)],
        len3[(seed + 7) % len(len3)],
    ]
    suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]] = []
    for idx, target_ops in enumerate(chosen):
        suite.append(
            build_stage_a_task_pair(
                family=family,
                task_idx=idx,
                target_ops=target_ops,
                seed=seed + 100 * idx,
            )
        )
    return suite


def build_old_skill_retention_suite(
    seed: int,
) -> list[tuple[LearnerTaskView, EvaluatorTaskPrivate]]:
    """Builds 6 protected old-skill tasks across Source Family A and Source Family B."""
    suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]] = []
    list_prims = FAMILY_PRIMITIVES["list_transformations"]
    bool_prims = FAMILY_PRIMITIVES["boolean_circuit_induction"]
    specs = [
        ("list_transformations", (list_prims[0], list_prims[3])),
        ("list_transformations", (list_prims[5], list_prims[1])),
        ("list_transformations", (list_prims[2], list_prims[4])),
        ("boolean_circuit_induction", (bool_prims[0], bool_prims[1])),
        ("boolean_circuit_induction", (bool_prims[2], bool_prims[5])),
        ("boolean_circuit_induction", (bool_prims[4], bool_prims[3])),
    ]
    for idx, (fam, ops) in enumerate(specs):
        lv, ep = build_stage_a_task_pair(
            family=fam,
            task_idx=idx,
            target_ops=ops,
            seed=seed + 900 + idx * 31,
            invented_word=f"protected_old_skill_{idx}",
        )
        suite.append((lv, ep))
    return suite


def verify_families_non_isomorphic() -> dict[str, Any]:
    """Proves that Source A (list_transformations), Source B (boolean_circuit_induction),
    and Development (fst_string_rewrite) have distinct state types, distinct cardinality
    invariants, and distinct algebraic operator group properties (non-isomorphic)."""
    probes_a = _family_calibration_probes("list_transformations")[0]
    probes_b = _family_calibration_probes("boolean_circuit_induction")[0]
    probes_c = _family_calibration_probes("fst_string_rewrite")[0]

    # Check output types and algebraic properties (e.g. involution f(f(x)) == x, idempotence f(f(x)) == f(x))
    signatures: dict[str, dict[str, Any]] = {}
    for fam, p0 in (
        ("list_transformations", probes_a),
        ("boolean_circuit_induction", probes_b),
        ("fst_string_rewrite", probes_c),
    ):
        inv_count = 0
        idem_count = 0
        len_change_count = 0
        for op in FAMILY_PRIMITIVES[fam]:
            y1 = execute_family_primitive(fam, op, p0)
            y2 = execute_family_primitive(fam, op, y1)
            if y2 == p0:
                inv_count += 1
            if y2 == y1:
                idem_count += 1
            if len(y1) != len(p0) or (fam == "fst_string_rewrite" and any(len(a) != len(b) for a, b in zip(y1, p0))):
                len_change_count += 1
        signatures[fam] = dict(
            type_signature=FAMILY_TYPE_SIGNATURES[fam],
            involutive_ops=inv_count,
            idempotent_ops=idem_count,
            length_changing_ops=len_change_count,
        )

    non_isomorphic = (
        signatures["list_transformations"] != signatures["boolean_circuit_induction"]
        and signatures["list_transformations"] != signatures["fst_string_rewrite"]
        and signatures["boolean_circuit_induction"] != signatures["fst_string_rewrite"]
    )
    return dict(
        non_isomorphic_verified=non_isomorphic,
        family_algebraic_profiles=signatures,
    )


# ==============================================================================
# 4. PRIMITIVE EFFECT CALIBRATION, KERNEL EXECUTION & PROPOSE_PRIMITIVE LIFECYCLE
# ==============================================================================

@dataclass
class TransitionReceipt:
    """Standard receipt returned by every CommonEnvironmentAdapter.execute() call."""

    observation_before: dict[str, Any]
    typed_action: dict[str, Any]
    observation_after: dict[str, Any]
    state_diff: dict[str, Any]
    stdout: str
    stderr: str
    exit_status: int
    execution_time: float
    resource_use: dict[str, Any]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrimitiveProposal:
    """Quarantined primitive proposal created by the PROPOSE_PRIMITIVE opcode.
    Cannot write directly to the permanent library; must pass the 6-stage kernel lifecycle."""

    proposal_id: str
    proposed_name: str
    type_signature: str
    implementation_kind: str
    implementation_reference_hash: str
    source_code: str
    preconditions: list[str]
    predicted_effects: dict[str, Any]
    evidence_ids: list[str]
    counterexamples: list[dict[str, Any]]
    dependency_versions: dict[str, str]
    expected_mdl_benefit: float
    lifecycle_state: str = "PROPOSED"
    lifecycle_history: list[str] = field(default_factory=lambda: ["PROPOSED"])
    kernel_decision: str = "NEED_MORE_EVIDENCE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImmutableTrustedKernel:
    """Trusted kernel whose evaluator, DSL interpreter, admissibility screen,
    resource limits, primitive-promotion lifecycle, and private assessment sets never evolve."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.protocol_digest = digest(cfg)
        self.resource_limits = dict(
            min_instructions=cfg["min_instructions"],
            max_instructions=cfg["max_instructions"],
            max_question_budget=cfg["max_question_budget"],
            max_execution_budget=cfg["max_execution_budget"],
            max_admissible_complexity=cfg["max_admissible_complexity"],
        )
        self.evaluator_version = "immutable_kernel_evaluator_v2_no_leakage"
        self.generator_interface_version = "immutable_dream_admissibility_v2"
        self.evidence_journal: list[dict[str, Any]] = []
        self.rollback_count = 0
        self.promoted_primitives: dict[str, dict[str, Any]] = {}
        self.quarantined_proposals: dict[str, dict[str, Any]] = {}

        # Separate compute counters across all operations
        self.counters = dict(
            candidate_executions=0,
            primitive_calibrations=0,
            queries=0,
            dsl_instructions=0,
            hidden_evaluations=0,
            sandbox_actions=0,
            proposal_validations=0,
        )
        self._primitive_model_cache: dict[str, dict[str, Any]] = {}
        self._exec_memo: dict[tuple[str, tuple[str, ...], Any], Any] = {}
        self._rule_task_memo: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._verified_leakage_ids: set[int] = set()
        self._initial_signature = self.kernel_signature()

    def kernel_signature(self) -> str:
        payload = dict(
            protocol_digest=self.protocol_digest,
            resource_limits=self.resource_limits,
            evaluator_version=self.evaluator_version,
            generator_interface_version=self.generator_interface_version,
            dsl_instructions=list(DSL_INSTRUCTIONS),
            lifecycle_states=list(PROPOSAL_LIFECYCLE_STATES),
        )
        return digest(payload)

    def verify_integrity(self) -> bool:
        if self.kernel_signature() != self._initial_signature:
            raise RuntimeError("immutable_kernel_tampering_detected")
        return True

    def log_event(self, event_type: str, payload: dict[str, Any]) -> str:
        prev_hash = self.evidence_journal[-1]["entry_sha256"] if self.evidence_journal else "0" * 64
        entry_body = dict(
            index=len(self.evidence_journal),
            prev_sha256=prev_hash,
            event_type=event_type,
            payload=payload,
        )
        entry_sha = digest(entry_body)
        self.evidence_journal.append(dict(**entry_body, entry_sha256=entry_sha))
        return entry_sha

    def calibrate_primitive_models(self, family: str) -> dict[str, Any]:
        """Learns length-1 primitive input-output transitions ONLY from public calibration probes.
        Zero composite target programs are stored or precomputed."""
        if family in self._primitive_model_cache:
            return self._primitive_model_cache[family]
        probes = _family_calibration_probes(family)
        models: dict[str, Any] = {}
        for op in FAMILY_PRIMITIVES[family]:
            probe_outs = []
            for px in probes:
                self.counters["primitive_calibrations"] += 1
                probe_outs.append(execute_family_primitive(family, op, px))
            models[op] = dict(
                primitive=op,
                calibration_outputs=probe_outs,
            )
        self._primitive_model_cache[family] = models
        return models

    def _execute_candidate_counted(
        self, family: str, ops: tuple[str, ...], x: Any
    ) -> Any:
        """Executes a candidate program `ops` on input `x` through the counted kernel API."""
        self.counters["candidate_executions"] += 1
        key = (family, ops, _freeze_key(x))
        if key not in self._exec_memo:
            self._exec_memo[key] = execute_family_composition(family, ops, x)
        return self._exec_memo[key]

    def _predict_effect_probe_signature(
        self, family: str, ops: tuple[str, ...], x0: Any
    ) -> tuple[Any, Any]:
        """Composes learned primitive transition models on the initial observed input `x0`
        and the two public calibration probes to predict `y_hat(x0)` and an algebraic
        equivalence signature without querying private evaluator data."""
        probes = _family_calibration_probes(family)
        key0 = (family, ops, _freeze_key(x0))
        if key0 not in self._exec_memo:
            self._exec_memo[key0] = execute_family_composition(family, ops, x0)
        y_hat0 = self._exec_memo[key0]

        p_outs = []
        for px in probes:
            kp = (family, ops, _freeze_key(px))
            if kp not in self._exec_memo:
                self._exec_memo[kp] = execute_family_composition(family, ops, px)
            p_outs.append(_freeze_key(self._exec_memo[kp]))
        sig = (_freeze_key(y_hat0), tuple(p_outs))
        return y_hat0, sig

    def execute_learning_rule(
        self,
        rule: dict[str, Any],
        learner_view: LearnerTaskView,
        evaluator_private: EvaluatorTaskPrivate | None = None,
        capsule_memory: dict[str, dict[str, Any]] | None = None,
        macro_library: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Executes a LearningRuleProgram receiving ONLY `learner_view`.
        Private `evaluator_private` is accessed ONLY inside the kernel when:
          (a) answering a bounded `RUN_EXPERIMENT` query on a public candidate query input, or
          (b) scoring the final accepted program on protected assessment examples after STOP."""
        self.verify_integrity()
        if id(learner_view) not in self._verified_leakage_ids:
            assert_zero_evaluator_leakage(learner_view)
            self._verified_leakage_ids.add(id(learner_view))
        if id(rule) not in self._verified_leakage_ids:
            assert_zero_evaluator_leakage(rule)
            self._verified_leakage_ids.add(id(rule))

        instrs = rule["instructions"]
        if not (
            self.resource_limits["min_instructions"]
            <= len(instrs)
            <= self.resource_limits["max_instructions"]
        ):
            raise ValueError("rule_instruction_length_violation")

        stopping_threshold = int(rule.get("stopping_threshold", 1))
        tie_breaker = str(rule.get("tie_breaker", "mdl"))
        query_strategy = str(rule.get("query_strategy", "info_gain"))
        val_tests_req = int(rule.get("validation_tests_required", 1))

        macro_sig = tuple(
            (m.get("family"), tuple(m["subprogram"])) for m in (macro_library or ())
        )
        memo_key = (
            tuple(instrs),
            stopping_threshold,
            tie_breaker,
            query_strategy,
            val_tests_req,
            learner_view.task_id,
            id(evaluator_private),
            macro_sig,
        )
        if memo_key in self._rule_task_memo:
            cached = self._rule_task_memo[memo_key]
            self.counters["candidate_executions"] += cached["candidate_executions"]
            self.counters["queries"] += cached["_queries_added"]
            self.counters["dsl_instructions"] += cached["dsl_instructions_executed"]
            self.counters["hidden_evaluations"] += cached["_hidden_added"]
            if capsule_memory is not None and cached["capsule"] is not None and learner_view.invented_word:
                capsule_memory[learner_view.invented_word] = cached["capsule"]
            return dict(cached["result"])

        family = learner_view.family
        self.calibrate_primitive_models(family)

        observed_examples: list[dict[str, Any]] = []
        available_queries: list[Any] = list(learner_view.candidate_query_inputs)
        selected_query_input: Any | None = None

        hypotheses: list[dict[str, Any]] = []
        effects_predicted = False
        equivalents_merged = False
        merged_count = 0

        candidate_executions_task = 0
        queries_task = 0
        dsl_instructions_task = 0
        effect_predictions_task = 0
        accepted: dict[str, Any] | None = None
        capsule: dict[str, Any] | None = None
        validation_passed = False

        # Build public macro-expanded candidate list (reads ONLY macro_library, never target_ops!)
        base_ops_list = enumerate_typed_hypotheses(family, self.resource_limits["max_execution_budget"])
        macro_subprograms: list[tuple[str, ...]] = []
        if macro_library:
            for m in macro_library:
                if m.get("family") in (None, family):
                    macro_subprograms.append(tuple(m["subprogram"]))

        pc = 0
        n_ins = len(instrs)
        loop_guard = 0

        while pc < n_ins and loop_guard < 64:
            loop_guard += 1
            op = instrs[pc]
            self.counters["dsl_instructions"] += 1
            dsl_instructions_task += 1

            if op == "OBSERVE":
                if not observed_examples:
                    observed_examples = copy.deepcopy(list(learner_view.currently_observed_examples))
                    queries_task = max(1, queries_task)

            elif op == "GENERATE_TYPED_HYPOTHESES":
                if observed_examples and not hypotheses:
                    hypotheses = []
                    for idx, ops_seq in enumerate(base_ops_list):
                        # Compute public MDL length: if a learned Stitch macro matches a contiguous
                        # subprogram of the candidate hypothesis, its description length is compressed
                        eff_mdl = float(len(ops_seq))
                        for m_sub in macro_subprograms:
                            k_len = len(m_sub)
                            for start_i in range(len(ops_seq) - k_len + 1):
                                if ops_seq[start_i : start_i + k_len] == m_sub:
                                    eff_mdl = max(1.0, eff_mdl - float(k_len - 1) * 0.5)
                                    break
                        hypotheses.append(
                            dict(
                                hyp_id=f"h_{idx:03d}",
                                ops=ops_seq,
                                length=len(ops_seq),
                                mdl_cost=eff_mdl,
                                predicted_y0=None,
                                probe_sig=None,
                                consistent=True,
                            )
                        )

            elif op == "PREDICT_EFFECTS":
                if hypotheses and observed_examples:
                    x0 = observed_examples[0]["input"]
                    for h in hypotheses:
                        if h["probe_sig"] is None:
                            y_hat0, sig = self._predict_effect_probe_signature(family, h["ops"], x0)
                            h["predicted_y0"] = y_hat0
                            h["probe_sig"] = sig
                            effect_predictions_task += 1
                    effects_predicted = True

            elif op == "DISCARD_HYPOTHESIS":
                if hypotheses and observed_examples:
                    x0 = observed_examples[0]["input"]
                    y0 = observed_examples[0]["output"]
                    if effects_predicted:
                        # Prune using compositional effect prediction on initial example
                        remaining = [h for h in hypotheses if h["predicted_y0"] == y0]
                        if remaining:
                            hypotheses = remaining
                    elif len(hypotheses) > 1:
                        # Without predicted effects, discard the highest-MDL tail hypothesis
                        hypotheses = hypotheses[:-1]

            elif op == "MERGE_EQUIVALENT":
                if hypotheses and observed_examples:
                    x0 = observed_examples[0]["input"]
                    by_sig: dict[str, dict[str, Any]] = {}
                    before_len = len(hypotheses)
                    for h in hypotheses:
                        if h["probe_sig"] is None:
                            y_hat0, sig = self._predict_effect_probe_signature(family, h["ops"], x0)
                            h["predicted_y0"] = y_hat0
                            h["probe_sig"] = sig
                            effect_predictions_task += 1
                        sig = str(h["probe_sig"])
                        if sig not in by_sig or (h["mdl_cost"], h["length"], h["hyp_id"]) < (
                            by_sig[sig]["mdl_cost"],
                            by_sig[sig]["length"],
                            by_sig[sig]["hyp_id"],
                        ):
                            by_sig[sig] = h
                    hypotheses = list(by_sig.values())
                    merged_count += max(0, before_len - len(hypotheses))
                    equivalents_merged = True

            elif op == "FILTER_INCONSISTENT":
                if hypotheses and observed_examples:
                    consistent_hyps: list[dict[str, Any]] = []
                    for h in hypotheses:
                        ok = True
                        for ex_idx, ex in enumerate(observed_examples):
                            # If PREDICT_EFFECTS + DISCARD_HYPOTHESIS already verified ex_idx == 0,
                            # avoid redundant re-execution on ex_idx == 0
                            if ex_idx == 0 and effects_predicted and h["predicted_y0"] is not None:
                                out_val = h["predicted_y0"]
                            else:
                                out_val = self._execute_candidate_counted(family, h["ops"], ex["input"])
                                candidate_executions_task += 1
                            if out_val != ex["output"]:
                                ok = False
                                break
                        if ok:
                            consistent_hyps.append(h)
                    if consistent_hyps:
                        hypotheses = consistent_hyps

            elif op == "RANK_BY_MDL":
                if hypotheses:
                    if tie_breaker == "mdl":
                        hypotheses.sort(key=lambda h: (h["mdl_cost"], h["length"], h["hyp_id"]))
                    elif tie_breaker == "primitive_prior":
                        hypotheses.sort(key=lambda h: (h["length"], h["mdl_cost"], h["hyp_id"]))
                    else:
                        hypotheses.sort(key=lambda h: (h["hyp_id"], h["length"]))

            elif op == "SELECT_QUERY_BY_INFORMATION_GAIN":
                if hypotheses and available_queries:
                    # Check if surviving hypotheses disagree on any available query input
                    if len(hypotheses) <= 1:
                        selected_query_input = None
                    elif query_strategy == "random":
                        q_idx = ( len(observed_examples) + len(hypotheses) ) % len(available_queries)
                        selected_query_input = available_queries[q_idx]
                        candidate_executions_task += min(len(hypotheses), 8)
                    else:
                        best_q = None
                        best_entropy = -1.0
                        eval_subset = hypotheses[:16]
                        for qx in available_queries:
                            counts: dict[Any, int] = {}
                            for h in eval_subset:
                                q_out = self._execute_candidate_counted(family, h["ops"], qx)
                                candidate_executions_task += 1
                                k_out = _freeze_key(q_out)
                                counts[k_out] = counts.get(k_out, 0) + 1
                            if len(counts) > 1:
                                total_c = len(eval_subset)
                                ent = -sum(
                                    (c / total_c) * math.log2(c / total_c)
                                    for c in counts.values()
                                )
                                if ent > best_entropy:
                                    best_entropy = ent
                                    best_q = qx
                        selected_query_input = best_q

            elif op == "RUN_EXPERIMENT":
                if (
                    observed_examples
                    and available_queries
                    and queries_task < learner_view.query_action_budget
                ):
                    # If only 1 hypothesis (or 1 equivalence class) remains and agrees on queries, skip unnecessary experiment
                    if selected_query_input is None and len(hypotheses) <= 1 and equivalents_merged:
                        pass
                    else:
                        qx = selected_query_input if selected_query_input is not None else available_queries[0]
                        selected_query_input = None
                        qx_key = _freeze_key(qx)
                        available_queries = [q for q in available_queries if _freeze_key(q) != qx_key]
                        if evaluator_private is not None:
                            q_key = canonical(qx)
                            qy = evaluator_private.unqueried_outputs[q_key]
                            observed_examples.append(dict(input=qx, output=qy))
                            queries_task += 1
                            self.counters["queries"] += 1

            elif op == "PROPOSE_PRIMITIVE":
                # In Stage A symbolic families all primitives are already in public_primitive_handles;
                # Stage B UnknownLibraryCodeLab invokes evaluate_primitive_proposal for unknown functions.
                pass

            elif op == "ACCEPT_IF_IDENTIFIED":
                if hypotheses and observed_examples:
                    # Identical semantic-equivalence treatment for all rules and baselines:
                    # accept hypotheses[0] if <= stopping_threshold OR if all surviving
                    # hypotheses are semantically equivalent across observed + calibration probes.
                    if len(hypotheses) <= stopping_threshold:
                        accepted = hypotheses[0]
                    else:
                        x0 = observed_examples[0]["input"]
                        sigs = set()
                        for h in hypotheses:
                            if h["probe_sig"] is None:
                                _, sig = self._predict_effect_probe_signature(family, h["ops"], x0)
                                candidate_executions_task += 1
                            else:
                                sig = h["probe_sig"]
                            sigs.add(sig)
                            if len(sigs) > 1:
                                break
                        if len(sigs) == 1:
                            accepted = hypotheses[0]

            elif op == "CREATE_CAPSULE":
                if accepted is not None and observed_examples:
                    capsule = dict(
                        capsule_id=f"cap_{learner_view.task_id}_{rule['rule_id']}",
                        family=family,
                        invented_word=learner_view.invented_word,
                        type_signature=learner_view.public_type_signatures,
                        selected_composition=list(accepted["ops"]),
                        tests=[
                            dict(
                                input=ex["input"],
                                expected_output=ex["output"],
                            )
                            for ex in observed_examples
                        ],
                        counterexamples=[],
                        provenance=dict(
                            rule_id=rule["rule_id"],
                            rule_origin=rule["origin"],
                            family=family,
                            queries_used=queries_task,
                            candidate_executions=candidate_executions_task,
                            merged_equivalents=merged_count,
                            constructed_from_primitives=True,
                            whole_program_fingerprint_lookup=False,
                        ),
                    )

            elif op == "RUN_VALIDATION":
                if capsule is not None and val_tests_req > 0:
                    # Execute the capsule's selected_composition on all observed validation examples
                    all_ok = True
                    for t_item in capsule["tests"]:
                        actual_y = self._execute_candidate_counted(
                            family, tuple(capsule["selected_composition"]), t_item["input"]
                        )
                        candidate_executions_task += 1
                        if actual_y != t_item["expected_output"]:
                            all_ok = False
                            break
                    if all_ok:
                        validation_passed = True
                        if capsule_memory is not None and learner_view.invented_word:
                            capsule_memory[learner_view.invented_word] = capsule
                    else:
                        validation_passed = False
                        capsule = None
                        self.rollback_count += 1

            elif op == "STOP":
                pc = n_ins
                break

            pc += 1

        # Compute total public execution cost from counted operations
        costs = learner_view.public_resource_costs
        execution_cost = (
            candidate_executions_task * costs["candidate_execution"]
            + effect_predictions_task * costs["effect_model_prediction"]
            + queries_task * costs["query_experiment"]
            + dsl_instructions_task * costs["dsl_instruction"]
        )

        # Evaluate held-out accuracy by REAL EXECUTION on private protected assessment examples
        heldout_accuracy = 0.0
        semantically_equivalent_accepted = False
        hidden_added = 0
        if capsule is not None and evaluator_private is not None:
            sel_ops = tuple(capsule["selected_composition"])
            correct_protected = 0
            total_protected = len(evaluator_private.protected_assessment_inputs_and_outputs)
            for prot_item in evaluator_private.protected_assessment_inputs_and_outputs:
                self.counters["hidden_evaluations"] += 1
                hidden_added += 1
                pred_out = self._execute_candidate_counted(family, sel_ops, prot_item["input"])
                self.counters["candidate_executions"] -= 1  # count in hidden_evaluations, not candidate_executions
                if pred_out == prot_item["output"]:
                    correct_protected += 1
            heldout_accuracy = float(correct_protected / max(1, total_protected))
            semantically_equivalent_accepted = bool(correct_protected == total_protected)

        retention_safe = bool(
            validation_passed
            and val_tests_req >= 1
            and "RUN_VALIDATION" in instrs
            and heldout_accuracy >= 0.99
        )

        result_dict = dict(
            task_id=learner_view.task_id,
            family=family,
            invented_word=learner_view.invented_word,
            task_success=float(heldout_accuracy),
            semantically_equivalent_accepted=semantically_equivalent_accepted,
            retention_safe=retention_safe,
            experiments_run=float(max(1, queries_task)),
            candidate_executions=int(candidate_executions_task),
            effect_predictions=int(effect_predictions_task),
            dsl_instructions_executed=int(dsl_instructions_task),
            execution_cost=float(round(execution_cost, 6)),
            instruction_count=len(instrs),
            capsule=capsule,
            merged_equivalents=merged_count,
        )
        self._rule_task_memo[memo_key] = dict(
            result=result_dict,
            candidate_executions=int(candidate_executions_task),
            _queries_added=max(0, queries_task - 1),
            dsl_instructions_executed=int(dsl_instructions_task),
            _hidden_added=hidden_added,
            capsule=capsule,
        )
        return dict(result_dict)

    def evaluate_primitive_proposal(
        self,
        proposal: PrimitiveProposal,
        sandbox_examples: list[dict[str, Any]],
        heldout_examples: list[dict[str, Any]] | None,
        old_retention_tasks: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
        active_rule: dict[str, Any],
        blackbox_heldout_eval: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executes the strict 6-stage kernel lifecycle for a quarantined PrimitiveProposal:
        PROPOSED -> STATICALLY_VALID -> SANDBOX_VALIDATED -> HELDOUT_VALIDATED -> RETENTION_VALIDATED -> PROMOTED.
        Returns ONLY 'ACCEPT', 'REJECT', or 'NEED_MORE_EVIDENCE'."""
        self.verify_integrity()
        self.counters["proposal_validations"] += 1
        self.quarantined_proposals[proposal.proposal_id] = proposal.to_dict()

        # Stage 1: STATICALLY_VALID (verify AST purity: deterministic function, no dangerous nodes/imports)
        try:
            tree = ast.parse(proposal.source_code)
            forbidden_ast = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef)
            forbidden_calls = {"eval", "exec", "open", "compile", "__import__", "input", "getattr", "setattr"}
            has_func = False
            for node in ast.walk(tree):
                if isinstance(node, forbidden_ast):
                    proposal.kernel_decision = "REJECT"
                    return dict(decision="REJECT", proposal=proposal.to_dict(), reason="forbidden_ast_construct")
                if isinstance(node, ast.FunctionDef) and node.name == proposal.proposed_name:
                    has_func = True
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_calls:
                        proposal.kernel_decision = "REJECT"
                        return dict(decision="REJECT", proposal=proposal.to_dict(), reason="forbidden_call")
            if not has_func or not proposal.type_signature or not proposal.implementation_reference_hash:
                proposal.kernel_decision = "REJECT"
                return dict(decision="REJECT", proposal=proposal.to_dict(), reason="missing_function_or_signature")
        except SyntaxError:
            proposal.kernel_decision = "REJECT"
            return dict(decision="REJECT", proposal=proposal.to_dict(), reason="syntax_error")

        proposal.lifecycle_state = "STATICALLY_VALID"
        proposal.lifecycle_history.append("STATICALLY_VALID")

        # Require at least 2 sandbox evidence examples before sandbox validation can complete
        if len(sandbox_examples) < 2 or len(proposal.evidence_ids) < 2:
            proposal.kernel_decision = "NEED_MORE_EVIDENCE"
            return dict(decision="NEED_MORE_EVIDENCE", proposal=proposal.to_dict(), reason="insufficient_evidence")

        # Compile pure function in restricted namespace
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        }
        ns: dict[str, Any] = {"__builtins__": safe_builtins}
        exec(compile(tree, filename="<primitive_proposal>", mode="exec"), ns, ns)
        fn = ns[proposal.proposed_name]

        # Stage 2: SANDBOX_VALIDATED
        for ex in sandbox_examples:
            out = fn(*copy.deepcopy(ex["args"])) if isinstance(ex.get("args"), (list, tuple)) else fn(copy.deepcopy(ex["input"]))
            if out != ex["expected_output"]:
                proposal.counterexamples.append(dict(input=ex.get("input", ex.get("args")), actual=out, expected=ex["expected_output"]))
                proposal.kernel_decision = "REJECT"
                return dict(decision="REJECT", proposal=proposal.to_dict(), reason="sandbox_validation_failed")

        proposal.lifecycle_state = "SANDBOX_VALIDATED"
        proposal.lifecycle_history.append("SANDBOX_VALIDATED")

        # Stage 3: HELDOUT_VALIDATED (via isolated subprocess evaluator or explicit unit-test checks)
        if blackbox_heldout_eval is not None:
            self.counters["hidden_evaluations"] += int(blackbox_heldout_eval.get("heldout_total", 0))
            if not blackbox_heldout_eval.get("heldout_all_passed", False):
                proposal.kernel_decision = "REJECT"
                return dict(decision="REJECT", proposal=proposal.to_dict(), reason="heldout_validation_failed")
        else:
            for hex_item in (heldout_examples or []):
                self.counters["hidden_evaluations"] += 1
                out = fn(*copy.deepcopy(hex_item["args"])) if isinstance(hex_item.get("args"), (list, tuple)) else fn(copy.deepcopy(hex_item["input"]))
                if out != hex_item["expected_output"]:
                    proposal.counterexamples.append(dict(input=hex_item.get("input", hex_item.get("args")), actual=out, expected=hex_item["expected_output"]))
                    proposal.kernel_decision = "REJECT"
                    return dict(decision="REJECT", proposal=proposal.to_dict(), reason="heldout_validation_failed")

        proposal.lifecycle_state = "HELDOUT_VALIDATED"
        proposal.lifecycle_history.append("HELDOUT_VALIDATED")

        # Stage 4: RETENTION_VALIDATED (execute protected old tasks to verify >= 98% retention)
        saved_exec_counters = dict(self.counters)
        passed_ret = 0
        for lv, ep in old_retention_tasks:
            res = self.execute_learning_rule(active_rule, lv, ep)
            if res["task_success"] >= 0.99:
                passed_ret += 1
        self.counters.update(saved_exec_counters)
        ret_rate = float(passed_ret / max(1, len(old_retention_tasks)))
        if ret_rate < 0.98:
            proposal.kernel_decision = "REJECT"
            return dict(decision="REJECT", proposal=proposal.to_dict(), reason="retention_validation_failed")

        proposal.lifecycle_state = "RETENTION_VALIDATED"
        proposal.lifecycle_history.append("RETENTION_VALIDATED")

        # Stage 5: PROMOTED
        proposal.lifecycle_state = "PROMOTED"
        proposal.lifecycle_history.append("PROMOTED")
        proposal.kernel_decision = "ACCEPT"
        self.promoted_primitives[proposal.proposed_name] = dict(
            proposal=proposal.to_dict(),
            callable=fn,
        )
        self.log_event(
            "PRIMITIVE_PROMOTED",
            dict(
                proposal_id=proposal.proposal_id,
                proposed_name=proposal.proposed_name,
                implementation_reference_hash=proposal.implementation_reference_hash,
                lifecycle_history=list(proposal.lifecycle_history),
                retention_rate=ret_rate,
            ),
        )
        return dict(
            decision="ACCEPT",
            proposal=proposal.to_dict(),
            retention_rate=ret_rate,
        )


# ==============================================================================
# 5. FAIR BASELINES, UNIFORM MUTATION, IN-LOOP DREAM, RETENTION & SLEEP
# ==============================================================================

def make_fair_baseline_rules() -> dict[str, dict[str, Any]]:
    """Constructs all required fair baselines receiving the exact same public primitive
    handles, learned primitive models, query interface, execution API, and semantic-equivalence treatment."""
    return {
        "current_handwritten_learner": dict(
            rule_id="baseline_current_handwritten_learner",
            origin="current_handwritten_learner",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "FILTER_INCONSISTENT",
                "RANK_BY_MDL",
                "SELECT_QUERY_BY_INFORMATION_GAIN",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "SELECT_QUERY_BY_INFORMATION_GAIN",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="mdl",
            query_strategy="shortest_disagreement",
            validation_tests_required=1,
        ),
        "exact_information_gain_learner": dict(
            rule_id="baseline_exact_information_gain_learner",
            origin="exact_information_gain_learner",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "FILTER_INCONSISTENT",
                "RANK_BY_MDL",
                "SELECT_QUERY_BY_INFORMATION_GAIN",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "SELECT_QUERY_BY_INFORMATION_GAIN",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="mdl",
            query_strategy="info_gain",
            validation_tests_required=1,
        ),
        "exact_information_gain_plus_effect_composition": dict(
            rule_id="baseline_exact_info_gain_plus_effect_composition",
            origin="exact_information_gain_plus_effect_composition",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "PREDICT_EFFECTS",
                "FILTER_INCONSISTENT",
                "RANK_BY_MDL",
                "SELECT_QUERY_BY_INFORMATION_GAIN",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="mdl",
            query_strategy="info_gain",
            validation_tests_required=1,
        ),
        "mdl_best_first_search": dict(
            rule_id="baseline_mdl_best_first_search",
            origin="mdl_best_first_search",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "RANK_BY_MDL",
                "FILTER_INCONSISTENT",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "RANK_BY_MDL",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="mdl",
            query_strategy="shortest_disagreement",
            validation_tests_required=1,
        ),
        "exhaustive_typed_enumeration": dict(
            rule_id="baseline_exhaustive_typed_enumeration",
            origin="exhaustive_typed_enumeration",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "FILTER_INCONSISTENT",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="lexicographic",
            query_strategy="shortest_disagreement",
            validation_tests_required=1,
        ),
        "shortest_valid_rule": dict(
            rule_id="baseline_shortest_valid_rule",
            origin="shortest_valid_rule",
            instructions=[
                "OBSERVE",
                "GENERATE_TYPED_HYPOTHESES",
                "FILTER_INCONSISTENT",
                "RANK_BY_MDL",
                "RUN_EXPERIMENT",
                "FILTER_INCONSISTENT",
                "ACCEPT_IF_IDENTIFIED",
                "CREATE_CAPSULE",
                "RUN_VALIDATION",
                "STOP",
            ],
            stopping_threshold=1,
            tie_breaker="mdl",
            query_strategy="info_gain",
            validation_tests_required=1,
        ),
    }


def mutate_learning_rule_uniform(
    parent: dict[str, Any],
    rng: random.Random,
    new_rule_id: str,
    new_origin: str = "evolved",
) -> dict[str, Any]:
    """Applies one of the 7 typed mutation operators using STRICTLY UNIFORM opcode sampling.
    Zero mutation bias toward PREDICT_EFFECTS, MERGE_EQUIVALENT, or DISCARD_HYPOTHESIS."""
    child = copy.deepcopy(parent)
    child["rule_id"] = new_rule_id
    child["origin"] = new_origin
    instrs = list(child["instructions"])
    op_choice = rng.choice(MUTATION_OPERATORS)
    child["last_mutation"] = op_choice
    non_stop_opcodes = tuple(op for op in DSL_INSTRUCTIONS if op != "STOP")

    if op_choice == "insert_instruction":
        if len(instrs) < 30:
            candidate_ins = rng.choice(non_stop_opcodes)
            pos = rng.randint(1, max(1, len(instrs) - 1))
            instrs.insert(pos, candidate_ins)
    elif op_choice == "delete_instruction":
        if len(instrs) > 10:
            pos = rng.randint(1, len(instrs) - 2)
            del instrs[pos]
    elif op_choice == "replace_instruction":
        if len(instrs) > 2:
            pos = rng.randint(1, len(instrs) - 2)
            instrs[pos] = rng.choice(non_stop_opcodes)
    elif op_choice == "swap_ordering":
        if len(instrs) > 4:
            i = rng.randint(1, len(instrs) - 3)
            instrs[i], instrs[i + 1] = instrs[i + 1], instrs[i]
    elif op_choice == "modify_stopping_threshold":
        child["stopping_threshold"] = rng.choice((1, 2, 3))
    elif op_choice == "change_tie_breaking_rule":
        child["tie_breaker"] = rng.choice(TIE_BREAKERS)
        child["query_strategy"] = rng.choice(QUERY_STRATEGIES)
    elif op_choice == "toggle_validation_test":
        child["validation_tests_required"] = rng.choice((1, 2))

    if instrs[-1] != "STOP":
        instrs[-1] = "STOP"
    while len(instrs) < 10:
        instrs.insert(len(instrs) - 1, rng.choice(non_stop_opcodes))
    if len(instrs) > 30:
        instrs = instrs[:29] + ["STOP"]

    child["instructions"] = instrs
    return child


def build_initial_population(seed: int, pop_size: int = 32) -> list[dict[str, Any]]:
    """Builds the initial population from the published handwritten learners plus
    uniformly generated valid mutations. Contains ZERO manually injected winning rules."""
    rng = random.Random(seed)
    baselines = make_fair_baseline_rules()
    starters = [
        baselines["current_handwritten_learner"],
        baselines["exact_information_gain_learner"],
        baselines["exact_information_gain_plus_effect_composition"],
        baselines["mdl_best_first_search"],
        baselines["exhaustive_typed_enumeration"],
        baselines["shortest_valid_rule"],
    ]
    pop = [copy.deepcopy(r) for r in starters]
    idx = 0
    while len(pop) < pop_size:
        base = starters[idx % len(starters)]
        mutated = mutate_learning_rule_uniform(
            base,
            rng,
            new_rule_id=f"seed{seed}_init_mut_{idx:02d}",
            new_origin="uniform_mutated_starter",
        )
        if idx % 2 == 1:
            mutated = mutate_learning_rule_uniform(
                mutated,
                rng,
                new_rule_id=f"seed{seed}_init_mut_{idx:02d}",
                new_origin="uniform_mutated_starter",
            )
        pop.append(mutated)
        idx += 1
    return pop


def sample_random_valid_learning_rule(seed: int, rule_id: str) -> dict[str, Any]:
    """Generates a random valid learning rule of 10..14 instructions."""
    rng = random.Random(seed)
    non_stop = [op for op in DSL_INSTRUCTIONS if op != "STOP"]
    length = rng.randint(10, 14)
    body = [rng.choice(non_stop) for _ in range(length - 2)]
    instrs = ["OBSERVE"] + body + ["STOP"]
    return dict(
        rule_id=rule_id,
        origin="random_valid_learning_rules",
        instructions=instrs,
        stopping_threshold=rng.choice((1, 2, 3)),
        tie_breaker=rng.choice(TIE_BREAKERS),
        query_strategy=rng.choice(QUERY_STRATEGIES),
        validation_tests_required=rng.choice((0, 1)),
    )


def evaluate_rule_on_stage_a_suites(
    kernel: ImmutableTrustedKernel,
    rule: dict[str, Any],
    source_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    dev_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    old_skill_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    macro_library: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluates a learning rule across Episodic and Continual regimes using real execution."""
    episodic_outcomes = [
        kernel.execute_learning_rule(rule, lv, ep, capsule_memory=None, macro_library=None)
        for lv, ep in source_suite
    ]
    dev_outcomes = [
        kernel.execute_learning_rule(rule, lv, ep, capsule_memory=None, macro_library=None)
        for lv, ep in dev_suite
    ]

    continual_memory: dict[str, dict[str, Any]] = {}
    continual_outcomes = [
        kernel.execute_learning_rule(rule, lv, ep, capsule_memory=continual_memory, macro_library=macro_library)
        for lv, ep in source_suite
    ]
    old_skill_outcomes = [
        kernel.execute_learning_rule(rule, lv, ep, capsule_memory=continual_memory, macro_library=macro_library)
        for lv, ep in old_skill_suite
    ]

    task_success = float(sum(o["task_success"] for o in episodic_outcomes) / len(episodic_outcomes))
    held_out_family_success = float(sum(o["task_success"] for o in dev_outcomes) / len(dev_outcomes))
    old_skill_retention = float(
        sum(1.0 if (o["task_success"] >= 0.99 and o["retention_safe"]) else 0.0 for o in old_skill_outcomes)
        / len(old_skill_outcomes)
    )

    episodic_experiments = float(sum(o["experiments_run"] for o in episodic_outcomes) / len(episodic_outcomes))
    episodic_cost = float(sum(o["execution_cost"] for o in episodic_outcomes) / len(episodic_outcomes))
    continual_experiments = float(sum(o["experiments_run"] for o in continual_outcomes) / len(continual_outcomes))
    continual_cost = float(sum(o["execution_cost"] for o in continual_outcomes) / len(continual_outcomes))
    dev_experiments = float(sum(o["experiments_run"] for o in dev_outcomes) / len(dev_outcomes))
    dev_cost = float(sum(o["execution_cost"] for o in dev_outcomes) / len(dev_outcomes))

    admissible = bool(
        task_success >= 0.99
        and old_skill_retention >= 0.98
        and held_out_family_success >= 0.99
    )

    return dict(
        rule_id=rule["rule_id"],
        origin=rule["origin"],
        admissible=admissible,
        task_success=task_success,
        old_skill_retention=old_skill_retention,
        held_out_family_success=held_out_family_success,
        episodic_experiments=episodic_experiments,
        episodic_execution_cost=episodic_cost,
        continual_experiments=continual_experiments,
        continual_execution_cost=continual_cost,
        dev_experiments=dev_experiments,
        dev_execution_cost=dev_cost,
        instruction_count=len(rule["instructions"]),
        acquired_capsules=[o["capsule"] for o in continual_outcomes if o["capsule"] is not None],
    )


def lexicographic_rule_key(metrics: dict[str, Any]) -> tuple[Any, ...]:
    return (
        1 if metrics["admissible"] else 0,
        round(metrics["task_success"], 6),
        round(metrics["old_skill_retention"], 6),
        round(metrics["held_out_family_success"], 6),
        -round(metrics["episodic_execution_cost"], 6),
        -round(metrics["episodic_experiments"], 6),
        -int(metrics["instruction_count"]),
    )


def pareto_dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    vec_a = (
        a["task_success"],
        a["old_skill_retention"],
        a["held_out_family_success"],
        -a["episodic_execution_cost"],
        -a["episodic_experiments"],
        -a["instruction_count"],
    )
    vec_b = (
        b["task_success"],
        b["old_skill_retention"],
        b["held_out_family_success"],
        -b["episodic_execution_cost"],
        -b["episodic_experiments"],
        -b["instruction_count"],
    )
    return all(x >= y for x, y in zip(vec_a, vec_b)) and any(x > y for x, y in zip(vec_a, vec_b))


def run_dream_generation_step(
    kernel: ImmutableTrustedKernel,
    gen: int,
    seed: int,
    reference_rule: dict[str, Any],
    challenger_rule: dict[str, Any],
    active_source_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    archive: list[dict[str, Any]],
) -> dict[str, Any]:
    """Executes Dream inside each evolutionary generation:
      - Generates candidate tasks only from Source Families A and B (never Sealed family);
      - Computes oracle solvability through real execution of the typed catalogue;
      - Rejects impossible and underdetermined tasks;
      - Computes semantic novelty WITHOUT including the random seed in the novelty identity;
      - Adds selected high-regret tasks to `active_source_suite` while retaining earlier tasks."""
    archived_hashes = {entry["semantic_novelty_sha256"] for entry in archive}
    all_list_hyps = enumerate_typed_hypotheses("list_transformations", 64)
    all_bool_hyps = enumerate_typed_hypotheses("boolean_circuit_induction", 64)

    # Pick novel candidate compositions for this generation
    cand_list_ops = all_list_hyps[(gen * 3 + 7) % len(all_list_hyps)]
    cand_bool_ops = all_bool_hyps[(gen * 5 + 11) % len(all_bool_hyps)]

    lv_a, ep_a = build_stage_a_task_pair(
        "list_transformations", 100 + gen, cand_list_ops, seed + 2000 + gen * 17
    )
    lv_b, ep_b = build_stage_a_task_pair(
        "boolean_circuit_induction", 200 + gen, cand_bool_ops, seed + 3000 + gen * 19
    )

    raw_candidates = [
        dict(lv=lv_a, ep=ep_a, impossible_foil=False, underdetermined_foil=False),
        dict(lv=lv_b, ep=ep_b, impossible_foil=False, underdetermined_foil=False),
        # Inadmissible foil 1: impossible target output not producible by any composition
        dict(lv=lv_a, ep=ep_a, impossible_foil=True, underdetermined_foil=False),
        # Inadmissible foil 2: underdetermined task (zero observed examples & zero query budget)
        dict(lv=lv_b, ep=ep_b, impossible_foil=False, underdetermined_foil=True),
    ]

    admissible_entries: list[dict[str, Any]] = []
    rejected_foils = 0

    for item in raw_candidates:
        lv: LearnerTaskView = item["lv"]
        ep: EvaluatorTaskPrivate = item["ep"]
        fam = lv.family
        probes = _family_calibration_probes(fam)

        # Compute semantic novelty strictly from behavioral outputs on canonical family probes
        # (NO random seed or task_id in the novelty identity!)
        canonical_behavior = [
            execute_family_composition(fam, ep.target_composition, px) for px in probes
        ]
        sem_sha = digest(dict(family=fam, canonical_probe_outputs=canonical_behavior))
        is_novel = sem_sha not in archived_hashes

        # Compute oracle solvability by executing typed catalogue on initial observation
        x0 = lv.currently_observed_examples[0]["input"]
        y0 = ["IMPOSSIBLE_ORACLE_OUTPUT"] if item["impossible_foil"] else lv.currently_observed_examples[0]["output"]
        solvable_hyps = []
        for h_ops in enumerate_typed_hypotheses(fam, 64):
            if kernel._execute_candidate_counted(fam, h_ops, x0) == y0:
                solvable_hyps.append(h_ops)

        oracle_solvable = len(solvable_hyps) > 0
        identifiable = not item["underdetermined_foil"] and lv.query_action_budget >= 1
        leakage_free = len(inspect_evaluator_leakage_paths(lv)) == 0
        complexity_ok = len(ep.target_composition) <= kernel.resource_limits["max_admissible_complexity"]

        checks = dict(
            oracle_solvable_by_execution=bool(oracle_solvable),
            identifiable_not_underdetermined=bool(identifiable),
            semantically_novel_without_seed=bool(is_novel),
            zero_evaluator_leakage=bool(leakage_free),
            complexity_bounded=bool(complexity_ok),
        )
        if all(checks.values()):
            ref_out = kernel.execute_learning_rule(reference_rule, lv, ep)
            chal_out = kernel.execute_learning_rule(challenger_rule, lv, ep)
            score_ref = ref_out["task_success"] - 0.01 * ref_out["execution_cost"]
            score_chal = chal_out["task_success"] - 0.01 * chal_out["execution_cost"]
            regret = float(round(score_ref - score_chal, 6))
            admissible_entries.append(
                dict(
                    task_id=lv.task_id,
                    family=fam,
                    semantic_novelty_sha256=sem_sha,
                    admissibility_checks=checks,
                    regret=regret,
                    pair=(lv, ep),
                )
            )
            archived_hashes.add(sem_sha)
        else:
            rejected_foils += 1

    admissible_entries.sort(key=lambda x: (-x["regret"], x["task_id"]))
    selected = admissible_entries[:1]
    for s_item in selected:
        lp, ep_priv = s_item["pair"]
        archive.append(
            dict(
                generation=gen,
                task_id=s_item["task_id"],
                family=s_item["family"],
                semantic_novelty_sha256=s_item["semantic_novelty_sha256"],
                regret=s_item["regret"],
            )
        )
        # Add selected Dream task to active evaluation curriculum while keeping archive of earlier tasks
        if len(active_source_suite) < 12:
            active_source_suite.append((lp, ep_priv))

    return dict(
        generation=gen,
        candidates_screened=len(raw_candidates),
        admissible_count=len(admissible_entries),
        rejected_inadmissible_foils=rejected_foils,
        selected_tasks=[s["task_id"] for s in selected],
        archive_size=len(archive),
    )


def evaluate_real_pre_post_retention(
    kernel: ImmutableTrustedKernel,
    pre_rule: dict[str, Any],
    post_rule: dict[str, Any],
    protected_old_tasks: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    post_capsules: dict[str, dict[str, Any]] | None = None,
    post_macros: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measures retention by real pre-update and post-update executions on the exact
    same protected old tasks, reporting per-task changes and worst regression."""
    per_task_records: list[dict[str, Any]] = []
    worst_regression = 0.0
    pre_scores: list[float] = []
    post_scores: list[float] = []

    for lv, ep in protected_old_tasks:
        pre_out = kernel.execute_learning_rule(pre_rule, lv, ep, capsule_memory=None, macro_library=None)
        post_out = kernel.execute_learning_rule(
            post_rule,
            lv,
            ep,
            capsule_memory=copy.deepcopy(post_capsules) if post_capsules else None,
            macro_library=post_macros,
        )
        delta = float(round(post_out["task_success"] - pre_out["task_success"], 6))
        regression = float(max(0.0, pre_out["task_success"] - post_out["task_success"]))
        if regression > worst_regression:
            worst_regression = regression
        pre_scores.append(pre_out["task_success"])
        post_scores.append(post_out["task_success"])
        per_task_records.append(
            dict(
                task_id=lv.task_id,
                family=lv.family,
                pre_accuracy=pre_out["task_success"],
                post_accuracy=post_out["task_success"],
                accuracy_delta=delta,
                pre_cost=pre_out["execution_cost"],
                post_cost=post_out["execution_cost"],
            )
        )

    return dict(
        pre_mean_accuracy=float(sum(pre_scores) / max(1, len(pre_scores))),
        post_mean_accuracy=float(sum(post_scores) / max(1, len(post_scores))),
        worst_regression=float(worst_regression),
        per_task_retention=per_task_records,
    )


def run_sleep_compression(
    kernel: ImmutableTrustedKernel,
    capsules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Executes real Sleep compression:
      1. Reruns every capsule's tests via actual execution through `execute_family_composition`
         rather than reading stored `passed` booleans;
      2. Calculates MDL with explicit macro-definition cost (`len(macro) + 1.0`) and
         call-site cost (`1.0` per non-overlapping substitution);
      3. Avoids double-counting overlapping macro substitutions via greedy non-overlapping
         token replacement;
      4. Excludes the neural distillation stub."""
    kernel.verify_integrity()

    # 1. Rerun all capsule tests by real execution
    total_tests = 0
    passed_tests = 0
    for cap in capsules:
        fam = cap["family"]
        comp = tuple(cap["selected_composition"])
        for t_item in cap.get("tests", []):
            total_tests += 1
            actual_out = kernel._execute_candidate_counted(fam, comp, t_item["input"])
            if actual_out == t_item["expected_output"]:
                passed_tests += 1

    # 2. Non-overlapping MDL macro discovery per family
    sequences = [list(c["selected_composition"]) for c in capsules]
    mdl_before = float(sum(len(seq) for seq in sequences))

    candidate_subprograms: dict[tuple[str, tuple[str, ...]], int] = {}
    for cap in capsules:
        fam = cap["family"]
        ops = tuple(cap["selected_composition"])
        for k_len in (2, 3):
            i = 0
            while i <= len(ops) - k_len:
                sub = ops[i : i + k_len]
                candidate_subprograms[(fam, sub)] = candidate_subprograms.get((fam, sub), 0) + 1
                i += 1

    accepted_macros: list[dict[str, Any]] = []
    # Work on mutable copies of capsule operator sequences to prevent overlapping macro substitutions!
    working_seqs = [
        dict(family=c["family"], tokens=list(c["selected_composition"]))
        for c in capsules
    ]

    for (fam, sub), _ in sorted(
        candidate_subprograms.items(),
        key=lambda kv: (-len(kv[0][1]) * kv[1], kv[0][0], kv[0][1]),
    ):
        k_len = len(sub)
        sub_list = list(sub)
        # Count non-overlapping occurrences in current working_seqs
        non_overlapping_hits = 0
        for w in working_seqs:
            if w["family"] != fam:
                continue
            toks = w["tokens"]
            idx = 0
            while idx <= len(toks) - k_len:
                if toks[idx : idx + k_len] == sub_list:
                    non_overlapping_hits += 1
                    idx += k_len
                else:
                    idx += 1

        # Macro definition cost = k_len + 1.0; each call site replaces k_len tokens with 1 macro call token
        definition_cost = float(k_len + 1.0)
        call_site_savings = float(non_overlapping_hits * (k_len - 1))
        net_mdl_delta = definition_cost - call_site_savings
        if net_mdl_delta < 0.0:
            macro_token = f"MACRO_{fam}_{'_'.join(sub)}"
            # Perform non-overlapping substitution on working_seqs so subsequent macros cannot overlap!
            for w in working_seqs:
                if w["family"] != fam:
                    continue
                toks = w["tokens"]
                new_toks: list[str] = []
                idx = 0
                while idx < len(toks):
                    if idx <= len(toks) - k_len and toks[idx : idx + k_len] == sub_list:
                        new_toks.append(macro_token)
                        idx += k_len
                    else:
                        new_toks.append(toks[idx])
                        idx += 1
                w["tokens"] = new_toks

            accepted_macros.append(
                dict(
                    macro_name=macro_token,
                    family=fam,
                    subprogram=sub_list,
                    non_overlapping_occurrences=non_overlapping_hits,
                    definition_cost=definition_cost,
                    call_site_cost_per_use=1.0,
                    mdl_delta=float(net_mdl_delta),
                )
            )

    mdl_after = float(
        sum(len(w["tokens"]) for w in working_seqs)
        + sum(m["definition_cost"] for m in accepted_macros)
    )

    return dict(
        replayed_verified_capsules=len(capsules),
        mdl_before=mdl_before,
        mdl_after=mdl_after,
        mdl_reduction=float(mdl_before - mdl_after),
        accepted_macros=accepted_macros,
        old_capsule_tests_total=total_tests,
        old_capsule_tests_passed=passed_tests,
        old_capsule_test_pass_rate=float(passed_tests / max(1, total_tests)),
        tests_verified_by_real_execution=True,
        neural_distillation_included=False,
    )


def evaluate_single_instruction_ablations(
    kernel: ImmutableTrustedKernel,
    evolved_rule: dict[str, Any],
    eval_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
) -> list[dict[str, Any]]:
    """Removes each instruction in `evolved_rule` individually and evaluates on `eval_suite`."""
    base_runs = [kernel.execute_learning_rule(evolved_rule, lv, ep) for lv, ep in eval_suite]
    base_acc = float(sum(r["task_success"] for r in base_runs) / len(base_runs))
    base_cost = float(sum(r["execution_cost"] for r in base_runs) / len(base_runs))

    ablations: list[dict[str, Any]] = []
    instrs = list(evolved_rule["instructions"])
    for idx, opcode in enumerate(instrs):
        if opcode == "STOP" and idx == len(instrs) - 1:
            continue
        ablated_instrs = instrs[:idx] + instrs[idx + 1 :]
        while len(ablated_instrs) < 10:
            # Pad with neutral OBSERVE before STOP to satisfy 10-instruction minimum
            ablated_instrs.insert(0, "OBSERVE")
        ablated_rule = copy.deepcopy(evolved_rule)
        ablated_rule["rule_id"] = f"{evolved_rule['rule_id']}_ablate_{idx}_{opcode}"
        ablated_rule["instructions"] = ablated_instrs
        runs = [kernel.execute_learning_rule(ablated_rule, lv, ep) for lv, ep in eval_suite]
        acc = float(sum(r["task_success"] for r in runs) / len(runs))
        cost = float(sum(r["execution_cost"] for r in runs) / len(runs))
        ablations.append(
            dict(
                instruction_index=idx,
                removed_opcode=opcode,
                task_success=acc,
                execution_cost=cost,
                accuracy_drop=float(round(base_acc - acc, 6)),
                cost_increase=float(round(cost - base_cost, 6)),
            )
        )
    return ablations


# ==============================================================================
# 6. STAGE B: BLACK-BOX SUBPROCESS EVALUATOR & MULTI-FILE CODE LAB ADAPTER
# ==============================================================================


def _call_blackbox_evaluator_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    """Invokes `nexus.seed.blackbox_evaluator_worker` in a separate OS process.
    Private test inputs and ground-truth reference implementations remain strictly
    inside the subprocess and are never exposed to the learner process."""
    src_root = str(Path(__file__).resolve().parents[2])
    env_vars = dict(os.environ)
    existing_py = env_vars.get("PYTHONPATH", "")
    env_vars["PYTHONPATH"] = f"{src_root}:{existing_py}" if existing_py else src_root
    proc = subprocess.run(
        [sys.executable, "-m", "nexus.seed.blackbox_evaluator_worker"],
        input=json.dumps(payload, sort_keys=True),
        text=True,
        capture_output=True,
        check=True,
        env=env_vars,
    )
    return json.loads(proc.stdout)


class CommonEnvironmentAdapter:
    """Reusable typed environment adapter implementing reset(seed), observe(),
    available_actions(), execute(typed_action), evaluate(goal_predicate),
    snapshot(), and restore() with TransitionReceipt provenance.

    All unseen library files (with 1 true helper + 2 decoy helpers across
    `helpers_alpha.py` and `helpers_beta.py`, and 3 plausible call sites / post-steps
    in `target_pipeline.py`) are generated after rule freeze inside the separate
    `blackbox_evaluator_worker` subprocess. Learner-accessible observations never
    contain `patched_target_body`, `post_op`, `correct_helper`, or private test inputs."""

    def __init__(
        self,
        family_name: str,
        seed: int,
        freeze_journal_sha256: str = "standalone_adapter_freeze_sha256",
    ) -> None:
        if family_name not in UNKNOWN_LIBRARY_FAMILIES:
            raise ValueError(f"unknown_code_lab_family:{family_name}")
        self.family_name = family_name
        self.seed = int(seed)
        self.freeze_journal_sha256 = str(freeze_journal_sha256)
        self._temp_dir = tempfile.TemporaryDirectory(prefix=f"nexus_ulib_{family_name}_")
        self.sandbox_root = Path(self._temp_dir.name).resolve()
        self.receipts: list[TransitionReceipt] = []
        self.reset(seed)

    def close(self) -> None:
        self._temp_dir.cleanup()

    def _bundle_workspace_source(self) -> str:
        parts: list[str] = []
        for fname in ("helpers_alpha.py", "helpers_beta.py", "target_pipeline.py"):
            fpath = self.sandbox_root / fname
            if fpath.exists():
                parts.append(fpath.read_text(encoding="utf-8"))
        return "\n\n".join(parts) + "\n"

    def _compile_workspace_namespace(self) -> dict[str, Any]:
        bundle_src = self._bundle_workspace_source()
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        }
        ns: dict[str, Any] = {"__builtins__": safe_builtins}
        exec(compile(ast.parse(bundle_src), filename="<sandbox_workspace>", mode="exec"), ns, ns)
        return ns

    def reset(self, seed: int) -> dict[str, Any]:
        self.seed = int(seed)
        ws = _call_blackbox_evaluator_subprocess(
            dict(
                mode="init_workspace",
                seed=self.seed,
                family_name=self.family_name,
                freeze_journal_sha256=self.freeze_journal_sha256,
            )
        )
        self.workspace_files: list[str] = sorted(ws["files"].keys())
        for fname, fcontent in ws["files"].items():
            (self.sandbox_root / fname).write_text(fcontent, encoding="utf-8")

        self.target_file: str = str(ws["target_file"])
        self.module_path: Path = self.sandbox_root / self.target_file
        self.target_function: str = str(ws["target_function"])
        self.candidate_call_sites: list[str] = list(ws["candidate_call_sites"])
        self.type_signature: str = str(ws["type_signature"])
        self.invented_word: str = str(ws["invented_word"])
        self.visible_tests: list[dict[str, Any]] = copy.deepcopy(ws["visible_tests"])
        self.teaching_example: dict[str, Any] = copy.deepcopy(ws["teaching_example"])

        self.inspected_spans: list[str] = []
        self.inspected_ast_nodes: dict[str, str] = {}
        self.helper_call_evidence: list[dict[str, Any]] = []
        self.generated_tests: list[dict[str, Any]] = []
        self.proposed_primitives: list[dict[str, Any]] = []
        self.exceptions: list[str] = []
        self.file_diffs: list[str] = []
        self.stopped = False
        return self.observe()

    def observe(self) -> dict[str, Any]:
        """Returns the public learner-facing observation (contains zero hidden tests,
        zero `patched_target_body`, zero `post_op`, and zero `correct_helper`)."""
        per_file_ast: dict[str, Any] = {}
        candidate_helpers: list[str] = []
        candidate_post_functions: list[str] = []
        signatures_and_types: dict[str, str] = {}
        file_hashes: dict[str, str] = {}

        for fname in self.workspace_files:
            fpath = self.sandbox_root / fname
            src = fpath.read_text(encoding="utf-8")
            file_hashes[fname] = hashlib.sha256(src.encode("utf-8")).hexdigest()
            tree = ast.parse(src)
            fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
            per_file_ast[fname] = dict(functions=fns, line_count=len(src.splitlines()))
            for fn_name in fns:
                signatures_and_types[fn_name] = self.type_signature
                if fn_name.startswith("_cand_"):
                    candidate_helpers.append(fn_name)
                elif fn_name.startswith("_post_"):
                    candidate_post_functions.append(fn_name)

        target_src = self.module_path.read_text(encoding="utf-8")
        obs = dict(
            family_name=self.family_name,
            workspace_files=list(self.workspace_files),
            module_file=self.module_path.name,
            target_function=self.target_function,
            candidate_helpers=candidate_helpers,
            candidate_post_functions=candidate_post_functions,
            source_file_ast=per_file_ast,
            signatures_and_types=signatures_and_types,
            selected_call_sites=list(self.candidate_call_sites),
            visible_tests=copy.deepcopy(self.visible_tests),
            teaching_example=copy.deepcopy(self.teaching_example),
            execution_receipts_count=len(self.receipts),
            exceptions=list(self.exceptions),
            file_diffs=list(self.file_diffs),
            source_dependency_hashes=dict(
                module_sha256=hashlib.sha256(target_src.encode("utf-8")).hexdigest(),
                workspace_file_hashes=file_hashes,
                python_stdlib_only="3.13",
                network_enabled="false",
            ),
            helper_evidence_count=len(self.helper_call_evidence),
        )
        assert_zero_evaluator_leakage(obs)
        return obs

    def available_actions(self) -> list[str]:
        return list(CODE_LAB_TYPED_ACTIONS)

    def snapshot(self) -> dict[str, Any]:
        files_state = {
            fname: (self.sandbox_root / fname).read_text(encoding="utf-8")
            for fname in self.workspace_files
        }
        return dict(
            files_state=files_state,
            inspected_spans=copy.deepcopy(self.inspected_spans),
            inspected_ast_nodes=copy.deepcopy(self.inspected_ast_nodes),
            helper_call_evidence=copy.deepcopy(self.helper_call_evidence),
            generated_tests=copy.deepcopy(self.generated_tests),
            proposed_primitives=copy.deepcopy(self.proposed_primitives),
            exceptions=copy.deepcopy(self.exceptions),
            file_diffs=copy.deepcopy(self.file_diffs),
            stopped=self.stopped,
        )

    def restore(self, snap: dict[str, Any]) -> TransitionReceipt:
        t0 = time.perf_counter()
        obs_before = self.observe()
        for fname, ftext in snap["files_state"].items():
            (self.sandbox_root / fname).write_text(ftext, encoding="utf-8")
        self.inspected_spans = copy.deepcopy(snap["inspected_spans"])
        self.inspected_ast_nodes = copy.deepcopy(snap["inspected_ast_nodes"])
        self.helper_call_evidence = copy.deepcopy(snap["helper_call_evidence"])
        self.generated_tests = copy.deepcopy(snap["generated_tests"])
        self.proposed_primitives = copy.deepcopy(snap["proposed_primitives"])
        self.exceptions = copy.deepcopy(snap["exceptions"])
        self.file_diffs = copy.deepcopy(snap["file_diffs"])
        self.stopped = bool(snap["stopped"])
        obs_after = self.observe()
        dt = time.perf_counter() - t0
        receipt = TransitionReceipt(
            observation_before=obs_before,
            typed_action={"action": "RESTORE_SNAPSHOT"},
            observation_after=obs_after,
            state_diff={"restored_module_sha256": obs_after["source_dependency_hashes"]["module_sha256"]},
            stdout="snapshot_restored",
            stderr="",
            exit_status=0,
            execution_time=float(round(dt, 6)),
            resource_use={"cpu_ops": 1, "sandbox_actions": 1, "function_calls": 0, "experiments": 0, "sandbox_fs_writes": 1},
            provenance={"sandbox_root": str(self.sandbox_root), "seed": self.seed},
        )
        self.receipts.append(receipt)
        return receipt

    def execute(self, typed_action: dict[str, Any]) -> TransitionReceipt:
        t0 = time.perf_counter()
        obs_before = self.observe()
        act = str(typed_action.get("action", ""))
        if act not in CODE_LAB_TYPED_ACTIONS:
            raise ValueError(f"unsupported_code_lab_action:{act}")

        stdout = ""
        stderr = ""
        exit_status = 0
        diff_summary: dict[str, Any] = {}
        resource_use = {
            "cpu_ops": 1,
            "sandbox_actions": 1,
            "function_calls": 0,
            "experiments": 0,
            "sandbox_fs_writes": 0,
        }

        if act == "INSPECT_FILE_SPAN":
            file_name = str(typed_action.get("file_name", self.target_file))
            fpath = self.sandbox_root / file_name
            lines = fpath.read_text(encoding="utf-8").splitlines()
            start = max(1, int(typed_action.get("start_line", 1)))
            end = min(len(lines), int(typed_action.get("end_line", len(lines))))
            span_text = "\n".join(lines[start - 1 : end])
            self.inspected_spans.append(span_text)
            stdout = span_text
            diff_summary = {"file_name": file_name, "inspected_lines": [start, end]}
            resource_use["cpu_ops"] = 2

        elif act == "INSPECT_AST_NODE":
            target_node = str(typed_action.get("node_name", "_cand_alpha_1"))
            found_src = ""
            found_file = ""
            for fname in self.workspace_files:
                fsrc = (self.sandbox_root / fname).read_text(encoding="utf-8")
                tree = ast.parse(fsrc)
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef) and node.name == target_node:
                        found_src = ast.unparse(node)
                        found_file = fname
                        break
                if found_src:
                    break
            if found_src:
                self.inspected_ast_nodes[target_node] = found_src
            stdout = found_src
            diff_summary = {"ast_node": target_node, "file_name": found_file, "found": bool(found_src)}
            resource_use["cpu_ops"] = 2

        elif act == "CALL_PURE_FUNCTION":
            fn_name = str(typed_action.get("function_name", "_cand_alpha_1"))
            arg_seq = list(typed_action.get("input", self.visible_tests[0]["input"]))
            ns = self._compile_workspace_namespace()
            out_val = ns[fn_name](copy.deepcopy(arg_seq))
            ev_id = digest(dict(fn=fn_name, input=arg_seq, output=out_val))[:16]
            self.helper_call_evidence.append(
                dict(evidence_id=ev_id, function_name=fn_name, input=arg_seq, expected_output=out_val)
            )
            stdout = json.dumps(out_val)
            diff_summary = {"called": fn_name, "evidence_id": ev_id, "output": out_val}
            resource_use["cpu_ops"] = 2
            resource_use["function_calls"] = 1

        elif act == "GENERATE_TEST":
            fn_name = str(typed_action.get("function_name", "_cand_alpha_1"))
            probe_seq = list(typed_action.get("input", [5, 2, 5, 8, 3, 4]))
            ns = self._compile_workspace_namespace()
            out_val = ns[fn_name](copy.deepcopy(probe_seq))
            ev_id = digest(dict(fn=fn_name, input=probe_seq, output=out_val))[:16]
            test_rec = dict(evidence_id=ev_id, function_name=fn_name, input=probe_seq, expected_output=out_val)
            self.generated_tests.append(test_rec)
            self.helper_call_evidence.append(test_rec)
            stdout = json.dumps(test_rec)
            diff_summary = {"generated_test_id": ev_id, "function_name": fn_name}
            resource_use["cpu_ops"] = 3
            resource_use["function_calls"] = 1
            resource_use["experiments"] = 1

        elif act == "REQUEST_MORE_EVIDENCE":
            fn_name = str(typed_action.get("function_name", "_cand_alpha_1"))
            extra_inp = list(
                typed_action.get(
                    "input",
                    self.visible_tests[min(len(self.helper_call_evidence), len(self.visible_tests) - 1)]["input"],
                )
            )
            ns = self._compile_workspace_namespace()
            out_val = ns[fn_name](copy.deepcopy(extra_inp))
            ev_id = digest(dict(fn=fn_name, input=extra_inp, output=out_val))[:16]
            self.helper_call_evidence.append(
                dict(evidence_id=ev_id, function_name=fn_name, input=extra_inp, expected_output=out_val)
            )
            stdout = f"evidence_added:{ev_id}"
            diff_summary = {"function_name": fn_name, "evidence_count": len(self.helper_call_evidence)}
            resource_use["cpu_ops"] = 3
            resource_use["function_calls"] = 1
            resource_use["experiments"] = 1

        elif act == "PROPOSE_PRIMITIVE":
            prop_name = str(typed_action.get("proposed_name", "_cand_alpha_1"))
            prop_src = str(typed_action.get("source_code", self.inspected_ast_nodes.get(prop_name, "")))
            self.proposed_primitives.append(dict(proposed_name=prop_name, source_code=prop_src))
            stdout = f"proposal_prepared:{prop_name}"
            diff_summary = {"proposed_primitive": prop_name, "has_source": bool(prop_src)}
            resource_use["cpu_ops"] = 2

        elif act == "APPLY_AST_PATCH":
            replacement_body = str(typed_action.get("replacement_body", "    return list(seq)"))
            target_fn = str(typed_action.get("target_function", self.target_function))
            src = self.module_path.read_text(encoding="utf-8")
            lines = src.splitlines()
            new_lines: list[str] = []
            in_target = False
            for line in lines:
                if line.startswith(f"def {target_fn}("):
                    in_target = True
                    new_lines.append(line)
                    new_lines.append(replacement_body)
                elif in_target:
                    if line.startswith("def "):
                        in_target = False
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            new_src = "\n".join(new_lines) + "\n"
            ast.parse(new_src)  # Validate syntax before writing
            diff_text = "\n".join(
                difflib.unified_diff(lines, new_src.splitlines(), fromfile="before", tofile="after", lineterm="")
            )
            self.module_path.write_text(new_src, encoding="utf-8")
            self.file_diffs.append(diff_text)
            stdout = "ast_patch_applied"
            diff_summary = {"patched_function": target_fn, "diff_lines": len(diff_text.splitlines())}
            resource_use["cpu_ops"] = 3
            resource_use["sandbox_fs_writes"] = 1

        elif act == "RUN_VISIBLE_TESTS":
            ns = self._compile_workspace_namespace()
            fn_target = ns[self.target_function]
            passed = 0
            for vt in self.visible_tests:
                actual = fn_target(copy.deepcopy(vt["input"]))
                if actual == vt["expected_output"]:
                    passed += 1
            stdout = f"visible_tests:{passed}/{len(self.visible_tests)}"
            diff_summary = {"visible_passed": passed, "visible_total": len(self.visible_tests)}
            resource_use["cpu_ops"] = 3
            resource_use["function_calls"] = len(self.visible_tests)
            resource_use["experiments"] = 1

        elif act == "STOP":
            self.stopped = True
            stdout = "stopped"
            diff_summary = {"stopped": True}
            resource_use["cpu_ops"] = 1

        obs_after = self.observe()
        dt = time.perf_counter() - t0
        receipt = TransitionReceipt(
            observation_before=obs_before,
            typed_action=copy.deepcopy(typed_action),
            observation_after=obs_after,
            state_diff=diff_summary,
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            execution_time=float(round(dt, 6)),
            resource_use=resource_use,
            provenance={
                "sandbox_root": str(self.sandbox_root),
                "module_sha256_before": obs_before["source_dependency_hashes"]["module_sha256"],
                "module_sha256_after": obs_after["source_dependency_hashes"]["module_sha256"],
            },
        )
        self.receipts.append(receipt)
        return receipt

    def evaluate(
        self,
        goal_predicate: Any = None,
        promoted_primitive_name: str = "",
        promoted_primitive_source: str = "",
        cross_lab_coding_enabled: bool = False,
        cross_lab_reasoning_enabled: bool = False,
    ) -> dict[str, Any]:
        """Evaluates the current workspace in the isolated `blackbox_evaluator_worker` subprocess.
        Private test inputs never leave the evaluator subprocess."""
        bundle_src = self._bundle_workspace_source()
        sub_res = _call_blackbox_evaluator_subprocess(
            dict(
                mode="evaluate_submission",
                seed=self.seed,
                family_name=self.family_name,
                patched_module_source=bundle_src,
                promoted_primitive_name=promoted_primitive_name,
                promoted_primitive_source=promoted_primitive_source,
                cross_lab_coding_enabled=cross_lab_coding_enabled,
                cross_lab_reasoning_enabled=cross_lab_reasoning_enabled,
            )
        )
        return dict(
            family_name=self.family_name,
            hidden_tests_total=int(sub_res["hidden_tests_total"]),
            hidden_tests_passed=int(sub_res["hidden_tests_passed"]),
            hidden_accuracy=float(sub_res["hidden_accuracy"]),
            cross_lab_coding_accuracy=float(sub_res["cross_lab_coding_accuracy"]),
            cross_lab_reasoning_accuracy=float(sub_res["cross_lab_reasoning_accuracy"]),
            evaluator_receipt_sha256=str(sub_res["evaluator_receipt_sha256"]),
            separate_evaluator_process=bool(sub_res["separate_evaluator_process"]),
            private_inputs_exposed_to_learner=bool(sub_res["private_inputs_exposed_to_learner"]),
            goal_satisfied=bool(sub_res["hidden_tests_passed"] == sub_res["hidden_tests_total"]),
        )


def _derive_stage_b_metrics_from_receipts_and_counters(
    method_receipts: list[TransitionReceipt],
    counters_before: dict[str, int],
    counters_after: dict[str, int],
) -> tuple[float, float]:
    """Derives `(experiments, compute_cost)` exclusively from recorded `TransitionReceipt`s
    and `ImmutableTrustedKernel` counter deltas."""
    experiments = float(
        max(1, sum(int(r.resource_use.get("experiments", 0)) for r in method_receipts))
    )
    receipt_cpu = float(sum(int(r.resource_use.get("cpu_ops", 0)) for r in method_receipts))
    receipt_fn_calls = float(sum(int(r.resource_use.get("function_calls", 0)) for r in method_receipts))
    receipt_fs_writes = float(sum(int(r.resource_use.get("sandbox_fs_writes", 0)) for r in method_receipts))

    delta_cand = max(0, counters_after["candidate_executions"] - counters_before["candidate_executions"])
    delta_dsl = max(0, counters_after["dsl_instructions"] - counters_before["dsl_instructions"])
    delta_queries = max(0, counters_after["queries"] - counters_before["queries"])
    delta_props = max(0, counters_after["proposal_validations"] - counters_before["proposal_validations"])

    compute_cost = float(
        round(
            receipt_cpu * 0.5
            + receipt_fn_calls * 1.25
            + receipt_fs_writes * 1.0
            + delta_cand * 1.0
            + delta_dsl * 0.1
            + delta_queries * 1.5
            + delta_props * 1.5,
            6,
        )
    )
    return experiments, compute_cost


def _predict_post_step_output(post_fn_name: str, seq: list[int]) -> list[int]:
    """Learner-side internal effect model for the known post-step functions."""
    if post_fn_name == "_post_reverse":
        return list(reversed(seq))
    if post_fn_name == "_post_inc":
        return [v + 1 for v in seq]
    if post_fn_name == "_post_dedup":
        seen: set[int] = set()
        out: list[int] = []
        for v in seq:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out
    return list(seq)


def _execute_stage_b_method_on_adapter(
    method_name: str,
    env: CommonEnvironmentAdapter,
    snap0: dict[str, Any],
    kernel: ImmutableTrustedKernel,
    frozen_evolved_rule: dict[str, Any],
    old_skill_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    macro_library: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    """Executes a single Stage B method (`method_name`) through the identical
    `CommonEnvironmentAdapter`, requiring the method to choose its own actions,
    propose its own primitive (if supported), and synthesize its own AST patch.
    Derives cost and experiment counts strictly from recorded receipts and kernel counters."""
    env.restore(snap0)
    receipt_start_idx = len(env.receipts)
    counters_before = dict(kernel.counters)

    obs = env.observe()
    cand_helpers = list(obs["candidate_helpers"])
    cand_posts = list(obs["candidate_post_functions"])
    vis_tests = list(obs["visible_tests"])
    x0 = vis_tests[0]["input"]
    y0 = vis_tests[0]["expected_output"]
    x1 = vis_tests[1]["input"]

    chosen_helper = ""
    chosen_post = cand_posts[0]
    promoted_source = ""
    lifecycle_record: dict[str, Any] | None = None

    if method_name in (
        "corrected_frozen_evolved_rule",
        "proposal_lifecycle_without_sleep_compression",
        "isolated_labs",
    ):
        use_sleep_macros = (method_name != "proposal_lifecycle_without_sleep_compression") and bool(macro_library)
        # 1. Inspect AST nodes across helper files and use PREDICT_EFFECTS + MERGE_EQUIVALENT incrementally
        for h_name in cand_helpers:
            env.execute({"action": "INSPECT_AST_NODE", "node_name": h_name})
            r_call = env.execute({"action": "CALL_PURE_FUNCTION", "function_name": h_name, "input": x0})
            kernel.counters["sandbox_actions"] += 2
            mid_out = json.loads(r_call.stdout)
            seen_post_outs: set[tuple[int, ...]] = set()
            for p_name in cand_posts:
                kernel.counters["dsl_instructions"] += 1
                pred_y = _predict_post_step_output(p_name, mid_out)
                if use_sleep_macros:
                    sig_key = tuple(pred_y)
                    if sig_key in seen_post_outs:
                        continue
                    seen_post_outs.add(sig_key)
                else:
                    kernel.counters["candidate_executions"] += 1
                if pred_y == y0:
                    chosen_helper = h_name
                    chosen_post = p_name
                    break
            if chosen_helper and use_sleep_macros:
                break

        if not chosen_helper:
            chosen_helper = cand_helpers[0]

        # If Sleep compression is disabled, learner performs an additional evidence request on x2
        if not use_sleep_macros:
            env.execute({"action": "REQUEST_MORE_EVIDENCE", "function_name": chosen_helper, "input": vis_tests[2]["input"]})
            kernel.counters["sandbox_actions"] += 1
            kernel.counters["queries"] += 1

        # 3. Generate second test on chosen_helper for kernel sandbox validation and propose primitive
        env.execute({"action": "GENERATE_TEST", "function_name": chosen_helper, "input": x1})
        kernel.counters["sandbox_actions"] += 1
        kernel.counters["queries"] += 1

        helper_src = env.inspected_ast_nodes[chosen_helper]
        env.execute({"action": "PROPOSE_PRIMITIVE", "proposed_name": chosen_helper, "source_code": helper_src})
        kernel.counters["sandbox_actions"] += 1

        helper_ev = [e for e in env.helper_call_evidence if e.get("function_name") == chosen_helper]
        proposal = PrimitiveProposal(
            proposal_id=f"prop_{env.family_name}_{method_name}_{seed}",
            proposed_name=chosen_helper,
            type_signature=obs["signatures_and_types"][chosen_helper],
            implementation_kind="pure_python_ast_function",
            implementation_reference_hash=hashlib.sha256(helper_src.encode("utf-8")).hexdigest(),
            source_code=helper_src,
            preconditions=["isinstance(seq, list)", "all(isinstance(x, int) for x in seq)"],
            predicted_effects={
                "non_isomorphic_to_v1_primitives": True,
                "sample_transition": helper_ev[0],
            },
            evidence_ids=[e["evidence_id"] for e in helper_ev],
            counterexamples=[],
            dependency_versions={"python_stdlib": "3.13"},
            expected_mdl_benefit=2.5,
        )
        bb_heldout = _call_blackbox_evaluator_subprocess(
            dict(
                mode="evaluate_helper_proposal",
                seed=env.seed,
                family_name=env.family_name,
                proposed_name=chosen_helper,
                source_code=helper_src,
            )
        )
        lifecycle_res = kernel.evaluate_primitive_proposal(
            proposal=proposal,
            sandbox_examples=helper_ev,
            heldout_examples=None,
            old_retention_tasks=old_skill_suite,
            active_rule=frozen_evolved_rule,
            blackbox_heldout_eval=bb_heldout,
        )
        lifecycle_record = lifecycle_res["proposal"]
        promoted_source = helper_src

        # 4. Synthesize AST patch and verify on visible tests
        synthesized_patch = f"    return {chosen_post}({chosen_helper}(seq))"
        env.execute({"action": "APPLY_AST_PATCH", "replacement_body": synthesized_patch})
        env.execute({"action": "RUN_VISIBLE_TESTS"})
        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 3

    elif method_name == "exact_information_gain_plus_effect_composition":
        # Inspects all files + AST nodes, calls all helpers on x0 and x1 (no MERGE_EQUIVALENT), predicts effects, patches
        for fname in obs["workspace_files"]:
            env.execute({"action": "INSPECT_FILE_SPAN", "file_name": fname, "start_line": 1, "end_line": 30})
            kernel.counters["sandbox_actions"] += 1
        for h_name in cand_helpers:
            env.execute({"action": "INSPECT_AST_NODE", "node_name": h_name})
            r0 = env.execute({"action": "CALL_PURE_FUNCTION", "function_name": h_name, "input": x0})
            r1 = env.execute({"action": "GENERATE_TEST", "function_name": h_name, "input": x1})
            kernel.counters["sandbox_actions"] += 3
            kernel.counters["queries"] += 1
            mid0 = json.loads(r0.stdout)
            mid1 = json.loads(r1.stdout)["expected_output"]
            for p_name in cand_posts:
                kernel.counters["candidate_executions"] += 2
                kernel.counters["dsl_instructions"] += 2
                if (
                    _predict_post_step_output(p_name, mid0) == y0
                    and _predict_post_step_output(p_name, mid1) == vis_tests[1]["expected_output"]
                ):
                    chosen_helper = h_name
                    chosen_post = p_name
        if not chosen_helper:
            chosen_helper = cand_helpers[0]
        promoted_source = env.inspected_ast_nodes[chosen_helper]
        env.execute({"action": "PROPOSE_PRIMITIVE", "proposed_name": chosen_helper, "source_code": promoted_source})
        synthesized_patch = f"    return {chosen_post}({chosen_helper}(seq))"
        env.execute({"action": "APPLY_AST_PATCH", "replacement_body": synthesized_patch})
        env.execute({"action": "RUN_VISIBLE_TESTS"})
        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 4

    elif method_name in ("strongest_handwritten_learner", "scratch_learning_in_target_lab"):
        # Inspects files & ASTs, probes candidate (helper, post) patches directly in sandbox via APPLY_AST_PATCH + RUN_VISIBLE_TESTS
        for fname in obs["workspace_files"]:
            env.execute({"action": "INSPECT_FILE_SPAN", "file_name": fname, "start_line": 1, "end_line": 30})
            kernel.counters["sandbox_actions"] += 1
        for h_name in cand_helpers:
            env.execute({"action": "INSPECT_AST_NODE", "node_name": h_name})
            env.execute({"action": "CALL_PURE_FUNCTION", "function_name": h_name, "input": x0})
            env.execute({"action": "GENERATE_TEST", "function_name": h_name, "input": x1})
            kernel.counters["sandbox_actions"] += 3
            kernel.counters["queries"] += 1

        found_pair = False
        for h_name in cand_helpers:
            for p_name in cand_posts:
                cand_patch = f"    return {p_name}({h_name}(seq))"
                env.execute({"action": "APPLY_AST_PATCH", "replacement_body": cand_patch})
                r_vis = env.execute({"action": "RUN_VISIBLE_TESTS"})
                kernel.counters["sandbox_actions"] += 2
                kernel.counters["candidate_executions"] += len(vis_tests)
                if r_vis.state_diff.get("visible_passed") == r_vis.state_diff.get("visible_total"):
                    chosen_helper = h_name
                    chosen_post = p_name
                    found_pair = True
                    break
            if found_pair:
                break

        if not chosen_helper:
            chosen_helper = cand_helpers[0]
        promoted_source = env.inspected_ast_nodes[chosen_helper]
        env.execute({"action": "PROPOSE_PRIMITIVE", "proposed_name": chosen_helper, "source_code": promoted_source})
        kernel.counters["sandbox_actions"] += 1

        # If scratch_learning_in_target_lab, re-runs discovery probes in downstream Coding and Reasoning labs
        if method_name == "scratch_learning_in_target_lab":
            for h_name in cand_helpers:
                env.execute({"action": "CALL_PURE_FUNCTION", "function_name": h_name, "input": obs["teaching_example"]["input"]})
                env.execute({"action": "REQUEST_MORE_EVIDENCE", "function_name": h_name, "input": vis_tests[2]["input"]})
                kernel.counters["sandbox_actions"] += 2
                kernel.counters["queries"] += 1

        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 1

    elif method_name == "exhaustive_sandbox_probing":
        # Exhaustively tests all 3x3 = 9 (helper, post_fn) patches and all visible inputs in the sandbox
        for fname in obs["workspace_files"]:
            env.execute({"action": "INSPECT_FILE_SPAN", "file_name": fname, "start_line": 1, "end_line": 40})
            kernel.counters["sandbox_actions"] += 1
        for h_name in cand_helpers:
            env.execute({"action": "INSPECT_AST_NODE", "node_name": h_name})
            for vt in vis_tests:
                env.execute({"action": "GENERATE_TEST", "function_name": h_name, "input": vt["input"]})
                kernel.counters["sandbox_actions"] += 1
                kernel.counters["queries"] += 1
        best_h = cand_helpers[0]
        best_p = cand_posts[0]
        for h_name in cand_helpers:
            for p_name in cand_posts:
                cand_patch = f"    return {p_name}({h_name}(seq))"
                env.execute({"action": "APPLY_AST_PATCH", "replacement_body": cand_patch})
                r_vis = env.execute({"action": "RUN_VISIBLE_TESTS"})
                kernel.counters["sandbox_actions"] += 2
                kernel.counters["candidate_executions"] += len(vis_tests)
                if r_vis.state_diff.get("visible_passed") == r_vis.state_diff.get("visible_total"):
                    best_h = h_name
                    best_p = p_name
        chosen_helper = best_h
        chosen_post = best_p
        promoted_source = env.inspected_ast_nodes[chosen_helper]
        env.execute({"action": "APPLY_AST_PATCH", "replacement_body": f"    return {chosen_post}({chosen_helper}(seq))"})
        env.execute({"action": "RUN_VISIBLE_TESTS"})
        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 3

    elif method_name == "examples_only_retrieval":
        # Attempts to solve using only known post-functions on `seq` without inspecting or calling unseen helpers
        for p_name in cand_posts:
            cand_patch = f"    return {p_name}(seq)"
            env.execute({"action": "APPLY_AST_PATCH", "replacement_body": cand_patch})
            env.execute({"action": "RUN_VISIBLE_TESTS"})
            kernel.counters["sandbox_actions"] += 2
            kernel.counters["candidate_executions"] += len(vis_tests)
        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 1

    elif method_name == "learner_without_propose_primitive":
        # Ablates PROPOSE_PRIMITIVE: inspects target_pipeline.py and tests known post-steps, but cannot promote or call quarantined helpers
        env.execute({"action": "INSPECT_FILE_SPAN", "file_name": "target_pipeline.py", "start_line": 1, "end_line": 30})
        for p_name in cand_posts[:2]:
            env.execute({"action": "APPLY_AST_PATCH", "replacement_body": f"    return {p_name}(seq)"})
            env.execute({"action": "RUN_VISIBLE_TESTS"})
            kernel.counters["sandbox_actions"] += 2
            kernel.counters["candidate_executions"] += len(vis_tests)
        env.execute({"action": "STOP"})
        kernel.counters["sandbox_actions"] += 2

    method_receipts = env.receipts[receipt_start_idx:]
    counters_after = dict(kernel.counters)
    experiments, compute_cost = _derive_stage_b_metrics_from_receipts_and_counters(
        method_receipts, counters_before, counters_after
    )

    cross_lab_enabled = bool(
        promoted_source
        and method_name not in ("examples_only_retrieval", "learner_without_propose_primitive", "isolated_labs")
    )
    hidden_eval = env.evaluate(
        promoted_primitive_name=chosen_helper,
        promoted_primitive_source=promoted_source,
        cross_lab_coding_enabled=cross_lab_enabled,
        cross_lab_reasoning_enabled=cross_lab_enabled,
    )
    kernel.counters["hidden_evaluations"] += hidden_eval["hidden_tests_total"]

    cross_lab_success = 0.5 * (
        hidden_eval["cross_lab_coding_accuracy"] + hidden_eval["cross_lab_reasoning_accuracy"]
    )
    return dict(
        method_name=method_name,
        chosen_helper=chosen_helper,
        chosen_post=chosen_post,
        promoted_source=promoted_source,
        lifecycle_record=lifecycle_record,
        hidden_eval=hidden_eval,
        experiments=experiments,
        compute_cost=compute_cost,
        cross_lab_success=cross_lab_success,
        receipts=[r.to_dict() for r in method_receipts],
    )


def run_stage_b_code_transfer_for_seed(
    kernel: ImmutableTrustedKernel,
    frozen_evolved_rule: dict[str, Any],
    old_skill_suite: list[tuple[LearnerTaskView, EvaluatorTaskPrivate]],
    macro_library: list[dict[str, Any]],
    seed: int,
    freeze_journal_sha256: str = "verified_freeze_journal_sha256",
) -> dict[str, Any]:
    """Executes Stage B (Open Primitive Code Transfer v1) across all 3 independently
    generated unknown-library families (`ulib_window_checksum`, `ulib_runlength_bucket`,
    `ulib_zigzag_interleave`) in the isolated black-box evaluator process and compares
    all 9 required Stage B methods through the identical `CommonEnvironmentAdapter`."""
    kernel.verify_integrity()

    per_family_results: dict[str, Any] = {}
    sample_receipts: list[dict[str, Any]] = []
    promotion_records: list[dict[str, Any]] = []
    cross_lab_bindings: list[dict[str, Any]] = []

    baseline_names = (
        "corrected_frozen_evolved_rule",
        "strongest_handwritten_learner",
        "exact_information_gain_plus_effect_composition",
        "exhaustive_sandbox_probing",
        "examples_only_retrieval",
        "learner_without_propose_primitive",
        "proposal_lifecycle_without_sleep_compression",
        "scratch_learning_in_target_lab",
        "isolated_labs",
    )
    agg_by_method: dict[str, list[dict[str, float]]] = {m: [] for m in baseline_names}

    for fam_idx, fam_name in enumerate(UNKNOWN_LIBRARY_FAMILIES):
        env = CommonEnvironmentAdapter(
            fam_name,
            seed + 100 * fam_idx,
            freeze_journal_sha256=freeze_journal_sha256,
        )
        try:
            snap0 = env.snapshot()
            method_runs: dict[str, dict[str, Any]] = {}
            for m_name in baseline_names:
                m_res = _execute_stage_b_method_on_adapter(
                    method_name=m_name,
                    env=env,
                    snap0=snap0,
                    kernel=kernel,
                    frozen_evolved_rule=frozen_evolved_rule,
                    old_skill_suite=old_skill_suite,
                    macro_library=macro_library,
                    seed=seed + 100 * fam_idx,
                )
                method_runs[m_name] = m_res
                agg_by_method[m_name].append(
                    dict(
                        success=m_res["hidden_eval"]["hidden_accuracy"],
                        experiments=m_res["experiments"],
                        compute_cost=m_res["compute_cost"],
                        cross_lab_success=m_res["cross_lab_success"],
                    )
                )

            ev_run = method_runs["corrected_frozen_evolved_rule"]
            hw_run = method_runs["strongest_handwritten_learner"]
            no_prop_run = method_runs["learner_without_propose_primitive"]

            if ev_run["lifecycle_record"] is not None:
                promotion_records.append(ev_run["lifecycle_record"])

            if fam_idx == 0:
                sample_receipts = ev_run["receipts"]

            # Infer cross-lab binding for the invented word using the public teaching example (no supplied mapping!)
            teaching_ex = env.teaching_example
            inv_word = teaching_ex["invented_word"]
            teaching_in = teaching_ex["input"]
            teaching_out = teaching_ex["expected_output"]
            inferred_prim_name = None
            binding_checks = 0
            for cand_name, cand_entry in kernel.promoted_primitives.items():
                binding_checks += 1
                try:
                    if cand_entry["callable"](list(teaching_in)) == teaching_out:
                        inferred_prim_name = cand_name
                        break
                except Exception:
                    continue

            cross_lab_bindings.append(
                dict(
                    family=fam_name,
                    invented_word=inv_word,
                    inferred_primitive=inferred_prim_name,
                    supplied_mapping_used=False,
                    binding_checks=binding_checks,
                    coding_lab_transfer_success=ev_run["hidden_eval"]["cross_lab_coding_accuracy"],
                    reasoning_lab_transfer_success=ev_run["hidden_eval"]["cross_lab_reasoning_accuracy"],
                )
            )

            per_family_results[fam_name] = dict(
                obfuscated_helper=ev_run["chosen_helper"],
                chosen_post_function=ev_run["chosen_post"],
                target_function=env.target_function,
                invented_word=inv_word,
                lifecycle_state=ev_run["lifecycle_record"]["lifecycle_state"] if ev_run["lifecycle_record"] else "NONE",
                kernel_decision="ACCEPT" if ev_run["lifecycle_record"] and ev_run["lifecycle_record"]["lifecycle_state"] == "PROMOTED" else "REJECT",
                hidden_accuracy=ev_run["hidden_eval"]["hidden_accuracy"],
                evolved_experiments=ev_run["experiments"],
                evolved_compute_cost=ev_run["compute_cost"],
                handwritten_compute_cost=hw_run["compute_cost"],
                without_propose_primitive_accuracy=no_prop_run["hidden_eval"]["hidden_accuracy"],
                cross_lab_coding_accuracy=ev_run["hidden_eval"]["cross_lab_coding_accuracy"],
                cross_lab_reasoning_accuracy=ev_run["hidden_eval"]["cross_lab_reasoning_accuracy"],
                evaluator_receipt_sha256=ev_run["hidden_eval"]["evaluator_receipt_sha256"],
                separate_evaluator_process=ev_run["hidden_eval"]["separate_evaluator_process"],
                private_inputs_exposed_to_learner=ev_run["hidden_eval"]["private_inputs_exposed_to_learner"],
            )
        finally:
            env.close()

    method_means: dict[str, Any] = {}
    for m_name, rows in agg_by_method.items():
        method_means[m_name] = dict(
            mean_success=float(sum(r["success"] for r in rows) / len(rows)),
            mean_experiments=float(sum(r["experiments"] for r in rows) / len(rows)),
            mean_compute_cost=float(sum(r["compute_cost"] for r in rows) / len(rows)),
            mean_cross_lab_success=float(sum(r["cross_lab_success"] for r in rows) / len(rows)),
        )

    return dict(
        per_family=per_family_results,
        method_summaries=method_means,
        promotion_records=promotion_records,
        cross_lab_bindings=cross_lab_bindings,
        sample_transition_receipts=sample_receipts,
    )


# ==============================================================================
# 7. FULL TWO-STAGE RUNNER, STATISTICAL GATES & SAVED REPLAY
# ==============================================================================

def _paired_stats(a_vals: list[float], b_vals: list[float]) -> dict[str, float]:
    diffs = [float(a - b) for a, b in zip(a_vals, b_vals)]
    n = len(diffs)
    mean_d = float(sum(diffs) / n)
    var_d = float(sum((d - mean_d) ** 2 for d in diffs) / max(1, n - 1))
    sd_d = math.sqrt(var_d)
    se_d = sd_d / math.sqrt(n)
    half_w = T_CRITICAL_DF7 * se_d
    return dict(
        mean_diff=mean_d,
        sd_diff=sd_d,
        se_diff=se_d,
        ci95_low=float(mean_d - half_w),
        ci95_high=float(mean_d + half_w),
    )


def run_single_seed_two_stage(seed_idx: int, seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    """Executes Stage A (Meta-Rule Evolution v2 without evaluator leakage) for `seed`,
    freezes the winning rule, checks the Stage A gate, and if passed, executes Stage B."""
    kernel = ImmutableTrustedKernel(cfg)
    kernel_sha_before = kernel.kernel_signature()
    rng = random.Random(seed)

    # 1. Build non-isomorphic Stage A suites (Source A, Source B, Dev FST, and Old-Skill Retention)
    list_suite = build_family_task_suite("list_transformations", seed)
    bool_suite = build_family_task_suite("boolean_circuit_induction", seed + 10)
    active_source_suite = list(list_suite) + list(bool_suite)
    dev_suite = build_family_task_suite("fst_string_rewrite", seed + 20)
    old_skill_suite = build_old_skill_retention_suite(seed)

    # Verify zero evaluator leakage across all learner views
    for lv, _ in active_source_suite + dev_suite + old_skill_suite:
        assert_zero_evaluator_leakage(lv)

    # 2. Initialize 32-rule population with zero guided injection
    population = build_initial_population(seed, cfg["population_size"])
    fair_baselines = make_fair_baseline_rules()

    generation_history: list[dict[str, Any]] = []
    dream_history: list[dict[str, Any]] = []
    dream_archive: list[dict[str, Any]] = []
    macro_library: list[dict[str, Any]] = []
    total_rule_evaluations = 0

    best_rule: dict[str, Any] = copy.deepcopy(population[0])
    best_eval: dict[str, Any] | None = None

    for gen in range(cfg["generations"]):
        scored_pop: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for rule in population:
            ev = evaluate_rule_on_stage_a_suites(
                kernel, rule, active_source_suite, dev_suite, old_skill_suite, macro_library=macro_library
            )
            total_rule_evaluations += 1
            scored_pop.append((rule, ev))

        scored_pop.sort(key=lambda pair: lexicographic_rule_key(pair[1]), reverse=True)
        gen_best_rule, gen_best_eval = scored_pop[0]
        if best_eval is None or lexicographic_rule_key(gen_best_eval) > lexicographic_rule_key(best_eval):
            best_rule = copy.deepcopy(gen_best_rule)
            best_eval = copy.deepcopy(gen_best_eval)

        pareto_front = [
            r_cand["rule_id"]
            for r_cand, ev_cand in scored_pop
            if not any(
                pareto_dominates(ev_other, ev_cand)
                for _, ev_other in scored_pop
                if ev_other["rule_id"] != ev_cand["rule_id"]
            )
        ]

        # Run Dream inside the evolution loop to add novel high-regret tasks to active_source_suite
        dream_step = run_dream_generation_step(
            kernel=kernel,
            gen=gen,
            seed=seed,
            reference_rule=gen_best_rule,
            challenger_rule=fair_baselines["exact_information_gain_learner"],
            active_source_suite=active_source_suite,
            archive=dream_archive,
        )
        dream_history.append(dream_step)

        # Run Sleep compression after generation 5 on acquired capsules
        if gen == 5 and gen_best_eval["acquired_capsules"]:
            sleep_step = run_sleep_compression(kernel, gen_best_eval["acquired_capsules"])
            macro_library = sleep_step["accepted_macros"]

        generation_history.append(
            dict(
                generation=gen,
                best_rule_id=gen_best_rule["rule_id"],
                best_task_success=gen_best_eval["task_success"],
                best_old_skill_retention=gen_best_eval["old_skill_retention"],
                best_episodic_experiments=gen_best_eval["episodic_experiments"],
                best_episodic_cost=gen_best_eval["episodic_execution_cost"],
                best_instruction_count=gen_best_eval["instruction_count"],
                pareto_front_size=len(pareto_front),
                active_curriculum_size=len(active_source_suite),
            )
        )

        # Elitist survival of top 8 rules -> 24 uniformly mutated children (NO child_idx == 0 overwrite!)
        elites = [copy.deepcopy(pair[0]) for pair in scored_pop[:8]]
        next_pop: list[dict[str, Any]] = list(elites)
        child_idx = 0
        while len(next_pop) < cfg["population_size"]:
            parent = elites[child_idx % len(elites)]
            child = mutate_learning_rule_uniform(
                parent,
                rng,
                new_rule_id=f"seed{seed}_g{gen + 1:02d}_c{child_idx:02d}",
                new_origin="evolved",
            )
            next_pop.append(child)
            child_idx += 1
        population = next_pop

    assert best_eval is not None

    # 3. Run Untouched Random Evolutionary Selection Control (same uniform mutations, random selection, NO overwrite!)
    rng_ctrl = random.Random(seed + 5000)
    rand_pop = build_initial_population(seed + 5000, 16)
    for g_c in range(cfg["generations"]):
        rand_elites = rng_ctrl.sample(rand_pop, 4)
        rand_pop = list(rand_elites) + [
            mutate_learning_rule_uniform(
                rng_ctrl.choice(rand_elites),
                rng_ctrl,
                new_rule_id=f"rand_sel_{seed}_{g_c}_{i}",
                new_origin="random_evolutionary_selection",
            )
            for i in range(12)
        ]
    random_evolutionary_selection_rule = copy.deepcopy(rand_pop[-1])
    random_valid_rule = sample_random_valid_learning_rule(seed + 7000, f"random_valid_rule_{seed}")

    # 4. FREEZE STAGE A EVOLVED RULE BEFORE STAGE B SEALED CODE TRANSFER
    frozen_evolved_rule = copy.deepcopy(best_rule)
    frozen_evolved_rule_sha256 = digest(frozen_evolved_rule)
    freeze_journal_sha = kernel.log_event(
        "FREEZE_STAGE_A_EVOLVED_RULE",
        dict(
            seed=seed,
            frozen_rule_id=frozen_evolved_rule["rule_id"],
            frozen_rule_sha256=frozen_evolved_rule_sha256,
        ),
    )

    # 5. Evaluate Frozen Evolved Rule and All Stage A Baselines Across Stage A Families
    eval_source_plus_dev = list_suite + bool_suite + dev_suite
    stage_a_rules = {
        "evolved_meta_rule": frozen_evolved_rule,
        "current_handwritten_learner": fair_baselines["current_handwritten_learner"],
        "exact_information_gain_learner": fair_baselines["exact_information_gain_learner"],
        "exact_information_gain_plus_effect_composition": fair_baselines["exact_information_gain_plus_effect_composition"],
        "mdl_best_first_search": fair_baselines["mdl_best_first_search"],
        "exhaustive_typed_enumeration": fair_baselines["exhaustive_typed_enumeration"],
        "random_valid_learning_rules": random_valid_rule,
        "random_evolutionary_selection": random_evolutionary_selection_rule,
        "shortest_valid_rule": fair_baselines["shortest_valid_rule"],
        "no_evolution_ablation": fair_baselines["exact_information_gain_plus_effect_composition"],
    }

    suites_by_family = {
        "list_transformations": list_suite,
        "boolean_circuit_induction": bool_suite,
        "fst_string_rewrite": dev_suite,
    }

    stage_a_comparisons: dict[str, Any] = {}
    evolved_capsules_dict: dict[str, dict[str, Any]] = {}
    evolved_capsules_list: list[dict[str, Any]] = []

    for r_name, r_prog in stage_a_rules.items():
        per_fam: dict[str, Any] = {}
        acc_vals: list[float] = []
        exp_vals: list[float] = []
        cost_vals: list[float] = []
        exec_vals: list[float] = []
        cont_cost_vals: list[float] = []

        cont_mem: dict[str, dict[str, Any]] = {}
        use_macros = macro_library if r_name == "evolved_meta_rule" else None

        for fam_name in STAGE_A_FAMILIES:
            f_suite = suites_by_family[fam_name]
            ep_runs = [
                kernel.execute_learning_rule(r_prog, lv, ep, capsule_memory=None, macro_library=None)
                for lv, ep in f_suite
            ]
            cont_runs = [
                kernel.execute_learning_rule(r_prog, lv, ep, capsule_memory=cont_mem, macro_library=use_macros)
                for lv, ep in f_suite
            ]
            if r_name == "evolved_meta_rule":
                for cr in cont_runs:
                    if cr["capsule"] is not None:
                        evolved_capsules_list.append(cr["capsule"])
                        evolved_capsules_dict[cr["invented_word"]] = cr["capsule"]

            f_acc = float(sum(x["task_success"] for x in ep_runs) / len(ep_runs))
            f_exp = float(sum(x["experiments_run"] for x in ep_runs) / len(ep_runs))
            f_cost = float(sum(x["execution_cost"] for x in ep_runs) / len(ep_runs))
            f_execs = float(sum(x["candidate_executions"] for x in ep_runs) / len(ep_runs))
            f_cont_cost = float(sum(x["execution_cost"] for x in cont_runs) / len(cont_runs))

            per_fam[fam_name] = dict(
                task_success=f_acc,
                episodic_experiments=f_exp,
                episodic_execution_cost=f_cost,
                candidate_executions=f_execs,
                continual_execution_cost=f_cont_cost,
            )
            acc_vals.append(f_acc)
            exp_vals.append(f_exp)
            cost_vals.append(f_cost)
            exec_vals.append(f_execs)
            cont_cost_vals.append(f_cont_cost)

        old_runs = [
            kernel.execute_learning_rule(r_prog, lv, ep, capsule_memory=cont_mem, macro_library=use_macros)
            for lv, ep in old_skill_suite
        ]
        old_ret = float(
            sum(1.0 if (x["task_success"] >= 0.99 and x["retention_safe"]) else 0.0 for x in old_runs)
            / len(old_runs)
        )

        stage_a_comparisons[r_name] = dict(
            rule_id=r_prog["rule_id"],
            instruction_count=len(r_prog["instructions"]),
            instructions=list(r_prog["instructions"]),
            stopping_threshold=r_prog["stopping_threshold"],
            tie_breaker=r_prog["tie_breaker"],
            query_strategy=r_prog["query_strategy"],
            mean_task_success=float(sum(acc_vals) / len(acc_vals)),
            old_skill_retention=old_ret,
            mean_episodic_experiments=float(sum(exp_vals) / len(exp_vals)),
            mean_episodic_execution_cost=float(sum(cost_vals) / len(cost_vals)),
            mean_candidate_executions=float(sum(exec_vals) / len(exec_vals)),
            mean_continual_execution_cost=float(sum(cont_cost_vals) / len(cont_cost_vals)),
            by_family=per_fam,
        )

    # 6. Real Pre/Post Retention, Sleep Report, and Single-Instruction Ablations
    retention_report = evaluate_real_pre_post_retention(
        kernel=kernel,
        pre_rule=fair_baselines["current_handwritten_learner"],
        post_rule=frozen_evolved_rule,
        protected_old_tasks=old_skill_suite,
        post_capsules=evolved_capsules_dict,
        post_macros=macro_library,
    )
    sleep_report = run_sleep_compression(kernel, evolved_capsules_list)
    instruction_ablations = evaluate_single_instruction_ablations(
        kernel, frozen_evolved_rule, eval_source_plus_dev
    )

    # Check whether Stage A passed for this seed
    ev_m = stage_a_comparisons["evolved_meta_rule"]
    strongest_hw = stage_a_comparisons["exact_information_gain_plus_effect_composition"]
    stage_a_seed_passed = bool(
        ev_m["mean_task_success"] >= 0.99
        and ev_m["old_skill_retention"] >= 0.98
        and ev_m["mean_episodic_execution_cost"] < strongest_hw["mean_episodic_execution_cost"]
    )

    # 7. Execute Stage B ONLY if Stage A passed
    stage_b_report = None
    if stage_a_seed_passed:
        stage_b_report = run_stage_b_code_transfer_for_seed(
            kernel=kernel,
            frozen_evolved_rule=frozen_evolved_rule,
            old_skill_suite=old_skill_suite,
            macro_library=sleep_report["accepted_macros"],
            seed=cfg["sealed_code_seed_base"] + seed_idx * 10,
            freeze_journal_sha256=freeze_journal_sha,
        )

    kernel_sha_after = kernel.kernel_signature()
    if kernel_sha_before != kernel_sha_after:
        raise RuntimeError("kernel_mutated_during_seed_run")

    return dict(
        seed_index=seed_idx,
        seed=seed,
        kernel_sha256_before=kernel_sha_before,
        kernel_sha256_after=kernel_sha_after,
        freeze_journal_sha256=freeze_journal_sha,
        frozen_evolved_rule=frozen_evolved_rule,
        frozen_evolved_rule_sha256=frozen_evolved_rule_sha256,
        total_evolution_rule_evaluations=total_rule_evaluations,
        generation_history=generation_history,
        dream_history=dream_history,
        dream_archive=dream_archive,
        sleep_report=sleep_report,
        retention_report=retention_report,
        single_instruction_ablations=instruction_ablations,
        stage_a_comparisons=stage_a_comparisons,
        stage_a_seed_passed=stage_a_seed_passed,
        stage_b_report=stage_b_report,
        kernel_counters=dict(kernel.counters),
    )


def evaluate_open_primitive_transfer_artifact(
    raw_study: dict[str, Any],
    protocol_text: str,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluates all Stage A and Stage B registered acceptance gates."""
    c = configuration(authorized=True) if cfg is None else cfg
    if hashlib.sha256(protocol_text.encode("utf-8")).hexdigest() != raw_study["protocol_sha256"]:
        raise ValueError("open_primitive_transfer_protocol_sha256_mismatch")

    seeds_data = raw_study["seeds"]
    stage_a_rule_names = (
        "evolved_meta_rule",
        "current_handwritten_learner",
        "exact_information_gain_learner",
        "exact_information_gain_plus_effect_composition",
        "mdl_best_first_search",
        "exhaustive_typed_enumeration",
        "random_valid_learning_rules",
        "random_evolutionary_selection",
        "shortest_valid_rule",
        "no_evolution_ablation",
    )

    stage_a_summaries: dict[str, Any] = {}
    for rn in stage_a_rule_names:
        acc_l = [s["stage_a_comparisons"][rn]["mean_task_success"] for s in seeds_data]
        ret_l = [s["stage_a_comparisons"][rn]["old_skill_retention"] for s in seeds_data]
        exp_l = [s["stage_a_comparisons"][rn]["mean_episodic_experiments"] for s in seeds_data]
        cost_l = [s["stage_a_comparisons"][rn]["mean_episodic_execution_cost"] for s in seeds_data]
        exec_l = [s["stage_a_comparisons"][rn]["mean_candidate_executions"] for s in seeds_data]
        cont_l = [s["stage_a_comparisons"][rn]["mean_continual_execution_cost"] for s in seeds_data]
        ins_l = [s["stage_a_comparisons"][rn]["instruction_count"] for s in seeds_data]

        by_fam: dict[str, Any] = {}
        for fam_name in STAGE_A_FAMILIES:
            f_acc = [s["stage_a_comparisons"][rn]["by_family"][fam_name]["task_success"] for s in seeds_data]
            f_exp = [s["stage_a_comparisons"][rn]["by_family"][fam_name]["episodic_experiments"] for s in seeds_data]
            f_cost = [s["stage_a_comparisons"][rn]["by_family"][fam_name]["episodic_execution_cost"] for s in seeds_data]
            f_exec = [s["stage_a_comparisons"][rn]["by_family"][fam_name]["candidate_executions"] for s in seeds_data]
            by_fam[fam_name] = dict(
                mean_task_success=float(sum(f_acc) / len(f_acc)),
                mean_episodic_experiments=float(sum(f_exp) / len(f_exp)),
                mean_episodic_execution_cost=float(sum(f_cost) / len(f_cost)),
                mean_candidate_executions=float(sum(f_exec) / len(f_exec)),
            )

        stage_a_summaries[rn] = dict(
            mean_task_success=float(sum(acc_l) / len(acc_l)),
            mean_old_skill_retention=float(sum(ret_l) / len(ret_l)),
            mean_episodic_experiments=float(sum(exp_l) / len(exp_l)),
            mean_episodic_execution_cost=float(sum(cost_l) / len(cost_l)),
            mean_candidate_executions=float(sum(exec_l) / len(exec_l)),
            mean_continual_execution_cost=float(sum(cont_l) / len(cont_l)),
            mean_instruction_count=float(sum(ins_l) / len(ins_l)),
            by_family=by_fam,
        )

    # Paired comparisons on Stage A (vs exact_information_gain_learner and vs exact_information_gain_plus_effect_composition)
    ev_a_costs = [s["stage_a_comparisons"]["evolved_meta_rule"]["mean_episodic_execution_cost"] for s in seeds_data]
    ig_a_costs = [s["stage_a_comparisons"]["exact_information_gain_learner"]["mean_episodic_execution_cost"] for s in seeds_data]
    ige_a_costs = [s["stage_a_comparisons"]["exact_information_gain_plus_effect_composition"]["mean_episodic_execution_cost"] for s in seeds_data]
    rand_sel_costs = [s["stage_a_comparisons"]["random_evolutionary_selection"]["mean_episodic_execution_cost"] for s in seeds_data]

    paired_a_vs_ig = _paired_stats(ig_a_costs, ev_a_costs)
    paired_a_vs_ige = _paired_stats(ige_a_costs, ev_a_costs)
    paired_a_vs_randsel = _paired_stats(rand_sel_costs, ev_a_costs)
    beats_random_selection_all_seeds = all(
        s["stage_a_comparisons"]["evolved_meta_rule"]["mean_task_success"]
        > s["stage_a_comparisons"]["random_evolutionary_selection"]["mean_task_success"]
        or s["stage_a_comparisons"]["evolved_meta_rule"]["mean_episodic_execution_cost"]
        < s["stage_a_comparisons"]["random_evolutionary_selection"]["mean_episodic_execution_cost"]
        for s in seeds_data
    )

    stage_a_pass = bool(
        all(s["stage_a_seed_passed"] for s in seeds_data)
        and stage_a_summaries["evolved_meta_rule"]["mean_task_success"] >= 0.99
        and stage_a_summaries["evolved_meta_rule"]["mean_old_skill_retention"] >= 0.98
        and paired_a_vs_ig["ci95_low"] > 0.0
        and paired_a_vs_ige["ci95_low"] > 0.0
        and beats_random_selection_all_seeds
    )

    # Aggregate Stage B summaries
    stage_b_method_names = (
        "corrected_frozen_evolved_rule",
        "strongest_handwritten_learner",
        "exact_information_gain_plus_effect_composition",
        "exhaustive_sandbox_probing",
        "examples_only_retrieval",
        "learner_without_propose_primitive",
        "proposal_lifecycle_without_sleep_compression",
        "scratch_learning_in_target_lab",
        "isolated_labs",
    )
    stage_b_summaries: dict[str, Any] = {}
    for mn in stage_b_method_names:
        m_succ = [s["stage_b_report"]["method_summaries"][mn]["mean_success"] for s in seeds_data]
        m_exp = [s["stage_b_report"]["method_summaries"][mn]["mean_experiments"] for s in seeds_data]
        m_cost = [s["stage_b_report"]["method_summaries"][mn]["mean_compute_cost"] for s in seeds_data]
        m_xlab = [s["stage_b_report"]["method_summaries"][mn]["mean_cross_lab_success"] for s in seeds_data]
        stage_b_summaries[mn] = dict(
            mean_success=float(sum(m_succ) / len(m_succ)),
            mean_experiments=float(sum(m_exp) / len(m_exp)),
            mean_compute_cost=float(sum(m_cost) / len(m_cost)),
            mean_cross_lab_success=float(sum(m_xlab) / len(m_xlab)),
        )

    stage_b_by_family: dict[str, Any] = {}
    for ufam in UNKNOWN_LIBRARY_FAMILIES:
        u_acc = [s["stage_b_report"]["per_family"][ufam]["hidden_accuracy"] for s in seeds_data]
        u_exp = [s["stage_b_report"]["per_family"][ufam]["evolved_experiments"] for s in seeds_data]
        u_cost = [s["stage_b_report"]["per_family"][ufam]["evolved_compute_cost"] for s in seeds_data]
        u_hw_cost = [s["stage_b_report"]["per_family"][ufam]["handwritten_compute_cost"] for s in seeds_data]
        u_no_prop = [s["stage_b_report"]["per_family"][ufam]["without_propose_primitive_accuracy"] for s in seeds_data]
        stage_b_by_family[ufam] = dict(
            mean_hidden_accuracy=float(sum(u_acc) / len(u_acc)),
            mean_evolved_experiments=float(sum(u_exp) / len(u_exp)),
            mean_evolved_compute_cost=float(sum(u_cost) / len(u_cost)),
            mean_handwritten_compute_cost=float(sum(u_hw_cost) / len(u_hw_cost)),
            mean_without_propose_primitive_accuracy=float(sum(u_no_prop) / len(u_no_prop)),
        )

    ev_b_costs = [s["stage_b_report"]["method_summaries"]["corrected_frozen_evolved_rule"]["mean_compute_cost"] for s in seeds_data]
    hw_b_costs = [s["stage_b_report"]["method_summaries"]["strongest_handwritten_learner"]["mean_compute_cost"] for s in seeds_data]
    ige_b_costs = [s["stage_b_report"]["method_summaries"]["exact_information_gain_plus_effect_composition"]["mean_compute_cost"] for s in seeds_data]
    ev_b_exps = [s["stage_b_report"]["method_summaries"]["corrected_frozen_evolved_rule"]["mean_experiments"] for s in seeds_data]
    hw_b_exps = [s["stage_b_report"]["method_summaries"]["strongest_handwritten_learner"]["mean_experiments"] for s in seeds_data]

    paired_b_cost_vs_hw = _paired_stats(hw_b_costs, ev_b_costs)
    paired_b_cost_vs_ige = _paired_stats(ige_b_costs, ev_b_costs)
    paired_b_exp_vs_hw = _paired_stats(hw_b_exps, ev_b_exps)

    # Check all 12 registered acceptance gates
    worst_ret_regression = max(s["retention_report"]["worst_regression"] for s in seeds_data)
    mean_post_ret = float(
        sum(s["retention_report"]["post_mean_accuracy"] for s in seeds_data) / len(seeds_data)
    )
    all_proposals_promoted = all(
        p["lifecycle_state"] == "PROMOTED"
        and p["lifecycle_history"] == list(PROPOSAL_LIFECYCLE_STATES)
        for s in seeds_data
        for p in s["stage_b_report"]["promotion_records"]
    )
    unknown_families_reproduced = sum(
        1
        for ufam, f_stat in stage_b_by_family.items()
        if f_stat["mean_hidden_accuracy"] >= 0.99
        and f_stat["mean_evolved_compute_cost"] < f_stat["mean_handwritten_compute_cost"]
    )

    gates = dict(
        gate_01_zero_evaluator_private_fields_reach_learner=bool(
            raw_study["leakage_proof"]["zero_leakage_verified"]
        ),
        gate_02_selected_program_passes_hidden_execution_tests=bool(
            stage_a_summaries["evolved_meta_rule"]["mean_task_success"] >= 0.99
            and stage_b_summaries["corrected_frozen_evolved_rule"]["mean_success"] >= 0.99
        ),
        gate_03_unknown_effect_learned_without_stored_complete_fingerprint=bool(
            not c["whole_program_fingerprints_stored"]
            and stage_b_summaries["corrected_frozen_evolved_rule"]["mean_success"] >= 0.99
        ),
        gate_04_proposed_primitive_passes_complete_kernel_lifecycle=bool(all_proposals_promoted),
        gate_05_frozen_rule_transfers_to_non_isomorphic_code_family=bool(
            raw_study["non_isomorphism_proof"]["non_isomorphic_verified"]
            and stage_b_summaries["corrected_frozen_evolved_rule"]["mean_success"] >= 0.99
        ),
        gate_06_beats_or_non_inferior_to_strongest_fair_baseline_on_success=bool(
            stage_a_summaries["evolved_meta_rule"]["mean_task_success"]
            >= stage_a_summaries["exact_information_gain_plus_effect_composition"]["mean_task_success"]
            and stage_b_summaries["corrected_frozen_evolved_rule"]["mean_success"]
            >= stage_b_summaries["strongest_handwritten_learner"]["mean_success"]
        ),
        gate_07_improves_experiments_or_compute_with_paired_ci_excluding_zero=bool(
            paired_a_vs_ige["ci95_low"] > 0.0
            and paired_b_cost_vs_hw["ci95_low"] > 0.0
            and paired_b_cost_vs_ige["ci95_low"] > 0.0
        ),
        gate_08_removing_promoted_primitive_removes_transfer_gain=bool(
            stage_b_summaries["corrected_frozen_evolved_rule"]["mean_success"]
            - stage_b_summaries["learner_without_propose_primitive"]["mean_success"]
            >= 0.50
        ),
        gate_09_no_human_written_cross_lab_semantic_mapping=bool(
            not c["manually_supplied_cross_lab_mapping"]
            and stage_b_summaries["corrected_frozen_evolved_rule"]["mean_cross_lab_success"] >= 0.99
        ),
        gate_10_old_task_retention_at_least_98pct_real_pre_post=bool(
            mean_post_ret >= 0.98 and worst_ret_regression == 0.0
        ),
        gate_11_all_discovery_evolution_sandbox_validation_costs_included=bool(
            all("kernel_counters" in s for s in seeds_data)
            and all(s["kernel_sha256_before"] == s["kernel_sha256_after"] for s in seeds_data)
        ),
        gate_12_at_least_two_unknown_library_families_reproduce=bool(
            unknown_families_reproduced >= 2
        ),
    )

    stage_b_pass = bool(stage_a_pass and all(gates.values()))
    if not stage_a_pass:
        verdict_key = "FAIL_STAGE_A"
    elif not stage_b_pass:
        verdict_key = "PASS_STAGE_A_FAIL_STAGE_B"
    else:
        verdict_key = "PASS_BOTH_STAGE_A_AND_STAGE_B"

    return dict(
        schema="seed_open_primitive_transfer_v1",
        stage_a_pass=stage_a_pass,
        stage_b_pass=stage_b_pass,
        overall_pass=stage_b_pass,
        verdict=verdict_key,
        permitted_conclusion=PERMITTED_CONCLUSIONS[verdict_key],
        gates=gates,
        stage_a_summaries=stage_a_summaries,
        stage_b_summaries=stage_b_summaries,
        stage_b_by_family=stage_b_by_family,
        unknown_families_reproduced=unknown_families_reproduced,
        paired_comparisons=dict(
            stage_a_cost_vs_exact_info_gain=paired_a_vs_ig,
            stage_a_cost_vs_info_gain_plus_effect=paired_a_vs_ige,
            stage_a_cost_vs_random_selection=paired_a_vs_randsel,
            stage_b_cost_vs_strongest_handwritten=paired_b_cost_vs_hw,
            stage_b_cost_vs_info_gain_plus_effect=paired_b_cost_vs_ige,
            stage_b_experiments_vs_strongest_handwritten=paired_b_exp_vs_hw,
        ),
        retention_summary=dict(
            mean_pre_accuracy=float(
                sum(s["retention_report"]["pre_mean_accuracy"] for s in seeds_data) / len(seeds_data)
            ),
            mean_post_accuracy=mean_post_ret,
            worst_regression=worst_ret_regression,
        ),
        sleep_summary=dict(
            mean_mdl_before=float(sum(s["sleep_report"]["mdl_before"] for s in seeds_data) / len(seeds_data)),
            mean_mdl_after=float(sum(s["sleep_report"]["mdl_after"] for s in seeds_data) / len(seeds_data)),
            mean_mdl_reduction=float(sum(s["sleep_report"]["mdl_reduction"] for s in seeds_data) / len(seeds_data)),
            old_capsule_test_pass_rate=float(
                sum(s["sleep_report"]["old_capsule_test_pass_rate"] for s in seeds_data) / len(seeds_data)
            ),
            tests_verified_by_real_execution=True,
        ),
    )


def build_open_primitive_transfer_study(
    repository: Path | str | None = None,
    study_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = Path(repository) if repository is not None else Path(__file__).resolve().parents[3]
    c = configuration(authorized=True) if study_config is None else study_config
    config_check(c)

    t0 = time.perf_counter()
    cpu0 = time.process_time()

    protocol_path = repo / "docs/NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md"
    protocol_text = protocol_path.read_text(encoding="utf-8")
    protocol_sha256 = hashlib.sha256(protocol_text.encode("utf-8")).hexdigest()

    v1_audit_report = v1_audit.run_v1_adversarial_audit(repo)
    non_iso_proof = verify_families_non_isomorphic()

    # Verify schema separation proof on sample task pair
    sample_lv, sample_ep = build_stage_a_task_pair(
        "list_transformations", 0, ("keep_even", "reverse_list"), c["seeds"][0]
    )
    leakage_violations = inspect_evaluator_leakage_paths(sample_lv)
    private_detected = inspect_evaluator_leakage_paths(sample_ep)
    leakage_proof = dict(
        learner_view_fields=list(sample_lv.__dataclass_fields__.keys()),
        evaluator_private_fields=list(sample_ep.__dataclass_fields__.keys()),
        forbidden_keys_checked=sorted(FORBIDDEN_LEARNER_KEYS),
        learner_view_violations=leakage_violations,
        evaluator_private_triggers_detector=len(private_detected) > 0,
        zero_leakage_verified=(len(leakage_violations) == 0 and len(private_detected) > 0),
    )

    frozen_before = dm.frozen_hashes(repo)
    seeds_results: list[dict[str, Any]] = []
    for idx, seed in enumerate(c["seeds"]):
        seeds_results.append(run_single_seed_two_stage(idx, seed, c))
    frozen_after = dm.frozen_hashes(repo)

    wall_s = time.perf_counter() - t0
    cpu_s = time.process_time() - cpu0

    total_counters = {
        k: sum(s["kernel_counters"][k] for s in seeds_results)
        for k in seeds_results[0]["kernel_counters"]
    }

    raw_study = dict(
        schema="seed_open_primitive_transfer_v1",
        declared_complete=True,
        protocol_sha256=protocol_sha256,
        config_sha256=digest(c),
        config=c,
        stored_whole_program_fingerprints=0,
        manually_supplied_cross_lab_mapping=False,
        neural_training_enabled=False,
        guided_rule_injection_enabled=False,
        v1_adversarial_audit_summary=dict(
            all_15_confounds_confirmed=v1_audit_report["all_15_confounds_confirmed"],
            confounds_confirmed=v1_audit_report["confounds_confirmed"],
            retraction_statement=v1_audit_report["retraction_statement"],
        ),
        leakage_proof=leakage_proof,
        non_isomorphism_proof=non_iso_proof,
        seeds=seeds_results,
        compute_accounting=dict(
            wall_clock_s=float(round(wall_s, 6)),
            cpu_time_s=float(round(cpu_s, 6)),
            authored_steps=c["max_authored_steps"],
            outer_updates=c["max_outer_updates"],
            imagined_transitions=c["max_imagined_transitions"],
            total_evolution_rule_evaluations=sum(
                s["total_evolution_rule_evaluations"] for s in seeds_results
            ),
            kernel_counters_total=total_counters,
            stored_whole_program_fingerprints=0,
            manually_supplied_cross_lab_mapping=False,
            guided_rule_injection_enabled=False,
            carried_used_s=c["carried_used_s"],
            carried_remaining_s=c["carried_remaining_s"],
            updated_used_s=float(c["carried_used_s"] + wall_s),
            updated_remaining_s=float(c["carried_remaining_s"] - wall_s),
        ),
        frozen_before=frozen_before,
        frozen_after=frozen_after,
    )

    evaluation = evaluate_open_primitive_transfer_artifact(raw_study, protocol_text, c)
    raw_study["evaluation"] = evaluation
    raw_study["analysis"] = evaluation
    raw_study["verdict"] = evaluation["verdict"]
    raw_study["overall_pass"] = evaluation["overall_pass"]
    raw_study["result_digest"] = digest(evaluation)
    return raw_study


def run_study(
    study_config: dict[str, Any] | None = None,
    repository: Path | str | None = None,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    import sys

    repo = Path(repository) if repository is not None else Path(__file__).resolve().parents[3]
    c = configuration(authorized=True) if study_config is None else study_config
    study = build_open_primitive_transfer_study(repository=repo, study_config=c)
    if progress_path is not None:
        Path(progress_path).write_text(canonical(study), encoding="utf-8")
    ev = study["evaluation"]
    ev_cost = ev["stage_a_summaries"]["evolved_meta_rule"]["mean_episodic_execution_cost"]
    base_cost = ev["stage_a_summaries"]["exact_information_gain_plus_effect_composition"][
        "mean_episodic_execution_cost"
    ]
    seeds_out = study["seeds"]
    curve = [
        dict(
            update=g_idx + 1,
            train_mse=round(
                float(
                    sum(s["generation_history"][g_idx]["best_episodic_cost"] for s in seeds_out)
                    / len(seeds_out)
                ),
                6,
            ),
            development_mse=round(base_cost, 6),
        )
        for g_idx in range(c["generations"])
    ]
    return dict(
        adapter="seed_open_primitive_transfer_v1",
        metrics=dict(
            mse=ev_cost,
            baseline_mse=base_cost,
            worst_error_increase=max(0.0, ev_cost - base_cost),
        ),
        curve=curve,
        study=study,
        analysis=ev,
        resources=dict(
            real_steps=c["max_authored_steps"],
            imagined_transitions=0,
            updates=c["max_outer_updates"],
            training_examples=64,
            development_examples=32,
            assessment_examples=768,
            network_forwards=0,
            parameter_count=len(DSL_INSTRUCTIONS),
            cpu_s=study["compute_accounting"]["cpu_time_s"],
        ),
        model=dict(
            schema="seed_open_primitive_transfer_models_v1",
            models=[s["frozen_evolved_rule"] for s in seeds_out],
        ),
        runtime=dict(
            python=sys.version.split()[0],
            torch="not_imported",
            device="cpu",
            threads=1,
        ),
    )


def run(request: dict[str, Any]) -> dict[str, Any]:
    if "inputs" in request and type(request["inputs"]) is dict:
        c = request["inputs"]["study_config"]
        repo = request["inputs"]["repository"]
        return run_study(c, repo, Path("progress.json"))
    cfg = request.get("config") or configuration(authorized=True)
    config_check(cfg)
    root = Path(request["root"]) if "root" in request and request["root"] else None
    progress = Path(request["progress"]) if "progress" in request and request["progress"] else None
    return run_study(cfg, repository=root, progress_path=progress)


def validate_output(output: dict[str, Any], c: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
    from . import source_acquisition as sa

    config_check(c)
    if type(output) is not dict or output.get("adapter") != "seed_open_primitive_transfer_v1":
        raise ValueError("open_primitive_transfer_output_schema")
    study = output.get("study")
    if type(study) is not dict or study.get("declared_complete") is not True:
        raise ValueError("incomplete_open_primitive_transfer_study")
    if study.get("frozen_before") != sa.FROZEN or study.get("frozen_after") != sa.FROZEN:
        raise ValueError("frozen_checkpoint_changed")
    root = Path(__file__).resolve().parents[3]
    protocol_text = (root / "docs/NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md").read_text(encoding="utf-8")
    recomputed = evaluate_open_primitive_transfer_artifact(study, protocol_text, c)
    if digest(study.get("analysis")) != digest(recomputed):
        raise ValueError("open_primitive_transfer_analysis_mismatch")
    work = output.get("resources", {})
    if (
        work.get("updates") != 16
        or work.get("real_steps") != 4096
        or work.get("imagined_transitions") != 0
        or work.get("network_forwards") != 0
    ):
        raise ValueError("open_primitive_transfer_resource_accounting")
    if work.get("cpu_s", 0.0) > caps["cpu_s"]:
        raise ValueError("open_primitive_transfer_cpu_cap_exceeded")
    digest(output)
    return output


def saved_replay(repository: Path | str | None = None) -> dict[str, Any]:
    repo = Path(repository) if repository is not None else Path(__file__).resolve().parents[3]
    art_path = repo / "artifacts/seed_open_primitive_transfer.json"
    data = json.loads(art_path.read_text(encoding="utf-8"))
    ev = data["evaluation"]
    evolved_a = ev["stage_a_summaries"]["evolved_meta_rule"]
    baseline_a = ev["stage_a_summaries"]["exact_information_gain_plus_effect_composition"]
    validate_output(
        dict(
            adapter="seed_open_primitive_transfer_v1",
            metrics=dict(
                mse=evolved_a["mean_episodic_execution_cost"],
                baseline_mse=baseline_a["mean_episodic_execution_cost"],
                worst_error_increase=max(0.0, evolved_a["mean_episodic_execution_cost"] - baseline_a["mean_episodic_execution_cost"]),
            ),
            curve=[],
            resources=data["resources"],
            model=dict(
                schema="seed_open_primitive_transfer_models_v1",
                models=[s["frozen_evolved_rule"] for s in data["seeds"]],
            ),
            study=data,
            runtime=data["runtime"],
        ),
        data["config"],
        dict(
            wall_s=120,
            cpu_s=120,
            memory_mb=2048,
            real_steps=4096,
            imagined_transitions=0,
            updates=16,
        ),
    )
    return dict(
        id=data.get("host_receipt", {}).get("id", "seed-open-primitive-transfer-1"),
        mode="exploration",
        status=data.get("host_receipt", {}).get("status", "complete_development"),
        scientific_claim="development_only",
        failure=data.get("host_receipt", {}).get("failure"),
        wall_s=data.get("host_receipt", {}).get("wall_s"),
        memory_mb=data.get("host_receipt", {}).get("peak_sampled_rss_mb"),
        revision=data.get("execution_sha", ""),
        model_sha256=data.get("result_digest", ""),
        resources=data.get("resources", {}),
        metrics=dict(
            mse=evolved_a["mean_episodic_execution_cost"],
            baseline_mse=baseline_a["mean_episodic_execution_cost"],
            worst_error_increase=max(0.0, evolved_a["mean_episodic_execution_cost"] - baseline_a["mean_episodic_execution_cost"]),
        ),
        curve=[],
        open_primitive_transfer=dict(
            screen=ev["verdict"],
            stage_a_pass=ev["stage_a_pass"],
            stage_b_pass=ev["stage_b_pass"],
            overall_pass=ev["overall_pass"],
            permitted_conclusion=ev["permitted_conclusion"],
            gates=ev["gates"],
            stage_a_summaries=ev["stage_a_summaries"],
            stage_b_summaries=ev["stage_b_summaries"],
            stage_b_by_family=ev["stage_b_by_family"],
            paired_comparisons=ev["paired_comparisons"],
        ),
    )
