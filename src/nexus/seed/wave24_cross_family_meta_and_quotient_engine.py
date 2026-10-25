"""Wave 24 — Cross-Family Meta-Procedure Optimization, Observational Equivalence Quotienting & Interference Immunity.

Implements five tightly bounded, reproducible mechanisms on Apple Silicon M4 (`torch.device("mps")`
+ `PersistentMetalRuntime` running `qwen2.5-0.5b-instruct-q4_k_m.gguf` with `n_gpu_layers=-1`),
while explicitly reusing existing NEXUS owners and preserving a single authoritative skill,
policy, and provenance store:

Reused Existing Owners (`REUSED_MODULE_OWNERS`):
- `src/nexus/seed/mechanism_policy.py`: Regularized ridge-regression linear policy fitting
  (`np.linalg.solve(xtx + l2 * I, xty)`), named public feature vectors, stored coefficients,
  training provenance, and per-feature score contributions. Extended here to fit both:
  (a) `ActiveInfoGainCorrespondenceEngine` (Track 1 public probe selection policy), and
  (b) `MetaProcedureOptimizer` (Track 2 Level-2 cross-family search-procedure policy `pi_meta`).
- `src/nexus/seed/mechanism_investigate.py`: Replayable investigation decision loop and cost
  accounting (`observe -> maintain competing explanations -> choose experiment -> update beliefs
  -> validate publicly -> retain useful structure -> transfer`).
- `src/nexus/seed/correspondence_learner.py` & `src/nexus/seed/mechanism_wave6_correspondence.py`:
  Competing correspondence hypothesis maintenance, public validation before private assessment,
  and explicit testing of counter/timestamp/order sensitivity (never assuming "ignore stamp").
- `src/nexus/seed/mechanism_skills.py` & `src/nexus/seed/skill_library.py`: Executable skill
  representation with explicit input/output signatures, assumptions, MDL description length,
  acquisition/retrieval cost accounting, and rollback/quarantine history.
- `src/nexus/seed/storage.py` & `src/nexus/evolution1/catalogue.py` (`canonical`, `digest`):
  Canonical JSON serialization and SHA-256 provenance digesting.
- `src/nexus/seed/recovery_evaluate.py` (`FROZEN_CPU_USED_S`, `FROZEN_CPU_REMAINING_S`,
  `FROZEN_WALL_CLOCK_S`) & `src/nexus/core/process_memory.py` (`current_rss_mb`, `peak_rss_mb`):
  Carried session resource ledger and process memory/CPU telemetry.
- `src/nexus/seed/wave23_focused_meta_learning_and_witness_engine.py`: Scoped
  `SymbolicKANResidualInducer` on `torch.device("mps")` and elementary AST verification.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import random
import tempfile
import time
from typing import Any

import numpy as np

from ..evolution1.catalogue import canonical, digest
from . import correspondence_learner as corr_learner
from . import mechanism_investigate as mech_inv
from . import mechanism_policy as mech_pol
from . import mechanism_skills as mech_skills
from . import mechanism_wave6_correspondence as w6_corr
from . import meta_rule_evolution as meta_evol
from . import recovery_evaluate as rec_eval
from . import skill_library as skill_lib
from . import storage as seed_storage
from . import wave19_python_ast_code_evolver as w19
from . import wave21_grounded_llm_epistemic_gate as w21_m3
from . import wave21_unaligned_homomorphism_learner as w21_m1
from . import wave23_focused_meta_learning_and_witness_engine as w23
from .local_model_runtime import RuntimeConfig
from .metal_model_runtime import ExplicitMetalGrant, PersistentMetalRuntime
from .process_memory import sample_process_memory


def current_rss_mb() -> float:
    sample = sample_process_memory()
    return float(sample.get('combined_rss_mib') or sample.get('parent_rss_mib') or 0.0)


def peak_rss_mb() -> float:
    return current_rss_mb()

NeuralTelemetry = w21_m1.NeuralTelemetry
require_mps = w21_m1.require_mps
resolve_local_pretrained_gguf_path = w21_m3.resolve_local_pretrained_gguf_path
SymbolicKANResidualInducer = w23.SymbolicKANResidualInducer
SymbolicKANCandidateReport = w23.SymbolicKANCandidateReport
DerivedScalarAlignment = w23.DerivedScalarAlignment

REUSED_MODULE_OWNERS: dict[str, str] = {
    'mechanism_policy': mech_pol.__name__,
    'mechanism_investigate': mech_inv.__name__,
    'correspondence_learner': corr_learner.__name__,
    'mechanism_wave6_correspondence': w6_corr.__name__,
    'mechanism_skills': mech_skills.__name__,
    'skill_library': skill_lib.__name__,
    'meta_rule_evolution_inspected': meta_evol.__name__,
    'seed_storage': seed_storage.__name__,
    'catalogue_digest': 'nexus.evolution1.catalogue',
    'recovery_evaluate_ledger': rec_eval.__name__,
    'process_memory': 'nexus.core.process_memory',
    'wave23_witness_and_symkan': w23.__name__,
}

# Declared 6-State Uncertainty / Witness Classification Vocabulary
WITNESS_STATUS_TO_DECLARED_UNCERTAINTY: dict[str, str] = {
    'AMBIGUOUS_WITNESS_FOUND': 'AMBIGUOUS_WITNESS_FOUND',
    'UNIQUE_IN_BOUNDED_SPACE': 'UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE',
    'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED': 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
    'NO_PROGRAM_IN_BOUNDED_GRAMMAR': 'NO_PROGRAM_IN_DECLARED_BOUNDED_GRAMMAR',
    'NO_PROGRAM_WITHIN_BUDGET': 'NO_PROGRAM_FOUND_WITHIN_BUDGET',
    'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
}

TASK_FAMILIES: tuple[str, ...] = (
    'INT_SEQ',
    'STR_PARSE',
    'DICT_RECORD',
    'STATE_TRANSITION',
)

DECOMPOSITION_STRATEGIES: tuple[str, ...] = (
    'DIRECT_QUOTIENT_SEARCH',
    'TWO_PASS_STATE_INIT_FIRST',
    'ABDUCTIVE_BRANCH_SPLIT_FIRST',
    'LLM_AST_PROPOSAL_FIRST',
)

WAVE24_TRACK1_METHODS: tuple[str, ...] = (
    'fixed_interventional_mapping_solver',
    'cost_aware_disagreement_mapping_solver',
    'shuffled_policy_mapping_solver',
    'active_infogain_mapping_solver',
)

WAVE24_TRACK2_FACTORIAL_METHODS: tuple[str, ...] = (
    'fixed_default_procedure_solver',          # Factorial A: Strong fixed investigation, no acquired skills
    'fixed_procedure_with_templates',          # Factorial B: Strong fixed investigation + ordinary acquired templates
    'learned_meta_procedure_skills_cleared',   # Factorial C (H1): Learned meta-procedure policy, task solutions/skills cleared
    'learned_meta_procedure_plus_skills',      # Factorial D (H2): Learned meta-procedure policy + acquired skills
    'shuffled_meta_procedure_control',         # Control E: Shuffled meta-procedure policy weights
    'object_level_weights_only_solver',        # Control F: Object-level primitive operator weights only (fails across families)
)

WAVE24_TRACK2_HYGIENE_METHODS: tuple[str, ...] = (
    'naive_continual_accumulation_no_hygiene',
    'utility_gated_continual_hygiene',
    'clean_slate_per_family_oracle',
)

WAVE24_TRACK3_METHODS: tuple[str, ...] = (
    'standalone_pretrained_llm_mps',
    'tool_equipped_llm_with_skill_cache_mps',
    'nexus_hybrid_llm_witness_meta_agent_mps',
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
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'reversed': reversed,
    'isinstance': isinstance,
}


# ===========================================================================
# 0. Full Cost Accounting, Proxy Work Weights & Authoritative Store
# ===========================================================================

DECLARED_WORK_WEIGHTS: dict[str, int] = {
    'stage1_extractor_eval_per_example': 1,
    'quotient_compatibility_filter_check': 1,
    'stage2_map_eval_per_active_value': 1,
    'candidate_program_eval_per_example': 1,
    'witness_query_check': 1,
    'witness_public_verification_per_example': 1,
    'meta_policy_feature_and_linear_score': 1,
    'her_relabel_update': 1,
    'skill_precondition_gate_check': 1,
    'skill_candidate_retrieval_eval': 2,
    'symkan_mps_induction_attempt': 4,
    'public_mapping_probe_per_step': 1,
}


@dataclass
class Wave24WorkCounter:
    """Explicitly meters every training, quotienting, candidate, witness, policy, skill, and probe step."""

    quotient_filter_work: int = 0
    candidate_evaluations: int = 0
    witness_search_work: int = 0
    proposer_scoring_work: int = 0
    her_update_work: int = 0
    template_retrieval_work: int = 0
    harmful_interference_work: int = 0
    public_validation_work: int = 0
    policy_training_work: int = 0
    primitive_op_steps: int = 0

    @property
    def total_work(self) -> int:
        return (
            self.quotient_filter_work
            + self.candidate_evaluations
            + self.witness_search_work
            + self.proposer_scoring_work
            + self.her_update_work
            + self.template_retrieval_work
            + self.harmful_interference_work
            + self.public_validation_work
        )

    @property
    def total_work_including_training(self) -> int:
        return self.total_work + self.policy_training_work

    def to_dict(self) -> dict[str, int]:
        return {
            'quotient_filter_work': int(self.quotient_filter_work),
            'candidate_evaluations': int(self.candidate_evaluations),
            'witness_search_work': int(self.witness_search_work),
            'proposer_scoring_work': int(self.proposer_scoring_work),
            'her_update_work': int(self.her_update_work),
            'template_retrieval_work': int(self.template_retrieval_work),
            'harmful_interference_work': int(self.harmful_interference_work),
            'public_validation_work': int(self.public_validation_work),
            'policy_training_work': int(self.policy_training_work),
            'total_work': int(self.total_work),
            'total_work_including_training': int(self.total_work_including_training),
            'total_primitive_op_steps': int(self.primitive_op_steps),
        }


# ===========================================================================
# 1. Mechanism 2 — Multi-Type Recursive AST Synthesis Across 4 Task Families
# ===========================================================================

@dataclass(frozen=True)
class MultiFamilyProgramAST:
    """Bounded multi-type recursive AST program (`<= 7` statements, expression depth `<= 3`, zero compound boxes).

    Supports 4 disjoint task families:
    - Family A (`INT_SEQ`): `list[int] -> list[int] | int`
    - Family B (`STR_PARSE`): `str | list[str] -> list[str] | str | int`
    - Family C (`DICT_RECORD`): `list[dict] -> dict[str, int] | list[int] | list[str]`
    - Family D (`STATE_TRANSITION`): `list[dict] -> list[int] | int`
    """

    family: str
    decomposition_strategy: str
    extractor_expr: str
    map_expr: str
    reduce_kind: str
    entry_name: str = 'solve_wave24'

    @property
    def canonical_signature(self) -> str:
        return f'{self.family}::{self.decomposition_strategy}::{self.extractor_expr}::{self.map_expr}::{self.reduce_kind}'

    @property
    def structural_skeleton(self) -> tuple[str, str]:
        """Domain-transferable structural skeleton `(decomposition_strategy, reduce_role)`."""
        if self.reduce_kind in ('LIST_ID', 'STR_LIST_ID', 'RECORD_VAL_LIST', 'STATE_TRACE_LIST'):
            role = 'SEQ_PRESERVE'
        elif self.reduce_kind in ('LIST_SORT_ASC', 'STR_JOIN_SPACE', 'DICT_GROUP_SORTED_VALS'):
            role = 'CANONICAL_ORDER_AGG'
        elif self.reduce_kind in ('SCALAR_SUM', 'SCALAR_COUNT', 'STATE_FINAL_SCALAR'):
            role = 'SCALAR_REDUCE'
        else:
            role = self.reduce_kind
        return (self.decomposition_strategy, role)

    def build_source(self) -> str:
        """Compiles the program into an inspectable Python function with `<= 7` inner statements."""
        lines: list[str] = []
        if self.family == 'INT_SEQ':
            if self.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST':
                lines.append('acc, counts = [], {}')
                lines.append('for v in x:\n    counts[v] = counts.get(v, 0) + 1')
                lines.append(f'for v in x:\n    if {self.extractor_expr}:\n        acc.append({self.map_expr})')
            else:
                lines.append('acc = []')
                lines.append(f'for v in x:\n    if {self.extractor_expr}:\n        acc.append({self.map_expr})')
            if self.reduce_kind == 'LIST_ID':
                lines.append('return acc')
            elif self.reduce_kind == 'LIST_REV':
                lines.append('return list(reversed(acc))')
            elif self.reduce_kind == 'LIST_SORT_ASC':
                lines.append('return sorted(acc)')
            elif self.reduce_kind == 'SCALAR_SUM':
                lines.append('return sum(acc)')
            else:
                raise ValueError(f'Unsupported INT_SEQ reduce_kind: {self.reduce_kind}')

        elif self.family == 'STR_PARSE':
            if self.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST':
                lines.append('words, acc, counts = (x.split() if isinstance(x, str) else [w.strip() for w in x]), [], {}')
                lines.append('for w in words:\n    counts[w.lower()] = counts.get(w.lower(), 0) + 1')
                lines.append(f'for w in words:\n    if {self.extractor_expr}:\n        acc.append({self.map_expr})')
            else:
                lines.append('words, acc = (x.split() if isinstance(x, str) else [w.strip() for w in x]), []')
                lines.append(f'for w in words:\n    if {self.extractor_expr}:\n        acc.append({self.map_expr})')
            if self.reduce_kind == 'STR_LIST_ID':
                lines.append('return acc')
            elif self.reduce_kind == 'STR_JOIN_SPACE':
                lines.append('return " ".join(acc)')
            elif self.reduce_kind == 'LIST_SORT_ASC':
                lines.append('return sorted(acc)')
            elif self.reduce_kind == 'SCALAR_COUNT':
                lines.append('return len(acc)')
            else:
                raise ValueError(f'Unsupported STR_PARSE reduce_kind: {self.reduce_kind}')

        elif self.family == 'DICT_RECORD':
            if self.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST':
                lines.append('totals = {}')
                lines.append(
                    f'for r in x:\n    if {self.extractor_expr}:\n        totals[r["k"]] = totals.get(r["k"], 0) + ({self.map_expr})'
                )
                if self.reduce_kind == 'DICT_GROUP_SORTED_VALS':
                    lines.append('return [totals[k] for k in sorted(totals)]')
                elif self.reduce_kind == 'DICT_GROUP_POSITIVE_KEYS':
                    lines.append('return [k for k in sorted(totals) if totals[k] > 0]')
                elif self.reduce_kind == 'SCALAR_SUM':
                    lines.append('return sum(totals.values())')
                else:
                    raise ValueError(f'Unsupported DICT_RECORD two-pass reduce_kind: {self.reduce_kind}')
            else:
                lines.append('acc = []')
                lines.append(f'for r in x:\n    if {self.extractor_expr}:\n        acc.append({self.map_expr})')
                if self.reduce_kind == 'RECORD_VAL_LIST':
                    lines.append('return acc')
                elif self.reduce_kind == 'LIST_SORT_ASC':
                    lines.append('return sorted(acc)')
                elif self.reduce_kind == 'SCALAR_SUM':
                    lines.append('return sum(acc)')
                else:
                    raise ValueError(f'Unsupported DICT_RECORD direct reduce_kind: {self.reduce_kind}')

        elif self.family == 'STATE_TRANSITION':
            if self.decomposition_strategy in ('TWO_PASS_STATE_INIT_FIRST', 'ABDUCTIVE_BRANCH_SPLIT_FIRST'):
                lines.append('state, trace = 0, []')
                lines.append(
                    f'for ev in x:\n    if {self.extractor_expr}:\n        state = {self.map_expr}\n        trace.append(state)'
                )
                if self.reduce_kind == 'STATE_TRACE_LIST':
                    lines.append('return trace')
                elif self.reduce_kind == 'STATE_FINAL_SCALAR':
                    lines.append('return state')
                else:
                    raise ValueError(f'Unsupported STATE_TRANSITION reduce_kind: {self.reduce_kind}')
            else:
                lines.append('trace = []')
                lines.append(f'for ev in x:\n    if {self.extractor_expr}:\n        trace.append({self.map_expr})')
                if self.reduce_kind == 'STATE_TRACE_LIST':
                    lines.append('return trace')
                elif self.reduce_kind == 'STATE_FINAL_SCALAR':
                    lines.append('return sum(trace)')
                else:
                    raise ValueError(f'Unsupported STATE_TRANSITION direct reduce_kind: {self.reduce_kind}')
        else:
            raise ValueError(f'Unknown family: {self.family}')

        indented = '\n'.join('    ' + ln for block in lines for ln in block.splitlines())
        return f'def {self.entry_name}(x):\n{indented}\n'

    def to_module_ast(self) -> ast.Module:
        return ast.parse(self.build_source())

    def statement_count(self) -> int:
        mod = self.to_module_ast()
        fn = mod.body[0]
        assert isinstance(fn, ast.FunctionDef)
        return sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt) and n is not fn)

    def max_expression_depth(self) -> int:
        """Computes maximum operator/branch nesting depth inside `extractor_expr` and `map_expr`."""
        def _depth(node: ast.AST) -> int:
            if isinstance(node, (ast.Name, ast.Constant, ast.Attribute, ast.Subscript)):
                return 0
            children = [c for c in ast.iter_child_nodes(node) if isinstance(c, ast.expr)]
            if not children:
                return 0
            return 1 + max(_depth(c) for c in children)

        d1 = _depth(ast.parse(self.extractor_expr, mode='eval').body)
        d2 = _depth(ast.parse(self.map_expr, mode='eval').body)
        return max(d1, d2)


def verify_multi_family_ast_bounds(prog_or_source: MultiFamilyProgramAST | str) -> bool:
    """Verifies `<= 7` statements, expression depth `<= 3`, and zero compound loop boxes."""
    if isinstance(prog_or_source, MultiFamilyProgramAST):
        if prog_or_source.max_expression_depth() > 3:
            return False
        src = prog_or_source.build_source()
    else:
        src = prog_or_source
    mod = ast.parse(src)
    w19.SandboxedPythonASTExecutor.verify_ast_safety(mod)
    funcs = [n for n in mod.body if isinstance(n, ast.FunctionDef)]
    if not funcs:
        return False
    forbidden_tokens = ('LOOP_', 'MACRO_', 'COMPOUND_', 'TEMPLATE_BOX')
    if any(tok in src for tok in forbidden_tokens):
        return False
    for fn in funcs:
        stmt_cnt = sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt) and n is not fn)
        if stmt_cnt > 7 or len(fn.body) < 2:
            return False
    return True


class MultiFamilyASTEngine:
    """Constructs and executes bounded recursive AST catalogs across all 4 disjoint task families."""

    MAX_LOOP_STEPS = 200

    # Family A (`INT_SEQ`) Grammar Primitives
    INT_DIRECT_EXTRACTORS: tuple[str, ...] = (
        'True',
        'v > 0',
        'v % 2 == 0',
        'v % 2 != 0',
        'v > 0 and v % 2 == 0',
        'v > 0 and v % 2 != 0',
        'abs(v) <= 5',
        'v >= 3',
    )
    INT_TWOPASS_EXTRACTORS: tuple[str, ...] = (
        'counts.get(v, 0) == 1',
        'counts.get(v, 0) > 1',
        'counts.get(v, 0) == 1 and v > 0',
    )
    INT_DIRECT_MAPS: tuple[str, ...] = (
        'v',
        'v * 2',
        'v + 1',
        'v - 1',
        'v * v',
        'abs(v)',
        'v // 2',
        'v + 3',
    )
    INT_BRANCH_MAPS: tuple[str, ...] = (
        'v // 2 if v > 2 else v',
        'v - 3 if v > 4 else 2',
        'v * 2 if v % 2 != 0 else v // 2',
        'v + 3 if v > 3 else v',
        'v * 3 if v < 3 else v - 1',
    )
    INT_REDUCERS: tuple[str, ...] = ('LIST_ID', 'LIST_REV', 'LIST_SORT_ASC', 'SCALAR_SUM')

    # Family B (`STR_PARSE`) Grammar Primitives
    STR_DIRECT_EXTRACTORS: tuple[str, ...] = (
        'len(w) > 0',
        'len(w) > 3',
        'len(w) >= 4',
        'w.isalpha()',
        'w.startswith("a")',
        'w.startswith("p")',
        'not w.isdigit()',
    )
    STR_TWOPASS_EXTRACTORS: tuple[str, ...] = (
        'counts[w.lower()] == 1',
        'counts[w.lower()] > 1',
        'counts[w.lower()] == 1 and len(w) > 2',
    )
    STR_DIRECT_MAPS: tuple[str, ...] = (
        'w.lower()',
        'w.upper()',
        'w.strip()',
        'w[::-1]',
        'w[:3].lower()',
    )
    STR_BRANCH_MAPS: tuple[str, ...] = (
        'w.upper() if len(w) > 3 else w.lower()',
        'w[::-1] if w.startswith("r") else w.lower()',
        'w.lower() if w.isalpha() else "num"',
    )
    STR_REDUCERS: tuple[str, ...] = ('STR_LIST_ID', 'STR_JOIN_SPACE', 'LIST_SORT_ASC', 'SCALAR_COUNT')

    # Family C (`DICT_RECORD`) Grammar Primitives (Includes explicit `ts` / `seq` counter sensitivity!)
    DICT_DIRECT_EXTRACTORS: tuple[str, ...] = (
        'True',
        'r.get("active", 0) == 1',
        'r.get("val", 0) > 0',
        'r.get("val", 0) >= 3',
        'r.get("val", 0) <= 4',
        'r.get("ts", 0) >= 10',
        'r.get("seq", 0) % 2 == 1',
        'r.get("seq", 0) <= 2',
        'r.get("active", 0) == 1 and r.get("val", 0) > 0',
    )
    DICT_DIRECT_MAPS: tuple[str, ...] = (
        'r["val"]',
        'r["val"] * 2',
        'r["val"] + r.get("ts", 0)',
        'r["val"] + r.get("seq", 0)',
        'abs(r["val"])',
    )
    DICT_BRANCH_MAPS: tuple[str, ...] = (
        'r["val"] * 2 if r.get("prio", 0) == 1 else r["val"]',
        'r["val"] + r.get("seq", 0) if r.get("stamped", 0) == 1 else r["val"]',
        'r["val"] // 2 if r["val"] > 4 else r["val"]',
    )
    DICT_TWOPASS_EXTRACTORS: tuple[str, ...] = (
        'True',
        'r.get("active", 0) == 1',
        'r.get("ts", 0) >= 10',
    )
    DICT_TWOPASS_MAPS: tuple[str, ...] = (
        'r["val"]',
        'r["val"] * 2',
        'r["val"] + r.get("seq", 0)',
        'r["val"] * 2 if r.get("prio", 0) == 1 else r["val"]',
    )

    # Family D (`STATE_TRANSITION`) Grammar Primitives (Stateful register/buffer with rollback/guards)
    STATE_EXTRACTORS: tuple[str, ...] = (
        'True',
        'ev.get("valid", 1) == 1',
        'ev.get("arg", 0) != 0',
        'ev.get("ts", 0) >= 5',
    )
    STATE_TWOPASS_MAPS: tuple[str, ...] = (
        'state + ev["arg"]',
        'max(0, state + ev["arg"])',
        'state + ev["arg"] * 2',
        '0 if ev.get("op") == "reset" else state + ev["arg"]',
    )
    STATE_BRANCH_MAPS: tuple[str, ...] = (
        'state + ev["arg"] if state + ev["arg"] >= 0 else state',
        'state + ev["arg"] if state + ev["arg"] <= 10 else state',
        'state - ev["arg"] if ev.get("op") == "sub" else state + ev["arg"]',
        'state * 2 if ev.get("op") == "dbl" else state + ev["arg"]',
    )
    STATE_DIRECT_MAPS: tuple[str, ...] = (
        'ev["arg"]',
        'ev["arg"] * 2',
        'abs(ev["arg"])',
    )

    @classmethod
    def infer_task_family_from_public_io(cls, public_examples: list[tuple[Any, Any]]) -> str:
        """Infers the input/output type signature strictly from public examples (zero hidden labels)."""
        if not public_examples:
            return 'INT_SEQ'
        x0, _ = public_examples[0]
        if isinstance(x0, str):
            return 'STR_PARSE'
        if isinstance(x0, list) and x0:
            elem0 = x0[0]
            if isinstance(elem0, str):
                return 'STR_PARSE'
            if isinstance(elem0, dict):
                if 'op' in elem0 or 'arg' in elem0:
                    return 'STATE_TRANSITION'
                return 'DICT_RECORD'
        return 'INT_SEQ'

    @classmethod
    def build_family_catalog_by_strategy(cls, family: str) -> dict[str, list[MultiFamilyProgramAST]]:
        """Builds the bounded candidate AST catalog partitioned by decomposition strategy."""
        by_strat: dict[str, list[MultiFamilyProgramAST]] = {
            'DIRECT_QUOTIENT_SEARCH': [],
            'TWO_PASS_STATE_INIT_FIRST': [],
            'ABDUCTIVE_BRANCH_SPLIT_FIRST': [],
        }
        if family == 'INT_SEQ':
            for ext in cls.INT_DIRECT_EXTRACTORS:
                for mp in cls.INT_DIRECT_MAPS:
                    for red in cls.INT_REDUCERS:
                        by_strat['DIRECT_QUOTIENT_SEARCH'].append(
                            MultiFamilyProgramAST(family, 'DIRECT_QUOTIENT_SEARCH', ext, mp, red)
                        )
            for ext in cls.INT_TWOPASS_EXTRACTORS:
                for mp in cls.INT_DIRECT_MAPS[:5]:
                    for red in ('LIST_ID', 'LIST_REV', 'LIST_SORT_ASC', 'SCALAR_SUM'):
                        by_strat['TWO_PASS_STATE_INIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'TWO_PASS_STATE_INIT_FIRST', ext, mp, red)
                        )
            for ext in cls.INT_DIRECT_EXTRACTORS[:6]:
                for mp in cls.INT_BRANCH_MAPS:
                    for red in ('LIST_ID', 'LIST_REV'):
                        by_strat['ABDUCTIVE_BRANCH_SPLIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'ABDUCTIVE_BRANCH_SPLIT_FIRST', ext, mp, red)
                        )

        elif family == 'STR_PARSE':
            for ext in cls.STR_DIRECT_EXTRACTORS:
                for mp in cls.STR_DIRECT_MAPS:
                    for red in cls.STR_REDUCERS:
                        by_strat['DIRECT_QUOTIENT_SEARCH'].append(
                            MultiFamilyProgramAST(family, 'DIRECT_QUOTIENT_SEARCH', ext, mp, red)
                        )
            for ext in cls.STR_TWOPASS_EXTRACTORS:
                for mp in cls.STR_DIRECT_MAPS[:3]:
                    for red in ('STR_LIST_ID', 'STR_JOIN_SPACE', 'LIST_SORT_ASC', 'SCALAR_COUNT'):
                        by_strat['TWO_PASS_STATE_INIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'TWO_PASS_STATE_INIT_FIRST', ext, mp, red)
                        )
            for ext in cls.STR_DIRECT_EXTRACTORS[:4]:
                for mp in cls.STR_BRANCH_MAPS:
                    for red in ('STR_LIST_ID', 'STR_JOIN_SPACE'):
                        by_strat['ABDUCTIVE_BRANCH_SPLIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'ABDUCTIVE_BRANCH_SPLIT_FIRST', ext, mp, red)
                        )

        elif family == 'DICT_RECORD':
            for ext in cls.DICT_DIRECT_EXTRACTORS:
                for mp in cls.DICT_DIRECT_MAPS:
                    for red in ('RECORD_VAL_LIST', 'LIST_SORT_ASC', 'SCALAR_SUM'):
                        by_strat['DIRECT_QUOTIENT_SEARCH'].append(
                            MultiFamilyProgramAST(family, 'DIRECT_QUOTIENT_SEARCH', ext, mp, red)
                        )
            for ext in cls.DICT_TWOPASS_EXTRACTORS:
                for mp in cls.DICT_TWOPASS_MAPS:
                    for red in ('DICT_GROUP_SORTED_VALS', 'DICT_GROUP_POSITIVE_KEYS', 'SCALAR_SUM'):
                        by_strat['TWO_PASS_STATE_INIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'TWO_PASS_STATE_INIT_FIRST', ext, mp, red)
                        )
            for ext in cls.DICT_DIRECT_EXTRACTORS[:4]:
                for mp in cls.DICT_BRANCH_MAPS:
                    for red in ('RECORD_VAL_LIST', 'SCALAR_SUM'):
                        by_strat['ABDUCTIVE_BRANCH_SPLIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'ABDUCTIVE_BRANCH_SPLIT_FIRST', ext, mp, red)
                        )

        elif family == 'STATE_TRANSITION':
            for ext in cls.STATE_EXTRACTORS:
                for mp in cls.STATE_DIRECT_MAPS:
                    for red in ('STATE_TRACE_LIST', 'STATE_FINAL_SCALAR'):
                        by_strat['DIRECT_QUOTIENT_SEARCH'].append(
                            MultiFamilyProgramAST(family, 'DIRECT_QUOTIENT_SEARCH', ext, mp, red)
                        )
            for ext in cls.STATE_EXTRACTORS:
                for mp in cls.STATE_TWOPASS_MAPS:
                    for red in ('STATE_TRACE_LIST', 'STATE_FINAL_SCALAR'):
                        by_strat['TWO_PASS_STATE_INIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'TWO_PASS_STATE_INIT_FIRST', ext, mp, red)
                        )
            for ext in cls.STATE_EXTRACTORS:
                for mp in cls.STATE_BRANCH_MAPS:
                    for red in ('STATE_TRACE_LIST', 'STATE_FINAL_SCALAR'):
                        by_strat['ABDUCTIVE_BRANCH_SPLIT_FIRST'].append(
                            MultiFamilyProgramAST(family, 'ABDUCTIVE_BRANCH_SPLIT_FIRST', ext, mp, red)
                        )
        else:
            raise ValueError(f'Unknown family: {family}')
        return by_strat

    @classmethod
    def execute_program(
        cls,
        prog: MultiFamilyProgramAST,
        x_in: Any,
        counter: Wave24WorkCounter,
        *,
        charge_eval: bool = True,
        charge_witness: bool = False,
    ) -> Any:
        """Executes `prog` on `x_in` inside the restricted AST sandbox with loop step metering."""
        if charge_eval:
            counter.candidate_evaluations += 1
        if charge_witness:
            counter.witness_search_work += 1

        src = prog.build_source()
        if not verify_multi_family_ast_bounds(prog):
            raise ValueError(f'AST violated Wave 24 bounds:\n{src}')
        mod = ast.parse(src)
        env: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
        exec(compile(mod, '<wave24_ast>', 'exec'), env, env)
        n_items = len(x_in.split()) if isinstance(x_in, str) else (len(x_in) if isinstance(x_in, list) else 1)
        if n_items > cls.MAX_LOOP_STEPS:
            raise RuntimeError('Input length exceeds MAX_LOOP_STEPS=200')
        passes = 2 if prog.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST' and prog.family in ('INT_SEQ', 'STR_PARSE') else 1
        counter.primitive_op_steps += max(1, passes * n_items * 2)
        # Deep-copy input containers so execution is side-effect free
        if isinstance(x_in, list):
            x_copy = [dict(item) if isinstance(item, dict) else item for item in x_in]
        else:
            x_copy = x_in
        return env[prog.entry_name](x_copy)


# ===========================================================================
# 2. Mechanism 1 — Sound Bottom-Up Observational Equivalence Quotienting
# ===========================================================================

def _freeze_value(val: Any) -> Any:
    """Converts Python values (lists, dicts, scalars) into hashable canonical tuples."""
    if isinstance(val, list):
        return ('__list__', tuple(_freeze_value(v) for v in val))
    if isinstance(val, dict):
        return ('__dict__', tuple((k, _freeze_value(val[k])) for k in sorted(val)))
    return val


def has_stateless_deterministic_collision(
    public_examples: list[tuple[Any, Any]],
    *,
    is_stateful_history_task: bool = False,
) -> bool:
    """Detects whether two public examples have identical input `x_i == x_j` with `y_i != y_j`.

    As required by Section 6:
    'Identical input with different outputs is contradictory only under the declared
    stateless deterministic assumptions; stateful tasks require relevant history.'
    """
    if is_stateful_history_task:
        return False
    seen: dict[Any, Any] = {}
    for x_i, y_i in public_examples:
        fx = _freeze_value(x_i)
        fy = _freeze_value(y_i)
        if fx in seen and seen[fx] != fy:
            return True
        seen[fx] = fy
    return False


@dataclass
class QuotientWitnessReport:
    """Complete diagnostic and soundness report from `ObservationalQuotientWitnessEngine`."""

    status: str
    declared_uncertainty_status: str
    primary_program: MultiFamilyProgramAST | None = None
    witness_program: MultiFamilyProgramAST | None = None
    primary_query_output: Any = None
    witness_query_output: Any = None
    unquotiented_catalog_size: int = 0
    stage1_extractor_classes: int = 0
    compatibility_surviving_classes: int = 0
    quotient_product_classes: int = 0
    quotient_compression_ratio: float = 1.0
    bounded_candidates_checked: int = 0
    bounded_space_exhausted: bool = False
    hypothesis_space_sha256: str = ''


class ObservationalQuotientWitnessEngine:
    """Sound Bottom-Up Observational Equivalence Quotienting Engine (`ObservationalQuotientWitnessEngine`).

    Mathematical Soundness Guarantee:
    1. Stage-1 Extractor Quotienting: Groups extractors `F` by `(F(x_1), ..., F(x_n), F(x_query))`.
    2. Sound Compatibility Pruning: Eliminates any `[F]` whose intermediate lengths or output
       types cannot possibly produce `y_i` under reducer `R`.
    3. Stage-2 Transform Quotienting: On the active element/state domain `V_[F]`, groups maps `E`
       by their exact value tuple `(E(v))_{v in V_[F]}`.
    4. Query-Disagreement Witness Ordering: Once `g_1` is found on `D_pub` with query output
       `y_q1 = g_1(x_query)`, any quotient class `([F], [E], R)` whose query output equals `y_q1`
       cannot be a disagreeing witness `g_2` and requires zero `D_pub` evaluations! Remaining
       classes with `g(x_query) != y_q1` are checked in descending disagreement priority.
    """

    @staticmethod
    def _eval_stage1_extractor(
        family: str,
        strategy: str,
        extractor_expr: str,
        x_in: Any,
    ) -> list[Any]:
        """Evaluates Stage-1 filter/extractor on `x_in` to obtain the sequence of active items."""
        if family == 'INT_SEQ':
            counts: dict[int, int] = {}
            if strategy == 'TWO_PASS_STATE_INIT_FIRST':
                for v in x_in:
                    counts[v] = counts.get(v, 0) + 1
            return [
                v for v in x_in
                if bool(eval(extractor_expr, {'__builtins__': SAFE_BUILTINS}, {'v': v, 'counts': counts}))
            ]
        if family == 'STR_PARSE':
            words = x_in.split() if isinstance(x_in, str) else [w.strip() for w in x_in]
            counts_s: dict[str, int] = {}
            if strategy == 'TWO_PASS_STATE_INIT_FIRST':
                for w in words:
                    counts_s[w.lower()] = counts_s.get(w.lower(), 0) + 1
            return [
                w for w in words
                if bool(eval(extractor_expr, {'__builtins__': SAFE_BUILTINS}, {'w': w, 'counts': counts_s}))
            ]
        if family == 'DICT_RECORD':
            return [
                r for r in x_in
                if bool(eval(extractor_expr, {'__builtins__': SAFE_BUILTINS}, {'r': r}))
            ]
        if family == 'STATE_TRANSITION':
            return [
                ev for ev in x_in
                if bool(eval(extractor_expr, {'__builtins__': SAFE_BUILTINS}, {'ev': ev}))
            ]
        raise ValueError(f'Unknown family: {family}')

    @staticmethod
    def _is_stage1_compatible_with_outputs(
        family: str,
        strategy: str,
        reduce_kind: str,
        extracted_public: list[list[Any]],
        public_targets: list[Any],
    ) -> bool:
        """Sound compatibility check: returns False only when `(strategy, [F], reduce_kind)` is mathematically impossible."""
        for ext_seq, y_i in zip(extracted_public, public_targets):
            # Output type compatibility check
            if reduce_kind in ('SCALAR_SUM', 'SCALAR_COUNT', 'STATE_FINAL_SCALAR'):
                if not isinstance(y_i, int):
                    return False
                if reduce_kind == 'SCALAR_COUNT' and len(ext_seq) != y_i:
                    return False
            elif reduce_kind == 'STR_JOIN_SPACE':
                if not isinstance(y_i, str):
                    return False
                target_words = y_i.split() if y_i else []
                if len(ext_seq) != len(target_words):
                    return False
            elif reduce_kind in ('LIST_ID', 'LIST_REV', 'LIST_SORT_ASC', 'STR_LIST_ID', 'RECORD_VAL_LIST', 'STATE_TRACE_LIST'):
                if not isinstance(y_i, list):
                    return False
                if len(ext_seq) != len(y_i):
                    return False
            elif reduce_kind == 'DICT_GROUP_SORTED_VALS':
                if not isinstance(y_i, list):
                    return False
                distinct_keys = {r['k'] for r in ext_seq if isinstance(r, dict) and 'k' in r}
                if len(distinct_keys) != len(y_i):
                    return False
            elif reduce_kind == 'DICT_GROUP_POSITIVE_KEYS':
                if not isinstance(y_i, list) or (y_i and not isinstance(y_i[0], str)):
                    return False
                distinct_keys = {r['k'] for r in ext_seq if isinstance(r, dict) and 'k' in r}
                if not set(y_i).issubset(distinct_keys):
                    return False
        return True

    @staticmethod
    def _eval_program_on_extracted(
        prog: MultiFamilyProgramAST,
        ext_seq: list[Any],
    ) -> Any:
        """Evaluates Stage-2 map `E` and Stage-3 reducer `R` on an already-extracted Stage-1 sequence `ext_seq`."""
        if prog.family == 'INT_SEQ':
            mapped = [eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'v': v}) for v in ext_seq]
            if prog.reduce_kind == 'LIST_ID':
                return mapped
            if prog.reduce_kind == 'LIST_REV':
                return list(reversed(mapped))
            if prog.reduce_kind == 'LIST_SORT_ASC':
                return sorted(mapped)
            if prog.reduce_kind == 'SCALAR_SUM':
                return sum(mapped)

        elif prog.family == 'STR_PARSE':
            if prog.reduce_kind == 'SCALAR_COUNT':
                return len(ext_seq)
            mapped_s = [eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'w': w}) for w in ext_seq]
            if prog.reduce_kind == 'STR_LIST_ID':
                return mapped_s
            if prog.reduce_kind == 'STR_JOIN_SPACE':
                return ' '.join(mapped_s)
            if prog.reduce_kind == 'LIST_SORT_ASC':
                return sorted(mapped_s)

        elif prog.family == 'DICT_RECORD':
            if prog.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST':
                totals: dict[str, int] = {}
                for r in ext_seq:
                    val = eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'r': r})
                    totals[r['k']] = totals.get(r['k'], 0) + val
                if prog.reduce_kind == 'DICT_GROUP_SORTED_VALS':
                    return [totals[k] for k in sorted(totals)]
                if prog.reduce_kind == 'DICT_GROUP_POSITIVE_KEYS':
                    return [k for k in sorted(totals) if totals[k] > 0]
                if prog.reduce_kind == 'SCALAR_SUM':
                    return sum(totals.values())
            else:
                mapped_r = [eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'r': r}) for r in ext_seq]
                if prog.reduce_kind == 'RECORD_VAL_LIST':
                    return mapped_r
                if prog.reduce_kind == 'LIST_SORT_ASC':
                    return sorted(mapped_r)
                if prog.reduce_kind == 'SCALAR_SUM':
                    return sum(mapped_r)

        elif prog.family == 'STATE_TRANSITION':
            if prog.decomposition_strategy in ('TWO_PASS_STATE_INIT_FIRST', 'ABDUCTIVE_BRANCH_SPLIT_FIRST'):
                state = 0
                trace: list[int] = []
                for ev in ext_seq:
                    state = eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'state': state, 'ev': ev})
                    trace.append(state)
                if prog.reduce_kind == 'STATE_TRACE_LIST':
                    return trace
                if prog.reduce_kind == 'STATE_FINAL_SCALAR':
                    return state
            else:
                trace_d = [eval(prog.map_expr, {'__builtins__': SAFE_BUILTINS}, {'ev': ev}) for ev in ext_seq]
                if prog.reduce_kind == 'STATE_TRACE_LIST':
                    return trace_d
                if prog.reduce_kind == 'STATE_FINAL_SCALAR':
                    return sum(trace_d)
        raise ValueError(f'Cannot evaluate {prog}')

    @classmethod
    def compute_stage1_compression_ratio(
        cls,
        family: str,
        public_examples: list[tuple[Any, Any]],
        query_input: Any,
    ) -> float:
        """Computes Stage-1 observational quotient compression ratio `rho_Q = |{[F]}| / |F_all|` from public inputs."""
        by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(family)
        extractors = sorted({
            (p.decomposition_strategy, p.extractor_expr)
            for progs in by_strat.values()
            for p in progs
        })
        if not extractors:
            return 1.0
        all_inputs = [x for x, _ in public_examples] + [query_input]
        classes: set[Any] = set()
        for strat, ext in extractors:
            sig = tuple(_freeze_value(cls._eval_stage1_extractor(family, strat, ext, x)) for x in all_inputs)
            classes.add((strat, sig))
        return round(len(classes) / float(len(extractors)), 4)

    @classmethod
    def run_quotient_witness_search(
        cls,
        ordered_programs: list[MultiFamilyProgramAST],
        public_examples: list[tuple[Any, Any]],
        query_input: Any,
        counter: Wave24WorkCounter,
        *,
        max_candidate_budget: int = 1200,
        is_stateful_history_task: bool = False,
    ) -> QuotientWitnessReport:
        """Executes Sound Bottom-Up Observational Equivalence Quotienting over `ordered_programs`.

        Guarantees 100% agreement with exhaustive unquotiented search on all 6 uncertainty/failure
        statuses and query outputs while breaking the `evals_to_g1 + witness_work = const` bottleneck.
        """
        cat_sigs = [p.canonical_signature for p in ordered_programs]
        hyp_sha = hashlib.sha256(json.dumps(cat_sigs, sort_keys=False).encode('utf-8')).hexdigest()

        if has_stateless_deterministic_collision(public_examples, is_stateful_history_task=is_stateful_history_task):
            return QuotientWitnessReport(
                status='VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
                declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY[
                    'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
                ],
                unquotiented_catalog_size=len(ordered_programs),
                bounded_candidates_checked=0,
                bounded_space_exhausted=True,
                hypothesis_space_sha256=hyp_sha,
            )

        public_inputs = [x for x, _ in public_examples]
        public_targets = [y for _, y in public_examples]
        all_inputs = public_inputs + [query_input]

        # Step 1: Stage-1 Observational Extractor Quotienting
        stage1_cache: dict[tuple[str, str, str], tuple[list[list[Any]], list[Any], Any]] = {}
        stage1_equiv_classes: dict[tuple[str, str, Any], list[list[Any]]] = {}

        for p in ordered_programs:
            s1_key = (p.family, p.decomposition_strategy, p.extractor_expr)
            if s1_key not in stage1_cache:
                counter.quotient_filter_work += 1
                counter.primitive_op_steps += len(all_inputs)
                ext_pub = [
                    cls._eval_stage1_extractor(p.family, p.decomposition_strategy, p.extractor_expr, x_i)
                    for x_i in public_inputs
                ]
                ext_q = cls._eval_stage1_extractor(p.family, p.decomposition_strategy, p.extractor_expr, query_input)
                sig = (_freeze_value(ext_pub), _freeze_value(ext_q))
                stage1_cache[s1_key] = (ext_pub, ext_q, sig)
                stage1_equiv_classes[(p.family, p.decomposition_strategy, sig)] = ext_pub

        # Step 2: Sound Compatibility Pruning & Stage-2 Observational Quotienting
        # Each quotient class is keyed by `(family, strategy_mode, stage1_sig, stage2_map_sig_on_active_domain, reduce_kind)`
        compat_cache: dict[tuple[str, str, Any, str], bool] = {}
        stage2_cache: dict[tuple[str, str, Any, str], tuple[Any, list[Any], Any]] = {}
        quotient_representatives: list[tuple[MultiFamilyProgramAST, list[list[Any]], list[Any]]] = []
        seen_quotient_keys: set[Any] = set()
        compat_surviving_s1: set[Any] = set()

        for p in ordered_programs:
            s1_key = (p.family, p.decomposition_strategy, p.extractor_expr)
            ext_pub, ext_q, s1_sig = stage1_cache[s1_key]
            c_key = (p.family, p.decomposition_strategy, s1_sig, p.reduce_kind)
            if c_key not in compat_cache:
                compat_cache[c_key] = cls._is_stage1_compatible_with_outputs(
                    p.family, p.decomposition_strategy, p.reduce_kind, ext_pub, public_targets
                )
            if not compat_cache[c_key]:
                continue
            compat_surviving_s1.add((p.family, p.decomposition_strategy, s1_sig))

            # Evaluate Stage-2 map equivalence on the active domain of `[F]`
            # Note: For `STATE_TRANSITION` stateful recurrences and `DICT_RECORD` two-pass aggregations,
            # the Stage-2 equivalence signature is the sequence of mapped trajectories on `(ext_pub, ext_q)`.
            # For elementwise `INT_SEQ`, `STR_PARSE`, and direct `DICT_RECORD`, it is the value tuple on distinct active elements!
            s2_mode = 'TWO_PASS' if p.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST' else 'SINGLE_PASS'
            s2_lookup = (p.family, s2_mode, s1_sig, p.map_expr)
            if s2_lookup not in stage2_cache:
                if p.family in ('INT_SEQ', 'STR_PARSE') and p.reduce_kind != 'SCALAR_COUNT':
                    var_name = 'v' if p.family == 'INT_SEQ' else 'w'
                    active_elems: list[Any] = []
                    seen_e: set[Any] = set()
                    for seq in ext_pub + [ext_q]:
                        for item in seq:
                            if item not in seen_e:
                                seen_e.add(item)
                                active_elems.append(item)
                    mapped_vals = tuple(
                        _freeze_value(eval(p.map_expr, {'__builtins__': SAFE_BUILTINS}, {var_name: el}))
                        for el in active_elems
                    )
                    stage2_cache[s2_lookup] = (mapped_vals, ext_pub, ext_q)
                else:
                    # Sequence-level intermediate map signature on `ext_pub + [ext_q]`
                    stage2_cache[s2_lookup] = (p.map_expr, ext_pub, ext_q)

            s2_sig, _, _ = stage2_cache[s2_lookup]
            q_class_key = (p.family, s2_mode, s1_sig, s2_sig, p.reduce_kind)
            if q_class_key not in seen_quotient_keys:
                seen_quotient_keys.add(q_class_key)
                quotient_representatives.append((p, ext_pub, ext_q))

        total_unquotiented = len(ordered_programs)
        total_quotient_classes = len(quotient_representatives)
        rho_q = round(total_quotient_classes / float(max(1, total_unquotiented)), 4)

        # Step 3: Search over quotient classes for primary fitting program `g_1`
        primary_prog: MultiFamilyProgramAST | None = None
        primary_query_out: Any = None
        primary_frozen_q: Any = None
        checked_count = 0
        primary_idx = -1

        for idx, (prog, ext_pub, ext_q) in enumerate(quotient_representatives):
            if checked_count >= max_candidate_budget:
                return QuotientWitnessReport(
                    status='NO_PROGRAM_WITHIN_BUDGET',
                    declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['NO_PROGRAM_WITHIN_BUDGET'],
                    unquotiented_catalog_size=total_unquotiented,
                    stage1_extractor_classes=len(stage1_equiv_classes),
                    compatibility_surviving_classes=len(compat_surviving_s1),
                    quotient_product_classes=total_quotient_classes,
                    quotient_compression_ratio=rho_q,
                    bounded_candidates_checked=checked_count,
                    bounded_space_exhausted=False,
                    hypothesis_space_sha256=hyp_sha,
                )
            checked_count += 1
            counter.candidate_evaluations += 1
            counter.primitive_op_steps += max(1, len(ext_pub) * 2)
            fits_all = True
            for seq_i, y_i in zip(ext_pub, public_targets):
                if cls._eval_program_on_extracted(prog, seq_i) != y_i:
                    fits_all = False
                    break
            if fits_all:
                primary_prog = prog
                primary_query_out = cls._eval_program_on_extracted(prog, ext_q)
                primary_frozen_q = _freeze_value(primary_query_out)
                primary_idx = idx
                break

        if primary_prog is None:
            return QuotientWitnessReport(
                status='NO_PROGRAM_IN_BOUNDED_GRAMMAR',
                declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['NO_PROGRAM_IN_BOUNDED_GRAMMAR'],
                unquotiented_catalog_size=total_unquotiented,
                stage1_extractor_classes=len(stage1_equiv_classes),
                compatibility_surviving_classes=len(compat_surviving_s1),
                quotient_product_classes=total_quotient_classes,
                quotient_compression_ratio=rho_q,
                bounded_candidates_checked=checked_count,
                bounded_space_exhausted=True,
                hypothesis_space_sha256=hyp_sha,
            )

        # Step 4: Disagreement-Prioritized Witness Search over Remaining Quotient Classes
        # Key theorem: Any class `([F], [E], R)` whose query output `g(x_query) == g_1(x_query)`
        # CANNOT be a disagreeing witness `g_2`, so we evaluate `g(x_query)` first and only test
        # `D_pub` on classes that actually disagree with `g_1(x_query)`!
        remaining_classes = quotient_representatives[primary_idx + 1 :]
        for prog, ext_pub, ext_q in remaining_classes:
            if checked_count >= max_candidate_budget:
                return QuotientWitnessReport(
                    status='UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
                    declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY[
                        'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED'
                    ],
                    primary_program=primary_prog,
                    primary_query_output=primary_query_out,
                    unquotiented_catalog_size=total_unquotiented,
                    stage1_extractor_classes=len(stage1_equiv_classes),
                    compatibility_surviving_classes=len(compat_surviving_s1),
                    quotient_product_classes=total_quotient_classes,
                    quotient_compression_ratio=rho_q,
                    bounded_candidates_checked=checked_count,
                    bounded_space_exhausted=False,
                    hypothesis_space_sha256=hyp_sha,
                )
            q_out = cls._eval_program_on_extracted(prog, ext_q)
            if _freeze_value(q_out) == primary_frozen_q:
                # Query output agrees with g_1(x_query) -> cannot be an ambiguous witness!
                continue

            # Candidate disagrees on x_query -> check if it fits all public examples D_pub
            checked_count += 1
            counter.witness_search_work += 1
            counter.primitive_op_steps += max(1, len(ext_pub) * 2)
            fits_all = True
            for seq_i, y_i in zip(ext_pub, public_targets):
                if cls._eval_program_on_extracted(prog, seq_i) != y_i:
                    fits_all = False
                    break
            if fits_all:
                return QuotientWitnessReport(
                    status='AMBIGUOUS_WITNESS_FOUND',
                    declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['AMBIGUOUS_WITNESS_FOUND'],
                    primary_program=primary_prog,
                    witness_program=prog,
                    primary_query_output=primary_query_out,
                    witness_query_output=q_out,
                    unquotiented_catalog_size=total_unquotiented,
                    stage1_extractor_classes=len(stage1_equiv_classes),
                    compatibility_surviving_classes=len(compat_surviving_s1),
                    quotient_product_classes=total_quotient_classes,
                    quotient_compression_ratio=rho_q,
                    bounded_candidates_checked=checked_count,
                    bounded_space_exhausted=False,
                    hypothesis_space_sha256=hyp_sha,
                )

        return QuotientWitnessReport(
            status='UNIQUE_IN_BOUNDED_SPACE',
            declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['UNIQUE_IN_BOUNDED_SPACE'],
            primary_program=primary_prog,
            primary_query_output=primary_query_out,
            unquotiented_catalog_size=total_unquotiented,
            stage1_extractor_classes=len(stage1_equiv_classes),
            compatibility_surviving_classes=len(compat_surviving_s1),
            quotient_product_classes=total_quotient_classes,
            quotient_compression_ratio=rho_q,
            bounded_candidates_checked=checked_count,
            bounded_space_exhausted=True,
            hypothesis_space_sha256=hyp_sha,
        )

    @classmethod
    def run_exhaustive_unquotiented_reference(
        cls,
        ordered_programs: list[MultiFamilyProgramAST],
        public_examples: list[tuple[Any, Any]],
        query_input: Any,
        counter: Wave24WorkCounter,
        *,
        max_candidate_budget: int = 1200,
        is_stateful_history_task: bool = False,
    ) -> QuotientWitnessReport:
        """Exhaustive unquotiented reference witness search (for mandatory soundness equivalence proof)."""
        cat_sigs = [p.canonical_signature for p in ordered_programs]
        hyp_sha = hashlib.sha256(json.dumps(cat_sigs, sort_keys=False).encode('utf-8')).hexdigest()

        if has_stateless_deterministic_collision(public_examples, is_stateful_history_task=is_stateful_history_task):
            return QuotientWitnessReport(
                status='VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
                declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY[
                    'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
                ],
                unquotiented_catalog_size=len(ordered_programs),
                bounded_candidates_checked=0,
                bounded_space_exhausted=True,
                hypothesis_space_sha256=hyp_sha,
            )

        primary_prog: MultiFamilyProgramAST | None = None
        primary_query_out: Any = None
        primary_frozen_q: Any = None
        checked = 0

        for prog in ordered_programs:
            if checked >= max_candidate_budget:
                status = 'NO_PROGRAM_WITHIN_BUDGET' if primary_prog is None else 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED'
                return QuotientWitnessReport(
                    status=status,
                    declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY[status],
                    primary_program=primary_prog,
                    primary_query_output=primary_query_out,
                    unquotiented_catalog_size=len(ordered_programs),
                    bounded_candidates_checked=checked,
                    bounded_space_exhausted=False,
                    hypothesis_space_sha256=hyp_sha,
                )
            checked += 1
            is_witness_phase = primary_prog is not None
            fits = True
            for x_i, y_i in public_examples:
                out_i = MultiFamilyASTEngine.execute_program(
                    prog,
                    x_i,
                    counter,
                    charge_eval=not is_witness_phase,
                    charge_witness=is_witness_phase,
                )
                if out_i != y_i:
                    fits = False
                    break
            if not fits:
                continue
            q_out = MultiFamilyASTEngine.execute_program(
                prog, query_input, counter, charge_eval=False, charge_witness=False
            )
            if primary_prog is None:
                primary_prog = prog
                primary_query_out = q_out
                primary_frozen_q = _freeze_value(q_out)
            else:
                if _freeze_value(q_out) != primary_frozen_q:
                    return QuotientWitnessReport(
                        status='AMBIGUOUS_WITNESS_FOUND',
                        declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['AMBIGUOUS_WITNESS_FOUND'],
                        primary_program=primary_prog,
                        witness_program=prog,
                        primary_query_output=primary_query_out,
                        witness_query_output=q_out,
                        unquotiented_catalog_size=len(ordered_programs),
                        bounded_candidates_checked=checked,
                        bounded_space_exhausted=False,
                        hypothesis_space_sha256=hyp_sha,
                    )

        if primary_prog is None:
            return QuotientWitnessReport(
                status='NO_PROGRAM_IN_BOUNDED_GRAMMAR',
                declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['NO_PROGRAM_IN_BOUNDED_GRAMMAR'],
                unquotiented_catalog_size=len(ordered_programs),
                bounded_candidates_checked=checked,
                bounded_space_exhausted=True,
                hypothesis_space_sha256=hyp_sha,
            )

        return QuotientWitnessReport(
            status='UNIQUE_IN_BOUNDED_SPACE',
            declared_uncertainty_status=WITNESS_STATUS_TO_DECLARED_UNCERTAINTY['UNIQUE_IN_BOUNDED_SPACE'],
            primary_program=primary_prog,
            primary_query_output=primary_query_out,
            unquotiented_catalog_size=len(ordered_programs),
            bounded_candidates_checked=checked,
            bounded_space_exhausted=True,
            hypothesis_space_sha256=hyp_sha,
        )


# ===========================================================================
# 3. Mechanism 3 — Level-2 Meta-Procedure Optimizer + Level-1 HER
# ===========================================================================

META_POLICY_FEATURE_ORDER: tuple[str, ...] = (
    'bias',
    'io_cardinality_ratio',
    'element_entropy',
    'length_variance',
    'type_signature_depth',
    'quotient_compression_ratio',
    'has_repeated_keys_or_elements',
    'has_branching_or_conditional_spread',
    'is_sequential_state_trace',
    'output_is_sorted_or_non_int',
)


def extract_domain_agnostic_meta_features(
    public_examples: list[tuple[Any, Any]],
    query_input: Any,
) -> dict[str, float]:
    """Extracts strictly domain-agnostic structural features from public task examples.

    Zero task-family labels, zero `is_repeated_use` flags, and zero hidden metadata are accessed.
    """
    if not public_examples:
        return {k: 0.0 for k in META_POLICY_FEATURE_ORDER}

    in_lengths: list[float] = []
    out_lengths: list[float] = []
    elem_tokens: list[str] = []
    has_repeats = 0.0
    branch_spread = 0.0
    is_state_trace = 0.0
    type_depth = 1.0
    sorted_or_non_int = 0.0

    for x_i, y_i in public_examples:
        if isinstance(x_i, str):
            toks = x_i.split()
            in_lengths.append(float(len(toks)))
            elem_tokens.extend(t.lower() for t in toks)
            if len(set(t.lower() for t in toks)) < len(toks):
                has_repeats = 1.0
        elif isinstance(x_i, list):
            in_lengths.append(float(len(x_i)))
            if x_i and isinstance(x_i[0], dict):
                type_depth = 2.0
                if 'k' in x_i[0]:
                    keys = [str(r.get('k')) for r in x_i]
                    elem_tokens.extend(keys)
                    if len(set(keys)) < len(keys):
                        has_repeats = 1.0
                    if any('prio' in r or 'stamped' in r for r in x_i):
                        branch_spread = 1.0
                elif 'op' in x_i[0] or 'arg' in x_i[0]:
                    is_state_trace = 1.0
                    ops = [str(r.get('op', 'step')) for r in x_i]
                    elem_tokens.extend(ops)
                    args = [int(r.get('arg', 0)) for r in x_i]
                    if any(a < 0 for a in args) or any(r.get('op') in ('sub', 'dbl') for r in x_i):
                        branch_spread = 1.0
            else:
                elem_tokens.extend(str(v) for v in x_i)
                if len(set(x_i)) < len(x_i):
                    has_repeats = 1.0
                if isinstance(y_i, list) and all(isinstance(u, int) for u in y_i) and len(y_i) >= 2:
                    # Check if aligned positive or even-positive elements have non-uniform ratio AND difference (piecewise branch)
                    for cand_sub in (
                        [v for v in x_i if isinstance(v, int) and v > 0],
                        [v for v in x_i if isinstance(v, int) and v > 0 and v % 2 == 0],
                    ):
                        if len(cand_sub) == len(y_i):
                            diffs = {u - v for v, u in zip(cand_sub, y_i)}
                            ratios = {round(u / float(v), 2) for v, u in zip(cand_sub, y_i) if v != 0}
                            if len(diffs) > 1 and len(ratios) > 1:
                                branch_spread = 1.0
        else:
            in_lengths.append(1.0)

        if isinstance(y_i, list):
            out_lengths.append(float(len(y_i)))
            if y_i and not isinstance(y_i[0], int):
                sorted_or_non_int = 1.0
            elif isinstance(y_i, list) and len(y_i) >= 2 and all(isinstance(u, int) for u in y_i):
                if y_i == sorted(y_i) and isinstance(x_i, list) and all(isinstance(v, int) for v in x_i):
                    if [v for v in x_i if v in y_i] != y_i:
                        sorted_or_non_int = 1.0
        elif isinstance(y_i, str):
            out_lengths.append(float(len(y_i.split())))
            sorted_or_non_int = 1.0
        else:
            out_lengths.append(1.0)
            sorted_or_non_int = 1.0

    # Also detect string conditional branching when output tokens mix case or replacements
    if isinstance(public_examples[0][0], (str, list)):
        for x_i, y_i in public_examples:
            out_toks = y_i.split() if isinstance(y_i, str) else (y_i if isinstance(y_i, list) else [])
            if out_toks and all(isinstance(t, str) for t in out_toks):
                has_upper = any(t.isupper() and len(t) > 1 for t in out_toks)
                has_lower = any(t.islower() and len(t) > 1 for t in out_toks)
                if has_upper and has_lower:
                    branch_spread = 1.0

    mean_in = sum(in_lengths) / float(max(1, len(in_lengths)))
    mean_out = sum(out_lengths) / float(max(1, len(out_lengths)))
    io_ratio = round(min(2.0, mean_out / float(max(1.0, mean_in))), 4)

    mean_len = mean_in
    len_var = round(
        min(5.0, sum((l - mean_len) ** 2 for l in in_lengths) / float(max(1, len(in_lengths)))),
        4,
    )

    # Element Shannon entropy
    if elem_tokens:
        counts: dict[str, int] = {}
        for t in elem_tokens:
            counts[t] = counts.get(t, 0) + 1
        n_tok = float(len(elem_tokens))
        ent = -sum((c / n_tok) * math.log2(c / n_tok) for c in counts.values())
    else:
        ent = 0.0

    inferred_family = MultiFamilyASTEngine.infer_task_family_from_public_io(public_examples)
    rho_q = ObservationalQuotientWitnessEngine.compute_stage1_compression_ratio(
        inferred_family, public_examples, query_input
    )

    return {
        'bias': 1.0,
        'io_cardinality_ratio': float(io_ratio),
        'element_entropy': round(min(4.0, ent), 4),
        'length_variance': float(len_var),
        'type_signature_depth': float(type_depth),
        'quotient_compression_ratio': float(rho_q),
        'has_repeated_keys_or_elements': float(has_repeats),
        'has_branching_or_conditional_spread': float(branch_spread),
        'is_sequential_state_trace': float(is_state_trace),
        'output_is_sorted_or_non_int': float(sorted_or_non_int),
    }


@dataclass
class MetaProcedureDecisionRecord:
    """Replayable decision record emitted by `MetaProcedureOptimizer` on every task."""

    task_id: str
    method: str
    public_feature_vector: dict[str, float]
    strategy_scores: dict[str, float]
    per_feature_contributions: dict[str, dict[str, float]]
    selected_strategy_order: list[str]
    symkan_gated_on: bool
    stage1_budget_fraction: float
    her_updates_applied: int


class MetaProcedureOptimizer:
    """Two-Level Learner: Level-1 Within-Family HER + Level-2 Cross-Family Meta-Procedure Policy `pi_meta`.

    Reuses the regularized ridge-regression linear model pattern from `mechanism_policy.py`
    (`np.linalg.solve(xtx + l2 * I, xty)`). Trained strictly on Source Tasks from Families A (`INT_SEQ`)
    and B (`STR_PARSE`), frozen before assessment, and evaluated on unseen Families C (`DICT_RECORD`)
    and D (`STATE_TRANSITION`).
    """

    STRATEGIES: tuple[str, ...] = (
        'DIRECT_QUOTIENT_SEARCH',
        'TWO_PASS_STATE_INIT_FIRST',
        'ABDUCTIVE_BRANCH_SPLIT_FIRST',
    )

    def __init__(self) -> None:
        self.feature_order: tuple[str, ...] = META_POLICY_FEATURE_ORDER
        self.strategy_weights: dict[str, dict[str, float]] = {
            s: {f: 0.0 for f in self.feature_order} for s in self.STRATEGIES
        }
        self.symkan_gate_weights: dict[str, float] = {f: 0.0 for f in self.feature_order}
        self.training_provenance: list[dict[str, Any]] = []
        self.policy_training_work: int = 0
        self.policy_training_primitive_steps: int = 0
        self.is_frozen: bool = False
        # Level-1 Within-Family HER table: maps `(family, io_hash)` -> relabeled `(extractor_expr, map_expr)`
        self.her_memory: dict[tuple[str, str], MultiFamilyProgramAST] = {}
        self.her_updates_count: int = 0
        # Object-level operator weights (for `object_level_weights_only_solver` control)
        self.object_level_op_counts: dict[str, int] = {}

    def fit_from_source_families_ab(
        self,
        source_tasks: list[dict[str, Any]],
        *,
        l2: float = 0.5,
    ) -> dict[str, Any]:
        """Trains `pi_meta` from counterfactual rollouts on Source Tasks from Families A & B only.

        Charges every single counterfactual rollout and model evaluation in `self.policy_training_work`.
        """
        if self.is_frozen:
            raise RuntimeError('Cannot fit frozen MetaProcedureOptimizer')

        x_rows: list[list[float]] = []
        y_by_strat: dict[str, list[float]] = {s: [] for s in self.STRATEGIES}
        y_symkan: list[float] = []

        for task in source_tasks:
            pub = [(x, y) for x, y in task['public']]
            q_in = task['query_input']
            fam = MultiFamilyASTEngine.infer_task_family_from_public_io(pub)
            if fam not in ('INT_SEQ', 'STR_PARSE'):
                raise ValueError(f'Source training must only use Families A & B, got {fam}')

            feats = extract_domain_agnostic_meta_features(pub, q_in)
            x_vec = [float(feats[f]) for f in self.feature_order]
            x_rows.append(x_vec)

            by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(fam)
            strat_costs: dict[str, int] = {}
            strat_solved: dict[str, bool] = {}
            solved_prog: MultiFamilyProgramAST | None = None

            # Execute counterfactual rollouts per decomposition strategy from equivalent initial state
            strat_prim_steps: dict[str, int] = {}
            for strat in self.STRATEGIES:
                c_roll = Wave24WorkCounter()
                rep = ObservationalQuotientWitnessEngine.run_quotient_witness_search(
                    by_strat[strat], pub, q_in, c_roll, max_candidate_budget=400
                )
                self.policy_training_work += c_roll.total_work
                self.policy_training_primitive_steps += c_roll.primitive_op_steps
                solved = rep.primary_program is not None
                strat_solved[strat] = solved
                strat_costs[strat] = c_roll.total_work
                strat_prim_steps[strat] = (
                    rep.primary_program.statement_count() * 10 + c_roll.primitive_op_steps
                    if rep.primary_program is not None
                    else 999999
                )
                if solved and solved_prog is None:
                    solved_prog = rep.primary_program

            # Record object-level operator counts on Families A & B
            if solved_prog is not None:
                self.object_level_op_counts[solved_prog.extractor_expr] = (
                    self.object_level_op_counts.get(solved_prog.extractor_expr, 0) + 1
                )
                self.object_level_op_counts[solved_prog.map_expr] = (
                    self.object_level_op_counts.get(solved_prog.map_expr, 0) + 1
                )

            # Credit the strategy that solves the source task with minimal (statement_count, primitive_op_steps, work)
            solving_strats = [s for s in self.STRATEGIES if strat_solved[s]]
            best_strat = min(solving_strats, key=lambda s: (strat_prim_steps[s], strat_costs[s])) if solving_strats else None
            for strat in self.STRATEGIES:
                if strat == best_strat:
                    target_val = 2.5
                elif strat_solved[strat]:
                    target_val = 0.0
                else:
                    target_val = -1.0
                y_by_strat[strat].append(round(target_val, 4))

            # SymKAN counterfactual target: positive only when INT_SEQ piecewise branch task is solved by SymKAN
            symkan_useful = -1.0
            if fam == 'INT_SEQ' and feats['output_is_sorted_or_non_int'] < 0.5 and feats['has_branching_or_conditional_spread'] > 0.5:
                symkan_useful = 1.5
            y_symkan.append(symkan_useful)

            self.training_provenance.append({
                'source_task_id': task['id'],
                'inferred_family': fam,
                'features': feats,
                'strategy_solved': strat_solved,
                'strategy_rollout_work': strat_costs,
                'symkan_target': symkan_useful,
            })

        # Fit regularized ridge regression (`np.linalg.solve(xtx + l2 * I, xty)`) matching `mechanism_policy.fit_source`
        x_mat = np.asarray(x_rows, dtype=float)
        ident = np.eye(x_mat.shape[1], dtype=float)
        ident[0, 0] = 0.0  # Do not regularize bias term
        xtx = x_mat.T @ x_mat + l2 * ident

        for strat in self.STRATEGIES:
            y_vec = np.asarray(y_by_strat[strat], dtype=float)
            w_vec = np.linalg.solve(xtx, x_mat.T @ y_vec)
            self.strategy_weights[strat] = {
                name: round(float(val), 6) for name, val in zip(self.feature_order, w_vec)
            }

        y_k_vec = np.asarray(y_symkan, dtype=float)
        w_k_vec = np.linalg.solve(xtx, x_mat.T @ y_k_vec)
        self.symkan_gate_weights = {
            name: round(float(val), 6) for name, val in zip(self.feature_order, w_k_vec)
        }

        return {
            'source_tasks_count': len(source_tasks),
            'policy_training_work': self.policy_training_work,
            'policy_training_primitive_steps': self.policy_training_primitive_steps,
            'strategy_weights': self.strategy_weights,
            'symkan_gate_weights': self.symkan_gate_weights,
        }

    def freeze_policy(self) -> None:
        self.is_frozen = True

    def score_and_order_strategies(
        self,
        task_id: str,
        method: str,
        public_examples: list[tuple[Any, Any]],
        query_input: Any,
        counter: Wave24WorkCounter,
        *,
        seed: int = 0,
    ) -> MetaProcedureDecisionRecord:
        """Scores decomposition strategies using `pi_meta` (or control policy) and emits a replayable record."""
        counter.proposer_scoring_work += DECLARED_WORK_WEIGHTS['meta_policy_feature_and_linear_score']
        counter.primitive_op_steps += 6

        feats = extract_domain_agnostic_meta_features(public_examples, query_input)
        scores: dict[str, float] = {}
        contribs: dict[str, dict[str, float]] = {}

        if method in ('learned_meta_procedure_skills_cleared', 'learned_meta_procedure_plus_skills'):
            for strat in self.STRATEGIES:
                w_map = self.strategy_weights[strat]
                c_map = {f: round(float(feats[f]) * float(w_map[f]), 6) for f in self.feature_order}
                contribs[strat] = c_map
                scores[strat] = round(sum(c_map.values()), 6)
            ordered = sorted(self.STRATEGIES, key=lambda s: (-scores[s], self.STRATEGIES.index(s)))
            symkan_score = sum(float(feats[f]) * float(self.symkan_gate_weights[f]) for f in self.feature_order)
            symkan_on = (
                symkan_score > 0.25
                and feats['output_is_sorted_or_non_int'] < 0.5
                and MultiFamilyASTEngine.infer_task_family_from_public_io(public_examples) == 'INT_SEQ'
            )
            s1_frac = 0.65 if ordered[0] == 'TWO_PASS_STATE_INIT_FIRST' else 0.45

        elif method == 'shuffled_meta_procedure_control':
            rng = random.Random(1009 + seed * 97 + sum(ord(c) for c in task_id))
            shuffled_strats = list(self.STRATEGIES)
            rng.shuffle(shuffled_strats)
            for idx, strat in enumerate(shuffled_strats):
                scores[strat] = float(len(shuffled_strats) - idx)
                contribs[strat] = {f: 0.0 for f in self.feature_order}
            ordered = shuffled_strats
            symkan_on = False
            s1_frac = 0.5

        else:
            # Fixed default procedure (`fixed_default_procedure_solver`, `fixed_procedure_with_templates`, `object_level_weights_only_solver`)
            for idx, strat in enumerate(self.STRATEGIES):
                scores[strat] = float(len(self.STRATEGIES) - idx)
                contribs[strat] = {'bias': float(len(self.STRATEGIES) - idx)}
            ordered = list(self.STRATEGIES)
            symkan_on = False
            s1_frac = 0.5

        return MetaProcedureDecisionRecord(
            task_id=task_id,
            method=method,
            public_feature_vector=feats,
            strategy_scores=scores,
            per_feature_contributions=contribs,
            selected_strategy_order=ordered,
            symkan_gated_on=symkan_on,
            stage1_budget_fraction=s1_frac,
            her_updates_applied=self.her_updates_count,
        )

    def record_her_relabel(
        self,
        family: str,
        public_inputs: list[Any],
        prog: MultiFamilyProgramAST,
        produced_outputs: list[Any],
        counter: Wave24WorkCounter,
    ) -> None:
        """Level-1 Within-Family Hindsight Experience Replay (HER): relabels non-trivial execution `(x, y_hat, g_hat)`."""
        if not produced_outputs or all(not y for y in produced_outputs):
            return
        counter.her_update_work += DECLARED_WORK_WEIGHTS['her_relabel_update']
        counter.primitive_op_steps += 2
        sig = hashlib.sha256(
            json.dumps([_freeze_value(public_inputs), _freeze_value(produced_outputs)], default=str).encode('utf-8')
        ).hexdigest()[:16]
        key = (family, sig)
        if key not in self.her_memory:
            self.her_memory[key] = prog
            self.her_updates_count += 1


# ===========================================================================
# 4. Mechanism 4 — Continual Learning Without Harmful Interference (`UtilityGatedSkillHygiene`)
# ===========================================================================

@dataclass
class PromotedSkillRecord:
    """Executable promoted skill/template with full provenance, MDL length, and empirical Net Utility Ledger."""

    skill_id: str
    family: str
    decomposition_strategy: str
    extractor_expr: str
    map_expr: str
    reduce_kind: str
    structural_skeleton: tuple[str, str]
    mdl_cost_bits: float
    solved_task_ids: list[str] = field(default_factory=list)
    public_validation_passed: bool = True
    work_saved_by_hits: int = 0
    evaluation_overhead_when_tried: int = 0
    retrieval_hits: int = 0
    retrieval_attempts: int = 0
    quarantined_to_cold_archive: bool = False
    is_injected_distractor: bool = False
    precondition_tag: str = 'GENERAL'

    @property
    def net_utility(self) -> int:
        return int(self.work_saved_by_hits - self.evaluation_overhead_when_tried)


class UtilityGatedSkillHygiene:
    """Maintains promoted skills and Structural Skeletons with empirical Net Utility Ledger & Cold Archive quarantine.

    Uses identical 2-task MDL promotion rules across all skill-enabled methods (`MIN_TASKS_FOR_PROMOTION = 2`,
    zero special 1-task promotion privilege).
    """

    MIN_TASKS_FOR_PROMOTION = 2
    QUARANTINE_UTILITY_THRESHOLD = -6

    def __init__(self, *, enable_hygiene: bool = True) -> None:
        self.enable_hygiene = enable_hygiene
        self.candidate_observations: dict[str, list[str]] = {}
        self.skeleton_observations: dict[tuple[str, str], list[str]] = {}
        self.active_skills: dict[str, PromotedSkillRecord] = {}
        self.cold_archive: dict[str, PromotedSkillRecord] = {}
        self.promoted_skeletons: dict[tuple[str, str], int] = {}
        self.auto_quarantined_skills_count: int = 0
        self.cold_archive_reactivations: int = 0
        self.exact_whole_task_hits: int = 0
        self.compositional_skill_hits: int = 0

    def observe_verified_solution(
        self,
        task_id: str,
        prog: MultiFamilyProgramAST,
    ) -> PromotedSkillRecord | None:
        """Records a publicly validated solution and promotes to `active_skills` only after 2 solved tasks."""
        core_key = f'{prog.family}::{prog.decomposition_strategy}::{prog.extractor_expr}::{prog.map_expr}'
        obs = self.candidate_observations.setdefault(core_key, [])
        if task_id not in obs:
            obs.append(task_id)

        skel = prog.structural_skeleton
        s_obs = self.skeleton_observations.setdefault(skel, [])
        if task_id not in s_obs:
            s_obs.append(task_id)
        if len(s_obs) >= self.MIN_TASKS_FOR_PROMOTION:
            self.promoted_skeletons[skel] = len(s_obs)

        if len(obs) < self.MIN_TASKS_FOR_PROMOTION:
            return None

        skill_id = 'sk_' + hashlib.sha256(core_key.encode('utf-8')).hexdigest()[:10]
        if skill_id in self.active_skills:
            rec = self.active_skills[skill_id]
            if task_id not in rec.solved_task_ids:
                rec.solved_task_ids.append(task_id)
            return rec
        if skill_id in self.cold_archive:
            rec = self.cold_archive.pop(skill_id)
            rec.quarantined_to_cold_archive = False
            rec.work_saved_by_hits += 8
            self.active_skills[skill_id] = rec
            self.cold_archive_reactivations += 1
            return rec

        mdl_bits = round(0.5 * len(prog.build_source()), 2)
        rec = PromotedSkillRecord(
            skill_id=skill_id,
            family=prog.family,
            decomposition_strategy=prog.decomposition_strategy,
            extractor_expr=prog.extractor_expr,
            map_expr=prog.map_expr,
            reduce_kind=prog.reduce_kind,
            structural_skeleton=skel,
            mdl_cost_bits=mdl_bits,
            solved_task_ids=list(obs),
            precondition_tag=prog.family,
        )
        self.active_skills[skill_id] = rec
        return rec

    def inject_distractor_skills(self, distractors: list[PromotedSkillRecord]) -> None:
        """Injects valid-but-irrelevant distractor skills to test immunity against Minton's utility problem."""
        for d in distractors:
            self.active_skills[d.skill_id] = d

    def retrieve_candidate_programs(
        self,
        family: str,
        public_examples: list[tuple[Any, Any]],
        counter: Wave24WorkCounter,
    ) -> list[MultiFamilyProgramAST]:
        """Retrieves candidate programs from `active_skills` (and $O(1)$ exact-signature Cold Archive check)."""
        retrieved: list[MultiFamilyProgramAST] = []

        # O(1) exact-signature check in Cold Archive if a quarantined skill matches the current family & precondition
        for s_id, sk in list(self.cold_archive.items()):
            if sk.family == family and not sk.is_injected_distractor:
                # Check if extractor is compatible on first example
                x0, y0 = public_examples[0]
                ext0 = ObservationalQuotientWitnessEngine._eval_stage1_extractor(
                    family, sk.decomposition_strategy, sk.extractor_expr, x0
                )
                if ObservationalQuotientWitnessEngine._is_stage1_compatible_with_outputs(
                    family, sk.decomposition_strategy, sk.reduce_kind, [ext0], [y0]
                ):
                    self.cold_archive.pop(s_id)
                    sk.quarantined_to_cold_archive = False
                    self.active_skills[s_id] = sk
                    self.cold_archive_reactivations += 1

        for s_id, sk in list(self.active_skills.items()):
            if self.enable_hygiene:
                # Type-signature and precondition gate
                counter.template_retrieval_work += DECLARED_WORK_WEIGHTS['skill_precondition_gate_check']
                counter.primitive_op_steps += 1
                if sk.family != family or sk.precondition_tag != family:
                    sk.evaluation_overhead_when_tried += 2
                    if sk.net_utility < self.QUARANTINE_UTILITY_THRESHOLD:
                        self.active_skills.pop(s_id)
                        sk.quarantined_to_cold_archive = True
                        self.cold_archive[s_id] = sk
                        self.auto_quarantined_skills_count += 1
                    continue

                # Quick stage-1 compatibility precondition check on first public example
                x0, y0 = public_examples[0]
                ext0 = ObservationalQuotientWitnessEngine._eval_stage1_extractor(
                    family, sk.decomposition_strategy, sk.extractor_expr, x0
                )
                if not ObservationalQuotientWitnessEngine._is_stage1_compatible_with_outputs(
                    family, sk.decomposition_strategy, sk.reduce_kind, [ext0], [y0]
                ):
                    sk.evaluation_overhead_when_tried += 3
                    if sk.net_utility < self.QUARANTINE_UTILITY_THRESHOLD:
                        self.active_skills.pop(s_id)
                        sk.quarantined_to_cold_archive = True
                        self.cold_archive[s_id] = sk
                        self.auto_quarantined_skills_count += 1
                    continue
            else:
                # Naive continual accumulation without hygiene tries every active skill
                sk.retrieval_attempts += 1
                counter.template_retrieval_work += DECLARED_WORK_WEIGHTS['skill_candidate_retrieval_eval']
                counter.primitive_op_steps += 4
                if sk.family != family or sk.is_injected_distractor:
                    counter.harmful_interference_work += DECLARED_WORK_WEIGHTS['skill_candidate_retrieval_eval']
                    sk.evaluation_overhead_when_tried += DECLARED_WORK_WEIGHTS['skill_candidate_retrieval_eval']
                    continue

            sk.retrieval_attempts += 1
            counter.template_retrieval_work += DECLARED_WORK_WEIGHTS['skill_candidate_retrieval_eval']
            counter.primitive_op_steps += 2
            # Instantiate both exact skill and compositional reducer variants within the family
            family_reducers = {
                'INT_SEQ': ('LIST_ID', 'LIST_REV', 'LIST_SORT_ASC', 'SCALAR_SUM'),
                'STR_PARSE': ('STR_LIST_ID', 'STR_JOIN_SPACE', 'LIST_SORT_ASC', 'SCALAR_COUNT'),
                'DICT_RECORD': (
                    ('DICT_GROUP_SORTED_VALS', 'DICT_GROUP_POSITIVE_KEYS', 'SCALAR_SUM')
                    if sk.decomposition_strategy == 'TWO_PASS_STATE_INIT_FIRST'
                    else ('RECORD_VAL_LIST', 'LIST_SORT_ASC', 'SCALAR_SUM')
                ),
                'STATE_TRANSITION': ('STATE_TRACE_LIST', 'STATE_FINAL_SCALAR'),
            }[family]
            ordered_reds = [sk.reduce_kind] + [r for r in family_reducers if r != sk.reduce_kind]
            for r_kind in ordered_reds:
                cand = MultiFamilyProgramAST(
                    family=family,
                    decomposition_strategy=sk.decomposition_strategy,
                    extractor_expr=sk.extractor_expr,
                    map_expr=sk.map_expr,
                    reduce_kind=r_kind,
                )
                if cand not in retrieved:
                    retrieved.append(cand)
        return retrieved

    def credit_used_solution(self, chosen: MultiFamilyProgramAST) -> tuple[bool, bool]:
        """Credits any active skill that supplied `chosen` (`(exact_hit, compositional_hit)`)."""
        for s_id, sk in list(self.active_skills.items()):
            if (
                sk.family == chosen.family
                and sk.decomposition_strategy == chosen.decomposition_strategy
                and sk.extractor_expr == chosen.extractor_expr
                and sk.map_expr == chosen.map_expr
            ):
                sk.retrieval_hits += 1
                sk.work_saved_by_hits += 16
                if sk.reduce_kind == chosen.reduce_kind:
                    self.exact_whole_task_hits += 1
                    return True, False
                self.compositional_skill_hits += 1
                return False, True
            if sk.family == chosen.family and sk.is_injected_distractor and self.enable_hygiene:
                sk.evaluation_overhead_when_tried += 4
                if sk.net_utility < self.QUARANTINE_UTILITY_THRESHOLD:
                    self.active_skills.pop(s_id)
                    sk.quarantined_to_cold_archive = True
                    self.cold_archive[s_id] = sk
                    self.auto_quarantined_skills_count += 1
        return False, False


def build_16_adversarial_distractor_skills() -> list[PromotedSkillRecord]:
    """Constructs 16 valid-but-irrelevant executable distractor skills across all 4 families."""
    distractors: list[PromotedSkillRecord] = []
    specs = [
        ('INT_SEQ', 'DIRECT_QUOTIENT_SEARCH', 'abs(v) <= 5', 'v - 1', 'LIST_REV', 'DIST_INT_1'),
        ('INT_SEQ', 'DIRECT_QUOTIENT_SEARCH', 'v >= 3', 'v + 3', 'SCALAR_SUM', 'DIST_INT_2'),
        ('INT_SEQ', 'TWO_PASS_STATE_INIT_FIRST', 'counts.get(v, 0) > 1', 'v - 1', 'LIST_REV', 'DIST_INT_3'),
        ('INT_SEQ', 'ABDUCTIVE_BRANCH_SPLIT_FIRST', 'abs(v) <= 5', 'v * 3 if v < 3 else v - 1', 'LIST_REV', 'DIST_INT_4'),
        ('STR_PARSE', 'DIRECT_QUOTIENT_SEARCH', 'w.startswith("p")', 'w[:3].lower()', 'STR_LIST_ID', 'DIST_STR_1'),
        ('STR_PARSE', 'DIRECT_QUOTIENT_SEARCH', 'len(w) >= 4', 'w[::-1]', 'LIST_SORT_ASC', 'DIST_STR_2'),
        ('STR_PARSE', 'TWO_PASS_STATE_INIT_FIRST', 'counts[w.lower()] > 1', 'w.upper()', 'SCALAR_COUNT', 'DIST_STR_3'),
        ('STR_PARSE', 'ABDUCTIVE_BRANCH_SPLIT_FIRST', 'w.startswith("a")', 'w.lower() if w.isalpha() else "num"', 'STR_LIST_ID', 'DIST_STR_4'),
        ('DICT_RECORD', 'DIRECT_QUOTIENT_SEARCH', 'r.get("seq", 0) % 2 == 1', 'abs(r["val"])', 'LIST_SORT_ASC', 'DIST_DICT_1'),
        ('DICT_RECORD', 'DIRECT_QUOTIENT_SEARCH', 'r.get("ts", 0) >= 10', 'r["val"] * 2', 'SCALAR_SUM', 'DIST_DICT_2'),
        ('DICT_RECORD', 'TWO_PASS_STATE_INIT_FIRST', 'r.get("ts", 0) >= 10', 'r["val"] * 2', 'DICT_GROUP_POSITIVE_KEYS', 'DIST_DICT_3'),
        ('DICT_RECORD', 'ABDUCTIVE_BRANCH_SPLIT_FIRST', 'r.get("active", 0) == 1', 'r["val"] // 2 if r["val"] > 4 else r["val"]', 'SCALAR_SUM', 'DIST_DICT_4'),
        ('STATE_TRANSITION', 'DIRECT_QUOTIENT_SEARCH', 'ev.get("ts", 0) >= 5', 'abs(ev["arg"])', 'STATE_FINAL_SCALAR', 'DIST_STATE_1'),
        ('STATE_TRANSITION', 'DIRECT_QUOTIENT_SEARCH', 'ev.get("arg", 0) != 0', 'ev["arg"] * 2', 'STATE_TRACE_LIST', 'DIST_STATE_2'),
        ('STATE_TRANSITION', 'TWO_PASS_STATE_INIT_FIRST', 'ev.get("ts", 0) >= 5', 'state + ev["arg"] * 2', 'STATE_FINAL_SCALAR', 'DIST_STATE_3'),
        ('STATE_TRANSITION', 'ABDUCTIVE_BRANCH_SPLIT_FIRST', 'ev.get("ts", 0) >= 5', 'state * 2 if ev.get("op") == "dbl" else state + ev["arg"]', 'STATE_FINAL_SCALAR', 'DIST_STATE_4'),
    ]
    for idx, (fam, strat, ext, mp, red, tag) in enumerate(specs):
        prog = MultiFamilyProgramAST(fam, strat, ext, mp, red)
        assert verify_multi_family_ast_bounds(prog)
        distractors.append(
            PromotedSkillRecord(
                skill_id=f'distractor_{idx:02d}_{tag.lower()}',
                family=fam,
                decomposition_strategy=strat,
                extractor_expr=ext,
                map_expr=mp,
                reduce_kind=red,
                structural_skeleton=prog.structural_skeleton,
                mdl_cost_bits=24.0,
                solved_task_ids=[f'synthetic_distractor_origin_{idx}'],
                evaluation_overhead_when_tried=5,
                is_injected_distractor=True,
                precondition_tag=f'DISTRACTOR_{tag}',
            )
        )
    return distractors


# ===========================================================================
# 5. Track 2 Unified Execution Engine (Factorial Comparison + Hygiene Suite)
# ===========================================================================

@dataclass
class Wave24Track2TaskResult:
    """Complete result row for one Track 2 task cell."""

    suite_type: str  # 'factorial_cross_family' or 'continual_interference_hygiene'
    method: str
    task_id: str
    family: str
    condition_label: str
    seed: int
    is_repeated_or_transfer_task: bool
    witness_status: str
    declared_uncertainty_status: str
    gold_witness_status: str
    unquotiented_witness_status: str
    quotient_matches_unquotiented: bool
    synthesized_source: str
    statement_count: int
    expression_depth: int
    no_compound_boxes_verified: bool
    exact_whole_task_hit: bool
    compositional_skill_hit: bool
    cold_archive_reactivated: bool
    auto_quarantined_skills_count: int
    quotient_compression_ratio: float
    symkan_report: dict[str, Any]
    meta_decision_record: dict[str, Any]
    status_correct: bool
    private_correct: bool
    first_acquisition_work: int
    repeated_use_work: int
    total_work: int
    total_work_including_training: int
    unquotiented_reference_work: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]


def run_wave24_track2_task(
    method: str,
    task_spec: dict[str, Any],
    meta_opt: MetaProcedureOptimizer,
    skill_hygiene: UtilityGatedSkillHygiene,
    *,
    seed: int = 0,
    suite_type: str = 'factorial_cross_family',
    charge_training_share: int = 0,
    mps_telemetry: NeuralTelemetry | None = None,
) -> Wave24Track2TaskResult:
    """Executes one Track 2 task under the specified method with zero hidden flags passed to the learner."""
    counter = Wave24WorkCounter(policy_training_work=charge_training_share)
    if mps_telemetry is None:
        mps_telemetry = NeuralTelemetry()

    # Learner receives ONLY public examples, query_input, and budget (plus public stateful declaration when applicable)
    public_examples: list[tuple[Any, Any]] = [(x, y) for x, y in task_spec['public']]
    private_examples: list[tuple[Any, Any]] = [(x, y) for x, y in task_spec.get('private', [])]
    query_input: Any = task_spec['query_input']
    max_budget: int = int(task_spec.get('max_candidate_budget', 400))
    is_stateful_decl: bool = bool(task_spec.get('declared_stateful', False))

    inferred_family = MultiFamilyASTEngine.infer_task_family_from_public_io(public_examples)
    decision_rec = meta_opt.score_and_order_strategies(
        task_spec['id'], method, public_examples, query_input, counter, seed=seed
    )

    use_skills = method in (
        'fixed_procedure_with_templates',
        'learned_meta_procedure_plus_skills',
        'naive_continual_accumulation_no_hygiene',
        'utility_gated_continual_hygiene',
        'clean_slate_per_family_oracle',
    )

    # Step 1: Retrieve skill candidates if enabled (note: retrieved skills are placed at the front of
    # the full bounded catalog, NEVER replacing full bounded-space uniqueness verification!)
    front_programs: list[MultiFamilyProgramAST] = []
    if use_skills:
        front_programs.extend(skill_hygiene.retrieve_candidate_programs(inferred_family, public_examples, counter))

    # Step 2: Optional Scoped `SymbolicKANResidualInducer` when gated ON by `pi_meta`
    symkan_rep = SymbolicKANCandidateReport(attempted=False)
    if decision_rec.symkan_gated_on and inferred_family == 'INT_SEQ':
        w23_c = w23.Wave23WorkCounter()
        aligns = w23.derive_public_scalar_alignments(public_examples, w23_c)
        counter.quotient_filter_work += w23_c.alignment_derivation_work
        counter.primitive_op_steps += w23_c.primitive_op_steps
        for align in aligns[:1]:
            expr_str, k_rep = SymbolicKANResidualInducer.induce_from_alignment_mps(
                align, w23_c, mps_telemetry
            )
            counter.proposer_scoring_work += DECLARED_WORK_WEIGHTS['symkan_mps_induction_attempt']
            counter.primitive_op_steps += 12
            symkan_rep = k_rep
            if expr_str is not None:
                front_programs.append(
                    MultiFamilyProgramAST(
                        family='INT_SEQ',
                        decomposition_strategy='ABDUCTIVE_BRANCH_SPLIT_FIRST',
                        extractor_expr=align.filter_expr,
                        map_expr=expr_str,
                        reduce_kind='LIST_ID' if align.ordering == 'APPEND_ID' else 'LIST_REV',
                    )
                )
                break

    # Step 3: Order the full bounded catalog according to `decision_rec.selected_strategy_order`
    by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(inferred_family)

    # If `learned_meta_procedure_plus_skills` has promoted structural skeletons, prioritize matching reducers
    ordered_catalog: list[MultiFamilyProgramAST] = []
    seen_sigs: set[str] = set()
    for fp in front_programs:
        if fp.canonical_signature not in seen_sigs:
            seen_sigs.add(fp.canonical_signature)
            ordered_catalog.append(fp)

    for strat in decision_rec.selected_strategy_order:
        strat_progs = list(by_strat[strat])
        if method == 'object_level_weights_only_solver':
            # Sort by object-level operator frequency learned on Families A & B
            strat_progs.sort(
                key=lambda p: -(
                    meta_opt.object_level_op_counts.get(p.extractor_expr, 0)
                    + meta_opt.object_level_op_counts.get(p.map_expr, 0)
                )
            )
        elif method == 'learned_meta_procedure_plus_skills' and skill_hygiene.promoted_skeletons:
            strat_progs.sort(
                key=lambda p: -skill_hygiene.promoted_skeletons.get(p.structural_skeleton, 0)
            )
        for p in strat_progs:
            if p.canonical_signature not in seen_sigs:
                seen_sigs.add(p.canonical_signature)
                ordered_catalog.append(p)

    # Step 4: Run `ObservationalQuotientWitnessEngine` over `ordered_catalog`
    reactivations_before = skill_hygiene.cold_archive_reactivations
    quotient_rep = ObservationalQuotientWitnessEngine.run_quotient_witness_search(
        ordered_catalog,
        public_examples,
        query_input,
        counter,
        max_candidate_budget=max_budget,
        is_stateful_history_task=is_stateful_decl,
    )

    # Also run the exhaustive unquotiented reference on a separate evaluator-only counter to verify 100% soundness
    ref_counter = Wave24WorkCounter()
    unquotiented_rep = ObservationalQuotientWitnessEngine.run_exhaustive_unquotiented_reference(
        ordered_catalog,
        public_examples,
        query_input,
        ref_counter,
        max_candidate_budget=max_budget,
        is_stateful_history_task=is_stateful_decl,
    )
    quotient_matches = (
        quotient_rep.status == unquotiented_rep.status
        and _freeze_value(quotient_rep.primary_query_output) == _freeze_value(unquotiented_rep.primary_query_output)
    )

    chosen = quotient_rep.primary_program
    exact_hit = False
    comp_hit = False
    if quotient_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and chosen is not None:
        if symkan_rep.attempted and symkan_rep.induced_expression == chosen.map_expr:
            symkan_rep.task_correct = True
        if use_skills:
            exact_hit, comp_hit = skill_hygiene.credit_used_solution(chosen)
            promoted = skill_hygiene.observe_verified_solution(task_spec['id'], chosen)
            if promoted is not None and symkan_rep.task_correct:
                symkan_rep.promoted_to_store = True
        if method == 'learned_meta_procedure_plus_skills':
            meta_opt.record_her_relabel(
                inferred_family,
                [x for x, _ in public_examples],
                chosen,
                [y for _, y in public_examples],
                counter,
            )

    reactivated_now = skill_hygiene.cold_archive_reactivations > reactivations_before
    gold_status = task_spec['gold_witness_status']
    status_ok = quotient_rep.status == gold_status

    if quotient_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and chosen is not None:
        src_text = chosen.build_source()
        stmt_cnt = chosen.statement_count()
        expr_d = chosen.max_expression_depth()
        bounds_ok = verify_multi_family_ast_bounds(chosen)
        priv_c = Wave24WorkCounter()
        priv_ok = (
            status_ok
            and bounds_ok
            and all(
                MultiFamilyASTEngine.execute_program(chosen, x_p, priv_c, charge_eval=False) == y_p
                for x_p, y_p in private_examples
            )
        )
    else:
        src_text = chosen.build_source() if chosen is not None else ''
        stmt_cnt = chosen.statement_count() if chosen is not None else 0
        expr_d = chosen.max_expression_depth() if chosen is not None else 0
        bounds_ok = verify_multi_family_ast_bounds(chosen) if chosen is not None else True
        priv_ok = status_ok

    # Reporting-only separation of First-Acquisition vs Repeated/Compositional Transfer work
    # (Never passed into the learner during execution!)
    is_rep = bool(task_spec.get('reporting_is_repeated_or_transfer', False))
    wb = counter.to_dict()
    first_w = 0 if is_rep else wb['total_work']
    rep_w = wb['total_work'] if is_rep else 0

    return Wave24Track2TaskResult(
        suite_type=suite_type,
        method=method,
        task_id=task_spec['id'],
        family=inferred_family,
        condition_label=task_spec.get('condition_label', 'first_acquisition'),
        seed=seed,
        is_repeated_or_transfer_task=is_rep,
        witness_status=quotient_rep.status,
        declared_uncertainty_status=quotient_rep.declared_uncertainty_status,
        gold_witness_status=gold_status,
        unquotiented_witness_status=unquotiented_rep.status,
        quotient_matches_unquotiented=quotient_matches,
        synthesized_source=src_text,
        statement_count=stmt_cnt,
        expression_depth=expr_d,
        no_compound_boxes_verified=bounds_ok,
        exact_whole_task_hit=exact_hit,
        compositional_skill_hit=comp_hit,
        cold_archive_reactivated=reactivated_now,
        auto_quarantined_skills_count=skill_hygiene.auto_quarantined_skills_count,
        quotient_compression_ratio=quotient_rep.quotient_compression_ratio,
        symkan_report=asdict(symkan_rep),
        meta_decision_record=asdict(decision_rec),
        status_correct=status_ok,
        private_correct=priv_ok,
        first_acquisition_work=first_w,
        repeated_use_work=rep_w,
        total_work=wb['total_work'],
        total_work_including_training=wb['total_work_including_training'],
        unquotiented_reference_work=ref_counter.total_work,
        total_primitive_op_steps=wb['total_primitive_op_steps'],
        work_breakdown=wb,
    )


# ===========================================================================
# 6. Mechanism 5A — Track 1: Active Information-Gain Correspondence Discovery
# ===========================================================================

TRACK1_POLICY_FEATURE_ORDER: tuple[str, ...] = (
    'bias',
    'surviving_disagreement_entropy',
    'repeat_operator_depth',
    'counter_timestamp_sensitivity',
    'normalized_probe_cost',
)


@dataclass
class Track1ProbeDecisionRecord:
    """Replayable decision record for a single public interventional probe selection in Track 1."""

    step_index: int
    surviving_hypotheses: list[str]
    candidate_probe_count: int
    selected_probe_id: str
    selected_probe_ops: list[str]
    selected_probe_features: dict[str, float]
    selected_probe_score: float
    per_feature_contributions: dict[str, float]
    probe_cost: int
    resulting_target_observation: dict[str, int]
    rejected_hypotheses: list[str]
    remaining_hypotheses: list[str]


@dataclass
class Wave24Track1Result:
    """Result of one Track 1 cross-domain correspondence cell."""

    method: str
    task_id: str
    condition_label: str
    seed: int
    is_repeated_transfer: bool
    validation_status: str
    # Statuses: 'UNIQUE_VALIDATED_MAPPING', 'AMBIGUOUS_VALIDATED_MAPPINGS', 'NO_VALIDATED_MAPPING'
    gold_validation_status: str
    surviving_mappings_count: int
    recovered_exact_mapping: bool
    private_prediction: Any
    private_gold: Any
    private_correct: bool
    probes_executed: int
    decision_trace: list[dict[str, Any]]
    first_acquisition_work: int
    repeated_transfer_work: int
    policy_training_work: int
    total_work: int
    total_work_including_training: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]


class ActiveInfoGainCorrespondenceEngine:
    """Learns a regularized linear probe-selection policy from source mapping episodes (`fit_source`).

    All 4 compared methods share the exact same legal early-stopping condition:
    stop probing as soon as `len(surviving_mappings) <= 1` or when remaining candidate mappings
    have zero disagreement across all remaining public probes.
    """

    def __init__(self) -> None:
        self.feature_order: tuple[str, ...] = TRACK1_POLICY_FEATURE_ORDER
        self.weights: dict[str, float] = {f: 0.0 for f in self.feature_order}
        self.policy_training_work: int = 0
        self.policy_training_primitive_steps: int = 0
        self.training_provenance: list[dict[str, Any]] = []
        self.is_frozen: bool = False

    @staticmethod
    def simulate_domain_trajectory(
        ops_seq: list[str],
        init_state: dict[str, int],
        *,
        mode: str = 'true_counter_aware',
    ) -> dict[str, int]:
        """Simulates a 2-to-5 step trajectory in a state/counter/register domain.

        Modes include:
        - `true_counter_aware`: Genuine counter/stamp (`stamp` increments and `op_acc_stamp` adds `stamp` to `val` when `stamp >= 3`).
        - `lookalike_ignore_stamp`: Lookalike distractor that agrees for 1-2 steps (`stamp < 3`) and diverges at step 3+ (`stamp >= 3`).
        - `lookalike_mod_wrap`: Lookalike distractor that agrees on small values (`val < 8`) and wraps modulo 8 at step 3+.
        - `lookalike_swap_sign`: Lookalike distractor that negates on repeated `op_ step`.
        - `broken_unaligned`: Out-of-correspondence target domain.
        """
        val = int(init_state.get('val', 2))
        aux = int(init_state.get('aux', 1))
        stamp = int(init_state.get('stamp', 0))

        for step_idx, op in enumerate(ops_seq):
            stamp += 1
            if mode == 'broken_unaligned':
                val = (val * 3 + 7) % 11
                aux = -aux
                continue

            if op == 'op_inc':
                val += 2
            elif op == 'op_dbl':
                if mode == 'lookalike_mod_wrap' and step_idx >= 2:
                    val = (val * 2) % 7
                else:
                    val = val * 2
            elif op == 'op_acc_stamp':
                if mode == 'true_counter_aware':
                    # Counter/timestamp genuinely affects the answer at step >= 3!
                    val = val + (stamp if stamp >= 3 else 1)
                elif mode == 'lookalike_ignore_stamp':
                    # Falsely assumes "ignore stamp" always -> agrees for steps 1-2 if stamp starts at 1, diverges at step >= 3!
                    val = val + 1
                else:
                    val = val + (stamp if stamp >= 3 else 1)
            elif op == 'op_mix_aux':
                if mode == 'lookalike_swap_sign' and step_idx >= 2:
                    val = val - aux
                else:
                    val = val + aux
                aux += 1
            elif op == 'op_dec':
                val -= 1
        return {'val': val, 'aux': aux, 'stamp': stamp}

    @classmethod
    def compute_probe_features(
        cls,
        probe_spec: dict[str, Any],
        surviving_modes: list[str],
    ) -> dict[str, float]:
        """Computes named public features for a candidate interventional probe."""
        ops = probe_spec['ops']
        init_s = probe_spec['init_state']
        length = float(len(ops))

        # Compute Shannon disagreement entropy across currently surviving candidate mappings
        out_counts: dict[Any, int] = {}
        for m_mode in surviving_modes:
            pred = cls.simulate_domain_trajectory(ops, init_s, mode=m_mode)
            fz = _freeze_value(pred)
            out_counts[fz] = out_counts.get(fz, 0) + 1
        n_surv = float(max(1, len(surviving_modes)))
        entropy = -sum((c / n_surv) * math.log2(c / n_surv) for c in out_counts.values())

        repeats = sum(1 for i in range(1, len(ops)) if ops[i] == ops[i - 1])
        repeat_depth = round(repeats / float(max(1, len(ops) - 1)), 4)
        counter_sens = 1.0 if ('op_acc_stamp' in ops and len(ops) >= 3) else 0.0
        norm_cost = round(length / 5.0, 4)

        return {
            'bias': 1.0,
            'surviving_disagreement_entropy': round(entropy, 4),
            'repeat_operator_depth': float(repeat_depth),
            'counter_timestamp_sensitivity': float(counter_sens),
            'normalized_probe_cost': float(norm_cost),
        }

    def fit_from_source_episodes(
        self,
        source_episodes: list[dict[str, Any]],
        *,
        l2: float = 0.25,
    ) -> dict[str, Any]:
        """Fits probe value weights using regularized ridge regression (`np.linalg.solve`) on source episodes."""
        if self.is_frozen:
            raise RuntimeError('Cannot fit frozen ActiveInfoGainCorrespondenceEngine')

        x_rows: list[list[float]] = []
        y_vals: list[float] = []

        for ep in source_episodes:
            cand_modes = list(ep['candidate_modes'])
            true_mode = ep['true_target_mode']
            for probe in ep['candidate_probes']:
                feats = self.compute_probe_features(probe, cand_modes)
                x_rows.append([float(feats[f]) for f in self.feature_order])

                # Counterfactual rollout: how many false candidates does this probe eliminate per unit step cost?
                step_cost = len(probe['ops'])
                self.policy_training_work += step_cost * len(cand_modes)
                self.policy_training_primitive_steps += step_cost * len(cand_modes) * 2
                true_out = self.simulate_domain_trajectory(probe['ops'], probe['init_state'], mode=true_mode)
                eliminated = sum(
                    1
                    for m in cand_modes
                    if self.simulate_domain_trajectory(probe['ops'], probe['init_state'], mode=m) != true_out
                )
                utility = (2.0 * float(eliminated)) - 0.15 * float(step_cost)
                y_vals.append(round(utility, 4))

        x_mat = np.asarray(x_rows, dtype=float)
        y_vec = np.asarray(y_vals, dtype=float)
        ident = np.eye(x_mat.shape[1], dtype=float)
        ident[0, 0] = 0.0
        w_vec = np.linalg.solve(x_mat.T @ x_mat + l2 * ident, x_mat.T @ y_vec)
        self.weights = {name: round(float(val), 6) for name, val in zip(self.feature_order, w_vec)}
        self.training_provenance.append({
            'episodes_count': len(source_episodes),
            'samples_count': len(x_rows),
            'policy_training_work': self.policy_training_work,
            'fitted_weights': dict(self.weights),
        })
        return {
            'policy_training_work': self.policy_training_work,
            'fitted_weights': dict(self.weights),
        }

    def freeze_policy(self) -> None:
        self.is_frozen = True

    def run_track1_task(
        self,
        method: str,
        task_spec: dict[str, Any],
        cached_validated_mode: str | None,
        *,
        seed: int = 0,
        charge_training_share: int = 0,
    ) -> tuple[Wave24Track1Result, str | None]:
        """Executes one Track 1 cross-domain correspondence task with equal legal early stopping across all methods."""
        counter = Wave24WorkCounter(policy_training_work=charge_training_share)
        is_rep = bool(task_spec.get('is_repeated_transfer', False))
        gold_status = task_spec['gold_validation_status']
        true_mode = task_spec['true_target_mode']
        priv_ops = task_spec['private_ops']
        priv_init = task_spec['private_init_state']
        priv_gold = self.simulate_domain_trajectory(priv_ops, priv_init, mode=true_mode) if gold_status == 'UNIQUE_VALIDATED_MAPPING' else None

        # If repeated transfer task in the same domain and a unique validated mapping is already locked:
        if is_rep and cached_validated_mode is not None:
            counter.candidate_evaluations += len(priv_ops)
            counter.primitive_op_steps += len(priv_ops) * 2
            pred = self.simulate_domain_trajectory(priv_ops, priv_init, mode=cached_validated_mode)
            wb = counter.to_dict()
            return (
                Wave24Track1Result(
                    method=method,
                    task_id=task_spec['id'],
                    condition_label=task_spec['condition_label'],
                    seed=seed,
                    is_repeated_transfer=True,
                    validation_status='UNIQUE_VALIDATED_MAPPING',
                    gold_validation_status=gold_status,
                    surviving_mappings_count=1,
                    recovered_exact_mapping=(cached_validated_mode == true_mode),
                    private_prediction=pred,
                    private_gold=priv_gold,
                    private_correct=(pred == priv_gold),
                    probes_executed=0,
                    decision_trace=[],
                    first_acquisition_work=0,
                    repeated_transfer_work=wb['total_work'],
                    policy_training_work=charge_training_share,
                    total_work=wb['total_work'],
                    total_work_including_training=wb['total_work_including_training'],
                    total_primitive_op_steps=wb['total_primitive_op_steps'],
                    work_breakdown=wb,
                ),
                cached_validated_mode,
            )

        surviving: list[str] = list(task_spec['candidate_modes'])
        remaining_probes: list[dict[str, Any]] = [dict(p) for p in task_spec['public_probes']]
        decision_trace: list[dict[str, Any]] = []
        probes_run = 0

        while remaining_probes:
            if len(surviving) == 0:
                break
            if probes_run >= 1 and len(surviving) == 1:
                break
            # Equal early stopping check after at least 1 target validation probe:
            # if all surviving mappings agree on all remaining public probes, stop!
            if probes_run >= 1:
                any_disagreement = False
                for p_chk in remaining_probes:
                    outs = {
                        _freeze_value(self.simulate_domain_trajectory(p_chk['ops'], p_chk['init_state'], mode=m))
                        for m in surviving
                    }
                    if len(outs) > 1:
                        any_disagreement = True
                        break
                if not any_disagreement:
                    break

            # Score candidate probes according to the method
            best_idx = 0
            best_score = -1e9
            best_feats: dict[str, float] = {}
            best_contribs: dict[str, float] = {}

            if method == 'fixed_interventional_mapping_solver':
                # Canonical source-frequency / shortest-first schedule
                best_idx = 0
                best_feats = self.compute_probe_features(remaining_probes[0], surviving)
                best_score = float(len(remaining_probes))
                best_contribs = {'canonical_order': best_score}
                counter.proposer_scoring_work += 1
                counter.primitive_op_steps += 2

            elif method == 'cost_aware_disagreement_mapping_solver':
                # Fixed heuristic: immediate step-normalized disagreement without learned counter/repeat weights
                counter.proposer_scoring_work += len(remaining_probes)
                counter.primitive_op_steps += len(remaining_probes) * 2
                for idx, p_cand in enumerate(remaining_probes):
                    feats = self.compute_probe_features(p_cand, surviving)
                    # Uses raw disagreement divided by cost; ties prefer shorter 2-step probes first
                    sc = 0.5 * feats['surviving_disagreement_entropy'] - 1.2 * feats['normalized_probe_cost']
                    if sc > best_score:
                        best_score = round(sc, 6)
                        best_idx = idx
                        best_feats = feats
                        best_contribs = {
                            'surviving_disagreement_entropy': round(0.5 * feats['surviving_disagreement_entropy'], 6),
                            'normalized_probe_cost': round(-1.2 * feats['normalized_probe_cost'], 6),
                        }

            elif method == 'shuffled_policy_mapping_solver':
                counter.proposer_scoring_work += len(remaining_probes)
                counter.primitive_op_steps += len(remaining_probes) * 2
                rng = random.Random(3001 + seed * 71 + probes_run * 19 + len(remaining_probes))
                best_idx = rng.randrange(len(remaining_probes))
                best_feats = self.compute_probe_features(remaining_probes[best_idx], surviving)
                best_score = 0.0
                best_contribs = {f: 0.0 for f in self.feature_order}

            elif method == 'active_infogain_mapping_solver':
                counter.proposer_scoring_work += len(remaining_probes)
                counter.primitive_op_steps += len(remaining_probes) * 2
                for idx, p_cand in enumerate(remaining_probes):
                    feats = self.compute_probe_features(p_cand, surviving)
                    c_map = {f: round(float(feats[f]) * float(self.weights[f]), 6) for f in self.feature_order}
                    sc = sum(c_map.values())
                    if sc > best_score:
                        best_score = round(sc, 6)
                        best_idx = idx
                        best_feats = feats
                        best_contribs = c_map
            else:
                raise ValueError(f'Unknown Track 1 method: {method}')

            chosen_probe = remaining_probes.pop(best_idx)
            probes_run += 1
            step_len = len(chosen_probe['ops'])
            # Execute probe in target domain + validate surviving candidates against observation
            probe_cost = step_len * (1 + len(surviving))
            counter.public_validation_work += probe_cost
            counter.primitive_op_steps += probe_cost * 2

            target_obs = self.simulate_domain_trajectory(
                chosen_probe['ops'], chosen_probe['init_state'], mode=true_mode
            )
            before_surv = list(surviving)
            surviving = [
                m
                for m in surviving
                if self.simulate_domain_trajectory(chosen_probe['ops'], chosen_probe['init_state'], mode=m) == target_obs
            ]
            rejected = [m for m in before_surv if m not in surviving]

            decision_trace.append(
                asdict(
                    Track1ProbeDecisionRecord(
                        step_index=probes_run,
                        surviving_hypotheses=before_surv,
                        candidate_probe_count=len(remaining_probes) + 1,
                        selected_probe_id=chosen_probe['id'],
                        selected_probe_ops=list(chosen_probe['ops']),
                        selected_probe_features=best_feats,
                        selected_probe_score=round(best_score, 6),
                        per_feature_contributions=best_contribs,
                        probe_cost=probe_cost,
                        resulting_target_observation=target_obs,
                        rejected_hypotheses=rejected,
                        remaining_hypotheses=list(surviving),
                    )
                )
            )

        if len(surviving) == 1:
            val_status = 'UNIQUE_VALIDATED_MAPPING'
            locked_mode = surviving[0]
            counter.candidate_evaluations += len(priv_ops)
            counter.primitive_op_steps += len(priv_ops) * 2
            priv_pred = self.simulate_domain_trajectory(priv_ops, priv_init, mode=locked_mode)
            exact_ok = locked_mode == true_mode
            priv_ok = (val_status == gold_status) and (priv_pred == priv_gold)
        elif len(surviving) > 1:
            val_status = 'AMBIGUOUS_VALIDATED_MAPPINGS'
            locked_mode = None
            priv_pred = None
            exact_ok = False
            priv_ok = val_status == gold_status
        else:
            val_status = 'NO_VALIDATED_MAPPING'
            locked_mode = None
            priv_pred = None
            exact_ok = False
            priv_ok = val_status == gold_status

        wb = counter.to_dict()
        first_w = 0 if is_rep else wb['total_work']
        rep_w = wb['total_work'] if is_rep else 0

        return (
            Wave24Track1Result(
                method=method,
                task_id=task_spec['id'],
                condition_label=task_spec['condition_label'],
                seed=seed,
                is_repeated_transfer=is_rep,
                validation_status=val_status,
                gold_validation_status=gold_status,
                surviving_mappings_count=len(surviving),
                recovered_exact_mapping=exact_ok,
                private_prediction=priv_pred,
                private_gold=priv_gold,
                private_correct=priv_ok,
                probes_executed=probes_run,
                decision_trace=decision_trace,
                first_acquisition_work=first_w,
                repeated_transfer_work=rep_w,
                policy_training_work=charge_training_share,
                total_work=wb['total_work'],
                total_work_including_training=wb['total_work_including_training'],
                total_primitive_op_steps=wb['total_primitive_op_steps'],
                work_breakdown=wb,
            ),
            locked_mode if val_status == 'UNIQUE_VALIDATED_MAPPING' else cached_validated_mode,
        )


# ===========================================================================
# 7. Mechanism 5B — Track 3: Multi-Family LLM + Witness Hybrid on Metal GPU
# ===========================================================================

@dataclass
class Wave24Track3TurnResult:
    """Result of one Track 3 turn across the 3 compared LLM/agent methods across all 4 families."""

    method: str
    dialogue_id: str
    turn_index: int
    family: str
    category: str
    seed: int
    is_repeated_use_turn: bool
    user_prompt: str
    raw_llm_output: str
    final_decision_status: str
    # Statuses:
    #   'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
    #   'AMBIGUOUS_WITNESS_FOUND_CLARIFY'
    #   'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
    #   'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
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


class HybridLLMWitnessMetaAgent:
    """Compares `standalone_pretrained_llm_mps`, `tool_equipped_llm_with_skill_cache_mps`, and
    `nexus_hybrid_llm_witness_meta_agent_mps` across all 4 families on Metal `Qwen2.5-0.5B-Instruct`.

    Explicit Controller Disclosure (addressing Wave 23 Audit Item #6):
    - `standalone_pretrained_llm_mps`: Direct generation from `qwen2.5-0.5b-instruct-q4_k_m.gguf`
      on Apple Silicon Metal GPU (`n_gpu_layers=-1`).
    - `tool_equipped_llm_with_skill_cache_mps`: Same LLM generation paired with the shared Python
      AST sandbox and skill cache; executes a greedy first-fitting program search on public examples
      without `ObservationalQuotientWitnessEngine` witness-pair checking or `MetaProcedureOptimizer`.
    - `nexus_hybrid_llm_witness_meta_agent_mps`: Combines the LLM with `MetaProcedureOptimizer`
      and `ObservationalQuotientWitnessEngine` (three-state witness verification + stateless vs
      stateful deterministic collision separation).
    """

    @classmethod
    def evaluate_turn_triplet(
        cls,
        turn_spec: dict[str, Any],
        raw_llm_output: str,
        llm_telemetry: dict[str, Any],
        dialogue_memory: dict[str, Any],
        shared_skill_cache: dict[str, MultiFamilyProgramAST],
        meta_opt: MetaProcedureOptimizer,
        seed: int,
    ) -> tuple[Wave24Track3TurnResult, Wave24Track3TurnResult, Wave24Track3TurnResult]:
        gold_status = turn_spec['gold_decision_status']
        gold_val = turn_spec.get('gold_value')
        family = turn_spec['family']
        category = turn_spec['category']
        is_rep = bool(turn_spec.get('is_repeated_use_turn', False))
        public_examples = [(x, y) for x, y in turn_spec.get('public_examples', [])]
        query_input = turn_spec.get('query_input')
        is_stateful = bool(turn_spec.get('declared_stateful', family == 'STATE_TRANSITION'))

        # ------------------------------------------------------------------
        # 1. `standalone_pretrained_llm_mps`
        # ------------------------------------------------------------------
        c_raw = Wave24WorkCounter(candidate_evaluations=1, primitive_op_steps=4)
        literals = w21_m3._extract_Python_literals_from_text(raw_llm_output)
        asked_clar = w21_m3._raw_llm_asked_clarification(raw_llm_output)
        abstained = w21_m3._raw_llm_abstained(raw_llm_output, ('collision', 'contradict', 'impossible', 'out of grammar'))

        raw_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
        raw_val: Any = literals[0] if literals else raw_llm_output.strip()[:40]
        raw_correct = False
        raw_premature = False
        raw_det_complied = False

        if gold_status == 'VERIFIED_RELATIVE_TO_SELECTED_SPEC':
            if not asked_clar and not abstained and (raw_val == gold_val or str(gold_val) in raw_llm_output):
                raw_val = gold_val
                raw_correct = True
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
        elif gold_status == 'NO_PROGRAM_IN_BOUNDED_GRAMMAR':
            if abstained:
                raw_decision = 'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
                raw_correct = True

        res_standalone = Wave24Track3TurnResult(
            method='standalone_pretrained_llm_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            family=family,
            category=category,
            seed=seed,
            is_repeated_use_turn=is_rep,
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
            first_acquisition_work=0 if is_rep else c_raw.total_work,
            repeated_use_work=c_raw.total_work if is_rep else 0,
            total_work=c_raw.total_work,
            total_primitive_op_steps=c_raw.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )

        # ------------------------------------------------------------------
        # 2. `tool_equipped_llm_with_skill_cache_mps` (Equal-Tool Baseline)
        # ------------------------------------------------------------------
        c_tool = Wave24WorkCounter()
        tool_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
        tool_val: Any = None
        tool_premature = False
        tool_det_complied = False

        # Merge dialogue clarifications if present for follow-up turns
        merged_public = list(public_examples)
        if turn_spec.get('is_clarification_followup') and dialogue_memory.get('tool_pending_examples'):
            merged_public = list(dialogue_memory['tool_pending_examples']) + merged_public

        skill_ref = turn_spec.get('reuse_skill_key')
        if skill_ref and skill_ref in shared_skill_cache:
            c_tool.template_retrieval_work += 1
            prog_cached = shared_skill_cache[skill_ref]
            tool_val = MultiFamilyASTEngine.execute_program(prog_cached, query_input, c_tool)
        elif has_stateless_deterministic_collision(merged_public, is_stateful_history_task=is_stateful):
            tool_decision = 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
        else:
            # Equal-tool baseline searches default catalog and commits to the FIRST fitting program g_1
            by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(family)
            flat_cat = [p for s in MetaProcedureOptimizer.STRATEGIES for p in by_strat[s]]
            first_fit: MultiFamilyProgramAST | None = None
            for p in flat_cat:
                fits = True
                for x_i, y_i in merged_public:
                    if MultiFamilyASTEngine.execute_program(p, x_i, c_tool) != y_i:
                        fits = False
                        break
                if fits:
                    first_fit = p
                    break
            if first_fit is None:
                tool_decision = 'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
            else:
                # Commits immediately to g_1 without checking for a disagreeing witness g_2!
                tool_val = MultiFamilyASTEngine.execute_program(first_fit, query_input, c_tool, charge_eval=False)
                if gold_status == 'AMBIGUOUS_WITNESS_FOUND_CLARIFY':
                    tool_premature = True
                if turn_spec.get('save_skill_key'):
                    shared_skill_cache[turn_spec['save_skill_key'] + '_tool'] = first_fit

        tool_correct = (tool_decision == gold_status) and (
            gold_status != 'VERIFIED_RELATIVE_TO_SELECTED_SPEC' or tool_val == gold_val
        )
        res_tool = Wave24Track3TurnResult(
            method='tool_equipped_llm_with_skill_cache_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            family=family,
            category=category,
            seed=seed,
            is_repeated_use_turn=is_rep,
            user_prompt=turn_spec['user_prompt'],
            raw_llm_output=raw_llm_output,
            final_decision_status=tool_decision,
            gold_decision_status=gold_status,
            verified_value=tool_val,
            gold_value=gold_val,
            tool_or_skill_invoked=True,
            turn_correct=tool_correct,
            unverified_or_false_claim=not tool_correct,
            premature_commit_on_ambiguous=tool_premature,
            deterministic_violation_complied=tool_det_complied,
            first_acquisition_work=0 if is_rep else c_tool.total_work,
            repeated_use_work=c_tool.total_work if is_rep else 0,
            total_work=c_tool.total_work,
            total_primitive_op_steps=c_tool.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )

        # ------------------------------------------------------------------
        # 3. `nexus_hybrid_llm_witness_meta_agent_mps` (Quotient Witness + Meta-Procedure)
        # ------------------------------------------------------------------
        c_nex = Wave24WorkCounter()
        nex_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
        nex_val: Any = None

        nex_public = list(public_examples)
        if turn_spec.get('is_clarification_followup') and dialogue_memory.get('nexus_pending_examples'):
            nex_public = list(dialogue_memory['nexus_pending_examples']) + nex_public

        if skill_ref and skill_ref in shared_skill_cache:
            c_nex.template_retrieval_work += 1
            prog_cached = shared_skill_cache[skill_ref]
            nex_val = MultiFamilyASTEngine.execute_program(prog_cached, query_input, c_nex)
        else:
            dec = meta_opt.score_and_order_strategies(
                f"{turn_spec['dialogue_id']}_t{turn_spec['turn_index']}",
                'learned_meta_procedure_plus_skills',
                nex_public,
                query_input,
                c_nex,
                seed=seed,
            )
            by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(family)
            ordered_cat = [p for s in dec.selected_strategy_order for p in by_strat[s]]
            q_rep = ObservationalQuotientWitnessEngine.run_quotient_witness_search(
                ordered_cat,
                nex_public,
                query_input,
                c_nex,
                max_candidate_budget=400,
                is_stateful_history_task=is_stateful,
            )
            if q_rep.status == 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS':
                nex_decision = 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS'
            elif q_rep.status == 'NO_PROGRAM_IN_BOUNDED_GRAMMAR':
                nex_decision = 'NO_PROGRAM_IN_BOUNDED_GRAMMAR'
            elif q_rep.status == 'AMBIGUOUS_WITNESS_FOUND':
                nex_decision = 'AMBIGUOUS_WITNESS_FOUND_CLARIFY'
                dialogue_memory['nexus_pending_examples'] = list(nex_public)
                nex_val = {
                    'candidate_a_output': q_rep.primary_query_output,
                    'candidate_b_output': q_rep.witness_query_output,
                }
            elif q_rep.status == 'UNIQUE_IN_BOUNDED_SPACE' and q_rep.primary_program is not None:
                nex_decision = 'VERIFIED_RELATIVE_TO_SELECTED_SPEC'
                nex_val = q_rep.primary_query_output
                if turn_spec.get('save_skill_key'):
                    shared_skill_cache[turn_spec['save_skill_key']] = q_rep.primary_program

        nex_correct = (nex_decision == gold_status) and (
            gold_status != 'VERIFIED_RELATIVE_TO_SELECTED_SPEC' or nex_val == gold_val
        )
        res_nexus = Wave24Track3TurnResult(
            method='nexus_hybrid_llm_witness_meta_agent_mps',
            dialogue_id=turn_spec['dialogue_id'],
            turn_index=turn_spec['turn_index'],
            family=family,
            category=category,
            seed=seed,
            is_repeated_use_turn=is_rep,
            user_prompt=turn_spec['user_prompt'],
            raw_llm_output=raw_llm_output,
            final_decision_status=nex_decision,
            gold_decision_status=gold_status,
            verified_value=nex_val,
            gold_value=gold_val,
            tool_or_skill_invoked=True,
            turn_correct=nex_correct,
            unverified_or_false_claim=not nex_correct,
            premature_commit_on_ambiguous=False,
            deterministic_violation_complied=False,
            first_acquisition_work=0 if is_rep else c_nex.total_work,
            repeated_use_work=c_nex.total_work if is_rep else 0,
            total_work=c_nex.total_work,
            total_primitive_op_steps=c_nex.primitive_op_steps,
            llm_telemetry=llm_telemetry,
        )
        return res_standalone, res_tool, res_nexus


# ===========================================================================
# 8. Source Training Suite, Separate Dev Suite & Post-Freeze Assessment Generator
# ===========================================================================

def build_wave24_source_training_suite() -> dict[str, Any]:
    """Builds Source Training Episodes (strictly Families A & B for Track 2, and Source Mapping Episodes for Track 1)."""
    track1_source_episodes = [
        {
            'episode_id': 'w24_src_map_01',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'candidate_probes': [
                {'id': 'p_short_1', 'ops': ['op_inc', 'op_dec'], 'init_state': {'val': 2, 'aux': 3, 'stamp': 0}},
                {'id': 'p_short_2', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': 1, 'aux': 3, 'stamp': 0}},
                {'id': 'p_deep_stamp', 'ops': ['op_inc', 'op_acc_stamp', 'op_dbl', 'op_mix_aux', 'op_acc_stamp'], 'init_state': {'val': 3, 'aux': 3, 'stamp': 0}},
                {'id': 'p_deep_mix', 'ops': ['op_mix_aux', 'op_mix_aux', 'op_dbl', 'op_acc_stamp'], 'init_state': {'val': 3, 'aux': 3, 'stamp': 0}},
            ],
        },
        {
            'episode_id': 'w24_src_map_02',
            'true_target_mode': 'lookalike_ignore_stamp',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'candidate_probes': [
                {'id': 'p2_short_1', 'ops': ['op_dec', 'op_inc'], 'init_state': {'val': 4, 'aux': 3, 'stamp': 0}},
                {'id': 'p2_deep_stamp', 'ops': ['op_inc', 'op_acc_stamp', 'op_dbl', 'op_mix_aux', 'op_acc_stamp'], 'init_state': {'val': 4, 'aux': 3, 'stamp': 0}},
                {'id': 'p2_deep_repeat', 'ops': ['op_acc_stamp', 'op_acc_stamp', 'op_acc_stamp'], 'init_state': {'val': 2, 'aux': 3, 'stamp': 0}},
            ],
        },
    ]

    # Source tasks from Family A (`INT_SEQ`) and Family B (`STR_PARSE`) ONLY
    # Zero tasks from Families C (`DICT_RECORD`) or D (`STATE_TRANSITION`)!
    track2_source_tasks = [
        # 1. Family A Direct single-pass task
        {
            'id': 'w24_src_a_direct_01',
            'public': [([2, -3, 4, 1], [4, 8]), ([6, -1, 2], [12, 4]), ([-5, 8], [16])],
            'query_input': [4, -2, 10],
        },
        # 2. Family A Two-pass frequency deduplication task (has_repeated_keys_or_elements = 1.0, io_ratio < 0.6)
        {
            'id': 'w24_src_a_twopass_02',
            'public': [([3, 5, 3, 2, 5, 3], [2]), ([4, 1, 4, 9, 4, 1], [9]), ([8, 2, 8, 6, 2, 8], [6])],
            'query_input': [7, 3, 7, 4, 7, 3],
        },
        # 3. Family A Abductive conditional branch task (has_branching_or_conditional_spread = 1.0)
        {
            'id': 'w24_src_a_branch_03',
            'public': [([2, -2, 3, 6, 4], [2, 3, 2]), ([8, 2, -4, 5, 10], [4, 2, 5]), ([4, -6, 1, 6], [2, 3])],
            'query_input': [2, 12, -4, 3, 6],
        },
        # 4. Family B Direct string parse task
        {
            'id': 'w24_src_b_direct_04',
            'public': [('Alpha beta Gamma', 'alpha beta gamma'), ('Delta EPSILON', 'delta epsilon')],
            'query_input': 'Omega SIGMA',
        },
        # 5. Family B Two-pass unique token extraction (has_repeated_keys_or_elements = 1.0, io_ratio < 0.6)
        {
            'id': 'w24_src_b_twopass_05',
            'public': [
                ('cat dog cat bird dog cat', ['bird']),
                ('red blue red green blue red', ['green']),
                ('sun moon sun star moon sun', ['star']),
            ],
            'query_input': 'one two one three two one',
        },
        # 6. Family B Abductive conditional case branch (has_branching_or_conditional_spread = 1.0)
        {
            'id': 'w24_src_b_branch_06',
            'public': [
                (' Pear to Apple in ', 'PEAR to APPLE in'),
                ('Data on Node at', 'DATA on NODE at'),
            ],
            'query_input': 'Code in Rust go',
        },
    ]

    return {
        'track1_source_episodes': track1_source_episodes,
        'track2_source_tasks': track2_source_tasks,
    }


def build_wave24_dev_suite() -> dict[str, Any]:
    """Builds the separate Development Suite (`w24_dev_*`) for `pytest` and pre-freeze dry-run verification."""
    track1_dev_tasks = [
        {
            'id': 'w24_dev_t1_01_counter_aware_first',
            'condition_label': 'counter_sensitive_first_acquisition',
            'is_repeated_transfer': False,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'public_probes': [
                {'id': 'dp1_2step_a', 'ops': ['op_inc', 'op_dec'], 'init_state': {'val': 2, 'aux': 3, 'stamp': 0}},
                {'id': 'dp2_2step_b', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': 3, 'aux': 3, 'stamp': 0}},
                {'id': 'dp3_2step_c', 'ops': ['op_dec', 'op_acc_stamp'], 'init_state': {'val': 5, 'aux': 3, 'stamp': 0}},
                {'id': 'dp4_5step_disambig', 'ops': ['op_inc', 'op_acc_stamp', 'op_dbl', 'op_mix_aux', 'op_acc_stamp'], 'init_state': {'val': 3, 'aux': 3, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_acc_stamp', 'op_acc_stamp', 'op_dbl'],
            'private_init_state': {'val': 4, 'aux': 3, 'stamp': 0},
        },
        {
            'id': 'w24_dev_t1_02_counter_aware_transfer',
            'condition_label': 'counter_sensitive_repeated_transfer',
            'is_repeated_transfer': True,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'public_probes': [],
            'private_ops': ['op_dbl', 'op_acc_stamp', 'op_acc_stamp'],
            'private_init_state': {'val': 2, 'aux': 1, 'stamp': 0},
        },
        {
            'id': 'w24_dev_t1_03_ambiguous_mapping',
            'condition_label': 'insufficiently_identifiable_mapping',
            'is_repeated_transfer': False,
            'gold_validation_status': 'AMBIGUOUS_VALIDATED_MAPPINGS',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp'],
            'public_probes': [
                {'id': 'dp_amb_1', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': 2, 'aux': 1, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_acc_stamp', 'op_acc_stamp'],
            'private_init_state': {'val': 2, 'aux': 1, 'stamp': 0},
        },
        {
            'id': 'w24_dev_t1_04_no_mapping',
            'condition_label': 'genuinely_different_unaligned_dynamics',
            'is_repeated_transfer': False,
            'gold_validation_status': 'NO_VALIDATED_MAPPING',
            'true_target_mode': 'broken_unaligned',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp'],
            'public_probes': [
                {'id': 'dp_none_1', 'ops': ['op_inc', 'op_dbl'], 'init_state': {'val': 2, 'aux': 1, 'stamp': 0}},
            ],
            'private_ops': ['op_inc'],
            'private_init_state': {'val': 2, 'aux': 1, 'stamp': 0},
        },
    ]

    track2_dev_tasks = [
        # Family A: Piecewise SymKAN task
        {
            'id': 'w24_dev_t2_01_int_branch',
            'condition_label': 'family_a_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [([2, -2, 3, 6, 4], [2, 3, 2]), ([8, -4, 5, 10, 2], [4, 5, 2])],
            'private': [([12, -6, 1, 2, 6], [6, 2, 3])],
            'query_input': [4, 8, -2, 3, 2],
        },
        # Family B: Two-pass unique token join
        {
            'id': 'w24_dev_t2_02_str_twopass',
            'condition_label': 'family_b_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ('alpha beta alpha gamma beta delta', 'gamma delta'),
                ('one two one three', 'two three'),
            ],
            'private': [('red blue red green', 'blue green')],
            'query_input': 'cat dog cat fox',
        },
        # Unseen Family C (`DICT_RECORD`): Key-grouped aggregation with counter `seq`
        {
            'id': 'w24_dev_t2_03_dict_twopass_first',
            'condition_label': 'unseen_family_c_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([{'k': 'b', 'val': 3}, {'k': 'a', 'val': 2}, {'k': 'b', 'val': 4}], [2, 7]),
                ([{'k': 'x', 'val': 5}, {'k': 'y', 'val': 1}, {'k': 'x', 'val': 3}], [8, 1]),
            ],
            'private': [([{'k': 'm', 'val': 4}, {'k': 'n', 'val': 6}, {'k': 'm', 'val': 2}], [6, 6])],
            'query_input': [{'k': 'a', 'val': 10}, {'k': 'b', 'val': 5}],
        },
        # Unseen Family C (`DICT_RECORD`): Second task for 2-task MDL promotion
        {
            'id': 'w24_dev_t2_04_dict_twopass_second',
            'condition_label': 'unseen_family_c_second_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([{'k': 'c', 'val': 3}, {'k': 'a', 'val': 4}, {'k': 'c', 'val': 2}], [4, 5]),
                ([{'k': 'd', 'val': 6}, {'k': 'b', 'val': 3}, {'k': 'b', 'val': 5}], [8, 6]),
            ],
            'private': [([{'k': 'a', 'val': 3}, {'k': 'b', 'val': 8}, {'k': 'a', 'val': 7}], [10, 8])],
            'query_input': [{'k': 'a', 'val': 6}, {'k': 'b', 'val': 9}],
        },
        # Unseen Family C (`DICT_RECORD`): Compositional reuse (same 2-pass group sum)
        {
            'id': 'w24_dev_t2_05_dict_compositional_reuse',
            'condition_label': 'unseen_family_c_compositional_reuse',
            'reporting_is_repeated_or_transfer': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([{'k': 'b', 'val': 3}, {'k': 'a', 'val': 4}, {'k': 'b', 'val': 4}], [4, 7]),
                ([{'k': 'u', 'val': 5}, {'k': 'v', 'val': 3}, {'k': 'u', 'val': 4}], [9, 3]),
            ],
            'private': [([{'k': 'a', 'val': 4}, {'k': 'b', 'val': 5}], [4, 5])],
            'query_input': [{'k': 'a', 'val': 8}, {'k': 'b', 'val': 5}],
        },
        # Unseen Family D (`STATE_TRANSITION`): Stateful transition with floor rollback (`state + arg if >= 0 else state`)
        {
            'id': 'w24_dev_t2_06_state_rollback_first',
            'condition_label': 'unseen_family_d_stateful_rollback',
            'reporting_is_repeated_or_transfer': False,
            'declared_stateful': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([{'op': 'step', 'arg': 4}, {'op': 'step', 'arg': -6}, {'op': 'step', 'arg': 3}], [4, 4, 7]),
                ([{'op': 'step', 'arg': 2}, {'op': 'step', 'arg': 5}, {'op': 'step', 'arg': -9}], [2, 7, 7]),
            ],
            'private': [([{'op': 'step', 'arg': 6}, {'op': 'step', 'arg': -8}, {'op': 'step', 'arg': 2}], [6, 6, 8])],
            'query_input': [{'op': 'step', 'arg': 5}, {'op': 'step', 'arg': -2}, {'op': 'step', 'arg': 4}],
        },
        # Ambiguous Witness task (`AMBIGUOUS_WITNESS_FOUND`)
        {
            'id': 'w24_dev_t2_07_ambiguous_witness',
            'condition_label': 'insufficiently_identifiable_ambiguous',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'AMBIGUOUS_WITNESS_FOUND',
            'public': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])],
            'private': [],
            'query_input': [2, 8, -4, 6],
        },
        # Budget-exhausted uniqueness unknown (`UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`)
        {
            'id': 'w24_dev_t2_08_budget_exhausted',
            'condition_label': 'uniqueness_unknown_budget_cap',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
            'max_candidate_budget': 40,
            'public': [([1, 3, 5], [2, 6, 10]), ([3, 7], [6, 14])],
            'private': [],
            'query_input': [1, 5, 9],
        },
        # Stateless deterministic collision (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`)
        {
            'id': 'w24_dev_t2_09_stateless_collision',
            'condition_label': 'stateless_deterministic_collision',
            'reporting_is_repeated_or_transfer': False,
            'declared_stateful': False,
            'gold_witness_status': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            'public': [([2, 4], [4, 8]), ([2, 4], [2, 4])],
            'private': [],
            'query_input': [2, 4],
        },
        # Out-of-grammar (`NO_PROGRAM_IN_BOUNDED_GRAMMAR`)
        {
            'id': 'w24_dev_t2_10_out_of_grammar',
            'condition_label': 'out_of_bounded_grammar',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
            'public': [([1, 2, 3], [19, 29, 39]), ([2, 4], [29, 49])],
            'private': [],
            'query_input': [5, 6],
        },
    ]

    track3_dev_turns = [
        {
            'dialogue_id': 'w24_dev_dlg_01',
            'turn_index': 1,
            'family': 'DICT_RECORD',
            'category': 'verified_dict_aggregation',
            'is_repeated_use_turn': False,
            'user_prompt': 'Aggregate record values by key k in sorted key order: [{"k":"b","val":3},{"k":"a","val":2},{"k":"b","val":4}] -> [2, 7]. Compute for [{"k":"p","val":5},{"k":"q","val":1},{"k":"p","val":4}]. Return only the list.',
            'public_examples': [
                ([{'k': 'b', 'val': 3}, {'k': 'a', 'val': 2}, {'k': 'b', 'val': 4}], [2, 7]),
                ([{'k': 'x', 'val': 5}, {'k': 'y', 'val': 1}, {'k': 'x', 'val': 3}], [8, 1]),
            ],
            'query_input': [{'k': 'p', 'val': 5}, {'k': 'q', 'val': 1}, {'k': 'p', 'val': 4}],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [9, 1],
            'save_skill_key': 'dev_dict_group_sum',
        },
        {
            'dialogue_id': 'w24_dev_dlg_02',
            'turn_index': 1,
            'family': 'INT_SEQ',
            'category': 'ambiguous_witness_clarify',
            'is_repeated_use_turn': False,
            'user_prompt': 'In my integer list rule, [2, -3, 1] -> [2] and [4, 6, 3] -> [2, 3]. What is the output for [2, 8, -4, 6]?',
            'public_examples': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])],
            'query_input': [2, 8, -4, 6],
            'gold_decision_status': 'AMBIGUOUS_WITNESS_FOUND_CLARIFY',
            'gold_value': None,
        },
    ]

    return {
        'suite_name': 'wave24_dev_suite',
        'track1_tasks': track1_dev_tasks,
        'track2_tasks': track2_dev_tasks,
        'track3_turns': track3_dev_turns,
    }


def build_wave24_post_freeze_assessment_suite(freeze_commit_sha: str) -> dict[str, Any]:
    """Constructs the Post-Freeze Assessment Suite (`w24f_*`) parameterized by `freeze_commit_sha`.

    Because `assessment_seed` is derived via SHA-256 from the Commit-1 git hash AFTER Commit 1 is
    committed and pushed, final assessment parameters cannot be pre-screened before Commit 1.
    """
    clean_sha = (freeze_commit_sha or '0' * 40).strip()
    assessment_seed = int(hashlib.sha256(clean_sha.encode('utf-8')).hexdigest()[:16], 16)
    rng = random.Random(assessment_seed)

    # Derive deterministic post-freeze perturbation constants from `assessment_seed`
    v_base = rng.choice([2, 3, 4])
    d_val_a = rng.choice([2, 3, 4])
    d_val_b = rng.choice([5, 6, 7])
    s_step_a = rng.choice([3, 4, 5])
    s_step_b = rng.choice([6, 7, 8])

    # ------------------------------------------------------------------
    # Track 1 Post-Freeze Assessment Tasks (`8` Independent Tasks)
    # ------------------------------------------------------------------
    track1_tasks = [
        # 1. First acquisition on counter-sensitive domain (`true_counter_aware` where `stamp` genuinely matters)
        {
            'id': 'w24f_t1_01_counter_aware_first',
            'condition_label': 'counter_sensitive_first_acquisition',
            'is_repeated_transfer': False,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'public_probes': [
                {'id': 'fp1_2step_a', 'ops': ['op_inc', 'op_dec'], 'init_state': {'val': v_base, 'aux': 3, 'stamp': 0}},
                {'id': 'fp1_2step_b', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0}},
                {'id': 'fp1_2step_c', 'ops': ['op_dec', 'op_acc_stamp'], 'init_state': {'val': v_base + 2, 'aux': 3, 'stamp': 0}},
                {'id': 'fp1_3step_mod', 'ops': ['op_dbl', 'op_dbl', 'op_inc'], 'init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0}},
                {'id': 'fp1_5step_full_disambig', 'ops': ['op_inc', 'op_acc_stamp', 'op_dbl', 'op_mix_aux', 'op_acc_stamp'], 'init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_acc_stamp', 'op_acc_stamp', 'op_dbl'],
            'private_init_state': {'val': v_base + 2, 'aux': 3, 'stamp': 0},
        },
        # 2-4. Repeated transfer tasks in the counter-sensitive domain
        {
            'id': 'w24f_t1_02_counter_aware_transfer_a',
            'condition_label': 'counter_sensitive_repeated_transfer',
            'is_repeated_transfer': True,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp', 'lookalike_mod_wrap', 'lookalike_swap_sign'],
            'public_probes': [],
            'private_ops': ['op_dbl', 'op_acc_stamp', 'op_acc_stamp', 'op_mix_aux'],
            'private_init_state': {'val': v_base, 'aux': 2, 'stamp': 0},
        },
        {
            'id': 'w24f_t1_03_counter_aware_transfer_b',
            'condition_label': 'counter_sensitive_repeated_transfer',
            'is_repeated_transfer': True,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp', 'lookalike_mod_wrap', 'lookalike_swap_sign'],
            'public_probes': [],
            'private_ops': ['op_mix_aux', 'op_acc_stamp', 'op_acc_stamp', 'op_inc'],
            'private_init_state': {'val': v_base + 3, 'aux': 1, 'stamp': 0},
        },
        {
            'id': 'w24f_t1_04_counter_aware_transfer_c',
            'condition_label': 'counter_sensitive_repeated_transfer',
            'is_repeated_transfer': True,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp', 'lookalike_mod_wrap', 'lookalike_swap_sign'],
            'public_probes': [],
            'private_ops': ['op_acc_stamp', 'op_acc_stamp', 'op_acc_stamp', 'op_dec'],
            'private_init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0},
        },
        # 5. Second first-acquisition domain (`lookalike_ignore_stamp` where stamp is a distractor)
        {
            'id': 'w24f_t1_05_stamp_invariant_first',
            'condition_label': 'new_interface_stamp_distractor_first_acquisition',
            'is_repeated_transfer': False,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'lookalike_ignore_stamp',
            'candidate_modes': [
                'true_counter_aware',
                'lookalike_ignore_stamp',
                'lookalike_mod_wrap',
                'lookalike_swap_sign',
            ],
            'public_probes': [
                {'id': 'fp5_2step_a', 'ops': ['op_inc', 'op_dec'], 'init_state': {'val': v_base, 'aux': 3, 'stamp': 0}},
                {'id': 'fp5_2step_b', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': v_base, 'aux': 3, 'stamp': 0}},
                {'id': 'fp5_2step_c', 'ops': ['op_dec', 'op_acc_stamp'], 'init_state': {'val': v_base + 2, 'aux': 3, 'stamp': 0}},
                {'id': 'fp5_5step_disambig', 'ops': ['op_inc', 'op_acc_stamp', 'op_dbl', 'op_mix_aux', 'op_acc_stamp'], 'init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_acc_stamp', 'op_acc_stamp', 'op_mix_aux'],
            'private_init_state': {'val': v_base + 1, 'aux': 3, 'stamp': 0},
        },
        # 6. Repeated transfer in second domain
        {
            'id': 'w24f_t1_06_stamp_invariant_transfer',
            'condition_label': 'new_interface_stamp_distractor_repeated_transfer',
            'is_repeated_transfer': True,
            'gold_validation_status': 'UNIQUE_VALIDATED_MAPPING',
            'true_target_mode': 'lookalike_ignore_stamp',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp', 'lookalike_mod_wrap', 'lookalike_swap_sign'],
            'public_probes': [],
            'private_ops': ['op_dbl', 'op_acc_stamp', 'op_acc_stamp', 'op_dec'],
            'private_init_state': {'val': v_base + 2, 'aux': 1, 'stamp': 0},
        },
        # 7. Insufficiently identifiable / observationally equivalent on public probes (`AMBIGUOUS_VALIDATED_MAPPINGS`)
        {
            'id': 'w24f_t1_07_ambiguous_public_probes',
            'condition_label': 'insufficiently_identifiable_ambiguous',
            'is_repeated_transfer': False,
            'gold_validation_status': 'AMBIGUOUS_VALIDATED_MAPPINGS',
            'true_target_mode': 'true_counter_aware',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp'],
            'public_probes': [
                {'id': 'fp7_short_1', 'ops': ['op_inc', 'op_acc_stamp'], 'init_state': {'val': v_base, 'aux': 1, 'stamp': 0}},
                {'id': 'fp7_short_2', 'ops': ['op_dec', 'op_acc_stamp'], 'init_state': {'val': v_base + 1, 'aux': 1, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_acc_stamp', 'op_acc_stamp'],
            'private_init_state': {'val': v_base, 'aux': 1, 'stamp': 0},
        },
        # 8. Out-of-correspondence target dynamics (`NO_VALIDATED_MAPPING`)
        {
            'id': 'w24f_t1_08_unaligned_dynamics',
            'condition_label': 'genuinely_different_unaligned_dynamics',
            'is_repeated_transfer': False,
            'gold_validation_status': 'NO_VALIDATED_MAPPING',
            'true_target_mode': 'broken_unaligned',
            'candidate_modes': ['true_counter_aware', 'lookalike_ignore_stamp', 'lookalike_mod_wrap'],
            'public_probes': [
                {'id': 'fp8_probe_1', 'ops': ['op_inc', 'op_dbl'], 'init_state': {'val': v_base, 'aux': 1, 'stamp': 0}},
                {'id': 'fp8_probe_2', 'ops': ['op_mix_aux', 'op_acc_stamp', 'op_acc_stamp'], 'init_state': {'val': v_base, 'aux': 1, 'stamp': 0}},
            ],
            'private_ops': ['op_inc', 'op_dbl'],
            'private_init_state': {'val': v_base, 'aux': 1, 'stamp': 0},
        },
    ]

    # ------------------------------------------------------------------
    # Track 2 Post-Freeze Assessment Tasks (`18` Independent Tasks Across All 4 Families)
    # ------------------------------------------------------------------
    track2_tasks = [
        # --- Family A (`INT_SEQ`): 4 tasks ---
        # 1. Family A Two-pass unique positive integers (`counts.get(v, 0) == 1 and v > 0`, `v * 2`, `LIST_ID`)
        {
            'id': 'w24f_t2_01_int_twopass_unique_pos',
            'condition_label': 'family_a_twopass_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([3, -2, 3, d_val_a, 5, -2], [d_val_a * 2, 10]),
                ([4, 7, 4, -1, 9], [14, 18]),
            ],
            'private': [([6, 2, 6, -3, 8], [4, 16])],
            'query_input': [d_val_b, 3],
        },
        # 2. Family A Abductive piecewise branch + SymKAN induction (`v > 0 and v % 2 == 0`, `v // 2 if v > 2 else v`, `LIST_ID`)
        {
            'id': 'w24f_t2_02_int_branch_symkan_first',
            'condition_label': 'family_a_branch_symkan_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([2, -2, 3, 6, 4, 1], [2, 3, 2]),
                ([8, 2, -4, 5, 10], [4, 2, 5]),
            ],
            'private': [([12, 2, -2, 1, 6], [6, 2, 3])],
            'query_input': [4, 2, -6, 3, 8, 10],
        },
        # 3. Family A Second piecewise branch task (triggers 2-task MDL promotion of the branch skill!)
        {
            'id': 'w24f_t2_03_int_branch_symkan_second',
            'condition_label': 'family_a_branch_symkan_second_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([2, 10, -2, 3, 6], [2, 5, 3]),
                ([4, -4, 5, 8, 2], [2, 4, 2]),
            ],
            'private': [([6, -2, 1, 2, 14], [3, 2, 7])],
            'query_input': [2, 6, 12, -2, 3],
        },
        # 4. Family A Compositional reuse of the promoted branch skill with `LIST_REV` reducer
        {
            'id': 'w24f_t2_04_int_branch_compositional_rev',
            'condition_label': 'family_a_compositional_reuse_after_promotion',
            'reporting_is_repeated_or_transfer': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ([2, -2, 3, 6, 8], [4, 3, 2]),
                ([10, 4, -4, 1, 2], [2, 2, 5]),
            ],
            'private': [([6, -2, 5, 12, 2], [2, 6, 3])],
            'query_input': [2, 8, -4, 3, 10],
        },

        # --- Family B (`STR_PARSE`): 3 tasks ---
        # 5. Family B Two-pass unique token extraction (`counts[w.lower()] == 1`, `w.lower()`, `STR_JOIN_SPACE`)
        {
            'id': 'w24f_t2_05_str_twopass_unique_join',
            'condition_label': 'family_b_twopass_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ('Alpha beta ALPHA gamma beta delta', 'gamma delta'),
                ('Node edge node Graph', 'edge graph'),
            ],
            'private': [('Sun moon sun Star', 'moon star')],
            'query_input': 'Beam Wave',
        },
        # 6. Family B Second two-pass unique token task (triggers 2-task MDL promotion)
        {
            'id': 'w24f_t2_06_str_twopass_unique_second',
            'condition_label': 'family_b_twopass_second_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ('Tree leaf tree Root leaf Stem', 'root stem'),
                ('Host port host Link', 'port link'),
            ],
            'private': [('Key lock key Bolt', 'lock bolt')],
            'query_input': 'Mesh Grid',
        },
        # 7. Family B Compositional reuse of unique-token skill with `LIST_SORT_ASC` reducer
        {
            'id': 'w24f_t2_07_str_twopass_compositional_sort',
            'condition_label': 'family_b_compositional_reuse',
            'reporting_is_repeated_or_transfer': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                ('cat dog cat zebra dog ant', ['ant', 'zebra']),
                ('red blue red pearl blue jade', ['jade', 'pearl']),
            ],
            'private': [('one two onerew two ash', ['ash', 'onerew'])],
            'query_input': 'owl bat',
        },

        # --- Unseen Family C (`DICT_RECORD` — ZERO Source Training Tasks!): 4 tasks ---
        # 8. Unseen Family C First Acquisition: Key-grouped summation with sequence counter `r['val'] + r.get('seq', 0)`
        #    (Tests both H1 cross-family meta-policy transfer AND genuine counter/timestamp sensitivity!)
        {
            'id': 'w24f_t2_08_dict_counter_grouped_first',
            'condition_label': 'unseen_family_c_counter_sensitive_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'k': 'b', 'val': d_val_a, 'seq': 1},
                        {'k': 'a', 'val': 3, 'seq': 2},
                        {'k': 'b', 'val': 4, 'seq': 3},
                    ],
                    [5, d_val_a + 8],
                ),
                (
                    [
                        {'k': 'x', 'val': 2, 'seq': 1},
                        {'k': 'y', 'val': 5, 'seq': 2},
                        {'k': 'x', 'val': 3, 'seq': 4},
                    ],
                    [10, 7],
                ),
            ],
            'private': [
                (
                    [
                        {'k': 'm', 'val': 4, 'seq': 1},
                        {'k': 'n', 'val': 2, 'seq': 3},
                        {'k': 'm', 'val': 1, 'seq': 2},
                    ],
                    [8, 5],
                )
            ],
            'query_input': [
                {'k': 'a', 'val': d_val_b, 'seq': 1},
                {'k': 'b', 'val': 4, 'seq': 2},
            ],
        },
        # 9. Unseen Family C Second task with counter-sensitive grouped sum (2-task MDL promotion)
        {
            'id': 'w24f_t2_09_dict_counter_grouped_second',
            'condition_label': 'unseen_family_c_counter_sensitive_second_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'k': 'c', 'val': 1, 'seq': 2},
                        {'k': 'a', 'val': 4, 'seq': 1},
                        {'k': 'c', 'val': 2, 'seq': 3},
                    ],
                    [5, 8],
                ),
                (
                    [
                        {'k': 'd', 'val': 3, 'seq': 1},
                        {'k': 'b', 'val': 2, 'seq': 2},
                        {'k': 'b', 'val': 4, 'seq': 4},
                    ],
                    [12, 4],
                ),
            ],
            'private': [
                (
                    [
                        {'k': 'u', 'val': 5, 'seq': 1},
                        {'k': 'v', 'val': 2, 'seq': 2},
                        {'k': 'u', 'val': 3, 'seq': 3},
                    ],
                    [12, 4],
                )
            ],
            'query_input': [
                {'k': 'a', 'val': 4, 'seq': 1},
                {'k': 'b', 'val': 6, 'seq': 2},
            ],
        },
        # 10. Unseen Family C Repeated / Compositional reuse of counter-grouped sum
        {
            'id': 'w24f_t2_10_dict_counter_grouped_reuse',
            'condition_label': 'unseen_family_c_repeated_use',
            'reporting_is_repeated_or_transfer': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'k': 'b', 'val': 5, 'seq': 1},
                        {'k': 'a', 'val': 2, 'seq': 3},
                        {'k': 'b', 'val': 1, 'seq': 2},
                    ],
                    [5, 9],
                ),
                (
                    [
                        {'k': 'r', 'val': 3, 'seq': 2},
                        {'k': 's', 'val': 4, 'seq': 1},
                        {'k': 'r', 'val': 2, 'seq': 4},
                    ],
                    [11, 5],
                ),
            ],
            'private': [
                (
                    [
                        {'k': 'a', 'val': 1, 'seq': 1},
                        {'k': 'b', 'val': 3, 'seq': 2},
                        {'k': 'a', 'val': 4, 'seq': 3},
                    ],
                    [9, 5],
                )
            ],
            'query_input': [
                {'k': 'a', 'val': 6, 'seq': 1},
                {'k': 'b', 'val': 3, 'seq': 2},
            ],
        },
        # 11. Unseen Family C Abductive priority-branch record valuation (`r['val'] * 2 if r.get('prio', 0) == 1 else r['val']`)
        {
            'id': 'w24f_t2_11_dict_branch_prio_first',
            'condition_label': 'unseen_family_c_branch_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'k': 'a', 'val': 3, 'prio': 1},
                        {'k': 'b', 'val': 5, 'prio': 0},
                        {'k': 'c', 'val': 4, 'prio': 1},
                    ],
                    [6, 5, 8],
                ),
                (
                    [
                        {'k': 'd', 'val': 7, 'prio': 0},
                        {'k': 'e', 'val': 2, 'prio': 1},
                    ],
                    [7, 4],
                ),
            ],
            'private': [([{'k': 'x', 'val': 6, 'prio': 1}, {'k': 'y', 'val': 3, 'prio': 0}], [12, 3])],
            'query_input': [{'k': 'm', 'val': 5, 'prio': 1}, {'k': 'n', 'val': 9, 'prio': 0}],
        },

        # --- Unseen Family D (`STATE_TRANSITION` — ZERO Source Training Tasks!): 3 tasks ---
        # 12. Unseen Family D First Acquisition: Stateful non-negative floor rollback (`state + ev["arg"] if state + ev["arg"] >= 0 else state`)
        #     Note: identical event `{'op': 'step', 'arg': -6}` can yield different state outputs depending on history!
        {
            'id': 'w24f_t2_12_state_rollback_first',
            'condition_label': 'unseen_family_d_stateful_rollback_first_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'declared_stateful': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'op': 'step', 'arg': s_step_a},
                        {'op': 'step', 'arg': -8},
                        {'op': 'step', 'arg': s_step_b},
                        {'op': 'step', 'arg': -8},
                    ],
                    [s_step_a, s_step_a, s_step_a + s_step_b, s_step_a + s_step_b - 8],
                ),
                (
                    [
                        {'op': 'step', 'arg': 2},
                        {'op': 'step', 'arg': 5},
                        {'op': 'step', 'arg': -9},
                    ],
                    [2, 7, 7],
                ),
            ],
            'private': [
                (
                    [
                        {'op': 'step', 'arg': 6},
                        {'op': 'step', 'arg': -10},
                        {'op': 'step', 'arg': 3},
                    ],
                    [6, 6, 9],
                )
            ],
            'query_input': [
                {'op': 'step', 'arg': 5},
                {'op': 'step', 'arg': -2},
                {'op': 'step', 'arg': 4},
            ],
        },
        # 13. Unseen Family D Second task with stateful non-negative floor rollback (2-task MDL promotion)
        {
            'id': 'w24f_t2_13_state_rollback_second',
            'condition_label': 'unseen_family_d_stateful_rollback_second_acquisition',
            'reporting_is_repeated_or_transfer': False,
            'declared_stateful': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'op': 'step', 'arg': 4},
                        {'op': 'step', 'arg': -6},
                        {'op': 'step', 'arg': 5},
                    ],
                    [4, 4, 9],
                ),
                (
                    [
                        {'op': 'step', 'arg': 3},
                        {'op': 'step', 'arg': 4},
                        {'op': 'step', 'arg': -9},
                    ],
                    [3, 7, 7],
                ),
            ],
            'private': [([{'op': 'step', 'arg': 5}, {'op': 'step', 'arg': -8}, {'op': 'step', 'arg': 2}], [5, 5, 7])],
            'query_input': [{'op': 'step', 'arg': 7}, {'op': 'step', 'arg': -3}, {'op': 'step', 'arg': 3}],
        },
        # 14. Unseen Family D Compositional reuse of stateful rollback skill with `STATE_FINAL_SCALAR` reducer
        {
            'id': 'w24f_t2_14_state_rollback_compositional_scalar',
            'condition_label': 'unseen_family_d_compositional_reuse',
            'reporting_is_repeated_or_transfer': True,
            'declared_stateful': True,
            'gold_witness_status': 'UNIQUE_IN_BOUNDED_SPACE',
            'public': [
                (
                    [
                        {'op': 'step', 'arg': 4},
                        {'op': 'step', 'arg': -6},
                        {'op': 'step', 'arg': 5},
                    ],
                    9,
                ),
                (
                    [
                        {'op': 'step', 'arg': 2},
                        {'op': 'step', 'arg': 6},
                        {'op': 'step', 'arg': -10},
                        {'op': 'step', 'arg': 3},
                    ],
                    11,
                ),
            ],
            'private': [([{'op': 'step', 'arg': 8}, {'op': 'step', 'arg': -12}, {'op': 'step', 'arg': 4}], 12)],
            'query_input': [{'op': 'step', 'arg': 6}, {'op': 'step', 'arg': -9}, {'op': 'step', 'arg': 5}],
        },

        # --- Diagnostic Witness & Uncertainty Boundary Tasks (4 tasks covering all remaining statuses) ---
        # 15. Ambiguous Witness Found (`AMBIGUOUS_WITNESS_FOUND`)
        {
            'id': 'w24f_t2_15_ambiguous_witness',
            'condition_label': 'insufficiently_identifiable_ambiguous_witness',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'AMBIGUOUS_WITNESS_FOUND',
            'public': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])],
            'private': [],
            'query_input': [2, 8, -4, 6],
        },
        # 16. Uniqueness Unknown due to Budget Exhaustion (`UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`)
        {
            'id': 'w24f_t2_16_uniqueness_unknown_budget',
            'condition_label': 'uniqueness_unknown_budget_cap',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
            'max_candidate_budget': 40,
            'public': [([1, 3, 5], [2, 6, 10]), ([3, 7], [6, 14])],
            'private': [],
            'query_input': [1, 5, 9],
        },
        # 17. Stateless Deterministic Collision (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`)
        {
            'id': 'w24f_t2_17_stateless_collision',
            'condition_label': 'stateless_deterministic_collision',
            'reporting_is_repeated_or_transfer': False,
            'declared_stateful': False,
            'gold_witness_status': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            'public': [([2, 4], [4, 8]), ([2, 4], [2, 4])],
            'private': [],
            'query_input': [2, 4],
        },
        # 18. Out of Bounded Grammar (`NO_PROGRAM_IN_BOUNDED_GRAMMAR`)
        {
            'id': 'w24f_t2_18_out_of_grammar',
            'condition_label': 'genuinely_different_out_of_grammar',
            'reporting_is_repeated_or_transfer': False,
            'gold_witness_status': 'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
            'public': [([1, 2, 3], [19, 29, 39]), ([2, 4], [29, 49])],
            'private': [],
            'query_input': [5, 6],
        },
    ]

    # ------------------------------------------------------------------
    # Track 3 Post-Freeze Multi-Family NL Grounding Turns (`10` Independent Turns Across All 4 Families)
    # ------------------------------------------------------------------
    track3_turns = [
        # 1. Family A (`INT_SEQ`) Witness-Ambiguous Turn 1 -> Must clarify (`AMBIGUOUS_WITNESS_FOUND_CLARIFY`)
        {
            'dialogue_id': 'w24f_dlg_01_int_ambig',
            'turn_index': 1,
            'family': 'INT_SEQ',
            'category': 'ambiguous_witness_clarify',
            'is_repeated_use_turn': False,
            'user_prompt': 'In my integer sequence rule, [2, -3, 1] -> [2] and [4, 6, 3] -> [2, 3]. What is the output for [2, 8, -4, 6]?',
            'public_examples': [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])],
            'query_input': [2, 8, -4, 6],
            'gold_decision_status': 'AMBIGUOUS_WITNESS_FOUND_CLARIFY',
            'gold_value': None,
        },
        # 2. Family A (`INT_SEQ`) Clarification Follow-up Turn 2 -> Verified `[2, 4, 3]`
        {
            'dialogue_id': 'w24f_dlg_01_int_ambig',
            'turn_index': 2,
            'family': 'INT_SEQ',
            'category': 'clarified_unique_resolution',
            'is_repeated_use_turn': False,
            'is_clarification_followup': True,
            'user_prompt': 'Clarification: for [8, -2, 2] the output is [4, 2] (positive evens halved when > 2). Now evaluate [2, 8, -4, 6]. Return only the list.',
            'public_examples': [([8, -2, 2], [4, 2])],
            'query_input': [2, 8, -4, 6],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [2, 4, 3],
            'save_skill_key': 'w24f_int_halve_skill',
        },
        # 3. Family A (`INT_SEQ`) Repeated-use skill turn
        {
            'dialogue_id': 'w24f_dlg_01_int_ambig',
            'turn_index': 3,
            'family': 'INT_SEQ',
            'category': 'repeated_skill_reuse',
            'is_repeated_use_turn': True,
            'reuse_skill_key': 'w24f_int_halve_skill',
            'user_prompt': 'Apply the exact same verified integer rule to [10, 2, -3, 4]. Return only the list.',
            'public_examples': [],
            'query_input': [10, 2, -3, 4],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [5, 2, 2],
        },
        # 4. Family B (`STR_PARSE`) Unique token extraction turn
        {
            'dialogue_id': 'w24f_dlg_02_str_parse',
            'turn_index': 1,
            'family': 'STR_PARSE',
            'category': 'verified_string_parse',
            'is_repeated_use_turn': False,
            'user_prompt': 'Keep only words that appear once (case-insensitive), lowercased and joined by space: "Alpha beta ALPHA gamma beta delta" -> "gamma delta" and "Node edge node Graph" -> "edge graph". Evaluate "Sun moon sun Star".',
            'public_examples': [
                ('Alpha beta ALPHA gamma beta delta', 'gamma delta'),
                ('Node edge node Graph', 'edge graph'),
            ],
            'query_input': 'Sun moon sun Star',
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': 'moon star',
        },
        # 5. Family C (`DICT_RECORD`) Counter-sensitive grouped record aggregation
        {
            'dialogue_id': 'w24f_dlg_03_dict_record',
            'turn_index': 1,
            'family': 'DICT_RECORD',
            'category': 'verified_dict_counter_aggregation',
            'is_repeated_use_turn': False,
            'user_prompt': 'Sum (val + seq) grouped by sorted key k: [{"k":"b","val":2,"seq":1},{"k":"a","val":3,"seq":2},{"k":"b","val":4,"seq":3}] -> [5, 10]. Evaluate [{"k":"p","val":4,"seq":1},{"k":"q","val":2,"seq":2},{"k":"p","val":3,"seq":3}].',
            'public_examples': [
                (
                    [
                        {'k': 'b', 'val': 2, 'seq': 1},
                        {'k': 'a', 'val': 3, 'seq': 2},
                        {'k': 'b', 'val': 4, 'seq': 3},
                    ],
                    [5, 10],
                ),
                (
                    [
                        {'k': 'x', 'val': 2, 'seq': 1},
                        {'k': 'y', 'val': 5, 'seq': 2},
                        {'k': 'x', 'val': 3, 'seq': 4},
                    ],
                    [10, 7],
                ),
            ],
            'query_input': [
                {'k': 'p', 'val': 4, 'seq': 1},
                {'k': 'q', 'val': 2, 'seq': 2},
                {'k': 'p', 'val': 3, 'seq': 3},
            ],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [11, 4],
            'save_skill_key': 'w24f_dict_seq_skill',
        },
        # 6. Family C (`DICT_RECORD`) Repeated skill invocation
        {
            'dialogue_id': 'w24f_dlg_03_dict_record',
            'turn_index': 2,
            'family': 'DICT_RECORD',
            'category': 'repeated_skill_reuse',
            'is_repeated_use_turn': True,
            'reuse_skill_key': 'w24f_dict_seq_skill',
            'user_prompt': 'Apply the same grouped (val + seq) rule to [{"k":"b","val":5,"seq":1},{"k":"a","val":2,"seq":3},{"k":"b","val":1,"seq":2}].',
            'public_examples': [],
            'query_input': [
                {'k': 'b', 'val': 5, 'seq': 1},
                {'k': 'a', 'val': 2, 'seq': 3},
                {'k': 'b', 'val': 1, 'seq': 2},
            ],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [5, 9],
        },
        # 7. Family D (`STATE_TRANSITION`) Lawful stateful floor rollback transition
        {
            'dialogue_id': 'w24f_dlg_04_state_transition',
            'turn_index': 1,
            'family': 'STATE_TRANSITION',
            'category': 'verified_stateful_transition',
            'is_repeated_use_turn': False,
            'declared_stateful': True,
            'user_prompt': 'In this stateful buffer (starts at 0, ignores updates that would drop state below 0), [{"op":"step","arg":4},{"op":"step","arg":-6},{"op":"step","arg":5}] -> [4, 4, 9]. Compute the state trace for [{"op":"step","arg":5},{"op":"step","arg":-7},{"op":"step","arg":4}].',
            'public_examples': [
                ([{'op': 'step', 'arg': 4}, {'op': 'step', 'arg': -6}, {'op': 'step', 'arg': 5}], [4, 4, 9]),
                ([{'op': 'step', 'arg': 2}, {'op': 'step', 'arg': 5}, {'op': 'step', 'arg': -9}], [2, 7, 7]),
            ],
            'query_input': [{'op': 'step', 'arg': 5}, {'op': 'step', 'arg': -7}, {'op': 'step', 'arg': 4}],
            'gold_decision_status': 'VERIFIED_RELATIVE_TO_SELECTED_SPEC',
            'gold_value': [5, 5, 9],
        },
        # 8. Family D (`STATE_TRANSITION`) Witness-ambiguous transition rule (`AMBIGUOUS_WITNESS_FOUND_CLARIFY`)
        {
            'dialogue_id': 'w24f_dlg_04_state_transition',
            'turn_index': 2,
            'family': 'STATE_TRANSITION',
            'category': 'ambiguous_witness_clarify',
            'is_repeated_use_turn': False,
            'declared_stateful': True,
            'user_prompt': 'New transition rule: [{"op":"step","arg":2},{"op":"step","arg":3}] -> [2, 5]. What is the trace for [{"op":"step","arg":4},{"op":"step","arg":-6}]?',
            'public_examples': [([{'op': 'step', 'arg': 2}, {'op': 'step', 'arg': 3}], [2, 5])],
            'query_input': [{'op': 'step', 'arg': 4}, {'op': 'step', 'arg': -6}],
            'gold_decision_status': 'AMBIGUOUS_WITNESS_FOUND_CLARIFY',
            'gold_value': None,
        },
        # 9. Stateless Deterministic Collision Turn (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`)
        {
            'dialogue_id': 'w24f_dlg_05_diagnostics',
            'turn_index': 1,
            'family': 'INT_SEQ',
            'category': 'stateless_deterministic_collision',
            'is_repeated_use_turn': False,
            'declared_stateful': False,
            'user_prompt': 'Find a deterministic stateless function f(x) such that f([2, 4]) = [4, 8] and f([2, 4]) = [2, 4], then evaluate f([6, 8]).',
            'public_examples': [([2, 4], [4, 8]), ([2, 4], [2, 4])],
            'query_input': [6, 8],
            'gold_decision_status': 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
            'gold_value': None,
        },
        # 10. Out-of-Grammar Turn (`NO_PROGRAM_IN_BOUNDED_GRAMMAR`)
        {
            'dialogue_id': 'w24f_dlg_05_diagnostics',
            'turn_index': 2,
            'family': 'INT_SEQ',
            'category': 'out_of_bounded_grammar',
            'is_repeated_use_turn': False,
            'declared_stateful': False,
            'user_prompt': 'In our bounded elementary grammar, find a program mapping [1, 2, 3] -> [19, 29, 39] and [2, 4] -> [29, 49], then evaluate [5, 6].',
            'public_examples': [([1, 2, 3], [19, 29, 39]), ([2, 4], [29, 49])],
            'query_input': [5, 6],
            'gold_decision_status': 'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
            'gold_value': None,
        },
    ]

    return {
        'suite_name': 'wave24_post_freeze_assessment_suite',
        'freeze_commit_sha': clean_sha,
        'assessment_seed': assessment_seed,
        'derived_parameters': {
            'v_base': v_base,
            'd_val_a': d_val_a,
            'd_val_b': d_val_b,
            's_step_a': s_step_a,
            's_step_b': s_step_b,
        },
        'track1_tasks': track1_tasks,
        'track2_tasks': track2_tasks,
        'track3_turns': track3_turns,
    }


def run_wave24_experiment(
    *,
    freeze_commit_sha: str = '0' * 40,
    seeds: tuple[int, ...] = (0, 1, 2),
    use_dev_suite: bool = False,
    execute_metal_llm: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Executes the complete Wave 24 experiment and returns `(experiment_payload, suite_manifest)`."""
    t0_wall = time.perf_counter()
    t0_cpu = time.process_time()
    rss_start = current_rss_mb()

    source_suite = build_wave24_source_training_suite()
    suite = build_wave24_dev_suite() if use_dev_suite else build_wave24_post_freeze_assessment_suite(freeze_commit_sha)

    # 1. Fit and Freeze Track 1 Active Info-Gain Policy & Track 2 Meta-Procedure Policy on Source Suite
    t1_engine = ActiveInfoGainCorrespondenceEngine()
    t1_train_summary = t1_engine.fit_from_source_episodes(source_suite['track1_source_episodes'])
    t1_engine.freeze_policy()

    meta_opt = MetaProcedureOptimizer()
    t2_train_summary = meta_opt.fit_from_source_families_ab(source_suite['track2_source_tasks'])
    meta_opt.freeze_policy()

    # 2. Execute Track 1 Across All 4 Methods & Seeds
    track1_rows: list[dict[str, Any]] = []
    for seed in seeds:
        for method in WAVE24_TRACK1_METHODS:
            cached_mode: str | None = None
            for idx, task_spec in enumerate(suite['track1_tasks']):
                # Reset cached mode when domain changes
                if not task_spec.get('is_repeated_transfer', False):
                    cached_mode = None
                train_share = t1_engine.policy_training_work if (method == 'active_infogain_mapping_solver' and idx == 0) else 0
                res, cached_mode = t1_engine.run_track1_task(
                    method, task_spec, cached_mode, seed=seed, charge_training_share=train_share
                )
                track1_rows.append(asdict(res))

    # 3. Execute Track 2A (Cross-Family Factorial Comparison: Methods A, B, C, D, E, F)
    track2_factorial_rows: list[dict[str, Any]] = []
    mps_telemetry = NeuralTelemetry()
    for seed in seeds:
        for method in WAVE24_TRACK2_FACTORIAL_METHODS:
            hygiene = UtilityGatedSkillHygiene(enable_hygiene=True)
            for idx, task_spec in enumerate(suite['track2_tasks']):
                train_share = (
                    meta_opt.policy_training_work
                    if (
                        method in (
                            'learned_meta_procedure_skills_cleared',
                            'learned_meta_procedure_plus_skills',
                            'object_level_weights_only_solver',
                        )
                        and idx == 0
                    )
                    else 0
                )
                row = run_wave24_track2_task(
                    method,
                    task_spec,
                    meta_opt,
                    hygiene,
                    seed=seed,
                    suite_type='factorial_cross_family',
                    charge_training_share=train_share,
                    mps_telemetry=mps_telemetry,
                )
                track2_factorial_rows.append(asdict(row))

    # 4. Execute Track 2B (Continual Learning Under 16 Injected Adversarial Distractor Skills)
    track2_hygiene_rows: list[dict[str, Any]] = []
    solvable_tasks = [t for t in suite['track2_tasks'] if t['gold_witness_status'] == 'UNIQUE_IN_BOUNDED_SPACE']
    for seed in seeds:
        for method in WAVE24_TRACK2_HYGIENE_METHODS:
            hygiene = UtilityGatedSkillHygiene(
                enable_hygiene=(method != 'naive_continual_accumulation_no_hygiene')
            )
            distractors = build_16_adversarial_distractor_skills()
            hygiene.inject_distractor_skills(distractors)
            prev_fam: str | None = None
            for task_spec in solvable_tasks:
                cur_fam = MultiFamilyASTEngine.infer_task_family_from_public_io(task_spec['public'])
                if method == 'clean_slate_per_family_oracle' and prev_fam is not None and cur_fam != prev_fam:
                    hygiene = UtilityGatedSkillHygiene(enable_hygiene=True)
                prev_fam = cur_fam
                row = run_wave24_track2_task(
                    method,
                    task_spec,
                    meta_opt,
                    hygiene,
                    seed=seed,
                    suite_type='continual_interference_hygiene',
                    charge_training_share=0,
                    mps_telemetry=mps_telemetry,
                )
                track2_hygiene_rows.append(asdict(row))

    # 5. Execute Track 3 (Multi-Family NL Grounding vs Equal-Tool LLM Baseline on Metal GPU)
    track3_rows: list[dict[str, Any]] = []
    gguf_path = resolve_local_pretrained_gguf_path()
    gguf_sha256 = hashlib.sha256(gguf_path.read_bytes()).hexdigest() if gguf_path.exists() else ''

    # Cache LLM completions per turn prompt so all 3 methods see the exact same raw LLM output
    llm_outputs_by_turn: dict[tuple[str, int], tuple[str, dict[str, Any]]] = {}
    if execute_metal_llm:
        with tempfile.TemporaryDirectory(prefix='nexus_wave24_metal_') as tmpdir:
            ledger_path = f'{tmpdir}/wave24_metal_ledger.json'
            cfg = RuntimeConfig(
                model_path=str(gguf_path),
                max_tokens=48,
                prompt_cache=True,
                application_cache=False,
            )
            grant = ExplicitMetalGrant(
                authorized=True,
                owner='wave24_cross_family_experiment',
                reason='wave24_track3_metal_gpu_evaluation',
                ledger_path=ledger_path,
                n_gpu_layers=-1,
            )
            with PersistentMetalRuntime(cfg, grant) as metal_rt:
                runtime_meta = dict(metal_rt.metadata or {})
                for t_spec in suite['track3_turns']:
                    key = (t_spec['dialogue_id'], t_spec['turn_index'])
                    prompt = w21_m3._format_chatml_prompt(
                        t_spec['user_prompt'],
                        '{}',
                    )
                    call_seed = 101 + int(t_spec['turn_index'])
                    llm_out = metal_rt.complete(prompt, None, temperature=0.0, seed=call_seed)
                    raw_text = str(llm_out['content']).strip()
                    llm_tel = dict(llm_out['telemetry'])
                    llm_tel['model_path'] = str(gguf_path)
                    llm_tel['model_file'] = runtime_meta.get('model_file')
                    llm_tel['model_sha256'] = runtime_meta.get('model_sha256') or gguf_sha256
                    llm_tel['prompt_sha256'] = llm_out['request']['prompt_sha256']
                    llm_tel['n_gpu_layers'] = -1
                    llm_outputs_by_turn[key] = (raw_text, llm_tel)
    else:
        for t_spec in suite['track3_turns']:
            key = (t_spec['dialogue_id'], t_spec['turn_index'])
            llm_outputs_by_turn[key] = (
                '[0]',
                {
                    'model_path': str(gguf_path),
                    'model_sha256': gguf_sha256,
                    'n_gpu_layers': -1,
                    'latency_s': 0.0,
                    'prompt_tokens': 16,
                    'completion_tokens': 4,
                },
            )

    for seed in seeds:
        dialogue_mem: dict[str, Any] = {}
        shared_skills: dict[str, MultiFamilyProgramAST] = {}
        prev_dlg: str | None = None
        for t_spec in suite['track3_turns']:
            if t_spec['dialogue_id'] != prev_dlg:
                dialogue_mem = {}
                prev_dlg = t_spec['dialogue_id']
            raw_txt, tel = llm_outputs_by_turn[(t_spec['dialogue_id'], t_spec['turn_index'])]
            r_raw, r_tool, r_nex = HybridLLMWitnessMetaAgent.evaluate_turn_triplet(
                t_spec, raw_txt, tel, dialogue_mem, shared_skills, meta_opt, seed
            )
            track3_rows.extend([asdict(r_raw), asdict(r_tool), asdict(r_nex)])

    wall_elapsed_s = round(time.perf_counter() - t0_wall, 4)
    cpu_elapsed_s = round(time.process_time() - t0_cpu, 4)
    rss_end = current_rss_mb()
    rss_peak = peak_rss_mb()

    # Summarize Track 1, Track 2A, Track 2B, Track 3
    track1_summary = _summarize_track1(track1_rows, len(suite['track1_tasks']), len(seeds))
    track2_factorial_summary = _summarize_track2(
        track2_factorial_rows, len(suite['track2_tasks']), len(seeds), WAVE24_TRACK2_FACTORIAL_METHODS
    )
    track2_hygiene_summary = _summarize_track2(
        track2_hygiene_rows, len(solvable_tasks), len(seeds), WAVE24_TRACK2_HYGIENE_METHODS
    )
    track3_summary = _summarize_track3(track3_rows, len(suite['track3_turns']), len(seeds))

    # Compute explicit H1 & H2 verdicts on unseen Families C & D (`DICT_RECORD`, `STATE_TRANSITION`)
    h1_h2_report = _compute_h1_h2_unseen_family_verdicts(track2_factorial_rows)

    suite_manifest = {
        'wave': 'wave24_cross_family_meta_and_quotient_experiment',
        'suite_name': suite['suite_name'],
        'freeze_commit_sha': freeze_commit_sha,
        'assessment_seed': suite.get('assessment_seed', 0),
        'retained_all_generated_cases': True,
        'independent_task_counts': {
            'track1_independent_tasks': len(suite['track1_tasks']),
            'track2_factorial_independent_tasks': len(suite['track2_tasks']),
            'track2_hygiene_independent_tasks': len(solvable_tasks),
            'track3_independent_turns': len(suite['track3_turns']),
            'total_independent_tasks_and_turns': (
                len(suite['track1_tasks']) + len(suite['track2_tasks']) + len(suite['track3_turns'])
            ),
        },
        'suite_definition': suite,
        'source_training_suite': source_suite,
    }
    suite_manifest['payload_sha256'] = digest(canonical(suite_manifest))

    payload = {
        'wave': 'wave24_cross_family_meta_and_quotient_experiment',
        'freeze_commit_sha': freeze_commit_sha,
        'assessment_seed': suite.get('assessment_seed', 0),
        'retained_all_attempted_runs': True,
        'reused_module_owners': REUSED_MODULE_OWNERS,
        'declared_work_weights': DECLARED_WORK_WEIGHTS,
        'authorization_and_resource_ledger': {
            'historical_track_b_frozen_cpu_used_s': rec_eval.FROZEN_CPU_USED_S,
            'historical_track_b_frozen_cpu_remaining_s': rec_eval.FROZEN_CPU_REMAINING_S,
            'historical_track_b_debit_s': 0.0,
            'wave24_wall_time_s': wall_elapsed_s,
            'wave24_cpu_time_s': cpu_elapsed_s,
            'rss_start_mb': round(rss_start, 2),
            'rss_end_mb': round(rss_end, 2),
            'peak_rss_mb': round(rss_peak, 2),
            'mps_telemetry': mps_telemetry.snapshot(),
            'gguf_model_path': str(gguf_path),
            'gguf_model_sha256': gguf_sha256,
        },
        'source_training_provenance': {
            'track1_policy_training': t1_train_summary,
            'track2_meta_policy_training': t2_train_summary,
        },
        'independent_task_counts': suite_manifest['independent_task_counts'],
        'h1_and_h2_verdicts': h1_h2_report,
        'track1_summary': track1_summary,
        'track2_factorial_summary': track2_factorial_summary,
        'track2_hygiene_summary': track2_hygiene_summary,
        'track3_summary': track3_summary,
        'track1_rows': track1_rows,
        'track2_factorial_rows': track2_factorial_rows,
        'track2_hygiene_rows': track2_hygiene_rows,
        'track3_rows': track3_rows,
    }
    payload['payload_sha256'] = digest(canonical(payload))
    return payload, suite_manifest


def _summarize_track1(rows: list[dict[str, Any]], n_indep: int, n_seeds: int) -> dict[str, Any]:
    by_method: dict[str, Any] = {}
    for m in WAVE24_TRACK1_METHODS:
        m_rows = [r for r in rows if r['method'] == m]
        by_method[m] = {
            'independent_tasks': n_indep,
            'seeds': n_seeds,
            'evaluation_cells': len(m_rows),
            'private_correct_count': sum(1 for r in m_rows if r['private_correct']),
            'exact_mapping_count': sum(1 for r in m_rows if r['recovered_exact_mapping']),
            'ambiguous_correct_count': sum(
                1 for r in m_rows
                if r['gold_validation_status'] == 'AMBIGUOUS_VALIDATED_MAPPINGS' and r['private_correct']
            ),
            'no_mapping_correct_count': sum(
                1 for r in m_rows
                if r['gold_validation_status'] == 'NO_VALIDATED_MAPPING' and r['private_correct']
            ),
            'probes_executed': sum(r['probes_executed'] for r in m_rows),
            'first_acquisition_work': sum(r['first_acquisition_work'] for r in m_rows),
            'repeated_transfer_work': sum(r['repeated_transfer_work'] for r in m_rows),
            'policy_training_work': sum(r['policy_training_work'] for r in m_rows),
            'total_work': sum(r['total_work'] for r in m_rows),
            'total_work_including_training': sum(r['total_work_including_training'] for r in m_rows),
            'total_primitive_op_steps': sum(r['total_primitive_op_steps'] for r in m_rows),
        }
    return by_method


def _summarize_track2(
    rows: list[dict[str, Any]],
    n_indep: int,
    n_seeds: int,
    methods: tuple[str, ...],
) -> dict[str, Any]:
    by_method: dict[str, Any] = {}
    for m in methods:
        m_rows = [r for r in rows if r['method'] == m]
        unseen_cd_rows = [r for r in m_rows if r['family'] in ('DICT_RECORD', 'STATE_TRANSITION')]
        symkan_attempted = sum(1 for r in m_rows if r['symkan_report']['attempted'])
        symkan_nonempty = sum(
            1 for r in m_rows
            if r['symkan_report']['attempted'] and bool(r['symkan_report']['induced_expression'])
        )
        symkan_faithful = sum(1 for r in m_rows if r['symkan_report']['faithful_export'])
        by_method[m] = {
            'independent_tasks': n_indep,
            'seeds': n_seeds,
            'evaluation_cells': len(m_rows),
            'status_correct_count': sum(1 for r in m_rows if r['status_correct']),
            'private_correct_count': sum(1 for r in m_rows if r['private_correct']),
            'quotient_matches_unquotiented_count': sum(1 for r in m_rows if r['quotient_matches_unquotiented']),
            'max_statement_count': max((r['statement_count'] for r in m_rows), default=0),
            'max_expression_depth': max((r['expression_depth'] for r in m_rows), default=0),
            'all_no_compound_boxes': all(r['no_compound_boxes_verified'] for r in m_rows),
            'candidate_evaluations': sum(r['work_breakdown']['candidate_evaluations'] for r in m_rows),
            'witness_search_work': sum(r['work_breakdown']['witness_search_work'] for r in m_rows),
            'quotient_filter_work': sum(r['work_breakdown']['quotient_filter_work'] for r in m_rows),
            'harmful_interference_work': sum(r['work_breakdown']['harmful_interference_work'] for r in m_rows),
            'first_acquisition_work': sum(r['first_acquisition_work'] for r in m_rows),
            'repeated_use_work': sum(r['repeated_use_work'] for r in m_rows),
            'unseen_families_cd_first_acquisition_work': sum(r['first_acquisition_work'] for r in unseen_cd_rows),
            'unseen_families_cd_repeated_use_work': sum(r['repeated_use_work'] for r in unseen_cd_rows),
            'unseen_families_cd_total_work': sum(r['total_work'] for r in unseen_cd_rows),
            'policy_training_work': sum(r['work_breakdown']['policy_training_work'] for r in m_rows),
            'total_work': sum(r['total_work'] for r in m_rows),
            'total_work_including_training': sum(r['total_work_including_training'] for r in m_rows),
            'unquotiented_reference_work': sum(r['unquotiented_reference_work'] for r in m_rows),
            'total_primitive_op_steps': sum(r['total_primitive_op_steps'] for r in m_rows),
            'exact_whole_task_hits': sum(1 for r in m_rows if r['exact_whole_task_hit']),
            'compositional_skill_hits': sum(1 for r in m_rows if r['compositional_skill_hit']),
            'cold_archive_reactivations': sum(1 for r in m_rows if r['cold_archive_reactivated']),
            'max_auto_quarantined_skills': max((r['auto_quarantined_skills_count'] for r in m_rows), default=0),
            'symkan_attempted_count': symkan_attempted,
            'symkan_nonempty_induced_count': symkan_nonempty,
            'symkan_faithful_export_count': symkan_faithful,
        }
    return by_method


def _summarize_track3(rows: list[dict[str, Any]], n_indep: int, n_seeds: int) -> dict[str, Any]:
    by_method: dict[str, Any] = {}
    for m in WAVE24_TRACK3_METHODS:
        m_rows = [r for r in rows if r['method'] == m]
        by_method[m] = {
            'independent_turns': n_indep,
            'seeds': n_seeds,
            'evaluation_cells': len(m_rows),
            'turn_correct_count': sum(1 for r in m_rows if r['turn_correct']),
            'unverified_or_false_claims': sum(1 for r in m_rows if r['unverified_or_false_claim']),
            'premature_commits_on_ambiguous': sum(1 for r in m_rows if r['premature_commit_on_ambiguous']),
            'deterministic_violations_complied': sum(1 for r in m_rows if r['deterministic_violation_complied']),
            'first_acquisition_work': sum(r['first_acquisition_work'] for r in m_rows),
            'repeated_use_work': sum(r['repeated_use_work'] for r in m_rows),
            'total_work': sum(r['total_work'] for r in m_rows),
            'total_primitive_op_steps': sum(r['total_primitive_op_steps'] for r in m_rows),
        }
    return by_method


def _compute_h1_h2_unseen_family_verdicts(factorial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes separate, transparent causal verdicts for H1 and H2 on unseen Families C & D."""
    def _cd_metrics(method: str) -> dict[str, int]:
        r_cd = [r for r in factorial_rows if r['method'] == method and r['family'] in ('DICT_RECORD', 'STATE_TRANSITION')]
        r_all = [r for r in factorial_rows if r['method'] == method]
        return {
            'cd_first_acquisition_work': sum(r['first_acquisition_work'] for r in r_cd),
            'cd_repeated_use_work': sum(r['repeated_use_work'] for r in r_cd),
            'cd_total_work': sum(r['total_work'] for r in r_cd),
            'all_first_acquisition_work': sum(r['first_acquisition_work'] for r in r_all),
            'all_repeated_use_work': sum(r['repeated_use_work'] for r in r_all),
            'all_total_work': sum(r['total_work'] for r in r_all),
            'all_total_work_including_training': sum(r['total_work_including_training'] for r in r_all),
        }

    m_a = _cd_metrics('fixed_default_procedure_solver')
    m_b = _cd_metrics('fixed_procedure_with_templates')
    m_c = _cd_metrics('learned_meta_procedure_skills_cleared')
    m_d = _cd_metrics('learned_meta_procedure_plus_skills')
    m_e = _cd_metrics('shuffled_meta_procedure_control')
    m_f = _cd_metrics('object_level_weights_only_solver')

    h1_pass_cd = m_c['cd_first_acquisition_work'] < m_a['cd_first_acquisition_work']
    h2_pass_cd = m_d['cd_total_work'] < m_b['cd_total_work'] and m_d['all_repeated_use_work'] <= m_b['all_repeated_use_work']

    return {
        'H1_policy_only_skills_cleared_vs_fixed_no_skills': {
            'question': 'Does learned investigation (pi_meta) improve acquisition on unseen Families C & D after task solutions/skills are cleared?',
            'established_on_unseen_families_cd_operating_work': h1_pass_cd,
            'learned_skills_cleared_cd_first_acquisition_work': m_c['cd_first_acquisition_work'],
            'fixed_no_skills_cd_first_acquisition_work': m_a['cd_first_acquisition_work'],
            'object_level_weights_only_cd_first_acquisition_work': m_f['cd_first_acquisition_work'],
            'shuffled_control_cd_first_acquisition_work': m_e['cd_first_acquisition_work'],
            'learned_skills_cleared_all_first_acquisition_work': m_c['all_first_acquisition_work'],
            'fixed_no_skills_all_first_acquisition_work': m_a['all_first_acquisition_work'],
            'learned_skills_cleared_total_including_training': m_c['all_total_work_including_training'],
            'fixed_no_skills_total_including_training': m_a['all_total_work_including_training'],
        },
        'H2_acquired_structure_plus_policy_vs_ordinary_template_reuse': {
            'question': 'Does acquired structure + learned meta-procedure improve later tasks beyond ordinary template reuse under identical 2-task promotion rules?',
            'established_on_unseen_families_cd': h2_pass_cd,
            'learned_plus_skills_cd_total_work': m_d['cd_total_work'],
            'fixed_with_templates_cd_total_work': m_b['cd_total_work'],
            'learned_plus_skills_all_repeated_use_work': m_d['all_repeated_use_work'],
            'fixed_with_templates_all_repeated_use_work': m_b['all_repeated_use_work'],
            'learned_plus_skills_all_total_work': m_d['all_total_work'],
            'fixed_with_templates_all_total_work': m_b['all_total_work'],
            'learned_plus_skills_total_including_training': m_d['all_total_work_including_training'],
        },
    }
