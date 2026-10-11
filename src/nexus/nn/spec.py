from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

ALLOWED_INIT = {"orthogonal", "xavier"}
ALLOWED_ACTIVATIONS = {
    "relu",
    "gelu",
    "silu",
    "tanh",
    "elu",
    "identity",
    "swishish",
}


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
        if self.activation.lower() not in ALLOWED_ACTIVATIONS:
            raise ValueError(f"unsupported activation: {self.activation}")
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
        return cls(**payload)
