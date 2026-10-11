"""Bounded predictive memory. Retrieval uses prediction quality, not task IDs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

from nexus.world.data import TransitionDataset, concat_datasets
from nexus.world.dynamics import WorldModel


def checkpoint_nbytes(wm: WorldModel) -> int:
    n = 0
    for t in wm.net.state_dict().values():
        n += int(t.nelement() * t.element_size())
    n += int(np.asarray(wm.obs_rms.mean).nbytes + np.asarray(wm.obs_rms.var).nbytes)
    return n


def snapshot_payload(wm: WorldModel) -> dict[str, Any]:
    return {
        "state_dict": {k: v.detach().cpu().clone() for k, v in wm.net.state_dict().items()},
        "obs_rms": {k: v.clone() if torch.is_tensor(v) else v for k, v in wm.obs_rms.state_dict().items()},
        "kind": wm.kind,
        "obs_dim": wm.net.obs_dim,
        "n_actions": wm.net.n_actions,
        "nbytes": checkpoint_nbytes(wm),
    }


def restore_world_model(payload: dict[str, Any]) -> WorldModel:
    wm = WorldModel.create(
        int(payload["obs_dim"]),
        int(payload["n_actions"]),
        kind=payload["kind"],
        hidden=(64, 64),
        seed=0,
    )
    wm.net.load_state_dict(payload["state_dict"])
    wm.obs_rms.load_state_dict(payload["obs_rms"])
    wm.net.eval()
    return wm


def probe_mae(model: WorldModel, probe: TransitionDataset) -> float:
    if len(probe) == 0:
        return float("inf")
    pred, _ = model.step(probe.obs, probe.action)
    return float(np.mean(np.abs(pred - probe.next_obs)))


@dataclass
class MemoryEntry:
    snapshot: dict[str, Any]
    probe: TransitionDataset
    stats: dict[str, Any] = field(default_factory=dict)
    replay: TransitionDataset | None = None
    label: str = ""  # diagnostic only; never used for retrieval


@dataclass
class PredictiveMemory:
    """Ring of snapshots + replay. Retrieval scores models on a live probe set."""

    max_entries: int = 8
    replay_cap: int = 2048
    entries: list[MemoryEntry] = field(default_factory=list)
    replay: TransitionDataset | None = None
    retrieval_inferences: int = 0
    store_count: int = 0

    def store(
        self,
        wm: WorldModel,
        probe: TransitionDataset,
        *,
        stats: dict[str, Any] | None = None,
        replay: TransitionDataset | None = None,
        label: str = "",
    ) -> None:
        entry = MemoryEntry(
            snapshot=snapshot_payload(wm),
            probe=probe,
            stats=dict(stats or {}),
            replay=replay,
            label=label,
        )
        self.entries.append(entry)
        self.store_count += 1
        if len(self.entries) > int(self.max_entries):
            self.entries = self.entries[-int(self.max_entries) :]
        if replay is not None and len(replay):
            self.replay = replay if self.replay is None else concat_datasets(self.replay, replay)
            if self.replay is not None and len(self.replay) > int(self.replay_cap):
                keep = np.arange(len(self.replay))[-int(self.replay_cap) :]
                self.replay = self.replay.slice(keep)

    def bytes_used(self) -> int:
        n = int(sum(int(e.snapshot["nbytes"]) for e in self.entries))
        if self.replay is not None:
            n += int(self.replay.obs.nbytes + self.replay.next_obs.nbytes + self.replay.action.nbytes)
        for e in self.entries:
            n += int(e.probe.obs.nbytes + e.probe.next_obs.nbytes + e.probe.action.nbytes)
        return n

    def retrieve(self, probe: TransitionDataset) -> tuple[WorldModel | None, dict[str, Any]]:
        """Pick the stored model with lowest one-step MAE on ``probe``. No task_id."""
        if not self.entries or len(probe) == 0:
            return None, {"n_candidates": 0, "mae": None, "retrieval_inferences": 0, "used_task_id": False}
        maes: list[float] = []
        inf = 0
        for e in self.entries:
            wm = restore_world_model(e.snapshot)
            maes.append(probe_mae(wm, probe))
            inf += len(probe)
        self.retrieval_inferences += inf
        best_i = int(np.argmin(np.asarray(maes, dtype=np.float64)))
        best = restore_world_model(self.entries[best_i].snapshot)
        return best, {
            "n_candidates": len(self.entries),
            "mae": float(maes[best_i]),
            "all_mae": [float(x) for x in maes],
            "index": best_i,
            "retrieval_inferences": inf,
            "used_task_id": False,
            "used_privileged_physics": False,
        }
