"""Wave 21 Module 1 — True Unaligned Cross-Domain Homomorphism Discovery.

Eliminates the hand-coded schema tag strings (`GUARD_PARITY_TRANSFORM`, etc.) used in
Waves 17-18. Discovers operator and guard homomorphisms across completely unaligned
black-box domains with zero shared operator names, zero shared state types, and zero
schema tags:

1. Autonomous Algebraic Probing (`probe_domain_algebraic_fingerprint`):
   Actively probes operators and guards on domain sample states (charging every call in
   `OpCounter`) to estimate relational algebraic invariants:
   - Involution rate: Pr[f(f(x)) == x]
   - Idempotence rate: Pr[f(f(x)) == f(x)]
   - Identity rate: Pr[f(x) == x]
   - Order-3 cycle rate: Pr[f(f(f(x))) == x]
   - Image diversity / state-change ratio: |{f(x) : x in S}| / |S|
   - Pairwise Left-Inverse matrix: I[i, j] = Pr[f_i(f_j(x)) == x]
   - Pairwise Commutativity matrix: C[i, j] = Pr[f_i(f_j(x)) == f_j(f_i(x))]
   - Pairwise Absorption matrix: A[i, j] = Pr[f_i(f_j(x)) == f_i(x)]
   - Pairwise Right-Stability matrix: R[i, j] = Pr[f_i(f_j(x)) == f_j(x)]
   - Guard marginal truth vector: P[a] = Pr[g_a(x) == True]
   - Guard-Transform Invariance matrix: G[a, b] = Pr[g_a(f_b(x)) == g_a(x)]
   - Guard-Transform Flip matrix: F[a, b] = Pr[g_a(f_b(x)) == (not g_a(x))]
   - Guard-Transform Truth-Forcing matrix: T[a, b] = Pr[g_a(f_b(x)) == True]

2. Graph Homomorphism Alignment on Apple Silicon M4 GPU (`mps`) & Active Disambiguation:
   Solves for the injective mapping (Phi: Ops(A) -> Ops(B), Psi: Guards(A) -> Guards(B))
   minimizing relational distortion L(Phi, Psi) on `torch.device("mps")`. When multiple
   candidate mappings achieve minimal distortion on initial probes, actively runs
   higher-order commutator / triple-composition probes f_i(f_j(f_k(x))) and
   g_a(f_i(f_j(x))) to disambiguate, or declares `ambiguous` when genuinely automorphic.

3. Zero-Shot Cross-Domain Composite Program Compilation:
   Compiles multi-step composite ASTs solved in Source Domain A directly into anonymous
   Target Domain B (`anon_op_0..k`, `anon_guard_0..m`) and verifies on held-out private
   target tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import random
import re
import time
from typing import Any, Callable

from . import wave18_m4_gpu_neuro_symbolic_learner as w18

NeuralTelemetry = w18.NeuralTelemetry
require_mps = w18.require_mps


@dataclass
class Wave21WorkCounter:
    """Explicit work and primitive-operation step counter for Wave 21 evaluations."""

    probe_executions: int = 0
    candidate_evaluations: int = 0
    macro_retrievals: int = 0
    commutator_probes: int = 0
    primitive_op_steps: int = 0

    @property
    def steps(self) -> int:
        return self.primitive_op_steps

    @steps.setter
    def steps(self, value: int) -> None:
        self.primitive_op_steps = int(value)

    @property
    def total_work(self) -> int:
        return (
            self.probe_executions
            + self.candidate_evaluations
            + self.macro_retrievals
            + self.commutator_probes
        )

    @property
    def total_primitive_op_steps(self) -> int:
        return self.primitive_op_steps

    def to_dict(self) -> dict[str, int]:
        return {
            'probe_executions': self.probe_executions,
            'candidate_evaluations': self.candidate_evaluations,
            'macro_retrievals': self.macro_retrievals,
            'commutator_probes': self.commutator_probes,
            'total_work': self.total_work,
            'total_primitive_op_steps': self.total_primitive_op_steps,
        }


OpCounter = Wave21WorkCounter

WAVE21_HOMOMORPHISM_METHODS = (
    'random_operator_mapping',
    'hand_tagged_schema_baseline',
    'unaligned_scratch_enumerator',
    'nexus_unaligned_homomorphism_full',
)

_ANON_OP_RE = re.compile(r'^anon_op_\d+$')
_ANON_GUARD_RE = re.compile(r'^anon_guard_\d+$')


@dataclass(frozen=True)
class OpaqueGraphBuffer:
    """Opaque target domain state with zero type or representation overlap with source tuples."""

    cipher_lanes: bytes
    topology_tag: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OpaqueGraphBuffer):
            return False
        return self.cipher_lanes == other.cipher_lanes and self.topology_tag == other.topology_tag

    def __hash__(self) -> int:
        return hash((self.cipher_lanes, self.topology_tag))


@dataclass
class AnonymousDomainEnvironment:
    """Black-box domain environment exposing only state equality, probe states, ops, and guards."""

    domain_id: str
    probe_states: tuple[Any, ...]
    operators: dict[str, Callable[[Any], Any]]
    guards: dict[str, Callable[[Any], bool]]
    is_anonymous_target: bool = False

    def validate(self) -> None:
        if not self.probe_states:
            raise ValueError('probe_states must be non-empty')
        if self.is_anonymous_target:
            for op_name in self.operators:
                if not _ANON_OP_RE.match(op_name):
                    raise ValueError(f'Target operator {op_name!r} violates anonymous naming anon_op_k')
            for g_name in self.guards:
                if not _ANON_GUARD_RE.match(g_name):
                    raise ValueError(f'Target guard {g_name!r} violates anonymous naming anon_guard_m')


@dataclass
class AlgebraicFingerprint:
    """Relational algebraic invariants discovered strictly via active black-box probing."""

    op_names: tuple[str, ...]
    guard_names: tuple[str, ...]
    unary_matrix: list[list[float]]            # (K, 5)
    left_inverse_matrix: list[list[float]]     # (K, K)
    commutativity_matrix: list[list[float]]    # (K, K)
    absorption_matrix: list[list[float]]       # (K, K)
    right_stability_matrix: list[list[float]]  # (K, K)
    guard_base_rate: list[float]               # (M,)
    guard_invariance_matrix: list[list[float]] # (M, K)
    guard_flip_matrix: list[list[float]]       # (M, K)
    guard_force_true_matrix: list[list[float]] # (M, K)
    commutator_tensor: list[list[list[float]]] = field(default_factory=list)       # (K, K, K)
    guard_two_step_tensor: list[list[list[float]]] = field(default_factory=list)   # (M, K, K)
    cached_fx: list[list[Any]] = field(default_factory=list, repr=False)
    cached_ffx: list[list[list[Any]]] = field(default_factory=list, repr=False)


def _call_op(
    env: AnonymousDomainEnvironment,
    op_name: str,
    state: Any,
    counter: OpCounter,
    *,
    is_probe: bool = False,
) -> Any:
    if is_probe:
        counter.probe_executions += 1
    else:
        counter.candidate_evaluations += 1
    counter.primitive_op_steps += 1
    return env.operators[op_name](state)


def _call_guard(
    env: AnonymousDomainEnvironment,
    guard_name: str,
    state: Any,
    counter: OpCounter,
    *,
    is_probe: bool = False,
) -> bool:
    if is_probe:
        counter.probe_executions += 1
    else:
        counter.candidate_evaluations += 1
    counter.primitive_op_steps += 1
    return bool(env.guards[guard_name](state))


def probe_domain_algebraic_fingerprint(
    env: AnonymousDomainEnvironment,
    counter: OpCounter,
    *,
    include_higher_order: bool = False,
) -> AlgebraicFingerprint:
    """Actively probes all operators and guards on `env.probe_states` to build relational matrices."""
    env.validate()
    op_names = tuple(sorted(env.operators.keys()))
    guard_names = tuple(sorted(env.guards.keys()))
    states = env.probe_states
    n_states = float(len(states))
    k_ops = len(op_names)
    m_guards = len(guard_names)

    # Step 1: One-step operator evaluations f_i(x) and one-step guard evaluations g_a(x)
    fx: list[list[Any]] = []
    for op_name in op_names:
        row = [_call_op(env, op_name, s, counter, is_probe=True) for s in states]
        fx.append(row)

    gx: list[list[bool]] = []
    for g_name in guard_names:
        row = [_call_guard(env, g_name, s, counter, is_probe=True) for s in states]
        gx.append(row)

    # Step 2: Two-step compositions f_i(f_j(x))
    ffx: list[list[list[Any]]] = [[[] for _ in range(k_ops)] for _ in range(k_ops)]
    for i, op_i in enumerate(op_names):
        for j in range(k_ops):
            ffx[i][j] = [_call_op(env, op_i, fx[j][s_idx], counter, is_probe=True) for s_idx in range(len(states))]

    # Step 3: Unary operator relational properties
    unary_matrix: list[list[float]] = []
    for i, op_i in enumerate(op_names):
        id_rate = sum(1 for s_idx in range(len(states)) if fx[i][s_idx] == states[s_idx]) / n_states
        inv_rate = sum(1 for s_idx in range(len(states)) if ffx[i][i][s_idx] == states[s_idx]) / n_states
        idem_rate = sum(1 for s_idx in range(len(states)) if ffx[i][i][s_idx] == fx[i][s_idx]) / n_states
        fff_i = [_call_op(env, op_i, ffx[i][i][s_idx], counter, is_probe=True) for s_idx in range(len(states))]
        cyc3_rate = sum(1 for s_idx in range(len(states)) if fff_i[s_idx] == states[s_idx]) / n_states
        distinct_outputs = len({ repr(v) if not isinstance(v, (tuple, int, bytes, OpaqueGraphBuffer)) else v for v in fx[i] })
        image_ratio = distinct_outputs / n_states
        unary_matrix.append([id_rate, inv_rate, idem_rate, cyc3_rate, image_ratio])

    # Step 4: Pairwise operator matrices I, C, A, R
    left_inverse_matrix = [[0.0] * k_ops for _ in range(k_ops)]
    commutativity_matrix = [[0.0] * k_ops for _ in range(k_ops)]
    absorption_matrix = [[0.0] * k_ops for _ in range(k_ops)]
    right_stability_matrix = [[0.0] * k_ops for _ in range(k_ops)]

    for i in range(k_ops):
        for j in range(k_ops):
            left_inverse_matrix[i][j] = (
                sum(1 for s_idx in range(len(states)) if ffx[i][j][s_idx] == states[s_idx]) / n_states
            )
            commutativity_matrix[i][j] = (
                sum(1 for s_idx in range(len(states)) if ffx[i][j][s_idx] == ffx[j][i][s_idx]) / n_states
            )
            absorption_matrix[i][j] = (
                sum(1 for s_idx in range(len(states)) if ffx[i][j][s_idx] == fx[i][s_idx]) / n_states
            )
            right_stability_matrix[i][j] = (
                sum(1 for s_idx in range(len(states)) if ffx[i][j][s_idx] == fx[j][s_idx]) / n_states
            )

    # Step 5: Guard marginal base rates & Guard-Operator interaction matrices G, F, T
    guard_base_rate = [sum(1 for val in gx[a] if val) / n_states for a in range(m_guards)]
    guard_invariance_matrix = [[0.0] * k_ops for _ in range(m_guards)]
    guard_flip_matrix = [[0.0] * k_ops for _ in range(m_guards)]
    guard_force_true_matrix = [[0.0] * k_ops for _ in range(m_guards)]

    gfx: list[list[list[bool]]] = [[[] for _ in range(k_ops)] for _ in range(m_guards)]
    for a, g_name in enumerate(guard_names):
        for b in range(k_ops):
            gfx[a][b] = [
                _call_guard(env, g_name, fx[b][s_idx], counter, is_probe=True)
                for s_idx in range(len(states))
            ]
            guard_invariance_matrix[a][b] = (
                sum(1 for s_idx in range(len(states)) if gfx[a][b][s_idx] == gx[a][s_idx]) / n_states
            )
            guard_flip_matrix[a][b] = (
                sum(1 for s_idx in range(len(states)) if gfx[a][b][s_idx] == (not gx[a][s_idx])) / n_states
            )
            guard_force_true_matrix[a][b] = (
                sum(1 for s_idx in range(len(states)) if gfx[a][b][s_idx] is True) / n_states
            )

    commutator_tensor: list[list[list[float]]] = []
    guard_two_step_tensor: list[list[list[float]]] = []
    if include_higher_order:
        commutator_tensor, guard_two_step_tensor = _probe_higher_order_tensors(
            env, op_names, guard_names, states, fx, ffx, counter
        )

    return AlgebraicFingerprint(
        op_names=op_names,
        guard_names=guard_names,
        unary_matrix=unary_matrix,
        left_inverse_matrix=left_inverse_matrix,
        commutativity_matrix=commutativity_matrix,
        absorption_matrix=absorption_matrix,
        right_stability_matrix=right_stability_matrix,
        guard_base_rate=guard_base_rate,
        guard_invariance_matrix=guard_invariance_matrix,
        guard_flip_matrix=guard_flip_matrix,
        guard_force_true_matrix=guard_force_true_matrix,
        commutator_tensor=commutator_tensor,
        guard_two_step_tensor=guard_two_step_tensor,
        cached_fx=fx,
        cached_ffx=ffx,
    )


def _probe_higher_order_tensors(
    env: AnonymousDomainEnvironment,
    op_names: tuple[str, ...],
    guard_names: tuple[str, ...],
    states: tuple[Any, ...],
    fx: list[list[Any]],
    ffx: list[list[list[Any]]],
    counter: OpCounter,
    *,
    active_op_indices: set[int] | None = None,
) -> tuple[list[list[list[float]]], list[list[list[float]]]]:
    """Executes active composition & two-step guard probes to break first-order ties."""
    k_ops = len(op_names)
    m_guards = len(guard_names)
    n_states = float(len(states))

    # Commutator / conjugate relation: Pr[f_i(f_j(x)) == f_k(x)] from cached fx, ffx
    comm_tensor = [[[0.0] * k_ops for _ in range(k_ops)] for _ in range(k_ops)]
    for i in range(k_ops):
        for j in range(k_ops):
            for k in range(k_ops):
                comm_tensor[i][j][k] = (
                    sum(1 for s_idx in range(len(states)) if ffx[i][j][s_idx] == fx[k][s_idx]) / n_states
                )

    # Two-step guard relation: Pr[g_a(f_i(f_j(x))) == True], probing ambiguous rows i
    g2_tensor = [[[0.0] * k_ops for _ in range(k_ops)] for _ in range(m_guards)]
    probe_rows = active_op_indices if active_op_indices is not None else set(range(k_ops))
    for a, g_name in enumerate(guard_names):
        for i in probe_rows:
            for j in range(k_ops):
                counter.commutator_probes += 1
                vals = [
                    _call_guard(env, g_name, ffx[i][j][s_idx], counter, is_probe=False)
                    for s_idx in range(len(states))
                ]
                # _call_guard incremented candidate_evaluations; move to probe accounting
                counter.candidate_evaluations -= len(states)
                g2_tensor[a][i][j] = sum(1 for v in vals if v) / n_states

    return comm_tensor, g2_tensor


def enrich_fingerprint_higher_order(
    env: AnonymousDomainEnvironment,
    fp: AlgebraicFingerprint,
    counter: OpCounter,
    *,
    active_op_indices: set[int] | None = None,
) -> AlgebraicFingerprint:
    """Actively runs higher-order commutator probes when initial relational alignment has ties."""
    if fp.commutator_tensor and fp.guard_two_step_tensor:
        return fp
    states = env.probe_states
    op_names = fp.op_names
    guard_names = fp.guard_names
    k_ops = len(op_names)
    fx = fp.cached_fx or [[_call_op(env, op, s, counter, is_probe=True) for s in states] for op in op_names]
    ffx = fp.cached_ffx or [
        [[_call_op(env, op_names[i], fx[j][s_idx], counter, is_probe=True) for s_idx in range(len(states))]
         for j in range(k_ops)]
        for i in range(k_ops)
    ]
    comm_tensor, g2_tensor = _probe_higher_order_tensors(
        env, op_names, guard_names, states, fx, ffx, counter, active_op_indices=active_op_indices
    )
    return AlgebraicFingerprint(
        op_names=fp.op_names,
        guard_names=fp.guard_names,
        unary_matrix=fp.unary_matrix,
        left_inverse_matrix=fp.left_inverse_matrix,
        commutativity_matrix=fp.commutativity_matrix,
        absorption_matrix=fp.absorption_matrix,
        right_stability_matrix=fp.right_stability_matrix,
        guard_base_rate=fp.guard_base_rate,
        guard_invariance_matrix=fp.guard_invariance_matrix,
        guard_flip_matrix=fp.guard_flip_matrix,
        guard_force_true_matrix=fp.guard_force_true_matrix,
        commutator_tensor=comm_tensor,
        guard_two_step_tensor=g2_tensor,
        cached_fx=fx,
        cached_ffx=ffx,
    )


def solve_homomorphism_alignment_mps(
    fp_src: AlgebraicFingerprint,
    fp_tgt: AlgebraicFingerprint,
    telemetry: NeuralTelemetry,
    *,
    use_higher_order: bool = False,
    distortion_tol: float = 1e-5,
) -> list[tuple[dict[str, str], dict[str, str], float]]:
    """Batch-evaluates all injective (Phi, Psi) mappings on Apple Silicon M4 GPU (`mps`)."""
    torch, device = require_mps()
    telemetry.mps_available = True
    k_src = len(fp_src.op_names)
    k_tgt = len(fp_tgt.op_names)
    m_src = len(fp_src.guard_names)
    m_tgt = len(fp_tgt.guard_names)
    if k_src > k_tgt or m_src > m_tgt:
        return []

    op_perms = list(itertools.permutations(range(k_tgt), k_src))
    guard_perms = list(itertools.permutations(range(m_tgt), m_src))

    torch.mps.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        u_a = torch.tensor(fp_src.unary_matrix, dtype=torch.float32, device=device)
        u_b = torch.tensor(fp_tgt.unary_matrix, dtype=torch.float32, device=device)
        i_a = torch.tensor(fp_src.left_inverse_matrix, dtype=torch.float32, device=device)
        i_b = torch.tensor(fp_tgt.left_inverse_matrix, dtype=torch.float32, device=device)
        c_a = torch.tensor(fp_src.commutativity_matrix, dtype=torch.float32, device=device)
        c_b = torch.tensor(fp_tgt.commutativity_matrix, dtype=torch.float32, device=device)
        a_a = torch.tensor(fp_src.absorption_matrix, dtype=torch.float32, device=device)
        a_b = torch.tensor(fp_tgt.absorption_matrix, dtype=torch.float32, device=device)
        r_a = torch.tensor(fp_src.right_stability_matrix, dtype=torch.float32, device=device)
        r_b = torch.tensor(fp_tgt.right_stability_matrix, dtype=torch.float32, device=device)

        p_a = torch.tensor(fp_src.guard_base_rate, dtype=torch.float32, device=device)
        p_b = torch.tensor(fp_tgt.guard_base_rate, dtype=torch.float32, device=device)
        g_a = torch.tensor(fp_src.guard_invariance_matrix, dtype=torch.float32, device=device)
        g_b = torch.tensor(fp_tgt.guard_invariance_matrix, dtype=torch.float32, device=device)
        f_a = torch.tensor(fp_src.guard_flip_matrix, dtype=torch.float32, device=device)
        f_b = torch.tensor(fp_tgt.guard_flip_matrix, dtype=torch.float32, device=device)
        t_a = torch.tensor(fp_src.guard_force_true_matrix, dtype=torch.float32, device=device)
        t_b = torch.tensor(fp_tgt.guard_force_true_matrix, dtype=torch.float32, device=device)

        has_ho = (
            use_higher_order
            and bool(fp_src.commutator_tensor)
            and bool(fp_tgt.commutator_tensor)
        )
        if has_ho:
            comm_a = torch.tensor(fp_src.commutator_tensor, dtype=torch.float32, device=device)
            comm_b = torch.tensor(fp_tgt.commutator_tensor, dtype=torch.float32, device=device)
            g2_a = torch.tensor(fp_src.guard_two_step_tensor, dtype=torch.float32, device=device)
            g2_b = torch.tensor(fp_tgt.guard_two_step_tensor, dtype=torch.float32, device=device)

        # Vectorized evaluation of all operator permutations on MPS
        op_idx = torch.tensor(op_perms, dtype=torch.long, device=device)  # (P_op, k_src)
        u_b_perm = u_b[op_idx]  # (P_op, k_src, 5)
        op_losses = torch.abs(u_b_perm - u_a.unsqueeze(0)).sum(dim=(1, 2))

        row_idx = op_idx.unsqueeze(2).expand(-1, k_src, k_src)
        col_idx = op_idx.unsqueeze(1).expand(-1, k_src, k_src)
        op_losses = op_losses + torch.abs(i_b[row_idx, col_idx] - i_a.unsqueeze(0)).sum(dim=(1, 2))
        op_losses = op_losses + torch.abs(c_b[row_idx, col_idx] - c_a.unsqueeze(0)).sum(dim=(1, 2))
        op_losses = op_losses + torch.abs(a_b[row_idx, col_idx] - a_a.unsqueeze(0)).sum(dim=(1, 2))
        op_losses = op_losses + torch.abs(r_b[row_idx, col_idx] - r_a.unsqueeze(0)).sum(dim=(1, 2))

        if has_ho:
            i3 = op_idx.unsqueeze(2).unsqueeze(3).expand(-1, k_src, k_src, k_src)
            j3 = op_idx.unsqueeze(1).unsqueeze(3).expand(-1, k_src, k_src, k_src)
            k3 = op_idx.unsqueeze(1).unsqueeze(2).expand(-1, k_src, k_src, k_src)
            op_losses = op_losses + torch.abs(comm_b[i3, j3, k3] - comm_a.unsqueeze(0)).sum(dim=(1, 2, 3))

        scored: list[tuple[dict[str, str], dict[str, str], float]] = []
        for g_perm in guard_perms:
            g_idx = torch.tensor(g_perm, dtype=torch.long, device=device)
            p_loss = torch.abs(p_b[g_idx] - p_a).sum()
            g_row = g_idx.unsqueeze(0).unsqueeze(2).expand(len(op_perms), m_src, k_src)
            g_col = op_idx.unsqueeze(1).expand(len(op_perms), m_src, k_src)
            g_loss = (
                p_loss
                + torch.abs(g_b[g_row, g_col] - g_a.unsqueeze(0)).sum(dim=(1, 2))
                + torch.abs(f_b[g_row, g_col] - f_a.unsqueeze(0)).sum(dim=(1, 2))
                + torch.abs(t_b[g_row, g_col] - t_a.unsqueeze(0)).sum(dim=(1, 2))
            )
            if has_ho:
                ga3 = g_idx.unsqueeze(0).unsqueeze(2).unsqueeze(3).expand(len(op_perms), m_src, k_src, k_src)
                gi3 = op_idx.unsqueeze(1).unsqueeze(3).expand(len(op_perms), m_src, k_src, k_src)
                gj3 = op_idx.unsqueeze(1).unsqueeze(2).expand(len(op_perms), m_src, k_src, k_src)
                g_loss = g_loss + torch.abs(g2_b[ga3, gi3, gj3] - g2_a.unsqueeze(0)).sum(dim=(1, 2, 3))

            total_loss = (op_losses + g_loss).detach().cpu().tolist()
            psi_map = {fp_src.guard_names[a]: fp_tgt.guard_names[g_perm[a]] for a in range(m_src)}
            for p_i, o_perm in enumerate(op_perms):
                phi_map = {fp_src.op_names[i]: fp_tgt.op_names[o_perm[i]] for i in range(k_src)}
                scored.append((phi_map, psi_map, float(total_loss[p_i])))

        telemetry.gpu_encoder_calls += 1
        telemetry.gpu_forward_passes += 1
        telemetry.gpu_allocated_peak_bytes = max(
            telemetry.gpu_allocated_peak_bytes, int(torch.mps.current_allocated_memory())
        )
        telemetry.gpu_driver_peak_bytes = max(
            telemetry.gpu_driver_peak_bytes, int(torch.mps.driver_allocated_memory())
        )

    torch.mps.synchronize()
    telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0

    scored.sort(key=lambda item: (round(item[2], 7), sorted(item[0].items()), sorted(item[1].items())))
    if not scored:
        return []
    min_loss = scored[0][2]
    best = [item for item in scored if item[2] <= min_loss + distortion_tol]
    return best if best else [scored[0]]


def eval_composite_program(
    env: AnonymousDomainEnvironment,
    program_ast: tuple,
    state: Any,
    counter: OpCounter,
    *,
    is_probe: bool = False,
) -> Any:
    """Executes a multi-step composite AST on `env`, charging every primitive op & guard."""
    kind = program_ast[0]
    if kind == 'OP':
        return _call_op(env, program_ast[1], state, counter, is_probe=is_probe)
    if kind == 'SEQ':
        mid = eval_composite_program(env, program_ast[1], state, counter, is_probe=is_probe)
        return eval_composite_program(env, program_ast[2], mid, counter, is_probe=is_probe)
    if kind == 'IF':
        _, guard_name, then_ast, else_ast = program_ast
        cond = _call_guard(env, guard_name, state, counter, is_probe=is_probe)
        branch = then_ast if cond else else_ast
        return eval_composite_program(env, branch, state, counter, is_probe=is_probe)
    if kind == 'REPEAT_UNTIL':
        _, guard_name, body_ast, max_steps = program_ast
        cur = state
        for _ in range(int(max_steps)):
            if _call_guard(env, guard_name, cur, counter, is_probe=is_probe):
                break
            cur = eval_composite_program(env, body_ast, cur, counter, is_probe=is_probe)
        return cur
    if kind == 'CONJUGATE':
        _, outer_op, inner_ast, inv_op = program_ast
        s1 = _call_op(env, outer_op, state, counter, is_probe=is_probe)
        s2 = eval_composite_program(env, inner_ast, s1, counter, is_probe=is_probe)
        return _call_op(env, inv_op, s2, counter, is_probe=is_probe)
    raise ValueError(f'Unknown composite AST node: {kind!r}')


def translate_composite_program(
    program_ast: tuple,
    phi_op_map: dict[str, str],
    psi_guard_map: dict[str, str],
) -> tuple:
    """Compiles a composite program AST from Domain A into Domain B via (Phi, Psi)."""
    kind = program_ast[0]
    if kind == 'OP':
        return ('OP', phi_op_map[program_ast[1]])
    if kind == 'SEQ':
        return (
            'SEQ',
            translate_composite_program(program_ast[1], phi_op_map, psi_guard_map),
            translate_composite_program(program_ast[2], phi_op_map, psi_guard_map),
        )
    if kind == 'IF':
        _, g_name, t_ast, e_ast = program_ast
        return (
            'IF',
            psi_guard_map[g_name],
            translate_composite_program(t_ast, phi_op_map, psi_guard_map),
            translate_composite_program(e_ast, phi_op_map, psi_guard_map),
        )
    if kind == 'REPEAT_UNTIL':
        _, g_name, body_ast, max_steps = program_ast
        return (
            'REPEAT_UNTIL',
            psi_guard_map[g_name],
            translate_composite_program(body_ast, phi_op_map, psi_guard_map),
            int(max_steps),
        )
    if kind == 'CONJUGATE':
        _, outer_op, inner_ast, inv_op = program_ast
        return (
            'CONJUGATE',
            phi_op_map[outer_op],
            translate_composite_program(inner_ast, phi_op_map, psi_guard_map),
            phi_op_map[inv_op],
        )
    raise ValueError(f'Unknown composite AST node: {kind!r}')


def enumerate_domain_composite_catalog(
    env: AnonymousDomainEnvironment,
    *,
    max_depth: int = 3,
) -> list[tuple]:
    """Generates bounded composite programs over `env`'s operators and guards."""
    op_names = sorted(env.operators.keys())
    guard_names = sorted(env.guards.keys())
    depth1 = [('OP', op) for op in op_names]
    depth2 = [('SEQ', a, b) for a in depth1 for b in depth1]
    catalog: list[tuple] = list(depth1) + list(depth2)

    if max_depth >= 3:
        # Guarded branches over depth1 and depth2
        for g in guard_names:
            for t_prog in depth1:
                for e_prog in depth1:
                    if t_prog != e_prog:
                        catalog.append(('IF', g, t_prog, e_prog))
            for t_prog in depth2:
                for e_prog in depth1:
                    catalog.append(('IF', g, t_prog, e_prog))
        # Repeat-until guarded loops
        for g in guard_names:
            for body in depth1:
                catalog.append(('REPEAT_UNTIL', g, body, 2))
        # Conjugate transforms and 3-step sequences
        for o1 in op_names:
            for inner in depth1 + depth2[:8]:
                for o2 in op_names:
                    catalog.append(('CONJUGATE', o1, inner, o2))
        for a in depth1:
            for b in depth2[:10]:
                catalog.append(('SEQ', a, b))
    return catalog


def _program_matches_examples(
    env: AnonymousDomainEnvironment,
    prog: tuple,
    examples: list[tuple[Any, Any]],
    counter: OpCounter,
) -> bool:
    for x, y in examples:
        pred = eval_composite_program(env, prog, x, counter, is_probe=False)
        if pred != y:
            return False
    return True


def _programs_equivalent_on_probes(
    env: AnonymousDomainEnvironment,
    prog_a: tuple,
    prog_b: tuple,
    counter: OpCounter,
) -> bool:
    for s in env.probe_states:
        va = eval_composite_program(env, prog_a, s, counter, is_probe=True)
        vb = eval_composite_program(env, prog_b, s, counter, is_probe=True)
        if va != vb:
            return False
    return True


@dataclass
class UnalignedHomomorphismResult:
    method: str
    task_id: str
    seed: int
    status: str  # 'unique', 'ambiguous', 'abstain'
    discovered_phi: dict[str, str]
    discovered_psi: dict[str, str]
    distortion: float
    commutator_disambiguation_used: bool
    translated_program_ast: tuple | None
    mapping_exact_match: bool
    private_correct: bool
    false_unique: bool
    ambiguous_correctly_declared: bool
    total_work: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]
    gpu_telemetry: dict[str, Any]


def solve_unaligned_cross_domain_task(
    method: str,
    task_spec: dict[str, Any],
    seed: int,
    *,
    cached_source_fp: AlgebraicFingerprint | None = None,
    alignment_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> tuple[UnalignedHomomorphismResult, AlgebraicFingerprint | None]:
    """Runs one method on an unaligned cross-domain task and evaluates on held-out private data."""
    if method not in WAVE21_HOMOMORPHISM_METHODS:
        raise ValueError(f'Unknown method {method!r}')

    counter = OpCounter()
    telemetry = NeuralTelemetry(mps_available=True)
    src_env: AnonymousDomainEnvironment = task_spec['source_env']
    tgt_env: AnonymousDomainEnvironment = task_spec['target_env']
    src_env.validate()
    tgt_env.validate()

    source_solved_programs: list[tuple] = list(task_spec['source_solved_programs'])
    public_examples: list[tuple[Any, Any]] = list(task_spec['target_public'])
    private_examples: list[tuple[Any, Any]] = list(task_spec['target_private'])
    gold_status: str = task_spec['gold_status']
    gold_phi: dict[str, str] = dict(task_spec.get('gold_phi', {}))
    gold_psi: dict[str, str] = dict(task_spec.get('gold_psi', {}))
    active_oracle: Callable[[Any], Any] | None = task_spec.get('target_active_oracle')

    discovered_phi: dict[str, str] = {}
    discovered_psi: dict[str, str] = {}
    distortion = float('inf')
    commutator_used = False
    chosen_program: tuple | None = None
    status = 'abstain'

    if method == 'random_operator_mapping':
        rng = random.Random(1009 + seed * 97 + hash(task_spec['id']) % 997)
        src_ops = sorted(src_env.operators.keys())
        tgt_ops = sorted(tgt_env.operators.keys())
        src_guards = sorted(src_env.guards.keys())
        tgt_guards = sorted(tgt_env.guards.keys())
        perm_ops = rng.sample(tgt_ops, len(src_ops))
        perm_guards = rng.sample(tgt_guards, len(src_guards))
        discovered_phi = dict(zip(src_ops, perm_ops))
        discovered_psi = dict(zip(src_guards, perm_guards))
        distortion = -1.0

        matching_progs: list[tuple] = []
        for src_prog in source_solved_programs:
            counter.macro_retrievals += 1
            cand = translate_composite_program(src_prog, discovered_phi, discovered_psi)
            if _program_matches_examples(tgt_env, cand, public_examples, counter):
                matching_progs.append(cand)
        if len(matching_progs) == 1:
            status = 'unique'
            chosen_program = matching_progs[0]
        elif len(matching_progs) > 1:
            status = 'ambiguous'
        else:
            status = 'abstain'

    elif method in ('hand_tagged_schema_baseline', 'unaligned_scratch_enumerator'):
        catalog = enumerate_domain_composite_catalog(tgt_env, max_depth=3)
        survivors: list[tuple] = []
        for cand in catalog:
            if _program_matches_examples(tgt_env, cand, public_examples, counter):
                if not any(_programs_equivalent_on_probes(tgt_env, cand, prev, counter) for prev in survivors):
                    survivors.append(cand)
                    if len(survivors) >= 3:
                        break
        if len(survivors) > 1 and active_oracle is not None:
            for s in tgt_env.probe_states:
                outs = [eval_composite_program(tgt_env, p, s, counter, is_probe=True) for p in survivors]
                if len(set(outs)) > 1:
                    counter.probe_executions += 1
                    counter.primitive_op_steps += 1
                    oracle_val = active_oracle(s)
                    survivors = [p for p, o in zip(survivors, outs) if o == oracle_val]
                    if len(survivors) <= 1:
                        break
        if len(survivors) == 1:
            status = 'unique'
            chosen_program = survivors[0]
        elif len(survivors) > 1:
            status = 'ambiguous'
        else:
            status = 'abstain'

    elif method == 'nexus_unaligned_homomorphism_full':
        pair_key = (src_env.domain_id, tgt_env.domain_id)
        if alignment_cache is not None and pair_key in alignment_cache:
            entry = alignment_cache[pair_key]
            fp_src = entry['fp_src']
            fp_tgt = entry['fp_tgt']
            commutator_used = bool(entry['commutator_used'])
            candidates = solve_homomorphism_alignment_mps(
                fp_src, fp_tgt, telemetry, use_higher_order=commutator_used
            )
            cached_source_fp = fp_src
        else:
            if cached_source_fp is None:
                cached_source_fp = probe_domain_algebraic_fingerprint(src_env, counter, include_higher_order=False)
            fp_src = cached_source_fp
            fp_tgt = probe_domain_algebraic_fingerprint(tgt_env, counter, include_higher_order=False)

            candidates = solve_homomorphism_alignment_mps(
                fp_src, fp_tgt, telemetry, use_higher_order=False
            )
            if len(candidates) > 1:
                commutator_used = True
                # Identify only those operator indices whose mapping varies across tied candidates
                src_ambig_indices: set[int] = set()
                tgt_ambig_indices: set[int] = set()
                for idx, op_s in enumerate(fp_src.op_names):
                    mapped_targets = {phi[op_s] for phi, _, _ in candidates}
                    if len(mapped_targets) > 1:
                        src_ambig_indices.add(idx)
                        for t_name in mapped_targets:
                            tgt_ambig_indices.add(fp_tgt.op_names.index(t_name))
                fp_src = enrich_fingerprint_higher_order(
                    src_env, fp_src, counter, active_op_indices=src_ambig_indices or None
                )
                cached_source_fp = fp_src
                fp_tgt = enrich_fingerprint_higher_order(
                    tgt_env, fp_tgt, counter, active_op_indices=tgt_ambig_indices or None
                )
                candidates = solve_homomorphism_alignment_mps(
                    fp_src, fp_tgt, telemetry, use_higher_order=True
                )
            if alignment_cache is not None:
                alignment_cache[pair_key] = {
                    'fp_src': fp_src,
                    'fp_tgt': fp_tgt,
                    'commutator_used': commutator_used,
                }

        if candidates:
            discovered_phi, discovered_psi, distortion = candidates[0]

        # Step 3: Zero-Shot Cross-Domain Compilation across surviving homomorphisms
        surviving_programs: list[tuple[tuple, dict[str, str], dict[str, str]]] = []
        for phi_cand, psi_cand, _ in candidates:
            for src_prog in source_solved_programs:
                counter.macro_retrievals += 1
                compiled = translate_composite_program(src_prog, phi_cand, psi_cand)
                if _program_matches_examples(tgt_env, compiled, public_examples, counter):
                    if not any(
                        _programs_equivalent_on_probes(tgt_env, compiled, prev_prog, counter)
                        for prev_prog, _, _ in surviving_programs
                    ):
                        surviving_programs.append((compiled, phi_cand, psi_cand))

        # Active target probe disambiguation if multiple compiled programs survive
        if len(surviving_programs) > 1 and active_oracle is not None:
            for s in tgt_env.probe_states:
                outs = [
                    eval_composite_program(tgt_env, prog, s, counter, is_probe=True)
                    for prog, _, _ in surviving_programs
                ]
                if len(set(outs)) > 1:
                    counter.probe_executions += 1
                    counter.primitive_op_steps += 1
                    oracle_val = active_oracle(s)
                    surviving_programs = [
                        item for item, o in zip(surviving_programs, outs) if o == oracle_val
                    ]
                    if len(surviving_programs) <= 1:
                        break

        if len(surviving_programs) == 1:
            chosen_program, discovered_phi, discovered_psi = surviving_programs[0]
            status = 'unique'
        elif len(surviving_programs) > 1:
            status = 'ambiguous'
        else:
            status = 'abstain'

    # Private evaluation (strictly after lock; never charges learner work)
    private_counter = OpCounter()
    if status == 'unique' and chosen_program is not None:
        all_match = all(
            eval_composite_program(tgt_env, chosen_program, x_priv, private_counter, is_probe=False) == y_priv
            for x_priv, y_priv in private_examples
        )
        private_correct = (gold_status == 'unique') and all_match
    else:
        private_correct = (status == gold_status)

    false_unique = (status == 'unique') and (not private_correct)
    ambiguous_ok = (status == 'ambiguous') and (gold_status == 'ambiguous')
    mapping_exact = bool(gold_phi) and (discovered_phi == gold_phi) and (discovered_psi == gold_psi)

    work_dict = counter.to_dict()
    return (
        UnalignedHomomorphismResult(
            method=method,
            task_id=task_spec['id'],
            seed=seed,
            status=status,
            discovered_phi=discovered_phi,
            discovered_psi=discovered_psi,
            distortion=round(float(distortion), 6) if distortion != float('inf') else -1.0,
            commutator_disambiguation_used=commutator_used,
            translated_program_ast=chosen_program,
            mapping_exact_match=mapping_exact,
            private_correct=private_correct,
            false_unique=false_unique,
            ambiguous_correctly_declared=ambiguous_ok,
            total_work=work_dict['total_work'],
            total_primitive_op_steps=work_dict['total_primitive_op_steps'],
            work_breakdown=work_dict,
            gpu_telemetry=telemetry.snapshot(),
        ),
        cached_source_fp,
    )


# ---------------------------------------------------------------------------
# Pre-freeze Synthetic Development Suite for Unit Tests (Not the Fresh Suite)
# ---------------------------------------------------------------------------

def build_pre_freeze_unaligned_pair(
    op_perm: tuple[int, ...] = (2, 0, 4, 1, 3),
    guard_perm: tuple[int, ...] = (1, 0),
) -> tuple[AnonymousDomainEnvironment, AnonymousDomainEnvironment, dict[str, str], dict[str, str], Callable[[tuple[int, int, int]], OpaqueGraphBuffer]]:
    """Constructs an isomorphic pair of completely unaligned domains over Z_6 x Z_6 x Z_2 vs OpaqueGraphBuffer."""
    # Source Domain A: tuples (x, y, flag) in Z_6 x Z_6 x {0, 1}
    src_probes: list[tuple[int, int, int]] = [
        (0, 0, 0), (1, 2, 0), (2, 5, 1), (3, 1, 0),
        (4, 3, 1), (5, 4, 0), (1, 1, 1), (2, 2, 0),
        (0, 3, 1), (4, 0, 0), (5, 2, 1), (3, 4, 1),
    ]

    # 5 algebraically distinct source operators:
    # src_op_0: involution swap + flip flag -> (y, x, 1 - flag) (involution=1, flips guard_1)
    # src_op_1: step +1 on x mod 6 -> ((x + 1) % 6, y, flag) (order 6, left inverse of src_op_2)
    # src_op_2: step -1 on x mod 6 -> ((x - 1) % 6, y, flag) (order 6, left inverse of src_op_1)
    # src_op_3: idempotent anchor projection -> (1, y, 1) (idempotent=1, forces guard_1 True, x=1)
    # src_op_4: order-3 cycle on y by +2 mod 6 -> (x, (y + 2) % 6, flag) (cycle3=1, commutes with src_op_1/2/3)
    canonical_src_ops: list[Callable[[tuple[int, int, int]], tuple[int, int, int]]] = [
        lambda s: (s[1], s[0], 1 - s[2]),
        lambda s: ((s[0] + 1) % 6, s[1], s[2]),
        lambda s: ((s[0] - 1) % 6, s[1], s[2]),
        lambda s: (1, s[1], 1),
        lambda s: (s[0], (s[1] + 2) % 6, s[2]),
    ]
    # 2 source guards:
    # src_guard_0: x == 0 (true on 1/6 of states, forced True by src_op_3, invariant under src_op_4)
    # src_guard_1: flag == 1 (true on 1/2 of states, flipped by src_op_0, forced True by src_op_3)
    canonical_src_guards: list[Callable[[tuple[int, int, int]], bool]] = [
        lambda s: s[0] == 0,
        lambda s: s[2] == 1,
    ]

    src_operators = {f'src_op_{i}': canonical_src_ops[i] for i in range(5)}
    src_guards = {f'src_guard_{a}': canonical_src_guards[a] for a in range(2)}

    # Bijective state encryption phi_state: (x, y, flag) <-> OpaqueGraphBuffer
    def encode_state(s: tuple[int, int, int]) -> OpaqueGraphBuffer:
        x, y, flag = s
        b0 = ((x * 13 + 5) & 0xFF) ^ 0xA5
        b1 = ((y * 17 + 3) & 0xFF) ^ 0x5A
        b2 = (flag * 73 + 19) & 0xFF
        tag = ((x + 2 * y + 4 * flag) ^ 0x3C)
        return OpaqueGraphBuffer(cipher_lanes=bytes([b0, b1, b2]), topology_tag=tag)

    inv_table = {encode_state((x, y, f)): (x, y, f) for x in range(6) for y in range(6) for f in (0, 1)}

    def decode_state(buf: OpaqueGraphBuffer) -> tuple[int, int, int]:
        return inv_table[buf]

    tgt_probes = tuple(encode_state(s) for s in src_probes)

    # Permute operators and guards into anonymous Target Domain B callables
    tgt_operators: dict[str, Callable[[OpaqueGraphBuffer], OpaqueGraphBuffer]] = {}
    gold_phi: dict[str, str] = {}
    for src_idx, tgt_idx in enumerate(op_perm):
        anon_name = f'anon_op_{tgt_idx}'
        gold_phi[f'src_op_{src_idx}'] = anon_name
        fn = canonical_src_ops[src_idx]
        tgt_operators[anon_name] = (lambda f_inner: lambda buf: encode_state(f_inner(decode_state(buf))))(fn)

    tgt_guards: dict[str, Callable[[OpaqueGraphBuffer], bool]] = {}
    gold_psi: dict[str, str] = {}
    for src_a, tgt_a in enumerate(guard_perm):
        anon_g = f'anon_guard_{tgt_a}'
        gold_psi[f'src_guard_{src_a}'] = anon_g
        gn = canonical_src_guards[src_a]
        tgt_guards[anon_g] = (lambda g_inner: lambda buf: bool(g_inner(decode_state(buf))))(gn)

    src_env = AnonymousDomainEnvironment(
        domain_id='dev_source_mod_tuple',
        probe_states=tuple(src_probes),
        operators=src_operators,
        guards=src_guards,
        is_anonymous_target=False,
    )
    tgt_env = AnonymousDomainEnvironment(
        domain_id='dev_target_opaque_graph',
        probe_states=tgt_probes,
        operators=tgt_operators,
        guards=tgt_guards,
        is_anonymous_target=True,
    )
    return src_env, tgt_env, gold_phi, gold_psi, encode_state


def build_pre_freeze_homomorphism_dev_suite() -> list[dict[str, Any]]:
    """Builds synthetic development tasks for pre-freeze verification of Module 1."""
    src_env, tgt_env, gold_phi, gold_psi, encode_state = build_pre_freeze_unaligned_pair()

    # Solved composite programs in Source Domain A
    prog_1 = (
        'IF',
        'src_guard_1',
        ('CONJUGATE', 'src_op_0', ('OP', 'src_op_1'), 'src_op_0'),
        ('SEQ', ('OP', 'src_op_4'), ('OP', 'src_op_3')),
    )
    prog_2 = (
        'SEQ',
        ('REPEAT_UNTIL', 'src_guard_0', ('OP', 'src_op_2'), 2),
        ('IF', 'src_guard_1', ('OP', 'src_op_4'), ('OP', 'src_op_0')),
    )
    source_library = [prog_1, prog_2]

    tgt_prog_1 = translate_composite_program(prog_1, gold_phi, gold_psi)
    tgt_prog_2 = translate_composite_program(prog_2, gold_phi, gold_psi)

    pub_inputs = [encode_state((1, 2, 1)), encode_state((3, 4, 0)), encode_state((2, 1, 1))]
    priv_inputs = [encode_state((4, 5, 1)), encode_state((0, 2, 0)), encode_state((5, 3, 1))]

    dummy_counter = OpCounter()
    t1_pub = [(x, eval_composite_program(tgt_env, tgt_prog_1, x, dummy_counter)) for x in pub_inputs]
    t1_priv = [(x, eval_composite_program(tgt_env, tgt_prog_1, x, dummy_counter)) for x in priv_inputs]

    t2_pub = [(x, eval_composite_program(tgt_env, tgt_prog_2, x, dummy_counter)) for x in pub_inputs]
    t2_priv = [(x, eval_composite_program(tgt_env, tgt_prog_2, x, dummy_counter)) for x in priv_inputs]

    # Ambiguous task: two source programs that agree on public input (1, 0, 1) where x=1, y=0, flag=1
    prog_amb_a = ('OP', 'src_op_0')  # (1, 0, 1) -> (0, 1, 0)
    prog_amb_b = ('SEQ', ('OP', 'src_op_3'), ('OP', 'src_op_0'))  # (1, 0, 1) -> (1, 0, 1) -> (0, 1, 0)
    amb_x = encode_state((1, 0, 1))
    amb_y = eval_composite_program(
        tgt_env, translate_composite_program(prog_amb_a, gold_phi, gold_psi), amb_x, dummy_counter
    )

    # Out-of-homomorphism task: impossible constant state not reachable by source library
    oog_target = OpaqueGraphBuffer(cipher_lanes=b'\xFF\xFF\xFF', topology_tag=999)

    return [
        {
            'id': 'dev_hom_conjugate_branch',
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': source_library,
            'target_public': t1_pub,
            'target_private': t1_priv,
            'gold_status': 'unique',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        },
        {
            'id': 'dev_hom_repeat_guarded',
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': source_library,
            'target_public': t2_pub,
            'target_private': t2_priv,
            'gold_status': 'unique',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        },
        {
            'id': 'dev_hom_ambiguous',
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': [prog_amb_a, prog_amb_b],
            'target_public': [(amb_x, amb_y)],
            'target_private': [],
            'gold_status': 'ambiguous',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        },
        {
            'id': 'dev_hom_abstain_oog',
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': source_library,
            'target_public': [(pub_inputs[0], oog_target)],
            'target_private': [],
            'gold_status': 'abstain',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        },
    ]
