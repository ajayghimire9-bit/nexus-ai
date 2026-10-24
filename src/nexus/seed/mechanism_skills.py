"""Scoped mechanism skills. Independently resettable from policy weights.

Reuses the RepairSchemaStore field pattern (preconditions, evidence,
uncertainty, failures). Not a second capsule store or investigation engine.
Exact cache is OrdinaryExactCache-style signature lookup.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .capability_evidence import digest
from .mechanism_compose import pipe_name, signature
from .mechanism_types import type_tag
from .repair_schema_memory import OrdinaryExactCache


class MechanismSkillStore:
    def __init__(self) -> None:
        self.skills: list[dict[str, Any]] = []
        self.exact = OrdinaryExactCache()
        self.templates: dict[str, list[str]] = {}
        self.hits = 0
        self.misses = 0
        self.retrieval_cost = 0

    def reset(self) -> None:
        self.skills = []
        self.exact = OrdinaryExactCache()
        self.templates = {}
        self.hits = 0
        self.misses = 0
        self.retrieval_cost = 0

    def remember(self, pipeline: tuple[str, ...], transcript: list[dict[str, Any]],
                 *, family: str, uncertainty: str = "scoped") -> dict[str, Any]:
        env = [row for row in transcript if not str(row["action"]).startswith("STOP")]
        sig = signature(pipeline)
        record = dict(
            pipeline=pipe_name(pipeline),
            parts=list(pipeline),
            type_tag=type_tag(pipeline),
            family=family,
            signature=list(sig),
            evidence=[dict(action=row["action"], observation=row.get("observation")) for row in env],
            preconditions=dict(n_evidence=len(env), first_action=env[0]["action"] if env else None),
            uncertainty=uncertainty,
            failures=[],
            skill_id=digest([pipe_name(pipeline), sig]),
        )
        self.skills.append(record)
        evidence = [(row["action"], row.get("observation")) for row in env]
        self.exact.put(digest(evidence), {}, {"pipeline": pipe_name(pipeline)})
        self.templates.setdefault(record["type_tag"], [])
        if record["pipeline"] not in self.templates[record["type_tag"]]:
            self.templates[record["type_tag"]].append(record["pipeline"])
        return record

    def lookup_exact(self, transcript: list[dict[str, Any]]) -> str | None:
        self.retrieval_cost += 1
        evidence = [
            (row["action"], row.get("observation"))
            for row in transcript if not str(row["action"]).startswith("STOP")
        ]
        row = self.exact.get(digest(evidence), {})
        if row:
            self.hits += 1
            return row["pipeline"]
        self.misses += 1
        return None

    def lookup_template(self, type_name: str) -> list[str]:
        self.retrieval_cost += 1
        found = list(self.templates.get(type_name) or [])
        if found:
            self.hits += 1
        else:
            self.misses += 1
        return found

    def lookup_nexus(self, transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.retrieval_cost += 1
        from .mechanism_compose import apply_pipeline
        kept = []
        for skill in self.skills:
            parts = tuple(skill["parts"])
            state = dict(s=0, prev=0)
            ok = True
            for row in transcript:
                if str(row["action"]).startswith("STOP"):
                    continue
                predicted = apply_pipeline(parts, state, row["action"])
                state = predicted["state"]
                if predicted["observation"] is None:
                    continue
                if int(row["observation"]) != int(predicted["observation"]):
                    ok = False
                    break
            if ok:
                kept.append(deepcopy(skill))
        if kept:
            self.hits += 1
        else:
            self.misses += 1
        return kept

    def snapshot(self) -> dict[str, Any]:
        return dict(
            n=len(self.skills),
            skills=deepcopy(self.skills),
            hits=self.hits,
            misses=self.misses,
            retrieval_cost=self.retrieval_cost,
            exact_hits=self.exact.hits,
            exact_misses=self.exact.misses,
        )


class SubMechanismLibrary:
    """Verified guard/transform sub-clauses, not whole-task cache.

    Reuses OrdinaryExactCache for exact whole-mechanism lookup (expected
    miss on unseen compositions) and a signature index for sub-clauses.
    Independently resettable from policy weights.
    """

    def __init__(self) -> None:
        self.clauses: list[dict[str, Any]] = []
        self.by_signature: dict[str, list[dict[str, Any]]] = {}
        self.exact = OrdinaryExactCache()
        self.sub_hits = 0
        self.sub_misses = 0
        self.whole_hits = 0
        self.whole_misses = 0
        self.retrieval_evals = 0
        self.distill_cost = 0

    def reset(self) -> None:
        self.clauses = []
        self.by_signature = {}
        self.exact = OrdinaryExactCache()
        self.sub_hits = 0
        self.sub_misses = 0
        self.whole_hits = 0
        self.whole_misses = 0
        self.retrieval_evals = 0
        self.distill_cost = 0

    def remember_whole(self, mechanism: str, transcript: list[dict[str, Any]]) -> None:
        evidence = [
            (row["action"], row.get("observation"))
            for row in transcript if not str(row["action"]).startswith("STOP")
        ]
        self.exact.put(digest(evidence), {}, {"mechanism": mechanism})

    def remember_subclause(self, record: dict[str, Any]) -> dict[str, Any]:
        stored = dict(record)
        stored.setdefault("skill_id", digest([
            record.get("clause"), record.get("signature"), record.get("source_mechanism"),
        ]))
        stored.setdefault("preconditions", dict(signature=record.get("signature")))
        stored.setdefault("uncertainty", "scoped_subclause")
        stored.setdefault("failures", [])
        self.clauses.append(stored)
        key = str(record["signature"])
        self.by_signature.setdefault(key, []).append(stored)
        return stored

    def lookup_whole(self, transcript: list[dict[str, Any]]) -> str | None:
        self.retrieval_evals += 1
        evidence = [
            (row["action"], row.get("observation"))
            for row in transcript if not str(row["action"]).startswith("STOP")
        ]
        row = self.exact.get(digest(evidence), {})
        if row:
            self.whole_hits += 1
            return row.get("mechanism")
        self.whole_misses += 1
        return None

    def lookup_subclause(self, signature: str) -> list[dict[str, Any]]:
        self.retrieval_evals += 1
        found = list(self.by_signature.get(str(signature)) or [])
        self.retrieval_evals += len(found)
        if found:
            self.sub_hits += 1
        else:
            self.sub_misses += 1
        return deepcopy(found)

    def stored_guards(self) -> list[str]:
        self.retrieval_evals += 1
        return sorted({str(row.get("guard")) for row in self.clauses if row.get("guard")})

    def lookup_guard(self, guard: str) -> list[dict[str, Any]]:
        self.retrieval_evals += 1
        found = [row for row in self.clauses if str(row.get("guard") or "") == str(guard)]
        self.retrieval_evals += len(found)
        if found:
            self.sub_hits += 1
        else:
            self.sub_misses += 1
        return deepcopy(found)

    def snapshot(self) -> dict[str, Any]:
        return dict(
            n_clauses=len(self.clauses),
            clauses=deepcopy(self.clauses),
            signatures=sorted(self.by_signature),
            sub_hits=self.sub_hits,
            sub_misses=self.sub_misses,
            whole_hits=self.whole_hits,
            whole_misses=self.whole_misses,
            retrieval_evals=self.retrieval_evals,
            distill_cost=self.distill_cost,
            exact_hits=self.exact.hits,
            exact_misses=self.exact.misses,
        )
