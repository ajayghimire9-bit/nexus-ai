from __future__ import annotations

import random

from nexus.nn.spec import ALLOWED_ACTIVATIONS, ArchitectureSpec

WIDTHS = (16, 32, 48, 64, 96, 128, 256)
MAX_LAYERS = 4


def random_spec(rng: random.Random) -> ArchitectureSpec:
    n_layers = rng.randint(1, 3)
    sizes = tuple(rng.choice(WIDTHS) for _ in range(n_layers))
    return ArchitectureSpec(
        hidden_sizes=sizes,
        activation=rng.choice(tuple(ALLOWED_ACTIVATIONS - {"identity"})),
        use_residual=rng.choice([False, True]),
        dropout=0.0,
        layer_norm=rng.choice([False, True]),
        shared_backbone=rng.choice([True, False]),
        init="orthogonal",
    )


def mutate_spec(spec: ArchitectureSpec, rng: random.Random) -> ArchitectureSpec:
    """Single-parent mutation. Invalid results fall back to the parent."""
    kind = rng.choice(["width", "add", "drop", "activation", "residual", "layernorm", "share"])
    sizes = list(spec.hidden_sizes)
    activation = spec.activation
    use_residual = spec.use_residual
    layer_norm = spec.layer_norm
    shared = spec.shared_backbone

    if kind == "width" and sizes:
        i = rng.randrange(len(sizes))
        sizes[i] = rng.choice(WIDTHS)
    elif kind == "add" and len(sizes) < MAX_LAYERS:
        sizes.append(rng.choice(WIDTHS))
    elif kind == "drop" and len(sizes) > 1:
        sizes.pop(rng.randrange(len(sizes)))
    elif kind == "activation":
        activation = rng.choice(tuple(ALLOWED_ACTIVATIONS - {"identity"}))
    elif kind == "residual":
        use_residual = not use_residual
    elif kind == "layernorm":
        layer_norm = not layer_norm
    elif kind == "share":
        shared = not shared

    try:
        return ArchitectureSpec(
            hidden_sizes=tuple(sizes),
            activation=activation,
            use_residual=use_residual,
            dropout=spec.dropout,
            layer_norm=layer_norm,
            shared_backbone=shared,
            init=spec.init,
        )
    except ValueError:
        return spec
