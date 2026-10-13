"""Pendulum-v1 family. Discrete torque interface frozen before confirmation."""

from __future__ import annotations

from nexus.tasks.spec import TaskSpec
from nexus.world.rewards import PENDULUM_TORQUES

PENDULUM_OBS_DIM = 3
PENDULUM_N_ACTIONS = 3
PENDULUM_MAX_STEPS = 200
# Frozen before any confirmation return. Gymnasium default max_torque is 2.0.
PENDULUM_TORQUE_NEG, PENDULUM_TORQUE_ZERO, PENDULUM_TORQUE_POS = PENDULUM_TORQUES


def pendulum_default() -> TaskSpec:
    return TaskSpec(
        task_id="pendulum_default",
        family="pendulum",
        gym_id="Pendulum-v1",
        obs_dim=PENDULUM_OBS_DIM,
        n_actions=PENDULUM_N_ACTIONS,
        params={
            "torque_neg": float(PENDULUM_TORQUE_NEG),
            "torque_zero": float(PENDULUM_TORQUE_ZERO),
            "torque_pos": float(PENDULUM_TORQUE_POS),
        },
        train_split="confirm_pendulum",
        notes=(
            "Pendulum-v1 with 3 fixed torques {-2,0,+2}. Uses Gymnasium published reward. "
            "Discretization frozen before confirmation. Not CartPole reward."
        ),
    )


def pendulum_development() -> TaskSpec:
    """Default Gymnasium physics. Horizon selection only. Not confirmation."""
    t = pendulum_default()
    return TaskSpec(
        task_id="pendulum_v089_dev",
        family=t.family,
        gym_id=t.gym_id,
        obs_dim=t.obs_dim,
        n_actions=t.n_actions,
        params=dict(t.params),
        train_split="dev_pendulum",
        notes="Development physics (default g=10). Horizon/search selection only.",
    )


def pendulum_confirmation_targets() -> tuple[TaskSpec, ...]:
    """Frozen before ranking. Unused in the H=3 cross-environment confirm."""
    return (
        TaskSpec(
            task_id="pendulum_v089g_c0",
            family="pendulum",
            gym_id="Pendulum-v1",
            obs_dim=PENDULUM_OBS_DIM,
            n_actions=PENDULUM_N_ACTIONS,
            params={
                "torque_neg": float(PENDULUM_TORQUE_NEG),
                "torque_zero": float(PENDULUM_TORQUE_ZERO),
                "torque_pos": float(PENDULUM_TORQUE_POS),
                "g": 8.3,
            },
            train_split="confirm_pendulum_g",
            notes="Confirmation g=8.3. Frozen before horizon ranking.",
        ),
        TaskSpec(
            task_id="pendulum_v089g_c1",
            family="pendulum",
            gym_id="Pendulum-v1",
            obs_dim=PENDULUM_OBS_DIM,
            n_actions=PENDULUM_N_ACTIONS,
            params={
                "torque_neg": float(PENDULUM_TORQUE_NEG),
                "torque_zero": float(PENDULUM_TORQUE_ZERO),
                "torque_pos": float(PENDULUM_TORQUE_POS),
                "g": 12.1,
            },
            train_split="confirm_pendulum_g",
            notes="Confirmation g=12.1. Frozen before horizon ranking.",
        ),
    )


# Gymnasium Pendulum-v1 defaults. Frozen before this transfer confirm.
PENDULUM_SOURCE_G = 10.0
PENDULUM_SOURCE_M = 1.0
PENDULUM_SOURCE_L = 1.0
PENDULUM_PLAN_HORIZON = 16
PENDULUM_PLAN_CANDIDATES = 16


def _pendulum(task_id: str, split: str, notes: str, *, g: float, m: float, l: float) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        family="pendulum",
        gym_id="Pendulum-v1",
        obs_dim=PENDULUM_OBS_DIM,
        n_actions=PENDULUM_N_ACTIONS,
        params={
            "torque_neg": float(PENDULUM_TORQUE_NEG),
            "torque_zero": float(PENDULUM_TORQUE_ZERO),
            "torque_pos": float(PENDULUM_TORQUE_POS),
            "g": float(g),
            "m": float(m),
            "l": float(l),
        },
        train_split=split,
        notes=notes,
    )


def pendulum_source() -> TaskSpec:
    return _pendulum(
        "pendulum_source",
        "source_pendulum",
        "Default Gymnasium physics (g=10, m=1, l=1). Source pretrain only.",
        g=PENDULUM_SOURCE_G,
        m=PENDULUM_SOURCE_M,
        l=PENDULUM_SOURCE_L,
    )


def pendulum_transfer_development() -> TaskSpec:
    """Unseen vs source; unused as a confirmation ranking set."""
    return _pendulum(
        "pendulum_xfer_dev_g",
        "dev_pendulum_xfer",
        "Development gravity shift g=11.5. Detector/sanity only.",
        g=11.5,
        m=PENDULUM_SOURCE_M,
        l=PENDULUM_SOURCE_L,
    )


def pendulum_transfer_confirmation() -> tuple[TaskSpec, ...]:
    """Frozen before any confirm returns. Distinct from horizon-diagnostic g=8.3/12.1."""
    return (
        _pendulum("pendulum_xfer_c_g", "confirm_pendulum_xfer", "Confirm gravity g=6.5.", g=6.5, m=1.0, l=1.0),
        _pendulum("pendulum_xfer_c_m", "confirm_pendulum_xfer", "Confirm mass m=1.8.", g=10.0, m=1.8, l=1.0),
        _pendulum("pendulum_xfer_c_l", "confirm_pendulum_xfer", "Confirm length l=1.45.", g=10.0, m=1.0, l=1.45),
    )


def pendulum_transfer_sequence() -> tuple[TaskSpec, TaskSpec, TaskSpec, TaskSpec]:
    """A,B,C then held-out D. Frozen before confirmation. Not the confirm gravity/mass/length cells."""
    a = _pendulum("pendulum_xfer_A", "seq_pendulum_xfer", "Sequence A: g=9.0.", g=9.0, m=1.0, l=1.0)
    b = _pendulum("pendulum_xfer_B", "seq_pendulum_xfer", "Sequence B: m=0.55.", g=10.0, m=0.55, l=1.0)
    c = _pendulum("pendulum_xfer_C", "seq_pendulum_xfer", "Sequence C: l=0.65.", g=10.0, m=1.0, l=0.65)
    d = _pendulum("pendulum_xfer_D", "seq_pendulum_xfer", "Held-out D: g=13.5, m=1.35, l=1.25.", g=13.5, m=1.35, l=1.25)
    return a, b, c, d


def pendulum_meta_train() -> tuple[TaskSpec, ...]:
    """Reptile/multitask tasks. Frozen before architecture ranking and confirmation."""
    return (
        _pendulum("pendulum_meta_tr0", "meta_train", "Meta-train g=7.2.", g=7.2, m=1.0, l=1.0),
        _pendulum("pendulum_meta_tr1", "meta_train", "Meta-train m=0.7.", g=10.0, m=0.7, l=1.0),
        _pendulum("pendulum_meta_tr2", "meta_train", "Meta-train l=0.8.", g=10.0, m=1.0, l=0.8),
        _pendulum("pendulum_meta_tr3", "meta_train", "Meta-train mild compound.", g=10.8, m=1.2, l=1.1),
    )


def pendulum_meta_val() -> tuple[TaskSpec, ...]:
    """Architecture selection only. Not confirmation."""
    return (
        _pendulum("pendulum_meta_va0", "meta_val", "Meta-val g=14.0.", g=14.0, m=1.0, l=1.0),
        _pendulum("pendulum_meta_va1", "meta_val", "Meta-val m=1.5 l=0.9.", g=10.0, m=1.5, l=0.9),
    )


def pendulum_meta_confirm() -> tuple[TaskSpec, ...]:
    """Held-out physics. Frozen before ranking. Distinct from all prior Pendulum confirms."""
    return (
        _pendulum("pendulum_meta_c0", "meta_confirm", "Confirm g=5.5.", g=5.5, m=1.0, l=1.0),
        _pendulum("pendulum_meta_c1", "meta_confirm", "Confirm m=2.2.", g=10.0, m=2.2, l=1.0),
        _pendulum("pendulum_meta_c2", "meta_confirm", "Confirm l=1.7.", g=10.0, m=1.0, l=1.7),
        _pendulum("pendulum_meta_c3", "meta_confirm", "Confirm compound D'.", g=12.8, m=0.4, l=1.35),
    )


def pendulum_context_train() -> tuple[TaskSpec, ...]:
    """Eight source physics. Frozen before development returns. Not confirmation."""
    rows = (
        (8.0, 1.0, 1.0),
        (10.0, 0.85, 1.0),
        (10.0, 1.0, 1.15),
        (9.4, 1.25, 0.95),
        (11.0, 0.9, 1.05),
        (7.6, 1.1, 1.2),
        (12.4, 0.6, 0.85),
        (10.5, 1.35, 1.3),
    )
    return tuple(
        _pendulum(f"pendulum_ctx_tr{i}", "context_train", f"Context source {g, m, l}.", g=g, m=m, l=l)
        for i, (g, m, l) in enumerate(rows)
    )


def pendulum_context_development() -> tuple[TaskSpec, ...]:
    """Development only. Not an untouched confirmation set."""
    rows = ((6.0, 1.0, 1.0), (10.0, 2.0, 1.0), (10.0, 1.0, 1.55))
    return tuple(
        _pendulum(f"pendulum_ctx_dev{i}", "context_dev", f"Context development {g, m, l}.", g=g, m=m, l=l)
        for i, (g, m, l) in enumerate(rows)
    )


def pendulum_context_confirmation() -> tuple[TaskSpec, ...]:
    """Fresh confirmation physics. Do not evaluate until the development gate passes."""
    rows = ((4.8, 1.0, 1.0), (15.2, 1.0, 1.0), (10.0, 0.35, 1.0), (11.8, 1.6, 0.75))
    return tuple(
        _pendulum(f"pendulum_ctx_c{i}", "context_confirm", f"Context confirmation {g, m, l}.", g=g, m=m, l=l)
        for i, (g, m, l) in enumerate(rows)
    )


def pendulum_physics_key(spec: TaskSpec) -> tuple[float, float, float]:
    p = spec.params
    return (float(p.get("g", PENDULUM_SOURCE_G)), float(p.get("m", PENDULUM_SOURCE_M)), float(p.get("l", PENDULUM_SOURCE_L)))


def tensors_compatible(a: TaskSpec, b: TaskSpec) -> bool:
    """Weight transfer requires matching obs/action tensor sizes. Not a claim of transfer."""
    return a.obs_dim == b.obs_dim and a.n_actions == b.n_actions and a.family == b.family
