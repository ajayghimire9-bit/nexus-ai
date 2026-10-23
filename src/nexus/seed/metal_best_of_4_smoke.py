"""Locked 2-cell Apple Silicon Metal Best-of-4 smoke.

Reuses ``score_code_candidates``, ``score_sentence_candidates``,
``verify_composed_response``, and ``write_sleep_jsonl``. Does not edit
``local_model_runtime.py``. Does not debit the frozen CPU ledger
(3564.568 s). Not learning-to-learn and not confirmation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .best_of_n_verify import score_code_candidates, score_sentence_candidates
from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .function_format import assemble_format_proposal, prompt_for_format, schema_for_format
from .lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from .metal_model_runtime import (
    CPU_LEDGER_USED_S,
    ExplicitMetalGrant,
    MetalGrantEnforcer,
    PersistentMetalRuntime,
    bind_live_metal_sampler,
    load_metal_ledger,
    local_runtime_sha256,
)
from .sleep_consolidation import collect_sleep_triples, write_sleep_jsonl
from .agent_loop_worker import evaluate_python_payload


LOCAL_RUNTIME_SHA256 = "5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781"
CODER15_SHA256 = "cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046"


@dataclass
class SmokeTask:
    request: str
    public_tests: list
    docs: list


def load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def grant_from_config(config: dict[str, Any], *, ledger_path: str | None = None) -> ExplicitMetalGrant:
    data = dict(config["metal_grant"])
    if ledger_path is not None:
        data["ledger_path"] = ledger_path
    return ExplicitMetalGrant.from_config(data, env={})


def code_spec(config: dict[str, Any]) -> dict[str, Any]:
    cell = config["cell1"]
    return dict(
        id=cell["id"],
        language="python",
        request=cell["request"],
        files=dict(cell["files"]),
        public=list(cell["public"]),
        private=list(cell["private"]),
    )


def code_prompt(config: dict[str, Any]) -> tuple[str, Any]:
    spec = code_spec(config)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    task = SmokeTask(spec["request"], spec["public"], [])
    user = prompt_for_format(config["format"], task, plan, None)
    if ".get" in user:
        raise ValueError("planted_get_in_prompt")
    rendered, _meta = render_prompt(config["prompt_style"], user)
    return rendered, plan


def sentence_prompt(config: dict[str, Any]) -> str:
    cell = config["cell2"]
    user = (
        f"Write one complete English sentence that uses the word {cell['term']}, "
        f"includes the tokens {', '.join(cell['required_tokens'])}, ends with a period, "
        f"and cites [{cell['doc_id']}]. Use only numbers that appear in the fact. "
        f"Reply with the sentence only.\n"
        f"Fact [{cell['doc_id']}]: {cell['fact']}\n"
        f"Term: {cell['term']} — {cell['definition']}\n"
    )
    if ".get" in user:
        raise ValueError("planted_get_in_prompt")
    rendered, _meta = render_prompt(config["prompt_style"], user)
    return rendered


def score_payload(result) -> dict[str, Any]:
    selected = None if result.selected is None else dict(
        index=result.selected.index,
        raw=result.selected.raw,
        public_passed=result.selected.public_passed,
        public_pass_count=result.selected.public_pass_count,
        public_n=result.selected.public_n,
        structurally_valid=result.selected.structurally_valid,
        sentence_passed=result.selected.sentence_passed,
        reasons=list(result.selected.reasons),
    )
    return dict(
        selected=selected,
        first_turn_public_all_passed=result.first_turn_public_all_passed,
        backend=result.backend,
        scores=[
            dict(
                index=row.index,
                raw=row.raw,
                public_passed=row.public_passed,
                public_pass_count=row.public_pass_count,
                public_n=row.public_n,
                structurally_valid=row.structurally_valid,
                sentence_passed=row.sentence_passed,
                reasons=list(row.reasons),
            )
            for row in result.scores
        ],
    )


def private_eval(config: dict[str, Any], raw: str, plan) -> dict[str, Any]:
    spec = code_spec(config)
    assembled = assemble_format_proposal(
        config["format"], raw, spec["request"], spec["files"], spec["public"], plan=plan,
    )
    files = assembled.get("patched_files") or spec["files"]
    public_payload = dict(language="python", files=files, cases=spec["private"])
    if not assembled.get("structurally_valid"):
        return dict(all_passed=False, passed_n=0, n=len(spec["private"]), reason="structurally_invalid")
    evaluated = evaluate_python_payload(public_payload)
    results = list(evaluated.get("results") or [])
    passed_n = sum(1 for row in results if row.get("passed"))
    return dict(
        all_passed=bool(evaluated.get("all_passed")),
        passed_n=passed_n,
        n=len(results),
        reason=evaluated.get("reason") or "",
        results=results,
    )


def replay_code_cell(config: dict[str, Any], raws: list[str]):
    spec = code_spec(config)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    return score_code_candidates(raws, spec, plan)


def replay_sentence_cell(config: dict[str, Any], drafts: list[str], directory: Path):
    cell = config["cell2"]
    vault = KnowledgeVault(directory / "replay_vault.sqlite")
    store = LexicalCapsuleStore(directory / "replay_capsules.sqlite")
    try:
        vault.ingest_document(cell["doc_id"], cell["title"], cell["fact"])
        capsule = store.ingest_new_term(
            cell["term"], cell["definition"], cell["pos_or_frame"],
            required_tokens=cell["required_tokens"],
        )
        facts = vault.retrieve_grounded_facts(cell["retrieve_query"])
        return score_sentence_candidates(drafts, targeted_capsule=capsule, retrieved_facts=facts)
    finally:
        vault.close()
        store.close()


def run_cells(
    config: dict[str, Any],
    directory: Path,
    *,
    grant: ExplicitMetalGrant,
    code_sampler: Callable,
    sentence_sampler: Callable,
    enforcer: MetalGrantEnforcer,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    spec = code_spec(config)
    rendered, plan = code_prompt(config)
    code = score_code_candidates(
        None,
        spec,
        plan,
        prompt=rendered,
        metal_grant=grant,
        metal_sampler=code_sampler,
        metal_enforcer=enforcer,
    )
    private = None
    if code.selected is not None:
        private = private_eval(config, code.selected.raw, plan)
    records.append(dict(
        kind="cell1_code",
        prompt=rendered,
        candidates=[row.raw for row in code.scores],
        result=score_payload(code),
        private=private,
        planted_get=False,
    ))

    cell = config["cell2"]
    vault = KnowledgeVault(directory / "vault.sqlite")
    store = LexicalCapsuleStore(directory / "capsules.sqlite")
    vault.ingest_document(cell["doc_id"], cell["title"], cell["fact"])
    capsule = store.ingest_new_term(
        cell["term"], cell["definition"], cell["pos_or_frame"],
        required_tokens=cell["required_tokens"],
    )
    facts = vault.retrieve_grounded_facts(cell["retrieve_query"])
    sentence_text = sentence_prompt(config)
    sentences = score_sentence_candidates(
        prompt=sentence_text,
        targeted_capsule=capsule,
        retrieved_facts=facts,
        metal_grant=grant,
        metal_sampler=sentence_sampler,
        metal_enforcer=enforcer,
    )
    sleep_path = directory / "sleep.jsonl"
    written = 0
    if sentences.selected is not None:
        triples = collect_sleep_triples(
            lexicon_episodes=[
                dict(
                    passed=True,
                    prompt=sentence_text,
                    grounded_context=cell["fact"],
                    verified_response=sentences.selected.raw,
                )
            ]
        )
        written = write_sleep_jsonl(sleep_path, triples)
    records.append(dict(
        kind="cell2_sentence",
        prompt=sentence_text,
        candidates=[row.raw for row in sentences.scores],
        result=score_payload(sentences),
        sleep_jsonl=str(sleep_path) if written else "",
        sleep_rows=written,
        doc_id=cell["doc_id"],
        term=cell["term"],
    ))
    vault.close()
    store.close()
    return records


def summarize(records: list[dict[str, Any]], config: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    code = next(row for row in records if row["kind"] == "cell1_code")
    sentence = next(row for row in records if row["kind"] == "cell2_sentence")
    selected_code = code["result"]["selected"]
    selected_sentence = sentence["result"]["selected"]
    return dict(
        cell1_promoted_index=None if selected_code is None else selected_code["index"],
        cell1_public_passed=bool(selected_code and selected_code["public_passed"]),
        cell1_private_3_of_3=bool((code.get("private") or {}).get("all_passed")),
        cell2_promoted_index=None if selected_sentence is None else selected_sentence["index"],
        cell2_sentence_passed=bool(selected_sentence and selected_sentence["sentence_passed"]),
        sleep_rows=sentence.get("sleep_rows") or 0,
        metal_used_s=ledger.get("used_s"),
        metal_peak_rss_mib=ledger.get("peak_rss_mib"),
        metal_calls=len(ledger.get("calls") or []),
        cpu_ledger_used_s=CPU_LEDGER_USED_S,
        cpu_ledger_debit_s=0,
        local_model_runtime_sha256=local_runtime_sha256(),
        local_model_runtime_unchanged=local_runtime_sha256() == LOCAL_RUNTIME_SHA256,
        learning_to_learn=False,
        confirmation=False,
    )


def build_payload(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    ledger: dict[str, Any],
    *,
    blocked: str | None,
    model_metadata: dict[str, Any] | None,
    wall_s: float,
) -> dict[str, Any]:
    return dict(
        study_id=config["id"],
        scientific=False,
        kind=config["kind"],
        config_hash=digest(config),
        blocked_step=blocked,
        model_metadata=model_metadata,
        records=records,
        metal_ledger=ledger,
        summary=summarize(records, config, ledger) if records else dict(
            cpu_ledger_used_s=CPU_LEDGER_USED_S,
            cpu_ledger_debit_s=0,
            local_model_runtime_unchanged=local_runtime_sha256() == LOCAL_RUNTIME_SHA256,
            learning_to_learn=False,
        ),
        resources=dict(wall_s=round(wall_s, 6)),
        learning_to_learn=False,
        agi=False,
    )


def start_live_runtime(config: dict[str, Any], grant: ExplicitMetalGrant):
    from .local_model_runtime import RuntimeConfig, file_hash

    spec = config["model"]
    model = Path(spec["path"])
    if not model.is_file():
        return None, "BLOCKED_MISSING_MODEL", None
    if file_hash(model) != spec["sha256"]:
        raise ValueError("frozen_model_hash_mismatch:" + spec["label"])
    if spec["sha256"] != CODER15_SHA256:
        raise ValueError("unexpected_coder_hash")
    runtime = PersistentMetalRuntime(
        RuntimeConfig(
            str(model),
            max_tokens=int(config.get("max_tokens") or 128),
            application_cache=False,
            request_timeout_s=float(config.get("request_timeout_s") or 8),
            startup_timeout_s=float(config.get("startup_timeout_s") or 25),
            threads=int(config.get("threads") or 2),
        ),
        grant,
    )
    return runtime, None, runtime.start()
