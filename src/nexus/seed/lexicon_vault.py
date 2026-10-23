"""CPU Knowledge Vault and living lexicon capsules.

Reuses ``digest`` only. Does not replace RepairSchemaStore, stigmergic
coding capsules, or the investigation engines. Does not edit
``local_model_runtime.py``. No neural calls.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .capability_evidence import digest


TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
CITATION = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9_.:-]*)\]")
YEAR_OR_NUMBER = re.compile(r"\b(?:19|20)\d{2}\b|\b\d+(?:\.\d+)?\b")
SENTENCE_END = re.compile(r"[.!?]$")


@dataclass(frozen=True)
class FactSnippet:
    doc_id: str
    title: str
    content: str
    source_hash: str
    timestamp: str
    score: float = 0.0

    def provenance_id(self) -> str:
        return self.doc_id


@dataclass
class LexicalCapsule:
    term: str
    definition: str
    pos_or_frame: str
    required_tokens: tuple[str, ...]
    verified_examples: tuple[str, ...]
    use_count: int = 0
    verified_pass_count: int = 0


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reasons: tuple[str, ...]
    cited_doc_ids: tuple[str, ...]
    targeted_term: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN.finditer(text or "")]


def _fts_query(query: str) -> str:
    parts = [f'"{tok}"' for tok in _tokens(query) if tok not in {"and", "or", "not"}]
    return " AND ".join(parts)


def _require_fts5(conn: sqlite3.Connection) -> None:
    options = {row[0] for row in conn.execute("PRAGMA compile_options")}
    if "ENABLE_FTS5" not in options:
        raise RuntimeError("sqlite_fts5_unavailable")


class KnowledgeVault:
    """On-disk SQLite FTS5 store for documents and conversation facts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        _require_fts5(self.conn)
        self.conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS facts USING fts5("
            "doc_id UNINDEXED, title, content, source_hash UNINDEXED, timestamp UNINDEXED"
            ")"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def ingest_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        *,
        source_hash: str | None = None,
        timestamp: str | None = None,
    ) -> FactSnippet:
        if not doc_id or not (content or "").strip():
            raise ValueError("empty_fact")
        hashed = source_hash or digest({"doc_id": doc_id, "title": title, "content": content})
        stamped = timestamp or _utc_now()
        self.conn.execute("DELETE FROM facts WHERE doc_id = ?", (doc_id,))
        self.conn.execute(
            "INSERT INTO facts(doc_id, title, content, source_hash, timestamp) VALUES (?, ?, ?, ?, ?)",
            (doc_id, title, content, hashed, stamped),
        )
        self.conn.commit()
        return FactSnippet(doc_id, title, content, hashed, stamped)

    def ingest_conversation_fact(self, doc_id: str, title: str, content: str, **kwargs: Any) -> FactSnippet:
        return self.ingest_document(doc_id, title, content, **kwargs)

    def get_document(self, doc_id: str) -> FactSnippet | None:
        """Load one stored fact by id. This is SQLite, not metal_ledger.json."""
        row = self.conn.execute(
            "SELECT doc_id, title, content, source_hash, timestamp FROM facts WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            return None
        return FactSnippet(
            doc_id=row["doc_id"],
            title=row["title"],
            content=row["content"],
            source_hash=row["source_hash"],
            timestamp=row["timestamp"],
        )

    def retrieve_grounded_facts(self, query: str, top_k: int = 3) -> list[FactSnippet]:
        match = _fts_query(query)
        if not match or top_k < 1:
            return []
        rows = self.conn.execute(
            "SELECT doc_id, title, content, source_hash, timestamp, rank "
            "FROM facts WHERE facts MATCH ? ORDER BY rank LIMIT ?",
            (match, int(top_k)),
        ).fetchall()
        return [
            FactSnippet(
                doc_id=row["doc_id"],
                title=row["title"],
                content=row["content"],
                source_hash=row["source_hash"],
                timestamp=row["timestamp"],
                score=float(row["rank"]),
            )
            for row in rows
        ]


class LexicalCapsuleStore:
    """Persistent living lexicon. Not a coding or investigation capsule store."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS capsules ("
            "term TEXT PRIMARY KEY,"
            "definition TEXT NOT NULL,"
            "pos_or_frame TEXT NOT NULL,"
            "required_tokens TEXT NOT NULL,"
            "verified_examples TEXT NOT NULL,"
            "use_count INTEGER NOT NULL,"
            "verified_pass_count INTEGER NOT NULL"
            ")"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _row(self, row: sqlite3.Row) -> LexicalCapsule:
        return LexicalCapsule(
            term=row["term"],
            definition=row["definition"],
            pos_or_frame=row["pos_or_frame"],
            required_tokens=tuple(json.loads(row["required_tokens"])),
            verified_examples=tuple(json.loads(row["verified_examples"])),
            use_count=int(row["use_count"]),
            verified_pass_count=int(row["verified_pass_count"]),
        )

    def ingest_new_term(
        self,
        term: str,
        definition: str,
        pos_or_frame: str,
        required_tokens: Iterable[str] = (),
        verified_examples: Iterable[str] = (),
    ) -> LexicalCapsule:
        cleaned = (term or "").strip()
        if not cleaned or not (definition or "").strip():
            raise ValueError("empty_capsule")
        capsule = LexicalCapsule(
            term=cleaned,
            definition=definition.strip(),
            pos_or_frame=pos_or_frame,
            required_tokens=tuple(tok.lower() for tok in required_tokens),
            verified_examples=tuple(verified_examples),
            use_count=0,
            verified_pass_count=0,
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO capsules VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                capsule.term,
                capsule.definition,
                capsule.pos_or_frame,
                json.dumps(list(capsule.required_tokens)),
                json.dumps(list(capsule.verified_examples)),
                capsule.use_count,
                capsule.verified_pass_count,
            ),
        )
        self.conn.commit()
        return capsule

    def get(self, term: str) -> LexicalCapsule | None:
        row = self.conn.execute("SELECT * FROM capsules WHERE term = ?", (term,)).fetchone()
        return None if row is None else self._row(row)

    def retrieve_relevant_capsules(self, context: str) -> list[LexicalCapsule]:
        tokens = set(_tokens(context))
        found: list[tuple[int, LexicalCapsule]] = []
        for row in self.conn.execute("SELECT * FROM capsules"):
            capsule = self._row(row)
            keys = {capsule.term.lower(), *_tokens(capsule.term), *capsule.required_tokens}
            overlap = len(tokens & keys)
            if overlap or capsule.term.lower() in (context or "").lower():
                self.conn.execute(
                    "UPDATE capsules SET use_count = use_count + 1 WHERE term = ?",
                    (capsule.term,),
                )
                capsule.use_count += 1
                found.append((-overlap, capsule))
        self.conn.commit()
        found.sort(key=lambda item: (item[0], item[1].term))
        return [capsule for _, capsule in found]

    def record_verified_pass(self, term: str) -> None:
        self.conn.execute(
            "UPDATE capsules SET verified_pass_count = verified_pass_count + 1 WHERE term = ?",
            (term,),
        )
        self.conn.commit()


def _complete_sentence(draft: str) -> bool:
    text = (draft or "").strip()
    words = text.split()
    return bool(text) and text[0].isupper() and bool(SENTENCE_END.search(text)) and len(words) >= 4


def _term_in_sentence(draft: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", draft, flags=re.IGNORECASE) is not None


def _definition_copy(draft: str, capsule: LexicalCapsule) -> bool:
    compact = re.sub(r"\s+", " ", draft.strip().lower())
    definition = re.sub(r"\s+", " ", capsule.definition.strip().lower())
    if compact == definition or compact.rstrip(".!?") == definition.rstrip(".!?"):
        return True
    prefix = f"{capsule.term.lower()} is {definition}"
    labeled = f"{capsule.term.lower()}: {definition}"
    return compact.rstrip(".!?") in {prefix.rstrip(".!?"), labeled.rstrip(".!?")}


def _frame_ok(draft: str, capsule: LexicalCapsule) -> bool:
    if not _term_in_sentence(draft, capsule.term):
        return False
    missing = [tok for tok in capsule.required_tokens if tok not in _tokens(draft)]
    if missing:
        return False
    if capsule.pos_or_frame == "verb_transitive":
        match = re.search(rf"\b{re.escape(capsule.term)}\b\s+(\w+)", draft, flags=re.IGNORECASE)
        return bool(match)
    return True


def _snippet_tokens(facts: Iterable[FactSnippet]) -> dict[str, set[str]]:
    return {fact.doc_id: set(_tokens(f"{fact.title} {fact.content}")) for fact in facts}


def _current_facts(facts: list[FactSnippet], vault: KnowledgeVault | None) -> list[FactSnippet]:
    """Replace retrieved rows with the live SQLite version of the same doc_id."""
    if vault is None:
        return facts
    current: list[FactSnippet] = []
    for fact in facts:
        live = vault.get_document(fact.doc_id)
        current.append(live if live is not None else fact)
    return current


def verify_composed_response(
    draft: str,
    *,
    targeted_capsule: LexicalCapsule | None = None,
    retrieved_facts: list[FactSnippet] | None = None,
    store: LexicalCapsuleStore | None = None,
    vault: KnowledgeVault | None = None,
) -> VerificationResult:
    """Deterministic lexical-frame and fact-attribution gate. Target < 1 ms."""
    reasons: list[str] = []
    facts = _current_facts(list(retrieved_facts or []), vault)
    cited = tuple(CITATION.findall(draft or ""))
    if targeted_capsule is not None:
        if not _complete_sentence(draft):
            reasons.append("lexical_frame:incomplete_sentence")
        if not _term_in_sentence(draft, targeted_capsule.term):
            reasons.append("lexical_frame:term_missing")
        if _definition_copy(draft, targeted_capsule):
            reasons.append("lexical_frame:definition_copy")
        if (draft or "").strip().lower().rstrip(".!?") == targeted_capsule.term.lower():
            reasons.append("lexical_frame:bare_fragment")
        if not _frame_ok(draft, targeted_capsule):
            reasons.append("lexical_frame:frame_mismatch")
    by_id = {fact.doc_id: fact for fact in facts}
    token_map = _snippet_tokens(facts)
    stop = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "was"}
    for doc_id in cited:
        if doc_id not in by_id:
            reasons.append(f"fact_attribution:unknown_citation:{doc_id}")
            continue
        overlap = (set(_tokens(draft)) & token_map[doc_id]) - stop
        if not overlap:
            reasons.append(f"fact_attribution:citation_tokens_missing:{doc_id}")
    if facts:
        used = [
            fact.doc_id
            for fact in facts
            if (set(_tokens(draft)) & token_map[fact.doc_id]) - stop - set(_tokens(fact.doc_id))
        ]
        for doc_id in used:
            if doc_id not in cited:
                reasons.append(f"fact_attribution:missing_citation:{doc_id}")
    draft_numbers = set(YEAR_OR_NUMBER.findall(CITATION.sub("", draft or "")))
    grounded_numbers: set[str] = set()
    for fact in facts:
        grounded_numbers.update(YEAR_OR_NUMBER.findall(f"{fact.title} {fact.content}"))
    ungrounded = [num for num in sorted(draft_numbers) if num not in grounded_numbers]
    years = [num for num in ungrounded if re.fullmatch(r"(?:19|20)\d{2}", num)]
    if facts and ungrounded:
        reasons.append("fact_attribution:ungrounded_number:" + ",".join(ungrounded))
    elif years:
        reasons.append("fact_attribution:ungrounded_number:" + ",".join(years))
    passed = not reasons
    if passed and targeted_capsule is not None and store is not None:
        store.record_verified_pass(targeted_capsule.term)
    return VerificationResult(
        passed=passed,
        reasons=tuple(reasons),
        cited_doc_ids=cited,
        targeted_term=None if targeted_capsule is None else targeted_capsule.term,
    )


def render_structured_binding(capsule: LexicalCapsule, fact: FactSnippet) -> str:
    """Deterministic term + current fact + citation. Not model generation."""
    content = (fact.content or "").strip()
    if not capsule.term or not fact.doc_id or not content:
        raise ValueError("structured_render_missing_fields")
    return f"{capsule.term} [{fact.doc_id}]: {content}"


def verify_structured_render(
    text: str,
    capsule: LexicalCapsule,
    fact: FactSnippet,
) -> VerificationResult:
    expected = render_structured_binding(capsule, fact)
    reasons: list[str] = []
    if (text or "").strip() != expected:
        reasons.append("structured_render:not_deterministic")
    if fact.doc_id not in CITATION.findall(text or ""):
        reasons.append("structured_render:citation_missing")
    if capsule.term.lower() not in (text or "").lower():
        reasons.append("structured_render:term_missing")
    if fact.content.strip() not in (text or ""):
        reasons.append("structured_render:stale_or_missing_content")
    return VerificationResult(
        passed=not reasons,
        reasons=tuple(reasons),
        cited_doc_ids=tuple(CITATION.findall(text or "")),
        targeted_term=capsule.term,
    )


def export_lora_sleep_dataset(path: str | Path, triples: Iterable[dict[str, Any]]) -> int:
    """Write only verifier-passing prompt/context/response triples."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", encoding="utf-8") as handle:
        for row in triples:
            if not row.get("passed"):
                continue
            payload = {
                "prompt": row["prompt"],
                "grounded_context": row["grounded_context"],
                "verified_response": row["verified_response"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n")
            written += 1
    return written


def capsule_record(capsule: LexicalCapsule) -> dict[str, Any]:
    return asdict(capsule)
