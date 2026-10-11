from __future__ import annotations

import random
from typing import Any

from nexus.evolution.mutate import mutate_spec, random_spec
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec


def propose_next_experiment(
    db_path: str,
    *,
    epsilon: float = 0.2,
    seed: int = 0,
    env_id: str | None = None,
) -> dict[str, Any]:
    """Epsilon-greedy proposal from stored *evaluated* runs.

    This is a Level-2 stub (contextual bandit / ε-greedy), not a trained
    meta-RL controller. It cannot change evaluation rules or risk limits.
    """
    rng = random.Random(seed)
    store = ExperimentStore(db_path)
    try:
        rows = store.all()
        if env_id:
            rows = [r for r in rows if r.env_id == env_id]
    finally:
        store.close()

    mode = "explore"
    parent: dict[str, Any] | None = None
    if rows and rng.random() >= epsilon:
        best = max(rows, key=lambda r: r.mean_return)
        parent = best.architecture
        spec = mutate_spec(ArchitectureSpec.from_dict(best.architecture), rng)
        mode = "exploit_mutate"
    else:
        spec = random_spec(rng)

    return {
        "mode": mode,
        "epsilon": epsilon,
        "n_prior": len(rows),
        "parent": parent,
        "proposal": spec.to_dict(),
        "note": (
            "Proposal only. Train and independently evaluate before treating "
            "this as an improvement. Not a claim of meta-learning."
        ),
    }
