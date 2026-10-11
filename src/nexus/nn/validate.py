from __future__ import annotations

from typing import Any

import torch
from torch import nn

# Piecewise-linear / kinked maps: subgradients exist; autograd.gradcheck at 0 is not required.
_NONSMOOTH_TYPES = (nn.ReLU, nn.ReLU6, nn.LeakyReLU, nn.PReLU, nn.Threshold)


def _is_nonsmooth(module: nn.Module) -> bool:
    return isinstance(module, _NONSMOOTH_TYPES)


def validate_activation(
    module: nn.Module,
    *,
    lo: float = -8.0,
    hi: float = 8.0,
    n: int = 513,
    gradcheck_eps: float = 1e-4,
) -> dict[str, Any]:
    """Numerical stability, autograd, and finite-difference gradient checks.

    Smooth maps (tanh, GELU, SiLU, …) must pass autograd.gradcheck.
    Nondifferentiable maps (ReLU family) must be finite and match FD away from kinks.
    Nonfinite forward values or gradients always fail.
    """
    module = module.train(False)
    nonsmooth = _is_nonsmooth(module)
    x = torch.linspace(lo, hi, n, dtype=torch.float32, requires_grad=True)
    try:
        y = module(x)
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "reason": f"forward_failed:{exc}", "nonsmooth": nonsmooth}
    if not torch.isfinite(y).all():
        return {"passed": False, "reason": "non_finite_forward", "max_abs_y": float("nan"), "nonsmooth": nonsmooth}

    y_sum = y.sum()
    try:
        y_sum.backward()
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "reason": f"backward_failed:{exc}", "nonsmooth": nonsmooth}
    if x.grad is None or not torch.isfinite(x.grad).all():
        return {"passed": False, "reason": "non_finite_grad", "nonsmooth": nonsmooth}

    analytic = x.grad.detach()
    with torch.no_grad():
        x_np = x.detach()
        yp = module(x_np + gradcheck_eps)
        ym = module(x_np - gradcheck_eps)
        if not torch.isfinite(yp).all() or not torch.isfinite(ym).all():
            return {
                "passed": False,
                "reason": "non_finite_finite_diff",
                "nonsmooth": nonsmooth,
            }
        numeric = (yp - ym) / (2 * gradcheck_eps)
        abs_err = (analytic - numeric).abs()
        # Away from origin (ReLU kink); mixed abs/rel so saturated tanh/GELU is not a false reject.
        mask = x_np.abs() > 1e-2
        mixed_ok = bool((abs_err <= (1e-2 + 0.05 * numeric.abs()))[mask].all()) if bool(mask.any()) else bool((abs_err <= 1e-2).all())
        rel = abs_err / (numeric.abs() + 1e-3)
        max_rel = float(rel[mask].max().item()) if bool(mask.any()) else float(rel.max().item())

    module_d = module.double() if hasattr(module, "double") else module
    xd = torch.randn(7, dtype=torch.float64, requires_grad=True)

    def _fn(inp: torch.Tensor) -> torch.Tensor:
        return module_d(inp)

    gradcheck_ok = False
    gradcheck_error: str | None = None
    try:
        gradcheck_ok = bool(torch.autograd.gradcheck(_fn, (xd,), eps=1e-6, atol=1e-4, raise_exception=False))
    except Exception as exc:  # noqa: BLE001
        gradcheck_ok = False
        gradcheck_error = str(exc)

    if nonsmooth:
        passed = mixed_ok
        reason = "ok_nonsmooth" if passed else "grad_mismatch"
    else:
        passed = mixed_ok and gradcheck_ok
        if not mixed_ok:
            reason = "grad_mismatch"
        elif not gradcheck_ok:
            reason = "gradcheck_failed" if gradcheck_error is None else f"gradcheck_failed:{gradcheck_error}"
        else:
            reason = "ok"

    return {
        "passed": passed,
        "reason": reason,
        "nonsmooth": nonsmooth,
        "max_abs_y": float(y.detach().abs().max().item()),
        "max_abs_grad": float(analytic.abs().max().item()),
        "max_rel_finite_diff": max_rel,
        "gradcheck_ok": gradcheck_ok,
        "gradcheck_error": gradcheck_error,
    }
