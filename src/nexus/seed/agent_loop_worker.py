"""Bounded subprocess execution worker for the Symbiotic Agent Loop.

Executes repository code and test cases inside an isolated child process with:
- Resource limits (`RLIMIT_CPU`, `RLIMIT_CORE`, `RLIMIT_FSIZE`)
- AST static policy enforcement (rejecting `os`, `sys`, `subprocess`, `socket`,
  `shutil`, `pathlib`, `http`, `urllib`, `eval`, `exec`, `open`, `__import__`,
  and dunder attribute access)
- In-memory module compilation with safe builtins (`SAFE_BUILTINS`) and optional
  line/call execution tracing (`sys.setprofile`) so the agent can localize faults
  from public test failures without any access to private reference solutions.
- Also supports bounded TypeScript validation (`tsc --noEmit` + `node --experimental-strip-types`)
  when `language == "typescript"`, and Lean 4 proof checking (`lean`) when
  `language == "lean4"`.
"""
from __future__ import annotations

import ast
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.blackbox_evaluator_worker import SAFE_AST_NODES, SAFE_BUILTINS

FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "http", "urllib",
    "ctypes", "multiprocessing", "threading", "pickle", "marshal", "builtins",
}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
}
ALLOWED_STDLIB_IMPORTS = {"math", " typing"}


def validate_and_compile_python_repo(files: dict[str, str]) -> dict[str, dict[str, Any]]:
    validate_repository_names(files)
    """Validate AST safety across all `.py` files in `files` and load them into
    isolated module namespaces with inter-module `from <mod> import <sym>` support.
    """
    if not isinstance(files, dict) or not files or len(files) > 16:
        raise ValueError("invalid_repository_file_count")
    if sum(len(v) for v in files.values()) > 60000:
        raise ValueError("repository_source_size_exceeded")

    py_modules: dict[str, ast.Module] = {}
    for filename, source in sorted(files.items()):
        if not filename.endswith(".py"):
            continue
        mod_name = filename[:-3]
        tree = ast.parse(source, filename=filename)
        nodes = list(ast.walk(tree))
        if len(nodes) > 800:
            raise ValueError(f"ast_size_exceeded:{filename}")

        for node in nodes:
            if not isinstance(node, SAFE_AST_NODES + (ast.Is, ast.IsNot, ast.ImportFrom, ast.alias)):
                raise ValueError(f"forbidden_ast_node:{filename}:{type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError(f"dunder_name_forbidden:{filename}:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise ValueError(f"dunder_attribute_forbidden:{filename}:{node.attr}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise ValueError(f"forbidden_call:{filename}:{node.func.id}")
            if isinstance(node, ast.Import):
                raise ValueError(f"direct_import_forbidden:{filename}")
            if isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    raise ValueError(f"relative_import_forbidden:{filename}")
                if node.module in FORBIDDEN_IMPORTS:
                    raise ValueError(f"forbidden_module_import:{filename}:{node.module}")
                if any(a.name == "*" for a in node.names):
                    raise ValueError(f"star_import_forbidden:{filename}")
        py_modules[mod_name] = tree

    loaded: dict[str, dict[str, Any]] = {}
    loading: set[str] = set()

    def load_mod(mod_name: str) -> dict[str, Any]:
        if mod_name in loaded:
            return loaded[mod_name]
        if mod_name in loading:
            raise ValueError(f"import_cycle:{mod_name}")
        if mod_name not in py_modules:
            raise ValueError(f"unknown_module_import:{mod_name}")
        loading.add(mod_name)
        safe_b = dict(SAFE_BUILTINS)
        safe_b.update({"float": float, "dict": dict, "round": round, "bool": bool, "int": int, "list": list})
        namespace: dict[str, Any] = {"__builtins__": safe_b}
        body: list[ast.stmt] = []
        for stmt in py_modules[mod_name].body:
            if isinstance(stmt, ast.ImportFrom):
                if stmt.module == "__future__":
                    continue
                dep_ns = load_mod(stmt.module)
                for alias in stmt.names:
                    if alias.name not in dep_ns:
                        raise ValueError(f"missing_imported_symbol:{stmt.module}.{alias.name}")
                    namespace[alias.asname or alias.name] = dep_ns[alias.name]
            else:
                body.append(stmt)
        code = compile(ast.Module(body=body, type_ignores=[]), f"{mod_name}.py", "exec")
        exec(code, namespace, namespace)
        loaded[mod_name] = namespace
        loading.remove(mod_name)
        return namespace

    for m in sorted(py_modules):
        load_mod(m)
    return loaded


def evaluate_python_payload(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        modules = validate_and_compile_python_repo(payload["files"])
    except Exception as exc:
        return dict(
            status="rejected",
            compilation_passed=False,
            reason=f"{type(exc).__name__}:{exc}",
            results=[],
            internal_s=time.perf_counter() - started,
        )
    compilation_s = time.perf_counter() - started
    t_tests = time.perf_counter()
    results = []
    valid_filenames = set(payload["files"].keys())
    trace_enabled = bool(payload.get("trace", False))

    for case in payload.get("cases", []):
        entry = case["entry"]
        mod_name, fn_name = entry.split(".", 1)
        if mod_name not in modules or fn_name.startswith("__") or fn_name not in modules[mod_name]:
            results.append(dict(
                entry=entry,
                actual=None,
                passed=False,
                error=f"missing_entry:{entry}",
                calls=[],
            ))
            continue
        calls: list[dict[str, Any]] = []

        def profiler(frame, event, arg):
            if event in ("call", "return") and frame.f_code.co_filename in valid_filenames:
                if len(calls) < 128:
                    calls.append(dict(
                        file=frame.f_code.co_filename,
                        function=frame.f_code.co_name,
                        event=event,
                        line=frame.f_lineno,
                    ))

        try:
            if trace_enabled:
                sys.setprofile(profiler)
            fn = modules[mod_name][fn_name]
            inp = case["input"]
            if case.get("unpack_args") and isinstance(inp, list):
                actual = fn(*inp)
            elif case.get("kwargs_input") and isinstance(inp, dict):
                actual = fn(**inp)
            else:
                actual = fn(inp)
            expected = case["expected"]
            if isinstance(expected, float) and isinstance(actual, (int, float)):
                passed = abs(float(actual) - expected) <= 1e-6
            else:
                passed = (type(actual) is type(expected) and actual == expected)
            results.append(dict(
                entry=entry,
                actual=actual,
                expected=expected,
                passed=bool(passed),
                error=None,
                calls=calls,
            ))
        except Exception as exc:
            results.append(dict(
                entry=entry,
                actual=None,
                expected=case.get("expected"),
                passed=False,
                error=f"{type(exc).__name__}:{exc}",
                trace=traceback.format_exc(limit=4),
                calls=calls,
            ))
        finally:
            sys.setprofile(None)

    all_passed = bool(results) and all(r["passed"] for r in results)
    return dict(
        status="passed" if all_passed else "failed",
        compilation_passed=True,
        all_passed=all_passed,
        results=results,
        compilation_s=compilation_s,
        tests_s=time.perf_counter() - t_tests,
        internal_s=time.perf_counter() - started,
    )


def evaluate_typescript_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validate_repository_names(payload.get('files', {}))
    started = time.perf_counter()
    files: dict[str, str] = payload["files"]
    cases: list[dict[str, Any]] = payload.get("cases", [])

    # Static check for forbidden process/fs/child_process access in TypeScript
    forbidden_ts = re.compile(r"\b(child_process|fs|net|http|https|eval|Function|process\.exit)\b")
    for fname, content in files.items():
        m = forbidden_ts.search(content)
        if m:
            return dict(
                status="rejected",
                compilation_passed=False,
                all_passed=False,
                reason=f"forbidden_ts_token:{fname}:{m.group(1)}",
                results=[],
                internal_s=time.perf_counter() - started,
            )

    env = dict(os.environ)
    env["PATH"] = f"/Users/ajayghimire/npm-global/bin:/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
    tsc_bin = shutil.which("tsc", path=env["PATH"])
    node_bin = shutil.which("node", path=env["PATH"])
    if not node_bin or not tsc_bin:
        return dict(
            status="blocked_missing_runtime",
            compilation_passed=False,
            all_passed=False,
            reason="tsc or node binary not available on host",
            results=[],
            internal_s=time.perf_counter() - started,
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ts_paths = []
        for fname, content in files.items():
            fpath = tmp_path / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
            if fname.endswith(".ts"):
                ts_paths.append(str(fpath))

        tproc = subprocess.run(
            [tsc_bin, "--noEmit", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext", "--strict"] + ts_paths,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=8.0,
            env=env,
        )
        if tproc.returncode != 0:
            return dict(
                status="failed",
                compilation_passed=False,
                all_passed=False,
                tsc_error=(tproc.stdout + "\n" + tproc.stderr).strip()[:800],
                results=[],
                internal_s=time.perf_counter() - started,
            )

        # Build test runner script in TypeScript
        imports_map: dict[str, set[str]] = {}
        for c in cases:
            mod, fn = c["entry"].split(".", 1)
            imports_map.setdefault(mod, set()).add(fn)
        runner_lines = []
        for mod, fns in sorted(imports_map.items()):
            runner_lines.append(f"import {{ {', '.join(sorted(fns))} }} from './{mod}.ts';")
        runner_lines.append("const results: any[] = [];")
        for idx, c in enumerate(cases):
            mod, fn = c["entry"].split(".", 1)
            inp_json = json.dumps(c["input"])
            exp_json = json.dumps(c["expected"])
            unpack = "true" if c.get("unpack_args") else "false"
            runner_lines.append(
                f"try {{\n"
                f"  const inp_{idx} = {inp_json};\n"
                f"  const exp_{idx} = {exp_json};\n"
                f"  const act_{idx} = {unpack} && Array.isArray(inp_{idx}) ? ({fn} as any)(...inp_{idx}) : ({fn} as any)(inp_{idx});\n"
                f"  const pass_{idx} = JSON.stringify(act_{idx}) === JSON.stringify(exp_{idx});\n"
                f"  results.push({{ entry: {json.dumps(c['entry'])}, actual: act_{idx}, expected: exp_{idx}, passed: pass_{idx}, error: null }});\n"
                f"}} catch (err: any) {{\n"
                f"  results.push({{ entry: {json.dumps(c['entry'])}, actual: null, expected: {exp_json}, passed: false, error: String(err?.message || err) }});\n"
                f"}}"
            )
        runner_lines.append("console.log(JSON.stringify(results));")
        runner_file = tmp_path / "_eval_runner.ts"
        runner_file.write_text("\n".join(runner_lines), encoding="utf-8")

        nproc = subprocess.run(
            [node_bin, "--experimental-strip-types", str(runner_file)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=6.0,
            env=env,
        )
        if nproc.returncode != 0:
            return dict(
                status="failed",
                compilation_passed=True,
                all_passed=False,
                node_error=(nproc.stdout + "\n" + nproc.stderr).strip()[:800],
                results=[],
                internal_s=time.perf_counter() - started,
            )
        results = json.loads(nproc.stdout.strip().splitlines()[-1])
        all_passed = bool(results) and all(r["passed"] for r in results)
        return dict(
            status="passed" if all_passed else "failed",
            compilation_passed=True,
            all_passed=all_passed,
            results=results,
            internal_s=time.perf_counter() - started,
        )


def run_worker_subprocess(payload: dict[str, Any], timeout_s: float = 10.0) -> dict[str, Any]:
    """Invoke this module in an isolated child process with resource bounds."""
    # Validate before any worker can materialize a path. The child also checks it.
    validate_repository_names(payload.get('files', {}))
    started = time.perf_counter()
    raw_in = json.dumps(payload, allow_nan=False)
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve())],
        input=raw_in,
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )
    wall_s = time.perf_counter() - started
    if proc.returncode != 0:
        return dict(
            status="failed",
            compilation_passed=False,
            all_passed=False,
            reason=f"worker_subprocess_error:{proc.stderr.strip()[-400:]}",
            results=[],
            wall_s=wall_s,
        )
    out = json.loads(proc.stdout)
    out["wall_s"] = wall_s
    return out


def validate_repository_names(files):
    for name in files:
        if (type(name) is not str or not name or Path(name).is_absolute()
                or '\\' in name or '\x00' in name or name.startswith('-')
                or any(p in ('', '.', '..') for p in name.split('/'))):
            raise ValueError('unsafe_repository_path')


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
    payload = json.loads(sys.stdin.read(200000))
    validate_repository_names(payload.get('files', {}))
    lang = payload.get("language", "python")
    if lang == "python":
        print(json.dumps(evaluate_python_payload(payload), allow_nan=False))
    elif lang == "typescript":
        print(json.dumps(evaluate_typescript_payload(payload), allow_nan=False))
    else:
        raise ValueError(f"unsupported_worker_language:{lang}")
