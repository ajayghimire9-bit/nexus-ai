from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from nexus.nn.activations import ACTIVATIONS

ALLOWED_INIT = {"orthogonal", "xavier"}
ALLOWED_ACTIVATIONS = ACTIVATIONS


@dataclass(frozen=True)
class ArchitectureSpec:
    """Validated neural architecture description for the factory."""

    hidden_sizes: tuple[int, ...]
    activation: str = "tanh"
    use_residual: bool = False
    dropout: float = 0.0
    layer_norm: bool = False
    shared_backbone: bool = True
    init: str = "orthogonal"

    def __post_init__(self) -> None:
        if not self.hidden_sizes:
            raise ValueError("hidden_sizes must be non-empty")
        if any(h <= 0 for h in self.hidden_sizes):
            raise ValueError("hidden sizes must be positive")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")
        key = self.activation.lower()
        if key not in ALLOWED_ACTIVATIONS and not key.startswith("expr_"):
            raise ValueError(f"unsupported activation: {self.activation}")
        if key.startswith("expr_") and key not in ALLOWED_ACTIVATIONS:
            raise ValueError(
                f"dynamic activation '{self.activation}' is not registered in this process"
            )
        if self.init not in ALLOWED_INIT:
            raise ValueError(f"unsupported init: {self.init}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hidden_sizes"] = list(self.hidden_sizes)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureSpec:
        payload = dict(data)
        payload["hidden_sizes"] = tuple(payload["hidden_sizes"])
        expr_tree = payload.pop("expr_tree", None)
        act = str(payload.get("activation", "tanh"))
        if act.startswith("expr_"):
            from nexus.nn.expr import maybe_restore_named

            maybe_restore_named(act, expr_tree if isinstance(expr_tree, dict) else None)
        return cls(**payload)
