"""Unfamiliar policy-only replication tests. No language-model inference."""
from __future__ import annotations

import random
from pathlib import Path
import tempfile

from nexus.seed.mechanism_investigate import DIAGNOSTIC_ORDER
from nexus.seed.mechanism_policy_replication import (
    FAMILY_X, FAMILY_Y, FIRST_PROBE, OPENED_IDS, branch_property, distill_order,
    filter_bank, reconstruct_work, run_episode, run_replication,
    verify_payload, zero_acquire,
)
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks
from nexus.seed.mechanism_world import LANGUAGE


def test_fresh_ids_are_disjoint_from_opened_and_source():
    source = unfamiliar_policy_tasks("up_source")
    holdout = unfamiliar_policy_tasks("up_holdout")
    retain = unfamiliar_policy_tasks("up_retain")
    ids = {row["task_id"] for row in source + holdout + retain}
    mechanisms = {row["mechanism"] for row in holdout}
    assert ids.isdisjoint(OPENED_IDS)
    assert mechanisms.isdisjoint({row["mechanism"] for row in source})
    assert mechanisms.isdisjoint(LANGUAGE)


def test_branch_a_and_b_are_exclusive_or_after_first_probe():
    report = branch_property()
    assert report["first_probe"] == FIRST_PROBE
    assert report["family_x"] == FAMILY_X
    assert report["family_y"] == FAMILY_Y
    assert report["holds"] is True
    assert report["branch_a"]["family_x_informative"] is True
    assert report["branch_a"]["family_y_redundant"] is True
    assert report["branch_a"]["family_y_splits"] == 1
    assert report["branch_b"]["family_y_informative"] is True
    assert report["branch_b"]["family_x_redundant"] is True
    assert report["branch_b"]["family_x_splits"] == 1
    remain_a = filter_bank([dict(action=FIRST_PROBE, observation=report["branch_a"]["y1"])])
    remain_b = filter_bank([dict(action=FIRST_PROBE, observation=report["branch_b"]["y1"])])
    assert set(remain_a) == {"up_pos_plus2", "up_twice_plus1"}
    assert set(remain_b) == {"up_neg_gate", "up_neg_twice"}


def test_static_order_cannot_condition_on_y1():
    hold_a = next(row for row in unfamiliar_policy_tasks("up_holdout") if row["mechanism"] == "up_pos_plus2")
    hold_b = next(row for row in unfamiliar_policy_tasks("up_holdout") if row["mechanism"] == "up_neg_gate")
    order = list(DIAGNOSTIC_ORDER)
    a = run_episode(hold_a, "source_distilled_fixed_order", zero_acquire(), order, random.Random(1))
    b = run_episode(hold_b, "source_distilled_fixed_order", zero_acquire(), order, random.Random(1))
    probes_a = [row["action"] for row in a["transcript"] if not str(row["action"]).startswith("STOP")]
    probes_b = [row["action"] for row in b["transcript"] if not str(row["action"]).startswith("STOP")]
    assert probes_a[0] == probes_b[0] == FIRST_PROBE
    assert probes_a[1] == probes_b[1]
    assert probes_a[1] != FAMILY_Y or probes_b[1] != FAMILY_X


def test_work_reconstruction_matches_runner():
    task = unfamiliar_policy_tasks("up_holdout")[0]
    episode = run_episode(
        task, "untrained_default_policy", zero_acquire(), list(DIAGNOSTIC_ORDER), random.Random(4),
    )
    assert reconstruct_work(episode)["env_interactions"] == episode["env_interactions"]
    assert reconstruct_work(episode)["hypothesis_evals"] == episode["hypothesis_evals"]
    assert reconstruct_work(episode)["total_acquisition_work"] == episode["total_acquisition_work"]
    assert episode["memory_cleared"] is True
    assert episode["retrieve"] is False


def test_distill_order_is_a_single_static_list():
    fake = [
        dict(transcript=[
            dict(action="ACT_1", observation=2),
            dict(action="ACT_2", observation=3),
        ]),
        dict(transcript=[
            dict(action="ACT_1", observation=0),
            dict(action="ACT_NEG", observation=-1),
        ]),
    ]
    order = distill_order(fake)
    assert set(order) >= {"ACT_1", "ACT_2", "ACT_NEG"}
    assert order.count("ACT_1") == 1


def test_replication_run_passes_verifier_and_keeps_tracks_closed():
    payload = run_replication(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert payload["usage"]["model_calls"] == 0
    assert payload["usage"]["frozen_debit_s"] == 0
    assert payload["usage"]["research_cpu_ledger_debit_s"] == 0
    assert payload["track_b_closed"] is True
    assert payload["skill_memory_paused"] is True
    assert payload["memory_cleared"] is True
    assert payload["learning_to_learn_established"] is False
    seen = {row["task_id"] for row in payload["assessment"]}
    assert seen.isdisjoint(OPENED_IDS)
    assert payload["gates"]["passed"] is True
    methods = {row["method"] for row in payload["assessment"]}
    assert methods == {
        "untrained_default_policy",
        "source_distilled_fixed_order",
        "source_learned_adaptive_policy",
    }
