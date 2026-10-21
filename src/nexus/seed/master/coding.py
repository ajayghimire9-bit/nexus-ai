"""Coding architecture for the NEXUS Seed master architecture.

Treats coding as program synthesis + repository modeling + execution + debugging:
1. CodeTaskParser
2. RepositoryModel
3. ProgramSynthesizer (retrieve verified skill, compose typed programs, generate constrained patch)
4. ExecutionSandbox (syntax, lint/static, unit tests, type/contract, security/resource limits, behavioral checks)
5. DebuggingController (repair_syntax, change_implementation, revise_specification, request_clarification, revert)
6. DebuggingSkill extraction
"""
import ast
import copy
import re
from typing import Any
from .. import skill_programs as ir
from ..foundation import programs as foundation_programs
from .types import DebuggingSkill, TaskSpec

FORBIDDEN_AST_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
}
FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "http", "urllib",
    "ctypes", "multiprocessing", "threading", "pickle", " marshal",
}


class CodeTaskParser:
    """Extracts target behavior, language, file/module scope, inputs/outputs,
    constraints, and acceptance tests into a validated TaskSpec."""

    def parse(self, specification: str | dict) -> TaskSpec:
        if isinstance(specification, dict):
            goal = str(specification.get("goal", "synthesize_program"))
            language = str(specification.get("language", "python"))
            scope = specification.get("scope", ["module.py"])
            inputs = specification.get("inputs", {})
            expected_outputs = specification.get("expected_outputs")
            constraints = list(specification.get("constraints", ["pure_function", "bounded_budget"]))
            tests = list(specification.get("acceptance_tests", []))
            return TaskSpec(
                goal=goal,
                inputs=dict(language=language, scope=scope, examples=inputs),
                expected_outputs=expected_outputs,
                constraints=constraints,
                success_tests=tests,
                permitted_actions=["retrieve_skill", "compose_programs", "generate_patch", "verify_sandbox"],
                uncertainty=dict(ambiguous=len(tests) == 0 and expected_outputs is None),
            )

        if type(specification) is not str or not specification.strip():
            raise ValueError("code_task_specification_required")
        raw = specification.strip()
        lower = raw.lower()
        ops = []
        for word, op in (
            ("sort", "sort"),
            ("reverse", "reverse"),
            ("unique", "unique"),
            ("remove duplicates", "unique"),
            ("even", "even"),
            ("increment", "increment"),
        ):
            if word in lower and op not in ops:
                ops.append(op)
        return TaskSpec(
            goal=raw,
            inputs=dict(language="python", scope=["in_memory_module.py"], requested_ops=ops),
            expected_outputs="transformed_list",
            constraints=["no_io_or_network", "ast_verified", "bounded_instruction_budget"],
            success_tests=[dict(input=[3, 1, 2, 1], check="matches_composed_operators")],
            permitted_actions=["retrieve_skill", "compose_programs", "generate_patch"],
            uncertainty=dict(ambiguous=len(ops) == 0),
        )


class RepositoryModel:
    """Structured graph of files, symbols, functions, imports, dependencies,
    tests, call graph, and recent edits."""

    def __init__(self):
        self.files: dict[str, str] = {}
        self.recent_edits: list[dict] = []

    def index_files(self, file_map: dict[str, str]) -> dict:
        if type(file_map) is not dict:
            raise ValueError("repository_file_map_required")
        for path, content in file_map.items():
            if type(path) is not str or type(content) is not str:
                raise ValueError("repository_file_str_required")
            self.files[path] = content

        symbols: dict[str, list[str]] = {}
        functions: dict[str, list[dict]] = {}
        imports: dict[str, list[str]] = {}
        dependencies: list[dict] = []
        tests: list[str] = []
        call_graph: list[dict] = []

        for path, source in sorted(self.files.items()):
            file_syms = []
            file_funcs = []
            file_imports = []
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        args = [a.arg for a in node.args.args]
                        file_syms.append(node.name)
                        file_funcs.append(dict(name=node.name, args=args, lineno=node.lineno))
                        if node.name.startswith("test_") or "test" in path:
                            tests.append(f"{path}::{node.name}")
                        for sub in ast.walk(node):
                            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                                call_graph.append(dict(caller=f"{path}:{node.name}", callee=sub.func.id))
                    elif isinstance(node, ast.ClassDef):
                        file_syms.append(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.append(alias.name)
                            dependencies.append(dict(file=path, depends_on=alias.name))
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        file_imports.append(node.module)
                        dependencies.append(dict(file=path, depends_on=node.module))
            except SyntaxError:
                file_syms.append("<syntax_error>")

            symbols[path] = file_syms
            functions[path] = file_funcs
            imports[path] = file_imports

        return dict(
            files=sorted(self.files.keys()),
            symbols=symbols,
            functions=functions,
            imports=imports,
            dependencies=dependencies,
            tests=sorted(set(tests)),
            call_graph=call_graph,
            recent_edits=list(self.recent_edits[-16:]),
        )

    def apply_edit(self, path: str, new_content: str, reason: str = "patch"):
        old_content = self.files.get(path, "")
        self.files[path] = new_content
        self.recent_edits.append(dict(file=path, reason=reason, previous_content=old_content, new_content=new_content))


class ProgramSynthesizer:
    """Synthesizes code in three modes:
    1. retrieve an existing verified skill
    2. compose existing typed programs
    3. generate a constrained code patch
    """

    OP_TO_PYTHON = {
        "sort": "x = sorted(x)",
        "reverse": "x = list(reversed(x))",
        "unique": "x = list(dict.fromkeys(x))",
        "even": "x = [v for v in x if v % 2 == 0]",
        "increment": "x = [v + 1 for v in x]",
    }

    def synthesize(self, task_spec: TaskSpec, available_skills: dict[str, Any] | None = None, mode: str = "auto") -> dict:
        skills = dict(available_skills or {})
        ops = task_spec.inputs.get("requested_ops", []) if isinstance(task_spec.inputs, dict) else []
        goal_lower = task_spec.goal.lower()

        # Mode 1: Retrieve existing verified skill
        if mode in ("auto", "retrieve_skill"):
            for name, sk in skills.items():
                if name.lower() in goal_lower:
                    prog = sk.typed_program if hasattr(sk, "typed_program") else sk.get("typed_program", {})
                    op_name = prog.get("op", "sort")
                    py_line = self.OP_TO_PYTHON.get(op_name, "return x")
                    code = f"def transform(x: list) -> list:\n    {py_line}\n    return x\n"
                    return dict(
                        mode="retrieve_skill",
                        skill_name=name,
                        typed_program=prog,
                        python_code=code,
                    )

        # Mode 2: Compose existing typed programs
        if mode in ("auto", "compose_programs") and ops:
            valid_ops = [o for o in ops if o in self.OP_TO_PYTHON]
            if valid_ops:
                tree = foundation_programs.pipeline(valid_ops)
                body = "\n".join(f"    {self.OP_TO_PYTHON[o]}" for o in valid_ops)
                code = f"def transform(x: list) -> list:\n{body}\n    return x\n"
                return dict(
                    mode="compose_programs",
                    operators=valid_ops,
                    typed_program=tree,
                    python_code=code,
                )

        # Mode 3: Constrained code patch generation from examples
        examples = task_spec.Success_tests if hasattr(task_spec, "Success_tests") else task_spec.success_tests
        for cand_prog in ir.catalogue("list"):
            if examples and all(
                isinstance(ex, dict) and "input" in ex and "output" in ex and ir.run(cand_prog, ex["input"]) == ex["output"]
                for ex in examples
            ):
                ops_seq = cand_prog.get("ops", [])
                body = "\n".join(f"    {self.OP_TO_PYTHON.get(s, 'x = x')}" for s in ops_seq) or "    x = x"
                code = f"def transform(x: list) -> list:\n{body}\n    return x\n"
                return dict(
                    mode="generate_patch",
                    typed_program=cand_prog,
                    python_code=code,
                )

        # Fallback identity patch
        return dict(
            mode="generate_patch",
            typed_program=dict(schema="list", ops=["sort"]),
            python_code="def transform(x: list) -> list:\n    x = sorted(x)\n    return x\n",
        )


class ExecutionSandbox:
    """Runs bounded verification checks on candidate code and typed programs:
    - syntax check
    - lint / static analysis
    - security / resource limits
    - type / contract checks
    - unit tests & expected output behavioral checks
    """

    def verify(self, python_code: str, typed_program: dict | None = None, unit_tests: list[dict] | None = None) -> dict:
        checks = dict(
            syntax_check=dict(passed=False, details=""),
            lint_static_analysis=dict(passed=False, issues=[]),
            security_resource_limits=dict(passed=False, violations=[]),
            type_contract_check=dict(passed=False, details=""),
            unit_and_behavioral_tests=dict(passed=False, results=[]),
        )

        # 1. Syntax check
        try:
            tree = ast.parse(python_code)
            checks["syntax_check"] = dict(passed=True, details="valid_python_ast")
        except SyntaxError as exc:
            checks["syntax_check"] = dict(passed=False, details=f"SyntaxError: {exc.msg} at line {exc.lineno}")
            return dict(passed=False, checks=checks, failure_stage="syntax_check")

        # 2. Lint / static analysis & 3. Security / resource limits
        lint_issues = []
        security_violations = []
        has_function = False
        has_return = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_function = True
                if len(node.body) > 32:
                    security_violations.append("function_body_exceeds_32_statements")
            elif isinstance(node, ast.Return):
                has_return = True
            elif isinstance(node, ast.While):
                security_violations.append("unbounded_while_loop_forbidden")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in getattr(node, "names", [])]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for n in names:
                    if n.split(".")[0] in FORBIDDEN_IMPORTS:
                        security_violations.append(f"forbidden_import:{n}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_AST_CALLS:
                    security_violations.append(f"forbidden_call:{node.func.id}")
                elif isinstance(node.func, ast.Attribute) and node.func.attr.startswith("__"):
                    security_violations.append(f"forbidden_dunder_access:{node.func.attr}")

        if not has_function:
            lint_issues.append("missing_function_definition")
        if not has_return:
            lint_issues.append("missing_return_statement")

        checks["lint_static_analysis"] = dict(passed=len(lint_issues) == 0, issues=lint_issues)
        checks["security_resource_limits"] = dict(passed=len(security_violations) == 0, violations=security_violations)
        if lint_issues or security_violations:
            return dict(
                passed=False,
                checks=checks,
                failure_stage="security_resource_limits" if security_violations else "lint_static_analysis",
            )

        # 4. Type / contract check & 5. Unit / behavioral tests using pure bounded interpreter
        test_results = []
        all_tests_passed = True
        type_ok = True

        for t in (unit_tests or []):
            inp = t["input"]
            expected = t["output"]
            try:
                if typed_program and "schema" in typed_program:
                    ir.value(typed_program["schema"], inp)
                    actual = ir.run(typed_program, inp)
                elif typed_program:
                    out = foundation_programs.execute(typed_program, {"x": inp}, budget=128)
                    actual = out["value"]
                else:
                    actual = self._run_restricted_ast_transform(tree, inp)
                if type(actual) is not type(expected):
                    type_ok = False
                matched = actual == expected
                if not matched:
                    all_tests_passed = False
                test_results.append(dict(input=inp, expected=expected, actual=actual, passed=matched))
            except Exception as exc:
                type_ok = False
                all_tests_passed = False
                test_results.append(dict(input=inp, expected=expected, error=str(exc), passed=False))

        checks["type_contract_check"] = dict(passed=type_ok, details="output_types_match_contract" if type_ok else "type_or_domain_error")
        checks["unit_and_behavioral_tests"] = dict(passed=all_tests_passed, results=test_results)
        overall = all(c["passed"] for c in checks.values())
        return dict(
            passed=overall,
            checks=checks,
            failure_stage=None if overall else "unit_and_behavioral_tests",
        )

    @staticmethod
    def _run_restricted_ast_transform(tree: ast.Module, inp: Any) -> Any:
        """Executes a verified restricted AST function over a copied list input without builtins."""
        x = copy.deepcopy(inp)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        src = ast.unparse(stmt.value).strip()
                        if src == "sorted(x)":
                            x = sorted(x)
                        elif src == "list(reversed(x))" or src == "x[::-1]":
                            x = list(reversed(x))
                        elif src == "list(dict.fromkeys(x))":
                            x = list(dict.fromkeys(x))
                        elif "v % 2 == 0" in src:
                            x = [v for v in x if v % 2 == 0]
                        elif "v + 1" in src:
                            x = [v + 1 for v in x]
                        elif "v - 1" in src:
                            x = [v - 1 for v in x]
                    elif isinstance(stmt, ast.Return):
                        ret_src = ast.unparse(stmt.value).strip()
                        if ret_src == "sorted(x)":
                            return sorted(x)
                        if ret_src in ("list(reversed(x))", "x[::-1]"):
                            return list(reversed(x))
                        return x
        return x


class DebuggingController:
    """Implements the closed-loop debugging workflow:
    Observe failure -> localize fault -> generate cause hypotheses ->
    run minimal diagnostic test -> apply smallest repair ->
    re-run full test suite -> store debugging lesson (DebuggingSkill).

    Supported repair actions:
    - repair_syntax
    - change_implementation
    - revise_specification
    - request_clarification
    - revert
    """

    REPAIR_ACTIONS = (
        "repair_syntax",
        "change_implementation",
        "revise_specification",
        "request_clarification",
        "revert",
    )

    def __init__(self, sandbox: ExecutionSandbox | None = None, synthesizer: ProgramSynthesizer | None = None):
        self.sandbox = sandbox or ExecutionSandbox()
        self.synthesizer = synthesizer or ProgramSynthesizer()

    def debug_and_repair(
        self,
        broken_code: str,
        unit_tests: list[dict],
        typed_program: dict | None = None,
        previous_working_code: str | None = None,
    ) -> dict:
        initial_report = self.sandbox.verify(broken_code, typed_program=typed_program, unit_tests=unit_tests)
        if initial_report["passed"]:
            return dict(
                status="already_passing",
                action_taken=None,
                repaired_code=broken_code,
                verification=initial_report,
                debugging_skill=None,
            )

        failure_stage = initial_report["failure_stage"]
        trace = [f"observe_failure: stage={failure_stage}"]

        # Case 1: Syntax failure -> repair_syntax
        if failure_stage == "syntax_check" or initial_report["checks"]["lint_static_analysis"]["issues"]:
            trace.append("localize_fault: syntax_or_missing_return")
            trace.append("hypothesis: missing colon, indentation, or return statement")
            repaired_lines = []
            for line in broken_code.splitlines():
                stripped = line.strip()
                if stripped.startswith("def ") and not stripped.endswith(":"):
                    line = line + ":"
                repaired_lines.append(line)
            if not any(l.strip().startswith("return ") for l in repaired_lines):
                repaired_lines.append("    return x")
            repaired_code = "\n".join(repaired_lines) + "\n"
            recheck = self.sandbox.verify(repaired_code, typed_program=typed_program, unit_tests=unit_tests)
            if recheck["passed"]:
                skill = self.extract_debugging_skill(
                    symptom="SyntaxError or missing return in transform function",
                    diagnostic_tests=unit_tests[:1],
                    likely_causes=["Missing function header colon", "Omitted return statement"],
                    repair_action="repair_syntax",
                    before_code=broken_code,
                    after_code=repaired_code,
                )
                return dict(
                    status="repaired",
                    action_taken="repair_syntax",
                    trace=trace + ["re_run_full_test_suite: passed"],
                    repaired_code=repaired_code,
                    verification=recheck,
                    debugging_skill=skill.to_dict(),
                )

        # Case 2: Behavioral / unit test failure -> check if examples are contradictory
        if not unit_tests:
            return dict(
                status="needs_clarification",
                action_taken="request_clarification",
                trace=trace + ["no_unit_tests_supplied"],
                repaired_code=broken_code,
                verification=initial_report,
                debugging_skill=None,
            )

        # Check for conflicting expected outputs on identical inputs (specification bug)
        seen_inputs: dict[str, Any] = {}
        for t in unit_tests:
            k = repr(t["input"])
            if k in seen_inputs and seen_inputs[k] != t["output"]:
                return dict(
                    status="specification_conflict",
                    action_taken="revise_specification",
                    trace=trace + [f"contradictory_test_outputs_for_input:{k}"],
                    repaired_code=broken_code,
                    verification=initial_report,
                    debugging_skill=None,
                )
            seen_inputs[k] = t["output"]

        # Try change_implementation via bounded program synthesis over diagnostic test
        trace.append("localize_fault: implementation_operator_mismatch")
        trace.append("run_minimal_diagnostic_test: searching verified list operators matching unit_tests[0]")
        spec = TaskSpec(
            goal="repair_implementation",
            inputs=dict(language="python"),
            expected_outputs="list",
            constraints=["pure_function"],
            success_tests=unit_tests,
            permitted_actions=["generate_patch"],
        )
        synth = self.synthesizer.synthesize(spec, mode="generate_patch")
        recheck = self.sandbox.verify(synth["python_code"], typed_program=synth["typed_program"], unit_tests=unit_tests)
        if recheck["passed"]:
            skill = self.extract_debugging_skill(
                symptom="Unit test output mismatch on sequence transformation",
                diagnostic_tests=unit_tests[:1],
                likely_causes=["Wrong list operator or wrong operator order"],
                repair_action="change_implementation",
                before_code=broken_code,
                after_code=synth["python_code"],
            )
            return dict(
                status="repaired",
                action_taken="change_implementation",
                trace=trace + ["apply_smallest_repair: change_implementation", "re_run_full_test_suite: passed"],
                repaired_code=synth["python_code"],
                typed_program=synth["typed_program"],
                verification=recheck,
                debugging_skill=skill.to_dict(),
            )

        # Case 3: Revert if a previous working version is available
        if previous_working_code is not None:
            return dict(
                status="reverted",
                action_taken="revert",
                trace=trace + ["no_candidate_patch_passed: reverting_to_previous_working_code"],
                repaired_code=previous_working_code,
                verification=initial_report,
                debugging_skill=None,
            )

        return dict(
            status="unresolved",
            action_taken="request_clarification",
            trace=trace + ["request_clarification: target behavior outside bounded operator catalog"],
            repaired_code=broken_code,
            verification=initial_report,
            debugging_skill=None,
        )

    @staticmethod
    def extract_debugging_skill(
        symptom: str,
        diagnostic_tests: list[dict],
        likely_causes: list[str],
        repair_action: str,
        before_code: str,
        after_code: str,
    ) -> DebuggingSkill:
        return DebuggingSkill(
            symptom=symptom,
            diagnostic_tests=diagnostic_tests,
            likely_causes=likely_causes,
            repair_pattern=dict(
                action=repair_action,
                before_snippet=before_code.strip(),
                after_snippet=after_code.strip(),
            ),
            applicability_conditions=["Pure list/sequence transformation function", "Deterministic unit test failure"],
            counterexamples=[dict(condition="Stateful I/O or external network side effects")],
        )
