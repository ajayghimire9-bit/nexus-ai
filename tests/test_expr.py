from __future__ import annotations

import random

import torch

from nexus.nn.expr import (
    canonical_key,
    crossover_expr,
    mutate_expr,
    node_count,
    population_exprs,
    register_expr,
)
from nexus.nn.validate import validate_activation
from nexus.nn.activations import get_activation


def test_population_dedup_and_complexity() -> None:
    rng = random.Random(0)
    pop = population_exprs(rng, 6)
    keys = [canonical_key(n) for n in pop]
    assert len(keys) == len(set(keys))
    assert all(node_count(n) <= 12 for n in pop)


def test_mutate_crossover_stay_bounded() -> None:
    rng = random.Random(1)
    pop = population_exprs(rng, 3)
    child = mutate_expr(pop[0], rng)
    mix = crossover_expr(pop[0], pop[-1], rng)
    assert node_count(child) <= 12
    assert node_count(mix) <= 12


def test_registered_expr_has_learnable_affine_and_validates() -> None:
    rng = random.Random(2)
    pop = population_exprs(rng, 4)
    name = register_expr(pop[0])
    module = get_activation(name)
    assert any(p.requires_grad for p in module.parameters())
    report = validate_activation(module)
    x = torch.linspace(-2, 2, 16)
    y = module(x)
    assert torch.isfinite(y).all()
    assert "passed" in report
