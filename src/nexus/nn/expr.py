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
MAX_NODES = 12


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


def node_count(node: Expr) -> int:
    op = node[0]
    if op == "x":
        return 1
    if op == "unary":
        return 1 + node_count(node[2])  # type: ignore[arg-type]
    if op == "binary":
        return 1 + node_count(node[2]) + node_count(node[3])  # type: ignore[arg-type]
    return 1


def _canonicalize(node: Expr) -> Expr:
    op = node[0]
    if op == "x":
        return ("x",)
    if op == "unary":
        return ("unary", node[1], _canonicalize(node[2]))  # type: ignore[arg-type]
    if op == "binary":
        left, right = _canonicalize(node[2]), _canonicalize(node[3])  # type: ignore[arg-type]
        if node[1] in {"add", "mul"} and json.dumps(left, default=str) > json.dumps(right, default=str):
            left, right = right, left
        return ("binary", node[1], left, right)
    return node


def canonical_key(node: Expr) -> str:
    blob = json.dumps(_canonicalize(node), separators=(",", ":"), default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def random_expr(rng: random.Random, depth: int = 2) -> Expr:
    if depth <= 0 or rng.random() < 0.35:
        return ("x",)
    if rng.random() < 0.55:
        child = random_expr(rng, depth - 1)
        node: Expr = ("unary", rng.choice(UNARY), child)
    else:
        node = (
            "binary",
            rng.choice(BINARY),
            random_expr(rng, depth - 1),
            random_expr(rng, depth - 1),
        )
    if node_count(node) > MAX_NODES:
        return ("x",)
    return node


def mutate_expr(node: Expr, rng: random.Random) -> Expr:
    if rng.random() < 0.4:
        return random_expr(rng, depth=2)
    op = node[0]
    if op == "unary":
        out: Expr = ("unary", rng.choice(UNARY), mutate_expr(node[2], rng))  # type: ignore[arg-type]
    elif op == "binary":
        if rng.random() < 0.5:
            out = ("binary", rng.choice(BINARY), mutate_expr(node[2], rng), node[3])  # type: ignore[arg-type]
        else:
            out = ("binary", node[1], node[2], mutate_expr(node[3], rng))  # type: ignore[arg-type]
    else:
        out = random_expr(rng, depth=1)
    if node_count(out) > MAX_NODES:
        return node
    return out


def crossover_expr(a: Expr, b: Expr, rng: random.Random) -> Expr:
    if a[0] == "binary" and rng.random() < 0.5:
        child: Expr = ("binary", a[1], a[2], b)  # type: ignore[misc]
    elif b[0] == "binary":
        child = ("binary", b[1], a, b[3] if len(b) > 3 else a)  # type: ignore[misc]
    elif a[0] == "unary":
        child = ("unary", a[1], b)
    else:
        child = mutate_expr(a, rng)
    if node_count(child) > MAX_NODES:
        return a
    return child


def expr_key(node: Expr) -> str:
    return f"expr_{canonical_key(node)}"


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
    """Restricted tree plus learnable affine coefficients (scale, shift)."""

    def __init__(self, node: Expr) -> None:
        super().__init__()
        self.node = node
        self.scale = nn.Parameter(torch.ones(()))
        self.shift = nn.Parameter(torch.zeros(()))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.scale * eval_expr(self.node, x) + self.shift


EXPR_TREES: dict[str, Expr] = {}


def expr_to_jsonable(node: Expr) -> Any:
    if isinstance(node, tuple):
        return [expr_to_jsonable(x) for x in node]
    return node


def expr_from_jsonable(obj: Any) -> Expr:
    if isinstance(obj, list):
        return tuple(expr_from_jsonable(x) for x in obj)  # type: ignore[return-value]
    return obj  # type: ignore[return-value]


def register_expr(node: Expr) -> str:
    node = _canonicalize(node)
    name = expr_key(node)
    EXPR_TREES[name] = node

    class _Registered(ExprActivation):
        def __init__(self) -> None:
            super().__init__(EXPR_TREES[name])

    ACTIVATIONS[name] = _Registered
    return name


def restore_expr(tree: Any, name: str | None = None) -> str:
    """Re-register a saved expression tree in a fresh process."""
    node = expr_from_jsonable(tree)
    restored = register_expr(node)
    if name is not None and name != restored:
        ACTIVATIONS[name] = ACTIVATIONS[restored]
        EXPR_TREES[name] = EXPR_TREES[restored]
        return name
    return restored


def dump_expr(name: str) -> dict[str, Any] | None:
    if name not in EXPR_TREES:
        return None
    return {"name": name, "tree": expr_to_jsonable(EXPR_TREES[name])}


def maybe_restore_named(name: str, payload: dict[str, Any] | None = None) -> None:
    if name in ACTIVATIONS:
        return
    if payload and payload.get("tree") is not None:
        restore_expr(payload["tree"], name=payload.get("name") or name)
        return
    if name.startswith("expr_"):
        raise ValueError(
            f"activation '{name}' is a dynamic expression that is not registered. "
            "Load the checkpoint expr_tree before constructing the network."
        )


def population_exprs(rng: random.Random, n: int, depth: int = 2) -> list[Expr]:
    seen: set[str] = set()
    out: list[Expr] = []
    guard = 0
    while len(out) < n and guard < n * 20:
        guard += 1
        node = random_expr(rng, depth=depth)
        key = canonical_key(node)
        if key in seen or node_count(node) > MAX_NODES:
            continue
        seen.add(key)
        out.append(node)
    return out
