from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ACTION_KINDS = (
    "mutate_architecture",
    "crossover_architecture",
    "mutate_activation_expr",
    "search_learning_rate",
    "optimize_network_size",
    "extra_evaluation",
    "transfer_architecture",
)

ActionKind = Literal[
    "mutate_architecture",
    "crossover_architecture",
    "mutate_activation_expr",
    "search_learning_rate",
    "optimize_network_size",
    "extra_evaluation",
    "transfer_architecture",
]

ALLOWED_ENVS = frozenset({"CartPole-v1", "Acrobot-v1"})
FORBIDDEN_KEYS = frozenset({"code", "python", "exec", "eval", "source", "bytecode"})


def fingerprint_payload(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class ExperimentAction:
    """Validated research action. Never carries executable source."""

    kind: str
    env_id: str
    architecture: dict[str, Any]
    learning_rate: float
    train_timesteps: int
    train_seeds: tuple[int, ...]
    holdout_eval_seed: int
    assessment_eval_seed: int
    parent_ids: tuple[str, ...] = ()
    expr: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"unknown action kind: {self.kind}")
        if self.env_id not in ALLOWED_ENVS:
            raise ValueError(f"unsupported env_id: {self.env_id}")
        if not (1e-5 <= self.learning_rate <= 1e-2):
            raise ValueError("learning_rate out of allowed range")
        if self.train_timesteps < 0:
            raise ValueError("train_timesteps must be non-negative")
        if not self.train_seeds:
            raise ValueError("train_seeds must be non-empty")
        if any(k in FORBIDDEN_KEYS for k in self.architecture):
            raise ValueError("architecture must not contain executable fields")
        if "hidden_sizes" not in self.architecture:
            raise ValueError("architecture.hidden_sizes required")

    def fingerprint(self) -> str:
        return fingerprint_payload(
            {
                "kind": self.kind,
                "env_id": self.env_id,
                "architecture": self.architecture,
                "learning_rate": self.learning_rate,
                "train_timesteps": self.train_timesteps,
                "train_seeds": list(self.train_seeds),
                "holdout_eval_seed": self.holdout_eval_seed,
                "expr": self.expr,
            }
        )

    def estimated_timesteps(self) -> int:
        if self.kind == "extra_evaluation":
            return 0
        return int(self.train_timesteps) * len(self.train_seeds)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fingerprint"] = self.fingerprint()
        data["estimated_timesteps"] = self.estimated_timesteps()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentAction:
        payload = {
            "kind": data["kind"],
            "env_id": data["env_id"],
            "architecture": data["architecture"],
            "learning_rate": float(data["learning_rate"]),
            "train_timesteps": int(data["train_timesteps"]),
            "train_seeds": tuple(int(s) for s in data["train_seeds"]),
            "holdout_eval_seed": int(data["holdout_eval_seed"]),
            "assessment_eval_seed": int(data["assessment_eval_seed"]),
            "parent_ids": tuple(data.get("parent_ids") or ()),
            "expr": data.get("expr"),
            "notes": data.get("notes") or "",
        }
        return cls(**payload)


@dataclass
class Proposal:
    action: ExperimentAction
    predicted_value: float
    estimated_cost: int
    reason: str
    controller: str
    is_meta_rl: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "predicted_value": self.predicted_value,
            "estimated_cost": self.estimated_cost,
            "reason": self.reason,
            "controller": self.controller,
            "is_meta_rl": self.is_meta_rl,
            **self.extras,
        }
