from __future__ import annotations

import random
from typing import Any

import numpy as np


def select_representative_checkpoint(seed_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick an independently evaluated seed closest to the multi-seed mean.

    Ranking uses the mean; the promoted file is a real validated checkpoint, not
    whatever seed happened to be trained last.
    """
    valid = [r for r in seed_rows if r.get("path") and r.get("mean_return") is not None]
    if not valid:
        return None
    mean = float(np.mean([float(r["mean_return"]) for r in valid]))
    return min(valid, key=lambda r: (abs(float(r["mean_return"]) - mean), int(r["seed"])))


def serialize_rng(rng: random.Random) -> dict[str, Any]:
    ver, seq, gauss = rng.getstate()
    return {"version": int(ver), "state": list(seq), "gauss": gauss}


def restore_rng(rng: random.Random, payload: dict[str, Any]) -> None:
    rng.setstate((int(payload["version"]), tuple(payload["state"]), payload.get("gauss")))
