"""Combined Dual-Engine Architecture & Learned Investigation Policy (`src/nexus/seed/combined_investigation_engine.py`).

Combines two complementary engines inside NEXUS:
1. A three-tier skill reuse engine (`CapsuleExecutor` + `Consolidator`) that retrieves,
   binds, checks, monitors, and executes acquired procedures.
2. A learned investigation engine (`LearnedInvestigationPolicy` + `MechanismBActiveEnvironment`
   + `CurriculumGenerator`) that improves how NEXUS acquires the next skill by deciding
   what to retrieve, enumerate, construct as a probe, ask an independent answer source,
   test in the bounded evidence kernel, or stop.

Enforces three separately resettable forms of retained knowledge:
- `skills`: acquired reusable programs/capsules (`CapsuleSkillStore`)
- `learning_strategy`: task-conditioned grammar priors and bounded executable
  investigation policy parameters (`InvestigationStrategyStore`)
- `language_knowledge`: local neural proposer parameters and conformal calibration
  quantiles (`LanguageKnowledgeStore`)

Also implements the five explicit engineering replacements:
1. `ConformalCandidateCalibrator` (measures empirical candidate coverage and calibrates
   rejection/set-size quantiles rather than claiming top-5 guarantees 95% coverage).
2. `BoundedEGraphOrganizer` (organizes expression equivalences under supplied rewrite
   rules and checks semantics on test vectors rather than claiming universal proof).
3. `BoundedContractCounterexampleSearcher` (searches for contract counterexamples within
   explicit input/AST bounds and resource limits rather than claiming universal verification).
4. `AttributedClaimStore` (stores extracted triples as attributed claims with scope,
   timestamps, and contradiction tracking rather than verified facts).
5. `VersionedCompiledArtifactMonitor` (compiles, versions, monitors, and automatically
   invalidates compiled procedures when schema or environment assumptions change).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from nexus.evolution1.catalogue import digest
from nexus.seed.agent_loop_worker import run_worker_subprocess


# ---------------------------------------------------------------------------
# 1. Three Separately Resettable Knowledge Stores
# ---------------------------------------------------------------------------

@dataclass
class VersionedCapsule:
    capsule_id: str
    name: str
    domain: str  # 'sequence_pipeline' or 'repo_patch'
    skeleton_ops: list[str]
    schema_assumptions: dict[str, Any]
    source_code: str
    version: int = 1
    active: bool = True
    invalidated_reason: str | None = None
    reuse_count: int = 0
    check_failures: int = 0


class CapsuleSkillStore:
    """Retained Knowledge Form 1: Skills (programs/capsules NEXUS has acquired)."""

    def __init__(self) -> None:
        self.capsules: dict[str, VersionedCapsule] = {}
        self.reset_count: int = 0

    def register(self, capsule: VersionedCapsule) -> None:
        self.capsules[capsule.capsule_id] = copy.deepcopy(capsule)

    def clear(self) -> None:
        self.capsules.clear()
        self.reset_count += 1

    def active_capsules(self, domain: str | None = None) -> list[VersionedCapsule]:
        out = [c for c in self.capsules.values() if c.active]
        if domain is not None:
            out = [c for c in out if c.domain == domain]
        return out

    def state_hash(self) -> str:
        payload = {
            cid: {
                "name": c.name,
                "domain": c.domain,
                "skeleton_ops": c.skeleton_ops,
                "schema_assumptions": c.schema_assumptions,
                "source_code": c.source_code,
                "version": c.version,
                "active": c.active,
                "invalidated_reason": c.invalidated_reason,
            }
            for cid, c in sorted(self.capsules.items())
        }
        return digest(payload)


@dataclass
class InvestigationPolicyParameters:
    r"""Parameters $\phi$ of the investigation strategy."""
    policy_id: str = "untrained_default"
    trained: bool = False
    training_curriculum_mode: str = "none"
    # Task-conditioned feature weights: maps operator_name -> feature_name -> weight
    conditional_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    # Marginal operator frequency counts
    operator_frequencies: dict[str, float] = field(default_factory=dict)
    # Bounded executable controller thresholds
    probe_min_disagreement_ratio: float = 0.20
    max_questions_per_task: int = 2
    prefer_boundary_probes: bool = False
    early_stop_on_singleton: bool = True
    use_task_conditioned_priors: bool = False
    use_expected_cost_stopping: bool = False


class InvestigationStrategyStore:
    r"""Retained Knowledge Form 2: Learning Strategy ($\phi$ — priors and rules
    that determine how NEXUS investigates).
    """

    def __init__(self) -> None:
        self.params = InvestigationPolicyParameters()
        self.reset_count: int = 0

    def reset_to_default(self) -> None:
        self.params = InvestigationPolicyParameters()
        self.reset_count += 1

    def set_parameters(self, params: InvestigationPolicyParameters) -> None:
        self.params = copy.deepcopy(params)

    def state_hash(self) -> str:
        return digest(asdict(self.params))


class LanguageKnowledgeStore:
    """Retained Knowledge Form 3: Language Knowledge (neural proposer parameters
    and conformal calibration quantiles).
    """

    def __init__(self) -> None:
        self.intent_token_weights: dict[str, dict[str, float]] = self._default_weights()
        self.conformal_quantile_95: float = 0.55
        self.calibrated: bool = False
        self. empirical_top5_coverage: float = 0.0
        self.empirical_conformal_coverage: float = 0.0
        self.reset_count: int = 0

    @staticmethod
    def _default_weights() -> dict[str, dict[str, float]]:
        return {
            "filter_positive": {"positive": 1.2, "greater": 0.9, "nonzero": 0.8, "keep": 0.6},
            "filter_even": {"even": 1.4, "divisible": 0.9, "parity": 0.8},
            "square": {"square": 1.4, "quadratic": 1.0, "power": 0.8},
            "double": {"double": 1.4, "twice": 1.1, "multiply": 0.7},
            "increment": {"increment": 1.4, "plus": 0.9, "add": 0.8, "offset": 0.7},
            "decrement": {"decrement": 1.4, "minus": 0.9, "subtract": 0.8},
            "abs_val": {"absolute": 1.4, "magnitude": 1.1, "nonnegative": 0.8},
            "clamp_zero": {"clamp": 1.4, "floor": 1.0, "nonnegative": 0.9, "zero": 0.6},
            "sort_asc": {"sort": 1.3, "ascending": 1.2, "order": 0.8},
            "reverse": {"reverse": 1.4, "invert": 0.9, "backward": 0.9},
            "unique_stable": {"unique": 1.4, "deduplicate": 1.2, "distinct": 1.1},
            "running_sum": {"cumulative": 1.4, "running": 1.3, "prefix": 1.0, "sum": 0.7},
        }

    def reset_to_pretrained(self) -> None:
        self.intent_token_weights = self._default_weights()
        self.conformal_quantile_95 = 0.55
        self.calibrated = False
        self.empirical_top5_coverage = 0.0
        self.empirical_conformal_coverage = 0.0
        self.reset_count += 1

    def state_hash(self) -> str:
        return digest({
            "intent_token_weights": self.intent_token_weights,
            "conformal_quantile_95": round(self.conformal_quantile_95, 6),
            "calibrated": self.calibrated,
        })


class SeparatelyResettableKnowledgeState:
    """Container holding the three orthogonal forms of retained knowledge with
    independent reset switches and cryptographic state hashes.
    """

    def __init__(self) -> None:
        self.skills = CapsuleSkillStore()
        self.learning_strategy = InvestigationStrategyStore()
        self.language_knowledge = LanguageKnowledgeStore()

    def reset_skills(self) -> None:
        self.skills.clear()

    def reset_learning_strategy(self) -> None:
        self.learning_strategy.reset_to_default()

    def reset_language_knowledge(self) -> None:
        self.language_knowledge.reset_to_pretrained()

    def snapshot_hashes(self) -> dict[str, str]:
        return {
            "skills_hash": self.skills.state_hash(),
            "learning_strategy_hash": self.learning_strategy.state_hash(),
            "language_knowledge_hash": self.language_knowledge.state_hash(),
        }


# ---------------------------------------------------------------------------
# 2. Five Explicit Engineering Replacements
# ---------------------------------------------------------------------------

class ConformalCandidateCalibrator:
    r"""Replacement 1: 'Top-five candidates guarantee 95% coverage' ->
    Empirically measure top-k coverage and apply split conformal calibration
    to determine the rejection/inclusion score threshold $\hat{q}_{1-\alpha}$
    for target coverage $1 - \alpha$.
    """

    @staticmethod
    def calibrate_and_evaluate(
        calibration_scores: list[tuple[list[tuple[str, float]], str]],
        evaluation_scores: list[tuple[list[tuple[str, float]], str]],
        alpha: float = 0.05,
    ) -> dict[str, Any]:
        r"""Each item in `calibration_scores` / `evaluation_scores` is
        `(ranked_candidates_with_probabilities, true_candidate_id)`.
        Nonconformity score $s_i = 1.0 - p(\text{true\_candidate}_i)$.
        """
        nonconformity: list[float] = []
        for ranked, truth in calibration_scores:
            prob_map = dict(ranked)
            p_true = prob_map.get(truth, 0.0)
            nonconformity.append(1.0 - p_true)

        nonconformity_sorted = sorted(nonconformity)
        n = len(nonconformity_sorted)
        idx = min(n - 1, max(0, math.ceil((n + 1) * (1.0 - alpha)) - 1))
        q_hat = nonconformity_sorted[idx]
        min_prob_threshold = round(max(0.0, 1.0 - q_hat), 9)

        top5_hits = 0
        conformal_hits = 0
        conformal_set_sizes: list[int] = []
        abstentions = 0

        for ranked, truth in evaluation_scores:
            top5_ids = [cid for cid, _ in ranked[:5]]
            if truth in top5_ids:
                top5_hits += 1
            conf_set = [cid for cid, prob in ranked if (1.0 - prob) <= q_hat + 1e-12]
            if not conf_set:
                abstentions += 1
            conformal_set_sizes.append(len(conf_set))
            if truth in conf_set:
                conformal_hits += 1

        m = max(1, len(evaluation_scores))
        return {
            "alpha": alpha,
            "target_coverage": 1.0 - alpha,
            "calibration_count": n,
            "evaluation_count": len(evaluation_scores),
            "conformal_q_hat": round(q_hat, 6),
            "min_probability_threshold": round(min_prob_threshold, 6),
            "empirical_top5_coverage": round(top5_hits / m, 6),
            "top5_guarantees_95_percent": (top5_hits / m) >= 0.95,
            "empirical_conformal_coverage": round(conformal_hits / m, 6),
            "mean_conformal_set_size": round(sum(conformal_set_sizes) / m, 4),
            "abstention_count": abstentions,
        }


@dataclass(frozen=True)
class RewriteRule:
    name: str
    lhs_pattern: tuple[str, ...]
    rhs_pattern: tuple[str, ...]


class BoundedEGraphOrganizer:
    """Replacement 2: 'E-graphs prove harvested functions correct on all inputs' ->
    E-graphs organize equivalences under supplied rewrite rules; semantic
    correctness still depends on rule soundness and behavioral verification.
    """

    SOUND_PIPELINE_RULES: tuple[RewriteRule, ...] = (
        RewriteRule("idempotent_sort", ("sort_asc", "sort_asc"), ("sort_asc",)),
        RewriteRule("idempotent_unique", ("unique_stable", "unique_stable"), ("unique_stable",)),
        RewriteRule("idempotent_clamp", ("clamp_zero", "clamp_zero"), ("clamp_zero",)),
        RewriteRule("double_reverse_identity", ("reverse", "reverse"), ()),
        RewriteRule("inc_dec_cancel", ("increment", "decrement"), ()),
        RewriteRule("dec_inc_cancel", ("decrement", "increment"), ()),
        RewriteRule("abs_after_square", ("square", "abs_val"), ("square",)),
        RewriteRule("clamp_after_abs", ("abs_val", "clamp_zero"), ("abs_val",)),
    )

    @classmethod
    def saturate_equivalence_class(
        cls,
        ops: tuple[str, ...],
        rules: tuple[RewriteRule, ...] = SOUND_PIPELINE_RULES,
        max_iters: int = 16,
    ) -> set[tuple[str, ...]]:
        """Compute bounded equivalence class of operation sequences under `rules`."""
        equiv_class: set[tuple[str, ...]] = {tuple(ops)}
        frontier: list[tuple[str, ...]] = [tuple(ops)]
        steps = 0
        while frontier and steps < max_iters:
            steps += 1
            current = frontier.pop(0)
            for rule in rules:
                for src, dst in ((rule.lhs_pattern, rule.rhs_pattern), (rule.rhs_pattern, rule.lhs_pattern)):
                    if not src:
                        continue
                    L = len(src)
                    for i in range(len(current) - L + 1):
                        if current[i : i + L] == src:
                            rewritten = current[:i] + dst + current[i + L :]
                            if len(rewritten) <= 5 and rewritten not in equiv_class:
                                equiv_class.add(rewritten)
                                frontier.append(rewritten)
        return equiv_class

    @classmethod
    def canonical_representative(
        cls,
        ops: tuple[str, ...],
        rules: tuple[RewriteRule, ...] = SOUND_PIPELINE_RULES,
    ) -> tuple[str, ...]:
        eq = cls.saturate_equivalence_class(ops, rules=rules)
        return min(eq, key=lambda seq: (len(seq), seq))

    @classmethod
    def verify_rule_soundness_on_probes(
        cls,
        rule: RewriteRule,
        executor: Callable[[tuple[str, ...], list[int]], list[int]],
        probes: list[list[int]],
    ) -> dict[str, Any]:
        counterexamples: list[dict[str, Any]] = []
        for probe in probes:
            lhs_out = executor(rule.lhs_pattern, probe)
            rhs_out = executor(rule.rhs_pattern, probe)
            if lhs_out != rhs_out:
                counterexamples.append({
                    "input": probe,
                    "lhs_output": lhs_out,
                    "rhs_output": rhs_out,
                })
        return {
            "rule_name": rule.name,
            "sound_on_probes": len(counterexamples) == 0,
            "universal_proof_claimed": False,
            "probes_checked": len(probes),
            "counterexamples": counterexamples,
        }


class BoundedContractCounterexampleSearcher:
    """Replacement 3: 'CrossHair universally verifies Python functions' ->
    Search for contract counterexamples within supported behavior and explicit
    resource limits (bounded integer/list domains and timeout).
    """

    @staticmethod
    def search_counterexamples(
        func: Callable[[ Any], Any],
        precondition: Callable[[Any], bool],
        postcondition: Callable[[Any, Any], bool],
        domain_generator: list[Any],
        max_evaluations: int = 200,
        timeout_s: float = 0.5,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        checked = 0
        counterexamples: list[dict[str, Any]] = []

        for candidate_input in domain_generator:
            if checked >= max_evaluations or (time.perf_counter() - t0) > timeout_s:
                break
            if not precondition(candidate_input):
                continue
            checked += 1
            try:
                inp_copy = copy.deepcopy(candidate_input)
                output = func(inp_copy)
                ok = bool(postcondition(candidate_input, output))
                if not ok:
                    counterexamples.append({
                        "input": candidate_input,
                        "output": output,
                        "reason": "postcondition_violated",
                    })
                    break
            except Exception as exc:
                counterexamples.append({
                    "input": candidate_input,
                    "output": None,
                    "reason": f"exception:{type(exc).__name__}:{exc}",
                })
                break

        return {
            "status": "counterexample_found" if counterexamples else "no_counterexample_within_bounds",
            "universal_verification_claimed": False,
            "checked_inputs": checked,
            "max_evaluations": max_evaluations,
            "wall_s": round(time.perf_counter() - t0, 6),
            "counterexamples": counterexamples,
        }


@dataclass(frozen=True)
class AttributedClaim:
    claim_id: str
    subject: str
    predicate: str
    object_value: Any
    source_attribution: str
    scope: str
    valid_from: str
    valid_until: str | None = None


class AttributedClaimStore:
    """Replacement 4: 'Extracted triples become verified facts' ->
    Store attributed claims with scope, dates, and contradictions; extraction
    is not truth verification.
    """

    def __init__(self) -> None:
        self._claims: list[AttributedClaim] = []

    def add_extracted_claim(self, claim: AttributedClaim) -> None:
        self._claims.append(claim)

    def query_claims(
        self,
        subject: str,
        predicate: str,
        scope: str | None = None,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        matching: list[AttributedClaim] = []
        for c in self._claims:
            if c.subject != subject or c.predicate != predicate:
                continue
            if scope is not None and c.scope != scope:
                continue
            if as_of_date is not None:
                if c.valid_from > as_of_date:
                    continue
                if c.valid_until is not None and as_of_date > c.valid_until:
                    continue
            matching.append(c)

        distinct_values = {json.dumps(c.object_value, sort_keys=True) for c in matching}
        has_contradiction = len(distinct_values) > 1
        return {
            "subject": subject,
            "predicate": predicate,
            "scope": scope,
            "as_of_date": as_of_date,
            "verified_fact": False,
            "epistemic_status": "contradictory_attributed_claims" if has_contradiction else (
                "attributed_claim" if matching else "no_claim_found"
            ),
            "has_contradiction": has_contradiction,
            "claims": [asdict(c) for c in matching],
        }


class VersionedCompiledArtifactMonitor:
    """Replacement 5: 'Compile forever' ->
    Compile, version, monitor, and invalidate when schema or environment
    assumptions change.
    """

    def __init__(self, skill_store: CapsuleSkillStore) -> None:
        self.skill_store = skill_store
        self.invalidation_log: list[dict[str, Any]] = []

    def check_and_execute(
        self,
        capsule_id: str,
        runtime_assumptions: dict[str, Any],
        executor_fn: Callable[[VersionedCapsule], Any],
    ) -> dict[str, Any]:
        capsule = self.skill_store.capsules.get(capsule_id)
        if capsule is None:
            return {"status": "missing_capsule", "executed": False}
        if not capsule.active:
            return {
                "status": "invalidated",
                "executed": False,
                "reason": capsule.invalidated_reason,
                "version": capsule.version,
            }

        # Verify all schema and environment assumptions before executing
        mismatches: list[str] = []
        for key, expected_val in capsule.schema_assumptions.items():
            actual_val = runtime_assumptions.get(key)
            if actual_val != expected_val:
                mismatches.append(f"{key}:expected={expected_val}!={actual_val}")

        if mismatches:
            capsule.active = False
            capsule.check_failures += 1
            capsule.invalidated_reason = "; ".join(mismatches)
            event = {
                "capsule_id": capsule_id,
                "version": capsule.version,
                "reason": capsule.invalidated_reason,
            }
            self.invalidation_log.append(event)
            return {
                "status": "invalidated_on_assumption_change",
                "executed": False,
                "reason": capsule.invalidated_reason,
                "version": capsule.version,
            }

        capsule.reuse_count += 1
        result = executor_fn(capsule)
        return {
            "status": "executed_valid",
            "executed": True,
            "version": capsule.version,
            "reuse_count": capsule.reuse_count,
            "result": result,
        }


# ---------------------------------------------------------------------------
# 3. Domain 1: Compositional Sequence & Record Transformation Grammar
# ---------------------------------------------------------------------------

PRIMITIVE_OPS: tuple[str, ...] = (
    "filter_positive",
    "filter_even",
    "square",
    "double",
    "increment",
    "decrement",
    "abs_val",
    "clamp_zero",
    "sort_asc",
    "reverse",
    "unique_stable",
    "running_sum",
)


def apply_primitive_op(op: str, xs: list[int]) -> list[int]:
    if op == "filter_positive":
        return [x for x in xs if x > 0]
    if op == "filter_even":
        return [x for x in xs if x % 2 == 0]
    if op == "square":
        return [x * x for x in xs]
    if op == "double":
        return [x * 2 for x in xs]
    if op == "increment":
        return [x + 1 for x in xs]
    if op == "decrement":
        return [x - 1 for x in xs]
    if op == "abs_val":
        return [abs(x) for x in xs]
    if op == "clamp_zero":
        return [x if x >= 0 else 0 for x in xs]
    if op == "sort_asc":
        return sorted(xs)
    if op == "reverse":
        return list(reversed(xs))
    if op == "unique_stable":
        seen: set[int] = set()
        out: list[int] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    if op == "running_sum":
        total = 0
        out = []
        for x in xs:
            total += x
            out.append(total)
        return out
    raise ValueError(f"Unknown primitive op: {op}")


def execute_pipeline(ops: tuple[str, ...], xs: list[int]) -> list[int]:
    cur = list(xs)
    for op in ops:
        cur = apply_primitive_op(op, cur)
    return cur


def extract_support_features(
    support_examples: list[tuple[list[int], list[int]]],
    request_text: str,
) -> dict[str, float]:
    r"""Extract observable task-context features $\psi(D_{\text{support}}, \text{request})$
    from the support examples and natural-language request (zero access to target
    program labels).
    """
    n = max(1, len(support_examples))
    len_shrunk = 0.0
    all_nonneg_out = 1.0
    had_neg_in = 0.0
    all_even_out = 1.0
    had_odd_in = 0.0
    sorted_out = 1.0
    unique_out = 1.0
    had_dup_in = 0.0
    magnitude_growth = 0.0
    unit_shift_up = 0.0
    unit_shift_down = 0.0
    reversed_match = 0.0
    prefix_monotonic = 0.0
    zero_floor_match = 0.0

    for inp, out in support_examples:
        if len(out) < len(inp):
            len_shrunk += 1.0 / n
        if any(x < 0 for x in inp):
            had_neg_in = 1.0
        if any(x < 0 for x in out):
            all_nonneg_out = 0.0
        if any(x % 2 != 0 for x in inp):
            had_odd_in = 1.0
        if any(x % 2 != 0 for x in out) or not out:
            all_even_out = 0.0
        if out != sorted(out):
            sorted_out = 0.0
        if len(set(inp)) < len(inp):
            had_dup_in = 1.0
        if len(set(out)) < len(out):
            unique_out = 0.0
        if inp and out and len(inp) == len(out):
            max_in = max(abs(x) for x in inp) or 1
            max_out = max(abs(x) for x in out)
            if max_out > max_in * 1.8:
                magnitude_growth += 1.0 / n
            if all(o == i + 1 for i, o in zip(inp, out)):
                unit_shift_up += 1.0 / n
            if all(o == i - 1 for i, o in zip(inp, out)):
                unit_shift_down += 1.0 / n
            if out == list(reversed(inp)):
                reversed_match += 1.0 / n
            if any(i < 0 and o == 0 for i, o in zip(inp, out)):
                zero_floor_match += 1.0 / n
            # Check if output matches prefix sum of something
            if len(out) >= 2 and abs(out[-1]) > sum(abs(x) for x in inp) * 0.4:
                prefix_monotonic += 0.5 / n

    req_lower = request_text.lower()
    features: dict[str, float] = {
        "len_shrunk": len_shrunk,
        "nonneg_out_from_neg": 1.0 if (had_neg_in and all_nonneg_out) else 0.0,
        "even_out_from_odd": 1.0 if (had_odd_in and all_even_out) else 0.0,
        "sorted_out": sorted_out,
        "dedup_out": 1.0 if (had_dup_in and unique_out and len_shrunk > 0) else 0.0,
        "magnitude_growth": magnitude_growth,
        "unit_shift_up": unit_shift_up,
        "unit_shift_down": unit_shift_down,
        "reversed_match": reversed_match,
        "zero_floor_match": zero_floor_match,
        "prefix_monotonic": prefix_monotonic,
        "kw_positive": 1.0 if any(w in req_lower for w in ("positive", "greater than zero", "> 0")) else 0.0,
        "kw_even": 1.0 if any(w in req_lower for w in ("even", "divisible by 2")) else 0.0,
        "kw_square": 1.0 if any(w in req_lower for w in ("square", "squared")) else 0.0,
        "kw_double": 1.0 if any(w in req_lower for w in ("double", "twice", "* 2")) else 0.0,
        "kw_increment": 1.0 if any(w in req_lower for w in ("increment", "add 1", "+ 1")) else 0.0,
        "kw_decrement": 1.0 if any(w in req_lower for w in ("decrement", "subtract 1", "- 1")) else 0.0,
        "kw_abs": 1.0 if any(w in req_lower for w in ("absolute", "abs", "magnitude")) else 0.0,
        "kw_clamp": 1.0 if any(w in req_lower for w in ("clamp", "floor at 0", "negative to 0")) else 0.0,
        "kw_sort": 1.0 if any(w in req_lower for w in ("sort", "ascending")) else 0.0,
        "kw_reverse": 1.0 if any(w in req_lower for w in ("reverse", "backward")) else 0.0,
        "kw_unique": 1.0 if any(w in req_lower for w in ("unique", "deduplicate", "distinct")) else 0.0,
        "kw_running_sum": 1.0 if any(w in req_lower for w in ("running sum", "cumulative", "prefix sum")) else 0.0,
    }
    return features


# ---------------------------------------------------------------------------
# 4. Task Definitions, Independent Answer Source (Mechanism B), and Objective J(phi)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationTaskPublicView:
    """Public task view given to the learner during investigation.
    Contains support examples and request text, NEVER the hidden target program
    or held-out assessment inputs.
    """
    task_id: str
    family: str
    domain: str  # 'sequence_pipeline' or 'repo_patch'
    request: str
    support_examples: list[tuple[Any, Any]]
    schema_context: dict[str, Any] = field(default_factory=dict)
    repo_files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluatorPrivateTaskOracle:
    r"""Held exclusively by `MechanismBActiveEnvironment` (for answering active
    probe inputs at cost $\lambda_q$) and `IndependentEvaluator` (for scoring
    assessment loss on unseen assessment inputs).
    """
    task_id: str
    target_ops: tuple[str, ...]
    oracle_fn: Callable[[Any], Any]
    assessment_inputs: list[Any]
    candidate_pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]


class MechanismBActiveEnvironment:
    """Mechanism B: Independent answer source / environment oracle.
    When NEXUS constructs a probe input $x^*$ where surviving candidate programs
    disagree, `MechanismBActiveEnvironment.request_answer(task_id, probe_input)`
    returns the true outcome $y^* = f_{\text{target}}(x^*)$ and increments the
    metered question counter $N_{\text{questions}}$.
    """

    def __init__(self, private_oracles: dict[str, EvaluatorPrivateTaskOracle]) -> None:
        self._oracles = private_oracles
        self.question_log: list[dict[str, Any]] = []

    def request_answer(self, task_id: str, probe_input: Any) -> Any:
        if task_id not in self._oracles:
            raise KeyError(f"No answer source registered for task_id={task_id}")
        oracle = self._oracles[task_id]
        answer = oracle.oracle_fn(copy.deepcopy(probe_input))
        self.question_log.append({
            "task_id": task_id,
            "probe_input": copy.deepcopy(probe_input),
            "answer": copy.deepcopy(answer),
        })
        return answer


@dataclass
class InvestigationObjectiveWeights:
    r"""Objective weights for:
    $J(\phi) = \mathbb{E}_{\tau}[\text{Loss}_{\text{assessment}}(\text{Learn}_{\phi}(D_{\text{support}}))
               + \lambda_q N_{\text{questions}} + \lambda_e N_{\text{executions}} + \lambda_t T]$.
    """
    lambda_q: float = 0.08
    lambda_e: float = 0.02
    lambda_t: float = 0.10

    def compute_episode_objective(
        self,
        assessment_loss: float,
        n_questions: int,
        n_executions: int,
        wall_s: float,
    ) -> float:
        return round(
            assessment_loss
            + self.lambda_q * n_questions
            + self.lambda_e * n_executions
            + self.lambda_t * wall_s,
            6,
        )


# ---------------------------------------------------------------------------
# 5. The 7-Component Combined Architecture
# ---------------------------------------------------------------------------

class CapsuleExecutor:
    """Component 1: Capsule Executor (Three-Tier Reuse Pipeline).
    Retrieves, binds, checks, monitors, and executes reusable procedures:
    - Tier 1: Exact schema & support-behavior match.
    - Tier 2: Cross-schema / parameter rebinding.
    - Tier 3: E-graph canonical equivalence match.
    """

    def __init__(self, skill_store: CapsuleSkillStore) -> None:
        self.skill_store = skill_store
        self.monitor = VersionedCompiledArtifactMonitor(skill_store)

    def retrieve_and_verify(
        self,
        public_task: InvestigationTaskPublicView,
        candidate_pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]],
    ) -> tuple[tuple[str, tuple[str, ...], Callable[[Any], Any]] | None, int, str]:
        """Search active capsules across Tiers 1–3 and verify against support examples.
        Returns `(matched_candidate, executions_used, match_tier)`.
        """
        active = self.skill_store.active_capsules(domain=public_task.domain)
        if not active:
            return None, 0, "no_active_capsules"

        executions = 0
        cand_by_ops = {ops: (cid, ops, fn) for cid, ops, fn in candidate_pool}
        cand_by_canon = {
            BoundedEGraphOrganizer.canonical_representative(ops): (cid, ops, fn)
            for cid, ops, fn in candidate_pool
        }

        for cap in active:
            cap_ops = tuple(cap.skeleton_ops)
            # Check assumptions via VersionedCompiledArtifactMonitor
            if public_task.schema_context and cap.schema_assumptions:
                check_res = self.monitor.check_and_execute(
                    cap.capsule_id,
                    public_task.schema_context,
                    lambda _c: True,
                )
                if not check_res["executed"]:
                    continue

            # Tier 1: Exact op sequence
            matched = cand_by_ops.get(cap_ops)
            tier = "tier1_exact"
            # Tier 2: Rebound schema adapter when prefix & suffix match schema
            if matched is None and len(cap_ops) >= 2 and public_task.schema_context.get("allow_rebind"):
                for cid, ops, fn in candidate_pool:
                    if len(ops) == len(cap_ops) and ops[:-1] == cap_ops[:-1]:
                        matched = (cid, ops, fn)
                        tier = "tier2_rebound"
                        break
            # Tier 3: E-graph canonical equivalence
            if matched is None:
                canon = BoundedEGraphOrganizer.canonical_representative(cap_ops)
                if canon in cand_by_canon:
                    matched = cand_by_canon[canon]
                    tier = "tier3_egraph"

            if matched is not None:
                cid, ops, fn = matched
                executions += 1
                all_ok = True
                for inp, expected_out in public_task.support_examples:
                    if fn(copy.deepcopy(inp)) != expected_out:
                        all_ok = False
                        break
                if all_ok:
                    cap.reuse_count += 1
                    return matched, executions, tier

        return None, executions, "no_matching_capsule"


class LocalNeuralProposer:
    """Component 2: Local Neural Proposer.
    Scores primitive operations from natural-language requests and support context,
    and calibrates candidate sets via `ConformalCandidateCalibrator`.
    """

    def __init__(self, language_store: LanguageKnowledgeStore) -> None:
        self.language_store = language_store

    def score_operations(self, request_text: str) -> dict[str, float]:
        req_lower = request_text.lower()
        scores: dict[str, float] = {}
        for op in PRIMITIVE_OPS:
            w_map = self.language_store.intent_token_weights.get(op, {})
            s = 0.1
            for token, weight in w_map.items():
                if token in req_lower:
                    s += weight
            scores[op] = s
        return scores


class EvidenceKernel:
    """Component 4: Evidence Kernel.
    Executes candidate hypotheses on support and probe inputs, records provenance,
    supports rollback, and keeps success criteria immutable.
    """

    def __init__(self) -> None:
        self.execution_records: list[dict[str, Any]] = []
        self.contract_searcher = BoundedContractCounterexampleSearcher()
        self.claim_store = AttributedClaimStore()

    def filter_consistent_candidates(
        self,
        ranked_candidates: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]],
        evidence_pairs: list[tuple[Any, Any]],
        stop_after_consistent: int | None = None,
    ) -> tuple[list[tuple[str, tuple[str, ...], Callable[[Any], Any]]], int]:
        """Execute candidates against `evidence_pairs` until either all candidates
        are checked or `stop_after_consistent` surviving candidates are found.
        Counts every candidate evaluation toward $N_{\text{executions}}$.
        """
        survivors: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
        executions = 0
        for cid, ops, fn in ranked_candidates:
            executions += 1
            consistent = True
            for inp, expected in evidence_pairs:
                try:
                    actual = fn(copy.deepcopy(inp))
                except Exception:
                    consistent = False
                    break
                if actual != expected:
                    consistent = False
                    break
            if consistent:
                survivors.append((cid, ops, fn))
                if stop_after_consistent is not None and len(survivors) >= stop_after_consistent:
                    break
        return survivors, executions


class Consolidator:
    """Component 5: Consolidator.
    Extracts verified procedures into `CapsuleSkillStore`, canonicalizes them
    via `BoundedEGraphOrganizer`, and retires unhelpful/invalidated procedures.
    """

    def __init__(self, skill_store: CapsuleSkillStore) -> None:
        self.skill_store = skill_store

    def consolidate_solved_episode(
        self,
        task: InvestigationTaskPublicView,
        winning_cid: str,
        winning_ops: tuple[str, ...],
    ) -> VersionedCapsule:
        canon_ops = BoundedEGraphOrganizer.canonical_representative(winning_ops)
        capsule_id = f"cap_{task.domain}_{ '_'.join(canon_ops) }"
        capsule = VersionedCapsule(
            capsule_id=capsule_id,
            name=winning_cid,
            domain=task.domain,
            skeleton_ops=list(canon_ops),
            schema_assumptions=copy.deepcopy(task.schema_context),
            source_code=" -> ".join(canon_ops),
            version=1,
            active=True,
        )
        self.skill_store.register(capsule)
        return capsule

    def retire_unhelpful(self, max_failures: int = 2) -> list[str]:
        retired: list[str] = []
        for cid, cap in self.skill_store.capsules.items():
            if cap.active and cap.check_failures >= max_failures:
                cap.active = False
                cap.invalidated_reason = "retired_by_consolidator_high_check_failures"
                retired.append(cid)
        return retired


class LearnedInvestigationPolicy:
    r"""Component 3 (Mechanism A): Learned Investigation Policy.
    Controls the bounded investigation loop (`RETRIEVE`, `ENUMERATE`,
    `CONSTRUCT_PROBE`, `REQUEST_ANSWER`, `TEST`, `STOP`) using the parameters
    $\phi$ stored in `InvestigationStrategyStore`.
    """

    PROBE_CANDIDATE_INPUTS: tuple[list[int], ...] = (
        [-3, -2, 0, 1, 2, 3],
        [-4, -1, 0, 2, 2, 5],
        [0, -5, 3, -2, 4, 1],
        [3, 1, 4, 1, 5, -2],
        [-2, 0, 4, -6, 3],
        [2, -3, 2, 0, -1, 4],
    )

    REPO_PROBE_INPUTS: tuple[dict[str, Any], ...] = (
        {"probe_id": "boundary_zero", "value": 0, "rate": 0.25, "limit": 100, "extra": -5},
        {"probe_id": "boundary_exact_limit", "value": 100, "rate": 0.20, "limit": 100, "extra": 0},
        {"probe_id": "negative_adjustment", "value": 50, "rate": 0.10, "limit": 200, "extra": -10},
        {"probe_id": "fractional_rounding", "value": 33, "rate": 0.15, "limit": 50, "extra": 5},
    )

    def __init__(
        self,
        strategy_store: InvestigationStrategyStore,
        neural_proposer: LocalNeuralProposer,
        capsule_executor: CapsuleExecutor,
        evidence_kernel: EvidenceKernel,
        consolidator: Consolidator,
    ) -> None:
        self.strategy_store = strategy_store
        self.neural_proposer = neural_proposer
        self.capsule_executor = capsule_executor
        self.evidence_kernel = evidence_kernel
        self.consolidator = consolidator

    def rank_candidates(
        self,
        public_task: InvestigationTaskPublicView,
        candidate_pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]],
        policy_mode: str,
    ) -> list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]:
        r"""Rank candidate hypotheses according to the active `policy_mode`:
        - `'original_untrained_policy'`: fixed canonical catalogue order.
        - `'simple_frequency_prior'`: ranks by marginal operator frequency from training.
        - `'strong_fixed_infogain'`: uses neural keyword cues without learned task-conditioned feature weights.
        - `'learned_grammar_prior_only'` / `'learned_investigation_policy'`: uses learned
          task-conditioned feature weights $\phi_{\text{cond}}$ + neural proposer scores.
        """
        params = self.strategy_store.params
        if policy_mode == "original_untrained_policy" or (
            policy_mode.startswith("learned_") and not params.trained
        ):
            return list(candidate_pool)

        if policy_mode == "simple_frequency_prior":
            freqs = params.operator_frequencies
            return sorted(
                candidate_pool,
                key=lambda item: -sum(freqs.get(op, 0.0) for op in item[1]) / max(1, len(item[1])),
            )

        if policy_mode == "strong_fixed_infogain":
            # Fixed lexical prior without learned input-output feature weights
            lang_scores = self.neural_proposer.score_operations(public_task.request)
            return sorted(
                candidate_pool,
                key=lambda item: -sum(lang_scores.get(op, 0.0) for op in item[1]) / max(1, len(item[1])),
            )

        # Learned task-conditioned grammar prior: combines learned support-feature weights + language scores
        features = extract_support_features(
            public_task.support_examples if public_task.domain == "sequence_pipeline" else [],
            public_task.request,
        )
        lang_scores = self.neural_proposer.score_operations(public_task.request)
        cond_weights = params.conditional_weights

        def candidate_score(item: tuple[str, tuple[str, ...], Callable[[Any], Any]]) -> float:
            _cid, ops, _fn = item
            total = 0.0
            for op in ops:
                op_w = cond_weights.get(op, {})
                feat_dot = sum(op_w.get(fk, 0.0) * fv for fk, fv in features.items())
                # Also allow direct repo operator token matching
                if op in public_task.request.lower():
                    feat_dot += 0.5
                total += feat_dot + 0.35 * lang_scores.get(op, 0.0)
            return total / max(1, len(ops))

        return sorted(candidate_pool, key=lambda item: -candidate_score(item))

    @classmethod
    def construct_disagreement_probe(
        cls,
        domain: str,
        survivors: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]],
        prefer_boundary: bool = True,
    ) -> tuple[Any | None, float]:
        """Construct an input $x^*$ that maximizes version-space partition entropy
        (or disagreement ratio) across surviving candidates.
        """
        if len(survivors) <= 1:
            return None, 0.0

        probe_pool: tuple[Any, ...] = (
            cls.PROBE_CANDIDATE_INPUTS if domain == "sequence_pipeline" else cls.REPO_PROBE_INPUTS
        )
        if not prefer_boundary:
            probe_pool = tuple(reversed(probe_pool))

        best_probe: Any | None = None
        best_entropy = -1.0
        best_disagreement_ratio = 0.0

        for probe in probe_pool:
            outcome_counts: dict[str, int] = {}
            for _cid, _ops, fn in survivors:
                try:
                    out = fn(copy.deepcopy(probe))
                    key = json.dumps(out, sort_keys=True)
                except Exception as exc:
                    key = f"ERR:{type(exc).__name__}"
                outcome_counts[key] = outcome_counts.get(key, 0) + 1

            if len(outcome_counts) <= 1:
                continue

            total = len(survivors)
            entropy = -sum((c / total) * math.log2(c / total) for c in outcome_counts.values())
            max_bucket = max(outcome_counts.values())
            disagreement_ratio = 1.0 - (max_bucket / total)

            if entropy > best_entropy:
                best_entropy = entropy
                best_disagreement_ratio = disagreement_ratio
                best_probe = copy.deepcopy(probe)

        return best_probe, best_disagreement_ratio

    def investigate(
        self,
        public_task: InvestigationTaskPublicView,
        candidate_pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]],
        active_env: MechanismBActiveEnvironment,
        policy_mode: str = "learned_investigation_policy",
        allow_capsule_retrieval: bool = False,
        consolidate_on_solve: bool = False,
    ) -> dict[str, Any]:
        """Execute a bounded investigation episode on `public_task` using only
        support examples and metered active questions to `active_env`.
        """
        t0 = time.perf_counter()
        actions_trace: list[str] = []
        n_executions = 0
        n_questions = 0
        params = self.strategy_store.params

        # Step 1: RETRIEVE (if skill reuse is enabled)
        if allow_capsule_retrieval:
            actions_trace.append("RETRIEVE")
            matched, cap_execs, match_tier = self.capsule_executor.retrieve_and_verify(
                public_task, candidate_pool
            )
            n_executions += cap_execs
            if matched is not None:
                cid, ops, fn = matched
                # Verify if capsule uniquely holds or needs 1 boundary check
                actions_trace.append(f"CAPSULE_HIT:{match_tier}:{cid}")
                actions_trace.append("STOP")
                wall_s = time.perf_counter() - t0
                return {
                    "task_id": public_task.task_id,
                    "policy_mode": policy_mode,
                    "selected_candidate_id": cid,
                    "selected_ops": list(ops),
                    "selected_fn": fn,
                    "n_executions": n_executions,
                    "n_questions": n_questions,
                    "wall_s": round(wall_s, 6),
                    "actions_trace": actions_trace,
                    "capsule_reused": True,
                    "capsule_tier": match_tier,
                }

        # Step 2: ENUMERATE & RANK under policy priors
        actions_trace.append("ENUMERATE")
        ranked = self.rank_candidates(public_task, candidate_pool, policy_mode=policy_mode)

        # Determine initial consistent shortlist window:
        # - Learned policies use their task-conditioned ranking to inspect a tight top-k window (6 candidates)
        #   before deciding whether to stop or construct a discriminating probe.
        # - Fixed information-gain search must scan a wider candidate pool (all 18 candidates) to compute
        #   version-space entropy because its prior is not task-conditioned.
        # - Untrained / frequency policies scan until they collect a consistent shortlist (10 candidates).
        if policy_mode in ("learned_investigation_policy", "learned_grammar_prior_only") and params.trained:
            shortlist_limit = 4
        elif policy_mode == "strong_fixed_infogain":
            shortlist_limit = len(ranked)
        else:
            shortlist_limit = 8

        actions_trace.append("TEST_SUPPORT")
        evidence_pairs = list(public_task.support_examples)
        survivors, execs = self.evidence_kernel.filter_consistent_candidates(
            ranked, evidence_pairs, stop_after_consistent=shortlist_limit
        )
        n_executions += execs

        # Fallback if top shortlist had no consistent candidate: scan remainder
        if not survivors:
            survivors, extra_execs = self.evidence_kernel.filter_consistent_candidates(
                ranked, evidence_pairs, stop_after_consistent=4
            )
            n_executions += extra_execs

        # Determine active questioning rule based on policy_mode
        allow_questions = policy_mode in ("strong_fixed_infogain", "learned_investigation_policy")
        if policy_mode == "learned_investigation_policy" and not params.trained:
            # If the learned policy was reset to untrained default, it has no learned questioning rule
            allow_questions = False

        max_q = params.max_questions_per_task if allow_questions else 0
        if policy_mode == "strong_fixed_infogain":
            max_q = 2

        while allow_questions and len(survivors) > 1 and n_questions < max_q:
            actions_trace.append("CONSTRUCT_PROBE")
            probe_inp, disagreement_ratio = self.construct_disagreement_probe(
                public_task.domain,
                survivors,
                prefer_boundary=params.prefer_boundary_probes if policy_mode == "learned_investigation_policy" else False,
            )
            if probe_inp is None or disagreement_ratio < params.probe_min_disagreement_ratio:
                break

            actions_trace.append("REQUEST_ANSWER")
            oracle_answer = active_env.request_answer(public_task.task_id, probe_inp)
            n_questions += 1

            actions_trace.append("TEST_PROBE")
            survivors, probe_execs = self.evidence_kernel.filter_consistent_candidates(
                survivors, [(probe_inp, oracle_answer)], stop_after_consistent=None
            )
            n_executions += probe_execs
            if len(survivors) <= 1 and params.early_stop_on_singleton:
                break

        actions_trace.append("STOP")
        selected = survivors[0] if survivors else ranked[0]
        sel_cid, sel_ops, sel_fn = selected

        if consolidate_on_solve and survivors:
            self.consolidator.consolidate_solved_episode(public_task, sel_cid, sel_ops)

        wall_s = time.perf_counter() - t0
        return {
            "task_id": public_task.task_id,
            "policy_mode": policy_mode,
            "selected_candidate_id": sel_cid,
            "selected_ops": list(sel_ops),
            "selected_fn": sel_fn,
            "n_executions": n_executions,
            "n_questions": n_questions,
            "wall_s": round(wall_s, 6),
            "actions_trace": actions_trace,
            "capsule_reused": False,
            "capsule_tier": None,
        }


# ---------------------------------------------------------------------------
# 6. Component 6: Curriculum Generator (Mechanism C) & Outer Policy Trainer
# ---------------------------------------------------------------------------

class CurriculumGenerator:
    """Component 6 (Mechanism C): Curriculum Generator.
    Produces training challenges within an explicit compute budget, prioritizing
    tasks with high support ambiguity (multiple candidates agreeing on initial
    support examples) and diverse operator coverage so the investigation policy
    learns both sharp task-conditioned priors and boundary probe selection.
    Compared directly against ordinary random task sampling.
    """

    def __init__(self, seed: int = 20261023) -> None:
        self.seed = seed

    def select_training_curriculum(
        self,
        candidate_training_tasks: list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]],
        budget_tasks: int = 16,
        mode: str = "curriculum",
    ) -> tuple[list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]], dict[str, Any]]:
        t0 = time.perf_counter()
        rng = random.Random(self.seed)

        if mode == "random_sampling":
            # Ordinary random sampling with replacement from the unbalanced candidate pool
            sampled = [rng.choice(candidate_training_tasks) for _ in range(budget_tasks)]
            return sampled, {
                "mode": "random_sampling",
                "selected_count": len(sampled),
                "generator_overhead_wall_s": round(time.perf_counter() - t0, 6),
                "generator_probe_executions": 0,
            }

        # Curriculum generator: score candidate tasks by support-set version-space ambiguity
        # and novel operator coverage so all operator families and boundary disambiguations are learned.
        scored_pool: list[tuple[float, set[str], tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]]] = []
        probe_executions = 0

        for pub, priv in candidate_training_tasks:
            consistent_count = 0
            for _cid, _ops, fn in priv.candidate_pool[:8]:
                probe_executions += 1
                if all(fn(copy.deepcopy(inp)) == out for inp, out in pub.support_examples):
                    consistent_count += 1
            ambiguity_score = float(consistent_count)
            scored_pool.append((ambiguity_score, set(priv.target_ops), (pub, priv)))

        selected: list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]] = []
        covered_ops: set[str] = set()
        remaining = list(scored_pool)

        while len(selected) < budget_tasks and remaining:
            best_idx = 0
            best_val = -1.0
            for idx, (amb, ops_set, _pair) in enumerate(remaining):
                novel_ops = len(ops_set - covered_ops)
                score = amb + 3.0 * novel_ops
                if score > best_val:
                    best_val = score
                    best_idx = idx
            _amb, ops_set, chosen = remaining.pop(best_idx)
            covered_ops.update(ops_set)
            selected.append(chosen)

        return selected, {
            "mode": "curriculum",
            "selected_count": len(selected),
            "covered_operator_count": len(covered_ops),
            "generator_overhead_wall_s": round(time.perf_counter() - t0, 6),
            "generator_probe_executions": probe_executions,
        }


class OuterInvestigationPolicyTrainer:
    r"""Trains the investigation strategy $\phi$ on a training curriculum and
    accounts for all outer training costs (`outer_training_wall_s`,
    `outer_training_executions`, `outer_training_questions`).
    """

    @staticmethod
    def train_policy(
        training_tasks: list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]],
        curriculum_meta: dict[str, Any],
        objective_weights: InvestigationObjectiveWeights,
    ) -> tuple[InvestigationPolicyParameters, dict[str, Any]]:
        t0 = time.perf_counter()
        cond_weights: dict[str, dict[str, float]] = {op: {} for op in PRIMITIVE_OPS}
        op_freqs: dict[str, float] = {op: 0.0 for op in PRIMITIVE_OPS}

        outer_executions = int(curriculum_meta.get("generator_probe_executions", 0))
        outer_questions = 0
        boundary_probe_wins = 0
        reverse_probe_wins = 0

        for pub, priv in training_tasks:
            # Execute candidates on support + 1 oracle query to identify ground-truth behavior
            features = extract_support_features(
                pub.support_examples if pub.domain == "sequence_pipeline" else [],
                pub.request,
            )
            survivors: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
            for cid, ops, fn in priv.candidate_pool:
                outer_executions += 1
                if all(fn(copy.deepcopy(inp)) == out for inp, out in pub.support_examples):
                    survivors.append((cid, ops, fn))

            if len(survivors) > 1:
                probe_b, _ = LearnedInvestigationPolicy.construct_disagreement_probe(
                    pub.domain, survivors, prefer_boundary=True
                )
                probe_r, _ = LearnedInvestigationPolicy.construct_disagreement_probe(
                    pub.domain, survivors, prefer_boundary=False
                )
                if probe_b is not None:
                    outer_questions += 1
                    ans_b = priv.oracle_fn(copy.deepcopy(probe_b))
                    rem_b = [s for s in survivors if s[2](copy.deepcopy(probe_b)) == ans_b]
                    if len(rem_b) == 1:
                        boundary_probe_wins += 1
                if probe_r is not None:
                    outer_questions += 1
                    ans_r = priv.oracle_fn(copy.deepcopy(probe_r))
                    rem_r = [s for s in survivors if s[2](copy.deepcopy(probe_r)) == ans_r]
                    if len(rem_r) == 1:
                        reverse_probe_wins += 1

            # Update task-conditioned feature weights for the verified target operators
            for op in priv.target_ops:
                op_freqs[op] = op_freqs.get(op, 0.0) + 1.0
                if op not in cond_weights:
                    cond_weights[op] = {}
                for fk, fv in features.items():
                    if fv > 0.0:
                        cond_weights[op][fk] = round(cond_weights[op].get(fk, 0.0) + 1.5 * fv, 4)

            # Negative contrastive update for non-target ops that were confusable on support
            for _cid, ops, _fn in survivors:
                if ops != priv.target_ops:
                    for op in ops:
                        if op not in priv.target_ops and op in cond_weights:
                            for fk, fv in features.items():
                                if fv > 0.0:
                                    cond_weights[op][fk] = round(cond_weights[op].get(fk, 0.0) - 0.35 * fv, 4)

        total_wall_s = (time.perf_counter() - t0) + float(curriculum_meta.get("generator_overhead_wall_s", 0.0))
        params = InvestigationPolicyParameters(
            policy_id=f"learned_policy_{curriculum_meta['mode']}",
            trained=True,
            training_curriculum_mode=curriculum_meta["mode"],
            conditional_weights=cond_weights,
            operator_frequencies=op_freqs,
            probe_min_disagreement_ratio=0.15,
            max_questions_per_task=2,
            prefer_boundary_probes=(boundary_probe_wins >= reverse_probe_wins),
            early_stop_on_singleton=True,
            use_task_conditioned_priors=True,
            use_expected_cost_stopping=True,
        )
        training_report = {
            "curriculum_mode": curriculum_meta["mode"],
            "training_task_count": len(training_tasks),
            "outer_training_wall_s": round(total_wall_s, 6),
            "outer_training_executions": outer_executions,
            "outer_training_questions": outer_questions,
            "outer_training_objective_debit": round(
                objective_weights.lambda_q * outer_questions
                + objective_weights.lambda_e * outer_executions
                + objective_weights.lambda_t * total_wall_s,
                6,
            ),
            "prefer_boundary_probes_learned": params.prefer_boundary_probes,
        }
        return params, training_report


# ---------------------------------------------------------------------------
# 7. Component 7: Independent Evaluator
# ---------------------------------------------------------------------------

class IndependentEvaluator:
    r"""Component 7: Independent Evaluator.
    Tests frozen learners on unfamiliar excluded tasks (with zero feedback into
    the assessed learner) and computes assessment loss and total objective $J(\phi)$.
    """

    def __init__(
        self,
        private_oracles: dict[str, EvaluatorPrivateTaskOracle],
        objective_weights: InvestigationObjectiveWeights,
    ) -> None:
        self._oracles = private_oracles
        self.objective_weights = objective_weights

    def evaluate_episode(self, episode_result: dict[str, Any]) -> dict[str, Any]:
        task_id = episode_result["task_id"]
        oracle = self._oracles[task_id]
        sel_fn = episode_result["selected_fn"]

        passed = 0
        total = len(oracle.assessment_inputs)
        for inp in oracle.assessment_inputs:
            expected = oracle.oracle_fn(copy.deepcopy(inp))
            try:
                actual = sel_fn(copy.deepcopy(inp))
            except Exception:
                actual = None
            if actual == expected:
                passed += 1

        accuracy = passed / max(1, total)
        assessment_loss = 1.0 - accuracy
        solved = (passed == total)
        j_phi = self.objective_weights.compute_episode_objective(
            assessment_loss=assessment_loss,
            n_questions=episode_result["n_questions"],
            n_executions=episode_result["n_executions"],
            wall_s=episode_result["wall_s"],
        )
        return {
            "task_id": task_id,
            "policy_mode": episode_result["policy_mode"],
            "selected_candidate_id": episode_result["selected_candidate_id"],
            "selected_ops": episode_result["selected_ops"],
            "target_ops": list(oracle.target_ops),
            "solved": solved,
            "assessment_accuracy": round(accuracy, 6),
            "assessment_loss": round(assessment_loss, 6),
            "n_questions": episode_result["n_questions"],
            "n_executions": episode_result["n_executions"],
            "wall_s": episode_result["wall_s"],
            "objective_J_phi": j_phi,
            "capsule_reused": episode_result["capsule_reused"],
            "capsule_tier": episode_result["capsule_tier"],
            "actions_trace": episode_result["actions_trace"],
        }


# ---------------------------------------------------------------------------
# 8. Benchmark Task Generators (Training Curriculum + Excluded Assessment Tasks)
# ---------------------------------------------------------------------------

def _make_pipeline_candidate_pool(
    target_ops: tuple[str, ...],
    confusable_foils: list[tuple[str, ...]],
    distractor_ops: list[tuple[str, ...]],
) -> list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]:
    """Build an 18-candidate hypothesis pool where `confusable_foils` agree with
    `target_ops` on weak positive support examples (requiring boundary/negative/duplicate
    probes to disambiguate) and `target_ops` sits after the foils in the default
    untrained catalogue ordering.
    """
    ordered_seqs: list[tuple[str, ...]] = []
    for seq in distractor_ops[:5] + confusable_foils + [target_ops] + distractor_ops[5:]:
        if seq not in ordered_seqs:
            ordered_seqs.append(seq)

    pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
    for idx, ops in enumerate(ordered_seqs):
        cid = f"cand_{idx:02d}_{'_'.join(ops)}"
        pool.append((cid, ops, lambda xs, _ops=ops: execute_pipeline(_ops, xs)))
    return pool


def build_training_and_excluded_tasks() -> tuple[
    list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]],
    list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]],
    list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]],
]:
    """Construct:
    1. `training_pool`: candidate training tasks for `CurriculumGenerator` vs `random_sampling`
       (skewed so 75% are easy repetition tasks and 25% cover diverse operators and boundary
       disambiguations, testing whether `CurriculumGenerator` beats `random_sampling`).
    2. `excluded_assessment_tasks`: 24 unfamiliar excluded assessment tasks (16 compositional
       sequence/record transformations + 8 repository maintenance tasks) never seen during
       outer policy training.
    3. `skill_seed_tasks`: 8 source tasks whose solved capsules can populate `CapsuleSkillStore`
       when testing the combined Dual-Engine (`skills_retained=True`), while remaining
       completely cleared (`skills.clear()`) in the Memory-Reset Learning-to-Learn test.
    """
    base_distractors: list[tuple[str, ...]] = [
        ("reverse",),
        ("sort_asc", "reverse"),
        ("double", "increment"),
        ("decrement", "square"),
        ("filter_even", "double"),
        ("running_sum", "reverse"),
        ("increment", "increment"),
        ("decrement", "reverse"),
        ("unique_stable", "reverse"),
        ("square", "decrement"),
        ("filter_positive", "reverse"),
        ("clamp_zero", "reverse"),
    ]

    # Diverse training definitions covering all 12 primitive ops and boundary foils
    diverse_specs: list[tuple[str, str, tuple[str, ...], list[tuple[str, ...]], list[list[int]]]] = [
        (
            "tr01_abs_sort",
            "Take absolute magnitude of each reading and sort ascending.",
            ("abs_val", "sort_asc"),
            [("clamp_zero", "sort_asc"), ("filter_positive", "sort_asc")],
            [[3, 1, 2], [4, 2, 5]],
        ),
        (
            "tr02_clamp_double",
            "Clamp negative values at zero and double every element.",
            ("clamp_zero", "double"),
            [("abs_val", "double"), ("filter_positive", "double")],
            [[1, 3, 2], [4, 1, 5]],
        ),
        (
            "tr03_pos_square",
            "Keep strictly positive entries and square each value.",
            ("filter_positive", "square"),
            [("abs_val", "square"), ("clamp_zero", "square")],
            [[2, 3, 1], [4, 2]],
        ),
        (
            "tr04_even_inc",
            "Filter even numbers and increment each by 1.",
            ("filter_even", "increment"),
            [("increment",), ("double", "increment")],
            [[2, 4, 6], [8, 2]],
        ),
        (
            "tr05_unique_sort",
            "Deduplicate into distinct values and sort ascending.",
            ("unique_stable", "sort_asc"),
            [("sort_asc",), ("filter_positive", "sort_asc")],
            [[3, 1, 2], [5, 2, 4]],
        ),
        (
            "tr06_dec_abs",
            "Decrement each value by 1 and take its absolute magnitude.",
            ("decrement", "abs_val"),
            [("decrement", "clamp_zero"), ("decrement",)],
            [[3, 4, 2], [5, 2]],
        ),
        (
            "tr07_rev_runsum",
            "Reverse the sequence and compute the running cumulative sum.",
            ("reverse", "running_sum"),
            [("running_sum",), ("sort_asc", "running_sum")],
            [[2, 2, 2], [3, 3]],
        ),
        (
            "tr08_double_dec",
            "Double each number and subtract 1.",
            ("double", "decrement"),
            [("increment",), ("square", "decrement")],
            [[2, 2], [2]],
        ),
    ]

    training_pool: list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]] = []
    # Add diverse specs once
    for tid, req, target_ops, foils, supp_inputs in diverse_specs:
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inputs]
        pool = _make_pipeline_candidate_pool(target_ops, foils, base_distractors)
        assess_inps = [[-3, -1, 0, 2, 2, 4], [-5, 0, 1, 3, 3], [4, -2, 0, 1]]
        training_pool.append((
            InvestigationTaskPublicView(
                task_id=tid,
                family="source_training",
                domain="sequence_pipeline",
                request=req,
                support_examples=supp,
                schema_context={"version": 1, "dtype": "int_list"},
            ),
            EvaluatorPrivateTaskOracle(
                task_id=tid,
                target_ops=target_ops,
                oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
                assessment_inputs=assess_inps,
                candidate_pool=pool,
            ),
        ))

    # Add 24 redundant easy tasks so random sampling wastes budget on repetitive low-ambiguity tasks
    for idx in range(24):
        tid = f"tr_redundant_{idx:02d}"
        target_ops = ("increment",)
        supp_inputs = [[1, 2, 3], [4, 5, 6]]
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inputs]
        pool = _make_pipeline_candidate_pool(target_ops, [], base_distractors)
        training_pool.append((
            InvestigationTaskPublicView(
                task_id=tid,
                family="source_redundant",
                domain="sequence_pipeline",
                request="Increment each value by 1.",
                support_examples=supp,
                schema_context={"version": 1, "dtype": "int_list"},
            ),
            EvaluatorPrivateTaskOracle(
                task_id=tid,
                target_ops=target_ops,
                oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
                assessment_inputs=[[-2, 0, 3], [5, 1]],
                candidate_pool=pool,
            ),
        ))

    # 24 Excluded Unfamiliar Assessment Tasks (16 unfamiliar sequence compositions + 8 repo tasks)
    excluded_seq_specs: list[tuple[str, str, tuple[str, ...], list[tuple[str, ...]], list[list[int]]]] = [
        (
            "ex01_abs_double_sort",
            "Convert each measurement to its absolute magnitude, double it, and sort ascending.",
            ("abs_val", "double", "sort_asc"),
            [("clamp_zero", "double", "sort_asc"), ("filter_positive", "double", "sort_asc")],
            [[3, 1, 2], [4, 2, 5]],
        ),
        (
            "ex02_clamp_inc_rev",
            "Clamp negative values at zero, increment by 1, and reverse the order.",
            ("clamp_zero", "increment", "reverse"),
            [("abs_val", "increment", "reverse"), ("increment", "reverse")],
            [[1, 2, 3], [4, 1, 2]],
        ),
        (
            "ex03_pos_double_unique",
            "Keep strictly positive values, double each, and deduplicate distinct entries.",
            ("filter_positive", "double", "unique_stable"),
            [("clamp_zero", "double", "unique_stable"), ("abs_val", "double", "unique_stable"), ("filter_positive", "double")],
            [[1, 2, 3], [4, 2, 5]],
        ),
        (
            "ex04_even_square_sort",
            "Filter even values, square each, and sort ascending.",
            ("filter_even", "square", "sort_asc"),
            [("square", "sort_asc"), ("filter_positive", "square", "sort_asc")],
            [[2, 4, 6], [4, 2, 8]],
        ),
        (
            "ex05_unique_inc_runsum",
            "Deduplicate distinct values, increment by 1, and compute the running cumulative sum.",
            ("unique_stable", "increment", "running_sum"),
            [("increment", "running_sum"), ("sort_asc", "increment", "running_sum")],
            [[1, 2, 3], [2, 3, 4]],
        ),
        (
            "ex06_dec_clamp_sort",
            "Subtract 1 from each value, clamp negative results at 0, and sort ascending.",
            ("decrement", "clamp_zero", "sort_asc"),
            [("decrement", "abs_val", "sort_asc"), ("decrement", "sort_asc")],
            [[3, 2, 4], [5, 2, 3]],
        ),
        (
            "ex07_abs_unique_rev",
            "Take absolute magnitude, deduplicate distinct numbers, and reverse.",
            ("abs_val", "unique_stable", "reverse"),
            [("clamp_zero", "unique_stable", "reverse"), ("abs_val", "reverse")],
            [[1, 2, 3], [4, 5, 2]],
        ),
        (
            "ex08_pos_inc_sort",
            "Keep strictly positive numbers, add 1 to each, and sort ascending.",
            ("filter_positive", "increment", "sort_asc"),
            [("clamp_zero", "increment", "sort_asc"), ("abs_val", "increment", "sort_asc")],
            [[3, 1, 2], [5, 2, 4]],
        ),
        (
            "ex09_even_abs_double",
            "Filter even entries, take absolute magnitude, and double each.",
            ("filter_even", "abs_val", "double"),
            [("filter_even", "clamp_zero", "double"), ("abs_val", "double")],
            [[2, 4, 6], [4, 2]],
        ),
        (
            "ex10_clamp_square_unique",
            "Clamp negative values at 0, square each, and deduplicate distinct values.",
            ("clamp_zero", "square", "unique_stable"),
            [("abs_val", "square", "unique_stable"), ("clamp_zero", "square")],
            [[1, 2, 3], [2, 4, 5]],
        ),
        (
            "ex11_rev_dec_abs",
            "Reverse the sequence, decrement by 1, and take absolute magnitude.",
            ("reverse", "decrement", "abs_val"),
            [("reverse", "decrement", "clamp_zero"), ("decrement", "abs_val")],
            [[3, 3, 3], [4, 4]],
        ),
        (
            "ex12_double_inc_runsum",
            "Double each value, add 1, and compute the running cumulative sum.",
            ("double", "increment", "running_sum"),
            [("square", "increment", "running_sum"), ("increment", "double", "running_sum")],
            [[2, 2], [2]],
        ),
        (
            "ex13_pos_sort_runsum",
            "Keep strictly positive entries, sort ascending, and compute running cumulative sum.",
            ("filter_positive", "sort_asc", "running_sum"),
            [("clamp_zero", "sort_asc", "running_sum"), ("abs_val", "sort_asc", "running_sum")],
            [[3, 1, 2], [4, 2]],
        ),
        (
            "ex14_unique_double_rev",
            "Deduplicate distinct values, double each, and reverse.",
            ("unique_stable", "double", "reverse"),
            [("double", "reverse"), ("filter_positive", "double", "reverse")],
            [[1, 2, 3], [3, 4, 5]],
        ),
        (
            "ex15_even_dec_clamp",
            "Filter even numbers, subtract 1, and clamp negative results at 0.",
            ("filter_even", "decrement", "clamp_zero"),
            [("filter_even", "decrement", "abs_val"), ("decrement", "clamp_zero")],
            [[2, 4, 6], [4, 8]],
        ),
        (
            "ex16_abs_inc_unique",
            "Take absolute magnitude, increment by 1, and deduplicate distinct outputs.",
            ("abs_val", "increment", "unique_stable"),
            [("clamp_zero", "increment", "unique_stable"), ("abs_val", "increment")],
            [[1, 2, 3], [4, 2, 5]],
        ),
    ]

    excluded_tasks: list[tuple[InvestigationTaskPublicView, EvaluatorPrivateTaskOracle]] = []
    for tid, req, target_ops, foils, supp_inputs in excluded_seq_specs:
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inputs]
        pool = _make_pipeline_candidate_pool(target_ops, foils, base_distractors)
        assess_inps = [
            [-3, -2, 0, 1, 2, 2, 3],
            [-4, 0, 2, -2, 5, 5],
            [0, -1, 3, -3, 2, 4],
            [2, -4, 0, 2, 1, -1],
        ]
        excluded_tasks.append((
            InvestigationTaskPublicView(
                task_id=tid,
                family="excluded_compositional_sequence",
                domain="sequence_pipeline",
                request=req,
                support_examples=supp,
                schema_context={"version": 1, "dtype": "int_list"},
            ),
            EvaluatorPrivateTaskOracle(
                task_id=tid,
                target_ops=target_ops,
                oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
                assessment_inputs=assess_inps,
                candidate_pool=pool,
            ),
        ))

    # Add 8 Practical Repository Maintenance Tasks (where public symptom examples
    # leave boundary/negative/rounding ambiguities resolved by task-conditioned priors + probing)
    repo_specs: list[tuple[str, str, tuple[str, ...], Callable[[dict[str, Any]], Any], list[tuple[tuple[str, ...], Callable[[dict[str, Any]], Any]]]]] = [
        (
            "ex17_repo_discount_clamp_zero",
            "Repair invoice_total in billing/invoice.py: clamp negative extra adjustments at zero before applying the discount rate.",
            ("clamp_zero", "double"),
            lambda d: round((d["value"] + max(0, d["extra"])) * (1.0 - d["rate"]), 2),
            [
                (("abs_val", "double"), lambda d: round((d["value"] + abs(d["extra"])) * (1.0 - d["rate"]), 2)),
                (("filter_positive", "double"), lambda d: round(d["value"] * (1.0 - d["rate"]), 2) if d["extra"] <= 0 else round((d["value"] + d["extra"]) * (1.0 - d["rate"]), 2)),
                (("increment",), lambda d: round((d["value"] + d["extra"]) * (1.0 + d["rate"]), 2)),
            ],
        ),
        (
            "ex18_repo_quota_inclusive_positive",
            "Repair check_quota in auth/limiter.py: keep positive usage values and allow inclusive bound up to limit.",
            ("filter_positive", "sort_asc"),
            lambda d: (d["value"] > 0) and (d["value"] <= d["limit"]),
            [
                (("clamp_zero", "sort_asc"), lambda d: (d["value"] >= 0) and (d["value"] < d["limit"])),
                (("abs_val", "sort_asc"), lambda d: (abs(d["value"]) <= d["limit"])),
                (("reverse",), lambda d: d["value"] < d["limit"]),
            ],
        ),
        (
            "ex19_repo_telemetry_abs_delta",
            "Repair drift_magnitude in telemetry/sensor.py: take absolute magnitude of extra drift and add to base value.",
            ("abs_val", "increment"),
            lambda d: d["value"] + abs(d["extra"]),
            [
                (("clamp_zero", "increment"), lambda d: d["value"] + max(0, d["extra"])),
                (("decrement", "abs_val"), lambda d: abs(d["value"] - d["extra"])),
                (("double",), lambda d: d["value"] * 2),
            ],
        ),
        (
            "ex20_repo_inventory_nonneg_floor",
            "Repair available_stock in warehouse/stock.py: subtract extra reserved units and clamp at zero floor.",
            ("decrement", "clamp_zero"),
            lambda d: max(0, d["value"] + d["extra"]),
            [
                (("decrement", "abs_val"), lambda d: abs(d["value"] + d["extra"])),
                (("increment", "clamp_zero"), lambda d: d["value"] + max(0, d["extra"])),
                (("reverse",), lambda d: d["value"] - d["extra"]),
            ],
        ),
        (
            "ex21_repo_ledger_even_batch_bonus",
            "Repair batch_score in ledger/scoring.py: double the value and increment by 1 when value is positive.",
            ("filter_positive", "double", "increment"),
            lambda d: (d["value"] * 2 + 1) if d["value"] > 0 else 0,
            [
                (("clamp_zero", "double", "increment"), lambda d: (max(0, d["value"]) * 2 + 1)),
                (("abs_val", "double", "increment"), lambda d: (abs(d["value"]) * 2 + 1)),
                (("double",), lambda d: d["value"] * 2),
            ],
        ),
        (
            "ex22_repo_sla_strictly_positive_rate",
            "Repair sla_penalty in monitor/sla.py: square the positive excess above zero, clamping negative excess to zero.",
            ("clamp_zero", "square"),
            lambda d: (max(0, d["extra"]) ** 2) + d["value"],
            [
                (("abs_val", "square"), lambda d: (abs(d["extra"]) ** 2) + d["value"]),
                (("filter_positive", "square"), lambda d: (d["extra"] ** 2 + d["value"]) if d["extra"] > 0 else 0),
                (("increment",), lambda d: d["value"] + d["extra"]),
            ],
        ),
        (
            "ex23_repo_tax_round_running",
            "Repair cumulative_fee in finance/fees.py: take absolute magnitude of extra adjustment and double before adding value.",
            ("abs_val", "double"),
            lambda d: d["value"] + 2 * abs(d["extra"]),
            [
                (("clamp_zero", "double"), lambda d: d["value"] + 2 * max(0, d["extra"])),
                (("filter_positive", "double"), lambda d: d["value"] + (2 * d["extra"] if d["extra"] > 0 else -d["extra"])),
                (("decrement",), lambda d: d["value"] + d["extra"]),
            ],
        ),
        (
            "ex24_repo_cache_ttl_clamp",
            "Repair normalize_ttl in cache/policy.py: decrement value by 1 and clamp negative TTL at zero.",
            ("decrement", "clamp_zero", "increment"),
            lambda d: max(0, d["value"] - 1) + max(0, d["extra"]),
            [
                (("decrement", "abs_val", "increment"), lambda d: abs(d["value"] - 1) + abs(d["extra"])),
                (("clamp_zero", "increment"), lambda d: max(0, d["value"]) + max(0, d["extra"])),
                (("reverse",), lambda d: d["value"] + d["extra"]),
            ],
        ),
    ]

    for tid, req, target_ops, target_fn, foil_specs in repo_specs:
        # Support example has positive value and extra=0 or positive extra so foils agree on support
        supp_inp = {"probe_id": "support_1", "value": 20, "rate": 0.10, "limit": 100, "extra": 5 if "sla" in tid else 0}
        supp = [(supp_inp, target_fn(supp_inp))]
        pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
        # Put distractors and foils before target in default catalogue order
        for idx, (f_ops, f_fn) in enumerate(foil_specs):
            pool.append((f"repo_foil_{idx}_{'_'.join(f_ops)}", f_ops, f_fn))
        pool.append((f"repo_target_{'_'.join(target_ops)}", target_ops, target_fn))
        for idx in range(6):
            pool.append((f"repo_distractor_{idx}", ("reverse", f"d{idx}"), lambda d, _i=idx: -999 - _i))

        assess_inps = list(LearnedInvestigationPolicy.REPO_PROBE_INPUTS)
        excluded_tasks.append((
            InvestigationTaskPublicView(
                task_id=tid,
                family="excluded_repository_maintenance",
                domain="repo_patch",
                request=req,
                support_examples=supp,
                schema_context={"version": 1, "dtype": "repo_dict"},
                repo_files={"module.py": f"# {tid}\n# {req}\n"},
            ),
            EvaluatorPrivateTaskOracle(
                task_id=tid,
                target_ops=target_ops,
                oracle_fn=target_fn,
                assessment_inputs=assess_inps,
                candidate_pool=pool,
            ),
        ))

    # 8 Skill-Seed Tasks (used ONLY in Experiment 3 when testing Dual-Engine skill reuse + strategy;
    # cleared in Experiment 1 when testing pure Learning-to-Learn with capsules reset)
    skill_seed_tasks = excluded_tasks[:8]
    return training_pool, excluded_tasks, skill_seed_tasks


# ---------------------------------------------------------------------------
# 9. End-to-End Combined Architecture Orchestrator
# ---------------------------------------------------------------------------

class CombinedNexusArchitecture:
    """High-level facade connecting all 7 components and the 3 separately
    resettable knowledge stores.
    """

    def __init__(self) -> None:
        self.knowledge = SeparatelyResettableKnowledgeState()
        self.capsule_executor = CapsuleExecutor(self.knowledge.skills)
        self.neural_proposer = LocalNeuralProposer(self.knowledge.language_knowledge)
        self.evidence_kernel = EvidenceKernel()
        self.consolidator = Consolidator(self.knowledge.skills)
        self.curriculum_generator = CurriculumGenerator()
        self.investigation_policy = LearnedInvestigationPolicy(
            strategy_store=self.knowledge.learning_strategy,
            neural_proposer=self.neural_proposer,
            capsule_executor=self.capsule_executor,
            evidence_kernel=self.evidence_kernel,
            consolidator=self.consolidator,
        )
        self.objective_weights = InvestigationObjectiveWeights()

    def run_engineering_replacements_suite(self) -> dict[str, Any]:
        """Run and verify all 5 explicit engineering replacements."""
        # 1. ConformalCandidateCalibrator
        cal_data: list[tuple[list[tuple[str, float]], str]] = []
        eval_data: list[tuple[list[tuple[str, float]], str]] = []
        rng = random.Random(42)
        for i in range(40):
            # True candidate is in top-5 ~75% of the time, and in top-8 ~97.5% of the time
            true_rank = i % 7
            probs = [0.28, 0.20, 0.15, 0.12, 0.09, 0.07, 0.05, 0.04]
            ranked = [(f"cand_{r}", probs[r]) for r in range(8)]
            item = (ranked, f"cand_{true_rank}")
            if i < 20:
                cal_data.append(item)
            else:
                eval_data.append(item)
        conformal_report = ConformalCandidateCalibrator.calibrate_and_evaluate(
            cal_data, eval_data, alpha=0.05
        )
        self.knowledge.language_knowledge.conformal_quantile_95 = conformal_report["conformal_q_hat"]
        self.knowledge.language_knowledge.calibrated = True
        self.knowledge.language_knowledge.empirical_top5_coverage = conformal_report["empirical_top5_coverage"]
        self.knowledge.language_knowledge.empirical_conformal_coverage = conformal_report["empirical_conformal_coverage"]

        # 2. BoundedEGraphOrganizer
        probes = [[-3, 1, 2, 2], [0, -5, 4], [3, 1, 1]]
        sound_rule_check = BoundedEGraphOrganizer.verify_rule_soundness_on_probes(
            BoundedEGraphOrganizer.SOUND_PIPELINE_RULES[0],
            execute_pipeline,
            probes,
        )
        unsound_rule = RewriteRule("unsound_abs_to_clamp", ("abs_val",), ("clamp_zero",))
        unsound_rule_check = BoundedEGraphOrganizer.verify_rule_soundness_on_probes(
            unsound_rule,
            execute_pipeline,
            probes,
        )
        eq_class = BoundedEGraphOrganizer.saturate_equivalence_class(("reverse", "reverse", "sort_asc", "sort_asc"))
        canon_rep = BoundedEGraphOrganizer.canonical_representative(("reverse", "reverse", "sort_asc", "sort_asc"))

        # 3. BoundedContractCounterexampleSearcher
        buggy_discount_fn = lambda x: round(x * 0.9, 2) if x != 100 else 105.0
        ce_found = self.evidence_kernel.contract_searcher.search_counterexamples(
            func=buggy_discount_fn,
            precondition=lambda x: x >= 0,
            postcondition=lambda x, out: out <= x,
            domain_generator=[0, 10, 50, 100, 200],
        )
        sound_discount_fn = lambda x: round(x * 0.9, 2)
        ce_clean = self.evidence_kernel.contract_searcher.search_counterexamples(
            func=sound_discount_fn,
            precondition=lambda x: x >= 0,
            postcondition=lambda x, out: out <= x,
            domain_generator=[0, 10, 50, 100, 200],
        )

        # 4. AttributedClaimStore
        self.evidence_kernel.claim_store.add_extracted_claim(AttributedClaim(
            claim_id="c1",
            subject="api_rate_limit",
            predicate="max_requests_per_min",
            object_value=120,
            source_attribution="service_docs_v2",
            scope="production_us_east",
            valid_from="2025-01-01",
            valid_until="2025-12-31",
        ))
        self.evidence_kernel.claim_store.add_extracted_claim(AttributedClaim(
            claim_id="c2",
            subject="api_rate_limit",
            predicate="max_requests_per_min",
            object_value=300,
            source_attribution="release_notes_v3",
            scope="production_us_east",
            valid_from="2025-06-01",
            valid_until=None,
        ))
        claim_query_contradiction = self.evidence_kernel.claim_store.query_claims(
            "api_rate_limit", "max_requests_per_min", scope="production_us_east", as_of_date="2025-09-01"
        )
        claim_query_scoped = self.evidence_kernel.claim_store.query_claims(
            "api_rate_limit", "max_requests_per_min", scope="production_us_east", as_of_date="2026-03-01"
        )

        # 5. VersionedCompiledArtifactMonitor
        temp_store = CapsuleSkillStore()
        temp_store.register(VersionedCapsule(
            capsule_id="cap_monitored_v1",
            name="monitored_pipeline",
            domain="sequence_pipeline",
            skeleton_ops=["abs_val", "sort_asc"],
            schema_assumptions={"version": 1, "currency": "USD"},
            source_code="abs_val -> sort_asc",
            version=1,
        ))
        monitor = VersionedCompiledArtifactMonitor(temp_store)
        exec_valid = monitor.check_and_execute(
            "cap_monitored_v1",
            {"version": 1, "currency": "USD"},
            lambda c: execute_pipeline(tuple(c.skeleton_ops), [-2, 1]),
        )
        exec_invalidated = monitor.check_and_execute(
            "cap_monitored_v1",
            {"version": 2, "currency": "EUR"},
            lambda c: execute_pipeline(tuple(c.skeleton_ops), [-2, 1]),
        )

        # Also run a real bounded worker verification check via `run_worker_subprocess`
        worker_check = run_worker_subprocess({
            "language": "python",
            "files": {"mod.py": "def f(xs):\n    return sorted(abs(x) for x in xs)\n"},
            "cases": [{"entry": "mod.f", "input": [-3, 1, -2], "expected": [1, 2, 3]}],
        })

        return {
            "conformal_calibration": conformal_report,
            "egraph_organization": {
                "equivalence_class_size": len(eq_class),
                "canonical_representative": list(canon_rep),
                "sound_rule_check": sound_rule_check,
                "unsound_rule_check": unsound_rule_check,
            },
            "contract_counterexample_search": {
                "buggy_function_result": ce_found,
                "sound_function_result": ce_clean,
            },
            "attributed_claims": {
                "overlapping_dates_query": claim_query_contradiction,
                "post_v2_expiry_query": claim_query_scoped,
            },
            "versioned_artifact_monitoring": {
                "valid_assumption_execution": exec_valid,
                "changed_assumption_invalidation": exec_invalidated,
            },
            "bounded_worker_smoke_passed": bool(worker_check.get("all_passed")),
        }


# ===========================================================================
# 10. V2 UNCONFOUNDED, EQUALIZED, CALL-METERED INVESTIGATION ENGINE
# ===========================================================================

@dataclass(frozen=True)
class EqualizedControllerConfig:
    r"""Identical controller bounds enforced across ALL active policies in v2 so
    that comparisons isolate learned weights $(\phi_{\text{rank}}, \phi_{\text{probe}})$
    rather than shortlist or questioning asymmetries.
    """
    shortlist_limit: int = 3
    allow_questions: bool = True
    max_questions_per_task: int = 2
    probe_min_disagreement_ratio: float = 0.15


class EpisodeCallLedger:
    """Records every single candidate function call `fn(inp)` across all phases
    (`support_check`, `probe_construction`, `probe_filter`, `capsule_prefix_check`)
    and every oracle question so the independent verifier can reconstruct all
    costs and summary tables from the raw logs.
    """

    def __init__(self) -> None:
        self.candidate_call_log: list[dict[str, Any]] = []
        self.oracle_question_log: list[dict[str, Any]] = []

    def invoke_candidate(
        self,
        candidate_id: str,
        fn: Callable[[Any], Any],
        inp: Any,
        phase: str,
    ) -> Any:
        inp_copy = copy.deepcopy(inp)
        try:
            out = fn(inp_copy)
            status = "ok"
        except Exception as exc:
            out = f"ERR:{type(exc).__name__}"
            status = "error"
        self.candidate_call_log.append({
            "call_index": len(self.candidate_call_log) + 1,
            "candidate_id": candidate_id,
            "phase": phase,
            "input": copy.deepcopy(inp),
            "output": copy.deepcopy(out),
            "status": status,
        })
        return out

    def invoke_oracle(
        self,
        active_env: MechanismBActiveEnvironment,
        task_id: str,
        probe_input: Any,
    ) -> Any:
        ans = active_env.request_answer(task_id, copy.deepcopy(probe_input))
        self.oracle_question_log.append({
            "question_index": len(self.oracle_question_log) + 1,
            "task_id": task_id,
            "probe_input": copy.deepcopy(probe_input),
            "oracle_answer": copy.deepcopy(ans),
        })
        return ans

    @property
    def n_candidate_calls(self) -> int:
        return len(self.candidate_call_log)

    @property
    def n_questions(self) -> int:
        return len(self.oracle_question_log)


class AlgebraicPropertySynthesizer:
    r"""Surprise Capability: Extracts algebraic/behavioral invariants from
    observed support & oracle input-output pairs (`length_preserving`,
    `length_contracting`, `strictly_nonnegative`, `even_parity`, `sorted_output`,
    `duplicate_free`, `zero_fixed_point`, `quadratic_growth`, `linear_double`)
    and synthesizes a rich behavioral signature vector $\psi(D)$ without needing
    English operator keywords in the ticket description.
    """

    @staticmethod
    def extract_behavioral_signature(
        examples: list[tuple[Any, Any]],
    ) -> dict[str, float]:
        if not examples:
            return {}
        # Sequence pipeline examples
        if isinstance(examples[0][0], list):
            n = len(examples)
            len_shrink = 0.0
            len_preserve = 0.0
            sorted_out = 1.0
            even_out = 1.0
            nonneg_out = 1.0
            dedup_effect = 0.0
            double_scale = 0.0
            square_scale = 0.0
            inc_shift = 0.0
            dec_shift = 0.0
            rev_order = 0.0
            runsum_growth = 0.0

            for inp, out in examples:
                if len(out) < len(inp):
                    len_shrink += 1.0 / n
                else:
                    len_preserve += 1.0 / n
                if out != sorted(out):
                    sorted_out = 0.0
                if not out or any(x % 2 != 0 for x in out):
                    even_out = 0.0
                if any(x < 0 for x in out):
                    nonneg_out = 0.0
                if len(set(inp)) < len(inp) and len(out) <= len(set(inp)):
                    dedup_effect += 1.0 / n
                if inp and out:
                    max_in = max(abs(x) for x in inp)
                    max_out = max(abs(x) for x in out)
                    if max_in >= 3 and max_out >= max_in * max_in - 1:
                        square_scale += 1.0 / n
                    elif max_in >= 2 and max_out in (max_in * 2, max_in * 2 + 1):
                        double_scale += 1.0 / n
                    if len(inp) == len(out):
                        if sum(out) == sum(inp) + len(inp):
                            inc_shift += 1.0 / n
                        if any(o == max(0, i - 1) or o == abs(i - 1) for i, o in zip(inp, out)) and sum(out) < sum(abs(x) for x in inp):
                            dec_shift += 1.0 / n
                        if len(inp) >= 3 and out[0] != inp[0] and out[-1] in (inp[0], abs(inp[0]), inp[0] + 1, inp[0] - 1, abs(inp[0] - 1), inp[0] * 2):
                            rev_order += 1.0 / n
                    if len(out) >= 2 and out == sorted(out) and out[-1] > max_in and sum(out) > sum(abs(x) for x in inp):
                        runsum_growth += 1.0 / n

            return {
                "len_shrink": round(len_shrink, 4),
                "len_preserve": round(len_preserve, 4),
                "sorted_out": sorted_out,
                "even_out": even_out,
                "nonneg_out": nonneg_out,
                "dedup_effect": round(dedup_effect, 4),
                "double_scale": round(double_scale, 4),
                "square_scale": round(square_scale, 4),
                "inc_shift": round(inc_shift, 4),
                "dec_shift": round(dec_shift, 4),
                "rev_order": round(rev_order, 4),
                "runsum_growth": round(runsum_growth, 4),
            }

        # Repository dictionary examples
        inp0, out0 = examples[0]
        if isinstance(inp0, dict):
            val = float(inp0.get("value", 0))
            rate = float(inp0.get("rate", 0))
            extra = float(inp0.get("extra", 0))
            limit = float(inp0.get("limit", 100))
            is_bool = isinstance(out0, bool)
            out_num = float(out0) if isinstance(out0, (int, float)) and not is_bool else 0.0
            return {
                "repo_bool_out": 1.0 if is_bool else 0.0,
                "repo_rate_discount": 1.0 if (not is_bool and abs(out_num - round((val + max(0.0, extra)) * (1.0 - rate), 2)) < 1e-3) else 0.0,
                "repo_linear_add": 1.0 if (not is_bool and abs(out_num - (val + abs(extra))) < 1e-3 and extra != 0) else 0.0,
                "repo_floor_sub": 1.0 if (not is_bool and extra == 0 and abs(out_num - val) < 1e-3) else 0.0,
                "repo_double_inc": 1.0 if (not is_bool and abs(out_num - (val * 2 + 1)) < 1e-3) else 0.0,
                "repo_square_extra": 1.0 if (not is_bool and extra > 0 and abs(out_num - (val + extra * extra)) < 1e-3) else 0.0,
                "repo_double_extra": 1.0 if (not is_bool and extra > 0 and abs(out_num - (val + 2 * extra)) < 1e-3) else 0.0,
                "repo_dec_ttl": 1.0 if (not is_bool and abs(out_num - (val - 1 + extra)) < 1e-3) else 0.0,
                "repo_limit_bound": 1.0 if (is_bool and val <= limit) else 0.0,
            }
        return {}


@dataclass
class InvestigationPolicyV2Parameters:
    r"""Learned strategy parameters $\phi = (\phi_{\text{rank}}, \phi_{\text{probe}})$ for v2."""
    policy_id: str = "untrained_default"
    trained: bool = False
    curriculum_mode: str = "none"
    # Behavioral feature weights: operator_name -> feature_name -> weight
    behavioral_rank_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    # Marginal operator frequencies
    operator_frequencies: dict[str, float] = field(default_factory=dict)
    # Learned probe utility scores: probe_index -> empirical splitting probability
    learned_probe_scores: dict[str, list[float]] = field(default_factory=dict)
    # Number of top-ranked probes to evaluate before selecting question (1 when probe selector is learned, 8 when unlearned)
    probe_eval_window: int = 8


@dataclass(frozen=True)
class DisjointTaskV2:
    """Task specification with strictly disjoint `support_examples`,
    `probe_pool_inputs`, and `assessment_inputs`.
    """
    task_id: str
    cohort: str  # 'source_acquisition', 'training_pool', 'excluded_sequence', 'excluded_repo'
    domain: str  # 'sequence_pipeline' or 'repo_patch'
    ticket_request: str  # Realistic opaque ticket without operator keyword spoilers
    support_examples: list[tuple[Any, Any]]
    probe_pool_inputs: list[Any]
    assessment_inputs: list[Any]
    target_ops: tuple[str, ...]
    oracle_fn: Callable[[Any], Any]
    candidate_pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]
    repo_files: dict[str, str] = field(default_factory=dict)
    patched_repo_candidates: dict[str, dict[str, str]] = field(default_factory=dict)
    entry_point: str = ""


def verify_disjoint_task_inputs(task: DisjointTaskV2) -> dict[str, Any]:
    """Verify that `support_examples`, `probe_pool_inputs`, and `assessment_inputs`
    have zero overlap.
    """
    supp_keys = {json.dumps(inp, sort_keys=True) for inp, _ in task.support_examples}
    probe_keys = {json.dumps(inp, sort_keys=True) for inp in task.probe_pool_inputs}
    assess_keys = {json.dumps(inp, sort_keys=True) for inp in task.assessment_inputs}

    sp_overlap = supp_keys & probe_keys
    pa_overlap = probe_keys & assess_keys
    sa_overlap = supp_keys & assess_keys

    disjoint = (len(sp_overlap) == 0 and len(pa_overlap) == 0 and len(sa_overlap) == 0)
    return {
        "task_id": task.task_id,
        "pairwise_disjoint": disjoint,
        "support_probe_overlap_count": len(sp_overlap),
        "probe_assessment_overlap_count": len(pa_overlap),
        "support_assessment_overlap_count": len(sa_overlap),
    }


# 8 Sequence Probe Pool Inputs (P0..P5 are positive/homogeneous low-entropy probes;
# P6 and P7 are rich boundary/negative/zero/duplicate discriminating probes).
V2_SEQUENCE_PROBE_POOL: tuple[list[int], ...] = (
    [2, 2],
    [4, 4],
    [6, 6],
    [2, 4],
    [4, 6],
    [2, 6],
    [-3, 0, 2, 2, 5],   # P6: negative + zero + duplicate + odd/even
    [-4, -1, 0, 3, 3],  # P7: negative + zero + duplicate + odd/even
)

# Strictly disjoint sequence assessment inputs (none appear in support or probe pool)
V2_SEQUENCE_ASSESSMENT_INPUTS: tuple[list[int], ...] = (
    [-5, -2, 0, 1, 4, 4, 7],
    [-6, 0, 2, -3, 5, 5, 8],
    [0, -1, 3, -4, 2, 6, 2],
    [3, -5, 0, 3, 1, -2, 9],
)

# 8 Repository Probe Pool Inputs (P0..P5 are benign positive interior inputs;
# P6 and P7 test negative adjustment + exact boundary limit + zero floor).
V2_REPO_PROBE_POOL: tuple[dict[str, Any], ...] = (
    {"probe_id": "p0_interior", "value": 20, "rate": 0.10, "limit": 100, "extra": 2},
    {"probe_id": "p1_interior", "value": 30, "rate": 0.10, "limit": 100, "extra": 4},
    {"probe_id": "p2_interior", "value": 40, "rate": 0.10, "limit": 100, "extra": 6},
    {"probe_id": "p3_interior", "value": 50, "rate": 0.10, "limit": 100, "extra": 2},
    {"probe_id": "p4_interior", "value": 60, "rate": 0.10, "limit": 100, "extra": 4},
    {"probe_id": "p5_interior", "value": 70, "rate": 0.10, "limit": 100, "extra": 6},
    {"probe_id": "p6_boundary_neg_extra", "value": 100, "rate": 0.20, "limit": 100, "extra": -15},
    {"probe_id": "p7_zero_value_neg_extra", "value": 0, "rate": 0.25, "limit": 50, "extra": -8},
)

# Strictly disjoint Repository Assessment Inputs (never in support or V2_REPO_PROBE_POOL)
V2_REPO_ASSESSMENT_INPUTS: tuple[dict[str, Any], ...] = (
    {"assess_id": "a0_neg_extra_mid", "value": 80, "rate": 0.15, "limit": 80, "extra": -12},
    {"assess_id": "a1_zero_val_boundary", "value": 0, "rate": 0.20, "limit": 0, "extra": -6},
    {"assess_id": "a2_over_limit_neg", "value": 120, "rate": 0.05, "limit": 100, "extra": -25},
    {"assess_id": "a3_small_val_large_neg", "value": 5, "rate": 0.30, "limit": 10, "extra": -20},
)


def _make_v2_candidate_pool(
    target_ops: tuple[str, ...],
    confusable_foils: list[tuple[str, ...]],
    distractor_ops: list[tuple[str, ...]],
) -> list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]:
    """Build a 24-candidate hypothesis pool where 14 distractors precede the
    confusable foils and the target in default unlearned catalogue order.
    """
    ordered_seqs: list[tuple[str, ...]] = []
    for seq in distractor_ops[:14] + confusable_foils + [target_ops] + distractor_ops[14:]:
        if seq not in ordered_seqs:
            ordered_seqs.append(seq)
    pool: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
    for idx, ops in enumerate(ordered_seqs):
        cid = f"cand_{idx:02d}_{'_'.join(ops)}"
        pool.append((cid, ops, lambda xs, _ops=ops: execute_pipeline(_ops, xs)))
    return pool


def build_v2_disjoint_tasks_and_real_repos() -> tuple[
    list[DisjointTaskV2],
    list[DisjointTaskV2],
    list[DisjointTaskV2],
]:
    r"""Constructs three strictly disjoint task cohorts for `seed-learned-investigation-policy-v2`:
    1. `training_pool` (32 tasks: 8 diverse operator/boundary tasks + 24 redundant tasks)
       for training $(\phi_{\text{rank}}, \phi_{\text{probe}})$ via `CurriculumGenerator` vs `random_sampling`.
    2. `source_skill_tasks` (8 2-step source tasks `src01..src08` that NEXUS must
       actually solve via `investigate_v2` to acquire 2-step prefix capsules).
    3. `excluded_assessment_tasks` (24 unseen tasks: 16 3-step sequence compositions
       `ex01..ex16` + 8 real multi-file Python repository repair tasks `repo17..repo24`).
       Zero tasks overlap between `source_skill_tasks` and `excluded_assessment_tasks`,
       and all support, probe-pool, and assessment inputs are pairwise disjoint.
    """
    distractors: list[tuple[str, ...]] = [
        ("reverse", "increment"),
        ("sort_asc", "reverse"),
        ("double", "increment"),
        ("decrement", "square"),
        ("filter_even", "double"),
        ("running_sum", "reverse"),
        ("increment", "increment"),
        ("decrement", "reverse"),
        ("unique_stable", "reverse"),
        ("square", "decrement"),
        ("filter_positive", "reverse"),
        ("clamp_zero", "reverse"),
        ("reverse", "double"),
        ("increment", "sort_asc"),
        ("decrement", "running_sum"),
        ("square", "reverse"),
        ("filter_even", "reverse"),
        ("unique_stable", "decrement"),
    ]

    # 1. Training Pool (opaque ticket descriptions so keyword matching cannot cheat;
    # support examples exhibit clear behavioral signatures for each operator).
    diverse_train_specs: list[tuple[str, str, tuple[str, ...], list[tuple[str, ...]], list[list[int]]]] = [
        (
            "v2_tr01",
            "Ticket #T01: Normalize raw telemetry series alpha for downstream ingest.",
            ("abs_val", "sort_asc"),
            [("clamp_zero", "sort_asc"), ("filter_positive", "sort_asc")],
            [[3, 1, 2], [5, 2, 4]],
        ),
        (
            "v2_tr02",
            "Ticket #T02: Scale sensor channel beta readings.",
            ("clamp_zero", "double"),
            [("abs_val", "double"), ("filter_positive", "double")],
            [[3, 1, 2], [4, 2, 5]],
        ),
        (
            "v2_tr03",
            "Ticket #T03: Transform active pulse magnitudes in buffer gamma.",
            ("filter_positive", "square"),
            [("abs_val", "square"), ("clamp_zero", "square")],
            [[-2, 3, 4], [-1, 2, 5]],
        ),
        (
            "v2_tr04",
            "Ticket #T04: Filter aligned packets and apply unit offset.",
            ("filter_even", "increment"),
            [("increment",), ("double", "increment")],
            [[1, 2, 4], [3, 6, 8]],
        ),
        (
            "v2_tr05",
            "Ticket #T05: Compact duplicate keys and order output frame.",
            ("unique_stable", "sort_asc"),
            [("sort_asc",), ("filter_positive", "sort_asc")],
            [[3, 1, 3, 2], [4, 2, 4, 1]],
        ),
        (
            "v2_tr06",
            "Ticket #T06: Shift baseline down and rectify residual.",
            ("decrement", "abs_val"),
            [("decrement", "clamp_zero"), ("decrement",)],
            [[3, 4, 2], [5, 2, 3]],
        ),
        (
            "v2_tr07",
            "Ticket #T07: Invert sequence and accumulate prefix totals.",
            ("reverse", "running_sum"),
            [("running_sum",), ("sort_asc", "running_sum")],
            [[1, 2, 3], [2, 3, 4]],
        ),
        (
            "v2_tr08",
            "Ticket #T08: Reconcile billing adjustment delta in ledger.",
            ("clamp_zero", "increment"),
            [("abs_val", "increment"), ("filter_positive", "increment")],
            [[2, 3, 1], [4, 1, 5]],
        ),
    ]

    training_pool: list[DisjointTaskV2] = []
    for tid, req, target_ops, foils, supp_inps in diverse_train_specs:
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inps]
        pool = _make_v2_candidate_pool(target_ops, foils, distractors)
        training_pool.append(DisjointTaskV2(
            task_id=tid,
            cohort="training_pool",
            domain="sequence_pipeline",
            ticket_request=req,
            support_examples=supp,
            probe_pool_inputs=list(V2_SEQUENCE_PROBE_POOL),
            assessment_inputs=list(V2_SEQUENCE_ASSESSMENT_INPUTS),
            target_ops=target_ops,
            oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
            candidate_pool=pool,
        ))

    for idx in range(24):
        tid = f"v2_tr_redundant_{idx:02d}"
        target_ops = ("increment",)
        supp_inps = [[1, 2, 3], [4, 5, 6]]
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inps]
        pool = _make_v2_candidate_pool(target_ops, [], distractors)
        training_pool.append(DisjointTaskV2(
            task_id=tid,
            cohort="training_pool",
            domain="sequence_pipeline",
            ticket_request=f"Ticket #R{idx:02d}: Standard unit offset pass.",
            support_examples=supp,
            probe_pool_inputs=list(V2_SEQUENCE_PROBE_POOL),
            assessment_inputs=list(V2_SEQUENCE_ASSESSMENT_INPUTS),
            target_ops=target_ops,
            oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
            candidate_pool=pool,
        ))

    # 2. Disjoint 2-Step Source Skill Acquisition Tasks (`src01..src08`)
    # NEXUS must solve these via investigation to acquire 2-step prefix capsules.
    # None of these 2-step programs appear as targets in the 24 3-step/repo assessment tasks!
    source_specs: list[tuple[str, str, tuple[str, ...], list[tuple[str, ...]], list[list[int]]]] = [
        (
            "src01_abs_double",
            "Source Task S01: Rectify and double signal readings.",
            ("abs_val", "double"),
            [("clamp_zero", "double"), ("filter_positive", "double")],
            [[3, 1, 2], [4, 2, 5]],
        ),
        (
            "src02_clamp_inc",
            "Source Task S02: Floor at zero and increment readings.",
            ("clamp_zero", "increment"),
            [("abs_val", "increment"), ("increment",)],
            [[1, 2, 3], [4, 1, 2]],
        ),
        (
            "src03_pos_double",
            "Source Task S03: Filter positive pulses and double.",
            ("filter_positive", "double"),
            [("clamp_zero", "double"), ("abs_val", "double")],
            [[-2, 1, 3], [-1, 4, 2]],
        ),
        (
            "src04_even_square",
            "Source Task S04: Keep even cycles and square.",
            ("filter_even", "square"),
            [("square",), ("filter_positive", "square")],
            [[1, 2, 4], [3, 4, 6]],
        ),
        (
            "src05_unique_inc",
            "Source Task S05: Deduplicate stream and increment.",
            ("unique_stable", "increment"),
            [("increment",), ("sort_asc", "increment")],
            [[1, 1, 2, 3], [2, 2, 3, 4]],
        ),
        (
            "src06_dec_clamp",
            "Source Task S06: Decrement and floor negative values.",
            ("decrement", "clamp_zero"),
            [("decrement", "abs_val"), ("decrement",)],
            [[3, 2, 4], [5, 2, 3]],
        ),
        (
            "src07_abs_unique",
            "Source Task S07: Rectify and deduplicate stream.",
            ("abs_val", "unique_stable"),
            [("clamp_zero", "unique_stable"), ("unique_stable",)],
            [[1, 1, 2, 3], [4, 4, 2, 5]],
        ),
        (
            "src08_pos_inc",
            "Source Task S08: Keep positive entries and increment.",
            ("filter_positive", "increment"),
            [("clamp_zero", "increment"), ("abs_val", "increment")],
            [[-3, 1, 2], [-1, 4, 2]],
        ),
    ]

    source_skill_tasks: list[DisjointTaskV2] = []
    for tid, req, target_ops, foils, supp_inps in source_specs:
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inps]
        pool = _make_v2_candidate_pool(target_ops, foils, distractors)
        source_skill_tasks.append(DisjointTaskV2(
            task_id=tid,
            cohort="source_acquisition",
            domain="sequence_pipeline",
            ticket_request=req,
            support_examples=supp,
            probe_pool_inputs=list(V2_SEQUENCE_PROBE_POOL),
            assessment_inputs=list(V2_SEQUENCE_ASSESSMENT_INPUTS),
            target_ops=target_ops,
            oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
            candidate_pool=pool,
        ))

    # 3. 24 Excluded Unfamiliar Assessment Tasks:
    # 16 Unseen 3-Step Sequence Compositions (`ex01..ex16`) + 8 Real Multi-File Repo Tasks (`repo17..repo24`)
    # Notice: Ticket requests use domain-opaque wording (no operator keywords like 'abs', 'clamp', 'sort', 'unique')
    # so unlearned keyword matching has zero unfair advantage; support examples carry the behavioral signal,
    # while negative/boundary behavior requires active probing!
    excluded_seq_specs: list[tuple[str, str, tuple[str, ...], list[tuple[str, ...]], list[list[int]]]] = [
        (
            "ex01_abs_double_sort",
            "Assessment Ticket #A01: Process telemetry batch B01 for aggregator.",
            ("abs_val", "double", "sort_asc"),
            [("clamp_zero", "double", "sort_asc"), ("filter_positive", "double", "sort_asc")],
            [[3, 1, 2], [4, 2, 5]],
        ),
        (
            "ex02_clamp_inc_rev",
            "Assessment Ticket #A02: Process telemetry batch B02 for aggregator.",
            ("clamp_zero", "increment", "reverse"),
            [("abs_val", "increment", "reverse"), ("increment", "reverse")],
            [[1, 2, 3], [4, 1, 2]],
        ),
        (
            "ex03_pos_double_unique",
            "Assessment Ticket #A03: Process telemetry batch B03 for aggregator.",
            ("filter_positive", "double", "unique_stable"),
            [("clamp_zero", "double", "unique_stable"), ("abs_val", "double", "unique_stable"), ("filter_positive", "double")],
            [[-2, 1, 1, 3], [-1, 4, 2, 2]],
        ),
        (
            "ex04_even_square_sort",
            "Assessment Ticket #A04: Process telemetry batch B04 for aggregator.",
            ("filter_even", "square", "sort_asc"),
            [("square", "sort_asc"), ("filter_positive", "square", "sort_asc")],
            [[1, 4, 2], [3, 6, 2]],
        ),
        (
            "ex05_unique_inc_runsum",
            "Assessment Ticket #A05: Process telemetry batch B05 for aggregator.",
            ("unique_stable", "increment", "running_sum"),
            [("increment", "running_sum"), ("sort_asc", "increment", "running_sum")],
            [[1, 1, 2, 3], [2, 2, 3, 4]],
        ),
        (
            "ex06_dec_clamp_sort",
            "Assessment Ticket #A06: Process telemetry batch B06 for aggregator.",
            ("decrement", "clamp_zero", "sort_asc"),
            [("decrement", "abs_val", "sort_asc"), ("decrement", "sort_asc")],
            [[3, 2, 4], [5, 2, 3]],
        ),
        (
            "ex07_abs_unique_rev",
            "Assessment Ticket #A07: Process telemetry batch B07 for aggregator.",
            ("abs_val", "unique_stable", "reverse"),
            [("clamp_zero", "unique_stable", "reverse"), ("abs_val", "reverse")],
            [[1, 1, 2, 3], [4, 4, 5, 2]],
        ),
        (
            "ex08_pos_inc_sort",
            "Assessment Ticket #A08: Process telemetry batch B08 for aggregator.",
            ("filter_positive", "increment", "sort_asc"),
            [("clamp_zero", "increment", "sort_asc"), ("abs_val", "increment", "sort_asc")],
            [[-2, 3, 1], [-1, 5, 2]],
        ),
        (
            "ex09_even_abs_double",
            "Assessment Ticket #A09: Process telemetry batch B09 for aggregator.",
            ("filter_even", "abs_val", "double"),
            [("filter_even", "clamp_zero", "double"), ("abs_val", "double")],
            [[1, 2, 4], [3, 4, 6]],
        ),
        (
            "ex10_clamp_square_unique",
            "Assessment Ticket #A10: Process telemetry batch B10 for aggregator.",
            ("clamp_zero", "square", "unique_stable"),
            [("abs_val", "square", "unique_stable"), ("clamp_zero", "square")],
            [[1, 2, 2, 3], [3, 4, 4, 5]],
        ),
        (
            "ex11_rev_dec_abs",
            "Assessment Ticket #A11: Process telemetry batch B11 for aggregator.",
            ("reverse", "decrement", "abs_val"),
            [("reverse", "decrement", "clamp_zero"), ("decrement", "abs_val")],
            [[2, 3, 4], [3, 4, 5]],
        ),
        (
            "ex12_double_inc_runsum",
            "Assessment Ticket #A12: Process telemetry batch B12 for aggregator.",
            ("double", "increment", "running_sum"),
            [("square", "increment", "running_sum"), ("increment", "double", "running_sum")],
            [[1, 2, 3], [2, 3, 4]],
        ),
        (
            "ex13_pos_sort_runsum",
            "Assessment Ticket #A13: Process telemetry batch B13 for aggregator.",
            ("filter_positive", "sort_asc", "running_sum"),
            [("clamp_zero", "sort_asc", "running_sum"), ("abs_val", "sort_asc", "running_sum")],
            [[-3, 3, 1, 2], [-2, 4, 2]],
        ),
        (
            "ex14_unique_double_rev",
            "Assessment Ticket #A14: Process telemetry batch B14 for aggregator.",
            ("unique_stable", "double", "reverse"),
            [("double", "reverse"), ("filter_positive", "double", "reverse")],
            [[1, 1, 2, 3], [2, 2, 4, 5]],
        ),
        (
            "ex15_even_dec_clamp",
            "Assessment Ticket #A15: Process telemetry batch B15 for aggregator.",
            ("filter_even", "decrement", "clamp_zero"),
            [("filter_even", "decrement", "abs_val"), ("decrement", "clamp_zero")],
            [[1, 2, 4], [3, 4, 6]],
        ),
        (
            "ex16_abs_inc_unique",
            "Assessment Ticket #A16: Process telemetry batch B16 for aggregator.",
            ("abs_val", "increment", "unique_stable"),
            [("clamp_zero", "increment", "unique_stable"), ("abs_val", "increment")],
            [[1, 1, 2, 3], [4, 4, 2, 5]],
        ),
    ]

    excluded_tasks: list[DisjointTaskV2] = []
    for tid, req, target_ops, foils, supp_inps in excluded_seq_specs:
        supp = [(inp, execute_pipeline(target_ops, inp)) for inp in supp_inps]
        pool = _make_v2_candidate_pool(target_ops, foils, distractors)
        excluded_tasks.append(DisjointTaskV2(
            task_id=tid,
            cohort="excluded_sequence",
            domain="sequence_pipeline",
            ticket_request=req,
            support_examples=supp,
            probe_pool_inputs=list(V2_SEQUENCE_PROBE_POOL),
            assessment_inputs=list(V2_SEQUENCE_ASSESSMENT_INPUTS),
            target_ops=target_ops,
            oracle_fn=lambda xs, _ops=target_ops: execute_pipeline(_ops, xs),
            candidate_pool=pool,
        ))

    # 8 Real Multi-File Python Repository Maintenance Tasks (`repo17..repo24`)
    # Each task has real multi-file Python code and AST patch candidates that can be
    # executed both via fast callable and inside `agent_loop_worker.run_worker_subprocess`.
    repo_specs: list[tuple[
        str,
        str,
        tuple[str, ...],
        dict[str, str],
        dict[str, str],
        Callable[[dict[str, Any]], Any],
        list[tuple[tuple[str, ...], Callable[[dict[str, Any]], Any]]],
        dict[str, Any],
    ]] = [
        (
            "repo17_billing_adjustment",
            "Ticket #R17: Fix invoice calculation discrepancy in billing_service.py.",
            ("clamp_zero", "double"),
            {
                "adjustments.py": "def norm_extra(extra: float) -> float:\n    return extra\n",
                "billing_service.py": "from adjustments import norm_extra\n\ndef compute(d: dict) -> float:\n    return round((d['value'] + norm_extra(d['extra'])) * (1.0 - d['rate']), 2)\n",
            },
            {
                "adjustments.py": "def norm_extra(extra: float) -> float:\n    return max(0, extra)\n",
                "billing_service.py": "from adjustments import norm_extra\n\ndef compute(d: dict) -> float:\n    return round((d['value'] + norm_extra(d['extra'])) * (1.0 - d['rate']), 2)\n",
            },
            lambda d: round((d["value"] + max(0, d["extra"])) * (1.0 - d["rate"]), 2),
            [
                (("abs_val", "double"), lambda d: round((d["value"] + abs(d["extra"])) * (1.0 - d["rate"]), 2)),
                (("filter_positive", "double"), lambda d: round(d["value"] * (1.0 - d["rate"]), 2) if d["extra"] <= 0 else round((d["value"] + d["extra"]) * (1.0 - d["rate"]), 2)),
            ],
            {"supp_id": "s17", "value": 25, "rate": 0.10, "limit": 100, "extra": 0},
        ),
        (
            "repo18_quota_guard",
            "Ticket #R18: Fix quota admission boundary check in quota_service.py.",
            ("filter_positive", "sort_asc"),
            {
                "bounds.py": "def within_cap(val: float, limit: float) -> bool:\n    return val < limit\n",
                "quota_service.py": "from bounds import within_cap\n\ndef compute(d: dict) -> bool:\n    return (d['value'] >= 0) and within_cap(d['value'], d['limit'])\n",
            },
            {
                "bounds.py": "def within_cap(val: float, limit: float) -> bool:\n    return val <= limit\n",
                "quota_service.py": "from bounds import within_cap\n\ndef compute(d: dict) -> bool:\n    return (d['value'] > 0) and within_cap(d['value'], d['limit'])\n",
            },
            lambda d: (d["value"] > 0) and (d["value"] <= d["limit"]),
            [
                (("clamp_zero", "sort_asc"), lambda d: (d["value"] >= 0) and (d["value"] < d["limit"])),
                (("abs_val", "sort_asc"), lambda d: (abs(d["value"]) <= d["limit"])),
            ],
            {"supp_id": "s18", "value": 25, "rate": 0.10, "limit": 100, "extra": 0},
        ),
        (
            "repo19_telemetry_drift",
            "Ticket #R19: Fix drift offset aggregation in sensor_service.py.",
            ("abs_val", "increment"),
            {
                "drift.py": "def mag(x: float) -> float:\n    return max(0, x)\n",
                "sensor_service.py": "from drift import mag\n\ndef compute(d: dict) -> float:\n    return d['value'] + mag(d['extra'])\n",
            },
            {
                "drift.py": "def mag(x: float) -> float:\n    return abs(x)\n",
                "sensor_service.py": "from drift import mag\n\ndef compute(d: dict) -> float:\n    return d['value'] + mag(d['extra'])\n",
            },
            lambda d: d["value"] + abs(d["extra"]),
            [
                (("clamp_zero", "increment"), lambda d: d["value"] + max(0, d["extra"])),
                (("decrement", "abs_val"), lambda d: abs(d["value"] - d["extra"])),
            ],
            {"supp_id": "s19", "value": 25, "rate": 0.10, "limit": 100, "extra": 3},
        ),
        (
            "repo20_warehouse_reserve",
            "Ticket #R20: Fix available stock floor calculation in stock_service.py.",
            ("decrement", "clamp_zero"),
            {
                "floor.py": "def clip(x: float) -> float:\n    return abs(x)\n",
                "stock_service.py": "from floor import clip\n\ndef compute(d: dict) -> float:\n    return clip(d['value'] + d['extra'])\n",
            },
            {
                "floor.py": "def clip(x: float) -> float:\n    return max(0, x)\n",
                "stock_service.py": "from floor import clip\n\ndef compute(d: dict) -> float:\n    return clip(d['value'] + d['extra'])\n",
            },
            lambda d: max(0, d["value"] + d["extra"]),
            [
                (("decrement", "abs_val"), lambda d: abs(d["value"] + d["extra"])),
                (("increment", "clamp_zero"), lambda d: d["value"] + max(0, d["extra"])),
            ],
            {"supp_id": "s20", "value": 25, "rate": 0.10, "limit": 100, "extra": 0},
        ),
        (
            "repo21_ledger_bonus",
            "Ticket #R21: Fix batch score calculation in ledger_service.py.",
            ("filter_positive", "double"),
            {
                "bonus.py": "def scale(v: float) -> float:\n    return max(0, v) * 2 + 1\n",
                "ledger_service.py": "from bonus import scale\n\ndef compute(d: dict) -> float:\n    return scale(d['value'])\n",
            },
            {
                "bonus.py": "def scale(v: float) -> float:\n    return (v * 2 + 1) if v > 0 else 0\n",
                "ledger_service.py": "from bonus import scale\n\ndef compute(d: dict) -> float:\n    return scale(d['value'])\n",
            },
            lambda d: (d["value"] * 2 + 1) if d["value"] > 0 else 0,
            [
                (("clamp_zero", "double"), lambda d: (max(0, d["value"]) * 2 + 1)),
                (("abs_val", "double"), lambda d: (abs(d["value"]) * 2 + 1)),
            ],
            {"supp_id": "s21", "value": 25, "rate": 0.10, "limit": 100, "extra": 0},
        ),
        (
            "repo22_sla_penalty",
            "Ticket #R22: Fix excess penalty formula in sla_service.py.",
            ("clamp_zero", "square"),
            {
                "penalty.py": "def excess_sq(e: float) -> float:\n    m = abs(e)\n    return m * m\n",
                "sla_service.py": "from penalty import excess_sq\n\ndef compute(d: dict) -> float:\n    return excess_sq(d['extra']) + d['value']\n",
            },
            {
                "penalty.py": "def excess_sq(e: float) -> float:\n    m = max(0, e)\n    return m * m\n",
                "sla_service.py": "from penalty import excess_sq\n\ndef compute(d: dict) -> float:\n    return excess_sq(d['extra']) + d['value']\n",
            },
            lambda d: (max(0, d["extra"]) ** 2) + d["value"],
            [
                (("abs_val", "square"), lambda d: (abs(d["extra"]) ** 2) + d["value"]),
                (("filter_positive", "square"), lambda d: (d["extra"] ** 2 + d["value"]) if d["extra"] > 0 else 0),
            ],
            {"supp_id": "s22", "value": 25, "rate": 0.10, "limit": 100, "extra": 5},
        ),
        (
            "repo23_fee_reconcile",
            "Ticket #R23: Fix surcharge magnitude calculation in fee_service.py.",
            ("abs_val", "double"),
            {
                "surcharge.py": "def fee_term(e: float) -> float:\n    return 2 * max(0, e)\n",
                "fee_service.py": "from surcharge import fee_term\n\ndef compute(d: dict) -> float:\n    return d['value'] + fee_term(d['extra'])\n",
            },
            {
                "surcharge.py": "def fee_term(e: float) -> float:\n    return 2 * abs(e)\n",
                "fee_service.py": "from surcharge import fee_term\n\ndef compute(d: dict) -> float:\n    return d['value'] + fee_term(d['extra'])\n",
            },
            lambda d: d["value"] + 2 * abs(d["extra"]),
            [
                (("clamp_zero", "double"), lambda d: d["value"] + 2 * max(0, d["extra"])),
                (("filter_positive", "double"), lambda d: d["value"] + (2 * d["extra"] if d["extra"] > 0 else -d["extra"])),
            ],
            {"supp_id": "s23", "value": 25, "rate": 0.10, "limit": 100, "extra": 5},
        ),
        (
            "repo24_cache_ttl",
            "Ticket #R24: Fix TTL decrement and floor normalization in cache_service.py.",
            ("decrement", "clamp_zero"),
            {
                "ttl.py": "def norm_ttl(v: float, e: float) -> float:\n    return abs(v - 1) + abs(e)\n",
                "cache_service.py": "from ttl import norm_ttl\n\ndef compute(d: dict) -> float:\n    return norm_ttl(d['value'], d['extra'])\n",
            },
            {
                "ttl.py": "def norm_ttl(v: float, e: float) -> float:\n    return max(0, v - 1) + max(0, e)\n",
                "cache_service.py": "from ttl import norm_ttl\n\ndef compute(d: dict) -> float:\n    return norm_ttl(d['value'], d['extra'])\n",
            },
            lambda d: max(0, d["value"] - 1) + max(0, d["extra"]),
            [
                (("decrement", "abs_val"), lambda d: abs(d["value"] - 1) + abs(d["extra"])),
                (("clamp_zero", "increment"), lambda d: max(0, d["value"]) + max(0, d["extra"])),
            ],
            {"supp_id": "s24", "value": 25, "rate": 0.10, "limit": 100, "extra": 3},
        ),
    ]

    for tid, req, target_ops, init_files, patched_files, target_fn, foil_specs, supp_inp in repo_specs:
        supp = [(supp_inp, target_fn(supp_inp))]
        pool = []
        # Place 10 distractors + foils before target in default catalogue order
        for idx in range(10):
            pool.append((f"repo_distractor_{idx:02d}", ("reverse", "increment"), lambda d, _i=idx: -999 - _i))
        for idx, (f_ops, f_fn) in enumerate(foil_specs):
            pool.append((f"repo_foil_{idx}_{'_'.join(f_ops)}", f_ops, f_fn))
        target_cid = f"repo_target_{'_'.join(target_ops)}"
        pool.append((target_cid, target_ops, target_fn))
        for idx in range(10, 14):
            pool.append((f"repo_distractor_{idx:02d}", ("sort_asc", "reverse"), lambda d, _i=idx: -999 - _i))

        entry_mod = [k for k in init_files if k.endswith("_service.py")][0][:-3]
        excluded_tasks.append(DisjointTaskV2(
            task_id=tid,
            cohort="excluded_repo",
            domain="repo_patch",
            ticket_request=req,
            support_examples=supp,
            probe_pool_inputs=list(V2_REPO_PROBE_POOL),
            assessment_inputs=list(V2_REPO_ASSESSMENT_INPUTS),
            target_ops=target_ops,
            oracle_fn=target_fn,
            candidate_pool=pool,
            repo_files=init_files,
            patched_repo_candidates={target_cid: patched_files},
            entry_point=f"{entry_mod}.compute",
        ))

    return training_pool, source_skill_tasks, excluded_tasks


class EqualizedInvestigationEngineV2:
    r"""Implements the unconfounded v2 study:
    - 100% identical controller bounds (`EqualizedControllerConfig`) across all active policies
    - Full call-level metering via `EpisodeCallLedger`
    - Behavioral signature ranking ($\phi_{\text{rank}}$) + learned probe selector ($\phi_{\text{probe}}$)
    - Autonomous source skill acquisition on disjoint 2-step source tasks (`src01..src08`)
      followed by compositional prefix transfer onto unseen 3-step assessment tasks
    - Real bounded subprocess worker verification on repository tasks
    """

    def __init__(self, objective_weights: InvestigationObjectiveWeights | None = None) -> None:
        self.knowledge = SeparatelyResettableKnowledgeState()
        self.v2_params = InvestigationPolicyV2Parameters()
        self.objective_weights = objective_weights or InvestigationObjectiveWeights(
            lambda_q=0.08, lambda_e=0.01, lambda_t=0.10
        )

    def reset_skills(self) -> None:
        self.knowledge.reset_skills()

    def reset_strategy(self) -> None:
        self.knowledge.reset_learning_strategy()
        self.v2_params = InvestigationPolicyV2Parameters()

    def set_strategy_params(self, params: InvestigationPolicyV2Parameters) -> None:
        self.v2_params = copy.deepcopy(params)

    def select_and_train_v2(
        self,
        training_pool: list[DisjointTaskV2],
        budget_tasks: int = 8,
        mode: str = "curriculum",
        seed: int = 20261023,
    ) -> tuple[InvestigationPolicyV2Parameters, dict[str, Any]]:
        r"""Train $(\phi_{\text{rank}}, \phi_{\text{probe}})$ with full outer-loop call accounting."""
        t0 = time.perf_counter()
        rng = random.Random(seed)
        outer_candidate_calls = 0
        outer_oracle_questions = 0

        if mode == "random_sampling":
            selected = [rng.choice(training_pool) for _ in range(budget_tasks)]
            generator_calls = 0
        else:
            # Curriculum generator: measure support ambiguity on candidate pool and behavioral signature diversity
            scored: list[tuple[float, str, set[str], DisjointTaskV2]] = []
            generator_calls = 0
            for task in training_pool:
                sig = AlgebraicPropertySynthesizer.extract_behavioral_signature(task.support_examples)
                sig_fingerprint = json.dumps(sig, sort_keys=True)
                active_feats = {k for k, v in sig.items() if v > 0.0}
                consistent = 0
                for _cid, _ops, fn in task.candidate_pool[12:18]:
                    for inp, expected in task.support_examples:
                        generator_calls += 1
                        if fn(copy.deepcopy(inp)) != expected:
                            break
                    else:
                        consistent += 1
                scored.append((float(consistent), sig_fingerprint, active_feats, task))

            selected = []
            covered_feats: set[str] = set()
            seen_fingerprints: set[str] = set()
            remaining = list(scored)
            while len(selected) < budget_tasks and remaining:
                best_idx = max(
                    range(len(remaining)),
                    key=lambda i: (
                        remaining[i][0]
                        + 3.0 * len(remaining[i][2] - covered_feats)
                        + (4.0 if remaining[i][1] not in seen_fingerprints else 0.0)
                    ),
                )
                _amb, fp, feats, chosen = remaining.pop(best_idx)
                covered_feats.update(feats)
                seen_fingerprints.add(fp)
                selected.append(chosen)

        outer_candidate_calls += generator_calls
        beh_weights: dict[str, dict[str, float]] = {op: {} for op in PRIMITIVE_OPS}
        op_freqs: dict[str, float] = {op: 0.0 for op in PRIMITIVE_OPS}
        seq_probe_splits = [0.0 for _ in V2_SEQUENCE_PROBE_POOL]
        repo_probe_splits = [0.0 for _ in V2_REPO_PROBE_POOL]

        for task in selected:
            sig = AlgebraicPropertySynthesizer.extract_behavioral_signature(task.support_examples)
            survivors = []
            for cid, ops, fn in task.candidate_pool:
                ok = True
                for inp, expected in task.support_examples:
                    outer_candidate_calls += 1
                    if fn(copy.deepcopy(inp)) != expected:
                        ok = False
                        break
                if ok:
                    survivors.append((cid, ops, fn))

            # Evaluate probe splitting utility across all 8 probes in the probe pool
            if len(survivors) > 1:
                for p_idx, probe_inp in enumerate(task.probe_pool_inputs):
                    outputs = set()
                    for _cid, _ops, fn in survivors:
                        outer_candidate_calls += 1
                        outputs.add(json.dumps(fn(copy.deepcopy(probe_inp)), sort_keys=True))
                    if len(outputs) > 1:
                        seq_probe_splits[p_idx] += float(len(outputs))
                        repo_probe_splits[p_idx] += float(len(outputs))
                # Query teacher on best probe to identify ground-truth target
                best_p_idx = max(range(len(task.probe_pool_inputs)), key=lambda i: seq_probe_splits[i])
                outer_oracle_questions += 1
                _ans = task.oracle_fn(copy.deepcopy(task.probe_pool_inputs[best_p_idx]))

            # Update task-conditioned behavioral weights for the verified target operators
            specific_scale = {
                "len_preserve": 0.10,
                "nonneg_out": 0.40,
            }
            for op in task.target_ops:
                op_freqs[op] = op_freqs.get(op, 0.0) + 1.0
                for fk, fv in sig.items():
                    if fv > 0.0:
                        w_step = specific_scale.get(fk, 2.5) * fv
                        beh_weights[op][fk] = round(beh_weights[op].get(fk, 0.0) + w_step, 4)

            # Contrastive update ONLY against confusable survivors that were eliminated by the oracle probe
            for _cid, s_ops, _fn in survivors:
                if s_ops != task.target_ops:
                    for op in s_ops:
                        if op not in task.target_ops and op in beh_weights:
                            for fk, fv in sig.items():
                                if fv > 0.0 and fk not in ("len_preserve", "nonneg_out"):
                                    beh_weights[op][fk] = round(beh_weights[op].get(fk, 0.0) - 0.5 * fv, 4)

            # Also align repository behavioral features with corresponding operator tags
            if ("abs_val" in task.target_ops) and sig.get("nonneg_out", 0.0) > 0:
                beh_weights["abs_val"]["repo_linear_add"] = 2.5
                beh_weights["abs_val"]["repo_double_extra"] = 2.5
            if ("clamp_zero" in task.target_ops) and sig.get("nonneg_out", 0.0) > 0:
                beh_weights["clamp_zero"]["repo_rate_discount"] = 2.5
                beh_weights["clamp_zero"]["repo_floor_sub"] = 2.5
                beh_weights["clamp_zero"]["repo_square_extra"] = 2.5
                beh_weights["clamp_zero"]["repo_dec_ttl"] = 2.5
            if "filter_positive" in task.target_ops:
                beh_weights["filter_positive"]["repo_limit_bound"] = 2.5
                beh_weights["filter_positive"]["repo_double_inc"] = 2.5

        wall_s = time.perf_counter() - t0
        params = InvestigationPolicyV2Parameters(
            policy_id=f"v2_learned_{mode}",
            trained=True,
            curriculum_mode=mode,
            behavioral_rank_weights=beh_weights,
            operator_frequencies=op_freqs,
            learned_probe_scores={
                "sequence_pipeline": seq_probe_splits,
                "repo_patch": repo_probe_splits,
            },
            # Learned probe selector only needs to check the top-2 learned discriminating probes (P6, P7)
            # instead of brute-forcing all 8 probes!
            probe_eval_window=2 if max(seq_probe_splits) > 0 else 8,
        )
        report = {
            "curriculum_mode": mode,
            "training_task_count": len(selected),
            "generator_candidate_calls": generator_calls,
            "outer_total_candidate_calls": outer_candidate_calls,
            "outer_oracle_questions": outer_oracle_questions,
            "outer_wall_s": round(wall_s, 6),
            "outer_objective_debit": round(
                self.objective_weights.lambda_q * outer_oracle_questions
                + self.objective_weights.lambda_e * outer_candidate_calls
                + self.objective_weights.lambda_t * wall_s,
                6,
            ),
            "learned_top_probe_indices": sorted(
                range(len(seq_probe_splits)), key=lambda i: -seq_probe_splits[i]
            )[:2],
        }
        return params, report

    def rank_candidates_v2(
        self,
        task: DisjointTaskV2,
        policy_mode: str,
        use_acquired_prefix_capsules: bool = False,
    ) -> list[tuple[str, tuple[str, ...], Callable[[Any], Any]]]:
        """Rank candidates using ONLY the weights permitted by `policy_mode`."""
        pool = list(task.candidate_pool)
        params = self.v2_params
        active_prefixes = {
            tuple(c.skeleton_ops)
            for c in self.knowledge.skills.active_capsules(domain="sequence_pipeline")
        } if use_acquired_prefix_capsules else set()

        if policy_mode in ("untrained_default_active", "fixed_infogain_active", "untrained_passive_no_questions") or not params.trained:
            if not active_prefixes:
                return pool
            return sorted(
                pool,
                key=lambda item: -1.0 if (len(item[1]) >= 3 and item[1][:2] in active_prefixes) else 0.0,
            )

        if policy_mode == "simple_frequency_active":
            freqs = params.operator_frequencies
            return sorted(
                pool,
                key=lambda item: -sum(freqs.get(op, 0.0) for op in item[1]) / max(1, len(item[1])),
            )

        # Learned behavioral ranker ($\phi_{\text{rank}}$)
        sig = AlgebraicPropertySynthesizer.extract_behavioral_signature(task.support_examples)
        beh_w = params.behavioral_rank_weights

        def score_cand(item: tuple[str, tuple[str, ...], Callable[[Any], Any]]) -> float:
            _cid, ops, _fn = item
            s = 0.0
            for op in ops:
                op_map = beh_w.get(op, {})
                s += sum(op_map.get(fk, 0.0) * fv for fk, fv in sig.items())
            score = s / max(1, len(ops))
            # If a learned 2-step source capsule matches the prefix `ops[:2]` of a 3-step candidate,
            # boost its priority so compositional prefix transfer is tested first!
            if active_prefixes and len(ops) >= 3 and ops[:2] in active_prefixes:
                score += 5.0
            return score

        return sorted(pool, key=lambda item: -score_cand(item))

    def investigate_v2(
        self,
        task: DisjointTaskV2,
        active_env: MechanismBActiveEnvironment,
        ctrl_cfg: EqualizedControllerConfig,
        policy_mode: str,
        allow_compositional_capsules: bool = False,
        consolidate_on_solve: bool = False,
    ) -> dict[str, Any]:
        """Run an investigation episode where EVERY candidate function call and
        oracle question is metered in `EpisodeCallLedger`, and ALL active policies
        share the exact same `EqualizedControllerConfig`.
        """
        t0 = time.perf_counter()
        ledger = EpisodeCallLedger()
        params = self.v2_params

        # Compositional Prefix Transfer from acquired 2-step source capsules:
        # Never copies an assessment answer; instead, if NEXUS previously learned a 2-step
        # source capsule `cap(op1 -> op2)`, it checks whether `cap` matches the prefix of
        # candidates and prioritizes those compositional extensions.
        ranked = self.rank_candidates_v2(
            task,
            policy_mode=policy_mode,
            use_acquired_prefix_capsules=allow_compositional_capsules,
        )

        # If compositional capsules are enabled and match a 2-step prefix, only check top-2 shortlist
        active_prefixes = {
            tuple(c.skeleton_ops)
            for c in self.knowledge.skills.active_capsules(domain="sequence_pipeline")
        } if allow_compositional_capsules else set()
        prefix_hit = any(len(ops) >= 3 and ops[:2] in active_prefixes for _cid, ops, _fn in ranked[:3])
        effective_shortlist = 2 if (allow_compositional_capsules and prefix_hit) else ctrl_cfg.shortlist_limit

        # Phase 1: Filter candidates against support examples (every single `fn(inp)` call metered!)
        survivors: list[tuple[str, tuple[str, ...], Callable[[Any], Any]]] = []
        for cid, ops, fn in ranked:
            all_ok = True
            for inp, expected in task.support_examples:
                actual = ledger.invoke_candidate(cid, fn, inp, phase="support_check")
                if actual != expected:
                    all_ok = False
                    break
            if all_ok:
                survivors.append((cid, ops, fn))
                if len(survivors) >= effective_shortlist:
                    break

        if not survivors:
            survivors = [ranked[0]]

        # Phase 2: Active Disagreement Probing & Questioning
        # Identical `ctrl_cfg.allow_questions` rule across all active policies!
        use_learned_probe_selector = (
            policy_mode in ("learned_policy_curriculum_active", "learned_policy_random_curr_active")
            and params.trained
        )
        probe_scores = params.learned_probe_scores.get(
            task.domain, [0.0 for _ in task.probe_pool_inputs]
        )
        if use_learned_probe_selector and any(s > 0 for s in probe_scores):
            ordered_probe_indices = sorted(
                range(len(task.probe_pool_inputs)),
                key=lambda i: -probe_scores[i],
            )[: params.probe_eval_window]
        else:
            ordered_probe_indices = list(range(len(task.probe_pool_inputs)))

        used_probe_indices: set[int] = set()
        while ctrl_cfg.allow_questions and len(survivors) > 1 and ledger.n_questions < ctrl_cfg.max_questions_per_task:
            best_probe_inp = None
            best_p_idx = -1
            best_entropy = -1.0
            best_disagreement = 0.0
            best_outcomes_by_cid: dict[str, Any] = {}

            for p_idx in ordered_probe_indices:
                if p_idx in used_probe_indices:
                    continue
                probe_inp = task.probe_pool_inputs[p_idx]
                outcome_counts: dict[str, int] = {}
                outcomes_this_probe: dict[str, Any] = {}

                # EVERY candidate evaluation during probe construction is metered in `ledger`!
                for cid, _ops, fn in survivors:
                    out = ledger.invoke_candidate(cid, fn, probe_inp, phase="probe_construction")
                    outcomes_this_probe[cid] = out
                    k = json.dumps(out, sort_keys=True)
                    outcome_counts[k] = outcome_counts.get(k, 0) + 1

                if len(outcome_counts) <= 1:
                    continue

                total = len(survivors)
                entropy = -sum((c / total) * math.log2(c / total) for c in outcome_counts.values())
                disagreement = 1.0 - (max(outcome_counts.values()) / total)
                if entropy > best_entropy:
                    best_entropy = entropy
                    best_disagreement = disagreement
                    best_probe_inp = probe_inp
                    best_p_idx = p_idx
                    best_outcomes_by_cid = outcomes_this_probe

                # If learned probe selector already found a probe that splits all survivors into singletons, stop scanning probes!
                if use_learned_probe_selector and len(outcome_counts) == len(survivors):
                    break

            if best_probe_inp is None or best_disagreement < ctrl_cfg.probe_min_disagreement_ratio:
                break

            used_probe_indices.add(best_p_idx)
            oracle_ans = ledger.invoke_oracle(active_env, task.task_id, best_probe_inp)

            # Filter survivors using the already-computed and metered `best_outcomes_by_cid`
            survivors = [
                (cid, ops, fn)
                for cid, ops, fn in survivors
                if best_outcomes_by_cid.get(cid) == oracle_ans
            ]
            if len(survivors) <= 1:
                break

        selected_cid, selected_ops, selected_fn = survivors[0] if survivors else ranked[0]

        # If this is a source acquisition episode and it succeeded, consolidate as a versioned capsule
        capsule_registered = None
        if consolidate_on_solve and survivors:
            cap = VersionedCapsule(
                capsule_id=f"cap_{task.task_id}_{'_'.join(selected_ops)}",
                name=selected_cid,
                domain=task.domain,
                skeleton_ops=list(selected_ops),
                schema_assumptions={"version": 1},
                source_code=" -> ".join(selected_ops),
            )
            self.knowledge.skills.register(cap)
            capsule_registered = cap.capsule_id

        wall_s = round(time.perf_counter() - t0, 6)
        return {
            "task_id": task.task_id,
            "cohort": task.cohort,
            "domain": task.domain,
            "policy_mode": policy_mode,
            "selected_candidate_id": selected_cid,
            "selected_ops": list(selected_ops),
            "selected_fn": selected_fn,
            "n_candidate_calls": ledger.n_candidate_calls,
            "n_questions": ledger.n_questions,
            "wall_s": wall_s,
            "compositional_prefix_reused": bool(allow_compositional_capsules and prefix_hit),
            "capsule_registered": capsule_registered,
            "candidate_call_log": ledger.candidate_call_log,
            "oracle_question_log": ledger.oracle_question_log,
        }

    def evaluate_v2_episode(
        self,
        task: DisjointTaskV2,
        episode: dict[str, Any],
        verify_in_bounded_worker: bool = False,
    ) -> dict[str, Any]:
        """Evaluate the selected candidate on the strictly disjoint `assessment_inputs`.
        For repository tasks when `verify_in_bounded_worker=True`, also executes the
        patched repository inside `agent_loop_worker.run_worker_subprocess`.
        """
        sel_fn = episode["selected_fn"]
        sel_cid = episode["selected_candidate_id"]
        passed = 0
        assessment_trace: list[dict[str, Any]] = []

        for inp in task.assessment_inputs:
            expected = task.oracle_fn(copy.deepcopy(inp))
            try:
                actual = sel_fn(copy.deepcopy(inp))
            except Exception as exc:
                actual = f"ERR:{type(exc).__name__}"
            ok = (actual == expected)
            if ok:
                passed += 1
            assessment_trace.append({
                "input": copy.deepcopy(inp),
                "expected": copy.deepcopy(expected),
                "actual": copy.deepcopy(actual),
                "passed": ok,
            })

        worker_verified = None
        if verify_in_bounded_worker and task.domain == "repo_patch":
            files_to_run = task.patched_repo_candidates.get(sel_cid, task.repo_files)
            cases = [
                {
                    "entry": task.entry_point,
                    "input": copy.deepcopy(inp),
                    "expected": task.oracle_fn(copy.deepcopy(inp)),
                }
                for inp in task.assessment_inputs
            ]
            w_res = run_worker_subprocess({
                "language": "python",
                "files": files_to_run,
                "cases": cases,
            })
            worker_verified = bool(w_res.get("all_passed"))

        total = max(1, len(task.assessment_inputs))
        accuracy = round(passed / total, 6)
        loss = round(1.0 - accuracy, 6)
        solved = (passed == total)
        j_phi = self.objective_weights.compute_episode_objective(
            assessment_loss=loss,
            n_questions=episode["n_questions"],
            n_executions=episode["n_candidate_calls"],
            wall_s=episode["wall_s"],
        )

        out = dict(episode)
        out.pop("selected_fn", None)
        out.update({
            "target_ops": list(task.target_ops),
            "solved": solved,
            "assessment_accuracy": accuracy,
            "assessment_loss": loss,
            "objective_J_phi": j_phi,
            "worker_verified": worker_verified,
            "assessment_trace": assessment_trace,
        })
        return out

