"""Offline Knowledge Vault and lexicon capsule checks. 0 model calls."""
from __future__ import annotations

import json
import time
from pathlib import Path

from nexus.seed.lexicon_vault import (
    KnowledgeVault,
    LexicalCapsuleStore,
    export_lora_sleep_dataset,
    verify_composed_response,
)


TERM = "photophosphorylation"
DEFINITION = "the light-driven synthesis of ATP in photosynthetic membranes"
FACT_ID = "seed-photo-1"
FACT_TITLE = "Seed photosynthetic note"
FACT_BODY = (
    "In 2026 the authored Seed lab recorded that photophosphorylation "
    "yields ATP inside a 6 by 6 object world."
)


def _day1(directory: Path):
    vault = KnowledgeVault(directory / "vault.sqlite")
    store = LexicalCapsuleStore(directory / "capsules.sqlite")
    snippet = vault.ingest_document(FACT_ID, FACT_TITLE, FACT_BODY)
    capsule = store.ingest_new_term(
        TERM,
        DEFINITION,
        "noun_phrase",
        required_tokens=("atp",),
        verified_examples=("Photophosphorylation yields ATP in the Seed lab.",),
    )
    return vault, store, snippet, capsule


def test_day1_ingests_term_and_fact(tmp_path: Path):
    vault, store, snippet, capsule = _day1(tmp_path)
    assert snippet.doc_id == FACT_ID
    assert snippet.source_hash
    assert snippet.timestamp
    assert store.get(TERM).definition == DEFINITION
    assert store.get(TERM).use_count == 0
    assert store.get(TERM).verified_pass_count == 0
    vault.close()
    store.close()


def test_retrieve_grounded_facts_is_fast_and_ranked(tmp_path: Path):
    vault, store, snippet, _capsule = _day1(tmp_path)
    vault.ingest_conversation_fact(
        "seed-other-1",
        "Unrelated note",
        "The conversation later mentioned a crate tally and no light chemistry.",
    )
    started = time.perf_counter()
    hits = vault.retrieve_grounded_facts("photophosphorylation ATP Seed", top_k=3)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert elapsed_ms < 5.0
    assert hits
    assert hits[0].doc_id == FACT_ID
    assert hits[0].provenance_id() == FACT_ID
    assert "ATP" in hits[0].content
    assert snippet.source_hash == hits[0].source_hash
    store.close()
    vault.close()


def test_day2_valid_sentence_passes_and_exports(tmp_path: Path):
    vault, store, _snippet, _capsule = _day1(tmp_path)
    capsules = store.retrieve_relevant_capsules("Explain photophosphorylation for tomorrow's draft.")
    assert [row.term for row in capsules] == [TERM]
    assert store.get(TERM).use_count == 1
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    draft = (
        "Photophosphorylation yields ATP inside the authored Seed lab in 2026 [seed-photo-1]."
    )
    started = time.perf_counter()
    result = verify_composed_response(
        draft, targeted_capsule=capsules[0], retrieved_facts=facts, store=store,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert elapsed_ms < 1.0
    assert result.passed is True
    assert result.reasons == ()
    assert result.cited_doc_ids == (FACT_ID,)
    assert store.get(TERM).verified_pass_count == 1
    export_path = tmp_path / "sleep.jsonl"
    written = export_lora_sleep_dataset(export_path, [
        {
            "passed": result.passed,
            "prompt": "Explain the new term with a grounded Seed fact.",
            "grounded_context": facts[0].content,
            "verified_response": draft,
        },
        {
            "passed": False,
            "prompt": "ignore",
            "grounded_context": "",
            "verified_response": "bad",
        },
    ])
    assert written == 1
    row = json.loads(export_path.read_text(encoding="utf-8").splitlines()[0])
    assert set(row) == {"prompt", "grounded_context", "verified_response"}
    assert row["verified_response"] == draft
    assert TERM.lower() in row["verified_response"].lower()
    vault.close()
    store.close()


def test_day2_rejects_fragment_definition_and_hallucination(tmp_path: Path):
    vault, store, _snippet, capsule = _day1(tmp_path)
    facts = vault.retrieve_grounded_facts("photophosphorylation")
    fragment = verify_composed_response(
        "Photophosphorylation.", targeted_capsule=capsule, retrieved_facts=facts,
    )
    assert fragment.passed is False
    assert any(reason.startswith("lexical_frame") for reason in fragment.reasons)
    copied = verify_composed_response(
        DEFINITION + ".", targeted_capsule=capsule, retrieved_facts=facts,
    )
    assert copied.passed is False
    assert "lexical_frame:definition_copy" in copied.reasons
    hallucinated = verify_composed_response(
        "Photophosphorylation created 99 ATP molecules in 1899 inside a 12 by 12 world.",
        targeted_capsule=capsule,
        retrieved_facts=facts,
    )
    assert hallucinated.passed is False
    assert any(reason.startswith("fact_attribution:ungrounded_number") for reason in hallucinated.reasons)
    assert any("missing_citation" in reason for reason in hallucinated.reasons)
    vault.close()
    store.close()


def test_unknown_citation_is_rejected(tmp_path: Path):
    vault, store, _snippet, capsule = _day1(tmp_path)
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    result = verify_composed_response(
        "Photophosphorylation yields ATP inside the authored Seed lab in 2026 [made-up-id].",
        targeted_capsule=capsule,
        retrieved_facts=facts,
    )
    assert result.passed is False
    assert "fact_attribution:unknown_citation:made-up-id" in result.reasons
    vault.close()
    store.close()
