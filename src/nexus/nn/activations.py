from __future__ import annotations

import torch
from torch import nn

ACTIVATIONS: dict[str, type[nn.Module]] = {
    "relu": nn.ReLU,
    "gelu": nn.GELU,
    "silu": nn.SiLU,
    "tanh": nn.Tanh,
    "elu": nn.ELU,
    "identity": nn.Identity,
}


class Swishish(nn.Module):
    """Composed candidate: x * sigmoid(a x) + b * tanh(x)."""

    def __init__(self) -> None:
        super().__init__()
        self.a = nn.Parameter(torch.ones(1))
        self.b = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(self.a * x) + self.b * torch.tanh(x)


class Mish(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.tanh(torch.nn.functional.softplus(x))


class XTanh(nn.Module):
    """Candidate primitive product. Stability tests may reject large |x|."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.tanh(x)


class SoftplusTanh(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.tanh(torch.nn.functional.softplus(x))


class BoundedExpLin(nn.Module):
    """x + 0.1 * (exp(clamp(x,-8,8)) - 1) — bounded exponential mix."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + 0.1 * (torch.exp(x.clamp(-8.0, 8.0)) - 1.0)


ACTIVATIONS["swishish"] = Swishish
ACTIVATIONS["mish"] = Mish
ACTIVATIONS["xtanh"] = XTanh
ACTIVATIONS["softplus_tanh"] = SoftplusTanh
ACTIVATIONS["bounded_explin"] = BoundedExpLin

BASELINE_ACTIVATIONS = ("relu", "gelu", "silu", "tanh")
SEARCH_ACTIVATIONS = (
    "relu",
    "gelu",
    "silu",
    "tanh",
    "elu",
    "swishish",
    "mish",
    "xtanh",
    "softplus_tanh",
    "bounded_explin",
)


def get_activation(name: str) -> nn.Module:
    key = name.lower()
    if key not in ACTIVATIONS:
        known = ", ".join(sorted(ACTIVATIONS))
        raise ValueError(f"Unknown activation '{name}'. Known: {known}")
    return ACTIVATIONS[key]()
