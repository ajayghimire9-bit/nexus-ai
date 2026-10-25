"""Opt-in source regression collection guard; historical files stay unchanged.

Use -p nexus.wave24_pytest_guard. Conservative exclusions are printed in full.
This does not mark unexecuted tests as passing or alter the normal pytest suite.
"""
import ast
import re

try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass
try:
    import multiprocessing
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass
except Exception:
    pass

EXCLUSIONS = {}
AUDITED_SOURCE_FILES = {"test_wave24_quotient_soundness.py", "test_wave24_resource_host_and_runner.py",
                        "test_wave24_open_world_arena.py"}


def exclusion_reason(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None  # a syntax error must remain a visible collection failure
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in ("mps", "cuda") or "llama-server" in node.value:
                return "GPU/LLM code present; old allocation cannot authorize this run"
            if re.search(r"\bw(?:1[2-9]|2[0-3])f_", node.value):
                return "closed-wave assessment namespace present"
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if re.match(r"run_wave\d+", name) or re.match(r"run_.*(?:experiment|assessment|benchmark)$", name):
                return "historical experiment/assessment runner call present"
            if any(k.arg == "execute_metal_llm" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
                return "historical Metal experiment enabled"
    return None


def pytest_ignore_collect(collection_path, config):
    path = collection_path
    if path.name in AUDITED_SOURCE_FILES or not path.name.startswith("test_") or path.suffix != ".py":
        return None
    reason = exclusion_reason(path.read_text())
    if reason:
        EXCLUSIONS[str(path)] = reason
        return True
    return None


def pytest_report_header(config):
    return "Wave24 SOURCE-ONLY guard enabled; protected tests are excluded, not passed"


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_sep("=", "Protected historical test exclusions (not executed)")
    for path, reason in sorted(EXCLUSIONS.items()):
        terminalreporter.write_line(path+": "+reason)
    terminalreporter.write_line(f"{len(EXCLUSIONS)} files excluded conservatively; this is not an unfiltered full-suite pass.")
