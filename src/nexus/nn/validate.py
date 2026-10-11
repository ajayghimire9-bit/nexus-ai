from __future__ import annotations

from typing import Any

import torch
from torch import nn


def validate_activation(
    module: nn.Module,
    *,
    lo: float = -8.0,
    hi: float = 8.0,
    n: int = 513,
    gradcheck_eps: float = 1e-4,
) -> dict[str, Any]:
    """Numerical stability, autograd, and finite-difference gradient checks."""
    module = module.train(False)
    x = torch.linspace(lo, hi, n, dtype=torch.float32, requires_grad=True)
    try:
        y = module(x)
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "reason": f"forward_failed:{exc}"}
    if not torch.isfinite(y).all():
        return {"passed": False, "reason": "non_finite_forward", "max_abs_y": float("nan")}

    y_sum = y.sum()
    try:
        y_sum.backward()
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "reason": f"backward_failed:{exc}"}
    if x.grad is None or not torch.isfinite(x.grad).all():
        return {"passed": False, "reason": "non_finite_grad"}

    analytic = x.grad.detach()
    with torch.no_grad():
        x_np = x.detach()
        yp = module(x_np + gradcheck_eps)
        ym = module(x_np - gradcheck_eps)
        numeric = (yp - ym) / (2 * gradcheck_eps)
        abs_err = (analytic - numeric).abs()
        rel = abs_err / (numeric.abs() + 1e-3)
        mask = x_np.abs() > 1e-2
        denom = numeric.abs() + 1e-3
        mixed_ok = bool((abs_err <= (1e-2 + 0.05 * numeric.abs()))[mask].all()) if bool(mask.any()) else bool((abs_err <= 1e-2).all())
        max_rel = float(rel[mask].max().item()) if bool(mask.any()) else float(rel.max().item())

    # Double-precision autograd.gradcheck on a tiny input.
    module_d = module.double() if hasattr(module, "double") else module
    xd = torch.randn(7, dtype=torch.float64, requires_grad=True)

    def _fn(inp: torch.Tensor) -> torch.Tensor:
        return module_d(inp)

    try:
        gradcheck_ok = bool(torch.autograd.gradcheck(_fn, (xd,), eps=1e-6, atol=1e-4, raise_exception=False))
    except Exception:  # noqa: BLE001
        gradcheck_ok = False

    passed = mixed_ok
    return {
        "passed": passed,
        "reason": "ok" if passed else "grad_mismatch",
        "max_abs_y": float(y.detach().abs().max().item()),
        "max_abs_grad": float(analytic.abs().max().item()),
        "max_rel_finite_diff": max_rel,
        "gradcheck_ok": gradcheck_ok,
    }
