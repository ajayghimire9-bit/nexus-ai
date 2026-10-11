"""Termination classification vs an always-nonterminal baseline."""

from __future__ import annotations

from typing import Any

import numpy as np


def termination_report(p_term: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    p = np.asarray(p_term, dtype=np.float64).reshape(-1)
    yt = np.asarray(y, dtype=np.float64).reshape(-1)
    yb = yt >= 0.5
    pred = p >= 0.5
    tp = int(np.sum(pred & yb))
    fp = int(np.sum(pred & ~yb))
    fn = int(np.sum(~pred & yb))
    tn = int(np.sum(~pred & ~yb))
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    prev = float(yb.mean()) if yb.size else 0.0
    brier = float(np.mean((p - yt) ** 2)) if p.size else None
    always0_brier = float(np.mean((np.zeros_like(yt) - yt) ** 2)) if yt.size else None
    return {
        "n": int(p.size),
        "prevalence": prev,
        "precision": float(prec),
        "recall": float(rec),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "brier": brier,
        "always_nonterminal_brier": always0_brier,
        "brier_minus_always_nonterminal": None if brier is None or always0_brier is None else float(brier - always0_brier),
    }
