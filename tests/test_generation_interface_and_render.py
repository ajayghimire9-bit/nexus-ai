"""Offline interface audit, structured render, and coding diagnostic gates."""
from __future__ import annotations

from pathlib import Path

from nexus.seed.coding_capacity_diagnostic import FAMILIES, load_config, run_supplied, summarize
from nexus.seed.generation_interface_audit import audit_compare_artifact, inspect_prompt, looks_malformed, termination_guess
from nexus.seed.lexicon_vault import (
    KnowledgeVault, LexicalCapsuleStore, VerificationResult, render_structured_binding,
    verify_composed_response, verify_structured_render,
)
from nexus.seed.metal_live_compare import AssistantCost
from nexus.seed.metal_revision_compare import revision_sentence_prompt

ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "artifacts/seed_metal_live_compare/seed_metal_live_compare.json"
DIAG = load_config(ROOT / "configs/seed_coding_capacity_diagnostic.json")


def test_live_compare_prompts_are_chatml_and_some_outputs_look_interface_broken():
    report = audit_compare_artifact(COMPARE)
    assert report["chatml_ok"] is True
    assert report["stop_reasons_were_not_logged"] is True
    assert report["any_hit_token_cap"] is False
    assert report["any_echoed_feedback"] is True
    assert report["any_malformed"] is True
    assert any(row["looks_like_truncated_get"] for row in report["rows"])
    kinds = {row["kind"] for row in report["rows"]}
    assert "code_revision" in kinds


def test_inspect_prompt_finds_json_body_and_rejects_planted_get():
    from nexus.seed.metal_live_compare import code_prompt, load_config

    config = load_config(ROOT / "configs/seed_metal_live_compare.json")
    rendered, _plan, _task = code_prompt(config)
    info = inspect_prompt(rendered)
    assert info["chatml"] is True
    assert info["asks_json_body"] is True
    assert info["planted_get"] is False


def test_sentence_revision_prompt_does_not_dump_json_to_echo():
    checked = VerificationResult(
        passed=False,
        reasons=("lexical_frame:term_missing", "fact_attribution:missing_citation:seed-compare-1"),
        cited_doc_ids=(),
        targeted_term="dockbinding",
    )
    prompt = revision_sentence_prompt("Write a sentence.", checked)
    assert "The previous sentence failed" in prompt
    assert '"reasons"' not in prompt
    assert "Write one new English sentence only" in prompt


def test_malformed_get_is_not_proven_token_cap():
    text = '{"body": "return f\'{item.get(\\"hall\\", \\\\\" }"}'
    assert looks_malformed(text) is True
    assert termination_guess(text) == "malformed_or_possibly_truncated"
    assert termination_guess(text, truncated=True, tokens_predicted=128) == "hit_token_cap"


def test_structured_render_is_deterministic_and_uses_current_fact(tmp_path: Path):
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    fact = vault.ingest_document(
        "seed-compare-1",
        "Dock note",
        "In 2026 the Seed dock catalog lists a verified binding for each stored crate label.",
    )
    capsule = store.ingest_new_term(
        "dockbinding",
        "a Seed-lab name for a stored crate label",
        "noun_phrase",
        required_tokens=("catalog", "crate"),
    )
    rendered = render_structured_binding(capsule, fact)
    checked = verify_structured_render(rendered, capsule, fact)
    assert checked.passed is True
    assert rendered.startswith("dockbinding [seed-compare-1]:")
    stale = render_structured_binding(capsule, fact).replace("2026", "2019")
    assert verify_structured_render(stale, capsule, fact).passed is False
    free = verify_composed_response(
        "Dockbinding lists each stored crate label in the Seed dock catalog in 2026 [seed-compare-1].",
        targeted_capsule=capsule,
        retrieved_facts=[fact],
        vault=vault,
    )
    assert free.passed is True
    vault.close()
    store.close()


def test_coding_diagnostic_scores_four_families_without_claiming_a_missing_stronger_model():
    proposals = {
        "current": {
            "field_access": '{"body": "return item[\'name\'].lower()"}',
            "missing_values": (
                '{"body": "return (item[\'room\'] if \'room\' in item else \'\').lower() + \'/\' + '
                '(item[\'shelf\'] if \'shelf\' in item else \'\').lower()"}'
            ),
            "aggregation": '{"body": "return sum(item[\'amounts\'])"}',
            "composition": '{"body": "return join_parts(item[\'left\'].lower(), item[\'right\'].lower())"}',
        }
    }
    records = run_supplied(DIAG, proposals)
    clock = AssistantCost()
    summary = summarize(records, clock, stronger_blocked=True)
    assert [task["family"] for task in DIAG["tasks"]] == list(FAMILIES)
    assert summary["stronger_blocked"] is True
    assert summary["comparison_established"] is False
    assert summary["vault_retention_is_not_acquired_knowledge"] is True
    assert summary["models"]["current"]["public_passed"] == 4
    assert summary["models"]["current"]["private_passed"] == 4
    assert ".get" not in DIAG["tasks"][1]["request"]
