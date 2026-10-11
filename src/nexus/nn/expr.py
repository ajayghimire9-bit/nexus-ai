from __future__ import annotations

import hashlib
import json
import random
from typing import Any

import torch
from torch import nn

from nexus.nn.activations import ACTIVATIONS

Expr = tuple[Any, ...]

UNARY = ("id", "tanh", "sigmoid", "softplus", "sin")
BINARY = ("add", "mul", "pdiv")


def _unary(name: str, x: torch.Tensor) -> torch.Tensor:
    if name == "id":
        return x
    if name == "tanh":
        return torch.tanh(x)
    if name == "sigmoid":
        return torch.sigmoid(x)
    if name == "softplus":
        return torch.nn.functional.softplus(x)
    if name == "sin":
        return torch.sin(x)
    raise ValueError(name)


def _binary(name: str, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    if name == "add":
        return a + b
    if name == "mul":
        return a * b
    if name == "pdiv":
        return a / (b.abs() + 1.0)
    raise ValueError(name)


def eval_expr(node: Expr, x: torch.Tensor) -> torch.Tensor:
    """Interpret a restricted expression tree with torch ops only (no exec)."""
    op = node[0]
    if op == "x":
        return x
    if op == "unary":
        return _unary(str(node[1]), eval_expr(node[2], x))  # type: ignore[arg-type]
    if op == "binary":
        return _binary(str(node[1]), eval_expr(node[2], x), eval_expr(node[3], x))  # type: ignore[arg-type]
    raise ValueError(f"unknown expr op {op}")


def random_expr(rng: random.Random, depth: int = 2) -> Expr:
    if depth <= 0 or rng.random() < 0.35:
        return ("x",)
    if rng.random() < 0.55:
        return ("unary", rng.choice(UNARY), random_expr(rng, depth - 1))
    return (
        "binary",
        rng.choice(BINARY),
        random_expr(rng, depth - 1),
        random_expr(rng, depth - 1),
    )


def mutate_expr(node: Expr, rng: random.Random) -> Expr:
    if rng.random() < 0.4:
        return random_expr(rng, depth=2)
    op = node[0]
    if op == "unary":
        return ("unary", rng.choice(UNARY), mutate_expr(node[2], rng))  # type: ignore[arg-type]
    if op == "binary":
        if rng.random() < 0.5:
            return ("binary", rng.choice(BINARY), mutate_expr(node[2], rng), node[3])  # type: ignore[arg-type]
        return ("binary", node[1], node[2], mutate_expr(node[3], rng))  # type: ignore[arg-type]
    return random_expr(rng, depth=1)


def expr_key(node: Expr) -> str:
    blob = json.dumps(node, separators=(",", ":"), default=str)
    digest = hashlib.sha1(blob.encode()).hexdigest()[:10]
    return f"expr_{digest}"


def expr_to_str(node: Expr) -> str:
    op = node[0]
    if op == "x":
        return "x"
    if op == "unary":
        return f"{node[1]}({expr_to_str(node[2])})"  # type: ignore[arg-type]
    if op == "binary":
        return f"({expr_to_str(node[2])} {node[1]} {expr_to_str(node[3])})"  # type: ignore[arg-type]
    return str(node)


class ExprActivation(nn.Module):
    def __init__(self, node: Expr) -> None:
        super().__init__()
        self.node = node

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return eval_expr(self.node, x)


def register_expr(node: Expr) -> str:
    name = expr_key(node)
    captured = node

    class _Registered(nn.Module):
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return eval_expr(captured, x)

    ACTIVATIONS[name] = _Registered
    return name
