"""Pre-allocation bounds and untrained probes over the existing factory."""
from __future__ import annotations

import math
import torch
from torch import nn

from nexus.nn.expr import EXPR_TREES, validate_tree
from nexus.nn.factory import build_from_spec


def architecture_cost(in_dim, spec, *, parameter_cap=100_000, mac_cap=100_000):
    """Trunk-only exact parameter count; dense MACs exclude nonlinear work.

    Not FLOPs or a full PPO/world-model bound. Expression node count is a
    separate conservative operation proxy. Heads/optimizer need own bounds.
    """
    if type(in_dim) is not int or not 1 <= in_dim <= 4096:
        raise ValueError("input_dimension_cap")
    if any(type(v) is not int or v < 1 for v in (parameter_cap, mac_cap)):
        raise ValueError("typed_positive_complexity_caps")
    if not 1 <= len(spec.hidden_sizes) <= 4 or any(type(w) is not int or not 1 <= w <= 256 for w in spec.hidden_sizes):
        raise ValueError("architecture_width_depth_cap")
    if not math.isfinite(spec.dropout) or type(spec.dropout) is bool:
        raise ValueError("finite_dropout")
    for flag in (spec.use_residual, spec.layer_norm, spec.shared_backbone):
        if type(flag) is not bool:
            raise ValueError("typed_architecture_flags")
    expr_nodes = validate_tree(EXPR_TREES[spec.activation]) if spec.activation.startswith("expr_") else 1
    params = macs = nonlinear = 0
    last = in_dim
    for width in spec.hidden_sizes:
        macs += last * width
        params += last * width + width + (2 * width if spec.layer_norm else 0)
        params += 2 if spec.activation.startswith("expr_") else 0
        nonlinear += width * expr_nodes
        last = width
    if params > parameter_cap or macs > mac_cap:
        raise ValueError("preallocation_complexity_cap")
    return dict(parameters=params, dense_macs_per_row=macs, activation_node_elements_per_row=nonlinear)


def probe_architecture(in_dim, spec, *, seed=0, **limits):
    cost = architecture_cost(in_dim, spec, **limits)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        net, width = build_from_spec(in_dim, spec)
        # Train-mode probe includes configured dropout; fork keeps caller RNG.
        x = torch.linspace(-8, 8, 7 * in_dim).reshape(7, in_dim).requires_grad_()
        out = net(x)
        out.square().mean().backward()
        tensors = [out, x.grad] + [p.grad for p in net.parameters()]
        if out.shape != (7, width) or any(t is None or not torch.isfinite(t).all() for t in tensors):
            raise ValueError("shape_or_finite_gradient_failure")
        actual = sum(p.numel() for p in net.parameters())
        if actual != cost["parameters"]:
            raise ValueError("parameter_bound_disagrees_with_factory")
        return dict(**cost, output_shape=list(out.shape), input_gradient_norm=float(x.grad.norm()),
                    parameter_gradient_norm=sum(float(p.grad.norm()) for p in net.parameters()),
                    trained=False)
