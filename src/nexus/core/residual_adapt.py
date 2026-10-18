"""Task-conditioned residual selection. Does not replace WorldModel.

Arms are E2.9 disposable residuals. Descriptors come from permitted
support transitions only. Checkpoints are read-only; local adapts use
clones and are not written back.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nexus.core.strategy_memory import KERNEL_LENGTH, RIDGE, SupportBatch, describe_support, support_from_arrays
from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.fixtures import PublicFixtureContext

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "artifacts" / "evolution2_source_arrays"
ARMS = (0, 1, 2)
ADAPT_STEPS = 8


def refuse_science_path(path: Path) -> None:
    text = str(path)
    if "persist_reset_science" in text:
        raise RuntimeError("e217_science_artifacts_forbidden")


def prediction_mae(model, obs, action, next_obs) -> float:
    pred, _ = model.step(obs, action)
    return float(np.mean(np.abs(np.asarray(pred, dtype=np.float64) - np.asarray(next_obs, dtype=np.float64))))


def adapt_clone(model, obs, action, next_obs, *, steps: int = ADAPT_STEPS, lr: float = 1e-3, seed: int = 0):
    """Few-step residual update on a clone. Does not save or touch the source file."""
    other = model.clone()
    other.net.train()
    opt = torch.optim.Adam(other.net.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    rng = np.random.default_rng(int(seed))
    n = int(obs.shape[0])
    for step in range(int(steps)):
        idx = rng.permutation(n)
        o = torch.as_tensor(other.normalize(obs[idx]), dtype=torch.float32)
        nxt = torch.as_tensor(other.normalize(next_obs[idx]), dtype=torch.float32)
        act = torch.as_tensor(np.asarray(action[idx]).reshape(-1), dtype=torch.int64)
        pred, _logit = other.net(o, act)
        target = nxt - o if other.kind == "residual" else nxt
        loss = loss_fn(pred, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(other.net.parameters(), 1.0)
        opt.step()
    other.net.eval()
    return other


@dataclass
class ResidualMemory:
    """Kernel memory over residual identities. Not the 12-arm catalogue."""

    seed: int = 7
    family_filter: bool = True
    _store: list[dict] = field(default_factory=list)
    _last: dict[str, int] = field(default_factory=dict)
    _known: dict[str, dict[int, float]] = field(default_factory=dict)

    def unused(self, family: str) -> list[int]:
        used = {int(row["arm"]) for row in self._store if row["family"] == family}
        return [arm for arm in ARMS if arm not in used]

    def choose(self, family: str, descriptor: np.ndarray, *, policy: str, explore: bool = True) -> int:
        if policy == "default":
            return 0
        if policy == "random":
            return int(np.random.default_rng(self.seed + 17 * len(self._store)).integers(0, 3))
        unused = self.unused(family) if explore else []
        if policy == "persist":
            if unused:
                return unused[0]
            return self._last.get(family, 0)
        if policy == "persist_best":
            if unused:
                return unused[0]
            known = self._known.get(family, {})
            if known:
                return min(known, key=known.get)
            return self._last.get(family, 0)
        if policy != "memory":
            raise ContractError("unknown_residual_policy")
        if unused:
            return unused[0]
        best_id, best = 0, -1.0
        found = False
        for arm in ARMS:
            shrunk, mass, min_dist = self._retrieve(family, descriptor, arm)
            if mass <= 0:
                continue
            found = True
            score = shrunk if min_dist <= KERNEL_LENGTH else 0.5
            if score > best:
                best, best_id = score, arm
        return best_id if found else self._last.get(family, 0)

    def update(self, family: str, descriptor: np.ndarray, arm: int, mae: float) -> None:
        score = float(max(0.0, 1.0 - mae))
        self._store.append(
            {
                "family": family,
                "descriptor": tuple(float(x) for x in descriptor),
                "arm": int(arm),
                "score": score,
                "mae": float(mae),
            }
        )
        self._last[family] = int(arm)
        self._known.setdefault(family, {})[int(arm)] = float(mae)

    def _retrieve(self, family: str, descriptor: np.ndarray, arm: int) -> tuple[float, float, float]:
        weights = []
        scores = []
        nearest = math.inf
        desc = np.asarray(descriptor, dtype=np.float64)
        for row in self._store:
            if row["arm"] != arm:
                continue
            if self.family_filter and row["family"] != family:
                continue
            dist = float(np.linalg.norm(desc - np.asarray(row["descriptor"], dtype=np.float64)))
            w = math.exp(-((dist / KERNEL_LENGTH) ** 2))
            weights.append(w)
            scores.append(row["score"])
            nearest = min(nearest, dist)
        if not weights:
            return 0.5, 0.0, math.inf
        w = np.asarray(weights, dtype=np.float64)
        s = np.asarray(scores, dtype=np.float64)
        raw = float(np.sum(w))
        shrunk = (float(np.sum(w * s)) + 0.5 * RIDGE) / (raw + RIDGE)
        return shrunk, raw, nearest


def load_support(family: str, bundle: int, start: int, n: int, context: PublicFixtureContext) -> tuple[SupportBatch, np.ndarray]:
    path = SOURCE / family / f"bundle{bundle}_train.npz"
    refuse_science_path(path)
    if not path.is_file():
        raise RuntimeError("permitted_source_array_missing")
    data = np.load(path)
    batch = support_from_arrays(data["obs"][start:], data["action"][start:], data["next_obs"][start:], n=n)
    return batch, describe_support(batch, context)
