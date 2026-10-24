"""Sub-clause skill work-reduction tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.mechanism_skill_work import (
    FAMILY_INDEX, NEG_SIGNATURE, OPENED_IDS, POS_SIGNATURE, compatible_names,
    run_skill_work, verify_payload,
)
from nexus.seed.mechanism_skills import SubMechanismLibrary
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks


def test_holdout_is_disjoint_and_shares_subclause_signatures():
    source = unfamiliar_policy_tasks("up_source")
    holdout = unfamiliar_policy_tasks("up_holdout")
    assert {row["task_id"] for row in source + holdout}.isdisjoint(OPENED_IDS)
    assert {row["mechanism"] for row in holdout}.isdisjoint({row["mechanism"] for row in source})
    assert FAMILY_INDEX["up_pos_plus2"] == FAMILY_INDEX["up_src_pos_plus"] == POS_SIGNATURE
    assert FAMILY_INDEX["up_neg_gate"] == FAMILY_INDEX["up_src_neg_id"] == NEG_SIGNATURE
    assert "up_pos_plus2" in compatible_names(POS_SIGNATURE)
    assert "up_src_pos_plus" in compatible_names(POS_SIGNATURE)
    assert "up_neg_twice" in compatible_names(NEG_SIGNATURE)


def test_whole_mechanism_cache_misses_unseen_composition():
    library = SubMechanismLibrary()
    library.remember_whole("up_src_pos_plus", [dict(action="ACT_1", observation=5)])
    assert library.lookup_whole([dict(action="ACT_1", observation=3)]) is None
    library.remember_subclause(dict(
        source_mechanism="up_src_pos_plus", signature=POS_SIGNATURE, clause="pos_guard_or_leaf",
    ))
    assert library.lookup_subclause(POS_SIGNATURE)
    assert library.whole_hits == 0
    assert library.sub_hits == 1
    assert library.retrieval_evals > 0


def test_skill_work_run_passes_verifier_and_keeps_policy_cost():
    payload = run_skill_work(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    hold = payload["totals"]["holdout"]
    cleared = hold["learned_adaptive_policy_memory_cleared"]
    memory = hold["learned_adaptive_policy_plus_subskill_memory"]
    assert cleared["env_interactions"] == memory["env_interactions"] == 21
    assert cleared["probe_feature_and_policy_evals"] == memory["probe_feature_and_policy_evals"] == 246
    assert cleared["total_acquisition_work"] == 699
    assert memory["total_acquisition_work"] < 699
    assert memory["whole_mechanism_hits"] == 0
    assert memory["subclause_hits"] > 0
    assert payload["usage"]["model_calls"] == 0
    assert payload["track_b_closed"] is True
    assert payload["learning_to_learn_established"] is False
