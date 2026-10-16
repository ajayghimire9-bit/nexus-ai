"""Opt-in batched twin of the Pendulum successor lookahead for new runners.

Historical experiment runners and the recorded parity provenance stay
untouched; this adapter exists so future Pendulum-family experiments inherit
the 51-to-17-call acceleration with the committed parity evidence attached.
Evidence: synthetic 160/160, archived observations with genuine saved student
contexts 2160/2160 (bitwise independent reproduction), and full paired fresh
episodes 60/60 with reward/return deviation 0.0. Reports:
docs/NEXUS_SUCCESSOR_SEARCH_EFFICIENCY_RESULTS.md,
docs/NEXUS_SUCCESSOR_ARCHIVED_PARITY_RESULTS.md,
docs/NEXUS_SUCCESSOR_ARCHIVED_PARITY_CLINE_RESCORE_RESULTS.md,
docs/NEXUS_SUCCESSOR_EPISODE_PARITY_CLINE_RESULTS.md.
"""
from __future__ import annotations

import numpy as np

from nexus.world.successor_search import PreparedSuccessorSearch


def prepare(sequences) -> PreparedSuccessorSearch:
    """Build the immutable reusable candidate table (once per candidate set)."""
    return PreparedSuccessorSearch(np.asarray(sequences), family="pendulum")


def lookahead_first_action(model, obs, sequences):
    """Drop-in batched twin of bellman_backup_control.lookahead_first_action.

    Same signature and (action, q, preds[action]) triple, the same 771
    imagined transitions, with 17 model calls instead of 51. Numerical parity
    with the serial twin is established on synthetic inputs, archived
    observations with saved student contexts, and full paired fresh episodes
    (2e-4 absolute / 2e-5 relative tolerance; identical actions on every
    tested grid, reward/return deviation 0.0 on the episode grid). Pendulum's
    historical outer-termination semantics are preserved inside
    PreparedSuccessorSearch. ``sequences`` may be a raw (16, 16) candidate
    array or a table already built with :func:`prepare` for reuse across
    contexts; passing anything else fails closed.
    """
    prepared = sequences if isinstance(sequences, PreparedSuccessorSearch) else prepare(sequences)
    result = prepared.score(model, obs)
    return result.action, [float(v) for v in result.q], np.asarray(result.successors[result.action])
