from __future__ import annotations

from dataclasses import replace

from nexus.config import MetaConfig, NexusConfig


def bind_slots_to_timestep_budget(meta: MetaConfig) -> MetaConfig:
    """Make the step cap bind before the experiment-slot cap.

    V0.5.2 comparisons could finish with unequal env-step totals because
    cost-aware ranking preferred explore and exhausted slots first.
    Controllers still cannot rewrite the numeric caps; this only sets them
    so a paired study uses matched actual compute.
    """
    cheapest = int(meta.explore_timesteps or 0) or int(meta.train_timesteps)
    unit = max(cheapest, 1)
    need = int(meta.max_timesteps) // unit + 2
    if meta.max_experiments >= need:
        return meta
    return replace(meta, max_experiments=need)


def apply_matched_compute(cfg: NexusConfig) -> NexusConfig:
    return replace(cfg, meta=bind_slots_to_timestep_budget(cfg.meta))
