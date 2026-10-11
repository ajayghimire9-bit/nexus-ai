from __future__ import annotations

import torch

from nexus.nn.activations import Swishish, get_activation


def test_named_activations_finite() -> None:
    x = torch.linspace(-5, 5, 16)
    for name in ("relu", "gelu", "silu", "tanh", "elu", "identity"):
        y = get_activation(name)(x)
        assert y.shape == x.shape
        assert torch.isfinite(y).all()


def test_swishish_autograd() -> None:
    m = Swishish()
    x = torch.randn(8, requires_grad=True)
    y = m(x).sum()
    y.backward()
    assert x.grad is not None
    assert torch.isfinite(x.grad).all()
    assert torch.isfinite(m.a.grad).all()
