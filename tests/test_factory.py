from __future__ import annotations

import torch

from nexus.nn.factory import build_from_spec
from nexus.nn.spec import ArchitectureSpec


def test_spec_rejects_empty() -> None:
    try:
        ArchitectureSpec(hidden_sizes=())
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_mlp_forward_shape() -> None:
    spec = ArchitectureSpec(hidden_sizes=(32, 16), activation="relu")
    net, out_dim = build_from_spec(4, spec)
    x = torch.randn(8, 4)
    y = net(x)
    assert y.shape == (8, 16)
    assert out_dim == 16


def test_residual_same_width() -> None:
    spec = ArchitectureSpec(hidden_sizes=(32, 32), activation="tanh", use_residual=True)
    net, _ = build_from_spec(32, spec)
    x = torch.randn(2, 32)
    y = net(x)
    assert y.shape == x.shape
    assert torch.isfinite(y).all()


def test_unknown_activation() -> None:
    try:
        ArchitectureSpec(hidden_sizes=(8,), activation="not-a-fn")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
