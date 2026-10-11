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
    """Example composed candidate: x * sigmoid(a x) + b * tanh(x).

    Parameters a, b are learnable. This is a factory primitive for later
    activation search, not a claimed better-than-ReLU result.
    """

    def __init__(self) -> None:
        super().__init__()
        self.a = nn.Parameter(torch.ones(1))
        self.b = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(self.a * x) + self.b * torch.tanh(x)


ACTIVATIONS["swishish"] = Swishish


def get_activation(name: str) -> nn.Module:
    key = name.lower()
    if key not in ACTIVATIONS:
        known = ", ".join(sorted(ACTIVATIONS))
        raise ValueError(f"Unknown activation '{name}'. Known: {known}")
    return ACTIVATIONS[key]()
