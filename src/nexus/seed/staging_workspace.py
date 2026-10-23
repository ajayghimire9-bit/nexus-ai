"""Shared staging workspace for coordinated multi-file patches.

Propose a coordinated change, generate bounded edits per file, validate
syntax, update the staged repository, run integration tests, revise from the
actual staged files and failure trace, and publish only after a passing test
receipt matches the exact staged-file hashes.

This does not claim that truncation caused failures. Stop reasons are recorded
from the completion API when available. Per-file apply helpers are not
evidence that a model generated per-file completions.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from typing import Any, Callable

from .local_model_patch_proposer import apply_patch, source_sha256, validate_patch


def files_sha256(files: dict[str, str]) -> dict[str, str]:
    return {path: source_sha256(files[path]) for path in sorted(files)}


def bundle_sha256(files: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(files_sha256(files), sort_keys=True).encode()
    ).hexdigest()


class _StagedFiles(dict):
    """In-place edits invalidate any passing receipt."""

    def __init__(self, owner: "StagingWorkspace", files: dict[str, str]) -> None:
        super().__init__(files)
        self._owner = owner
        self._frozen = False

    def _touch(self) -> None:
        if not self._frozen:
            self._owner._invalidate_receipt()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._touch()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._touch()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._touch()

    def clear(self):
        super().clear()
        self._touch()


class StagingWorkspace:
    """In-memory staged repository. Publish requires a matching passing receipt."""

    def __init__(self, files: dict[str, str]) -> None:
        self.original = dict(files)
        self.history: list[dict[str, Any]] = []
        self.published = False
        self.last_validation: dict[str, Any] | None = None
        self.test_receipt: dict[str, Any] | None = None
        self.staged = _StagedFiles(self, files)

    def _invalidate_receipt(self) -> None:
        self.test_receipt = None
        self.published = False

    def replace_staged(self, files: dict[str, str]) -> None:
        self.staged = _StagedFiles(self, files)
        self._invalidate_receipt()

    def propose_coordinated(self, intent: str, files: list[str] | None = None) -> dict[str, Any]:
        targets = list(files) if files is not None else sorted(self.staged)
        proposal = {
            "intent": intent,
            "files": targets,
            "source_sha256": {path: source_sha256(self.staged[path]) for path in targets if path in self.staged},
        }
        self.history.append({"kind": "propose", **proposal})
        return proposal

    def apply_edits(self, payload: dict[str, Any]) -> dict[str, Any]:
        validated = payload if payload.get("structurally_valid") else validate_patch(payload, dict(self.staged))
        self.replace_staged(apply_patch(dict(self.staged), validated))
        syntax: dict[str, str] = {}
        for edit in validated.get("edits", []):
            path = edit["path"]
            if path.endswith(".py"):
                ast.parse(self.staged[path])
            syntax[path] = "ok"
        note = {"kind": "stage", "files": sorted(syntax), "syntax": syntax, "receipt_invalidated": True}
        self.history.append(note)
        return note

    def apply_per_file(self, edits_by_file: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        applied = []
        for path, edits in sorted(edits_by_file.items()):
            applied.append(self.apply_edits({"edits": edits}))
        return {
            "kind": "per_file_stage",
            "applied": applied,
            "model_generated_per_file": False,
        }

    def validate_syntax(self) -> dict[str, Any]:
        errors: dict[str, str] = {}
        for path, source in self.staged.items():
            if not path.endswith(".py"):
                continue
            try:
                ast.parse(source)
            except SyntaxError as exc:
                errors[path] = str(exc)
        result = {"ok": not errors, "errors": errors}
        self.last_validation = result
        self.history.append({"kind": "syntax", **result})
        return result

    def run_tests(self, runner: Callable[[dict[str, str]], dict[str, Any]]) -> dict[str, Any]:
        snapshot = files_sha256(dict(self.staged))
        result = runner(copy.deepcopy(dict(self.staged)))
        passed = bool(result.get("all_passed"))
        if passed:
            self.test_receipt = {
                "all_passed": True,
                "files_sha256": snapshot,
                "bundle_sha256": bundle_sha256(self.staged),
                "status": result.get("status"),
            }
        else:
            self.test_receipt = None
        self.history.append({
            "kind": "tests",
            "all_passed": passed,
            "status": result.get("status"),
            "receipt_bound": bool(self.test_receipt),
            "files_sha256": snapshot,
        })
        return result

    def receipt_matches(self) -> bool:
        receipt = self.test_receipt
        if not receipt or receipt.get("all_passed") is not True:
            return False
        return receipt.get("files_sha256") == files_sha256(self.staged)

    def revise_from_staged(self, failure_trace: Any, new_files: dict[str, str]) -> None:
        self.history.append({
            "kind": "revise",
            "from_staged_sha": files_sha256(self.staged),
            "failure_trace": failure_trace,
        })
        self.replace_staged(new_files)

    def publish(self) -> dict[str, str]:
        syntax = self.validate_syntax()
        if not syntax["ok"]:
            raise ValueError("cannot_publish_invalid_syntax")
        if not self.receipt_matches():
            raise ValueError("cannot_publish_without_passing_receipt")
        self.published = True
        self.history.append({
            "kind": "publish",
            "files": sorted(self.staged),
            "receipt_bundle_sha256": self.test_receipt["bundle_sha256"],
        })
        return dict(self.staged)


def inspect_completion_stop(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Record stop fields. Do not infer that truncation caused a failed patch."""
    raw = raw or {}
    telemetry = raw.get("telemetry") or {}
    truncated = raw.get("truncated")
    if truncated is None:
        truncated = telemetry.get("truncated")
    stopped_limit = raw.get("stopped_limit")
    if stopped_limit is None:
        stopped_limit = telemetry.get("stopped_limit")
    stop_type = raw.get("stop_type") or telemetry.get("stop_type")
    if stop_type is None:
        if truncated is True or stopped_limit is True:
            stop_type = "length"
        elif raw.get("stopped_eos") or telemetry.get("stopped_eos"):
            stop_type = "eos"
        elif raw.get("stop") is True or telemetry.get("stop") is True:
            stop_type = "stop"
    return {
        "truncated": truncated,
        "stopped_eos": raw.get("stopped_eos", telemetry.get("stopped_eos")),
        "stopped_limit": stopped_limit,
        "stopped_word": raw.get("stopped_word", telemetry.get("stopped_word")),
        "stop_type": stop_type,
        "generated_tokens": telemetry.get("generated_tokens", raw.get("tokens_predicted")),
        "input_tokens": telemetry.get("input_tokens", raw.get("tokens_evaluated")),
        "content_chars": len(raw.get("content") or ""),
        "truncation_claimed_as_cause": False,
    }


def compare_generation_budgets(single: dict[str, Any], per_file: dict[str, Any]) -> dict[str, Any]:
    """Record comparable totals. Do not declare a winner without measurement."""
    return {
        "single_generated_tokens": single.get("generated_tokens"),
        "single_input_tokens": single.get("input_tokens"),
        "single_wall_s": single.get("wall_s"),
        "single_completions": single.get("completions", 1),
        "per_file_generated_tokens": per_file.get("generated_tokens"),
        "per_file_input_tokens": per_file.get("input_tokens"),
        "per_file_wall_s": per_file.get("wall_s"),
        "per_file_completions": per_file.get("completions"),
        "comparable_total_budget": True,
        "winner": None,
        "truncation_claimed_as_cause": False,
        "per_file_means_one_complete_per_file": True,
    }


class CompletionInspector:
    """Wrap PersistentLocalRuntime._http without editing the hashed source file."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.last: dict[str, Any] = {}
        original = getattr(runtime, "_http", None)
        if original is None:
            return

        def wrapped(method, path, payload, timeout):
            raw = original(method, path, payload, timeout)
            if path == "/completion" and isinstance(raw, dict):
                self.last = inspect_completion_stop(raw)
            return raw

        runtime._http = wrapped
