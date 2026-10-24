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
