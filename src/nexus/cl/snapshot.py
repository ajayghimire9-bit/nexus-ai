"""Policy + RMS snapshots for retention that does not confuse new heads with forgetting."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import torch

from nexus.rl.ppo import PPOTrainer
from nexus.rl.running_stats import RunningMeanStd
from nexus.tasks.spec import TaskSpec


def capture_snapshot(trainer: PPOTrainer) -> dict[str, Any]:
    rms = None if trainer.obs_rms is None else trainer.obs_rms.state_dict()
    return {
        "state_dict": {k: v.detach().cpu().clone() for k, v in trainer.agent.state_dict().items()},
        "obs_rms": None if rms is None else {k: deepcopy(v) for k, v in rms.items()},
        "head_keys": [k for k in trainer.agent.state_dict() if "policy_head" in k or "value_head" in k],
        "encoder_keys": [k for k in trainer.agent.state_dict() if k.startswith("backbone.")],
    }


def _load_rms(trainer: PPOTrainer, snap: dict[str, Any]) -> RunningMeanStd | None:
    if snap.get("obs_rms") is None:
        return None
    if trainer.obs_rms is None:
        return None
    rms = RunningMeanStd(tuple(trainer.obs_rms.mean.shape))
    rms.load_state_dict(snap["obs_rms"])
    return rms


def eval_snapshot(
    trainer: PPOTrainer,
    spec: TaskSpec,
    snap: dict[str, Any],
    *,
    episodes: int,
    seed: int,
    eval_fn,
    use_snapshot_rms: bool = True,
    restore_heads_from: dict[str, Any] | None = None,
) -> float:
    """Evaluate ``snap`` weights (optionally mixing source heads) then restore trainer."""
    live = {k: v.detach().cpu().clone() for k, v in trainer.agent.state_dict().items()}
    live_rms = None if trainer.obs_rms is None else trainer.obs_rms.state_dict()
    merged = dict(snap["state_dict"])
    if restore_heads_from is not None:
        for k in restore_heads_from.get("head_keys", []):
            if k in restore_heads_from["state_dict"]:
                merged[k] = restore_heads_from["state_dict"][k]
    trainer.agent.load_state_dict(merged, strict=False)
    rms = _load_rms(trainer, snap) if use_snapshot_rms else trainer.obs_rms
    score = float(
        eval_fn(
            trainer.agent,
            spec,
            episodes=episodes,
            seed=seed,
            device=trainer.device,
            obs_rms=rms if use_snapshot_rms else trainer.obs_rms,
        )["mean_return"]
    )
    trainer.agent.load_state_dict(live)
    if live_rms is not None and trainer.obs_rms is not None:
        trainer.obs_rms.load_state_dict(live_rms)
    return score


def retention_bundle(
    *,
    trainer: PPOTrainer,
    source_spec: TaskSpec,
    source_snap: dict[str, Any],
    adapted_is_new_heads: bool,
    episodes: int,
    seed: int,
    eval_fn,
) -> dict[str, Any]:
    """A–E retention diagnostics. Encoder-only transfer leaves D undefined as forgetting."""
    a = eval_snapshot(trainer, source_spec, source_snap, episodes=episodes, seed=seed, eval_fn=eval_fn)
    b = float(
        eval_fn(
            trainer.agent,
            source_spec,
            episodes=episodes,
            seed=seed,
            device=trainer.device,
            obs_rms=trainer.obs_rms,
        )["mean_return"]
    )
    c = a  # preserved independent snapshot equals A
    e = eval_snapshot(
        trainer,
        source_spec,
        {"state_dict": {k: v.detach().cpu().clone() for k, v in trainer.agent.state_dict().items()}, "obs_rms": source_snap.get("obs_rms")},
        episodes=episodes,
        seed=seed,
        eval_fn=eval_fn,
        use_snapshot_rms=True,
    )
    if adapted_is_new_heads:
        d = eval_snapshot(
            trainer,
            source_spec,
            {"state_dict": {k: v.detach().cpu().clone() for k, v in trainer.agent.state_dict().items()}, "obs_rms": source_snap.get("obs_rms"), "head_keys": source_snap["head_keys"]},
            restore_heads_from=source_snap,
            episodes=episodes,
            seed=seed,
            eval_fn=eval_fn,
        )
        forgetting = None
        note = "new heads: B is not catastrophic forgetting of the source policy"
    else:
        d = None
        forgetting = a - b
        note = "same heads: B vs A is source-policy retention"
    return {
        "A_source_before": a,
        "B_adapted_on_source": b,
        "C_preserved_snapshot": c,
        "D_encoder_with_source_heads": d,
        "E_adapted_weights_source_rms": e,
        "forgetting_same_policy": forgetting,
        "retention_defined": not adapted_is_new_heads,
        "note": note,
    }
