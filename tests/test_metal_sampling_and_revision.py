"""Offline sampling-audit, revision-feedback, and vault-restart gates."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.function_format import prompt_for_format
from nexus.seed.lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from nexus.seed.local_model_runtime import RuntimeConfig
from nexus.seed.metal_best_of_4_smoke import SmokeTask, code_spec, load_config
from nexus.seed.metal_model_runtime import (
    ExplicitMetalGrant, MetalGrantEnforcer, PersistentMetalRuntime, audit_request_log,
)
from nexus.seed.metal_revision_compare import (
    code_error_feedback, run_independent_code, run_revision_code,
)
from nexus.seed.metal_sampling_audit import AUDIT_PROMPT, run_sampling_audit
from nexus.seed.sleep_consolidation import collect_sleep_triples, write_sleep_jsonl

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "configs/seed_metal_best_of_4_smoke.json")
FAIL = '{"body": "return yard.lower() + \'/\' + slip.lower()"}'
SAFE = (
    '{"body": "return (item[\'yard\'] if \'yard\' in item else \'\').lower() + \'/\' + '
    '(item[\'slip\'] if \'slip\' in item else \'\').lower()"}'
)


def test_complete_posts_four_distinct_temperature_seed_payloads():
    grant = ExplicitMetalGrant(authorized=True, ledger_path="unused.json", seed=42)
    runtime = PersistentMetalRuntime.__new__(PersistentMetalRuntime)
    runtime.config = RuntimeConfig("unused.gguf", application_cache=False, prompt_cache=False)
    runtime.grant = grant
    runtime.process = SimpleNamespace(poll=lambda: None)
    runtime.request_log = []
    runtime._lock = threading.Lock()
    runtime._cancel = threading.Event()
    runtime._connection = None
    posted = []

    def fake_http(method, path, payload, timeout):
        posted.append(dict(payload))
        return dict(content=f"{payload['temperature']}:{payload['seed']}", tokens_evaluated=3, tokens_predicted=2)

    runtime._http = fake_http
    runtime._abort_request = lambda: None
    texts = []
    for temperature, seed in ((0.0, 42), (0.35, 43), (0.35, 44), (0.35, 45)):
        out = runtime.complete("ping", None, temperature=temperature, seed=seed)
        texts.append(out["content"])
    audit = audit_request_log(runtime.request_log)
    assert [row["temperature"] for row in posted] == [0.0, 0.35, 0.35, 0.35]
    assert [row["seed"] for row in posted] == [42, 43, 44, 45]
    assert all(row["cache_prompt"] is False for row in posted)
    assert all(row.get("application_cache_consulted") is False for row in runtime.request_log)
    assert audit["four_distinct_requests"] is True
    assert audit["identical_drafts_do_not_prove_sampler_bug"] is True
    assert len(set(texts)) == 4


def test_sampling_audit_counts_distinct_requests_even_if_texts_match(tmp_path: Path):
    grant = ExplicitMetalGrant(
        authorized=True, ledger_path=str(tmp_path / "metal_ledger.json"), seed=42,
    )
    enforcer = MetalGrantEnforcer(grant, hardware_probe=lambda: True, rss_reader=lambda: 64.0)

    def sampler(prompt, plan):
        del prompt
        return "gold"

    report = run_sampling_audit(grant=grant, sampler=sampler, enforcer=enforcer, prompt=AUDIT_PROMPT)
    assert report["texts"] == ["gold"] * 4
    assert report["audit"]["distinct_raw_texts"] == 1
    assert report["audit"]["four_distinct_requests"] is True
    assert report["identical_drafts_do_not_prove_sampler_bug"] is True


def test_revision_feedback_names_keys_without_planting_a_function():
    spec = code_spec(CONFIG)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    from nexus.seed.metal_revision_compare import evaluate_code_raw

    public = evaluate_code_raw(FAIL, spec, plan)
    feedback = code_error_feedback(public, spec, FAIL)
    assert "yard" in feedback["undefined_names"]
    assert "slip" in feedback["undefined_names"]
    assert feedback["public_input_keys"] == ["slip", "yard"]
    blob = json.dumps(feedback)
    assert ".get" not in blob
    assert "if 'yard' in item" not in blob
    assert "lower()" not in blob


def test_equal_budget_revision_can_use_error_feedback(tmp_path: Path):
    spec = code_spec(CONFIG)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    task = SmokeTask(spec["request"], spec["public"], [])
    rendered, _ = (prompt_for_format("json_body", task, plan, None), plan)

    def independent_sampler(prompt, plan_row):
        del prompt
        return [FAIL, FAIL, FAIL, SAFE][plan_row.index]

    independent = run_independent_code(independent_sampler, rendered, spec, plan)
    assert independent["n_calls"] == 4
    assert independent["selected_index"] == 3
    assert independent["public_passed"] is True

    def revision_sampler(prompt, plan_row):
        if plan_row.index == 0:
            return FAIL
        assert "undefined_names" in prompt or "public_input_keys" in prompt
        assert ".get" not in prompt
        return SAFE

    revision = run_revision_code(revision_sampler, rendered, spec, plan, task)
    assert revision["n_calls"] == 2
    assert revision["budget"] == 4
    assert revision["public_passed"] is True
    assert revision["selected_index"] == 1
    assert revision["planted_solution"] is False


def test_failed_drafts_do_not_become_sleep_examples(tmp_path: Path):
    written = write_sleep_jsonl(
        tmp_path / "sleep.jsonl",
        collect_sleep_triples(
            lexicon_episodes=[
                {
                    "passed": False,
                    "prompt": "Explain the term.",
                    "grounded_context": "unused",
                    "verified_response": "In 2026 the Seed lab stores verified lexicon sentences.",
                }
            ]
        ),
    )
    assert written == 0
    assert (tmp_path / "sleep.jsonl").read_text(encoding="utf-8") == ""


def test_smoke_sqlite_homes_are_not_the_metal_ledger():
    vault = KnowledgeVault(ROOT / "artifacts/seed_metal_best_of_4_smoke/vault.sqlite")
    store = LexicalCapsuleStore(ROOT / "artifacts/seed_metal_best_of_4_smoke/capsules.sqlite")
    loaded = vault.get_document("seed-metal-1")
    assert loaded is not None
    assert loaded.doc_id == "seed-metal-1"
    assert "knowledge vault" in loaded.content
    assert store.get("metalvault") is not None
    vault.close()
    store.close()


def test_vault_survives_restart_with_provenance(tmp_path: Path):
    vault_path = tmp_path / "vault.sqlite"
    capsule_path = tmp_path / "capsules.sqlite"
    vault = KnowledgeVault(vault_path)
    store = LexicalCapsuleStore(capsule_path)
    snippet = vault.ingest_document(
        "seed-metal-1",
        "Seed Metal vault note",
        "In 2026 the Seed lab stores verified lexicon sentences in the knowledge vault.",
    )
    store.ingest_new_term(
        "metalvault",
        "the Seed-lab store of verified lexicon sentences",
        "noun_phrase",
        required_tokens=("vault", "sentence"),
    )
    vault.close()
    store.close()
    vault2 = KnowledgeVault(vault_path)
    store2 = LexicalCapsuleStore(capsule_path)
    loaded = vault2.get_document("seed-metal-1")
    assert loaded is not None
    assert loaded.source_hash == snippet.source_hash
    assert loaded.timestamp == snippet.timestamp
    assert loaded.content == snippet.content
    hits = vault2.retrieve_grounded_facts("verified lexicon sentences vault")
    assert hits and hits[0].doc_id == "seed-metal-1"
    assert hits[0].source_hash == snippet.source_hash
    capsule = store2.get("metalvault")
    assert capsule is not None
    assert capsule.required_tokens == ("vault", "sentence")
    tables = {row[0] for row in vault2.conn.execute("SELECT name FROM sqlite_master")}
    assert "facts" in tables
    assert "procedures" not in tables
    vault2.close()
    store2.close()
