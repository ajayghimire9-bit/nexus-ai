"""Stop adaptation at a saved checkpoint. Not a claim of bitwise-exact rollback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus.rl.ppo import PPOTrainer


def save_adapt_checkpoint(trainer: PPOTrainer, path: str | Path) -> Path:
    path = Path(path)
    trainer.save(path)
    return path


def stop_at_checkpoint(trainer: PPOTrainer, path: str | Path) -> dict[str, Any]:
    """Restore the last good checkpoint and halt. Do not continue training.

    Restores weights, optimizer, observation RMS, and PPO cursor when present.
    Vector-env / RNG restore fidelity is reported; if load fails, this raises
    rather than silently continuing an inconsistent trainer.
    """
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"checkpoint restore failed; refusing to continue: missing {path}")
    try:
        trainer.load_training_state(path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"checkpoint restore failed; refusing to continue: {exc}") from exc
    fidelity = str(getattr(trainer, "_resume_fidelity", "unknown"))
    return {
        "stopped_at_checkpoint": True,
        "checkpoint": str(path),
        "resume_fidelity": fidelity,
        "exact_rollback_claimed": False,
        "timesteps_done": int(getattr(trainer, "_timesteps_done", 0)),
    }
