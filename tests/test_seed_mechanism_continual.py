"""Continual Track A tests. No language-model inference. Do not rescore opened cells."""
from __future__ import annotations

import random
from pathlib import Path
import tempfile

from nexus.seed.mechanism_claims import score_claims
from nexus.seed.mechanism_continual import (
    OPENED_IDS, run_continual, run_episode, verify_payload, zero_acquire,
)
from nexus.seed.mechanism_policy import zero_weights
from nexus.seed.mechanism_skills import MechanismSkillStore
from nexus.seed.mechanism_tasks import wave_tasks
from nexus.seed.mechanism_types import (
    STRUCTURAL_PRIMITIVES, fit_affine, type_tag, typed_compositions,
)
from nexus.seed.mechanism_world import LANGUAGE


def test_affine_fitter_solves_add1_and_misses_if_pos():
    add1 = [
        dict(action="ACT_0", observation=1),
        dict(action="ACT_1", observation=2),
        dict(action="ACT_2", observation=3),
    ]
    fitted = fit_affine(add1)
    assert fitted == dict(kind="affine", a=1, b=1, origin="model_fit")
    gate = [
        dict(action="ACT_0", observation=0),
        dict(action="ACT_1", observation=1),
        dict(action="ACT_NEG", observation=0),
    ]
    assert fit_affine(gate) is None


def test_type_directed_allows_if_pos_add1_not_sat_sat():
    allowed = set(typed_compositions())
    assert ("if_pos", "add1") in allowed
    assert ("sat_inc", "mul2") in allowed
    assert ("sat_inc", "sat_dec") not in allowed
    assert ("if_pos", "if_neg") not in allowed


def test_skill_store_resets_independently_of_policy():
    store = MechanismSkillStore()
    store.remember(("add1",), [dict(action="ACT_0", observation=1)], family="affine")
    weights = zero_weights()
    store.reset()
    assert store.skills == []
    assert weights["ACT_0"] == zero_weights()["ACT_0"]


def test_sign_pos_reject_is_not_acquisition():
    claims = score_claims(
        dict(mechanism="sign_pos", role="reject", primitives=list(STRUCTURAL_PRIMITIVES)),
        [], dict(remaining=[], representative=None), None, "STOP_UNRESOLVED",
        [dict(action="ACT_1", predicted=None, observed=1)],
    )
    assert claims["useful_acquisition"] is False
    assert claims["correct_reject"] is True
    assert claims["exact_mechanism_identification"] is False


def test_wave_tasks_are_fresh_and_structurally_split():
    ids = {row["task_id"] for row in wave_tasks(
        "wave1_source", "wave1_dev", "wave2_target", "wave2_reject",
        "wave3_compose", "wave3_retain",
    )}
    assert ids.isdisjoint(OPENED_IDS)
    targets = {row["mechanism"] for row in wave_tasks("wave2_target")}
    source = {row["mechanism"] for row in wave_tasks("wave1_source")}
    assert not (targets & source)
    assert "sign_pos" in {row["mechanism"] for row in wave_tasks("wave2_reject")}
    assert "if_pos_add1" not in LANGUAGE


def test_fixed_learner_acquires_if_pos_on_fresh_instance():
    task = next(row for row in wave_tasks("wave1_source") if row["mechanism"] == "if_pos")
    episode = run_episode(task, "fixed_learner", zero_acquire(), None, random.Random(2),
                          remember=False, retrieve=False)
    assert episode["useful_acquisition"] is True
    assert episode["exact_mechanism_identification"] is False
    assert episode["probe_origin"] == "programmer_supplied"


def test_continual_run_does_not_rescore_opened_or_write_assessment_memory():
    payload = run_continual(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    seen = {row["task_id"] for row in (payload.get("wave2") or []) + (payload.get("wave3") or [])}
    assert seen.isdisjoint(OPENED_IDS)
    if payload.get("wave2"):
        assert all(not row.get("memory_updated") for row in payload["wave2"])
        assert all(not row.get("policy_updated") for row in payload["wave2"])
        assert {row["arm"] for row in payload["wave2"]} >= {
            "fixed_learner", "policy_only", "memory_only", "full_nexus",
        }
