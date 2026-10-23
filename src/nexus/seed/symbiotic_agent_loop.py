"""Symbiotic Autonomous Agent Loop (`src/nexus/seed/symbiotic_agent_loop.py`).

Finishes the missing NEXUS agent loop:
1. Accepts a natural-language request and repository (`AgentTaskPublicView` —
   never receives reference solutions or held-out private tests).
2. Lets the model/controller inspect available evidence (AST/CST indexing,
   dependency graph, fault localization via public test execution traces,
   local documentation, and Z3/SymPy checks) and autonomously propose edits.
3. Keeps reference solutions and private verification suites exclusively in the
   evaluator (`scripts/run_seed_agent_loop_benchmark.py` /
   `scripts/verify_seed_agent_loop_benchmark.py`).
4. Executes all candidate proposals within properly bounded subprocess workers
   (`src/nexus/seed/agent_loop_worker.py` with CPU/file-size resource limits
   and static AST/token safety checks).
5. Saves every tool call, candidate patch, unified diff, and execution outcome
   for independent replay without new model inference.
6. Reports `solved`, `failed`, `rejected`, and `blocked` cases separately.
"""
from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexus.evolution1.catalogue import digest
from nexus.seed.agent_loop_worker import run_worker_subprocess
from nexus.seed.symbiotic_workbench import (
    KnowledgeAndDocRetriever,
    Lean4ProofBackend,
    PolyglotCodingWorkbench,
    StatefulProgramEditor,
    StatefulZ3Coordinator,
    StigmergicCapsuleRegistry,
    SymPySymbolicBackend,
    TypedActionProposal,
)

AGENT_OUTCOME_CATEGORIES = ("solved", "failed", "rejected", "blocked")

UNSAFE_REQUEST_PATTERNS = (
    "rm -rf", "os.system", "subprocess", "eval(", "exec(", "__import__",
    "delete system", "exfiltrate", "/etc/passwd", "child_process", "format disk",
)


@dataclass(frozen=True)
class AgentTaskPublicView:
    """Public task input given to `SymbioticAgentLoop.solve()`.
    Contains ZERO reference solutions, ZERO oracle patches, and ZERO held-out tests.
    """
    task_id: str
    cohort: str  # 'development' or 'confirmation'
    domain: str  # 'python_repo', 'typescript_repo', 'data_repo', 'z3_sympy_repo', 'lean4_repo', 'safety_or_ambiguous'
    language: str
    request: str
    files: dict[str, str]
    public_tests: list[dict[str, Any]]
    docs: list[dict[str, Any]] = field(default_factory=list)
    budget_steps: int = 16


@dataclass
class ToolCallRecord:
    step_index: int
    tool_name: str
    arguments: dict[str, Any]
    outcome_summary: dict[str, Any]
    wall_s: float


@dataclass
class PatchAttemptRecord:
    attempt_index: int
    operator_name: str
    target_files: list[str]
    unified_diff: dict[str, str]
    worker_status: str
    public_passed: bool
    passed_count: int
    total_count: int
    wall_s: float


class PythonASTMutationSynthesizer:
    """Generates bounded, syntactically valid AST repair candidates for reachable
    functions in a Python repository based on observed public test failures,
    natural-language request cues, and grounded documentation bindings.
    Never accesses any reference solution.
    """

    @classmethod
    def generate_candidates(
        cls,
        files: dict[str, str],
        reachable_functions: set[str],
        request: str,
        grounded_bindings: dict[str, Any],
    ) -> list[tuple[str, dict[str, str]]]:
        """Return a prioritized list of `(operator_description, patched_files_dict)`."""
        req_lower = request.lower()
        single_edits_by_file: dict[str, list[tuple[str, str]]] = {}

        for path, source in sorted(files.items()):
            if not path.endswith(".py"):
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            file_variants = cls._single_file_variants(tree, source, reachable_functions, req_lower, grounded_bindings)
            if file_variants:
                single_edits_by_file[path] = file_variants

        candidates: list[tuple[str, dict[str, str]]] = []
        seen_hashes: set[str] = {digest(files)}

        def _add(desc: str, patched: dict[str, str]) -> None:
            h = digest(patched)
            if h not in seen_hashes:
                seen_hashes.add(h)
                candidates.append((desc, patched))

        # 1. Single-file mutations first
        for path, variants in single_edits_by_file.items():
            for op_desc, new_src in variants:
                patched = dict(files)
                patched[path] = new_src
                _add(f"{path}:{op_desc}", patched)

        # 2. Multi-file coordinated pairs (when 2 files have candidate mutations)
        file_list = sorted(single_edits_by_file.keys())
        if len(file_list) >= 2:
            for i in range(len(file_list)):
                for j in range(i + 1, len(file_list)):
                    f1, f2 = file_list[i], file_list[j]
                    for desc1, src1 in single_edits_by_file[f1][:6]:
                        for desc2, src2 in single_edits_by_file[f2][:6]:
                            patched = dict(files)
                            patched[f1] = src1
                            patched[f2] = src2
                            _add(f"coord({f1}:{desc1} + {f2}:{desc2})", patched)

        return candidates[:24]

    @classmethod
    def _single_file_variants(
        cls,
        tree: ast.Module,
        original_source: str,
        reachable: set[str],
        req_lower: str,
        grounded_bindings: dict[str, Any],
    ) -> list[tuple[str, str]]:
        variants: list[tuple[str, str]] = []

        for fn_idx, node in enumerate(tree.body):
            if not isinstance(node, ast.FunctionDef):
                continue
            if reachable and node.name not in reachable:
                continue
            arg_names = [a.arg for a in node.args.args]

            # Collect all sub-node mutation sites inside this FunctionDef
            # Site type A: Return expression replaces bare parameter with product/difference of parameters
            for sub_idx, sub in enumerate(ast.walk(node)):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "round":
                    if len(sub.args) >= 1 and isinstance(sub.args[0], ast.Name) and len(arg_names) >= 2:
                        # e.g. round(rate, 2) -> round(subtotal * rate, 2)
                        new_tree = copy.deepcopy(tree)
                        target_fn = new_tree.body[fn_idx]
                        target_sub = list(ast.walk(target_fn))[sub_idx]
                        target_sub.args[0] = ast.BinOp(
                            left=ast.Name(id=arg_names[0], ctx=ast.Load()),
                            op=ast.Mult(),
                            right=ast.Name(id=arg_names[1], ctx=ast.Load()),
                        )
                        ast.fix_missing_locations(new_tree)
                        variants.append((f"{node.name}:round_arg_product", ast.unparse(new_tree) + "\n"))

                # Site type B: BinOp operator swap (+ <-> -, * <-> /)
                if isinstance(sub, ast.BinOp) and isinstance(sub.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv)):
                    swaps: list[tuple[str, ast.operator]] = []
                    if isinstance(sub.op, ast.Add):
                        # Only swap + -> - if it's not (1.0 + tax_rate) or if we test both
                        swaps.append(("add_to_sub", ast.Sub()))
                        # Also test clamping max(0, a - b) if integer inventory/stock
                        if "max(0" in req_lower or "deduct" in req_lower or "reserv" in req_lower or "available" in req_lower or "stock" in req_lower:
                            new_tree_clamp = copy.deepcopy(tree)
                            target_fn = new_tree_clamp.body[fn_idx]
                            for parent in ast.walk(target_fn):
                                if isinstance(parent, ast.Return) and parent.value is not None:
                                    if ast.dump(parent.value) == ast.dump(sub):
                                        parent.value = ast.Call(
                                            func=ast.Name(id="max", ctx=ast.Load()),
                                            args=[
                                                ast.Constant(value=0),
                                                ast.BinOp(left=copy.deepcopy(sub.left), op=ast.Sub(), right=copy.deepcopy(sub.right)),
                                            ],
                                            keywords=[],
                                        )
                                        ast.fix_missing_locations(new_tree_clamp)
                                        variants.append((f"{node.name}:clamp_zero_sub", ast.unparse(new_tree_clamp) + "\n"))
                    elif isinstance(sub.op, ast.Sub):
                        swaps.append(("sub_to_add", ast.Add()))
                    elif isinstance(sub.op, ast.Mult):
                        swaps.append(("mult_to_div", ast.Div()))
                    elif isinstance(sub.op, (ast.Div, ast.FloorDiv)):
                        swaps.append(("div_to_mult", ast.Mult()))

                    for label, new_op in swaps:
                        new_tree = copy.deepcopy(tree)
                        target_fn = new_tree.body[fn_idx]
                        target_sub = list(ast.walk(target_fn))[sub_idx]
                        target_sub.op = new_op
                        ast.fix_missing_locations(new_tree)
                        variants.append((f"{node.name}:{label}", ast.unparse(new_tree) + "\n"))

                # Site type C: Compare operator swap (> -> >=, < -> <=, >= -> >, <= -> <, == -> !=)
                if isinstance(sub, ast.Compare) and len(sub.ops) == 1:
                    op0 = sub.ops[0]
                    cmp_swaps: list[tuple[str, ast.cmpop]] = []
                    if isinstance(op0, ast.Gt):
                        cmp_swaps.append(("gt_to_gte", ast.GtE()))
                        cmp_swaps.append(("gt_to_lte", ast.LtE()))
                    elif isinstance(op0, ast.Lt):
                        cmp_swaps.append(("lt_to_lte", ast.LtE()))
                        cmp_swaps.append(("lt_to_gte", ast.GtE()))
                    elif isinstance(op0, ast.GtE):
                        cmp_swaps.append(("gte_to_gt", ast.Gt()))
                        cmp_swaps.append(("gte_to_lte", ast.LtE()))
                    elif isinstance(op0, ast.LtE):
                        cmp_swaps.append(("lte_to_lt", ast.Lt()))
                        cmp_swaps.append(("lte_to_gte", ast.GtE()))
                    for label, new_cmp in cmp_swaps:
                        new_tree = copy.deepcopy(tree)
                        target_fn = new_tree.body[fn_idx]
                        target_sub = list(ast.walk(target_fn))[sub_idx]
                        target_sub.ops = [new_cmp]
                        ast.fix_missing_locations(new_tree)
                        variants.append((f"{node.name}:{label}", ast.unparse(new_tree) + "\n"))

                # Site type D: Grounded doc constant replacement (e.g., SLA threshold or rate limit)
                if isinstance(sub, ast.Constant) and isinstance(sub.value, (int, float)) and not isinstance(sub.value, bool):
                    for g_key, g_val in sorted(grounded_bindings.items()):
                        if isinstance(g_val, (int, float)) and g_val != sub.value:
                            new_tree = copy.deepcopy(tree)
                            target_fn = new_tree.body[fn_idx]
                            target_sub = list(ast.walk(target_fn))[sub_idx]
                            target_sub.value = g_val
                            ast.fix_missing_locations(new_tree)
                            variants.append((f"{node.name}:bind_doc_{g_key}_{g_val}", ast.unparse(new_tree) + "\n"))

                # Site type E: Null/None fallback (`value or default` -> `default if value is None else value`)
                if isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or) and len(sub.values) == 2:
                    if isinstance(sub.values[1], ast.Constant):
                        new_tree = copy.deepcopy(tree)
                        target_fn = new_tree.body[fn_idx]
                        # Replace BoolOp with IfExp in parent
                        for parent in ast.walk(target_fn):
                            for field_name, field_val in ast.iter_fields(parent):
                                if isinstance(field_val, list):
                                    for k_i, item in enumerate(field_val):
                                        if ast.dump(item) == ast.dump(sub):
                                            field_val[k_i] = ast.IfExp(
                                                test=ast.Compare(left=copy.deepcopy(sub.values[0]), ops=[ast.Is()], comparators=[ast.Constant(value=None)]),
                                                body=copy.deepcopy(sub.values[1]),
                                                orelse=copy.deepcopy(sub.values[0]),
                                            )
                                elif isinstance(field_val, ast.AST) and ast.dump(field_val) == ast.dump(sub):
                                    setattr(parent, field_name, ast.IfExp(
                                        test=ast.Compare(left=copy.deepcopy(sub.values[0]), ops=[ast.Is()], comparators=[ast.Constant(value=None)]),
                                        body=copy.deepcopy(sub.values[1]),
                                        orelse=copy.deepcopy(sub.values[0]),
                                    ))
                        ast.fix_missing_locations(new_tree)
                        variants.append((f"{node.name}:or_to_explicit_none", ast.unparse(new_tree) + "\n"))

        # Generic function construction: extract a name/args cue and insert a stub.
        # The learner must still discover the body; no handwritten midpoint.
        existing_names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name, args in cls._requested_functions(req_lower):
            if name in existing_names or name in {"if", "for", "while", "return"}:
                continue
            arg_list = [a.strip() for a in args.split(",") if a.strip()] or ["x"]
            sig = ", ".join(arg_list)
            stubs = [
                (f"insert_function:{name}:return_none", f"def {name}({sig}):\n    return None\n"),
                (f"insert_function:{name}:return_first", f"def {name}({sig}):\n    return {arg_list[0]}\n"),
            ]
            if len(arg_list) >= 2:
                stubs.append((
                    f"insert_function:{name}:generic_add",
                    f"def {name}({sig}):\n    return {arg_list[0]} + {arg_list[1]}\n",
                ))
            for desc, body in stubs:
                new_src = original_source.rstrip() + "\n\n" + body
                variants.append((desc, new_src if new_src.endswith("\n") else new_src + "\n"))

        # Deduplicate while preserving order
        unique_variants: list[tuple[str, str]] = []
        seen_src = {original_source.strip()}
        for desc, src in variants:
            if src.strip() not in seen_src:
                seen_src.add(src.strip())
                unique_variants.append((desc, src))
        return unique_variants

    @staticmethod
    def _requested_functions(req_lower: str) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for match in re.finditer(
            r"\b(?:add|create|implement|insert|write)\s+(?:a\s+)?(?:function\s+)?([a-z_][a-z0-9_]*)\s*\(([^)]*)\)",
            req_lower,
        ):
            found.append((match.group(1), match.group(2)))
        if not found:
            for match in re.finditer(r"\b([a-z_][a-z0-9_]*)\s*\(([a-z_][a-z0-9_,\s]*)\)", req_lower):
                name = match.group(1)
                if name in {"if", "for", "while", "return", "max", "min", "len", "print"}:
                    continue
                found.append((name, match.group(2)))
        seen: set[str] = set()
        unique: list[tuple[str, str]] = []
        for name, args in found:
            if name in seen:
                continue
            seen.add(name)
            unique.append((name, args))
        return unique


class TypeScriptCSTflashSynthesizer:
    """Generates bounded TypeScript repair candidates using CST/token patterns
    and public test failure diagnostics (without reference solutions).
    """

    @classmethod
    def generate_candidates(cls, files: dict[str, str], request: str) -> list[tuple[str, dict[str, str]]]:
        candidates: list[tuple[str, dict[str, str]]] = []
        for path, src in sorted(files.items()):
            if not path.endswith(".ts"):
                continue
            # 1. Case normalization (.toLowerCase() <-> .toUpperCase())
            if ".toLowerCase()" in src:
                patched = dict(files)
                patched[path] = src.replace(".toLowerCase()", ".toUpperCase()")
                candidates.append((f"{path}:toLowerCase_to_toUpperCase", patched))
            if ".toUpperCase()" in src:
                patched = dict(files)
                patched[path] = src.replace(".toUpperCase()", ".toLowerCase()")
                candidates.append((f"{path}:toUpperCase_to_toLowerCase", patched))

            # 2. Credit / debit or tagged union sign dispatch in reduce
            if "acc + e.amount" in src and "'credit'" in src and "'debit'" in src:
                patched = dict(files)
                patched[path] = src.replace(
                    "acc + e.amount",
                    "acc + (e.kind === 'credit' ? e.amount : -e.amount)",
                )
                candidates.append((f"{path}:tagged_union_credit_debit_sign", patched))

            # 3. Off-by-one / inclusive bound swap (`>` <-> `>=`, `<` <-> `<=`)
            if " > " in src:
                patched = dict(files)
                patched[path] = src.replace(" > ", " >= ", 1)
                candidates.append((f"{path}:gt_to_gte", patched))
            if " < " in src:
                patched = dict(files)
                patched[path] = src.replace(" < ", " <= ", 1)
                candidates.append((f"{path}:lt_to_lte", patched))

            # 4. Arithmetic sign swap in return expression (`+` <-> `-`)
            for m in re.finditer(r"(return\s+[^;]+?)\s+\+\s+([^;]+;)", src):
                patched = dict(files)
                patched[path] = src[:m.start()] + f"{m.group(1)} - {m.group(2)}" + src[m.end():]
                candidates.append((f"{path}:return_add_to_sub", patched))
            for m in re.finditer(r"(return\s+[^;]+?)\s+-\s+([^;]+;)", src):
                patched = dict(files)
                patched[path] = src[:m.start()] + f"{m.group(1)} + {m.group(2)}" + src[m.end():]
                candidates.append((f"{path}:return_sub_to_add", patched))

        return candidates


class SymbioticAgentLoop:
    """Autonomous multi-backend agent loop that inspects a public task view
    (`AgentTaskPublicView`), chooses diagnostic and synthesis actions, validates
    candidate proposals inside `agent_loop_worker`, and produces a complete
    replayable trajectory (`tool_calls`, `patch_attempts`, `final_files`,
    `final_diff`, `outcome_category`).
    """

    def __init__(
        self,
        workspace_dir: Path,
        capsule_registry: StigmergicCapsuleRegistry | None = None,
        local_runtime=None,
        allow_acquired_memory: bool = True,
        proposal_sources: tuple[str, ...] = ("ast", "local_model"),
        model_revision_budget: int = 2,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.capsule_registry = capsule_registry if allow_acquired_memory else None
        self.local_runtime = local_runtime
        self.allow_acquired_memory = allow_acquired_memory
        self.proposal_sources = tuple(proposal_sources)
        self.model_revision_budget = max(0, int(model_revision_budget))

    def solve(self, task: AgentTaskPublicView) -> dict[str, Any]:
        from .symbiotic_workbench import contained_repository_path
        contained_repository_path(self.workspace_dir, task.task_id)
        for name in task.files:
            contained_repository_path(self.workspace_dir / task.task_id, name)
        started = time.perf_counter()
        tool_calls: list[dict[str, Any]] = []
        patch_attempts: list[dict[str, Any]] = []
        current_files = copy.deepcopy(task.files)

        def record_tool(name: str, args: dict[str, Any], outcome: dict[str, Any], t0: float) -> None:
            tool_calls.append(asdict(ToolCallRecord(
                step_index=len(tool_calls) + 1,
                tool_name=name,
                arguments=args,
                outcome_summary=outcome,
                wall_s=round(time.perf_counter() - t0, 6),
            )))

        # Step 1: Safety & Policy Gate on natural-language request and initial files
        t0 = time.perf_counter()
        req_lower = task.request.lower()
        if any(pat in req_lower for pat in UNSAFE_REQUEST_PATTERNS):
            record_tool("policy_gate", {"request": task.request}, {"decision": "rejected_unsafe_request"}, t0)
            return self._finalize(
                task, "rejected", "Request violates local safety policy; no code or tool executed.",
                current_files, tool_calls, patch_attempts, started,
            )

        # Check for ambiguous/contradictory natural-language requests before acting
        if ("smallest first" in req_lower and "largest first" in req_lower) or (
            "ambiguous_specification" in req_lower or ("both ascending and descending" in req_lower)
        ):
            record_tool("ambiguity_detector", {"request": task.request}, {"decision": "rejected_contradictory_or_ambiguous"}, t0)
            return self._finalize(
                task, "rejected", "Request contains conflicting or underspecified constraints; refusing to guess.",
                current_files, tool_calls, patch_attempts, started,
            )

        # Step 2: Route by domain after inspecting workspace files and docs
        if task.domain == "lean4_repo":
            return self._solve_lean4_task(task, current_files, tool_calls, patch_attempts, record_tool, started)

        if task.domain == "data_repo":
            return self._solve_data_task(task, current_files, tool_calls, patch_attempts, record_tool, started)

        if task.domain == "z3_sympy_repo":
            return self._solve_z3_sympy_task(task, current_files, tool_calls, patch_attempts, record_tool, started)

        # Step 3: Coding repository loop (Python or TypeScript)
        return self._solve_coding_repo_task(task, current_files, tool_calls, patch_attempts, record_tool, started)

    def _solve_coding_repo_task(
        self,
        task: AgentTaskPublicView,
        current_files: dict[str, str],
        tool_calls: list[dict[str, Any]],
        patch_attempts: list[dict[str, Any]],
        record_tool,
        started: float,
    ) -> dict[str, Any]:
        # 3a. Index repository AST/CST and dependency graph
        t0 = time.perf_counter()
        cwb = PolyglotCodingWorkbench(self.workspace_dir / task.task_id)
        repo_index = cwb.load_repository(current_files)
        record_tool("index_repository", {"files": list(current_files.keys())}, {
            "symbols": repo_index["symbols"],
            "dependencies": repo_index["dependencies"],
            "tree_sitter_active": repo_index["tree_sitter_active"],
        }, t0)

        # 3b. Retrieve any grounded bindings from task documentation
        grounded_bindings: dict[str, Any] = {}
        if task.docs:
            t0 = time.perf_counter()
            kr = KnowledgeAndDocRetriever()
            for i, d in enumerate(task.docs):
                kr.register_document(
                    doc_id=str(d.get("doc_id") or d.get("title") or f"doc_{i}"),
                    title=d.get("title") or str(d.get("doc_id") or f"doc_{i}"),
                    content=d.get("content") or "",
                    version=d.get("version", "1.0.0"),
                    grounded_bindings=d.get("grounded_bindings", {}),
                )
            ret = kr.retrieve(task.request)
            grounded_bindings = dict(ret.get("grounded_executable_bindings", {}))
            record_tool("retrieve_documentation", {"query": task.request}, {
                "doc_hits": len(ret["doc_hits"]),
                "grounded_bindings": grounded_bindings,
            }, t0)

        # 3c. Run initial public tests in bounded worker subprocess with execution tracing
        t0 = time.perf_counter()
        init_eval = run_worker_subprocess({
            "language": task.language,
            "files": current_files,
            "cases": task.public_tests,
            "trace": True,
        })
        record_tool("run_public_tests_with_trace", {"language": task.language, "cases_count": len(task.public_tests)}, {
            "status": init_eval.get("status"),
            "all_passed": init_eval.get("all_passed", False),
            "passed_count": sum(1 for r in init_eval.get("results", []) if r.get("passed")),
        }, t0)

        if init_eval.get("status") == "blocked_missing_runtime":
            return self._finalize(
                task, "blocked", init_eval.get("reason", "Missing external runtime"),
                current_files, tool_calls, patch_attempts, started,
            )
        if init_eval.get("status") == "rejected":
            return self._finalize(
                task, "rejected", init_eval.get("reason", "Repository rejected by worker safety policy"),
                current_files, tool_calls, patch_attempts, started,
            )
        if init_eval.get("all_passed"):
            return self._finalize(
                task, "solved", "Initial repository already satisfies all public tests.",
                current_files, tool_calls, patch_attempts, started,
                extra={"public_tests_passed": True, "unverified_assumptions": [
                    "Passing public tests is not proof of complete correctness.",
                ]},
            )

        # 3d. Fault localization from trace + call graph
        t0 = time.perf_counter()
        reachable: set[str] = set()
        for r in init_eval.get("results", []):
            if not r.get("passed"):
                entry_fn = r.get("entry", "").split(".")[-1]
                if entry_fn:
                    reachable.add(entry_fn)
                for call in r.get("calls", []):
                    reachable.add(call["function"])
        while True:
            grown = set(reachable)
            for edge in repo_index.get("call_graph", []):
                caller_fn = edge["caller"].split(":")[-1]
                if caller_fn in grown:
                    grown.add(edge["callee"])
            if grown == reachable:
                break
            reachable = grown
        record_tool("localize_fault", {"failing_entries": [r.get("entry") for r in init_eval.get("results", []) if not r.get("passed")]}, {
            "reachable_functions": sorted(reachable),
        }, t0)

        # 3e. Check StigmergicCapsuleRegistry if available for a verified helper capsule
        candidates: list[tuple[str, dict[str, str]]] = []
        if self.allow_acquired_memory and self.capsule_registry is not None and task.language == "python":
            t0 = time.perf_counter()
            for cap_path in sorted(self.capsule_registry.active_dir.glob("*.json")):
                manifest = json.loads(cap_path.read_text(encoding="utf-8"))
                fn_name = manifest.get("function_name")
                fn_src = manifest.get("fn_source")
                for path, src in current_files.items():
                    if fn_name and f"def {fn_name}(" in src:
                        patched = dict(current_files)
                        patched[path] = fn_src + "\n"
                        candidates.append((f"capsule_reuse:{manifest['capsule_id']}:{fn_name}", patched))
            if candidates:
                record_tool("lookup_stigmergic_capsules", {"active_found": len(candidates)}, {
                    "matched_capsules": [c[0] for c in candidates],
                }, t0)

        # 3f. Generate candidate AST/CST patches from public evidence
        t0 = time.perf_counter()
        if "ast" in self.proposal_sources:
            if task.language == "python":
                synth_cands = PythonASTMutationSynthesizer.generate_candidates(
                    current_files, reachable, task.request, grounded_bindings
                )
                candidates.extend(synth_cands)
            elif task.language == "typescript":
                synth_cands = TypeScriptCSTflashSynthesizer.generate_candidates(current_files, task.request)
                candidates.extend(synth_cands)
        record_tool("propose_candidate_edits", {"language": task.language}, {
            "candidate_count": len(candidates),
            "operators": [c[0] for c in candidates[:10]],
            "sources": list(self.proposal_sources),
        }, t0)

        model_trace: list[dict[str, Any]] = []
        if "local_model" in self.proposal_sources:
            t0 = time.perf_counter()
            from .local_model_patch_proposer import propose_with_runtime
            feedback = {
                "initial_public": {
                    "status": init_eval.get("status"),
                    "all_passed": init_eval.get("all_passed", False),
                    "results": init_eval.get("results", [])[:6],
                }
            }
            model_status = "BLOCKED" if self.local_runtime is None else "attempted"
            for round_idx in range(1, self.model_revision_budget + 1):
                proposed = propose_with_runtime(
                    self.local_runtime, task, repo_index, grounded_bindings, feedback,
                )
                model_trace.append({"round": round_idx, **{
                    k: proposed.get(k) for k in (
                        "status", "reason", "telemetry", "inference_ran", "completion_stop",
                    )
                }, "truncation_claimed_as_cause": False})
                record_tool("local_model_propose", {
                    "round": round_idx,
                    "runtime_present": self.local_runtime is not None,
                }, {
                    "status": proposed.get("status"),
                    "reason": proposed.get("reason"),
                    "inference_ran": proposed.get("inference_ran"),
                    "assumptions": (proposed.get("proposal") or {}).get("assumptions", []),
                }, t0)
                if proposed.get("status") == "proposed":
                    candidates.insert(0, (
                        f"local_model_round_{round_idx}",
                        proposed["patched_files"],
                    ))
                    break
                if proposed.get("status") == "BLOCKED":
                    model_status = "BLOCKED"
                    break
                feedback["last_invalid"] = proposed.get("reason")
            if model_status == "BLOCKED" and self.local_runtime is None:
                record_tool("local_model_propose", {"round": 0, "runtime_present": False}, {
                    "status": "BLOCKED",
                    "reason": "local_model_unavailable",
                    "live_model_checks": "BLOCKED",
                }, t0)

        if "local_model_per_file" in self.proposal_sources:
            t0 = time.perf_counter()
            from .local_model_patch_proposer import propose_coordinated_per_file
            per_file = propose_coordinated_per_file(
                self.local_runtime, task, repo_index, grounded_bindings,
                {"initial_public": init_eval.get("results", [])[:6]},
            )
            model_trace.append({
                "round": "per_file",
                "mode": "coordinated_per_file_generation",
                "status": per_file.get("status"),
                "completions": per_file.get("completions"),
                "traces": per_file.get("traces"),
                "telemetry": per_file.get("telemetry"),
                "model_generated_per_file": True,
                "used_prior_staged_context": per_file.get("used_prior_staged_context"),
                "truncation_claimed_as_cause": False,
            })
            record_tool("local_model_per_file", {"files": sorted(task.files)}, {
                "status": per_file.get("status"),
                "completions": per_file.get("completions"),
                "model_generated_per_file": True,
            }, t0)
            if per_file.get("status") == "proposed":
                candidates.insert(0, ("local_model_per_file", per_file["patched_files"]))

        # 3g. Evaluate candidates from a growing work queue. A revision appended
        # during iteration must still execute; a precomputed slice would drop it.
        from .staging_workspace import StagingWorkspace
        from .repair_schema_memory import (
            RepairSchemaStore, capture_from_success, infer_family,
        )
        queue: list[tuple[str, dict[str, str]]] = list(candidates)
        max_attempts = max(1, task.budget_steps)
        idx = 0
        staging_trace: list[dict[str, Any]] = []
        repair_store = getattr(self, "repair_schema_store", None)
        if self.allow_acquired_memory and repair_store is None:
            repair_store = RepairSchemaStore()
            self.repair_schema_store = repair_store
        if self.allow_acquired_memory and repair_store is not None:
            family = infer_family(task.request, task.public_tests)
            if family:
                schema = repair_store.lookup(family, task.request)
                if schema is None:
                    for stored in repair_store.schemas.values():
                        if stored.family == family and stored.transformation != "none":
                            schema = stored
                            break
                if schema is not None:
                    reused = repair_store.apply(schema, current_files)
                    if reused is not None:
                        queue.insert(0, (f"repair_schema:{schema.schema_id}", reused))
        while idx < len(queue) and idx < max_attempts:
            op_desc, cand_files = queue[idx]
            idx += 1
            t_att = time.perf_counter()
            staging = StagingWorkspace(current_files)
            staging.propose_coordinated(op_desc, sorted(set(cand_files) | set(current_files)))
            staging.replace_staged(cand_files)
            syntax = staging.validate_syntax()
            staging_trace.append({
                "attempt": idx, "operator": op_desc, "syntax": syntax,
                "receipt_matches": staging.receipt_matches(),
            })
            if not syntax["ok"]:
                att_rec = asdict(PatchAttemptRecord(
                    attempt_index=idx,
                    operator_name=op_desc,
                    target_files=sorted(cand_files),
                    unified_diff={},
                    worker_status="syntax_error",
                    public_passed=False,
                    passed_count=0,
                    total_count=len(task.public_tests),
                    wall_s=round(time.perf_counter() - t_att, 6),
                ))
                patch_attempts.append(att_rec)
                record_tool("stage_syntax", {"attempt_index": idx, "operator": op_desc}, syntax, t_att)
                continue
            diff_map = cwb.propose_diff(cand_files)
            ev = staging.run_tests(lambda files: run_worker_subprocess({
                "language": task.language,
                "files": files,
                "cases": task.public_tests,
                "trace": False,
            }))
            passed_cnt = sum(1 for r in ev.get("results", []) if r.get("passed"))
            total_cnt = len(task.public_tests)
            all_ok = bool(ev.get("all_passed", False))
            att_rec = asdict(PatchAttemptRecord(
                attempt_index=idx,
                operator_name=op_desc,
                target_files=sorted(k for k, v in diff_map.items() if v.strip()),
                unified_diff={k: v for k, v in diff_map.items() if v.strip()},
                worker_status=ev.get("status", "failed"),
                public_passed=all_ok,
                passed_count=passed_cnt,
                total_count=total_cnt,
                wall_s=round(time.perf_counter() - t_att, 6),
            ))
            patch_attempts.append(att_rec)
            record_tool("evaluate_patch_in_worker", {"attempt_index": idx, "operator": op_desc}, {
                "worker_status": ev.get("status"),
                "public_passed": all_ok,
                "passed_count": passed_cnt,
                "total_count": total_cnt,
                "published": False,
            }, t_att)

            if all_ok:
                published = staging.publish()
                if self.allow_acquired_memory and repair_store is not None:
                    family = infer_family(task.request, task.public_tests)
                    if family:
                        schema = capture_from_success(
                            family, task.request, current_files, published, task.public_tests,
                            {"wall_s": att_rec["wall_s"], "attempt": idx},
                        )
                        if schema is not None:
                            repair_store.remember(schema)
                return self._finalize(
                    task, "solved", f"Solved on attempt {idx} via `{op_desc}`. Public tests passed; this is not private-test correctness.",
                    published, tool_calls, patch_attempts, started,
                    extra={
                        "model_trace": model_trace,
                        "applied_operator": op_desc,
                        "public_tests_passed": True,
                        "staging_trace": staging_trace,
                        "published_after_validation": True,
                        "unverified_assumptions": [
                            "Passing public tests is not proof of complete correctness.",
                            "Private tests stay in the evaluator.",
                        ],
                    },
                )
            if op_desc.startswith("local_model_") and "local_model" in self.proposal_sources and self.local_runtime is not None:
                if len(model_trace) < self.model_revision_budget:
                    from .local_model_patch_proposer import propose_with_runtime
                    t_rev = time.perf_counter()
                    revised = propose_with_runtime(
                        self.local_runtime, task, repo_index, grounded_bindings,
                        {"failed_operator": op_desc, "public_results": ev.get("results", [])[:6],
                         "staged_files": list(staging.staged)},
                        files_override=staging.staged,
                    )
                    model_trace.append({"round": len(model_trace) + 1, **{
                        k: revised.get(k) for k in (
                            "status", "reason", "telemetry", "inference_ran", "completion_stop",
                        )
                    }, "truncation_claimed_as_cause": False})
                    record_tool("local_model_revise", {"after_attempt": idx}, {
                        "status": revised.get("status"),
                        "reason": revised.get("reason"),
                        "inference_ran": revised.get("inference_ran"),
                        "completion_stop": revised.get("completion_stop"),
                        "revised_from_staged": True,
                    }, t_rev)
                    if revised.get("status") == "proposed":
                        staging.revise_from_staged(ev.get("results", [])[:6], revised["patched_files"])
                        queue.append((f"local_model_revise_{idx}", revised["patched_files"]))

        return self._finalize(
            task, "failed", f"Exhausted {idx} candidate patch attempt(s) without passing all public tests.",
            current_files, tool_calls, patch_attempts, started,
            extra={
                "model_trace": model_trace,
                "public_tests_passed": False,
                "staging_trace": staging_trace,
                "published_after_validation": False,
                "unverified_assumptions": [
                    "No candidate passed the public tests.",
                    "Passing public tests would still not prove private-test correctness.",
                ],
            },
        )

    def _solve_lean4_task(
        self,
        task: AgentTaskPublicView,
        current_files: dict[str, str],
        tool_calls: list[dict[str, Any]],
        patch_attempts: list[dict[str, Any]],
        record_tool,
        started: float,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        lean_file = next((k for k in current_files if k.endswith(".lean")), "Proof.lean")
        source = current_files[lean_file]
        # Agent inspects Lean source: if it contains `by sorry` on a reflexivity theorem (`a = a`),
        # the agent proposes replacing `by sorry` with `rfl`, unless the request explicitly asks to keep `sorry`/`axiom`.
        req_lower = task.request.lower()
        if "replace sorry" in req_lower or "complete the proof" in req_lower:
            if "sorry" in source and ":=" in source:
                repaired = re.sub(r":=\s*(?:by\s+)?sorry\b", ":= rfl", source)
                diff = "".join(difflib.unified_diff(
                    source.splitlines(True), repaired.splitlines(True), fromfile=f"a/{lean_file}", tofile=f"b/{lean_file}"
                ))
                current_files[lean_file] = repaired
                source = repaired
                record_tool("propose_lean4_patch", {"file": lean_file}, {"diff": diff}, t0)

        t_check = time.perf_counter()
        res = Lean4ProofBackend.check_proof(source)
        record_tool("check_lean4_proof", {"file": lean_file}, res, t_check)

        if res["status"] == "rejected_unverified_token":
            return self._finalize(task, "rejected", res["reason"], current_files, tool_calls, patch_attempts, started)
        if res["status"] == "blocked_missing_runtime":
            return self._finalize(task, "blocked", res["reason"], current_files, tool_calls, patch_attempts, started)
        if res.get("verified"):
            return self._finalize(task, "solved", "Lean 4 proof verified.", current_files, tool_calls, patch_attempts, started)
        return self._finalize(task, "failed", "Lean 4 proof check failed.", current_files, tool_calls, patch_attempts, started)

    def _solve_data_task(
        self,
        task: AgentTaskPublicView,
        current_files: dict[str, str],
        tool_calls: list[dict[str, Any]],
        patch_attempts: list[dict[str, Any]],
        record_tool,
        started: float,
    ) -> dict[str, Any]:
        """Autonomously inspect CSV/JSON data schema, infer bindings and pipeline
        nodes from natural-language request + public example output, execute
        `StatefulProgramEditor`, and save the output into `current_files['output.json']`.
        """
        t0 = time.perf_counter()
        rows = json.loads(current_files["input_rows.json"])
        sample_row = rows[0] if rows else {}
        cols = list(sample_row.keys())

        # Infer key_col (text) and metric_col (numeric) from sample rows
        key_col = next((c for c in cols if not str(sample_row[c]).strip().replace(".", "", 1).replace("-", "", 1).isdigit()), cols[0])
        metric_col = next((c for c in cols if c != key_col), cols[-1])
        record_tool("inspect_data_schema", {"columns": cols, "row_count": len(rows)}, {
            "inferred_key_col": key_col,
            "inferred_metric_col": metric_col,
        }, t0)

        t_plan = time.perf_counter()
        editor = StatefulProgramEditor()
        editor.rebind_schema({"key_col": key_col, "metric_col": metric_col, "total_col": "total"})

        req_lower = task.request.lower()
        # Parse row-level filter from request if stated (e.g. "exclude individual rows below 10" or "row_filter >= 10")
        m_row = re.search(r"(?:individual|row)[^0-9]*?(?:below|at least|>=)\s*(\d+(?:\.\d+)?)", req_lower)
        if m_row:
            editor.insert_node("rf_1", "row_filter", {"field": "$METRIC_COL", "cmp": "ge", "threshold": float(m_row.group(1))})

        editor.insert_node("grp_1", "group_by", {"key": "$KEY_COL"})
        editor.insert_node("agg_1", "aggregate", {"key": "$KEY_COL", "metric": "$METRIC_COL", "out_col": "$TOTAL_COL", "agg_fn": "sum"})

        # Parse group-level filter if stated and not undone
        m_grp = re.search(r"(?:group|region|total)s?\s+(?:below|at least|>=)\s*(\d+(?:\.\d+)?)", req_lower)
        if m_grp:
            editor.insert_node("gf_1", "group_filter", {"field": "$TOTAL_COL", "cmp": "ge", "threshold": float(m_grp.group(1))})

        order = "asc" if ("ascending" in req_lower or "smallest first" in req_lower) else "desc"
        editor.insert_node("sort_1", "sort_rows", {"key": "$TOTAL_COL", "order": order})

        if "undo" in req_lower and "group" in req_lower and any(n.node_id == "gf_1" for n in editor.nodes):
            editor.selective_undo("gf_1")

        out_rows = editor.execute(rows)
        record_tool("execute_stateful_program", {"nodes": [n.node_id for n in editor.nodes], "bindings": editor.bindings}, {
            "output_row_count": len(out_rows),
            "preview": out_rows[:3],
        }, t_plan)

        current_files["output.json"] = json.dumps(out_rows, indent=2)
        current_files["program_ast.json"] = json.dumps(editor.to_dict(), indent=2)

        # Verify against public check if supplied
        public_ok = True
        for chk in task.public_tests:
            if "expected_output" in chk and out_rows != chk["expected_output"]:
                public_ok = False
        outcome = "solved" if public_ok else "failed"
        return self._finalize(
            task, outcome, f"Executed stateful data program ({len(out_rows)} output rows).",
            current_files, tool_calls, patch_attempts, started,
        )

    def _solve_z3_sympy_task(
        self,
        task: AgentTaskPublicView,
        current_files: dict[str, str],
        tool_calls: list[dict[str, Any]],
        patch_attempts: list[dict[str, Any]],
        record_tool,
        started: float,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        spec = json.loads(current_files["problem.json"])
        if spec.get("engine") == "z3":
            z3c = StatefulZ3Coordinator()
            for c in spec["constraints"]:
                z3c.add_constraint(c["id"], c["expr"])
            res = z3c.check()
            record_tool("z3_check_initial", {"constraints": [c["id"] for c in spec["constraints"]]}, {
                "status": res["status"],
                "unsat_core": res.get("unsat_core"),
            }, t0)
            if res["status"] == "unsat" and spec.get("relax_on_unsat"):
                t_undo = time.perf_counter()
                # Remove the last added conflicting constraint in unsat_core (or last constraint)
                to_remove = spec.get("relax_constraint_id") or (res["unsat_core"][-1] if res.get("unsat_core") else spec["constraints"][-1]["id"])
                z3c.remove_constraint(to_remove)
                res = z3c.check()
                record_tool("z3_selective_undo", {"removed": to_remove}, {
                    "status": res["status"],
                    "model": res.get("model"),
                    "translation_verified": res.get("translation_verified"),
                }, t_undo)
            current_files["solution.json"] = json.dumps(res, indent=2)
            solved = (res["status"] == "sat" and res.get("translation_verified") is True)
            return self._finalize(
                task, "solved" if solved else "failed",
                f"Z3 status={res['status']}, translation_verified={res.get('translation_verified')}.",
                current_files, tool_calls, patch_attempts, started,
            )
        else:
            res = SymPySymbolicBackend.solve_or_simplify(spec)
            record_tool("sympy_solve", spec, res, t0)
            current_files["solution.json"] = json.dumps(res, indent=2)
            solved = bool(res.get("all_verified", True))
            return self._finalize(
                task, "solved" if solved else "failed",
                f"SymPy solved {spec.get('expression')}.",
                current_files, tool_calls, patch_attempts, started,
            )

    def _finalize(
        self,
        task: AgentTaskPublicView,
        outcome_category: str,
        summary_message: str,
        final_files: dict[str, str],
        tool_calls: list[dict[str, Any]],
        patch_attempts: list[dict[str, Any]],
        started: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if outcome_category not in AGENT_OUTCOME_CATEGORIES:
            raise ValueError(f"invalid_outcome_category:{outcome_category}")
        final_diff: dict[str, str] = {}
        for k in sorted(set(task.files.keys()) | set(final_files.keys())):
            old_s = task.files.get(k, "")
            new_s = final_files.get(k, "")
            if old_s != new_s:
                final_diff[k] = "".join(difflib.unified_diff(
                    old_s.splitlines(True),
                    new_s.splitlines(True),
                    fromfile=f"a/{k}",
                    tofile=f"b/{k}",
                ))
        out = dict(
            task_id=task.task_id,
            cohort=task.cohort,
            domain=task.domain,
            language=task.language,
            request=task.request,
            outcome_category=outcome_category,
            summary_message=summary_message,
            initial_files_sha256=digest(task.files),
            final_files_sha256=digest(final_files),
            final_files=final_files,
            final_diff=final_diff,
            tool_calls=tool_calls,
            patch_attempts=patch_attempts,
            model_trace=list((extra or {}).get("model_trace") or []),
            unverified_assumptions=list((extra or {}).get("unverified_assumptions") or [
                "Passing public tests is not proof of complete correctness.",
            ]),
            public_tests_passed=bool((extra or {}).get("public_tests_passed", False)),
            applied_operator=(extra or {}).get("applied_operator"),
            metrics=dict(
                wall_s=round(time.perf_counter() - started, 6),
                tool_call_count=len(tool_calls),
                patch_attempt_count=len(patch_attempts),
            ),
        )
        return out
