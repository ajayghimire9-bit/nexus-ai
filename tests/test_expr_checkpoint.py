from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.nn.expr import dump_expr, random_expr, register_expr
from nexus.rl.ppo import PPOTrainer


def test_expr_checkpoint_loads_in_fresh_process(tmp_path: Path) -> None:
    import random

    node = random_expr(random.Random(0), depth=2)
    name = register_expr(node)
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=1,
        num_steps=8,
        update_epochs=1,
        num_minibatches=1,
        seed=0,
        device="cpu",
        log_interval=10_000,
    )
    arch = ArchitectureConfig(hidden_sizes=(8,), activation=name)
    ckpt = tmp_path / "expr.pt"
    trainer = PPOTrainer(ppo, arch)
    try:
        trainer.train(8)
        trainer.save(ckpt)
        payload_name = dump_expr(name)
        assert payload_name is not None
    finally:
        trainer.close()

    child = r"""
import sys
from pathlib import Path
import torch
from nexus.rl.ppo import PPOTrainer

path = Path(sys.argv[1])
loaded = torch.load(path, map_location="cpu", weights_only=False)
assert loaded.get("expr_tree"), "missing expr_tree"
trainer = PPOTrainer.from_checkpoint(path)
assert trainer.architecture.activation.startswith("expr_")
x = trainer._obs_tensor_no_update(trainer._raw_obs)
y = trainer.agent.value(x)
assert y.isfinite().all()
trainer.close()
print("ok")
"""
    proc = subprocess.run(
        [sys.executable, "-c", child, str(ckpt)],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={**dict(**__import__("os").environ), "PYTHONPATH": "src:.deps"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout
