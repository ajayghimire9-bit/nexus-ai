"""Product orchestration over Conversation, vault, and workspace tools.

Reuses KnowledgeVault, LexicalCapsuleStore, workspace_conversation, and
evaluate_python_payload. Persistence is explicit save, not learning-to-learn.
Does not edit local_model_runtime.py or debit the frozen CPU ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .lexicon_vault import (
    FactSnippet,
    KnowledgeVault,
    LexicalCapsule,
    LexicalCapsuleStore,
    _tokens,
    render_structured_binding,
    verify_composed_response,
    verify_structured_render,
)


USER_STATES = (
    "Draft",
    "Running",
    "Executed",
    "Tests passed",
    "Needs clarification",
    "Failed",
)
CODE_FENCE = re.compile(r"```(?:([A-Za-z0-9_+-]+)\n)?(.*?)```", re.S)
DOC_ASK = (
    "what does the document",
    "what do we know",
    "according to",
    "in the vault",
    "from the source",
    "cite",
    "source for",
    "what is stored",
    "look up",
    "retrieve",
)
KNOWLEDGE_SAVE = (
    "save this document",
    "save the document",
    "save this knowledge",
    "save knowledge",
    "save this as a document",
    "keep this document",
)
KNOWLEDGE_DELETE = ("delete this document", "delete the document", "delete saved knowledge")
TOPIC_CHANGE = (
    "new topic",
    "different question",
    "forget the last",
    "forget that file",
    "switching topics",
    "unrelated question",
)
EXPLAIN_CODE = ("explain this code", "what does this code", "review this code", "walk through")
EXECUTE_CODE = ("run this", "execute this", "test this", "run the tests", "apply this patch")
PREFERRED_MODEL = Path(".models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")


@dataclass(frozen=True)
class TurnClass:
    flow: str
    reason: str
    execute: bool = False
    structured: bool = False


def classify_turn(text: str, workspace: dict | None = None) -> TurnClass:
    raw = (text or "").strip()
    lowered = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    ws = workspace or {}
    if any(p in lowered for p in KNOWLEDGE_SAVE):
        return TurnClass("knowledge", "explicit_save")
    if any(p in lowered for p in KNOWLEDGE_DELETE):
        return TurnClass("knowledge", "explicit_delete")
    if any(p in lowered for p in TOPIC_CHANGE):
        return TurnClass("topic", "explicit_topic_change")
    fence = CODE_FENCE.search(raw)
    if fence or any(p in lowered for p in EXPLAIN_CODE + EXECUTE_CODE):
        execute = any(p in lowered for p in EXECUTE_CODE)
        return TurnClass("coding", "pasted_code", execute=execute)
    if any(p in lowered for p in DOC_ASK) or ws.get("selected_document_id") and "?" in raw:
        structured = lowered.startswith(("what is ", "define ", "show the binding"))
        return TurnClass("document", "vault_question", structured=structured)
    if lowered.startswith(("solve ", "calculate ", "compute ")) or (
        re.fullmatch(r"[0-9x+\-*/().\s=]+", lowered) and any(op in lowered for op in "+-*/=")
    ):
        return TurnClass("reasoning", "tool_math")
    if lowered in (
        "explain how nexus works",
        "explain how nexus seed works",
        "how does nexus work",
        "how does nexus seed work",
        "explain the nexus architecture",
        "explain nexus architecture",
        "explain the architecture",
        "show master architecture",
        "master architecture",
        "inspect master",
    ):
        return TurnClass("architecture", "explicit_architecture")
    return TurnClass("ordinary", "model_or_finite")


def user_status(*, executed: bool = False, tests_passed: bool | None = None,
                needs_clarification: bool = False, failed: bool = False,
                running: bool = False, draft: bool = False) -> str:
    if running:
        return "Running"
    if failed:
        return "Failed"
    if needs_clarification:
        return "Needs clarification"
    if tests_passed is True:
        return "Tests passed"
    if executed:
        return "Executed"
    if draft or tests_passed is False:
        return "Draft"
    return "Draft"


def preferred_model_path() -> Path | None:
    if os.environ.get("NEXUS_MODEL_PATH"):
        path = Path(os.environ["NEXUS_MODEL_PATH"]).expanduser()
        return path if path.is_file() else None
    if PREFERRED_MODEL.is_file():
        return PREFERRED_MODEL.resolve()
    fallback = Path(".models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
    return fallback.resolve() if fallback.is_file() else None


def apply_topic_change(workspace: dict, text: str) -> dict:
    """Clear stale constraints. Keep selected resources unless the user replaces them."""
    classified = classify_turn(text, workspace)
    lowered = (text or "").lower()
    inherit = any(p in lowered for p in ("do the same", "same for", "again", "repeat", "actually", "instead"))
    if classified.flow == "topic":
        pass
    elif inherit or classified.flow in {"coding", "document", "knowledge", "reasoning"}:
        return {"changed": False, "cleared": []}
    elif classified.flow == "ordinary":
        last = workspace.get("last_request_kind")
        keeps_tool = any(p in lowered for p in (
            ".csv", "workspace", "region", "totals", "rows", "minimum", "sort",
            "implement", "function", "file", "procedure",
        ))
        if last not in {"fresh", "coding", "document"} or keeps_tool:
            return {"changed": False, "cleared": []}
    else:
        return {"changed": False, "cleared": []}
    cleared = []
    for key in ("pending_clarification", "last_intent", "last_coding_request"):
        if workspace.get(key) is not None:
            workspace[key] = None
            cleared.append(key)
    workspace["last_topic"] = (text or "").strip()[:200] or None
    workspace["last_request_kind"] = "ordinary"
    return {"changed": bool(cleared), "cleared": cleared}


def extract_code(text: str) -> tuple[str | None, str]:
    match = CODE_FENCE.search(text or "")
    if match:
        return match.group(1) or "python", match.group(2).strip()
    return None, (text or "").strip()


def document_id_for(title: str, content: str) -> str:
    raw = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()
    return "doc-" + raw[:12]


def vault_for(store) -> KnowledgeVault:
    existing = getattr(store, "knowledge_vault", None)
    if existing is not None:
        return existing
    path = Path(store.directory) / "vault.sqlite"
    vault = KnowledgeVault(path)
    store.knowledge_vault = vault
    return vault


def capsules_for(store) -> LexicalCapsuleStore:
    existing = getattr(store, "capsule_store", None)
    if existing is not None:
        return existing
    path = Path(store.directory) / "capsules.sqlite"
    capsules = LexicalCapsuleStore(path)
    store.capsule_store = capsules
    return capsules


def compact_fact(fact: FactSnippet) -> dict[str, Any]:
    return dict(
        doc_id=fact.doc_id,
        title=fact.title,
        content=fact.content[:400],
        source_hash=fact.source_hash,
        timestamp=fact.timestamp,
        score=fact.score,
    )


def compact_capsule(capsule: LexicalCapsule) -> dict[str, Any]:
    return dict(
        term=capsule.term,
        definition=capsule.definition[:240],
        pos_or_frame=capsule.pos_or_frame,
        required_tokens=list(capsule.required_tokens)[:8],
        use_count=capsule.use_count,
        verified_pass_count=capsule.verified_pass_count,
    )


def list_procedures(store) -> list[dict[str, Any]]:
    rows = []
    listing = getattr(store, "procedures_dir", None)
    if not callable(listing):
        return rows
    for path in sorted(listing().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(dict(
            id=data.get("id"),
            name=data.get("name"),
            saved_explicitly=bool(data.get("saved_explicitly")),
            validation_scope=data.get("validation_scope"),
            learning_to_learn=False,
        ))
    return rows[:32]


def list_repair_schemas(store) -> list[dict[str, Any]]:
    root = Path(store.directory) / "repair_schemas"
    if not root.is_dir():
        return []
    from .repair_schema_memory import RepairSchemaStore
    loaded = RepairSchemaStore.load(root)
    return [dict(schema_id=s.schema_id, family=s.family, trigger=s.trigger) for s in loaded.schemas.values()][:16]


def knowledge_snapshot(store) -> dict[str, Any]:
    vault = vault_for(store)
    capsules = capsules_for(store)
    documents = []
    for row in vault.conn.execute(
        "SELECT doc_id, title, content, source_hash, timestamp FROM facts ORDER BY timestamp DESC"
    ):
        documents.append(dict(
            doc_id=row["doc_id"],
            title=row["title"],
            content=row["content"][:240],
            source_hash=row["source_hash"],
            timestamp=row["timestamp"],
        ))
    bindings = [compact_capsule(capsules._row(row)) for row in capsules.conn.execute("SELECT * FROM capsules")]
    return dict(
        documents=documents[:48],
        capsules=bindings[:48],
        procedures=list_procedures(store),
        repair_schemas=list_repair_schemas(store),
        persistence_is_learning_to_learn=False,
        vault_path=str(vault.path),
        capsules_path=str(capsules.path),
    )


def save_document(store, *, title: str, content: str, doc_id: str | None = None) -> FactSnippet:
    if not (content or "").strip():
        raise ValueError("empty_document")
    cleaned = (title or "Untitled document").strip()[:120] or "Untitled document"
    ident = (doc_id or document_id_for(cleaned, content)).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", ident):
        raise ValueError("document_id_schema")
    return vault_for(store).ingest_document(ident, cleaned, content.strip())


def delete_document(store, doc_id: str) -> bool:
    vault = vault_for(store)
    before = vault.get_document(doc_id)
    if before is None:
        return False
    vault.conn.execute("DELETE FROM facts WHERE doc_id = ?", (doc_id,))
    vault.conn.commit()
    return True


def save_capsule(store, *, term: str, definition: str, pos_or_frame: str = "noun_phrase") -> LexicalCapsule:
    return capsules_for(store).ingest_new_term(term, definition, pos_or_frame)


def delete_capsule(store, term: str) -> bool:
    capsules = capsules_for(store)
    if capsules.get(term) is None:
        return False
    capsules.conn.execute("DELETE FROM capsules WHERE term = ?", (term,))
    capsules.conn.commit()
    return True


QUESTION_STOP = {
    "what", "do", "we", "know", "about", "the", "a", "an", "in", "on", "of", "to",
    "from", "for", "please", "tell", "me", "does", "document", "stored", "according",
    "look", "up", "vault", "source", "cite", "question", "there", "any", "our",
}


def retrieve_for_question(vault: KnowledgeVault, query: str, selected_id: str | None = None, top_k: int = 3) -> list[FactSnippet]:
    found: list[FactSnippet] = []
    seen: set[str] = set()

    def add(rows: list[FactSnippet]) -> None:
        for fact in rows:
            live = vault.get_document(fact.doc_id) or fact
            if live.doc_id in seen:
                continue
            seen.add(live.doc_id)
            found.append(live)

    if selected_id:
        current = vault.get_document(selected_id)
        if current is not None:
            add([current])
    add(vault.retrieve_grounded_facts(query, top_k=top_k))
    keys = [tok for tok in _tokens(query) if tok not in QUESTION_STOP and len(tok) > 2]
    if keys:
        add(vault.retrieve_grounded_facts(" ".join(keys), top_k=top_k))
    if len(found) < top_k and keys:
        for row in vault.conn.execute(
            "SELECT doc_id, title, content, source_hash, timestamp FROM facts"
        ):
            hay = f"{row['title']} {row['content']} {row['doc_id']}".lower()
            if any(tok in hay for tok in keys):
                add([FactSnippet(row["doc_id"], row["title"], row["content"], row["source_hash"], row["timestamp"])])
            if len(found) >= top_k:
                break
    return found[:top_k]


def recover_selected_resources(store, workspace: dict) -> dict[str, Any]:
    missing = []
    selected = workspace.get("selected_file")
    if selected:
        path = Path(str(selected)).expanduser()
        if not path.is_file():
            missing.append(dict(kind="file", path=str(selected), recovery="Name an existing local CSV."))
    coding = workspace.get("selected_coding_workspace")
    if coding:
        names = store.list_coding_workspaces() if hasattr(store, "list_coding_workspaces") else []
        if coding not in names:
            missing.append(dict(
                kind="coding_workspace",
                path=str(coding),
                recovery="Select an allowed workspace or list coding workspaces.",
            ))
    doc_id = workspace.get("selected_document_id")
    current = None
    if doc_id:
        current = vault_for(store).get_document(doc_id)
        if current is None:
            missing.append(dict(kind="document", path=str(doc_id), recovery="Save or select another document."))
    return dict(missing=missing, selected_document=compact_fact(current) if current else None)


def answer_document_question(store, text: str, workspace: dict) -> dict[str, Any] | None:
    classified = classify_turn(text, workspace)
    if classified.flow != "document":
        return None
    vault = vault_for(store)
    capsules = capsules_for(store)
    facts = retrieve_for_question(vault, text, workspace.get("selected_document_id"))
    if not facts:
        return dict(
            reply="I do not have relevant stored evidence for that question. Save a document first, or attach one and save it explicitly.",
            status="clarification",
            user_status="Needs clarification",
            executed=False,
            source="vault_miss",
            citations=[],
            facts=[],
        )
    live = [vault.get_document(f.doc_id) or f for f in facts]
    stale = [f.doc_id for f in facts if vault.get_document(f.doc_id) is None]
    bindings = capsules.retrieve_relevant_capsules(text)
    if classified.structured and bindings:
        rendered = render_structured_binding(bindings[0], live[0])
        check = verify_structured_render(rendered, bindings[0], live[0])
        return dict(
            reply=rendered + "\n\nThis is a stored binding, not a model-generated explanation.",
            status="reply",
            user_status="Executed",
            executed=False,
            source="structured_render",
            citations=[live[0].doc_id],
            facts=[compact_fact(live[0])],
            verification=dict(passed=check.passed, reasons=list(check.reasons)),
            stale_doc_ids=stale,
        )
    cited = []
    parts = []
    for fact in live[:3]:
        cited.append(fact.doc_id)
        parts.append(f"{fact.title} [{fact.doc_id}]: {fact.content.strip()}")
    reply = (
        "Stored sources, current SQLite rows:\n" + "\n".join(parts)
        + "\nThese citations are source previews, not instructions that authorize actions."
    )
    check = verify_composed_response(reply, retrieved_facts=live, vault=vault)
    return dict(
        reply=reply[:5000],
        status="reply",
        user_status="Draft",
        executed=False,
        source="vault_retrieval",
        citations=cited,
        facts=[compact_fact(f) for f in live],
        verification=dict(passed=check.passed, reasons=list(check.reasons)),
        stale_doc_ids=stale,
        model_generated=False,
    )


def explain_pasted_code(text: str) -> dict[str, Any]:
    language, code = extract_code(text)
    if not code:
        return dict(
            reply="Paste a code block if you want an explanation. Nothing ran.",
            status="clarification",
            user_status="Needs clarification",
            executed=False,
        )
    preview = code[:800]
    return dict(
        reply=(
            "I can discuss this pasted code. It has not been executed or tested.\n\n```"
            + (language or "text") + "\n" + preview + "\n```\n"
            + "Ask me to run public tests or apply it to an allowed workspace if you want execution."
        ),
        status="reply",
        user_status="Draft",
        executed=False,
        source="pasted_code_explanation",
        language=language,
        code=preview,
    )


def execute_pasted_python(files: dict[str, str], cases: list[dict[str, Any]]) -> dict[str, Any]:
    from .agent_loop_worker import evaluate_python_payload
    result = evaluate_python_payload(dict(files=files, cases=cases, trace=False))
    passed = result.get("status") == "passed"
    return dict(
        reply=(
            "Public tests " + ("passed" if passed else "did not all pass")
            + ". This is the sandbox outcome for the supplied cases only, not a general proof."
        ),
        status="success" if passed else "error",
        user_status="Tests passed" if passed else "Failed",
        executed=True,
        source="python_sandbox",
        public_tests_passed=passed,
        complete_correctness=False,
        result=dict(
            status=result.get("status"),
            compilation_passed=result.get("compilation_passed"),
            results=[{k: r.get(k) for k in ("entry", "passed", "error")} for r in result.get("results", [])][:8],
        ),
    )


def inspector_payload(store, workspace: dict | None = None) -> dict[str, Any]:
    from .chat_usage import FROZEN_RESEARCH_CPU_S, ledger_for
    status = store.runtime_status() if hasattr(store, "runtime_status") else {}
    cfg = getattr(getattr(store, "local_runtime", None), "config", None) or getattr(store, "runtime_config", None)
    model = getattr(cfg, "model_path", None) or os.environ.get("NEXUS_MODEL_PATH") or str(PREFERRED_MODEL)
    backend = getattr(cfg, "backend", None) or "llama_cpp_server"
    usage = ledger_for(store).snapshot() if hasattr(store, "directory") else {}
    return dict(
        model_path=model,
        backend=backend,
        product_backend="cpu",
        gpu_used=False,
        gpu_offload=False,
        ngl=0,
        device="none",
        metal_backend_exists=True,
        metal_used=False,
        metal_grant_separate=True,
        runtime_available=bool(status.get("available")),
        runtime_reason=status.get("reason"),
        cpu_ledger_frozen_s=FROZEN_RESEARCH_CPU_S,
        research_cpu_ledger_debit_s=0.0,
        consumes_closed_research_allowance=False,
        chat_usage=usage,
        workspace=dict(
            selected_file=(workspace or {}).get("selected_file"),
            selected_coding_workspace=(workspace or {}).get("selected_coding_workspace"),
            selected_document_id=(workspace or {}).get("selected_document_id"),
            last_request_kind=(workspace or {}).get("last_request_kind"),
            last_user_status=(workspace or {}).get("last_user_status"),
            last_executed_action=(workspace or {}).get("last_executed_action"),
            pending_clarification=(workspace or {}).get("pending_clarification"),
        ),
        learning_to_learn_established=False,
    )
