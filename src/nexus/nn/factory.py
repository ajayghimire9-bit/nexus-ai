from __future__ import annotations

from torch import nn

from nexus.nn.activations import get_activation
from nexus.nn.spec import ArchitectureSpec


class ResidualBlock(nn.Module):
    def __init__(self, inner: nn.Module) -> None:
        super().__init__()
        self.inner = inner

    def forward(self, x):  # type: ignore[no-untyped-def]
        return x + self.inner(x)


def _init_linear(layer: nn.Linear, method: str, gain: float) -> None:
    if method == "orthogonal":
        nn.init.orthogonal_(layer.weight, gain=gain)
    else:
        nn.init.xavier_uniform_(layer.weight, gain=gain)
    if layer.bias is not None:
        nn.init.zeros_(layer.bias)


def build_mlp(
    in_dim: int,
    hidden_sizes: tuple[int, ...],
    activation: str,
    *,
    use_residual: bool = False,
    dropout: float = 0.0,
    layer_norm: bool = False,
    init: str = "orthogonal",
) -> tuple[nn.Sequential, int]:
    """Build an MLP trunk. Returns (module, output_dim)."""
    layers: list[nn.Module] = []
    last = in_dim
    for width in hidden_sizes:
        block: list[nn.Module] = [nn.Linear(last, width)]
        _init_linear(block[0], init, gain=1.0)
        if layer_norm:
            block.append(nn.LayerNorm(width))
        block.append(get_activation(activation))
        if dropout > 0:
            block.append(nn.Dropout(dropout))
        sequential = nn.Sequential(*block)
        if use_residual and last == width:
            layers.append(ResidualBlock(sequential))
        else:
            layers.append(sequential)
        last = width
    return nn.Sequential(*layers), last


def build_from_spec(in_dim: int, spec: ArchitectureSpec) -> tuple[nn.Sequential, int]:
    return build_mlp(
        in_dim,
        spec.hidden_sizes,
        spec.activation,
        use_residual=spec.use_residual,
        dropout=spec.dropout,
        layer_norm=spec.layer_norm,
        init=spec.init,
    )
