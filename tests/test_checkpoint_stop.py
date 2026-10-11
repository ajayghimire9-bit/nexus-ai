from __future__ import annotations

from pathlib import Path

import pytest
import torch

from nexus.cl.checkpoint_stop import save_adapt_checkpoint, stop_at_checkpoint
from nexus.cl.v064 import make_v064_trainer
from nexus.tasks.cartpole_family import source_policy_task
from nexus.cl.train import train_on_task


def test_stop_at_checkpoint_restores_weights_and_halts(tmp_path: Path) -> None:
    spec = source_policy_task()
    trainer = make_v064_trainer(seed=0, timesteps=256, spec=spec)
    ckpt = tmp_path / "pre.pt"
    save_adapt_checkpoint(trainer, ckpt)
    w0 = {k: v.detach().clone() for k, v in trainer.agent.state_dict().items()}
    train_on_task(trainer, spec, timesteps=256, seed=0)
    changed = any(not torch.equal(w0[k], v) for k, v in trainer.agent.state_dict().items())
    assert changed
    info = stop_at_checkpoint(trainer, ckpt)
    assert info["stopped_at_checkpoint"] is True
    assert info["exact_rollback_claimed"] is False
    for k, v in trainer.agent.state_dict().items():
        assert torch.allclose(w0[k], v)
    trainer.close()


def test_missing_checkpoint_refuses_to_continue(tmp_path: Path) -> None:
    spec = source_policy_task()
    trainer = make_v064_trainer(seed=1, timesteps=128, spec=spec)
    with pytest.raises(RuntimeError, match="refusing to continue"):
        stop_at_checkpoint(trainer, tmp_path / "missing.pt")
    trainer.close()
