from __future__ import annotations

import random
from collections import Counter
from typing import Any

from nexus.evolution.mutate import mutate_spec, random_spec
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec


def _comparable_rows(
    rows: list[Any],
    *,
    env_id: str | None,
    timesteps: int | None,
) -> tuple[list[Any], str]:
    """Keep only rows that share env and training budget. Never rank raw returns across tasks."""
    if env_id is not None:
        rows = [r for r in rows if r.env_id == env_id]
        if not rows:
            return [], "no_rows_for_env"
    else:
        env_counts = Counter(r.env_id for r in rows)
        if len(env_counts) > 1:
            return [], "refused_cross_env_ranking"
        if len(env_counts) == 1:
            env_id = next(iter(env_counts))

    if timesteps is not None:
        rows = [r for r in rows if int(r.timesteps) == int(timesteps)]
        if not rows:
            return [], "no_rows_for_budget"
    else:
        budgets = Counter(int(r.timesteps) for r in rows)
        if len(budgets) > 1:
            # Unequal budgets are not comparable; keep the modal matched budget only.
            modal, _ = budgets.most_common(1)[0]
            rows = [r for r in rows if int(r.timesteps) == modal]
            return rows, f"matched_modal_budget_{modal}"
    return rows, "ok"


def propose_next_experiment(
    db_path: str,
    *,
    epsilon: float = 0.2,
    seed: int = 0,
    env_id: str | None = None,
    timesteps: int | None = None,
) -> dict[str, Any]:
    """Epsilon-greedy proposal from stored *evaluated* runs.

    This is a Level-2 heuristic proposer (ε-greedy over comparable past runs).
    It is **not** learned meta-RL: there is no inner/outer loop, no credit
    assignment over experiment selection, and no trained bandit/RL policy.

    Raw mean_return is never compared across different env_id values or
    unequal training budgets.
    """
    rng = random.Random(seed)
    store = ExperimentStore(db_path)
    try:
        rows = store.all()
    finally:
        store.close()

    comparable, comparability = _comparable_rows(rows, env_id=env_id, timesteps=timesteps)

    note_base = (
        "Proposal only. Train and independently evaluate before treating this as an improvement. "
        "Not learned meta-RL; ε-greedy over comparable (same env, same timestep budget) records."
    )

    mode = "explore"
    parent: dict[str, Any] | None = None
    if comparable and rng.random() >= epsilon:
        best = max(comparable, key=lambda r: r.mean_return)
        parent = best.architecture
        spec = mutate_spec(ArchitectureSpec.from_dict(best.architecture), rng)
        mode = "exploit_mutate"
    else:
        spec = random_spec(rng)

    return {
        "mode": mode,
        "epsilon": epsilon,
        "n_prior": len(comparable),
        "n_stored": len(rows),
        "comparability": comparability,
        "parent": parent,
        "proposal": spec.to_dict(),
        "note": note_base,
        "is_meta_rl": False,
    }
