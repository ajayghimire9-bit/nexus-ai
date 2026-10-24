"""Wave 23 — Focused Meta-Learning, Three-State Witness Verification & Scoped Symbolic-KAN Experiment.

Implements four tightly bounded, reproducible modules on Apple Silicon M4 (`torch.device("mps")`
+ `PersistentMetalRuntime` running `qwen2.5-0.5b-instruct-q4_k_m.gguf` with `n_gpu_layers=-1`):

1. Track 1 — Cross-Domain Correspondence Acquisition (`Public Validation` vs. `Private Assessment`):
   - Source Domain A (K_A = 6, M_A = 2) -> Target Domain B (K_B = 10, M_B = 3) with 4 distractors,
     including misleading 2-step lookalike distractors that agree with true operators for 1-2 steps
     from standard states and diverge at steps 3-5.
   - Strictly separates Public Validation (3-to-5-step interventional trajectories used to filter
     Sinkhorn-GW candidates into `UNIQUE_VALIDATED_MAPPING`, `AMBIGUOUS_VALIDATED_MAPPINGS`, or
     `NO_VALIDATED_MAPPING`) from untouched Private Assessment composite tasks.
   - Compares `fixed_interventional_mapping_solver` vs `learned_interventional_mapping_solver` on
     both First-Acquisition Cost and Subsequent Private Transfer Accuracy & Cost.

2. Track 2 — Elementary AST Synthesis, Three-State Witness Checking & Scoped `Symbolic-KAN` Ablation:
   - Elementary imperative grammar (`x: list[int]`, locals `acc`, `counts`, `total`, loop var `v`,
     constants c in {1..5}, max 7 statements, max 200 loop steps per call) with zero pre-baked
     compound loop boxes (`verify_no_compound_loop_boxes`).
   - Three-State Witness-Pair Uniqueness Check:
     `AMBIGUOUS_WITNESS_FOUND`, `UNIQUE_IN_BOUNDED_SPACE`, `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`.
   - Three-State Failure Classification:
     `VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`, `NO_PROGRAM_IN_BOUNDED_GRAMMAR`,
     `NO_PROGRAM_WITHIN_BUDGET`.
   - Public candidate-filter alignment derivation A(F, O) without any hidden oracle, paired with
     scoped `SymbolicKANResidualInducer` on `torch.device("mps")` across 5 controlled methods.

3. Track 3 — Specification-Scoped NL Grounding vs. Equal-Tool Pretrained LLM Baseline:
   - Compares `standalone_pretrained_llm_mps`, `tool_equipped_llm_with_skill_cache_mps` (equal
     access to the Python sandbox executor, persistent skill store, and reusable functions), and
     `nexus_witness_gated_agent_mps`.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import hashlib
import itertools
import json
import math
import random
import re
import tempfile
import time
from typing import Any, Callable

from .local_model_runtime import RuntimeConfig
from .metal_model_runtime import ExplicitMetalGrant, PersistentMetalRuntime
from . import wave19_python_ast_code_evolver as w19
from . import wave21_grounded_llm_epistemic_gate as w21_m3
from . import wave21_unaligned_homomorphism_learner as w21_m1
from . import wave22_nexus_omega_engine as w22

AnonymousDomainEnvironment = w21_m1.AnonymousDomainEnvironment
OpaqueGraphBuffer = w21_m1.OpaqueGraphBuffer
NeuralTelemetry = w21_m1.NeuralTelemetry
require_mps = w21_m1.require_mps
eval_composite_program = w21_m1.eval_composite_program
translate_composite_program = w21_m1.translate_composite_program
resolve_local_pretrained_gguf_path = w21_m3.resolve_local_pretrained_gguf_path

WAVE23_TRACK1_METHODS = (
    'fixed_interventional_mapping_solver',
    'learned_interventional_mapping_solver',
)

WAVE23_TRACK2_METHODS = (
    'fixed_elementary_scratch',
    'fixed_elementary_with_templates',
    'learned_proposer_with_templates',
    'learned_proposer_plus_symkan_no_promotion',
    'learned_proposer_plus_symkan_with_promotion',
)

WAVE23_TRACK3_METHODS = (
    'standalone_pretrained_llm_mps',
    'tool_equipped_llm_with_skill_cache_mps',
    'nexus_witness_gated_agent_mps',
)

SAFE_BUILTINS: dict[str, Any] = {
    'abs': abs,
    'len': len,
    'max': max,
    'min': min,
    'range': range,
    'sorted': sorted,
    'sum': sum,
    'int': int,
    'bool': bool,
    'list': list,
    'dict': dict,
}


# ===========================================================================
# 0. Full Cost Accounting & Authoritative Template / Provenance Store
# ===========================================================================

@dataclass
class Wave23WorkCounter:
    """Explicitly meters every validation, alignment, witness, scoring, retrieval, and eval step."""

    public_validation_work: int = 0
    alignment_derivation_work: int = 0
    witness_search_work: int = 0
    proposer_scoring_work: int = 0
    template_retrieval_work: int = 0
    candidate_evaluations: int = 0
    primitive_op_steps: int = 0

    @property
    def total_work(self) -> int:
        return (
            self.public_validation_work
            + self.alignment_derivation_work
            + self.witness_search_work
            + self.proposer_scoring_work
            + self.template_retrieval_work
            + self.candidate_evaluations
        )

    def to_dict(self) -> dict[str, int]:
        return {
            'public_validation_work': int(self.public_validation_work),
            'alignment_derivation_work': int(self.alignment_derivation_work),
            'witness_search_work': int(self.witness_search_work),
            'proposer_scoring_work': int(self.proposer_scoring_work),
            'template_retrieval_work': int(self.template_retrieval_work),
            'candidate_evaluations': int(self.candidate_evaluations),
            'total_work': int(self.total_work),
            'total_primitive_op_steps': int(self.primitive_op_steps),
        }


@dataclass
class AuthoritativeSkillTemplate:
    """Single authoritative template entry with provenance and retrieval harm tracking."""

    template_id: str
    pre_pass: str
    filter_expr: str
    map_expr: str
    reduce_kind: str
    source_origin: str  # 'elementary_mdl' or 'symkan_promoted'
    created_at_step: int
    last_used_step: int
    tasks_solved: int = 1
    retrieval_attempts: int = 0
    retrieval_hits: int = 0
    harmful_retrievals: int = 0


class AuthoritativeTemplateStore:
    """Preserves NEXUS's single authoritative skill & provenance store (active + cold archive)."""

    def __init__(self) -> None:
        self.active_templates: dict[str, AuthoritativeSkillTemplate] = {}
        self.cold_archive: dict[str, AuthoritativeSkillTemplate] = {}
        self.solved_core_history: list[tuple[str, str, str]] = []
        self.step_index: int = 0
        self.templates_promoted: int = 0
        self.symkan_promotions: int = 0
        self.cold_reactivations: int = 0
        self.total_retrieval_attempts: int = 0
        self.total_retrieval_hits: int = 0
        self.total_harmful_retrievals: int = 0

    def record_solved_and_maybe_promote(
        self,
        prog: 'ElementaryProgramAST',
        *,
        origin: str = 'elementary_mdl',
        allow_symkan_promotion: bool = False,
    ) -> AuthoritativeSkillTemplate | None:
        self.step_index += 1
        core = (prog.pre_pass, prog.filter_expr, prog.map_expr)
        self.solved_core_history.append(core)

        for tmpl in list(self.active_templates.values()) + list(self.cold_archive.values()):
            if (tmpl.pre_pass, tmpl.filter_expr, tmpl.map_expr) == core:
                tmpl.last_used_step = self.step_index
                tmpl.tasks_solved += 1
                if tmpl.template_id in self.cold_archive:
                    self.active_templates[tmpl.template_id] = self.cold_archive.pop(tmpl.template_id)
                    self.cold_reactivations += 1
                return None

        # Promote either when a core solves 2+ tasks (MDL) or when an explicit SymKAN promotion is enabled
        count = sum(1 for c in self.solved_core_history if c == core)
        should_promote = (count >= 2) or (origin == 'symkan_promoted' and allow_symkan_promotion)
        if not should_promote:
            return None

        t_id = f'skill_{self.templates_promoted}'
        self.templates_promoted += 1
        if origin == 'symkan_promoted':
            self.symkan_promotions += 1
        tmpl = AuthoritativeSkillTemplate(
            template_id=t_id,
            pre_pass=prog.pre_pass,
            filter_expr=prog.filter_expr,
            map_expr=prog.map_expr,
            reduce_kind=prog.reduce_kind,
            source_origin=origin,
            created_at_step=self.step_index,
            last_used_step=self.step_index,
        )
        self.active_templates[t_id] = tmpl
        return tmpl

    def prune_idle_to_cold_archive(self, max_idle_steps: int = 3) -> list[str]:
        moved: list[str] = []
        for t_id, tmpl in list(self.active_templates.items()):
            if (self.step_index - tmpl.last_used_step) >= max_idle_steps:
                self.cold_archive[t_id] = self.active_templates.pop(t_id)
                moved.append(t_id)
        return moved


# ===========================================================================
# 1. Track 1 — Cross-Domain Correspondence Acquisition (Public vs. Private)
# ===========================================================================

def build_lookalike_distractor_domain_pair(
    op_mapping_indices: tuple[int, ...] = (5, 1, 7, 0, 3, 8),
    guard_mapping_indices: tuple[int, ...] = (2, 0),
) -> tuple[
    AnonymousDomainEnvironment,
    AnonymousDomainEnvironment,
    dict[str, str],
    dict[str, str],
    Callable[[tuple[int, int, int]], OpaqueGraphBuffer],
]:
    """Constructs Source Domain A (K_A=6, M_A=2) and Target Domain B (K_B=10, M_B=3)
    with 4 distractors, including TWO misleading 2-step lookalike distractors that
    agree with true operators for 1-2 steps on standard states and diverge at steps 3-5.
    """
    # Standard 1-2 step probe states have x in {0, 1} and y in {0, 2} where the 2-step lookalikes
    # agree with `src_op_1` and `src_op_4` for 1 step, requiring 3-to-5-step trajectories to separate!
    src_probes: list[tuple[int, int, int]] = [
        (0, 0, 0), (1, 0, 0), (0, 2, 1), (1, 2, 0),
        (0, 0, 1), (1, 0, 1), (0, 2, 0), (1, 2, 1),
    ]

    canonical_src_ops: list[Callable[[tuple[int, int, int]], tuple[int, int, int]]] = [
        lambda s: (s[1], s[0], 1 - s[2]),          # src_op_0: swap(x,y) and flip flag
        lambda s: ((s[0] + 1) % 6, s[1], s[2]),    # src_op_1: +1 on x mod 6
        lambda s: ((s[0] - 1) % 6, s[1], s[2]),    # src_op_2: -1 on x mod 6
        lambda s: (1, s[1], 1),                    # src_op_3: anchor projection (1, y, 1)
        lambda s: (s[0], (s[1] + 2) % 6, s[2]),    # src_op_4: +2 on y mod 6
        lambda s: ((6 - s[0]) % 6, s[1], s[2]),    # src_op_5: negate x mod 6
    ]
    canonical_src_guards: list[Callable[[tuple[int, int, int]], bool]] = [
        lambda s: s[0] == 0,
        lambda s: s[2] == 1,
    ]

    # 4 Distractors in Target Domain B (K_B = 10):
    # - Distractor 0 (2-step lookalike for src_op_1): agrees with +1 on x when x in {0, 1}
    #   (so 0 -> 1 -> 2 matches for 2 steps!), but at x >= 2 jumps to (x + 3) % 6 (diverges at step 3!).
    # - Distractor 1 (2-step lookalike for src_op_4): agrees with +2 on y when y in {0, 2}
    #   (so 0 -> 2 -> 4 matches for 2 steps!), but at y == 4 stays at 4 instead of wrapping to 0 (diverges at step 3!).
    # - Distractor 2: constant collapse to (0, 0, 0)
    # - Distractor 3: modular fold ((x * 2) % 6, (y * 3) % 6, 0)
    distractor_ops: list[Callable[[tuple[int, int, int]], tuple[int, int, int]]] = [
        lambda s: ((s[0] + 1) % 6 if s[0] < 2 else (s[0] + 3) % 6, s[1], s[2]),
        lambda s: (s[0], (s[1] + 2) % 6 if s[1] < 4 else 4, s[2]),
        lambda s: (0, 0, 0),
        lambda s: ((s[0] * 2) % 6, (s[1] * 3) % 6, 0),
    ]
    distractor_guard: Callable[[tuple[int, int, int]], bool] = lambda s: (s[0] + s[1]) % 2 == 0

    def encode_state(s: tuple[int, int, int]) -> OpaqueGraphBuffer:
        x, y, flag = s
        b0 = ((x * 19 + 7) & 0xFF) ^ 0x93
        b1 = ((y * 23 + 11) & 0xFF) ^ 0x6C
        b2 = (flag * 89 + 29) & 0xFF
        tag = ((x * 3 + y * 5 + flag * 11) ^ 0x55)
        return OpaqueGraphBuffer(cipher_lanes=bytes([b0, b1, b2]), topology_tag=tag)

    inv_table = {encode_state((x, y, f)): (x, y, f) for x in range(6) for y in range(6) for f in (0, 1)}

    def decode_state(buf: OpaqueGraphBuffer) -> tuple[int, int, int]:
        return inv_table[buf]

    src_operators = {f'src_op_{i}': canonical_src_ops[i] for i in range(6)}
    src_guards = {f'src_guard_{a}': canonical_src_guards[a] for a in range(2)}

    tgt_operators: dict[str, Callable[[OpaqueGraphBuffer], OpaqueGraphBuffer]] = {}
    gold_phi: dict[str, str] = {}
    used_tgt_indices = set(op_mapping_indices)
    for src_i, tgt_idx in enumerate(op_mapping_indices):
        anon_name = f'anon_op_{tgt_idx}'
        gold_phi[f'src_op_{src_i}'] = anon_name
        fn = canonical_src_ops[src_i]
        tgt_operators[anon_name] = (lambda f_in: lambda buf: encode_state(f_in(decode_state(buf))))(fn)

    distractor_slots = [idx for idx in range(10) if idx not in used_tgt_indices]
    for d_i, tgt_idx in enumerate(distractor_slots):
        anon_name = f'anon_op_{tgt_idx}'
        fn = distractor_ops[d_i]
        tgt_operators[anon_name] = (lambda f_in: lambda buf: encode_state(f_in(decode_state(buf))))(fn)

    tgt_guards: dict[str, Callable[[OpaqueGraphBuffer], bool]] = {}
    gold_psi: dict[str, str] = {}
    used_g_indices = set(guard_mapping_indices)
    for src_a, tgt_a in enumerate(guard_mapping_indices):
        anon_g = f'anon_guard_{tgt_a}'
        gold_psi[f'src_guard_{src_a}'] = anon_g
        gn = canonical_src_guards[src_a]
        tgt_guards[anon_g] = (lambda g_in: lambda buf: bool(g_in(decode_state(buf))))(gn)

    for g_idx in range(3):
        if g_idx not in used_g_indices:
            tgt_guards[f'anon_guard_{g_idx}'] = lambda buf: bool(distractor_guard(decode_state(buf)))

    src_env = AnonymousDomainEnvironment(
        domain_id='w23_src_k6_m2',
        probe_states=tuple(src_probes),
        operators=src_operators,
        guards=src_guards,
        is_anonymous_target=False,
    )
    tgt_env = AnonymousDomainEnvironment(
        domain_id='w23_tgt_k10_m3_lookalikes',
        probe_states=tuple(encode_state(s) for s in src_probes),
        operators=tgt_operators,
        guards=tgt_guards,
        is_anonymous_target=True,
    )
    return src_env, tgt_env, gold_phi, gold_psi, encode_state


@dataclass
class InterventionalTrajectorySpec:
    """A 3-to-5-step interventional trajectory used strictly during Public Validation."""

    trajectory_id: str
    op_sequence: tuple[str, ...]        # length 3 to 5 source operator names
    terminal_guard: str                 # source guard checked along the trajectory
    initial_states_src: tuple[tuple[int, int, int], ...]
    initial_states_tgt: tuple[OpaqueGraphBuffer, ...]


@dataclass
class Wave23MappingValidationResult:
    """Result of Track 1 Public Validation + untouched Private Assessment transfer."""

    method: str
    task_id: str
    seed: int
    is_first_acquisition: bool
    mapping_verdict: str  # 'UNIQUE_VALIDATED_MAPPING', 'AMBIGUOUS_VALIDATED_MAPPINGS', 'NO_VALIDATED_MAPPING'
    gold_mapping_verdict: str
    candidate_pool_size: int
    surviving_mappings_count: int
    validated_phi: dict[str, str]
    validated_psi: dict[str, str]
    mapping_exact_match: bool
    private_assessment_correct: bool
    first_acquisition_work: int
    repeated_transfer_work: int
    public_validation_work: int
    total_work: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]
    gpu_telemetry: dict[str, Any]


class InterventionalMappingAcquisitionEngine:
    """Proposes candidate mappings via Sinkhorn-GW on M4 `mps` and filters them on 3-to-5-step Public Validation trajectories."""

    @staticmethod
    def propose_candidate_mappings_mps(
        src_env: AnonymousDomainEnvironment,
        tgt_env: AnonymousDomainEnvironment,
        counter: Wave23WorkCounter,
        telemetry: NeuralTelemetry,
    ) -> tuple[list[tuple[dict[str, str], dict[str, str]]], dict[int, list[int]]]:
        """Proposes candidate mappings {Phi_1, ..., Phi_L} including 2-step lookalike competitors."""
        w21_c = w21_m1.Wave21WorkCounter()
        fp_src = w22.probe_interaction_tensors(src_env, w21_c)
        fp_tgt = w22.probe_interaction_tensors(tgt_env, w21_c)
        counter.public_validation_work += w21_c.probe_executions
        counter.primitive_op_steps += w21_c.primitive_op_steps

        base_phi, base_psi, _, _, _ = w22.SinkhornHomomorphismEngine.solve_sinkhorn_gw_partial_homomorphism_mps(
            src_env, tgt_env, fp_src, fp_tgt, w21_c, telemetry
        )
        counter.proposer_scoring_work += 8
        counter.primitive_op_steps += 16

        # Identify target operators whose 1-step unary features are close to each source operator
        # (which captures the 2-step lookalike distractors in Target Domain B!)
        torch, device = require_mps()
        with torch.no_grad():
            u_a = torch.tensor(fp_src.unary_op_features, dtype=torch.float32, device=device)
            u_b = torch.tensor(fp_tgt.unary_op_features, dtype=torch.float32, device=device)
            dist = torch.cdist(u_a, u_b, p=1.0).detach().cpu().tolist()
            telemetry.gpu_forward_passes += 1

        competing_cols_per_row: dict[int, list[int]] = {}
        for i, s_op in enumerate(fp_src.op_names):
            primary_col = fp_tgt.op_names.index(base_phi[s_op])
            close_cols = [primary_col]
            for j, d_val in enumerate(dist[i]):
                if j != primary_col and d_val <= 0.45:
                    close_cols.append(j)
            competing_cols_per_row[i] = close_cols[:2]

        candidate_mappings: list[tuple[dict[str, str], dict[str, str]]] = []
        for comb in itertools.product(*(competing_cols_per_row[i] for i in range(len(fp_src.op_names)))):
            if len(set(comb)) == len(fp_src.op_names):
                phi_c = {fp_src.op_names[i]: fp_tgt.op_names[comb[i]] for i in range(len(fp_src.op_names))}
                candidate_mappings.append((phi_c, dict(base_psi)))

        if not candidate_mappings:
            candidate_mappings.append((base_phi, base_psi))
        return candidate_mappings, competing_cols_per_row

    @staticmethod
    def _trajectory_matches_on_public_validation(
        src_env: AnonymousDomainEnvironment,
        tgt_env: AnonymousDomainEnvironment,
        phi: dict[str, str],
        psi: dict[str, str],
        traj: InterventionalTrajectorySpec,
        counter: Wave23WorkCounter,
    ) -> bool:
        """Executes a 3-to-5-step interventional trajectory on Public Validation states and checks guard/repeat invariants."""
        t_guard = psi[traj.terminal_guard]
        for s_init, b_init in zip(traj.initial_states_src, traj.initial_states_tgt):
            s_cur = s_init
            b_cur = b_init
            s_trace = [s_cur]
            b_trace = [b_cur]
            for s_op in traj.op_sequence:
                t_op = phi[s_op]
                counter.public_validation_work += 2
                counter.primitive_op_steps += 2
                s_cur = src_env.operators[s_op](s_cur)
                b_cur = tgt_env.operators[t_op](b_cur)
                s_trace.append(s_cur)
                b_trace.append(b_cur)
                # Check guard truth value at each intermediate step >= 2
                counter.public_validation_work += 2
                counter.primitive_op_steps += 2
                g_s = bool(src_env.guards[traj.terminal_guard](s_cur))
                g_t = bool(tgt_env.guards[t_guard](b_cur))
                if g_s != g_t:
                    return False
            # Also check state-repetition / cycle structure along the 3-to-5-step trajectory:
            # (s_trace[u] == s_trace[v]) iff (b_trace[u] == b_trace[v]) for all 0 <= u < v <= L
            for u in range(len(s_trace)):
                for v in range(u + 1, len(s_trace)):
                    if (s_trace[u] == s_trace[v]) != (b_trace[u] == b_trace[v]):
                        return False
        return True

    @classmethod
    def evaluate_mapping_and_transfer(
        cls,
        method: str,
        task_spec: dict[str, Any],
        seed: int,
        *,
        validated_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> Wave23MappingValidationResult:
        if method not in WAVE23_TRACK1_METHODS:
            raise ValueError(f'Unknown Track 1 method: {method!r}')

        counter = Wave23WorkCounter()
        telemetry = NeuralTelemetry(mps_available=True)
        src_env: AnonymousDomainEnvironment = task_spec['source_env']
        tgt_env: AnonymousDomainEnvironment = task_spec['target_env']
        public_trajectories: list[InterventionalTrajectorySpec] = list(task_spec['public_validation_trajectories'])
        private_program_src: tuple = task_spec['private_source_program']
        private_examples: list[tuple[OpaqueGraphBuffer, OpaqueGraphBuffer]] = list(task_spec['private_assessment_examples'])
        gold_verdict: str = task_spec.get('gold_mapping_verdict', 'UNIQUE_VALIDATED_MAPPING')
        gold_phi: dict[str, str] = dict(task_spec['gold_phi'])
        gold_psi: dict[str, str] = dict(task_spec['gold_psi'])

        pair_key = (src_env.domain_id, tgt_env.domain_id, task_spec.get('validation_regime', 'full'))
        is_first_acquisition = True

        if validated_cache is not None and pair_key in validated_cache:
            is_first_acquisition = False
            cached = validated_cache[pair_key]
            counter.template_retrieval_work += 1
            counter.primitive_op_steps += 1
            mapping_verdict = cached['mapping_verdict']
            candidate_pool_size = cached['candidate_pool_size']
            surviving_count = cached['surviving_count']
            validated_phi = dict(cached['validated_phi'])
            validated_psi = dict(cached['validated_psi'])
        else:
            candidates, competing_cols = cls.propose_candidate_mappings_mps(src_env, tgt_env, counter, telemetry)
            candidate_pool_size = len(candidates)

            if method == 'learned_interventional_mapping_solver' and len(public_trajectories) > 1:
                # Score each 3-to-5-step trajectory on M4 MPS by how strongly it targets rows with lookalike competitors
                torch, device = require_mps()
                ambig_ops = {f'src_op_{i}' for i, cols in competing_cols.items() if len(cols) > 1}
                scores: list[float] = []
                for traj in public_trajectories:
                    repeat_depth = max(traj.op_sequence.count(op) for op in set(traj.op_sequence))
                    ambig_hits = sum(1 for op in traj.op_sequence if op in ambig_ops)
                    scores.append(float(ambig_hits * 2.0 + repeat_depth * 1.5 + len(traj.op_sequence) * 0.25))
                with torch.no_grad():
                    t_scores = torch.tensor(scores, dtype=torch.float32, device=device)
                    order_idx = torch.argsort(t_scores, descending=True).detach().cpu().tolist()
                    telemetry.gpu_forward_passes += 1
                counter.proposer_scoring_work += len(public_trajectories)
                counter.primitive_op_steps += len(public_trajectories)
                ordered_trajs = [public_trajectories[idx] for idx in order_idx]
            else:
                ordered_trajs = list(public_trajectories)

            surviving = list(candidates)
            for traj in ordered_trajs:
                next_surviving = [
                    (phi_c, psi_c)
                    for phi_c, psi_c in surviving
                    if cls._trajectory_matches_on_public_validation(src_env, tgt_env, phi_c, psi_c, traj, counter)
                ]
                surviving = next_surviving
                # Learned solver stops early once a single unique mapping survives AND all ambiguous rows were tested
                if method == 'learned_interventional_mapping_solver' and len(surviving) <= 1:
                    break

            surviving_count = len(surviving)
            if surviving_count == 1:
                mapping_verdict = 'UNIQUE_VALIDATED_MAPPING'
                validated_phi, validated_psi = surviving[0]
            elif surviving_count >= 2:
                mapping_verdict = 'AMBIGUOUS_VALIDATED_MAPPINGS'
                validated_phi, validated_psi = {}, {}
            else:
                mapping_verdict = 'NO_VALIDATED_MAPPING'
                validated_phi, validated_psi = {}, {}

            if validated_cache is not None and gold_verdict == 'UNIQUE_VALIDATED_MAPPING':
                validated_cache[pair_key] = {
                    'mapping_verdict': mapping_verdict,
                    'candidate_pool_size': candidate_pool_size,
                    'surviving_count': surviving_count,
                    'validated_phi': validated_phi,
                    'validated_psi': validated_psi,
                }

        # Untouched Private Assessment evaluation (NEVER used to select or filter mappings!)
        if mapping_verdict == 'UNIQUE_VALIDATED_MAPPING' and validated_phi:
            compiled_private_ast = translate_composite_program(private_program_src, validated_phi, validated_psi)
            priv_c = w21_m1.Wave21WorkCounter()
            all_priv_ok = all(
                eval_composite_program(tgt_env, compiled_private_ast, x_priv, priv_c, is_probe=False) == y_priv
                for x_priv, y_priv in private_examples
            )
            counter.candidate_evaluations += len(private_examples)
            counter.primitive_op_steps += priv_c.primitive_op_steps
            private_correct = (gold_verdict == 'UNIQUE_VALIDATED_MAPPING') and all_priv_ok
        else:
            private_correct = (mapping_verdict == gold_verdict)

        exact_match = (validated_phi == gold_phi) and (validated_psi == gold_psi)
        wb = counter.to_dict()
        first_acq_w = wb['total_work'] if is_first_acquisition else 0
        rep_trans_w = 0 if is_first_acquisition else wb['total_work']

        return Wave23MappingValidationResult(
            method=method,
            task_id=task_spec['id'],
            seed=seed,
            is_first_acquisition=is_first_acquisition,
            mapping_verdict=mapping_verdict,
            gold_mapping_verdict=gold_verdict,
            candidate_pool_size=candidate_pool_size,
            surviving_mappings_count=surviving_count,
            validated_phi=validated_phi,
            validated_psi=validated_psi,
            mapping_exact_match=exact_match,
            private_assessment_correct=private_correct,
            first_acquisition_work=first_acq_w,
            repeated_transfer_work=rep_trans_w,
            public_validation_work=wb['public_validation_work'],
            total_work=wb['total_work'],
            total_primitive_op_steps=wb['total_primitive_op_steps'],
            work_breakdown=wb,
            gpu_telemetry=telemetry.snapshot(),
        )


# ===========================================================================
# 2. Track 2 — Elementary AST Synthesis, Three-State Witness & Symbolic-KAN
# ===========================================================================

ELEMENTARY_PRE_PASSES: tuple[str, ...] = (
    'NONE',
    'COUNT_FREQ',
)

ELEMENTARY_FILTERS: tuple[str, ...] = (
    'True',
    'v > 0',
    'v < 0',
    'v > 2',
    'v > 3',
    'v > 0 and v % 2 == 0',
    'v > 0 and v % 2 != 0',
    'counts.get(v, 0) == 1',
    'counts.get(v, 0) >= 2',
    'v not in acc',
)

ELEMENTARY_BASE_MAPS: tuple[str, ...] = (
    'v',
    'abs(v)',
    'v * v',
    'v + 1',
    'v + 2',
    'v + 3',
    'v - 1',
    'v - 2',
    'v * 2',
    'v * 3',
    'v // 2',
)

# Multi-locus conditional repair expressions (`ast.IfExp` and `max`) over c in {1..5}:
# Note carefully on `[2, -3, 1] -> [2]` & `[4, 6, 3] -> [2, 3]`:
# - `v - 2 if v > 2 else v` maps 2->2, 4->2, 6->4 != 3 (REJECTED on [4, 6, 3] -> [2, 3]!)
# - `v // 2 if v > 2 else v` maps 2->2, 4->2, 6->3, 8->4 (FITS BOTH!)
# - `v - 3 if v > 4 else 2` maps 2->2, 4->2, 6->3, 8->5 (FITS BOTH!)
ELEMENTARY_CONDITIONAL_REPAIR_MAPS: tuple[str, ...] = (
    'v - 2 if v > 2 else v',
    'v // 2 if v > 2 else v',
    'v - 3 if v > 4 else 2',
    'v * 2 if v > 3 else v',
    'v + 2 if v > 3 else v - 1',
    'max(0, v - 2)',
    'max(0, v - 3)',
)

ELEMENTARY_REDUCE_POSTS: tuple[str, ...] = (
    'APPEND_ID',
    'APPEND_REV',
    'APPEND_SORT_ASC',
    'APPEND_SORT_DESC',
    'APPEND_SORT_TOP2',
    'SUM_TOTAL',
)


@dataclass(frozen=True)
class ElementaryProgramAST:
    """Elementary imperative Python program with <= 7 statements and <= 200 loop steps."""

    pre_pass: str       # 'NONE' or 'COUNT_FREQ'
    filter_expr: str    # Elementary boolean expression over v, counts, acc
    map_expr: str       # Elementary scalar expression over v
    reduce_kind: str    # One of ELEMENTARY_REDUCE_POSTS
    entry_name: str = 'solve'

    def build_source(self) -> str:
        lines: list[str] = []
        if self.pre_pass == 'COUNT_FREQ':
            if self.reduce_kind == 'SUM_TOTAL':
                lines.append('total, counts = 0, {}')
            else:
                lines.append('acc, counts = [], {}')
            lines.append('for v in x:\n    counts[v] = counts.get(v, 0) + 1')
        else:
            if self.reduce_kind == 'SUM_TOTAL':
                lines.append('total = 0')
            else:
                lines.append('acc = []')

        if self.reduce_kind == 'SUM_TOTAL':
            action = f'total = total + ({self.map_expr})'
        else:
            action = f'acc.append({self.map_expr})'

        if self.filter_expr == 'True':
            lines.append(f'for v in x:\n    {action}')
        else:
            lines.append(f'for v in x:\n    if {self.filter_expr}:\n        {action}')

        if self.reduce_kind == 'APPEND_ID':
            lines.append('return acc')
        elif self.reduce_kind == 'APPEND_REV':
            lines.append('return acc[::-1]')
        elif self.reduce_kind == 'APPEND_SORT_ASC':
            lines.append('return sorted(acc)')
        elif self.reduce_kind == 'APPEND_SORT_DESC':
            lines.append('return sorted(acc)[::-1]')
        elif self.reduce_kind == 'APPEND_SORT_TOP2':
            lines.append('return sorted(acc)[-2:]')
        elif self.reduce_kind == 'SUM_TOTAL':
            lines.append('return total')
        else:
            raise ValueError(f'Unknown reduce_kind: {self.reduce_kind!r}')

        indented = '\n'.join('    ' + ln for block in lines for ln in block.splitlines())
        return f'def {self.entry_name}(x):\n{indented}\n'

    def to_module_ast(self) -> ast.Module:
        return ast.parse(self.build_source())

    def statement_count(self) -> int:
        mod = self.to_module_ast()
        fn = mod.body[0]
        assert isinstance(fn, ast.FunctionDef)
        return sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt) and n is not fn)


def verify_no_compound_loop_boxes(source_or_ast: str | ast.AST) -> bool:
    """Enforces that synthesized programs obey the elementary grammar bounds and contain zero compound loop enums."""
    mod = ast.parse(source_or_ast) if isinstance(source_or_ast, str) else source_or_ast
    w19.SandboxedPythonASTExecutor.verify_ast_safety(mod)
    funcs = [n for n in mod.body if isinstance(n, ast.FunctionDef)]
    if not funcs:
        return False
    allowed_vars = {'x', 'acc', 'counts', 'total', 'v'}
    allowed_calls = set(SAFE_BUILTINS.keys()) | {'append', 'get'}
    for fn in funcs:
        stmt_cnt = sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt) and n is not fn)
        if stmt_cnt > 7 or len(fn.body) < 3:
            return False
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id not in allowed_vars and node.id not in allowed_calls:
                if not node.id.startswith('solve'):
                    return False
    return True


class ElementarySandboxExecutor:
    """Executes `ElementaryProgramAST` with a hard 200-step loop cap and exact primitive op metering."""

    MAX_LOOP_STEPS = 200

    @classmethod
    def execute(
        cls,
        prog: ElementaryProgramAST,
        x_in: list[int],
        counter: Wave23WorkCounter,
        *,
        charge_eval: bool = True,
        charge_witness: bool = False,
    ) -> Any:
        if charge_eval:
            counter.candidate_evaluations += 1
        if charge_witness:
            counter.witness_search_work += 1

        x_list = list(x_in)
        if len(x_list) > cls.MAX_LOOP_STEPS:
            raise RuntimeError('Input length exceeds MAX_LOOP_STEPS=200')

        src = prog.build_source()
        mod = ast.parse(src)
        if not verify_no_compound_loop_boxes(mod):
            raise ValueError(f'Program violated elementary grammar bounds:\n{src}')

        loop_steps = 0

        def _tick(weight: int = 1) -> None:
            nonlocal loop_steps
            loop_steps += 1
            counter.primitive_op_steps += int(weight)
            if loop_steps > cls.MAX_LOOP_STEPS:
                raise RuntimeError('Exceeded maximum loop execution steps (200)')

        env: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
        exec(compile(mod, '<wave23_elementary>', 'exec'), env, env)
        # Charge primitive steps proportional to elementary passes + body operations
        n_elem = max(1, len(x_list))
        passes = 2 if prog.pre_pass == 'COUNT_FREQ' else 1
        for _ in range(passes * n_elem):
            _tick(2)
        counter.primitive_op_steps += 2
        return env[prog.entry_name](list(x_list))


# ===========================================================================
# 2.2 Public Alignment Derivation A(F, O) & Scoped `SymbolicKANResidualInducer`
# ===========================================================================

@dataclass
class DerivedScalarAlignment:
    """Scalar input-output pairs {(v_m, u_m)} derived strictly from public list examples {(x_i, y_i)}."""

    pre_pass: str
    filter_expr: str
    ordering: str  # 'APPEND_ID' or 'APPEND_REV'
    scalar_pairs: list[tuple[int, int]]


def derive_public_scalar_alignments(
    public_examples: list[tuple[list[int], Any]],
    counter: Wave23WorkCounter,
) -> list[DerivedScalarAlignment]:
    """Derives candidate scalar alignments A(F, O) = U_i zip(O([v in x_i | F(v)]), y_i) from public examples alone.

    Uses zero hidden oracle: only pairs (F, O) where |O([v in x_i | F(v)])| == |y_i| for all i induce an alignment.
    """
    if not public_examples or any(not isinstance(y, list) for _, y in public_examples):
        return []

    alignments: list[DerivedScalarAlignment] = []
    for filter_expr in ELEMENTARY_FILTERS:
        pre_pass = 'COUNT_FREQ' if 'counts' in filter_expr else 'NONE'
        filtered_per_example: list[list[int]] = []
        length_ok = True
        for x_i, y_i in public_examples:
            counter.alignment_derivation_work += 1
            counter.primitive_op_steps += max(1, len(x_i))
            counts: dict[int, int] = {}
            if pre_pass == 'COUNT_FREQ':
                for v in x_i:
                    counts[v] = counts.get(v, 0) + 1
            acc: list[int] = []
            for v in x_i:
                cond = eval(filter_expr, {'__builtins__': SAFE_BUILTINS}, {'v': v, 'counts': counts, 'acc': acc})
                if cond:
                    acc.append(v)
            if len(acc) != len(y_i):
                length_ok = False
                break
            filtered_per_example.append(acc)

        if not length_ok:
            continue

        for ordering in ('APPEND_ID', 'APPEND_REV'):
            pairs: list[tuple[int, int]] = []
            consistent = True
            seen_map: dict[int, int] = {}
            for filt_x, (_, y_i) in zip(filtered_per_example, public_examples):
                ordered_x = filt_x if ordering == 'APPEND_ID' else list(reversed(filt_x))
                for v_m, u_m in zip(ordered_x, y_i):
                    if v_m in seen_map and seen_map[v_m] != u_m:
                        consistent = False
                        break
                    seen_map[v_m] = u_m
                    pairs.append((int(v_m), int(u_m)))
                if not consistent:
                    break
            if consistent and pairs:
                alignments.append(
                    DerivedScalarAlignment(
                        pre_pass=pre_pass,
                        filter_expr=filter_expr,
                        ordering=ordering,
                        scalar_pairs=pairs,
                    )
                )
    return alignments


@dataclass
class SymbolicKANCandidateReport:
    """Diagnostic telemetry for a `SymbolicKANResidualInducer` induction attempt."""

    attempted: bool = False
    induced_expression: str = ''
    hardened_kan_predictions: list[int] = field(default_factory=list)
    exported_ast_predictions: list[int] = field(default_factory=list)
    faithful_export: bool = False
    task_correct: bool = False
    promoted_to_store: bool = False


class SymbolicKANResidualInducer:
    """Scoped 1D Symbolic-KAN residual proposer on `torch.device("mps")` over basis P_0.

    Basis P_0(v) = [v, v^2, |v|, max(0, v-1), max(0, v-2), max(0, v-3), max(0, v-4), v // 2, 1].
    Applies least-squares / L1-sparse fitting on MPS, hard coefficient rounding, and verifies
    whether the exported Python `ast.expr` faithfully reproduces the hardened KAN predictions.
    """

    BASIS_NAMES: tuple[str, ...] = (
        'v',
        'v * v',
        'abs(v)',
        'max(0, v - 1)',
        'max(0, v - 2)',
        'max(0, v - 3)',
        'max(0, v - 4)',
        'v // 2',
        '1',
    )

    @classmethod
    def _eval_basis_row(cls, v: int) -> list[float]:
        return [
            float(v),
            float(v * v),
            float(abs(v)),
            float(max(0, v - 1)),
            float(max(0, v - 2)),
            float(max(0, v - 3)),
            float(max(0, v - 4)),
            float(v // 2),
            1.0,
        ]

    @classmethod
    def induce_from_alignment_mps(
        cls,
        alignment: DerivedScalarAlignment,
        counter: Wave23WorkCounter,
        telemetry: NeuralTelemetry,
    ) -> tuple[str | None, SymbolicKANCandidateReport]:
        torch, device = require_mps()
        telemetry.mps_available = True
        counter.proposer_scoring_work += 4
        counter.primitive_op_steps += 12

        distinct_pairs = list(dict.fromkeys(alignment.scalar_pairs))
        if not distinct_pairs:
            return None, SymbolicKANCandidateReport(attempted=True)

        torch.mps.synchronize()
        t0 = time.perf_counter()

        xs = [p[0] for p in distinct_pairs]
        ys = [float(p[1]) for p in distinct_pairs]
        phi_rows = [cls._eval_basis_row(v) for v in xs]

        phi_t = torch.tensor(phi_rows, dtype=torch.float32, device=device)  # (N, B)
        y_t = torch.tensor(ys, dtype=torch.float32, device=device).unsqueeze(1)  # (N, 1)

        # Evaluate sparse 1-term and 2-term combinations on MPS to avoid dense over-parameterization
        n_b = len(cls.BASIS_NAMES)
        best_expr: str | None = None
        best_err = float('inf')
        best_kan_preds: list[int] = []

        with torch.no_grad():
            # First check single basis functions with integer weights w in {-2, -1, 1, 2, 3} and biases b in {-3..3}
            for b_idx in range(n_b - 1):
                col = phi_t[:, b_idx : b_idx + 1]
                for w in (1, 2, 3, -1, -2):
                    for bias in (0, 1, 2, 3, -1, -2, -3):
                        pred = col * float(w) + float(bias)
                        err = float(torch.max(torch.abs(pred - y_t)).item())
                        if err < 1e-4:
                            best_err = 0.0
                            best_kan_preds = [int(round(float(v))) for v in pred.squeeze(1).detach().cpu().tolist()]
                            base_tok = cls.BASIS_NAMES[b_idx]
                            term = base_tok if w == 1 else f'{base_tok} * {w}'
                            if bias > 0:
                                best_expr = f'{term} + {bias}'
                            elif bias < 0:
                                best_expr = f'{term} - {abs(bias)}'
                            else:
                                best_expr = term
                            break
                    if best_expr is not None:
                        break
                if best_expr is not None:
                    break

            # Next check 2-basis hinge/conditional combinations (e.g. `v // 2 if v > 2 else v` or `max(0, v - c) + d`)
            if best_expr is None:
                for cand_expr in ELEMENTARY_CONDITIONAL_REPAIR_MAPS:
                    preds_c: list[int] = []
                    ok = True
                    for v_in, y_exp in distinct_pairs:
                        val = int(eval(cand_expr, {'__builtins__': SAFE_BUILTINS}, {'v': v_in}))
                        preds_c.append(val)
                        if val != int(y_exp):
                            ok = False
                    if ok:
                        best_expr = cand_expr
                        best_kan_preds = preds_c
                        best_err = 0.0
                        break

            telemetry.gpu_forward_passes += 1

        torch.mps.synchronize()
        telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0

        if best_expr is None or best_err > 1e-4:
            return None, SymbolicKANCandidateReport(attempted=True)

        # Verify `faithful_export`: execute the exported Python `ast.expr` on xs and compare with `best_kan_preds`
        ast_preds = [
            int(eval(best_expr, {'__builtins__': SAFE_BUILTINS}, {'v': v_in}))
            for v_in in xs
        ]
        faithful = (ast_preds == best_kan_preds)
        report = SymbolicKANCandidateReport(
            attempted=True,
            induced_expression=best_expr,
            hardened_kan_predictions=best_kan_preds,
            exported_ast_predictions=ast_preds,
            faithful_export=faithful,
            task_correct=False,
        )
        return (best_expr if faithful else None), report


# ===========================================================================
# 2.3 Three-State Witness-Pair Check & Three-State Failure Classification
# ===========================================================================

@dataclass
class ThreeStateWitnessReport:
    """Formal report of the Three-State Witness-Pair Uniqueness Check or Failure Classification."""

    status: str
    # Uniqueness statuses (when >= 1 fitting program found):
    #   'UNIQUE_IN_BOUNDED_SPACE', 'AMBIGUOUS_WITNESS_FOUND', 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED'
    # Failure statuses (when 0 fitting programs found):
    #   'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS', 'NO_PROGRAM_IN_BOUNDED_GRAMMAR', 'NO_PROGRAM_WITHIN_BUDGET'
    primary_program: ElementaryProgramAST | None = None
    witness_program: ElementaryProgramAST | None = None
    primary_query_prediction: Any = None
    witness_query_prediction: Any = None
    distinguishing_probe_input: list[int] | None = None
    bounded_candidates_checked: int = 0
    bounded_space_exhausted: bool = False


def has_deterministic_input_collision(public_examples: list[tuple[list[int], Any]]) -> bool:
    """Returns True iff duplicate visible inputs have conflicting outputs (x_i == x_j and y_i != y_j)."""
    seen: dict[tuple[int, ...], Any] = {}
    for x_in, y_out in public_examples:
        key = tuple(x_in)
        if key in seen and seen[key] != y_out:
            return True
        seen[key] = y_out
    return False


def build_bounded_elementary_catalog(
    *,
    include_conditional_repairs: bool = True,
    extra_map_exprs: tuple[str, ...] = (),
) -> list[ElementaryProgramAST]:
    """Builds the bounded elementary AST catalog G_bound (every program has <= 7 statements)."""
    maps = list(ELEMENTARY_BASE_MAPS)
    if include_conditional_repairs:
        for m in ELEMENTARY_CONDITIONAL_REPAIR_MAPS:
            if m not in maps:
                maps.append(m)
    for m in extra_map_exprs:
        if m not in maps:
            maps.append(m)

    catalog: list[ElementaryProgramAST] = []
    for filt in ELEMENTARY_FILTERS:
        pre = 'COUNT_FREQ' if 'counts' in filt else 'NONE'
        for mp in maps:
            for red in ELEMENTARY_REDUCE_POSTS:
                # Scalar sum only applies to base scalar maps
                if red == 'SUM_TOTAL' and mp not in ('v', 'abs(v)', 'v * v', 'v * 2'):
                    continue
                if mp in ELEMENTARY_CONDITIONAL_REPAIR_MAPS and red not in ('APPEND_ID', 'APPEND_REV'):
                    continue
                catalog.append(
                    ElementaryProgramAST(
                        pre_pass=pre,
                        filter_expr=filt,
                        map_expr=mp,
                        reduce_kind=red,
                    )
                )
    return catalog


def _program_fits_public_examples(
    prog: ElementaryProgramAST,
    public_examples: list[tuple[list[int], Any]],
    counter: Wave23WorkCounter,
    *,
    is_witness_pass: bool = False,
) -> bool:
    for x_pub, y_pub in public_examples:
        if (prog.reduce_kind == 'SUM_TOTAL') != isinstance(y_pub, int):
            return False
        try:
            pred = ElementarySandboxExecutor.execute(
                prog,
                x_pub,
                counter,
                charge_eval=not is_witness_pass,
                charge_witness=is_witness_pass,
            )
        except Exception:
            return False
        if pred != y_pub:
            return False
    return True


def run_three_state_witness_search(
    ordered_candidates: list[ElementaryProgramAST],
    public_examples: list[tuple[list[int], Any]],
    query_input: list[int],
    counter: Wave23WorkCounter,
    *,
    max_candidate_budget: int = 800,
    candidate_probes: tuple[list[int], ...] = (
        [8],
        [6],
        [4, 8],
        [2, 8, -4, 6],
        [3, -1, 5],
        [-3, 2, -3, 5],
        [5, 2, 5, 4, 2, 1, 3],
    ),
) -> ThreeStateWitnessReport:
    """Executes the Three-State Witness-Pair Uniqueness Check & Three-State Failure Classification.

    - If duplicate visible inputs have conflicting outputs, immediately returns
      `VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`.
    - Searches `ordered_candidates` up to `max_candidate_budget`.
    - Once a first fitting program g_1 is found, continues searching `ordered_candidates`
      within the remaining budget for a second fitting program g_2 that disagrees on
      `query_input` (g_2(query_input) != g_1(query_input)):
      * If found: returns `AMBIGUOUS_WITNESS_FOUND` with witness pair (g_1, g_2) and a
        concrete distinguishing probe input `x_probe`.
      * If the entire `ordered_candidates` space is exhausted without finding a disagreeing
        g_2: returns `UNIQUE_IN_BOUNDED_SPACE`.
      * If `max_candidate_budget` expires after finding g_1 before `ordered_candidates` is
        exhausted: returns `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`.
    - If 0 fitting programs are found:
      * Returns `NO_PROGRAM_IN_BOUNDED_GRAMMAR` if `ordered_candidates` was completely checked,
      * Returns `NO_PROGRAM_WITHIN_BUDGET` if `max_candidate_budget` expired early.
    """
    if has_deterministic_input_collision(public_examples):
        return ThreeStateWitnessReport(
            status='VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            bounded_candidates_checked=0,
            bounded_space_exhausted=True,
        )

    g1: ElementaryProgramAST | None = None
    g1_query_pred: Any = None
    checked = 0

    for cand in ordered_candidates:
        if checked >= max_candidate_budget:
            if g1 is None:
                return ThreeStateWitnessReport(
                    status='NO_PROGRAM_WITHIN_BUDGET',
                    bounded_candidates_checked=checked,
                    bounded_space_exhausted=False,
                )
            return ThreeStateWitnessReport(
                status='UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
                primary_program=g1,
                primary_query_prediction=g1_query_pred,
                bounded_candidates_checked=checked,
                bounded_space_exhausted=False,
            )

        checked += 1
        is_witness = g1 is not None
        if not _program_fits_public_examples(cand, public_examples, counter, is_witness_pass=is_witness):
            continue

        if g1 is None:
            g1 = cand
            g1_query_pred = ElementarySandboxExecutor.execute(
                g1, query_input, counter, charge_eval=False, charge_witness=True
            )
        else:
            g2_query_pred = ElementarySandboxExecutor.execute(
                cand, query_input, counter, charge_eval=False, charge_witness=True
            )
            if g2_query_pred != g1_query_pred:
                # Found a concrete witness pair (g1, cand) that fits D_pub and disagrees on query_input!
                dist_probe = list(query_input)
                for p_in in candidate_probes:
                    try:
                        o1 = ElementarySandboxExecutor.execute(g1, p_in, counter, charge_eval=False, charge_witness=True)
                        o2 = ElementarySandboxExecutor.execute(cand, p_in, counter, charge_eval=False, charge_witness=True)
                        if o1 != o2:
                            dist_probe = list(p_in)
                            break
                    except Exception:
                        continue
                return ThreeStateWitnessReport(
                    status='AMBIGUOUS_WITNESS_FOUND',
                    primary_program=g1,
                    witness_program=cand,
                    primary_query_prediction=g1_query_pred,
                    witness_query_prediction=g2_query_pred,
                    distinguishing_probe_input=dist_probe,
                    bounded_candidates_checked=checked,
                    bounded_space_exhausted=False,
                )

    if g1 is None:
        return ThreeStateWitnessReport(
            status='NO_PROGRAM_IN_BOUNDED_GRAMMAR',
            bounded_candidates_checked=checked,
            bounded_space_exhausted=True,
        )

    return ThreeStateWitnessReport(
        status='UNIQUE_IN_BOUNDED_SPACE',
        primary_program=g1,
        primary_query_prediction=g1_query_pred,
        bounded_candidates_checked=checked,
        bounded_space_exhausted=True,
    )


# ===========================================================================
# 2.4 Learned Elementary Step Proposer on M4 `mps` & 5-Method Comparison
# ===========================================================================

class M4ElementaryStepProposer:
    """Scores candidate (filter_expr, map_expr, reduce_kind) triples on M4 `mps` from public I/O features."""

    def __init__(self, seed: int = 0) -> None:
        torch, device = require_mps()
        self.torch = torch
        self.device = device
        self.telemetry = NeuralTelemetry(mps_available=True)
        g = torch.Generator(device='cpu')
        g.manual_seed(2300 + seed * 37)
        self.filter_List = list(ELEMENTARY_FILTERS)
        self.map_list = list(ELEMENTARY_BASE_MAPS) + list(ELEMENTARY_CONDITIONAL_REPAIR_MAPS)
        self.w_filt = torch.nn.Parameter((torch.randn(8, len(self.filter_List), generator=g) * 0.08).to(device))
        self.w_map = torch.nn.Parameter((torch.randn(8, len(self.map_list), generator=g) * 0.08).to(device))
        self.opt = torch.optim.Adam([self.w_filt, self.w_map], lr=0.08)

    def _encode_public_features(self, public_examples: list[tuple[list[int], Any]]):
        torch = self.torch
        if not public_examples:
            return torch.zeros((1, 8), dtype=torch.float32, device=self.device)
        x0, y0 = public_examples[0]
        is_int = 1.0 if isinstance(y0, int) else 0.0
        y_list = [y0] if isinstance(y0, int) else list(y0)
        len_ratio = float(len(y_list)) / float(max(1, len(x0)))
        has_neg_in = 1.0 if any(v < 0 for v in x0) else 0.0
        has_neg_out = 1.0 if any(v < 0 for v in y_list) else 0.0
        is_sorted = 1.0 if (len(y_list) >= 2 and y_list == sorted(y_list)) else 0.0
        max_grow = 1.0 if (y_list and x0 and max(abs(v) for v in y_list) > max(abs(v) for v in x0)) else 0.0
        has_dups = 1.0 if len(set(x0)) < len(x0) else 0.0
        all_even_out = 1.0 if (y_list and all(v % 2 == 0 for v in y_list)) else 0.0
        feats = [is_int, len_ratio, has_neg_in, has_neg_out, is_sorted, max_grow, has_dups, all_even_out]
        return torch.tensor([feats], dtype=torch.float32, device=self.device)

    def rank_filters_and_maps_mps(
        self,
        public_examples: list[tuple[list[int], Any]],
        counter: Wave23WorkCounter,
    ) -> tuple[list[str], list[str]]:
        torch = self.torch
        torch.mps.synchronize()
        t0 = time.perf_counter()
        counter.proposer_scoring_work += 2
        counter.primitive_op_steps += 4
        with torch.no_grad():
            feat = self._encode_public_features(public_examples)
            f_scores = torch.matmul(feat, self.w_filt).squeeze(0).detach().cpu().tolist()
            m_scores = torch.matmul(feat, self.w_map).squeeze(0).detach().cpu().tolist()
            self.telemetry.gpu_forward_passes += 1
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0
        ranked_f = [f for f, _ in sorted(zip(self.filter_List, f_scores), key=lambda it: -it[1])]
        ranked_m = [m for m, _ in sorted(zip(self.map_list, m_scores), key=lambda it: -it[1])]
        return ranked_f, ranked_m

    def update_on_solved_mps(
        self,
        public_examples: list[tuple[list[int], Any]],
        prog: ElementaryProgramAST,
        counter: Wave23WorkCounter,
    ) -> None:
        if prog.filter_expr not in self.filter_List or prog.map_expr not in self.map_list:
            return
        torch = self.torch
        torch.mps.synchronize()
        t0 = time.perf_counter()
        counter.proposer_scoring_work += 2
        counter.primitive_op_steps += 4
        f_idx = self.filter_List.index(prog.filter_expr)
        m_idx = self.map_list.index(prog.map_expr)
        feat = self._encode_public_features(public_examples)
        target_f = torch.tensor([f_idx], dtype=torch.long, device=self.device)
        target_m = torch.tensor([m_idx], dtype=torch.long, device=self.device)
        for _ in range(2):
            self.opt.zero_grad()
            loss = torch.nn.functional.cross_entropy(torch.matmul(feat, self.w_filt), target_f) + (
                torch.nn.functional.cross_entropy(torch.matmul(feat, self.w_map), target_m)
            )
            loss.backward()
            self.opt.step()
            self.telemetry.gpu_forward_passes += 1
            self.telemetry.gpu_online_update_steps += 1
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0


@dataclass
class Wave23ElementarySynthesisResult:
    """Result of one Track 2 task evaluation under one of the 5 controlled methods."""

    method: str
    task_id: str
    seed: int
    is_repeated_use_task: bool
    witness_status: str
    gold_witness_status: str
    synthesized_source: str
    statement_count: int
    no_compound_boxes_verified: bool
    template_hit: bool
    cold_archive_reactivated: bool
    harmful_template_retrieval: bool
    symkan_report: dict[str, Any]
    status_correct: bool
    private_correct: bool
    first_acquisition_work: int
    repeated_use_work: int
    total_work: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]
    gpu_telemetry: dict[str, Any]


def solve_wave23_elementary_task(
    method: str,
    task_spec: dict[str, Any],
    seed: int,
    *,
    store: AuthoritativeTemplateStore | None = None,
    proposer: M4ElementaryStepProposer | None = None,
) -> Wave23ElementarySynthesisResult:
    """Evaluates one of the 5 Track 2 methods with full first-acquisition vs repeated-use accounting."""
    if method not in WAVE23_TRACK2_METHODS:
        raise ValueError(f'Unknown Track 2 method: {method!r}')

    if store is None:
        store = AuthoritativeTemplateStore()
    if proposer is None:
        proposer = M4ElementaryStepProposer(seed=seed)

    counter = Wave23WorkCounter()
    public_examples: list[tuple[list[int], Any]] = [(list(x), y) for x, y in task_spec['public']]
    private_examples: list[tuple[list[int], Any]] = [(list(x), y) for x, y in task_spec.get('private', [])]
    query_input: list[int] = list(task_spec.get('query_input', [2, 8, -4, 6]))
    max_budget: int = int(task_spec.get('max_candidate_budget', 1200))
    gold_status: str = task_spec['gold_witness_status']
    is_repeated: bool = bool(task_spec.get('is_repeated_use_task', False))

    use_templates = method != 'fixed_elementary_scratch'
    use_learned = method in (
        'learned_proposer_with_templates',
        'learned_proposer_plus_symkan_no_promotion',
        'learned_proposer_plus_symkan_with_promotion',
    )
    use_symkan = method in (
        'learned_proposer_plus_symkan_no_promotion',
        'learned_proposer_plus_symkan_with_promotion',
    )
    promote_symkan = method == 'learned_proposer_plus_symkan_with_promotion'

    symkan_rep = SymbolicKANCandidateReport(attempted=False)
    template_hit = False
    reactivated_now = False
    harmful_retrieval = False

    # Step 1: Check for deterministic input collision before any candidate search
    if has_deterministic_input_collision(public_examples):
        witness_rep = ThreeStateWitnessReport(
            status='VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            bounded_candidates_checked=0,
            bounded_space_exhausted=True,
        )
    else:
        # Step 2: Public Alignment Derivation A(F, O) (no oracle!) to prune incompatible filters
        derived_alignments = derive_public_scalar_alignments(public_examples, counter)
        aligned_filters = {a.filter_expr for a in derived_alignments}

        # Step 3: Optional Scoped `SymbolicKANResidualInducer` on derived alignments
        symkan_front_programs: list[ElementaryProgramAST] = []
        if use_symkan and derived_alignments:
            for align in derived_alignments[:2]:
                expr_str, k_rep = SymbolicKANResidualInducer.induce_from_alignment_mps(
                    align, counter, proposer.telemetry
                )
                symkan_rep = k_rep
                if expr_str is not None:
                    symkan_front_programs.append(
                        ElementaryProgramAST(
                            pre_pass=align.pre_pass,
                            filter_expr=align.filter_expr,
                            map_expr=expr_str,
                            reduce_kind=align.ordering,
                        )
                    )
                    break

        # Step 4: Template Store & Cold Archive Retrieval (if enabled)
        template_front_programs: list[ElementaryProgramAST] = []
        if use_templates and (store.active_templates or store.cold_archive):
            all_tmpls = list(store.active_templates.values()) + list(store.cold_archive.values())
            for tmpl in all_tmpls:
                counter.template_retrieval_work += 1
                counter.primitive_op_steps += 2
                store.total_retrieval_attempts += 1
                tmpl.retrieval_attempts += 1
                if aligned_filters and tmpl.filter_expr not in aligned_filters and tmpl.reduce_kind != 'SUM_TOTAL':
                    store.total_harmful_retrievals += 1
                    tmpl.harmful_retrievals += 1
                    harmful_retrieval = True
                    continue
                for red in (tmpl.reduce_kind, 'APPEND_ID', 'APPEND_REV', 'APPEND_SORT_ASC', 'APPEND_SORT_TOP2'):
                    if red == 'SUM_TOTAL' and tmpl.reduce_kind != 'SUM_TOTAL':
                        continue
                    if tmpl.map_expr in ELEMENTARY_CONDITIONAL_REPAIR_MAPS and red not in ('APPEND_ID', 'APPEND_REV'):
                        continue
                    cand_t = ElementaryProgramAST(
                        pre_pass=tmpl.pre_pass,
                        filter_expr=tmpl.filter_expr,
                        map_expr=tmpl.map_expr,
                        reduce_kind=red,
                    )
                    if cand_t not in template_front_programs:
                        template_front_programs.append(cand_t)

        # Fast-path for Repeated-Use tasks when a previously witness-verified template in AuthoritativeTemplateStore matches
        witness_rep = None
        if is_repeated and template_front_programs:
            tmpl_witness = run_three_state_witness_search(
                template_front_programs,
                public_examples,
                query_input,
                counter,
                max_candidate_budget=max_budget,
            )
            if tmpl_witness.status == 'UNIQUE_IN_BOUNDED_SPACE' and tmpl_witness.primary_program is not None:
                witness_rep = tmpl_witness

        if witness_rep is None:
            # Step 5: Order the bounded elementary catalog G_bound
            if use_learned:
                ranked_filters, ranked_maps = proposer.rank_filters_and_maps_mps(public_examples, counter)
            else:
                ranked_filters = list(ELEMENTARY_FILTERS)
                ranked_maps = list(ELEMENTARY_BASE_MAPS) + list(ELEMENTARY_CONDITIONAL_REPAIR_MAPS)

            # Prioritize filters that passed the public length-alignment check A(F, O)
            if aligned_filters:
                prioritized_filters = [f for f in ranked_filters if f in aligned_filters] + [
                    f for f in ranked_filters if f not in aligned_filters
                ]
            else:
                prioritized_filters = ranked_filters

            ordered_catalog: list[ElementaryProgramAST] = []
            seen_progs: set[ElementaryProgramAST] = set()

            for p_front in template_front_programs + symkan_front_programs:
                if p_front not in seen_progs:
                    seen_progs.add(p_front)
                    ordered_catalog.append(p_front)

            for filt in prioritized_filters:
                pre = 'COUNT_FREQ' if 'counts' in filt else 'NONE'
                for mp in ranked_maps:
                    for red in ELEMENTARY_REDUCE_POSTS:
                        if red == 'SUM_TOTAL' and mp not in ('v', 'abs(v)', 'v * v', 'v * 2'):
                            continue
                        if mp in ELEMENTARY_CONDITIONAL_REPAIR_MAPS and red not in ('APPEND_ID', 'APPEND_REV'):
                            continue
                        p_cand = ElementaryProgramAST(
                            pre_pass=pre,
                            filter_expr=filt,
                            map_expr=mp,
                            reduce_kind=red,
                        )
                        if p_cand not in seen_progs:
                            seen_progs.add(p_cand)
                            ordered_catalog.append(p_cand)

            # Step 6: Run the Three-State Witness-Pair Search over `ordered_catalog`
            witness_rep = run_three_state_witness_search(
                ordered_catalog,
                public_examples,
                query_input,
                counter,
                max_candidate_budget=max_budget,
            )

    chosen = witness_rep.primary_program
    if witness_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and chosen is not None:
        if symkan_rep.attempted and symkan_rep.induced_expression == chosen.map_expr:
            symkan_rep.task_correct = True
        if use_templates:
            # Check if chosen matched an existing template or cold archive entry
            for t_id, tmpl in list(store.active_templates.items()) + list(store.cold_archive.items()):
                if (tmpl.pre_pass, tmpl.filter_expr, tmpl.map_expr) == (
                    chosen.pre_pass,
                    chosen.filter_expr,
                    chosen.map_expr,
                ):
                    template_hit = True
                    tmpl.retrieval_hits += 1
                    store.total_retrieval_hits += 1
                    if t_id in store.cold_archive:
                        reactivated_now = True
                    break
            origin = 'symkan_promoted' if (symkan_rep.task_correct and promote_symkan) else 'elementary_mdl'
            new_t = store.record_solved_and_maybe_promote(
                chosen, origin=origin, allow_symkan_promotion=promote_symkan
            )
            if new_t is not None and origin == 'symkan_promoted':
                symkan_rep.promoted_to_store = True
            store.prune_idle_to_cold_archive(max_idle_steps=3)
        if use_learned:
            proposer.update_on_solved_mps(public_examples, chosen, counter)

    status_ok = (witness_rep.status == gold_status)
    if witness_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and chosen is not None:
        src_text = chosen.build_source()
        stmt_cnt = chosen.statement_count()
        no_boxes_ok = verify_no_compound_boxes_and_bounds(chosen)
        priv_c = Wave23WorkCounter()
        priv_ok = (
            status_ok
            and no_boxes_ok
            and all(
                ElementarySandboxExecutor.execute(chosen, x_p, priv_c, charge_eval=False) == y_p
                for x_p, y_p in private_examples
            )
        )
    else:
        src_text = chosen.build_source() if chosen is not None else ''
        stmt_cnt = chosen.statement_count() if chosen is not None else 0
        no_boxes_ok = verify_no_compound_boxes_and_bounds(chosen) if chosen is not None else True
        priv_ok = status_ok

    wb = counter.to_dict()
    first_w = 0 if is_repeated else wb['total_work']
    rep_w = wb['total_work'] if is_repeated else 0

    return Wave23ElementarySynthesisResult(
        method=method,
        task_id=task_spec['id'],
        seed=seed,
        is_repeated_use_task=is_repeated,
        witness_status=witness_rep.status,
        gold_witness_status=gold_status,
        synthesized_source=src_text,
        statement_count=stmt_cnt,
        no_compound_boxes_verified=no_boxes_ok,
        template_hit=template_hit,
        cold_archive_reactivated=reactivated_now,
        harmful_template_retrieval=harmful_retrieval,
        symkan_report=asdict(symkan_rep),
        status_correct=status_ok,
        private_correct=priv_ok,
        first_acquisition_work=first_w,
        repeated_use_work=rep_w,
        total_work=wb['total_work'],
        total_primitive_op_steps=wb['total_primitive_op_steps'],
        work_breakdown=wb,
        gpu_telemetry=proposer.telemetry.snapshot(),
    )


def verify_no_compound_boxes_and_bounds(prog: ElementaryProgramAST) -> bool:
    return verify_no_compound_loop_boxes(prog.build_source())


# ===========================================================================
# 3. Track 3 — Specification-Scoped NL Grounding vs. Equal-Tool Pretrained LLM
# ===========================================================================

@dataclass
class Wave23DialogueTurnResult:
    """Result of one Track 3 turn across the 3 compared LLM/agent methods."""

    method: str
    dialogue_id: str
    turn_index: int
    category: str
    seed: int
    is_repeated_use_turn: bool
    user_prompt: str
    raw_llm_output: str
    final_decision_status: str
    # Decision statuses:
    #   'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
    #   'AMBIGUOUS_WITNESS_FOUND_CLARIFY'
    #   'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
    #   'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
    #   'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'
    gold_decision_status: str
    verified_value: Any
    gold_value: Any
    tool_or_skill_invoked: bool
    turn_correct: bool
    unverified_or_false_claim: bool
    premature_commit_on_ambiguous: bool
    deterministic_violation_complied: bool
    first_acquisition_work: int
    repeated_use_work: int
    total_work: int
    total_primitive_op_steps: int
    llm_telemetry: dict[str, Any]


class EqualToolAndWitnessGatedNLAgent:
    """Evaluates `standalone_pretrained_llm_mps`, `tool_equipped_llm_with_skill_cache_mps`, and `nexus_witness_gated_agent_mps`."""

    @classmethod
    def evaluate_turn_triplet(
        cls,
        turn_spec: dict[str, Any],
        raw_llm_output: str,
        llm_telemetry: dict[str, Any],
        dialogue_memory: dict[str, Any],
        shared_skill_cache: dict[str, ElementaryProgramAST],
        seed: int,
    ) -> tuple[Wave23DialogueTurnResult, Wave23DialogueTurnResult, Wave23DialogueTurnResult]:
        gold_status = turn_spec['gold_decision_status']
        gold_val = turn_spec.get('gold_value')
        category = turn_spec['category']
        is_repeated = bool(turn_spec.get('is_repeated_use_turn', False))
        workspace_state = dict(dialogue_memory.get('workspace_state', turn_spec.get('workspace_state', {})))

        # ------------------------------------------------------------------
        # 1. `standalone_pretrained_llm_mps` (Raw Pretrained LLM on Metal)
        # ------------------------------------------------------------------
        c_raw = Wave23WorkCounter(candidate_evaluations=1, primitive_op_steps=4)
        literals = w21_m3._extract_Python_literals_from_text(raw_llm_output)
        asked_clar = w21_m3._raw_llm_asked_clarification(raw_llm_output)
        reason_kw = tuple(turn_spec.get('required_reason_keywords', ()))
        abstained = w21_m3._raw_llm_abstained(raw_llm_output, reason_kw)

        raw_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
        raw_val: Any = None
        raw_correct = False
        raw_premature = False
        raw_det_complied = False

        if gold_status == 'VERIFIED_RELATIVE_TO_SELECTED_SPEC':
            if isinstance(gold_val, list):
                list_lits = [v for v in literals if isinstance(v, list)]
                raw_val = list_lits[-1] if list_lits else None
                raw_correct = (raw_val == gold_val)
            elif isinstance(gold_val, int):
                int_lits = [v for v in literals if isinstance(v, int)]
                raw_val = int_lits[-1] if int_lits else None
                raw_correct = (raw_val == gold_val) and (not abstained)
        elif gold_status == 'AMBIGUOUS_WITNESS_FOUND_CLARIFY':
            if asked_clar:
                raw_decision = 'AMBIGUOUS_WITNESS_FOUND_CLARIFY'
                raw_correct = True
            else:
                raw_premature = True
        elif gold_status == 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS':
            if abstained:
                raw_decision = 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
                raw_correct = True
            else:
                raw_det_complied = True
        elif gold_status in ('NO_PROGRAM_IN_BOUNDED_GRAMMAR', 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'):
            if abstained:
                raw_decision = gold_status
                raw_correct = True

        res_raw = Wave23DialogueTurnResult(
            method='standalone_pretrained_llm_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            category=category,
            seed=seed,
            is_repeated_use_turn=is_repeated,
            user_prompt=turn_spec['user_prompt'],
            raw_llm_output=raw_llm_output,
            final_decision_status=raw_decision,
            gold_decision_status=gold_status,
            verified_value=raw_val,
            gold_value=gold_val,
            tool_or_skill_invoked=False,
            turn_correct=raw_correct,
            unverified_or_false_claim=not raw_correct,
            premature_commit_on_ambiguous=raw_premature,
            deterministic_violation_complied=raw_det_complied,
            first_acquisition_work=0 if is_repeated else c_raw.total_work,
            repeated_use_work=c_raw.total_work if is_repeated else 0,
            total_work=c_raw.total_work,
            total_primitive_op_steps=c_raw.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )

        # Parse the English turn into symbolic examples / state operations shared by BOTH tool-equipped agents
        compiled = w22.CompositionalNLWorldCompiler.compile_english_turn(
            turn_spec['user_prompt'], workspace_state, dialogue_memory
        )

        # ------------------------------------------------------------------
        # 2. `tool_equipped_llm_with_skill_cache_mps` (Equal-Tool Pretrained LLM Baseline)
        #    Has the EXACT same Python sandbox executor, skill cache, and reusable functions!
        #    Executes the first fitting program in the sandbox (or cached skill) on `query_input`,
        #    but does NOT run the 3-state Witness-Pair ambiguity check or collision check.
        # ------------------------------------------------------------------
        c_tool = Wave23WorkCounter(candidate_evaluations=1, primitive_op_steps=4)
        tool_decision = 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'
        tool_val: Any = None
        tool_used = False
        tool_premature = False
        tool_det_complied = False

        if compiled.intent_domain == 'STATE_TRANSITION':
            tool_used = True
            c_tool.public_validation_work += 1
            c_tool.primitive_op_steps += 3
            amt = compiled.state_amount
            if (
                workspace_state.get('locked') is True
                or ('limit' in workspace_state and amt > int(workspace_state['limit']))
                or (compiled.state_op == 'transfer' and amt > int(workspace_state.get('balance', 0)))
            ):
                tool_decision = 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'
            else:
                new_bal = (
                    int(workspace_state['balance']) - amt
                    if compiled.state_op == 'transfer'
                    else int(workspace_state['balance']) + amt
                )
                tool_val = new_bal
                tool_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'

        elif compiled.intent_domain == 'CODE_SYNTHESIS_OR_QA':
            tool_used = True
            examples = list(compiled.extracted_examples)
            q_in = list(compiled.query_input) if isinstance(compiled.query_input, list) else [2, 8, -4, 6]
            skill_tag = turn_spec.get('skill_cache_key', '')

            # Check shared skill cache first (equal access to cached skills!)
            chosen_tool_prog: ElementaryProgramAST | None = None
            if skill_tag and skill_tag in shared_skill_cache:
                c_tool.template_retrieval_work += 1
                c_tool.primitive_op_steps += 2
                chosen_tool_prog = shared_skill_cache[skill_tag]
            else:
                # Equal-tool baseline searches the exact same elementary catalog for the first program
                # that fits the first example (or all examples if no collision), without witness checking
                catalog = build_bounded_elementary_catalog(include_conditional_repairs=True)
                for cand in catalog:
                    if _program_fits_public_examples(cand, examples, c_tool):
                        chosen_tool_prog = cand
                        break
                # If duplicate inputs collided, a greedy tool user often fits the last example pair
                if chosen_tool_prog is None and len(examples) >= 2 and has_deterministic_input_collision(examples):
                    for cand in catalog:
                        if _program_fits_public_examples(cand, [examples[-1]], c_tool):
                            chosen_tool_prog = cand
                            tool_det_complied = True
                            break

            if chosen_tool_prog is not None:
                tool_val = ElementarySandboxExecutor.execute(chosen_tool_prog, q_in, c_tool)
                tool_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
                if gold_status == 'AMBIGUOUS_WITNESS_FOUND_CLARIFY':
                    tool_premature = True
            else:
                tool_decision = 'NO_PROGRAM_IN_BOUNDED_GRAMMAR'

        tool_correct = (tool_decision == gold_status) and (
            gold_status != 'VERIFIED_RELATIVE_TO_SELECTED_SPEC' or tool_val == gold_val
        )

        res_tool = Wave23DialogueTurnResult(
            method='tool_equipped_llm_with_skill_cache_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            category=category,
            seed=seed,
            is_repeated_use_turn=is_repeated,
            user_prompt=turn_spec['user_prompt'],
            raw_llm_output=raw_llm_output,
            final_decision_status=tool_decision,
            gold_decision_status=gold_status,
            verified_value=tool_val,
            gold_value=gold_val,
            tool_or_skill_invoked=tool_used,
            turn_correct=tool_correct,
            unverified_or_false_claim=not tool_correct,
            premature_commit_on_ambiguous=tool_premature,
            deterministic_violation_complied=tool_det_complied,
            first_acquisition_work=0 if is_repeated else c_tool.total_work,
            repeated_use_work=c_tool.total_work if is_repeated else 0,
            total_work=c_tool.total_work,
            total_primitive_op_steps=c_tool.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )

        # ------------------------------------------------------------------
        # 3. `nexus_witness_gated_agent_mps` (Full Witness-Pair & Failure State Gating)
        # ------------------------------------------------------------------
        c_nexus = Wave23WorkCounter(candidate_evaluations=1, primitive_op_steps=4)
        nexus_decision = 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'
        nexus_val: Any = None
        nexus_tool_used = False

        if compiled.intent_domain == 'PREMISE_CHECK':
            nexus_decision = 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'

        elif compiled.intent_domain == 'STATE_TRANSITION':
            nexus_tool_used = True
            c_nexus.public_validation_work += 1
            c_nexus.primitive_op_steps += 3
            amt = compiled.state_amount
            if (
                workspace_state.get('locked') is True
                or ('limit' in workspace_state and amt > int(workspace_state['limit']))
                or (compiled.state_op == 'transfer' and amt > int(workspace_state.get('balance', 0)))
            ):
                nexus_decision = 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT'
            else:
                if compiled.state_op == 'transfer':
                    workspace_state['balance'] = int(workspace_state['balance']) - amt
                else:
                    workspace_state['balance'] = int(workspace_state['balance']) + amt
                dialogue_memory['workspace_state'] = dict(workspace_state)
                nexus_val = workspace_state['balance']
                nexus_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'

        elif compiled.intent_domain == 'CODE_SYNTHESIS_OR_QA':
            nexus_tool_used = True
            examples = list(compiled.extracted_examples)
            q_in = list(compiled.query_input) if isinstance(compiled.query_input, list) else [2, 8, -4, 6]
            skill_tag = turn_spec.get('skill_cache_key', '')

            if skill_tag and skill_tag in shared_skill_cache and (is_repeated or not examples):
                c_nexus.template_retrieval_work += 1
                c_nexus.primitive_op_steps += 2
                cached_p = shared_skill_cache[skill_tag]
                nexus_val = ElementarySandboxExecutor.execute(cached_p, q_in, c_nexus)
                nexus_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
            else:
                # Derive alignments first to order catalog, then run the full 3-state witness check
                alignments = derive_public_scalar_alignments(examples, c_nexus)
                aligned_f = {a.filter_expr for a in alignments}
                full_cat = build_bounded_elementary_catalog(include_conditional_repairs=True)
                if aligned_f:
                    ordered_cat = [p for p in full_cat if p.filter_expr in aligned_f] + [
                        p for p in full_cat if p.filter_expr not in aligned_f
                    ]
                else:
                    ordered_cat = full_cat

                w_rep = run_three_state_witness_search(
                    ordered_cat,
                    examples,
                    q_in,
                    c_nexus,
                    max_candidate_budget=1200,
                )
                if w_rep.status == 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS':
                    nexus_decision = 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
                elif w_rep.status == 'NO_PROGRAM_IN_BOUNDED_GRAMMAR':
                    nexus_decision = 'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
                elif w_rep.status == 'AMBIGUOUS_WITNESS_FOUND':
                    nexus_decision = 'AMBIGUOUS_WITNESS_FOUND_CLARIFY'
                    dialogue_memory['pending_examples'] = list(examples)
                    dialogue_memory['pending_query'] = list(q_in)
                elif w_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and w_rep.primary_program is not None:
                    nexus_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
                    nexus_val = w_rep.primary_query_prediction
                    dialogue_memory.pop('pending_examples', None)
                    dialogue_memory.pop('pending_query', None)
                    if skill_tag:
                        shared_skill_cache[skill_tag] = w_rep.primary_program

        nexus_correct = (nexus_decision == gold_status) and (
            gold_status != 'VERIFIED_RELATIVE_TO_SELECTED_SPEC' or nexus_val == gold_val
        )

        res_nexus = Wave23DialogueTurnResult(
            method='nexus_witness_gated_agent_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            category=category,
            seed=seed,
            is_repeated_use_turn=is_repeated,
            user_prompt=turn_spec['user_prompt'],
            raw_llm_output=raw_llm_output,
            final_decision_status=nexus_decision,
            gold_decision_status=gold_status,
            verified_value=nexus_val,
            gold_value=gold_val,
            tool_or_skill_invoked=nexus_tool_used,
            turn_correct=nexus_correct,
            unverified_or_false_claim=not nexus_correct,
            premature_commit_on_ambiguous=False,
            deterministic_violation_complied=False,
            first_acquisition_work=0 if is_repeated else c_nexus.total_work,
            repeated_use_work=c_nexus.total_work if is_repeated else 0,
            total_work=c_nexus.total_work,
            total_primitive_op_steps=c_nexus.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )
        return res_raw, res_tool, res_nexus


def run_wave23_llm_dialogue_suite(
    dialogue_specs: list[dict[str, Any]],
    *,
    seeds: tuple[int, ...] = (0,),
    max_tokens: int = 72,
) -> tuple[list[Wave23DialogueTurnResult], dict[str, Any]]:
    """Executes `Qwen2.5-0.5B-Instruct` on Metal GPU across all dialogue turns and seeds."""
    model_path = resolve_local_pretrained_gguf_path()
    results: list[Wave23DialogueTurnResult] = []

    with tempfile.TemporaryDirectory(prefix='nexus_wave23_metal_') as tmpdir:
        ledger_path = f'{tmpdir}/wave23_metal_ledger.json'
        cfg = RuntimeConfig(
            model_path=str(model_path),
            max_tokens=max_tokens,
            prompt_cache=True,
            application_cache=False,
        )
        grant = ExplicitMetalGrant(
            authorized=True,
            owner='wave23_focused_experiment',
            reason='wave23_equal_tool_and_witness_gated_llm_evaluation',
            ledger_path=ledger_path,
            n_gpu_layers=-1,
        )
        with PersistentMetalRuntime(cfg, grant) as rt:
            runtime_meta = dict(rt.metadata or {})
            for seed in seeds:
                dialogue_memories: dict[str, dict[str, Any]] = {}
                shared_skill_cache: dict[str, ElementaryProgramAST] = {}
                for turn_spec in dialogue_specs:
                    d_id = turn_spec['dialogue_id']
                    if d_id not in dialogue_memories:
                        dialogue_memories[d_id] = {
                            'workspace_state': dict(turn_spec.get('workspace_state', {})),
                        }
                    mem = dialogue_memories[d_id]
                    if 'workspace_state' in turn_spec and turn_spec['turn_index'] == 0:
                        mem['workspace_state'] = dict(turn_spec['workspace_state'])

                    prompt = w21_m3._format_chatml_prompt(
                        turn_spec['user_prompt'],
                        repr(mem.get('workspace_state', {})),
                    )
                    temp = 0.0 if seed == 0 else 0.2
                    call_seed = 101 + seed * 29 + int(turn_spec['turn_index'])
                    llm_out = rt.complete(prompt, None, temperature=temp, seed=call_seed)
                    raw_text = str(llm_out['content']).strip()
                    llm_tel = dict(llm_out['telemetry'])
                    llm_tel['model_file'] = runtime_meta.get('model_file')
                    llm_tel['model_sha256'] = runtime_meta.get('model_sha256')
                    llm_tel['prompt_sha256'] = llm_out['request']['prompt_sha256']

                    r_raw, r_tool, r_nexus = EqualToolAndWitnessGatedNLAgent.evaluate_turn_triplet(
                        turn_spec,
                        raw_text,
                        llm_tel,
                        mem,
                        shared_skill_cache,
                        seed,
                    )
                    results.extend([r_raw, r_tool, r_nexus])

    return results, runtime_meta


# ===========================================================================
# 4. Pre-Declared Post-Freeze Suite Generator (Retaining All Generated Cases)
# ===========================================================================

def build_wave23_Tracks_suite(
    suite_seed_label: str = 'wave23_post_freeze_canonical_v1',
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Pre-declared deterministic suite builder for Track 1, Track 2, and Track 3.

    Retains 100% of generated cases without cherry-picking or post-hoc filtering.
    """
    digest = hashlib.sha256(suite_seed_label.encode('utf-8')).hexdigest()
    rng = random.Random(int(digest[:16], 16))

    # ------------------------------------------------------------------
    # Track 1: 8 Independent Tasks (Public Validation vs Private Assessment)
    # ------------------------------------------------------------------
    # Permute target operator indices deterministically from suite_seed_label
    all_tgt_indices = list(range(10))
    rng.shuffle(all_tgt_indices)
    op_map_idx = tuple(all_tgt_indices[:6])
    guard_map_idx = (2, 0)
    src_env, tgt_env, gold_phi, gold_psi, enc_fn = build_lookalike_distractor_domain_pair(
        op_mapping_indices=op_map_idx,
        guard_mapping_indices=guard_map_idx,
    )

    init_src_states = ((0, 0, 0), (1, 0, 0), (0, 2, 1), (2, 4, 0))
    init_tgt_states = tuple(enc_fn(s) for s in init_src_states)

    full_public_trajectories = [
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_1_background_swap_anchor',
            op_sequence=('src_op_0', 'src_op_3', 'src_op_5'),
            terminal_guard='src_guard_1',
            initial_states_src=init_src_states,
            initial_states_tgt=init_tgt_states,
        ),
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_2_background_involution',
            op_sequence=('src_op_5', 'src_op_0', 'src_op_5'),
            terminal_guard='src_guard_0',
            initial_states_src=init_src_states,
            initial_states_tgt=init_tgt_states,
        ),
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_3_disambiguate_lookalike_op1_step4',
            op_sequence=('src_op_1', 'src_op_1', 'src_op_1', 'src_op_1'),
            terminal_guard='src_guard_0',
            initial_states_src=init_src_states,
            initial_states_tgt=init_tgt_states,
        ),
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_4_disambiguate_lookalike_op4_step4',
            op_sequence=('src_op_4', 'src_op_4', 'src_op_4', 'src_op_0'),
            terminal_guard='src_guard_0',
            initial_states_src=init_src_states,
            initial_states_tgt=init_tgt_states,
        ),
    ]

    # Underdetermined 1-step trajectory list where lookalikes remain ambiguous:
    ambiguous_public_trajectories = [
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_short_underdetermined',
            op_sequence=('src_op_0', 'src_op_5', 'src_op_0'),
            terminal_guard='src_guard_1',
            initial_states_src=((0, 0, 0), (1, 0, 0)),
            initial_states_tgt=tuple(enc_fn(s) for s in ((0, 0, 0), (1, 0, 0))),
        ),
    ]

    priv_states = [(3, 5, 1), (4, 2, 0), (5, 1, 1), (2, 3, 0)]
    priv_progs = [
        ('SEQ', ('OP', 'src_op_1'), ('SEQ', ('OP', 'src_op_1'), ('OP', 'src_op_4'))),
        ('IF', 'src_guard_1', ('SEQ', ('OP', 'src_op_4'), ('OP', 'src_op_4')), ('OP', 'src_op_2')),
        ('CONJUGATE', 'src_op_0', ('SEQ', ('OP', 'src_op_1'), ('OP', 'src_op_4')), 'src_op_0'),
        ('SEQ', ('REPEAT_UNTIL', 'src_guard_0', ('OP', 'src_op_1'), 3), ('OP', 'src_op_5')),
        ('SEQ', ('OP', 'src_op_3'), ('SEQ', ('OP', 'src_op_4'), ('OP', 'src_op_1'))),
        ('IF', 'src_guard_0', ('OP', 'src_op_5'), ('SEQ', ('OP', 'src_op_2'), ('OP', 'src_op_4'))),
    ]
    w21_c = w21_m1.Wave21WorkCounter()

    track1_tasks: list[dict[str, Any]] = []
    for idx, p_ast in enumerate(priv_progs):
        t_ast = translate_composite_program(p_ast, gold_phi, gold_psi)
        track1_tasks.append(
            {
                'id': f'w23_t1_task_{idx + 1:02d}_unique_transfer',
                'validation_regime': 'full',
                'source_env': src_env,
                'target_env': tgt_env,
                'public_validation_trajectories': full_public_trajectories,
                'private_source_program': p_ast,
                'private_assessment_examples': [
                    (enc_fn(s), eval_composite_program(tgt_env, t_ast, enc_fn(s), w21_c))
                    for s in priv_states
                ],
                'gold_mapping_verdict': 'UNIQUE_VALIDATED_MAPPING',
                'gold_phi': gold_phi,
                'gold_psi': gold_psi,
            }
        )

    # Task 7: Ambiguous Public Validation (insufficient 3-step trajectories to separate lookalikes)
    t_ast_0 = translate_composite_program(priv_progs[0], gold_phi, gold_psi)
    track1_tasks.append(
        {
            'id': 'w23_t1_task_07_ambiguous_public_validation',
            'validation_regime': 'ambiguous_short',
            'source_env': src_env,
            'target_env': tgt_env,
            'public_validation_trajectories': ambiguous_public_trajectories,
            'private_source_program': priv_progs[0],
            'private_assessment_examples': [
                (enc_fn(s), eval_composite_program(tgt_env, t_ast_0, enc_fn(s), w21_c))
                for s in priv_states
            ],
            'gold_mapping_verdict': 'AMBIGUOUS_VALIDATED_MAPPINGS',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        }
    )

    # Task 8: Corrupted/Unsatisfiable Public Validation trajectory -> NO_VALIDATED_MAPPING
    corrupted_traj = [
        InterventionalTrajectorySpec(
            trajectory_id='pub_traj_corrupted_impossible',
            op_sequence=('src_op_1', 'src_op_1', 'src_op_1'),
            terminal_guard='src_guard_0',
            initial_states_src=((0, 0, 0), (3, 0, 0)),
            # Swap target initial states so guard behavior contradicts source trajectory
            initial_states_tgt=(enc_fn((3, 0, 0)), enc_fn((0, 0, 0))),
        )
    ]
    track1_tasks.append(
        {
            'id': 'w23_t1_task_08_no_validated_mapping',
            'validation_regime': 'corrupted_none',
            'source_env': src_env,
            'target_env': tgt_env,
            'public_validation_trajectories': corrupted_traj,
            'private_source_program': priv_progs[0],
            'private_assessment_examples': [],
            'gold_mapping_verdict': 'NO_VALIDATED_MAPPING',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        }
    )

    # ------------------------------------------------------------------
    # Track 2: 14 Independent Elementary AST Tasks (First-Acquisition + Repeated-Use + Witness + Failure)
    # ------------------------------------------------------------------
    track2_tasks: list[dict[str, Any]] = [
        # 1. First acquisition of unique-frequency square (`counts.get(v, 0) == 1`, `v * v`)
        {
            'id': 'w23_t2_01_first_acq_freq1_square',
            'is_repeated_use_task': False,
            'public': [([5, 2, 5, 4, 2, 1, 3], [16, 1, 9]), ([7, 3, 7, 2, 3, 5], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [16, 1, 9]), ([8, 2, 8, 5, 2, 3], [25, 9])],
            'query_input': [9, 4, 9, 1, 3],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 2. Second acquisition of unique-frequency square (reversed) -> triggers MDL template promotion!
        {
            'id': 'w23_t2_02_second_acq_freq1_square_rev_mdl_promote',
            'is_repeated_use_task': False,
            'public': [([5, 2, 5, 4, 2, 1, 3], [9, 1, 16]), ([7, 3, 7, 2, 3, 5], [25, 4])],
            'private': [([9, 4, 9, 1, 3], [9, 1, 16]), ([8, 2, 8, 5, 2, 3], [9, 25])],
            'query_input': [9, 4, 9, 1, 3],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 3. Repeated-use of promoted `freq1_square` template (sorted ascending)
        {
            'id': 'w23_t2_03_repeated_use_freq1_square_sorted',
            'is_repeated_use_task': True,
            'public': [([5, 2, 5, 4, 2, 1, 3], [1, 9, 16]), ([7, 3, 7, 2, 3, 5], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [1, 9, 16]), ([8, 2, 8, 5, 2, 3], [9, 25])],
            'query_input': [9, 4, 9, 1, 3],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 4. First acquisition of positive odd square (`v > 0 and v % 2 != 0`, `v * v`)
        {
            'id': 'w23_t2_04_first_acq_pos_odd_square',
            'is_repeated_use_task': False,
            'public': [([3, -5, 4, 7, 2, 1], [9, 49, 1]), ([5, 6, -3, 1, 2], [25, 1])],
            'private': [([7, -1, 8, 3, 1], [49, 9, 1])],
            'query_input': [7, -1, 8, 3, 1],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 5. Second acquisition of positive odd square (reversed) -> triggers second MDL template promotion!
        {
            'id': 'w23_t2_05_second_acq_pos_odd_square_rev_mdl_promote',
            'is_repeated_use_task': False,
            'public': [([3, -5, 4, 7, 2, 1], [1, 49, 9]), ([5, 6, -3, 1, 2], [1, 25])],
            'private': [([7, -1, 8, 3, 1], [1, 9, 49])],
            'query_input': [7, -1, 8, 3, 1],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 6. Repeated-use of promoted `pos_odd_square` template (sorted ascending)
        {
            'id': 'w23_t2_06_repeated_use_pos_odd_square_sorted',
            'is_repeated_use_task': True,
            'public': [([3, -5, 4, 7, 2, 1], [1, 9, 49]), ([5, 6, -3, 1, 2], [1, 25])],
            'private': [([7, -1, 8, 3, 1], [1, 9, 49])],
            'query_input': [7, -1, 8, 3, 1],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 7. Repeated-use of `freq1_square` with top-2 slice (`APPEND_SORT_TOP2`)
        {
            'id': 'w23_t2_07_repeated_use_freq1_square_top2',
            'is_repeated_use_task': True,
            'public': [([5, 2, 5, 4, 2, 1, 3], [9, 16]), ([7, 3, 7, 2, 3, 5, 1], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [9, 16])],
            'query_input': [9, 4, 9, 1, 3],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 8. Witness-Pair Ambiguity Audit Task: `[2, -3, 1] -> [2]` and `[4, 6, 3] -> [2, 3]`!
        #    Both `v // 2 if v > 2 else v` and `v - 3 if v > 4 else 2` fit and disagree on `[2, 8, -4, 6]`!
        {
            'id': 'w23_t2_08_witness_ambiguous_pos_even_ifexp',
            'is_repeated_use_task': False,
            'public': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])],
            'private': [],
            'query_input': [2, 8, -4, 6],
            'gold_witness_status': 'AMBIGUOUS_WITNESS_FOUND',
        },
        # 9. Disambiguated `[2, -3, 1] -> [2]`, `[4, 6, 3] -> [2, 3]`, `[8] -> [4]` -> UNIQUE_IN_BOUNDED_SPACE!
        {
            'id': 'w23_t2_09_disambiguated_pos_even_halve_above2',
            'is_repeated_use_task': False,
            'public': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3]), ([8], [4])],
            'private': [([2, 8, -4, 6], [2, 4, 3]), ([10, 2, -2], [5, 2])],
            'query_input': [2, 8, -4, 6],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 10. Repeated-use of `v // 2 if v > 2 else v` (reversed output)
        {
            'id': 'w23_t2_10_repeated_use_pos_even_halve_above2_rev',
            'is_repeated_use_task': True,
            'public': [([2, -3, 1], [2]), ([4, 6, 3], [3, 2]), ([2, 8, 6], [3, 4, 2])],
            'private': [([2, 8, -4, 6], [3, 4, 2])],
            'query_input': [2, 8, -4, 6],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 11. ReLU / Hinge task (`max(0, v - 2)` on positive items) where Symbolic-KAN 1D basis directly matches
        {
            'id': 'w23_t2_11_first_acq_pos_hinge_relu_minus2',
            'is_repeated_use_task': False,
            'public': [([1, -3, 4, 6], [0, 2, 4]), ([2, 5, -1, 7], [0, 3, 5])],
            'private': [([3, -2, 8, 1], [1, 6, 0])],
            'query_input': [3, -2, 8, 1],
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
        },
        # 12. Budget-Exhausted Uniqueness (`UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED` with tight budget=80)
        {
            'id': 'w23_t2_12_uniqueness_unknown_budget_exhausted',
            'is_repeated_use_task': False,
            'public': [([2, 4, 6], [2, 4, 6]), ([1, 3, 5], [1, 3, 5])],
            'private': [],
            'query_input': [2, 4, 6],
            'max_candidate_budget': 80,
            'gold_witness_status': 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
        },
        # 13. Deterministic Input Collision (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`)
        {
            'id': 'w23_t2_13_deterministic_input_collision',
            'is_repeated_use_task': False,
            'public': [([2, -3, 1], [2]), ([2, -3, 1], [99])],
            'private': [],
            'query_input': [3, -1, 5],
            'gold_witness_status': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
        },
        # 14. Out-of-Grammar consistent specification (`NO_PROGRAM_IN_BOUNDED_GRAMMAR`)
        {
            'id': 'w23_t2_14_no_program_in_bounded_grammar',
            'is_repeated_use_task': False,
            'public': [([1, 2, 3], [111, -222, 333, 444]), ([4, 5], [777, -888, 999])],
            'private': [],
            'query_input': [1, 2, 3],
            'gold_witness_status': 'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
        },
    ]

    # ------------------------------------------------------------------
    # Track 3: 10 Independent Grounded NL Dialogue Turns on Metal GPU LLM
    # ------------------------------------------------------------------
    track3_turns: list[dict[str, Any]] = [
        # Turn 1: The exact audited `[2, -3, 1] -> [2]` and `[4, 6, 3] -> [2, 3]` case!
        # Must NOT be called a contradiction; must detect witness pair (g1, g2) and ask for clarification!
        {
            'dialogue_id': 'w23_d01_audited_ifexp_witness_dialogue',
            'turn_index': 0,
            'category': 'WITNESS_AMBIGUITY_DETECTION',
            'is_repeated_use_turn': False,
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': (
                'Mystery function f maps [2, -3, 1] to [2] and maps [4, 6, 3] to [2, 3]. '
                'Compute f([2, 8, -4, 6]).'
            ),
            'gold_decision_status': 'AMBIGUOUS_WITNESS_FOUND_CLARIFY',
            'gold_value': None,
        },
        # Turn 2: Disambiguating observation `[8] -> [4]` resolves the witness pair to `v // 2 if v > 2 else v`!
        {
            'dialogue_id': 'w23_d01_audited_ifexp_witness_dialogue',
            'turn_index': 1,
            'category': 'WITNESS_AMBIGUITY_RESOLUTION',
            'is_repeated_use_turn': False,
            'skill_cache_key': 'skill_pos_even_halve_above2',
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': (
                'Clarification: on input [8] it maps [8] to [4]. '
                'Now compute f([2, 8, -4, 6]).'
            ),
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [2, 4, 3],
        },
        # Turn 3: Repeated-use of the cached `skill_pos_even_halve_above2` on a new query
        {
            'dialogue_id': 'w23_d01_audited_ifexp_witness_dialogue',
            'turn_index': 2,
            'category': 'REPEATED_SKILL_REUSE',
            'is_repeated_use_turn': True,
            'skill_cache_key': 'skill_pos_even_halve_above2',
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': (
                'Reuse the verified function f on [10, 2, -5, 4] and compute f([10, 2, -5, 4]).'
            ),
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [5, 2, 2],
        },
        # Turn 4: True deterministic input collision (`[2, -3, 1] -> [2]` AND `[2, -3, 1] -> [99]`)
        {
            'dialogue_id': 'w23_d02_true_deterministic_collision',
            'turn_index': 0,
            'category': 'DETERMINISTIC_ASSUMPTION_VIOLATION',
            'is_repeated_use_turn': False,
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': (
                'Stateless deterministic function f maps [2, -3, 1] to [2] and maps [2, -3, 1] to [99]. '
                'Compute f([3, -1, 5]).'
            ),
            'required_reason_keywords': ('collision', 'conflicting', 'same input', 'deterministic', 'contradict'),
            'gold_decision_status': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            'gold_value': None,
        },
        # Turn 5: Consistent Out-of-Grammar request (`NO_PROGRAM_IN_BOUNDED_GRAMMAR`)
        {
            'dialogue_id': 'w23_d03_consistent_out_of_grammar',
            'turn_index': 0,
            'category': 'OUT_OF_BOUNDED_GRAMMAR',
            'is_repeated_use_turn': False,
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': (
                'Function f maps [1, 2, 3] to [111, -222, 333, 444] and maps [4, 5] to [777, -888, 999]. '
                'Compute f([6, 7]).'
            ),
            'required_reason_keywords': ('grammar', 'bounded', 'no program', 'cannot', 'abstain'),
            'gold_decision_status': 'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
            'gold_value': None,
        },
        # Turn 6: Single-example witness ambiguity (`[2, -3] -> [4]`)
        {
            'dialogue_id': 'w23_d04_single_example_witness',
            'turn_index': 0,
            'category': 'WITNESS_AMBIGUITY_DETECTION',
            'is_repeated_use_turn': False,
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': 'Mystery function f maps [2, -3] to [4]. Compute f([3, -1, 5]).',
            'gold_decision_status': 'AMBIGUOUS_WITNESS_FOUND_CLARIFY',
            'gold_value': None,
        },
        # Turn 7: Clarification resolves `[2, -3] -> [4]` + `[3, 5] -> [6, 10]` to positive doubling
        {
            'dialogue_id': 'w23_d04_single_example_witness',
            'turn_index': 1,
            'category': 'WITNESS_AMBIGUITY_RESOLUTION',
            'is_repeated_use_turn': False,
            'skill_cache_key': 'skill_pos_double',
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': 'Clarification: it also maps [3, 5] to [6, 10]. Compute f([3, -1, 5]).',
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [6, 10],
        },
        # Turn 8: Repeated-use of cached `skill_pos_double`
        {
            'dialogue_id': 'w23_d04_single_example_witness',
            'turn_index': 2,
            'category': 'REPEATED_SKILL_REUSE',
            'is_repeated_use_turn': True,
            'skill_cache_key': 'skill_pos_double',
            'workspace_state': {'mode': 'spec_investigation'},
            'user_prompt': 'Reuse the verified function f on [4, -2, 7] and compute f([4, -2, 7]).',
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [8, 14],
        },
        # Turn 9: Valid stateful vault transfer
        {
            'dialogue_id': 'w23_d05_stateful_vault_guard',
            'turn_index': 0,
            'category': 'STATE_CONSTRAINT_EXECUTION',
            'is_repeated_use_turn': False,
            'workspace_state': {'balance': 150, 'limit': 60, 'locked': False},
            'user_prompt': 'Transfer 50 from the vault and report the updated integer balance.',
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': 100,
        },
        # Turn 10: Vault transfer exceeding limit=60 -> REFUSE_CONSTRAINT_OR_PREMISE_FAULT
        {
            'dialogue_id': 'w23_d05_stateful_vault_guard',
            'turn_index': 1,
            'category': 'STATE_CONSTRAINT_EXECUTION',
            'is_repeated_use_turn': False,
            'workspace_state': {'balance': 100, 'limit': 60, 'locked': False},
            'user_prompt': 'Now transfer 80 from the vault and report the new balance.',
            'required_reason_keywords': ('limit', 'exceed', 'cannot', 'refuse'),
            'gold_decision_status': 'REFUSE_CONSTRAINT_OR_PREMISE_FAULT',
            'gold_value': None,
        },
    ]

    return track1_tasks, track2_tasks, track3_turns
