from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from nexus.evolution.mutate import WIDTHS, crossover_spec, mutate_spec, random_spec
from nexus.meta.schema import ACTION_KINDS, ExperimentAction, Proposal
from nexus.nn.expr import canonical_key, crossover_expr, expr_to_str, mutate_expr, random_expr, register_expr
from nexus.nn.spec import ArchitectureSpec
from nexus.nn.validate import validate_activation
from nexus.nn.activations import get_activation

CONTEXT_DIM = 8


def _spec_dict(spec: ArchitectureSpec) -> dict[str, Any]:
    return spec.to_dict()


def _context(
    *,
    remaining_frac: float,
    n_prior: int,
    fail_rate: float,
    best_score: float,
    last_reward: float,
    complexity: float,
    budget_used_frac: float,
    extra_eval_recent: float,
) -> np.ndarray:
    return np.asarray(
        [
            remaining_frac,
            math.log1p(n_prior) / 5.0,
            fail_rate,
            max(-1.0, min(1.0, best_score)),
            max(-1.0, min(1.0, last_reward)),
            max(0.0, min(1.0, complexity)),
            budget_used_frac,
            extra_eval_recent,
        ],
        dtype=np.float64,
    )


class ResearchController(ABC):
    """Selects a validated ExperimentAction. Not allowed to edit safety or budget caps."""

    name: str
    is_meta_rl: bool = False

    @abstractmethod
    def propose(self, state: dict[str, Any], limits: dict[str, Any], rng: random.Random) -> Proposal:
        raise NotImplementedError

    def update(self, context: np.ndarray, kind: str, reward: float) -> None:
        return None

    def state_dict(self) -> dict[str, Any]:
        return {"name": self.name}

    def load_state_dict(self, payload: dict[str, Any]) -> None:
        return None


def _fill_action(
    kind: str,
    state: dict[str, Any],
    limits: dict[str, Any],
    rng: random.Random,
) -> ExperimentAction:
    env_id = str(limits["env_id"])
    if kind == "transfer_architecture":
        env_id = str(limits["transfer_env_id"])
    train_seeds = tuple(int(s) for s in limits["train_seeds"])
    holdout = int(limits["holdout_eval_seed"])
    assessment = int(limits["assessment_eval_seed"])
    timesteps = int(limits["train_timesteps"])
    lr = float(limits["learning_rate"])
    elites: list[ArchitectureSpec] = list(state.get("elites") or [])
    parent = elites[0] if elites else ArchitectureSpec.from_dict(state["default_architecture"])
    expr = None
    notes = kind
    if kind == "mutate_architecture":
        spec = mutate_spec(parent, rng)
    elif kind == "crossover_architecture":
        other = elites[1] if len(elites) > 1 else ArchitectureSpec.from_dict(state["default_architecture"])
        spec = crossover_spec(parent, other, rng)
    elif kind == "optimize_network_size":
        sizes = list(parent.hidden_sizes)
        i = rng.randrange(len(sizes))
        sizes[i] = rng.choice(WIDTHS)
        spec = ArchitectureSpec(
            hidden_sizes=tuple(sizes),
            activation=parent.activation,
            use_residual=parent.use_residual,
            dropout=parent.dropout,
            layer_norm=parent.layer_norm,
            shared_backbone=parent.shared_backbone,
            init=parent.init,
        )
    elif kind == "search_learning_rate":
        spec = parent
        lr = float(rng.choice([1e-4, 2.5e-4, 3e-4, 5e-4, 1e-3]))
    elif kind == "mutate_activation_expr":
        node = mutate_expr(state.get("best_expr") or random_expr(rng, depth=2), rng)
        if rng.random() < 0.3 and state.get("best_expr"):
            node = crossover_expr(state["best_expr"], random_expr(rng, depth=2), rng)
        name = register_expr(node)
        report = validate_activation(get_activation(name))
        if not report["passed"]:
            spec = parent
            notes = "expr_rejected_fallback_parent"
        else:
            spec = ArchitectureSpec(
                hidden_sizes=parent.hidden_sizes,
                activation=name,
                use_residual=parent.use_residual,
                dropout=parent.dropout,
                layer_norm=parent.layer_norm,
                shared_backbone=parent.shared_backbone,
                init=parent.init,
            )
            expr = expr_to_str(node)
            notes = f"expr:{canonical_key(node)}"
    elif kind == "extra_evaluation":
        spec = parent
        timesteps = 0
        notes = "controller_feedback_holdout_vs_assessment_split"
    elif kind == "transfer_architecture":
        spec = parent
    else:
        spec = random_spec(rng)
    return ExperimentAction(
        kind=kind,
        env_id=env_id,
        architecture=_spec_dict(spec),
        learning_rate=lr,
        train_timesteps=timesteps,
        train_seeds=train_seeds,
        holdout_eval_seed=holdout,
        assessment_eval_seed=assessment,
        notes=notes,
        expr=expr,
    )


class RandomController(ResearchController):
    name = "random"
    is_meta_rl = False

    def propose(self, state: dict[str, Any], limits: dict[str, Any], rng: random.Random) -> Proposal:
        kind = rng.choice(ACTION_KINDS)
        action = _fill_action(kind, state, limits, rng)
        return Proposal(
            action=action,
            predicted_value=0.0,
            estimated_cost=action.estimated_timesteps(),
            reason="Uniform random action among the seven validated research actions.",
            controller=self.name,
            is_meta_rl=False,
        )


class EpsilonGreedyController(ResearchController):
    """Heuristic proposer. Not a trained bandit and not meta-RL."""

    name = "epsilon_greedy"
    is_meta_rl = False

    def __init__(self, epsilon: float = 0.2) -> None:
        self.epsilon = epsilon

    def propose(self, state: dict[str, Any], limits: dict[str, Any], rng: random.Random) -> Proposal:
        if rng.random() < self.epsilon or not state.get("elites"):
            kind = rng.choice(ACTION_KINDS)
            reason = f"ε-greedy explore (ε={self.epsilon})."
        else:
            kind = "mutate_architecture"
            reason = "ε-greedy exploit: mutate current elite on the same env/budget."
        action = _fill_action(kind, state, limits, rng)
        return Proposal(
            action=action,
            predicted_value=float(state.get("best_score") or 0.0),
            estimated_cost=action.estimated_timesteps(),
            reason=reason,
            controller=self.name,
            is_meta_rl=False,
        )

    def state_dict(self) -> dict[str, Any]:
        return {"name": self.name, "epsilon": self.epsilon}

    def load_state_dict(self, payload: dict[str, Any]) -> None:
        self.epsilon = float(payload.get("epsilon", self.epsilon))


class LinUCBController(ResearchController):
    """Disjoint LinUCB over research-action arms.

    This is a contextual bandit, not meta-RL: there is no inner/outer RL loop
    and no policy over sequential experiment trajectories.
    """

    name = "linucb"
    is_meta_rl = False

    def __init__(self, alpha: float = 0.5, n_arms: int = len(ACTION_KINDS)) -> None:
        self.alpha = alpha
        self.n_arms = n_arms
        d = CONTEXT_DIM
        self.A = [np.eye(d, dtype=np.float64) for _ in range(n_arms)]
        self.b = [np.zeros(d, dtype=np.float64) for _ in range(n_arms)]

    def _ucb(self, x: np.ndarray) -> np.ndarray:
        scores = np.zeros(self.n_arms, dtype=np.float64)
        for a in range(self.n_arms):
            a_inv = np.linalg.pinv(self.A[a])
            theta = a_inv @ self.b[a]
            scores[a] = float(theta @ x + self.alpha * math.sqrt(max(0.0, float(x @ a_inv @ x))))
        return scores

    def propose(self, state: dict[str, Any], limits: dict[str, Any], rng: random.Random) -> Proposal:
        x = np.asarray(state["context"], dtype=np.float64)
        scores = self._ucb(x)
        remaining = int(limits["remaining_timesteps"])
        # Do not select an action whose estimated cost exceeds the frozen budget.
        masked = scores.copy()
        for i, kind in enumerate(ACTION_KINDS):
            cost = 0 if kind == "extra_evaluation" else int(limits["train_timesteps"]) * len(limits["train_seeds"])
            if cost > remaining and kind != "extra_evaluation":
                masked[i] = -1e9
        arm = int(np.argmax(masked))
        if masked[arm] <= -1e8:
            arm = ACTION_KINDS.index("extra_evaluation")
        kind = ACTION_KINDS[arm]
        action = _fill_action(kind, state, limits, rng)
        return Proposal(
            action=action,
            predicted_value=float(scores[arm]),
            estimated_cost=action.estimated_timesteps(),
            reason=(
                f"LinUCB arm={kind} UCB={scores[arm]:.4f}. "
                "Contextual bandit over action types; not meta-RL."
            ),
            controller=self.name,
            is_meta_rl=False,
            extras={"ucb_scores": {k: float(scores[i]) for i, k in enumerate(ACTION_KINDS)}},
        )

    def update(self, context: np.ndarray, kind: str, reward: float) -> None:
        arm = ACTION_KINDS.index(kind)
        x = np.asarray(context, dtype=np.float64)
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x

    def state_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "alpha": self.alpha,
            "A": [m.tolist() for m in self.A],
            "b": [v.tolist() for v in self.b],
        }

    def load_state_dict(self, payload: dict[str, Any]) -> None:
        if payload.get("A"):
            self.A = [np.asarray(m, dtype=np.float64) for m in payload["A"]]
        if payload.get("b"):
            self.b = [np.asarray(v, dtype=np.float64) for v in payload["b"]]
        self.alpha = float(payload.get("alpha", self.alpha))


class FrozenLinUCBController(LinUCBController):
    """Same initialization as LinUCB, but parameters never update.

    Ablation: any advantage that remains here is prior/initialization, not learning.
    """

    name = "linucb_frozen"

    def update(self, context: np.ndarray, kind: str, reward: float) -> None:
        return None

    def propose(self, state: dict[str, Any], limits: dict[str, Any], rng: random.Random) -> Proposal:
        proposal = super().propose(state, limits, rng)
        proposal.controller = self.name
        proposal.reason = "Frozen LinUCB (no parameter updates). Not meta-RL."
        proposal.is_meta_rl = False
        return proposal

    def state_dict(self) -> dict[str, Any]:
        data = super().state_dict()
        data["name"] = self.name
        data["frozen"] = True
        return data


def make_controller(name: str, **kwargs: Any) -> ResearchController:
    if name == "random":
        return RandomController()
    if name in {"epsilon_greedy", "egreedy", "epsilon"}:
        return EpsilonGreedyController(epsilon=float(kwargs.get("epsilon", 0.2)))
    if name == "linucb":
        return LinUCBController(alpha=float(kwargs.get("alpha", 0.5)))
    if name in {"linucb_frozen", "frozen_linucb"}:
        return FrozenLinUCBController(alpha=float(kwargs.get("alpha", 0.5)))
    raise ValueError(f"unknown controller: {name}")


def build_controller_state(
    *,
    remaining_frac: float,
    n_prior: int,
    fail_rate: float,
    best_score: float,
    last_reward: float,
    n_params: int,
    budget_used_frac: float,
    extra_eval_recent: float,
    elites: list[ArchitectureSpec],
    default_architecture: dict[str, Any],
    best_expr: Any | None,
) -> dict[str, Any]:
    complexity = math.log(max(n_params, 2)) / 12.0
    ctx = _context(
        remaining_frac=remaining_frac,
        n_prior=n_prior,
        fail_rate=fail_rate,
        best_score=best_score,
        last_reward=last_reward,
        complexity=complexity,
        budget_used_frac=budget_used_frac,
        extra_eval_recent=extra_eval_recent,
    )
    return {
        "context": ctx,
        "elites": elites,
        "default_architecture": default_architecture,
        "best_score": best_score,
        "best_expr": best_expr,
    }
