"""Offline retrieval relevance and citation provenance. 0 model calls."""
from __future__ import annotations

from pathlib import Path

from nexus.seed.lexicon_vault import KnowledgeVault, LexicalCapsuleStore, verify_composed_response


def _vault(tmp_path: Path) -> KnowledgeVault:
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    vault.ingest_document(
        "seed-photo-1",
        "Photosynthesis note",
        "In 2026 photophosphorylation yields ATP inside the Seed lab.",
    )
    vault.ingest_document(
        "seed-crate-1",
        "Crate tally",
        "The west aisle stored 17 unmarked crates and no light chemistry.",
    )
    return vault


def test_competing_documents_retrieve_the_relevant_source(tmp_path: Path):
    vault = _vault(tmp_path)
    hits = vault.retrieve_grounded_facts("photophosphorylation ATP Seed")
    assert hits
    assert hits[0].doc_id == "seed-photo-1"
    assert all(row.doc_id != "seed-crate-1" for row in hits)
    vault.close()


def test_unrelated_query_and_missing_information_return_nothing(tmp_path: Path):
    vault = _vault(tmp_path)
    assert vault.retrieve_grounded_facts("zebra piano nebula") == []
    assert vault.get_document("does-not-exist") is None
    vault.close()


def test_answer_must_cite_the_retrieved_source(tmp_path: Path):
    vault = _vault(tmp_path)
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    capsule = store.ingest_new_term(
        "photophosphorylation",
        "the light-driven synthesis of ATP",
        "noun_phrase",
        required_tokens=("atp",),
    )
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    missing = verify_composed_response(
        "Photophosphorylation yields ATP inside the Seed lab in 2026.",
        targeted_capsule=capsule,
        retrieved_facts=facts,
        vault=vault,
    )
    assert missing.passed is False
    assert any("missing_citation:seed-photo-1" in reason for reason in missing.reasons)
    wrong = verify_composed_response(
        "Photophosphorylation yields ATP inside the Seed lab in 2026 [seed-crate-1].",
        targeted_capsule=capsule,
        retrieved_facts=facts,
        vault=vault,
    )
    assert wrong.passed is False
    assert "fact_attribution:unknown_citation:seed-crate-1" in wrong.reasons
    ok = verify_composed_response(
        "Photophosphorylation yields ATP inside the Seed lab in 2026 [seed-photo-1].",
        targeted_capsule=capsule,
        retrieved_facts=facts,
        vault=vault,
    )
    assert ok.passed is True
    vault.close()
    store.close()


def test_updated_document_cannot_keep_an_old_citation_payload(tmp_path: Path):
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    first = vault.ingest_document(
        "seed-compare-1",
        "Old dock note",
        "In 2019 the north hangar stored 17 unmarked crates.",
    )
    old_hash = first.source_hash
    stale = vault.get_document("seed-compare-1")
    updated = vault.ingest_document(
        "seed-compare-1",
        "New dock note",
        "In 2026 the Seed dock catalog lists a verified binding for each stored crate label.",
    )
    assert updated.source_hash != old_hash
    assert vault.get_document("seed-compare-1").content != stale.content
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    capsule = store.ingest_new_term(
        "dockbinding",
        "a Seed-lab name for a stored crate label",
        "noun_phrase",
        required_tokens=("catalog", "crate"),
    )
    retrieved = vault.retrieve_grounded_facts("Seed dock catalog crate")
    old_text = "Dockbinding catalog kept 17 unmarked crate labels in the north hangar in 2019 [seed-compare-1]."
    checked = verify_composed_response(
        old_text,
        targeted_capsule=capsule,
        retrieved_facts=[stale] if stale is not None else retrieved,
        vault=vault,
    )
    assert checked.passed is False
    assert any(
        reason.startswith("fact_attribution:ungrounded_number")
        or "citation_tokens_missing" in reason
        for reason in checked.reasons
    )
    current = verify_composed_response(
        "Dockbinding lists each stored crate label in the Seed dock catalog in 2026 [seed-compare-1].",
        targeted_capsule=capsule,
        retrieved_facts=retrieved,
        vault=vault,
    )
    assert current.passed is True
    vault.close()
    store.close()
