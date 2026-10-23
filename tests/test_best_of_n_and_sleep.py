"""Offline Best-of-N sandbox selection and sleep-export gates. 0 model calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.seed.best_of_n_verify import (
    GPU_REFUSED, metal_sampler_status, sample_metal_candidates,
    score_code_candidates, score_sentence_candidates,
)
from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from nexus.seed.sleep_consolidation import (
    collect_sleep_triples, metal_lora_status, run_metal_lora, write_sleep_jsonl,
)


SPEC = {
    "id": "py_path_slash_mock",
    "language": "python",
    "request": "Create function tag(item) that returns lane and bay in lowercase joined by one slash.",
    "files": {"lane.py": "def echo(text):\n    return text\n"},
    "public": [
        {"entry": "lane.tag", "input": {"lane": "Lab", "bay": "East"}, "expected": "lab/east"},
        {"entry": "lane.tag", "input": {"bay": "East"}, "expected": "/east"},
        {"entry": "lane.tag", "input": {"lane": "Lab"}, "expected": "lab/"},
    ],
}
SAFE = (
    "return (item['lane'] if 'lane' in item else '').lower() + '/' + "
    "(item['bay'] if 'bay' in item else '').lower()"
)
FAIL_FSTR = "return f\"{item['lane'].lower()}/{item['bay'].lower()}\""
FAIL_SET = "return {item['zone'].lower()}/{item['path'].lower()}"
FAIL_LITERAL = "return '/lab/'"


def _plan():
    return plan_constrained_edit(SPEC["request"], SPEC["files"], SPEC["public"])


def test_best_of_4_picks_first_public_pass():
    result = score_code_candidates(
        [
            json.dumps({"body": FAIL_FSTR}),
            json.dumps({"body": FAIL_SET}),
            json.dumps({"body": FAIL_LITERAL}),
            json.dumps({"body": SAFE}),
        ],
        SPEC,
        _plan(),
    )
    assert result.backend == "cpu_sandbox"
    assert result.learning_to_learn is False
    assert result.first_turn_public_all_passed is True
    assert result.selected is not None
    assert result.selected.index == 3
    assert result.selected.public_pass_count == 3
    assert result.selected.public_n == 3
    assert [row.public_passed for row in result.scores] == [False, False, False, True]


def test_best_of_4_reports_no_pass_without_planting():
    result = score_code_candidates(
        [
            json.dumps({"body": FAIL_FSTR}),
            json.dumps({"body": FAIL_SET}),
            json.dumps({"body": FAIL_LITERAL}),
            json.dumps({"body": "return item['lane']"}),
        ],
        SPEC,
        _plan(),
    )
    assert result.selected is None
    assert result.first_turn_public_all_passed is False


def test_sentence_best_of_n_uses_lexicon_verifier(tmp_path: Path):
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    vault.ingest_document(
        "seed-photo-1",
        "Seed note",
        "In 2026 photophosphorylation yields ATP inside the Seed lab.",
    )
    capsule = store.ingest_new_term(
        "photophosphorylation",
        "the light-driven synthesis of ATP",
        "noun_phrase",
        required_tokens=("atp",),
    )
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    result = score_sentence_candidates(
        [
            "Photophosphorylation.",
            "Photophosphorylation created 99 ATP in 1899.",
            "Photophosphorylation yields ATP inside the Seed lab in 2026 [seed-photo-1].",
        ],
        targeted_capsule=capsule,
        retrieved_facts=facts,
    )
    assert result.selected is not None
    assert result.selected.index == 2
    assert result.selected.sentence_passed is True
    vault.close()
    store.close()


def test_metal_sampler_and_lora_are_refused():
    status = metal_sampler_status()
    assert status["available"] is False
    assert status["reason"] == GPU_REFUSED
    assert status["pinned_runtime_temperature"] == 0
    with pytest.raises(ValueError, match=GPU_REFUSED):
        sample_metal_candidates("unused")
    lora = metal_lora_status()
    assert lora["available"] is False
    assert lora["learning_to_learn"] is False
    with pytest.raises(ValueError, match=GPU_REFUSED):
        run_metal_lora("unused.jsonl", output_dir="unused")


def test_sleep_export_keeps_only_verified_episodes(tmp_path: Path):
    triples = collect_sleep_triples(
        coding_episodes=[
            {"public_passed": True, "prompt": "tag(item)", "body": SAFE, "public": SPEC["public"]},
            {"public_passed": False, "prompt": "bad", "body": FAIL_LITERAL},
        ],
        lexicon_episodes=[
            {
                "passed": True,
                "prompt": "Explain the term.",
                "grounded_context": "In 2026 photophosphorylation yields ATP.",
                "verified_response": "Photophosphorylation yields ATP in 2026 [seed-photo-1].",
            },
        ],
    )
    path = tmp_path / "sleep.jsonl"
    written = write_sleep_jsonl(path, triples)
    assert written == 2
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(set(row) == {"prompt", "grounded_context", "verified_response"} for row in rows)
    assert SAFE in rows[0]["verified_response"]
