from __future__ import annotations

from nexus.nn.activations import get_activation
from nexus.nn.validate import validate_activation


def test_relu_passes_checks() -> None:
    report = validate_activation(get_activation("relu"))
    assert report["passed"] is True


def test_silu_passes_checks() -> None:
    report = validate_activation(get_activation("silu"))
    assert report["passed"] is True
    assert report["gradcheck_ok"] is True


def test_tanh_passes_saturation_fd() -> None:
    report = validate_activation(get_activation("tanh"))
    assert report["passed"] is True


def test_nonfinite_forward_rejected() -> None:
    import torch
    from torch import nn

    class Boom(nn.Module):
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return x * float("inf")

    report = validate_activation(Boom())
    assert report["passed"] is False
    assert report["reason"] == "non_finite_forward"


def test_relu_is_nonsmooth_and_still_passes() -> None:
    report = validate_activation(get_activation("relu"))
    assert report["nonsmooth"] is True
    assert report["passed"] is True


def test_running_mean_std() -> None:
    import numpy as np

    from nexus.rl.running_stats import RunningMeanStd

    rms = RunningMeanStd((2,))
    data = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    rms.update(data)
    assert rms.mean.shape == (2,)
    normed = rms.normalize(data)
    assert np.isfinite(normed).all()
    assert abs(normed.mean()) < 1.0
