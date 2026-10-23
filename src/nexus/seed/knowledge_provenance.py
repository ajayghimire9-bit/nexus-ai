"""Resolve document conflicts with version, effective date and supersession.

Ingestion timestamp is recorded and is not treated as fact freshness.
A newer row can be an unrelated bulletin. Same-subject conflicts without
a replacement relationship are reported, not silently picked. This adapter
is programmer-supplied. It is not schema learning.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProvenanceRecord:
    doc_id: str
    subject: str
    content: str
    ingested_at: str
    source_version: int | None = None
    effective_date: str | None = None
    supersedes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def records_conflict(left: ProvenanceRecord, right: ProvenanceRecord) -> bool:
    if left.subject != right.subject or left.doc_id == right.doc_id:
        return False
    return (left.content or "").strip() != (right.content or "").strip()


def replacement_of(newer: ProvenanceRecord, older: ProvenanceRecord) -> bool:
    if newer.subject != older.subject:
        return False
    if newer.supersedes == older.doc_id:
        return True
    if (
        newer.source_version is not None
        and older.source_version is not None
        and newer.source_version > older.source_version
        and newer.effective_date
        and older.effective_date
        and newer.effective_date > older.effective_date
    ):
        return True
    return False


def dump_all(rows: list[ProvenanceRecord]) -> dict[str, Any]:
    return dict(
        method="dump_all",
        selected=[row.doc_id for row in rows],
        conflict=False,
        conflict_ids=[],
        dropped=[],
        reason="return_retrieved_rows",
        programmer_supplied=True,
        used_ingestion_timestamp_as_freshness=False,
    )


def timestamp_sort(rows: list[ProvenanceRecord], subject: str | None = None) -> dict[str, Any]:
    scoped = [row for row in rows if subject is None or row.subject == subject] or list(rows)
    ordered = sorted(scoped, key=lambda row: row.ingested_at, reverse=True)
    chosen = ordered[0] if ordered else None
    return dict(
        method="timestamp_sort",
        selected=[chosen.doc_id] if chosen else [],
        conflict=False,
        conflict_ids=[],
        dropped=[row.doc_id for row in ordered[1:]],
        reason="newest_ingestion_timestamp",
        programmer_supplied=True,
        used_ingestion_timestamp_as_freshness=True,
    )


def provenance_resolve(rows: list[ProvenanceRecord], subject: str) -> dict[str, Any]:
    scoped = [row for row in rows if row.subject == subject]
    unrelated = [row.doc_id for row in rows if row.subject != subject]
    if not scoped:
        return dict(
            method="provenance_resolve",
            selected=[],
            conflict=False,
            conflict_ids=[],
            dropped=unrelated,
            reason="no_subject_match",
            programmer_supplied=True,
            used_ingestion_timestamp_as_freshness=False,
        )
    current = list(scoped)
    replaced: list[str] = []
    changed = True
    while changed:
        changed = False
        for left in list(current):
            for right in list(current):
                if left.doc_id == right.doc_id:
                    continue
                if replacement_of(left, right) and right in current:
                    current.remove(right)
                    replaced.append(right.doc_id)
                    changed = True
    conflicts = []
    for index, left in enumerate(current):
        for right in current[index + 1:]:
            if records_conflict(left, right) and not (
                replacement_of(left, right) or replacement_of(right, left)
            ):
                conflicts.extend([left.doc_id, right.doc_id])
    conflicts = sorted(set(conflicts))
    if conflicts:
        return dict(
            method="provenance_resolve",
            selected=[],
            conflict=True,
            conflict_ids=conflicts,
            dropped=replaced + unrelated,
            reason="same_subject_no_replacement",
            programmer_supplied=True,
            used_ingestion_timestamp_as_freshness=False,
        )
    return dict(
        method="provenance_resolve",
        selected=[row.doc_id for row in current],
        conflict=False,
        conflict_ids=[],
        dropped=replaced + unrelated,
        reason="version_effective_date_or_supersession",
        programmer_supplied=True,
        used_ingestion_timestamp_as_freshness=False,
    )


def render_resolution(rows: list[ProvenanceRecord], resolved: dict[str, Any]) -> str:
    by_id = {row.doc_id: row for row in rows}
    if resolved.get("conflict"):
        parts = []
        for doc_id in resolved.get("conflict_ids") or []:
            fact = by_id.get(doc_id)
            if fact:
                parts.append(f"{fact.doc_id}: {fact.content}")
        return (
            "These sources conflict on the same subject and neither supersedes the other: "
            + " | ".join(parts)
        )
    parts = []
    for doc_id in resolved.get("selected") or []:
        fact = by_id.get(doc_id)
        if fact:
            parts.append(f"{fact.content} [{fact.doc_id}]")
    return " ".join(parts) if parts else "No current source for that subject."


def score_knowledge_resolution(task: dict[str, Any], resolved: dict[str, Any],
                               text: str) -> dict[str, Any]:
    selected = list(resolved.get("selected") or [])
    want = set(task.get("must_select") or [])
    forbid = set(task.get("must_not_select") or [])
    select_ok = want <= set(selected) if want else True
    stale_ok = not (set(selected) & forbid)
    conflict_ok = bool(resolved.get("conflict")) == bool(task.get("must_conflict"))
    if task.get("must_conflict"):
        select_ok = selected == []
    fact_ok = True
    if task.get("expected_fact"):
        fact_ok = task["expected_fact"].lower() in (text or "").lower()
    if task.get("forbidden_fact"):
        fact_ok = fact_ok and task["forbidden_fact"].lower() not in (text or "").lower()
    passed = bool(select_ok and stale_ok and conflict_ok and fact_ok)
    return dict(
        passed=passed,
        select_ok=select_ok,
        stale_ok=stale_ok,
        conflict_ok=conflict_ok,
        fact_ok=fact_ok,
        selected=selected,
        conflict=bool(resolved.get("conflict")),
        conflict_ids=list(resolved.get("conflict_ids") or []),
        text=text,
        method=resolved.get("method"),
        used_ingestion_timestamp_as_freshness=bool(
            resolved.get("used_ingestion_timestamp_as_freshness")
        ),
        token_overlap_score=False,
    )
