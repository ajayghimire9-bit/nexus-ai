"""Bottleneck-breaker evaluation for NEXUS Seed across four capability axes:

1. Stop Starving the Proposer (Interface Architecture):
   128-token raw JSON replacement vs 512-token symbol-targeted AST actions
   (`insert_function`, `replace_function`, cross-file symbol routing, and
   execution-trace diagnostic feedback).
2. Separate Pretrained Data/Capacity from Interface Architecture:
   `Qwen2.5-0.5B-Instruct` (469 MB) vs `Qwen2.5-Coder-1.5B-Instruct` (1.0 GB)
   under the exact same symbol-targeted 512-token interface, plus grounded
   workspace conversation with `KnowledgeAndDocRetriever`.
3. Unseen Tasks via Test-Time Compute (`Interpret -> Plan -> Execute -> Inspect -> Revise`):
   Multi-round execution trace inspection (`calls` with per-function locals,
   line numbers, and return values) on unseen repository tasks.
4. Process-Level Learning-to-Learn (`CodingDiagnosticMetaPolicy` with `reset_skills()`):
   Train a diagnostic meta-policy `phi_diag` on disjoint source coding tasks that
   maps public failure trace signatures `psi(T, trace_0)` to repair operator
   families. Clear all cached code patches (`reset_skills()`), and test whether
   retaining `phi_diag` alone solves unseen assessment repositories with fewer
   worker executions than `fixed_default_order`, `diag_policy_reset_control`,
   and `diag_policy_shuffled_control`.
"""
from __future__ import annotations

import ast
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
import random
import tempfile
import time
from typing import Any

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .local_model_patch_proposer import (
    propose_with_runtime,
    top_level_definition_names,
)
from .local_model_runtime import PersistentLocalRuntime, RuntimeConfig, file_hash
from .repair_schema_memory import (
    OrdinaryExactCache,
    RepairSchemaStore,
    transfer_success_rate,
)
from .scoped_id_staging import trace_costs
from .selective_reuse import valid_edit_stats
from .symbiotic_agent_loop import (
    AgentTaskPublicView,
    PythonASTMutationSynthesizer,
    SymbioticAgentLoop,
)
from .workspace_conversation import score_workspace_reply, workspace_context_header


DIAGNOSTIC_SIGNATURE_FEATURES: tuple[str, ...] = (
    "missing_entry_symbol",
    "none_or_empty_error",
    "boundary_equality_mismatch",
    "doc_formula_token",
    "multi_file_call_chain",
    "arithmetic_sign_or_rate_mismatch",
)

OPERATOR_FAMILIES: tuple[str, ...] = (
    "missing_function",
    "null_default",
    "comparison_boundary",
    "documented_api",
    "multi_file",
    "arithmetic_operator",
)


def classify_operator_family(op_name: str) -> str:
    """Map an AST/model candidate operator descriptor to one of the 6 operator families."""
    low = str(op_name or "").lower()
    if "insert_function:" in low or "insert_function" in low:
        return "missing_function"
    if any(tok in low for tok in (
        "or_to_explicit_none", "null_guard", "none_coalesce", "empty_", "default_", "none_guard",
    )):
        return "null_default"
    if any(tok in low for tok in (
        "gt_to_gte", "gt_to_lte", "lt_to_lte", "lt_to_gte",
        "gte_to_gt", "gte_to_lte", "lte_to_lt", "lte_to_gte",
        "cmp_op", "boundary", "inclusive", "exclusive",
    )):
        return "comparison_boundary"
    if any(tok in low for tok in ("bind_doc_", "doc_formula", "doc_const", "grounded_doc")):
        return "documented_api"
    if low.startswith("coord(") or low.startswith("coordinated_multi_file:") or "multi_file" in low:
        return "multi_file"
    return "arithmetic_operator"


def extract_diagnostic_signature(
    task: AgentTaskPublicView,
    current_files: dict[str, str],
    init_eval: dict[str, Any],
) -> dict[str, float]:
    """Extract a 6-dimensional public failure trace signature psi(T, trace_0).

    Uses ONLY public test cases, initial public worker execution trace, docs,
    and repository AST structure. Never accesses private/assessment tests.
    """
    from .local_model_patch_proposer import locate_symbol

    sig = {feat: 0.0 for feat in DIAGNOSTIC_SIGNATURE_FEATURES}
    results = [r for r in (init_eval.get("results") or []) if isinstance(r, dict)]
    failed = [r for r in results if not r.get("passed")]

    entry_nodes: list[ast.AST] = []
    # 1. Missing entry symbol in module AST
    for case in (task.public_tests or [])[:6]:
        entry = str(case.get("entry") or "")
        if "." in entry:
            mod, fn = entry.split(".", 1)
            tfile = f"{mod}.py"
            if tfile in current_files:
                try:
                    present = top_level_definition_names(current_files[tfile])
                    node = locate_symbol(current_files[tfile], fn, "module")
                    if node is not None:
                        entry_nodes.append(node)
                except SyntaxError:
                    present = set()
                if fn not in present:
                    sig["missing_entry_symbol"] = 1.0
    for r in failed:
        if str(r.get("error") or "").startswith("missing_entry:"):
            sig["missing_entry_symbol"] = 1.0

    has_or_fallback_ast = any(
        isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
        for enode in entry_nodes
        for n in ast.walk(enode)
    )
    has_compare_ast = any(
        isinstance(n, ast.Compare)
        for enode in entry_nodes
        for n in ast.walk(enode)
    )

    # 2. None, falsy-zero, or empty input failure
    for r in failed:
        inp = r.get("input")
        err = str(r.get("error") or "")
        has_null_or_falsy = False
        if inp is None or inp == "" or inp == [] or inp == 0:
            has_null_or_falsy = True
        elif isinstance(inp, dict):
            for v in inp.values():
                if v is None or v == "" or v == 0 or (isinstance(v, str) and not v.strip()):
                    has_null_or_falsy = True
        elif isinstance(inp, list):
            if any(v is None or v == "" or v == 0 for v in inp):
                has_null_or_falsy = True
        if (has_null_or_falsy and has_or_fallback_ast) or "NoneType" in err or "AttributeError" in err:
            sig["none_or_empty_error"] = 1.0

    # 3. Comparison boundary mismatch (boolean expected or comparison in entry AST with equal inputs)
    for r in failed:
        inp = r.get("input")
        exp = r.get("expected")
        act = r.get("actual")
        if (isinstance(exp, bool) or isinstance(act, bool)) and has_compare_ast:
            sig["boundary_equality_mismatch"] = 1.0
        elif isinstance(inp, dict) and has_compare_ast and not has_or_fallback_ast:
            nums = [v for v in inp.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) >= 2 and len(set(nums)) < len(nums):
                sig["boundary_equality_mismatch"] = 1.0

    # 4. Documented API / formula token
    if task.docs:
        sig["doc_formula_token"] = 1.0

    # 5. Multi-file call chain in repository / execution trace
    traced_files = {
        str(c.get("file"))
        for r in failed
        for c in (r.get("calls") or [])
        if isinstance(c, dict) and c.get("file")
    }
    if len(current_files) > 1 or len(traced_files) > 1:
        sig["multi_file_call_chain"] = 1.0

    # 6. Arithmetic sign or rate mismatch
    for r in failed:
        exp = r.get("expected")
        act = r.get("actual")
        if (
            isinstance(exp, (int, float))
            and not isinstance(exp, bool)
            and isinstance(act, (int, float))
            and not isinstance(act, bool)
            and sig["missing_entry_symbol"] == 0.0
            and sig["none_or_empty_error"] == 0.0
            and sig["boundary_equality_mismatch"] == 0.0
            and sig["doc_formula_token"] == 0.0
            and sig["multi_file_call_chain"] == 0.0
        ):
            sig["arithmetic_sign_or_rate_mismatch"] = 1.0

    return sig


@dataclass
class CodingDiagnosticMetaPolicy:
    """Process-level diagnostic meta-learner phi_diag over failure trace signatures.

    Learns a linear mapping W from diagnostic trace signature features
    psi(T, trace_0) to repair operator families from public-test verification
    episodes on source tasks. Supports:
    - `reset_learning_strategy()`: zeroes all learned weights (unlearned default order)
    - `shuffle_weights(seed)`: permutes learned family weights per feature
    """
    policy_mode: str = "learned"
    learning_rate: float = 1.0
    weights: dict[str, dict[str, float]] = field(default_factory=lambda: {
        feat: {fam: 0.0 for fam in OPERATOR_FAMILIES}
        for feat in DIAGNOSTIC_SIGNATURE_FEATURES
    })
    episodes_observed: int = 0
    update_history: list[dict[str, Any]] = field(default_factory=list)

    def clone(self, mode: str | None = None) -> "CodingDiagnosticMetaPolicy":
        copied = CodingDiagnosticMetaPolicy(
            policy_mode=mode or self.policy_mode,
            learning_rate=self.learning_rate,
            weights=deepcopy(self.weights),
            episodes_observed=self.episodes_observed,
            update_history=deepcopy(self.update_history),
        )
        return copied

    def reset_learning_strategy(self) -> None:
        """Reset all learned diagnostic weights while keeping candidate pool identical."""
        self.policy_mode = "reset_control"
        self.weights = {
            feat: {fam: 0.0 for fam in OPERATOR_FAMILIES}
            for feat in DIAGNOSTIC_SIGNATURE_FEATURES
        }
        self.episodes_observed = 0

    def shuffle_weights(self, seed: int = 86101) -> None:
        """Deterministically permute operator-family weights to break feature-to-family alignment."""
        self.policy_mode = "shuffled_control"
        rng = random.Random(seed)
        families = list(OPERATOR_FAMILIES)
        for feat in DIAGNOSTIC_SIGNATURE_FEATURES:
            vals = [self.weights[feat][fam] for fam in families]
            # Derangement rotation + seeded shuffle so learned peak moves to a different family
            rotated = vals[2:] + vals[:2]
            rng.shuffle(rotated)
            if rotated == vals and len(rotated) > 1:
                rotated = vals[1:] + vals[:1]
            self.weights[feat] = {fam: rotated[i] for i, fam in enumerate(families)}

    def observe_episode(
        self,
        task_id: str,
        signature: dict[str, float],
        tested_operators: list[str],
        winning_operator: str | None,
        all_pool_operators: list[str] | None = None,
    ) -> None:
        """Update weights from public-test verification outcome on a source training task."""
        if winning_operator is None:
            return
        win_fam = classify_operator_family(winning_operator)
        pool_ops = all_pool_operators if all_pool_operators is not None else tested_operators
        failed_fams = {
            classify_operator_family(op)
            for op in pool_ops
            if op != winning_operator and classify_operator_family(op) != win_fam
        }
        for feat, active in signature.items():
            if active <= 0.0:
                continue
            self.weights[feat][win_fam] = round(
                self.weights[feat][win_fam] + self.learning_rate * active, 6
            )
            for ffam in failed_fams:
                self.weights[feat][ffam] = round(
                    self.weights[feat][ffam] - 0.35 * self.learning_rate * active, 6
                )
        self.episodes_observed += 1
        self.update_history.append({
            "task_id": task_id,
            "active_features": [k for k, v in signature.items() if v > 0],
            "winning_operator": winning_operator,
            "winning_family": win_fam,
            "tested_count": len(tested_operators),
        })

    def score_family(self, family: str, signature: dict[str, float]) -> float:
        if self.policy_mode in ("fixed_default", "reset_control"):
            return 0.0
        total = 0.0
        for feat, val in signature.items():
            if val > 0.0:
                total += val * float(self.weights.get(feat, {}).get(family, 0.0))
        return round(total, 6)

    def propose_and_rank_candidates(
        self,
        task: AgentTaskPublicView,
        current_files: dict[str, str],
        reachable: set[str],
        grounded_bindings: dict[str, Any],
        init_eval: dict[str, Any],
        existing_candidates: list[tuple[str, dict[str, str]]],
    ) -> dict[str, Any]:
        """Rank the exact same candidate pool using the diagnostic meta-policy."""
        sig = extract_diagnostic_signature(task, current_files, init_eval)
        family_scores = {
            fam: self.score_family(fam, sig) for fam in OPERATOR_FAMILIES
        }
        ranked_families = [
            fam for fam, _ in sorted(
                family_scores.items(),
                key=lambda kv: (-kv[1], OPERATOR_FAMILIES.index(kv[0])),
            )
        ]
        if self.policy_mode in ("fixed_default", "reset_control"):
            # Preserve exact default synthesizer order
            ordered = list(existing_candidates)
        else:
            # Stable sort by descending learned family score, preserving within-family order
            indexed = list(enumerate(existing_candidates))
            indexed.sort(
                key=lambda item: (
                    -family_scores.get(classify_operator_family(item[1][0]), 0.0),
                    item[0],
                )
            )
            ordered = [cand for _, cand in indexed]
        return {
            "policy_mode": self.policy_mode,
            "signature": sig,
            "family_scores": family_scores,
            "ranked_families": ranked_families,
            "candidates": ordered,
        }


def _assess_private(meter: EventMeter, scope: str, spec: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    cases = spec.get("assessment") or spec.get("private") or []
    return meter.call(
        scope,
        "assessment_worker",
        spec["id"],
        lambda payload: run_worker_subprocess(payload, 10),
        dict(language=spec.get("language", "python"), files=files, cases=cases),
    )


def _solve_starved_128_task(
    runtime: Any,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Run the 128-token starved baseline (no symbol-level normalization, max_tokens=128)."""
    from .local_model_patch_proposer import (
        PATCH_SCHEMA,
        apply_patch,
        parse_model_patch,
        validate_patch,
    )
    from .staging_workspace import StagingWorkspace, inspect_completion_stop

    started = time.perf_counter()
    current_files = deepcopy(spec["files"])
    task = AgentTaskPublicView(
        task_id=spec["id"],
        cohort="development",
        domain=spec.get("domain", "python_repo"),
        language=spec.get("language", "python"),
        request=spec["request"],
        files=current_files,
        public_tests=spec["public"],
        docs=spec.get("docs", []),
        budget_steps=spec.get("budget_steps", 4),
    )
    init_eval = run_worker_subprocess({
        "language": task.language,
        "files": current_files,
        "cases": task.public_tests,
        "trace": False,
    })
    feedback: dict[str, Any] = {
        "initial_public": {
            "status": init_eval.get("status"),
            "all_passed": init_eval.get("all_passed", False),
            "results": init_eval.get("results", [])[:6],
        }
    }
    model_trace: list[dict[str, Any]] = []
    patch_attempts: list[dict[str, Any]] = []
    final_files = dict(current_files)
    public_passed = False
    outcome = "failed"

    if runtime is None:
        return {
            "task_id": spec["id"],
            "outcome_category": "blocked",
            "public_tests_passed": False,
            "final_files": final_files,
            "model_trace": [{
                "round": 1,
                "status": "BLOCKED",
                "reason": "local_model_unavailable",
                "inference_ran": False,
                "telemetry": {},
                "completion_stop": {"stop_type": "not_run", "truncated": False},
                "max_tokens": 128,
            }],
            "patch_attempts": [],
            "wall_s": round(time.perf_counter() - started, 6),
        }

    for round_idx in range(1, 3):
        # Starved 128-token prompt without trace diagnostics or multi-def normalization
        starved_prompt = (
            "Propose a JSON patch for this local repository. Use only public tests and docs.\n"
            f"Request: {task.request}\n"
            f"Public tests: {json.dumps(task.public_tests)}\n"
            f"Files: {json.dumps(current_files)}\n"
        )
        cfg = getattr(runtime, "config", None)
        prev_max = getattr(cfg, "max_tokens", None) if cfg is not None else None
        try:
            if cfg is not None and prev_max is not None:
                object.__setattr__(cfg, "max_tokens", 128)
            raw = runtime.complete(starved_prompt, PATCH_SCHEMA)
        except Exception as exc:
            model_trace.append({
                "round": round_idx,
                "status": "BLOCKED",
                "reason": f"{type(exc).__name__}: {exc}",
                "inference_ran": False,
                "telemetry": {},
                "completion_stop": {"stop_type": "error", "truncated": False},
                "max_tokens": 128,
            })
            break
        finally:
            if cfg is not None and prev_max is not None:
                object.__setattr__(cfg, "max_tokens", prev_max)

        stop = inspect_completion_stop(raw)
        tel = dict(raw.get("telemetry") or {})
        tel["completion_stop"] = stop
        try:
            parsed = parse_model_patch(raw.get("content", ""))
            # In starved mode, validate raw model edits directly without symbol-splitting/cross-file routing
            edits = []
            for raw_edit in parsed["edits"]:
                path = str(raw_edit.get("path", "")).strip()
                action = str(raw_edit.get("action") or "replace")
                new_text = str(raw_edit.get("new_text") or "")
                old_text = str(raw_edit.get("old_text") or "")
                symbol = raw_edit.get("symbol")
                if path not in current_files:
                    raise ValueError(f"missing_target_file:{path}")
                if action == "replace" and old_text and current_files[path].count(old_text) != 1:
                    raise ValueError(f"old_text_not_unique:{path}")
                if action in ("insert_function", "insert_after_symbol") and symbol:
                    if f"def {symbol}(" in current_files[path]:
                        raise ValueError(f"duplicate_definition:{symbol}")
                edits.append({
                    "path": path,
                    "action": action if action in ("replace", "create", "insert_function", "insert_after_symbol") else "replace",
                    "old_text": old_text,
                    "new_text": new_text,
                    "symbol": symbol,
                    "scope": raw_edit.get("scope") or "module",
                    "source_sha256": None,
                })
            validated = validate_patch({"edits": edits, "assumptions": []}, current_files)
            patched = apply_patch(current_files, validated)
        except Exception as exc:
            model_trace.append({
                "round": round_idx,
                "status": "invalid_proposal",
                "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                "inference_ran": bool(tel.get("inference_ran")),
                "telemetry": tel,
                "completion_stop": stop,
                "max_tokens": 128,
            })
            feedback["validation_error"] = str(exc)[:200]
            continue

        model_trace.append({
            "round": round_idx,
            "status": "proposed",
            "reason": None,
            "inference_ran": bool(tel.get("inference_ran")),
            "telemetry": tel,
            "completion_stop": stop,
            "max_tokens": 128,
        })
        staging = StagingWorkspace(current_files)
        staging.propose_coordinated(f"starved_128_round_{round_idx}", sorted(patched))
        staging.replace_staged(patched)
        syntax = staging.validate_syntax()
        if not syntax["ok"]:
            patch_attempts.append({
                "attempt_index": len(patch_attempts) + 1,
                "operator_name": f"starved_128_round_{round_idx}",
                "public_passed": False,
                "worker_status": "syntax_error",
            })
            continue
        ev = staging.run_tests(lambda files: run_worker_subprocess({
            "language": task.language,
            "files": files,
            "cases": task.public_tests,
            "trace": False,
        }))
        all_ok = bool(ev.get("all_passed", False))
        patch_attempts.append({
            "attempt_index": len(patch_attempts) + 1,
            "operator_name": f"starved_128_round_{round_idx}",
            "public_passed": all_ok,
            "worker_status": ev.get("status", "failed"),
        })
        if all_ok:
            final_files = staging.publish()
            public_passed = True
            outcome = "solved"
            break

    return {
        "task_id": spec["id"],
        "outcome_category": outcome,
        "public_tests_passed": public_passed,
        "final_files": final_files,
        "model_trace": model_trace,
        "patch_attempts": patch_attempts,
        "wall_s": round(time.perf_counter() - started, 6),
    }


def _open_model_runtime(model_spec: dict[str, Any]) -> PersistentLocalRuntime | None:
    model_path = Path(model_spec["model_path"]).expanduser()
    if not model_path.is_file():
        fallback = Path(".models") / model_path.name
        if fallback.is_file():
            model_path = fallback.resolve()
        else:
            return None
    rc = RuntimeConfig(
        model_path=str(model_path.resolve()),
        threads=int(model_spec.get("threads", 4)),
        request_timeout_s=float(model_spec.get("request_timeout_s", 60.0)),
        startup_timeout_s=float(model_spec.get("startup_timeout_s", 30.0)),
        max_tokens=int(model_spec.get("max_tokens", 512)),
    )
    rt = PersistentLocalRuntime(rc)
    rt.start()
    return rt


def run_proposer_and_capacity_ablation(
    config: dict[str, Any],
    emit,
    meter: EventMeter,
    runtimes: dict[str, PersistentLocalRuntime | None],
) -> None:
    """Part 1 & 2: Compare 0.5B Starved (128 tok) vs 0.5B Symbol (512 tok) vs 1.5B-Coder Symbol (512 tok) vs 1.5B-Coder + Closed-Loop AST."""
    for cond in config["proposer_conditions"]:
        cond_id = cond["id"]
        model_key = cond["model_key"]
        max_tok = int(cond["max_tokens"])
        mode = cond["interface_mode"]
        rt = runtimes.get(model_key)

        for spec in config["coding_tasks"]:
            scope = f"coding_ablation:{cond_id}:{spec['id']}"
            if mode == "starved_128":
                res = meter.call(
                    scope, "agent_loop", spec["id"],
                    lambda s: _solve_starved_128_task(rt, s),
                    spec,
                )
            else:
                proposal_sources = tuple(cond.get("proposal_sources") or ["local_model", "local_model_per_file"])

                def _run_symbol(s: dict[str, Any]) -> dict[str, Any]:
                    with tempfile.TemporaryDirectory() as tmp:
                        loop = SymbioticAgentLoop(
                            workspace_dir=Path(tmp),
                            proposal_sources=proposal_sources,
                            local_runtime=rt,
                            model_revision_budget=int(cond.get("revision_budget", 2)),
                            proposer_max_tokens=max_tok,
                            allow_acquired_memory=False,
                        )
                        return loop.solve(AgentTaskPublicView(
                            task_id=s["id"],
                            cohort="development",
                            domain=s.get("domain", "python_repo"),
                            language=s.get("language", "python"),
                            request=s["request"],
                            files=deepcopy(s["files"]),
                            public_tests=s["public"],
                            docs=s.get("docs", []),
                            budget_steps=int(s.get("budget_steps", 6)),
                        ))

                res = meter.call(scope, "agent_loop", spec["id"], _run_symbol, spec)

            private = _assess_private(
                meter,
                f"coding_ablation_assess:{cond_id}:{spec['id']}",
                spec,
                res.get("final_files") or spec["files"],
            )
            stats = valid_edit_stats(res.get("model_trace") or [])
            costs = trace_costs(res)
            emit({
                "kind": "capability",
                "area": "coding_bottleneck_ablation",
                "category": "coding_ablation",
                "condition": cond_id,
                "model_key": model_key,
                "max_tokens": max_tok,
                "interface_mode": mode,
                "id": spec["id"],
                "family": spec["family"],
                "outcome": res.get("outcome_category"),
                "public_passed": bool(res.get("public_tests_passed")),
                "private": private,
                "private_passed": bool(private.get("all_passed")),
                "edit_stats": stats,
                "model_trace": res.get("model_trace", []),
                "applied_operator": res.get("applied_operator"),
                "complete_correctness": False,
                **costs,
            })


def run_unseen_test_time_compute(
    config: dict[str, Any],
    emit,
    meter: EventMeter,
    runtimes: dict[str, PersistentLocalRuntime | None],
) -> None:
    """Part 3: Unseen multi-step & algorithmic tasks solved via Interpret -> Plan -> Execute -> Inspect -> Revise."""
    rt = runtimes.get("qwen_1_5b_coder") or runtimes.get("qwen_0_5b")
    for spec in config["unseen_reasoning_tasks"]:
        scope = f"unseen_ttc:{spec['id']}"
        init_trace = meter.call(
            f"{scope}:initial_trace",
            "worker_trace",
            spec["id"],
            lambda payload: run_worker_subprocess(payload, 10),
            dict(
                language=spec.get("language", "python"),
                files=deepcopy(spec["files"]),
                cases=spec["public"],
                trace=True,
            ),
        )

        def _solve_unseen(s: dict[str, Any]) -> dict[str, Any]:
            with tempfile.TemporaryDirectory() as tmp:
                loop = SymbioticAgentLoop(
                    workspace_dir=Path(tmp),
                    proposal_sources=("local_model", "local_model_per_file", "ast"),
                    local_runtime=rt,
                    model_revision_budget=2,
                    proposer_max_tokens=512,
                    allow_acquired_memory=False,
                )
                return loop.solve(AgentTaskPublicView(
                    task_id=s["id"],
                    cohort="development",
                    domain=s.get("domain", "python_repo"),
                    language=s.get("language", "python"),
                    request=s["request"],
                    files=deepcopy(s["files"]),
                    public_tests=s["public"],
                    docs=s.get("docs", []),
                    budget_steps=int(s.get("budget_steps", 8)),
                ))

        res = meter.call(scope, "agent_loop", spec["id"], _solve_unseen, spec)
        private = _assess_private(
            meter,
            f"{scope}:assess",
            spec,
            res.get("final_files") or spec["files"],
        )
        traced_calls = sum(
            len(r.get("calls") or [])
            for r in (init_trace.get("results") or [])
            if isinstance(r, dict)
        )
        emit({
            "kind": "capability",
            "area": "unseen_test_time_compute",
            "category": "unseen_ttc",
            "id": spec["id"],
            "family": spec["family"],
            "outcome": res.get("outcome_category"),
            "public_passed": bool(res.get("public_tests_passed")),
            "private": private,
            "private_passed": bool(private.get("all_passed")),
            "initial_traced_call_events": traced_calls,
            "patch_attempts_count": len(res.get("patch_attempts") or []),
            "applied_operator": res.get("applied_operator"),
            "complete_correctness": False,
            **trace_costs(res),
        })


def run_grounded_conversation(
    config: dict[str, Any],
    emit,
    meter: EventMeter,
    runtimes: dict[str, PersistentLocalRuntime | None],
) -> None:
    """Part 2b: Open-ended and document-grounded conversation evaluation."""
    from .conversation_capability import send
    from .lab import SeedWorkspace

    rt = runtimes.get("qwen_1_5b_coder") or runtimes.get("qwen_0_5b")
    with tempfile.TemporaryDirectory() as tmp:
        ws = SeedWorkspace(Path(tmp) / "chat", local_runtime=rt, attach_local_runtime=False)
        ws.knowledge_docs = deepcopy(config.get("knowledge_docs") or [])
        sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
        for spec in config["conversation_turns"]:
            result = meter.call(
                f"chat:{spec['id']}",
                "chat",
                spec["id"],
                lambda text: send(ws, sid, text),
                spec["text"],
            )
            follow = None
            if spec.get("follow_up"):
                follow = meter.call(
                    f"chat:{spec['id']}:follow",
                    "chat",
                    spec["id"],
                    lambda text: send(ws, sid, text),
                    spec["follow_up"],
                )
            ctx = result["chat"]["context"]["workspace"]
            header, meta = workspace_context_header(ws, ctx)
            reply_text = str(result.get("text") or "")
            scored = score_workspace_reply(reply_text, ctx, meta)
            cards_list = (result["chat"]["messages"][-1].get("cards") or []) if result["chat"].get("messages") else []
            grounded_docs = []
            for c in cards_list:
                if isinstance(c, dict) and isinstance(c.get("data"), dict):
                    if c["data"].get("grounded_docs"):
                        grounded_docs.extend(c["data"]["grounded_docs"])
            expected_tokens = [str(t).lower() for t in (spec.get("expected_any_substrings") or [])]
            rubric_met = True
            if expected_tokens:
                combined_low = (reply_text + " " + ( str(follow.get("text") or "") if isinstance(follow, dict) else "" )).lower()
                rubric_met = any(tok in combined_low for tok in expected_tokens)
            emit({
                "kind": "capability",
                "area": "language",
                "category": "language",
                "id": spec["id"],
                "conversation_kind": spec["kind"],
                "rubric": spec["rubric"],
                "rubric_met": rubric_met,
                "grounded_docs": grounded_docs,
                "workspace_score": scored,
                "header_input_token_estimate": meta["input_token_estimate"],
                "response_excerpt": reply_text[:400],
            })


def _execute_diagnostic_episode(
    meter: EventMeter,
    scope_prefix: str,
    spec: dict[str, Any],
    policy: CodingDiagnosticMetaPolicy,
    repair_store: RepairSchemaStore | None,
    exact_cache: OrdinaryExactCache | None,
    allow_memory: bool,
) -> dict[str, Any]:
    """Run one repository repair episode under the given diagnostic policy and memory setting,
    metering every worker execution (`candidate_eval` and `initial_trace`).
    """
    from .repair_schema_memory import capture_from_success, infer_family, propose_retrieved_repair
    from .staging_workspace import StagingWorkspace

    started = time.perf_counter()
    current_files = deepcopy(spec["files"])
    task = AgentTaskPublicView(
        task_id=spec["id"],
        cohort=spec.get("cohort", "assessment"),
        domain=spec.get("domain", "python_repo"),
        language=spec.get("language", "python"),
        request=spec["request"],
        files=current_files,
        public_tests=spec["public"],
        docs=spec.get("docs", []),
        budget_steps=int(spec.get("budget_steps", 12)),
    )
    init_eval = meter.call(
        f"{scope_prefix}:init",
        "worker_eval",
        spec["id"],
        lambda payload: run_worker_subprocess(payload, 10),
        dict(language=task.language, files=current_files, cases=task.public_tests, trace=True),
    )
    reachable: set[str] = set()
    grounded: dict[str, Any] = {}
    for d in task.docs or []:
        if isinstance(d, dict):
            grounded.update(d.get("grounded_bindings") or {})
            doc_text = str(d.get("content") or d.get("text") or "")
            import re as _re
            for m_bind in _re.finditer(r"\b([A-Z][A-Z0-9_]{2,})\s*=\s*(-?\d+(?:\.\d+)?)\b", doc_text):
                raw_num = m_bind.group(2)
                grounded.setdefault(
                    m_bind.group(1),
                    float(raw_num) if "." in raw_num else int(raw_num),
                )

    raw_candidates = PythonASTMutationSynthesizer.generate_candidates(
        current_files, reachable, task.request, grounded
    )
    diag_out = policy.propose_and_rank_candidates(
        task=task,
        current_files=current_files,
        reachable=reachable,
        grounded_bindings=grounded,
        init_eval=init_eval,
        existing_candidates=raw_candidates,
    )
    queue: list[tuple[str, dict[str, str]]] = list(diag_out["candidates"])

    reused_memory = False
    cache_hit = False
    if allow_memory and exact_cache is not None:
        cached_files = exact_cache.get(task.request, current_files)
        if cached_files is not None:
            queue.insert(0, ("exact_cache_hit", cached_files))
            cache_hit = True
    if allow_memory and repair_store is not None:
        family = infer_family(task.request, task.public_tests)
        if family:
            schema = repair_store.lookup(family, task.request)
            if schema is None:
                for stored in repair_store.schemas.values():
                    if stored.family == family and stored.transformation != "none":
                        schema = stored
                        break
            if schema is not None:
                proposal = propose_retrieved_repair(
                    schema, task.request, current_files, task.public_tests
                )
                if proposal.decision == "apply" and proposal.files is not None:
                    queue.insert(0, (f"repair_schema:{schema.schema_id}", proposal.files))
                    reused_memory = True

    tested_operators: list[str] = []
    winning_operator: str | None = None
    published_files = dict(current_files)
    public_passed = False
    worker_evals = 0
    max_attempts = max(1, int(spec.get("budget_steps", 12)))

    for idx, (op_desc, cand_files) in enumerate(queue[:max_attempts], start=1):
        staging = StagingWorkspace(current_files)
        staging.propose_coordinated(op_desc, sorted(set(cand_files) | set(current_files)))
        staging.replace_staged(cand_files)
        syntax = staging.validate_syntax()
        if not syntax["ok"]:
            continue
        tested_operators.append(op_desc)
        worker_evals += 1
        ev = staging.run_tests(
            lambda staged_files: meter.call(
                f"{scope_prefix}:cand:{idx}",
                "worker_eval",
                spec["id"],
                lambda payload: run_worker_subprocess(payload, 10),
                dict(language=task.language, files=staged_files, cases=task.public_tests, trace=False),
            )
        )
        if ev.get("all_passed"):
            published_files = staging.publish()
            public_passed = True
            winning_operator = op_desc
            if allow_memory and repair_store is not None:
                fam = infer_family(task.request, task.public_tests)
                if fam:
                    captured = capture_from_success(
                        fam, task.request, current_files, published_files, task.public_tests,
                        {"attempt": idx},
                    )
                    if captured is not None:
                        repair_store.remember(captured)
            if allow_memory and exact_cache is not None:
                exact_cache.put(task.request, current_files, published_files)
            break

    private = _assess_private(meter, f"{scope_prefix}:assess", spec, published_files)
    return {
        "task_id": spec["id"],
        "family": spec["family"],
        "policy_mode": policy.policy_mode,
        "signature": diag_out["signature"],
        "ranked_families": diag_out["ranked_families"],
        "candidate_pool_size": len(raw_candidates),
        "all_pool_operators": [op for op, _ in raw_candidates],
        "worker_evaluations": worker_evals,
        "tested_operators": tested_operators,
        "winning_operator": winning_operator,
        "public_passed": public_passed,
        "private": private,
        "private_passed": bool(private.get("all_passed")),
        "reused_memory": reused_memory,
        "cache_hit": cache_hit,
        "store_schemas_count": len(repair_store.schemas) if repair_store is not None else 0,
        "wall_s": round(time.perf_counter() - started, 6),
    }


def run_diagnostic_meta_learning(
    config: dict[str, Any],
    emit,
    meter: EventMeter,
) -> dict[str, Any]:
    """Part 4: Train CodingDiagnosticMetaPolicy phi_diag on disjoint source coding tasks,
    then evaluate on unseen assessment tasks under strict reset_skills() separation.
    """
    trained_policy = CodingDiagnosticMetaPolicy(policy_mode="learned", learning_rate=1.0)
    training_store = RepairSchemaStore()
    training_cache = OrdinaryExactCache()

    # Phase 1: Train phi_diag on disjoint source coding tasks (never touching assessment tasks)
    for src_spec in config["meta_learning"]["source_tasks"]:
        ep = _execute_diagnostic_episode(
            meter=meter,
            scope_prefix=f"meta_train:{src_spec['id']}",
            spec=src_spec,
            policy=trained_policy,
            repair_store=training_store,
            exact_cache=training_cache,
            allow_memory=True,
        )
        trained_policy.observe_episode(
            task_id=src_spec["id"],
            signature=ep["signature"],
            tested_operators=ep["tested_operators"],
            winning_operator=ep["winning_operator"],
            all_pool_operators=ep["all_pool_operators"],
        )
        emit({
            "kind": "meta_train_episode",
            "id": src_spec["id"],
            "family": src_spec["family"],
            "worker_evaluations": ep["worker_evaluations"],
            "winning_operator": ep["winning_operator"],
            "private_passed": ep["private_passed"],
        })

    learned_weights_snapshot = deepcopy(trained_policy.weights)
    emit({
        "kind": "diagnostic_meta_policy_snapshot",
        "episodes_observed": trained_policy.episodes_observed,
        "weights": learned_weights_snapshot,
        "update_history": deepcopy(trained_policy.update_history),
    })

    # Phase 2: Evaluate on unseen assessment tasks across 5 falsifiable conditions
    conditions = (
        "fixed_default_order",
        "learned_diag_policy_capsules_cleared",
        "learned_diag_policy_plus_repair_memory",
        "diag_policy_reset_control",
        "diag_policy_shuffled_control",
    )

    for cond in conditions:
        if cond == "fixed_default_order":
            pol = CodingDiagnosticMetaPolicy(policy_mode="fixed_default")
            store = RepairSchemaStore()
            cache = OrdinaryExactCache()
            allow_mem = False
        elif cond == "learned_diag_policy_capsules_cleared":
            # reset_skills(): clear all cached patches and repair schemas, keep ONLY phi_diag
            pol = trained_policy.clone(mode="learned")
            store = RepairSchemaStore()  # explicitly empty!
            cache = OrdinaryExactCache()  # explicitly empty!
            allow_mem = False
        elif cond == "learned_diag_policy_plus_repair_memory":
            pol = trained_policy.clone(mode="learned")
            store = deepcopy(training_store)
            cache = deepcopy(training_cache)
            allow_mem = True
        elif cond == "diag_policy_reset_control":
            pol = trained_policy.clone(mode="learned")
            pol.reset_learning_strategy()
            store = RepairSchemaStore()
            cache = OrdinaryExactCache()
            allow_mem = False
        elif cond == "diag_policy_shuffled_control":
            pol = trained_policy.clone(mode="learned")
            pol.shuffle_weights(seed=int(config["meta_learning"].get("shuffle_seed", 86101)))
            store = RepairSchemaStore()
            cache = OrdinaryExactCache()
            allow_mem = False
        else:
            raise ValueError(f"unknown meta_learning condition: {cond}")

        for assess_spec in config["meta_learning"]["assessment_tasks"]:
            ep = _execute_diagnostic_episode(
                meter=meter,
                scope_prefix=f"meta_eval:{cond}:{assess_spec['id']}",
                spec=assess_spec,
                policy=pol,
                repair_store=store,
                exact_cache=cache,
                allow_memory=allow_mem,
            )
            emit({
                "kind": "meta_eval_episode",
                "condition": cond,
                "id": assess_spec["id"],
                "family": assess_spec["family"],
                "policy_mode": ep["policy_mode"],
                "ranked_families": ep["ranked_families"],
                "candidate_pool_size": ep["candidate_pool_size"],
                "worker_evaluations": ep["worker_evaluations"],
                "winning_operator": ep["winning_operator"],
                "public_passed": ep["public_passed"],
                "private": ep["private"],
                "private_passed": ep["private_passed"],
                "reused_memory": ep["reused_memory"],
                "cache_hit": ep["cache_hit"],
                "store_schemas_count": ep["store_schemas_count"],
                "capsules_cleared": not allow_mem,
                "wall_s": ep["wall_s"],
            })

    return {
        "episodes_observed": trained_policy.episodes_observed,
        "weights": learned_weights_snapshot,
    }


def run(config: dict[str, Any], emit, live_mode: bool = False) -> EventMeter:
    meter = EventMeter(emit)
    runtimes: dict[str, PersistentLocalRuntime | None] = {
        "qwen_0_5b": None,
        "qwen_1_5b_coder": None,
    }
    model_Swap_info: dict[str, Any] = {}
    try:
        if live_mode:
            for key, mspec in (config.get("models") or {}).items():
                rt = _open_model_runtime(mspec)
                runtimes[key] = rt
                mpath = Path(mspec["model_path"]).expanduser()
                if not mpath.is_file() and (Path(".models") / mpath.name).is_file():
                    mpath = (Path(".models") / mpath.name).resolve()
                model_Swap_info[key] = {
                    "available": rt is not None,
                    "model_path": str(mpath),
                    "sha256": file_hash(mpath) if mpath.is_file() else None,
                    "parameters_label": mspec.get("parameters_label"),
                }
        else:
            for key, mspec in (config.get("models") or {}).items():
                model_Swap_info[key] = {
                    "available": False,
                    "model_path": mspec.get("model_path"),
                    "sha256": mspec.get("sha256"),
                    "parameters_label": mspec.get("parameters_label"),
                }

        emit({
            "kind": "audit_manifest",
            "config_hash": digest(config),
            "live_mode": bool(live_mode),
            "models": model_Swap_info,
            "gemini": config.get("gemini", "NOT_RUN"),
            "result_label": "authored_source_development_pilot_not_confirmation",
            "separate_improvements": [
                "proposer_interface_512_symbol_ast",
                "pretrained_coder_1_5b_capacity",
                "test_time_compute_trace_revision",
                "diagnostic_meta_policy_phi_diag_after_capsule_reset",
            ],
        })

        run_proposer_and_capacity_ablation(config, emit, meter, runtimes)
        run_unseen_test_time_compute(config, emit, meter, runtimes)
        run_grounded_conversation(config, emit, meter, runtimes)
        run_diagnostic_meta_learning(config, emit, meter)
    finally:
        for rt in runtimes.values():
            if rt is not None:
                rt.close()
    return meter


def summarize(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    ablation_rows = [r for r in records if r.get("category") == "coding_ablation"]
    ttc_rows = [r for r in records if r.get("category") == "unseen_ttc"]
    lang_rows = [r for r in records if r.get("category") == "language"]
    meta_train = [r for r in records if r.get("kind") == "meta_train_episode"]
    meta_eval = [r for r in records if r.get("kind") == "meta_eval_episode"]

    by_condition: dict[str, Any] = {}
    for cond in config["proposer_conditions"]:
        cid = cond["id"]
        rows = [r for r in ablation_rows if r.get("condition") == cid]
        proposals = sum(int((r.get("edit_stats") or {}).get("proposals") or 0) for r in rows)
        valid = sum(int((r.get("edit_stats") or {}).get("structurally_valid") or 0) for r in rows)
        pub_pass = sum(1 for r in rows if r.get("public_passed"))
        priv_pass = sum(1 for r in rows if r.get("private_passed"))
        by_condition[cid] = {
            "n": len(rows),
            "proposals": proposals,
            "structurally_valid": valid,
            "valid_edit_rate": (valid / proposals) if proposals else 0.0,
            "public_pass": pub_pass,
            "private_pass": priv_pass,
            "private_pass_rate": (priv_pass / len(rows)) if rows else 0.0,
            "completions": sum(int(r.get("completions") or 0) for r in rows),
            "input_tokens": sum(int(r.get("input_tokens") or 0) for r in rows),
            "generated_tokens": sum(int(r.get("generated_tokens") or 0) for r in rows),
            "request_wall_s": round(sum(float(r.get("request_wall_s") or 0.0) for r in rows), 6),
        }

    ttc_summary = {
        "n": len(ttc_rows),
        "public_pass": sum(1 for r in ttc_rows if r.get("public_passed")),
        "private_pass": sum(1 for r in ttc_rows if r.get("private_passed")),
        "total_traced_call_events": sum(int(r.get("initial_traced_call_events") or 0) for r in ttc_rows),
        "tasks": [
            {
                "id": r["id"],
                "family": r.get("family"),
                "outcome": r.get("outcome"),
                "public_passed": r.get("public_passed"),
                "private_passed": r.get("private_passed"),
                "applied_operator": r.get("applied_operator"),
            }
            for r in ttc_rows
        ],
    }

    lang_summary = {
        "n": len(lang_rows),
        "rubric_met_count": sum(1 for r in lang_rows if r.get("rubric_met")),
        "grounded_doc_turns": sum(1 for r in lang_rows if r.get("grounded_docs")),
        "turns": [
            {
                "id": r["id"],
                "kind": r.get("conversation_kind"),
                "rubric_met": r.get("rubric_met"),
                "grounded_docs": r.get("grounded_docs"),
            }
            for r in lang_rows
        ],
    }

    def _pack_meta(cond_name: str) -> dict[str, Any]:
        rows = [r for r in meta_eval if r.get("condition") == cond_name]
        return {
            "n": len(rows),
            "public_solved": sum(1 for r in rows if r.get("public_passed")),
            "private_solved": sum(1 for r in rows if r.get("private_passed")),
            "worker_evaluations": sum(int(r.get("worker_evaluations") or 0) for r in rows),
            "reused_memory_count": sum(1 for r in rows if r.get("reused_memory")),
            "cache_hits": sum(1 for r in rows if r.get("cache_hit")),
            "capsules_cleared": all(bool(r.get("capsules_cleared")) for r in rows) if rows else False,
        }

    fixed_pack = _pack_meta("fixed_default_order")
    cleared_pack = _pack_meta("learned_diag_policy_capsules_cleared")
    memory_pack = _pack_meta("learned_diag_policy_plus_repair_memory")
    reset_pack = _pack_meta("diag_policy_reset_control")
    shuffled_pack = _pack_meta("diag_policy_shuffled_control")

    advantage_vs_fixed = (
        cleared_pack["private_solved"] >= fixed_pack["private_solved"]
        and cleared_pack["worker_evaluations"] < fixed_pack["worker_evaluations"]
        if cleared_pack["n"] and fixed_pack["n"] else False
    )
    remains_after_capsule_reset = (
        cleared_pack["capsules_cleared"] is True
        and cleared_pack["reused_memory_count"] == 0
        and cleared_pack["cache_hits"] == 0
        and cleared_pack["worker_evaluations"] < fixed_pack["worker_evaluations"]
        if cleared_pack["n"] and fixed_pack["n"] else False
    )
    disappears_when_reset = (
        reset_pack["worker_evaluations"] > cleared_pack["worker_evaluations"]
        and reset_pack["worker_evaluations"] == fixed_pack["worker_evaluations"]
        if reset_pack["n"] and cleared_pack["n"] else False
    )
    disappears_when_shuffled = (
        shuffled_pack["worker_evaluations"] > cleared_pack["worker_evaluations"]
        if shuffled_pack["n"] and cleared_pack["n"] else False
    )
    meta_established = bool(
        advantage_vs_fixed
        and remains_after_capsule_reset
        and disappears_when_reset
        and disappears_when_shuffled
    )

    model_rows = ablation_rows + ttc_rows
    reconstructed_costs = {
        "completions": sum(int(r.get("completions") or 0) for r in model_rows),
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in model_rows),
        "generated_tokens": sum(int(r.get("generated_tokens") or 0) for r in model_rows),
        "request_wall_s": round(sum(float(r.get("request_wall_s") or 0.0) for r in model_rows), 6),
    }

    return {
        "proposer_and_capacity_ablation": by_condition,
        "unseen_test_time_compute": ttc_summary,
        "grounded_conversation": lang_summary,
        "diagnostic_meta_learning": {
            "source_training_episodes": len(meta_train),
            "fixed_default_order": fixed_pack,
            "learned_diag_policy_capsules_cleared": cleared_pack,
            "learned_diag_policy_plus_repair_memory": memory_pack,
            "diag_policy_reset_control": reset_pack,
            "diag_policy_shuffled_control": shuffled_pack,
            "advantage_vs_fixed": advantage_vs_fixed,
            "remains_after_capsule_reset": remains_after_capsule_reset,
            "disappears_when_reset": disappears_when_reset,
            "disappears_when_shuffled": disappears_when_shuffled,
            "process_level_learning_to_learn_established": meta_established,
        },
        "reconstructed_costs": reconstructed_costs,
        "verdict": "DEVELOPMENT_PILOT_ONLY",
    }
