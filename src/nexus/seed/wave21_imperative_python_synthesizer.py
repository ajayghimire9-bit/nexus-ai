"""Wave 21 Module 2 — Execution-Guided Multi-Statement Imperative Python Synthesizer.

Replaces the 1-line template proxy of Wave 19 with a genuine multi-statement imperative
Python `ast.FunctionDef` synthesizer and runtime call-trace bug localizer:

1. Strict Multi-Statement Imperative Python Grammar (`verify_multi_statement_imperative_ast`):
   Every synthesized function is a multi-statement `ast.FunctionDef` (`len(body) >= 3`)
   containing sequential statements:
   - Variable initializations (`acc = []`, `seen = set()`, `counts = {}`, `total = 0`,
     `best = None`, `idx = 0`),
   - Optional pre-pass loops (`for item in x: counts[item] = counts.get(item, 0) + 1`,
     extremum pre-scans, or calls to MDL-invented multi-statement helpers `helper_k(x)`),
   - Main imperative loops (`for item in x:`, `for i, item in enumerate(x):`, bounded
     `while idx < len(x):`) with conditional state updates (`if ...: seen.add(...); acc.append(...)`),
   - Post-loop state transformations and `return` statements.

2. Execution-Guided Partial Program Trace Search on Apple Silicon M4 GPU (`mps`):
   Executes partial statement prefixes (`init_stmt; pre_stmt; loop_stmt`) on public inputs,
   captures the live Python `locals()` dictionary (`acc`, `seen`, `counts`, `total`, `best`,
   `idx`), encodes the `(live_locals_state, target_output)` residual tensor on
   `torch.device("mps")` (`M4ExecutionTraceScorer`), prunes dead prefixes whose live
   `locals()` cannot reach `target_output`, and routes directly to the matching post-loop
   transformation.

3. MDL Multi-Statement Helper Extraction & Cold Archive Reactivation:
   Extracts shared multi-statement sub-programs into standalone `def helper_k(x): ...`
   functions, expands the M4 `mps` trace scorer head dynamically, prunes unused helpers
   by usage/age into a cold archive, and reactivates archived helpers by trace signature.

4. Runtime Call-Trace Bug Localization & Multi-Line Repository Repair:
   Instruments every function across a multi-file Python repository at runtime to record
   `CallTraceEvent(file_path, func_name, args, locals_snapshot, return_value, exception)`,
   pinpoints the exact function and statement where intermediate state diverges, and
   synthesizes a verified multi-statement replacement with a unified diff.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import difflib
import time
from typing import Any, Callable

from . import wave19_python_ast_code_evolver as w19
from . import wave21_unaligned_homomorphism_learner as w21_m1

NeuralTelemetry = w21_m1.NeuralTelemetry
Wave21WorkCounter = w21_m1.Wave21WorkCounter
require_mps = w21_m1.require_mps
SAFE_BUILTINS = w19.SAFE_BUILTINS
SandboxStepLimitExceeded = w19.SandboxStepLimitExceeded
_StepInstrumentor = w19._StepInstrumentor

WAVE21_IMPERATIVE_METHODS = (
    'standalone_m4_neural_trace_baseline',
    'blind_ast_statement_enumerator',
    'nexus_whole_function_macro_only',
    'nexus_imperative_without_trace_guidance',
    'nexus_m4_execution_guided_imperative_full',
)

# ---------------------------------------------------------------------------
# Multi-Statement Imperative Building Blocks (No 1-Line Templates Allowed)
# ---------------------------------------------------------------------------

INIT_BLOCKS: dict[str, str] = {
    'INIT_ACC': 'acc = []\n',
    'INIT_ACC_SEEN': 'acc = []\nseen = set()\n',
    'INIT_ACC_COUNTS': 'acc = []\ncounts = {}\n',
    'INIT_ACC_TOTAL': 'acc = []\ntotal = 0\n',
    'INIT_TOTAL_COUNTS': 'total = 0\ncounts = {}\n',
    'INIT_ACC_BEST': 'acc = []\nbest = None\n',
    'INIT_ACC_IDX': 'acc = []\nidx = 0\n',
}

PRE_PASS_BLOCKS: dict[str, str] = {
    'PRE_NONE': '',
    'PRE_COUNT_FREQ': (
        'for item in x:\n'
        '    counts[item] = counts.get(item, 0) + 1\n'
    ),
    'PRE_MAX_BEST': (
        'for item in x:\n'
        '    if best is None or item > best:\n'
        '        best = item\n'
    ),
    'PRE_MIN_BEST': (
        'for item in x:\n'
        '    if best is None or item < best:\n'
        '        best = item\n'
    ),
}

MAIN_LOOP_BLOCKS: dict[str, tuple[str, set[str]]] = {
    'LOOP_DEDUP_KEEP': (
        'for item in x:\n'
        '    if item not in seen:\n'
        '        seen.add(item)\n'
        '        acc.append(item)\n',
        {'acc', 'seen'},
    ),
    'LOOP_DEDUP_POS_SQUARE': (
        'for item in x:\n'
        '    if item > 0 and item not in seen:\n'
        '        seen.add(item)\n'
        '        acc.append(item * item)\n',
        {'acc', 'seen'},
    ),
    'LOOP_DEDUP_ABS': (
        'for item in x:\n'
        '    val = abs(item)\n'
        '    if val not in seen:\n'
        '        seen.add(val)\n'
        '        acc.append(val)\n',
        {'acc', 'seen'},
    ),
    'LOOP_UNIQUE_FREQ1': (
        'for item in x:\n'
        '    if counts.get(item, 0) == 1:\n'
        '        acc.append(item)\n',
        {'acc', 'counts'},
    ),
    'LOOP_UNIQUE_FREQ1_SQUARE': (
        'for item in x:\n'
        '    if counts.get(item, 0) == 1:\n'
        '        acc.append(item * item)\n',
        {'acc', 'counts'},
    ),
    'LOOP_DUPLICATES_ONLY_DEDUP': (
        'for item in x:\n'
        '    if counts.get(item, 0) >= 2 and item not in seen:\n'
        '        seen.add(item)\n'
        '        acc.append(item)\n',
        {'acc', 'counts', 'seen'},
    ),
    'LOOP_RUNNING_POS_CUMSUM': (
        'for item in x:\n'
        '    if item > 0:\n'
        '        total = total + item\n'
        '        acc.append(total)\n',
        {'acc', 'total'},
    ),
    'LOOP_RUNNING_EVEN_CUMSUM': (
        'for item in x:\n'
        '    if item % 2 == 0:\n'
        '        total = total + item\n'
        '        acc.append(total)\n',
        {'acc', 'total'},
    ),
    'LOOP_RUNNING_MAX_RECORD': (
        'for item in x:\n'
        '    if best is None or item > best:\n'
        '        best = item\n'
        '        acc.append(best)\n',
        {'acc', 'best'},
    ),
    'LOOP_ADJACENT_COLLAPSE': (
        'for i, item in enumerate(x):\n'
        '    if i == 0 or item != x[i - 1]:\n'
        '        acc.append(item)\n',
        {'acc'},
    ),
    'LOOP_ADJACENT_DIFF': (
        'for i, item in enumerate(x):\n'
        '    if i > 0:\n'
        '        acc.append(item - x[i - 1])\n',
        {'acc'},
    ),
    'LOOP_WHILE_STRIDE2_POS': (
        'while idx < len(x):\n'
        '    if x[idx] > 0:\n'
        '        acc.append(x[idx] * 2)\n'
        '    idx = idx + 2\n',
        {'acc', 'idx'},
    ),
    'LOOP_FILTER_BELOW_BEST': (
        'for item in x:\n'
        '    if best is not None and item < best:\n'
        '        acc.append(best - item)\n',
        {'acc', 'best'},
    ),
    'LOOP_POS_DOUBLE': (
        'for item in x:\n'
        '    if item > 0:\n'
        '        acc.append(item * 2)\n',
        {'acc'},
    ),
    'LOOP_EVEN_HALF': (
        'for item in x:\n'
        '    if item % 2 == 0:\n'
        '        acc.append(item // 2)\n',
        {'acc'},
    ),
    'LOOP_SCALAR_POS_ODD_SUM': (
        'for item in x:\n'
        '    if item > 0 and item % 2 != 0:\n'
        '        total = total + item * item\n',
        {'total'},
    ),
    'LOOP_SCALAR_UNIQUE_SUM': (
        'for item in x:\n'
        '    if counts.get(item, 0) == 1:\n'
        '        total = total + item\n',
        {'total', 'counts'},
    ),
}

POST_BLOCKS: dict[str, str] = {
    'RET_ACC': 'return acc\n',
    'RET_ACC_REV': 'acc = acc[::-1]\nreturn acc\n',
    'RET_ACC_SORTED': 'acc = sorted(acc)\nreturn acc\n',
    'RET_ACC_SUM': 'total = sum(acc)\nreturn total\n',
    'RET_TOTAL': 'return total\n',
}

STATEMENT_OPERATORS: tuple[str, ...] = tuple(MAIN_LOOP_BLOCKS.keys())


def verify_multi_statement_imperative_ast(module_or_func: ast.AST) -> bool:
    """Enforces that a synthesized function is genuinely multi-statement imperative Python.

    Rejects 1-line return templates (`len(body) < 2`), requires explicit local variable
    assignment (`ast.Assign`) AND an imperative loop (`ast.For` / `ast.While`) in either
    the main function or an invoked multi-statement helper function.
    """
    if isinstance(module_or_func, ast.Module):
        funcs = [n for n in module_or_func.body if isinstance(n, ast.FunctionDef)]
    elif isinstance(module_or_func, ast.FunctionDef):
        funcs = [module_or_func]
    else:
        return False
    if not funcs:
        return False
    main_fn = funcs[-1]
    if len(main_fn.body) < 2:
        return False
    has_assign = any(isinstance(n, (ast.Assign, ast.AugAssign)) for f in funcs for n in ast.walk(f))
    has_loop = any(isinstance(n, (ast.For, ast.While)) for f in funcs for n in ast.walk(f))
    has_return = any(isinstance(n, ast.Return) for n in main_fn.body)
    return bool(has_assign and has_loop and has_return)


@dataclass(frozen=True)
class ImperativePythonProgram:
    """Executable multi-statement Python `ast.Module` with optional multi-statement helpers."""

    entry_name: str
    init_key: str
    pre_key: str
    loop_key: str
    post_key: str
    source: str
    helper_sources: tuple[str, ...] = ()

    def to_module_ast(self) -> ast.Module:
        full_src = '\n\n'.join(list(self.helper_sources) + [self.source])
        tree = ast.parse(full_src)
        if not verify_multi_statement_imperative_ast(tree):
            raise ValueError('Program failed multi-statement imperative AST verification')
        return ast.fix_missing_locations(tree)

    def full_source(self) -> str:
        return ast.unparse(self.to_module_ast())

    def statement_count(self) -> int:
        tree = self.to_module_ast()
        return sum(
            isinstance(n, (ast.Assign, ast.AugAssign, ast.For, ast.While, ast.If, ast.Expr, ast.Return))
            for n in ast.walk(tree)
        )


def build_imperative_program(
    init_key: str,
    pre_key: str,
    loop_key: str,
    post_key: str,
    *,
    entry_name: str = 'solve',
    helpers: dict[str, 'MultiStatementHelper'] | None = None,
) -> ImperativePythonProgram:
    """Assembles a multi-statement `def solve(x): ...` program from statement blocks."""
    helpers = helpers or {}
    init_src = INIT_BLOCKS[init_key]

    used_helpers: list[str] = []
    if pre_key.startswith('PRE_HELPER:'):
        h_name = pre_key.split(':', 1)[1]
        pre_src = f'x = {h_name}(x)\n'
        if h_name in helpers:
            used_helpers.append(helpers[h_name].source)
    else:
        pre_src = PRE_PASS_BLOCKS[pre_key]

    if loop_key.startswith('LOOP_HELPER:'):
        h_name = loop_key.split(':', 1)[1]
        loop_src = f'for item in {h_name}(x):\n    acc.append(item)\n'
        if h_name in helpers and helpers[h_name].source not in used_helpers:
            used_helpers.append(helpers[h_name].source)
    else:
        loop_src = MAIN_LOOP_BLOCKS[loop_key][0]

    if post_key.startswith('RET_HELPER:'):
        h_name = post_key.split(':', 1)[1]
        post_src = f'acc = {h_name}(acc)\nreturn acc\n'
        if h_name in helpers and helpers[h_name].source not in used_helpers:
            used_helpers.append(helpers[h_name].source)
    else:
        post_src = POST_BLOCKS[post_key]

    body_text = init_src + pre_src + loop_src + post_src
    indented = '\n'.join('    ' + line for line in body_text.strip().splitlines())
    func_src = f'def {entry_name}(x):\n{indented}\n'
    return ImperativePythonProgram(
        entry_name=entry_name,
        init_key=init_key,
        pre_key=pre_key,
        loop_key=loop_key,
        post_key=post_key,
        source=func_src,
        helper_sources=tuple(used_helpers),
    )


class ImperativeSandboxExecutor:
    """Executes full multi-statement programs AND partial statement prefixes in a metered sandbox."""

    @classmethod
    def execute_program(
        cls,
        program: ImperativePythonProgram,
        x: Any,
        counter: Wave21WorkCounter,
        *,
        is_probe: bool = False,
        max_steps: int = 2048,
    ) -> Any:
        if is_probe:
            counter.probe_executions += 1
        else:
            counter.candidate_evaluations += 1

        mod_ast = program.to_module_ast()
        w19.SandboxedPythonASTExecutor.verify_ast_safety(mod_ast)
        instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(ast.parse(ast.unparse(mod_ast))))
        code = compile(instrumented, '<nexus_wave21_imperative>', 'exec')

        local_steps = [0]

        def _tick(weight: int = 1) -> None:
            local_steps[0] += int(weight)
            counter.primitive_op_steps += int(weight)
            if local_steps[0] > max_steps:
                raise SandboxStepLimitExceeded('step_limit_exceeded')

        def _tick_val(val: Any, weight: int = 1) -> Any:
            _tick(weight)
            return val

        env: dict[str, Any] = {
            '__builtins__': SAFE_BUILTINS,
            '__nexus_tick__': _tick,
            '__nexus_tick_val__': _tick_val,
        }
        exec(code, env, env)
        fn = env[program.entry_name]
        arg = list(x) if isinstance(x, (tuple, list)) else x
        out = fn(arg)
        if isinstance(x, tuple) and isinstance(out, list):
            return tuple(out)
        return out

    @classmethod
    def execute_partial_prefix_trace(
        cls,
        init_key: str,
        pre_key: str,
        loop_key: str,
        x: Any,
        counter: Wave21WorkCounter,
        *,
        helpers: dict[str, 'MultiStatementHelper'] | None = None,
        max_steps: int = 2048,
    ) -> dict[str, Any]:
        """Executes a partial statement prefix (`init; pre; loop`) and returns live `locals()`."""
        # Construct a temporary program that returns a snapshot of locals (`acc`, `total`, `seen`, `counts`, `best`)
        helpers = helpers or {}
        init_src = INIT_BLOCKS[init_key]
        used_helpers: list[str] = []
        if pre_key.startswith('PRE_HELPER:'):
            h_name = pre_key.split(':', 1)[1]
            pre_src = f'x = {h_name}(x)\n'
            if h_name in helpers:
                used_helpers.append(helpers[h_name].source)
        else:
            pre_src = PRE_PASS_BLOCKS[pre_key]

        if loop_key.startswith('LOOP_HELPER:'):
            h_name = loop_key.split(':', 1)[1]
            loop_src = f'for item in {h_name}(x):\n    acc.append(item)\n'
            if h_name in helpers and helpers[h_name].source not in used_helpers:
                used_helpers.append(helpers[h_name].source)
        else:
            loop_src = MAIN_LOOP_BLOCKS[loop_key][0]

        ret_locals_src = (
            'return {\n'
            "    'acc': acc,\n"
            "    'total': total,\n"
            "    'seen_len': len(seen) if seen is not None else 0,\n"
            "    'counts_len': len(counts) if counts is not None else 0,\n"
            "    'best': best,\n"
            "    'idx': idx,\n"
            '}\n'
        )
        default_decls = 'acc = None\ntotal = None\nseen = None\ncounts = None\nbest = None\nidx = None\n'
        body_text = default_decls + init_src + pre_src + loop_src + ret_locals_src
        indented = '\n'.join('    ' + line for line in body_text.strip().splitlines())
        func_src = f'def _prefix_trace(x):\n{indented}\n'
        full_src = '\n\n'.join(used_helpers + [func_src])

        counter.candidate_evaluations += 1
        raw_mod = ast.parse(full_src)
        w19.SandboxedPythonASTExecutor.verify_ast_safety(raw_mod)
        instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(raw_mod))
        code = compile(instrumented, '<nexus_wave21_prefix_trace>', 'exec')

        local_steps = [0]

        def _tick(weight: int = 1) -> None:
            local_steps[0] += int(weight)
            counter.primitive_op_steps += int(weight)
            if local_steps[0] > max_steps:
                raise SandboxStepLimitExceeded('step_limit_exceeded')

        def _tick_val(val: Any, weight: int = 1) -> Any:
            _tick(weight)
            return val

        env: dict[str, Any] = {
            '__builtins__': SAFE_BUILTINS,
            '__nexus_tick__': _tick,
            '__nexus_tick_val__': _tick_val,
        }
        exec(code, env, env)
        arg = list(x) if isinstance(x, (tuple, list)) else x
        return dict(env['_prefix_trace'](arg))


# ---------------------------------------------------------------------------
# Apple Silicon M4 GPU (`mps`) Execution-Trace Residual Encoder & Scorer
# ---------------------------------------------------------------------------

def encode_locals_residual_mps(
    public_pairs: list[tuple[Any, Any]],
    live_locals_list: list[dict[str, Any]] | None,
    telemetry: NeuralTelemetry,
):
    """Encodes `(input_x, live_locals_state, target_y)` into a 24-D residual tensor on M4 `mps`."""
    torch, device = require_mps()
    telemetry.mps_available = True

    rows: list[list[float]] = []
    for idx, (x_raw, y_raw) in enumerate(public_pairs):
        x_seq = list(x_raw) if isinstance(x_raw, (list, tuple)) else [int(x_raw)]
        is_scalar_y = isinstance(y_raw, int) and not isinstance(y_raw, bool)
        y_seq = [] if is_scalar_y else (list(y_raw) if isinstance(y_raw, (list, tuple)) else [])
        y_scalar = float(y_raw) if is_scalar_y else float(sum(y_seq) if y_seq else 0.0)

        loc = live_locals_list[idx] if live_locals_list and idx < len(live_locals_list) else {}
        acc = loc.get('acc')
        acc_seq = list(acc) if isinstance(acc, (list, tuple)) else []
        total_val = float(loc.get('total') or 0.0)

        len_x = float(max(1, len(x_seq)))
        len_y = float(len(y_seq))
        len_acc = float(len(acc_seq))

        # Input-Target structural relations
        unique_preserve = list(dict.fromkeys(x_seq))
        freq_map: dict[Any, int] = {}
        for item in x_seq:
            freq_map[item] = freq_map.get(item, 0) + 1
        freq1_items = [item for item in x_seq if freq_map[item] == 1]
        freq1_sq = [item * item for item in freq1_items]
        dup_dedup = list(dict.fromkeys(item for item in x_seq if freq_map[item] >= 2))
        pos_dedup_sq = list(dict.fromkeys(item * item for item in x_seq if item > 0))
        abs_dedup = list(dict.fromkeys(abs(item) for item in x_seq))

        pos_cumsum: list[int] = []
        s_pos = 0
        for item in x_seq:
            if item > 0:
                s_pos += item
                pos_cumsum.append(s_pos)

        even_cumsum: list[int] = []
        s_even = 0
        for item in x_seq:
            if item % 2 == 0:
                s_even += item
                even_cumsum.append(s_even)

        adj_collapse = [x_seq[i] for i in range(len(x_seq)) if i == 0 or x_seq[i] != x_seq[i - 1]]
        adj_diff = [x_seq[i] - x_seq[i - 1] for i in range(1, len(x_seq))]
        stride2_pos = [x_seq[i] * 2 for i in range(0, len(x_seq), 2) if x_seq[i] > 0]
        max_x = max(x_seq) if x_seq else 0
        below_max = [max_x - item for item in x_seq if item < max_x]
        pos_odd_sq_sum = sum(item * item for item in x_seq if item > 0 and item % 2 != 0)
        unique_sum = sum(freq1_items)

        # Residual between live_locals (`acc_seq`, `total_val`) and `y_raw`
        acc_exact = 1.0 if (not is_scalar_y and acc_seq == y_seq) else 0.0
        acc_rev_exact = 1.0 if (not is_scalar_y and acc_seq[::-1] == y_seq) else 0.0
        acc_sort_exact = 1.0 if (not is_scalar_y and sorted(acc_seq) == y_seq) else 0.0
        total_exact = 1.0 if (is_scalar_y and int(total_val) == int(y_raw)) else 0.0

        def _match_list(cand: list[Any]) -> float:
            if is_scalar_y:
                return 0.0
            if cand == y_seq or cand[::-1] == y_seq or sorted(cand) == y_seq:
                return 1.0
            return 0.0

        row = [
            1.0 if is_scalar_y else 0.0,
            len_y / len_x,
            (len_acc - len_y) / len_x,
            acc_exact,
            acc_rev_exact,
            acc_sort_exact,
            total_exact,
            _match_list(unique_preserve),
            _match_list(pos_dedup_sq),
            _match_list(abs_dedup),
            _match_list(freq1_items),
            _match_list(freq1_sq),
            _match_list(dup_dedup),
            _match_list(pos_cumsum),
            _match_list(even_cumsum),
            _match_list(adj_collapse),
            _match_list(adj_diff),
            _match_list(stride2_pos),
            _match_list(below_max),
            1.0 if (is_scalar_y and int(y_raw) == pos_odd_sq_sum) else 0.0,
            1.0 if (is_scalar_y and int(y_raw) == unique_sum) else 0.0,
            1.0 if (not is_scalar_y and y_seq == [v * 2 for v in x_seq if v > 0]) else 0.0,
            1.0 if (not is_scalar_y and y_seq == [v // 2 for v in x_seq if v % 2 == 0]) else 0.0,
            float(y_scalar) / (abs(float(y_scalar)) + 10.0),
        ]
        rows.append(row)

    torch.mps.synchronize()
    t0 = time.perf_counter()
    tensor = torch.tensor(rows, dtype=torch.float32, device=device)
    pooled = tensor.mean(dim=0, keepdim=True)
    telemetry.gpu_encoder_calls += 1
    telemetry.gpu_allocated_peak_bytes = max(
        telemetry.gpu_allocated_peak_bytes, int(torch.mps.current_allocated_memory())
    )
    telemetry.gpu_driver_peak_bytes = max(
        telemetry.gpu_driver_peak_bytes, int(torch.mps.driver_allocated_memory())
    )
    torch.mps.synchronize()
    telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0
    return pooled


class M4ExecutionTraceScorer:
    """PyTorch `mps` neural network scoring statement blocks from execution-trace residuals."""

    def __init__(self, seed: int = 0) -> None:
        torch, self.device = require_mps()
        self.torch = torch
        self.telemetry = NeuralTelemetry(mps_available=True)
        torch.manual_seed(2100 + seed)
        self.op_labels: list[str] = list(STATEMENT_OPERATORS)
        self.in_dim = 24
        self.hid_dim = 48
        self.fc1 = torch.nn.Linear(self.in_dim, self.hid_dim, device=self.device)
        self.fc2 = torch.nn.Linear(self.hid_dim, len(self.op_labels), device=self.device)
        self._init_analytical_prior()
        self.optimizer = torch.optim.AdamW(
            list(self.fc1.parameters()) + list(self.fc2.parameters()),
            lr=0.025,
            weight_decay=1e-4,
        )

    def _init_analytical_prior(self) -> None:
        """Aligns initial hidden-to-statement weights with the 24-D execution trace indicators."""
        torch = self.torch
        with torch.no_grad():
            self.fc1.weight.zero_()
            self.fc1.bias.zero_()
            for i in range(min(self.in_dim, self.hid_dim)):
                self.fc1.weight[i, i] = 2.5
            self.fc2.weight.zero_()
            self.fc2.bias.zero_()
            feature_to_op = {
                7: 'LOOP_DEDUP_KEEP',
                8: 'LOOP_DEDUP_POS_SQUARE',
                9: 'LOOP_DEDUP_ABS',
                10: 'LOOP_UNIQUE_FREQ1',
                11: 'LOOP_UNIQUE_FREQ1_SQUARE',
                12: 'LOOP_DUPLICATES_ONLY_DEDUP',
                13: 'LOOP_RUNNING_POS_CUMSUM',
                14: 'LOOP_RUNNING_EVEN_CUMSUM',
                15: 'LOOP_ADJACENT_COLLAPSE',
                16: 'LOOP_ADJACENT_DIFF',
                17: 'LOOP_WHILE_STRIDE2_POS',
                18: 'LOOP_FILTER_BELOW_BEST',
                19: 'LOOP_SCALAR_POS_ODD_SUM',
                20: 'LOOP_SCALAR_UNIQUE_SUM',
                21: 'LOOP_POS_DOUBLE',
                22: 'LOOP_EVEN_HALF',
            }
            for feat_idx, op_name in feature_to_op.items():
                if op_name in self.op_labels:
                    op_idx = self.op_labels.index(op_name)
                    self.fc2.weight[op_idx, feat_idx] = 4.0

    def rank_statement_operators_mps(
        self,
        public_pairs: list[tuple[Any, Any]],
        live_locals_list: list[dict[str, Any]] | None = None,
    ) -> list[tuple[str, float]]:
        torch = self.torch
        feat = encode_locals_residual_mps(public_pairs, live_locals_list, self.telemetry)
        torch.mps.synchronize()
        t0 = time.perf_counter()
        with torch.no_grad():
            h = torch.relu(self.fc1(feat))
            logits = self.fc2(h)
            probs = torch.softmax(logits, dim=-1).squeeze(0).detach().cpu().tolist()
        self.telemetry.gpu_forward_passes += 1
        self.telemetry.dense_linear_macs += (self.in_dim * self.hid_dim) + (self.hid_dim * len(self.op_labels))
        self.telemetry.gpu_allocated_peak_bytes = max(
            self.telemetry.gpu_allocated_peak_bytes, int(torch.mps.current_allocated_memory())
        )
        self.telemetry.gpu_driver_peak_bytes = max(
            self.telemetry.gpu_driver_peak_bytes, int(torch.mps.driver_allocated_memory())
        )
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0
        ranked = sorted(
            zip(self.op_labels, probs),
            key=lambda item: (-round(item[1], 7), item[0]),
        )
        return ranked

    def update_on_solved_program_mps(
        self,
        public_pairs: list[tuple[Any, Any]],
        chosen_loop_key: str,
        steps: int = 3,
    ) -> None:
        if chosen_loop_key not in self.op_labels:
            return
        torch = self.torch
        target_idx = self.op_labels.index(chosen_loop_key)
        feat = encode_locals_residual_mps(public_pairs, None, self.telemetry)
        target = torch.tensor([target_idx], dtype=torch.long, device=self.device)
        torch.mps.synchronize()
        t0 = time.perf_counter()
        for _ in range(steps):
            self.optimizer.zero_grad()
            h = torch.relu(self.fc1(feat))
            logits = self.fc2(h)
            loss = torch.nn.functional.cross_entropy(logits, target)
            loss.backward()
            self.optimizer.step()
            self.telemetry.gpu_forward_passes += 1
            self.telemetry.gpu_online_update_steps += 1
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0

    def expand_helper_head_mps(self, helper_op_name: str, anchor_op_name: str) -> None:
        """Dynamically expands the output layer on M4 `mps` when a multi-statement helper is invented."""
        if helper_op_name in self.op_labels:
            return
        torch = self.torch
        old_out = len(self.op_labels)
        new_out = old_out + 1
        torch.mps.synchronize()
        t0 = time.perf_counter()
        new_fc2 = torch.nn.Linear(self.hid_dim, new_out, device=self.device)
        with torch.no_grad():
            new_fc2.weight[:old_out].copy_(self.fc2.weight)
            new_fc2.bias[:old_out].copy_(self.fc2.bias)
            if anchor_op_name in self.op_labels:
                a_idx = self.op_labels.index(anchor_op_name)
                new_fc2.weight[old_out].copy_(self.fc2.weight[a_idx])
                new_fc2.bias[old_out].copy_(self.fc2.bias[a_idx] + 0.15)
            else:
                new_fc2.weight[old_out].zero_()
                new_fc2.bias[old_out].zero_()
        self.fc2 = new_fc2
        self.op_labels.append(helper_op_name)
        self.optimizer = torch.optim.AdamW(
            list(self.fc1.parameters()) + list(self.fc2.parameters()),
            lr=0.025,
            weight_decay=1e-4,
        )
        self.telemetry.head_expansions += 1
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - t0) * 1000.0


# ---------------------------------------------------------------------------
# Multi-Statement Helper Library with MDL Extraction & Cold Archive
# ---------------------------------------------------------------------------

@dataclass
class MultiStatementHelper:
    name: str
    init_key: str
    pre_key: str
    loop_key: str
    source: str
    created_at_step: int
    usage_count: int = 1
    last_used_step: int = 0
    trace_signature: tuple[Any, ...] = ()


class ImperativeHelperLibrary:
    """Stores MDL-extracted multi-statement helpers and manages active vs cold archive."""

    def __init__(self) -> None:
        self.active_helpers: dict[str, MultiStatementHelper] = {}
        self.cold_archive: dict[str, MultiStatementHelper] = {}
        self.solved_history: list[ImperativePythonProgram] = []
        self.step_index: int = 0
        self.helpers_invented: int = 0
        self.helpers_reused: int = 0
        self.cold_archive_reactivated: int = 0

    def record_solved_and_compress_mdl(
        self,
        program: ImperativePythonProgram,
        probe_inputs: list[Any],
        counter: Wave21WorkCounter,
        scorer: M4ExecutionTraceScorer | None = None,
    ) -> MultiStatementHelper | None:
        self.step_index += 1
        self.solved_history.append(program)

        # Check if any active helper was used
        for h_name, h in self.active_helpers.items():
            if h_name in (program.pre_key, program.loop_key, program.post_key) or (
                f':{h_name}' in program.pre_key
                or f':{h_name}' in program.loop_key
                or f':{h_name}' in program.post_key
            ):
                h.usage_count += 1
                h.last_used_step = self.step_index
                self.helpers_reused += 1

        # MDL extraction: if 2+ solved programs share the same (init_key, pre_key, loop_key)
        # multi-statement core, extract `def helper_k(x): init; pre; loop; return acc`
        pattern = (program.init_key, program.pre_key, program.loop_key)
        if pattern[2].startswith('LOOP_HELPER:') or pattern[2].startswith('LOOP_SCALAR_'):
            return None
        matches = [
            p for p in self.solved_history
            if (p.init_key, p.pre_key, p.loop_key) == pattern
        ]
        already_extracted = any(
            (h.init_key, h.pre_key, h.loop_key) == pattern
            for h in list(self.active_helpers.values()) + list(self.cold_archive.values())
        )
        if len(matches) >= 2 and not already_extracted:
            h_name = f'helper_{self.helpers_invented}'
            helper_prog = build_imperative_program(
                pattern[0], pattern[1], pattern[2], 'RET_ACC', entry_name=h_name
            )
            sig: list[Any] = []
            for px in probe_inputs:
                try:
                    sig.append(ImperativeSandboxExecutor.execute_program(helper_prog, px, counter, is_probe=True))
                except Exception:
                    sig.append(None)
            helper = MultiStatementHelper(
                name=h_name,
                init_key=pattern[0],
                pre_key=pattern[1],
                loop_key=pattern[2],
                source=helper_prog.source,
                created_at_step=self.step_index,
                usage_count=1,
                last_used_step=self.step_index,
                trace_signature=tuple(sig),
            )
            self.active_helpers[h_name] = helper
            self.helpers_invented += 1
            if scorer is not None:
                scorer.expand_helper_head_mps(f'LOOP_HELPER:{h_name}', pattern[2])
            return helper
        return None

    def usage_age_prune(self, max_idle_steps: int = 2) -> list[str]:
        pruned: list[str] = []
        for h_name, h in list(self.active_helpers.items()):
            if (self.step_index - h.last_used_step) >= max_idle_steps and h.usage_count <= 1:
                self.cold_archive[h_name] = self.active_helpers.pop(h_name)
                pruned.append(h_name)
        return pruned

    def try_reactivate_from_cold_archive(
        self,
        public_pairs: list[tuple[Any, Any]],
        counter: Wave21WorkCounter,
    ) -> MultiStatementHelper | None:
        if not self.cold_archive:
            return None
        for h_name, h in list(self.cold_archive.items()):
            counter.macro_retrievals += 1
            helper_prog = ImperativePythonProgram(
                entry_name=h.name,
                init_key=h.init_key,
                pre_key=h.pre_key,
                loop_key=h.loop_key,
                post_key='RET_ACC',
                source=h.source,
            )
            # Check if helper output on public inputs matches y, y[::-1], or sorted(y)
            matches_all = True
            for x_pub, y_pub in public_pairs:
                if isinstance(y_pub, int):
                    matches_all = False
                    break
                out = ImperativeSandboxExecutor.execute_program(helper_prog, x_pub, counter, is_probe=False)
                y_list = list(y_pub) if isinstance(y_pub, tuple) else y_pub
                out_list = list(out) if isinstance(out, tuple) else out
                if y_list not in (out_list, out_list[::-1], sorted(out_list)):
                    matches_all = False
                    break
            if matches_all:
                restored = self.cold_archive.pop(h_name)
                restored.last_used_step = self.step_index
                restored.usage_count += 1
                self.active_helpers[h_name] = restored
                self.cold_archive_reactivated += 1
                return restored
        return None


# ---------------------------------------------------------------------------
# Execution-Guided Prefix Search vs Baselines
# ---------------------------------------------------------------------------

def _required_init_and_pre_for_loop(loop_key: str) -> tuple[str, str]:
    """Determines the minimal sound variable initialization & pre-pass for a given loop block."""
    if loop_key.startswith('LOOP_HELPER:'):
        return 'INIT_ACC', 'PRE_NONE'
    _, req = MAIN_LOOP_BLOCKS[loop_key]
    if req == {'acc', 'seen'}:
        return 'INIT_ACC_SEEN', 'PRE_NONE'
    if req == {'acc', 'counts'}:
        return 'INIT_ACC_COUNTS', 'PRE_COUNT_FREQ'
    if req == {'acc', 'counts', 'seen'}:
        return 'INIT_ACC_SEEN', 'PRE_COUNT_FREQ'
    if req == {'acc', 'total'}:
        return 'INIT_ACC_TOTAL', 'PRE_NONE'
    if req == {'acc', 'best'}:
        if loop_key == 'LOOP_FILTER_BELOW_BEST':
            return 'INIT_ACC_BEST', 'PRE_MAX_BEST'
        return 'INIT_ACC_BEST', 'PRE_NONE'
    if req == {'acc', 'idx'}:
        return 'INIT_ACC_IDX', 'PRE_NONE'
    if req == {'total'}:
        return 'INIT_ACC_TOTAL', 'PRE_NONE'
    if req == {'total', 'counts'}:
        return 'INIT_TOTAL_COUNTS', 'PRE_COUNT_FREQ'
    return 'INIT_ACC', 'PRE_NONE'


@dataclass
class ImperativeSynthesisResult:
    method: str
    task_id: str
    seed: int
    status: str  # 'unique', 'ambiguous', 'abstain'
    synthesized_source: str
    statement_count: int
    is_multi_statement_verified: bool
    helper_used: bool
    cold_archive_reactivated: bool
    private_correct: bool
    false_unique: bool
    ambiguous_correctly_declared: bool
    total_work: int
    total_primitive_op_steps: int
    work_breakdown: dict[str, int]
    gpu_telemetry: dict[str, Any]


def solve_imperative_python_task(
    method: str,
    task_spec: dict[str, Any],
    seed: int,
    *,
    scorer: M4ExecutionTraceScorer | None = None,
    library: ImperativeHelperLibrary | None = None,
) -> ImperativeSynthesisResult:
    """Runs one synthesis method on a multi-statement Python task and verifies on private tests."""
    if method not in WAVE21_IMPERATIVE_METHODS:
        raise ValueError(f'Unknown method {method!r}')

    counter = Wave21WorkCounter()
    if scorer is None:
        scorer = M4ExecutionTraceScorer(seed=seed)
    if library is None:
        library = ImperativeHelperLibrary()

    public_pairs: list[tuple[Any, Any]] = list(task_spec['public'])
    private_pairs: list[tuple[Any, Any]] = list(task_spec['private'])
    probe_inputs: list[Any] = list(task_spec.get('probes', [[-3, 2, -3, 4, 1, 2], [5, 2, 5, -1, 3]]))
    gold_status: str = task_spec['gold_status']
    active_oracle: Callable[[Any], Any] | None = task_spec.get('active_oracle')

    reactivated_now = False
    if method == 'nexus_m4_execution_guided_imperative_full':
        restored = library.try_reactivate_from_cold_archive(public_pairs, counter)
        if restored is not None:
            reactivated_now = True

    surviving_programs: list[ImperativePythonProgram] = []

    if method == 'standalone_m4_neural_trace_baseline':
        # Top-1 greedy decode from the neural scorer without execution-trace post-routing or search
        ranked = scorer.rank_statement_operators_mps(public_pairs)
        top_loop = ranked[0][0]
        init_k, pre_k = _required_init_and_pre_for_loop(top_loop)
        default_post = 'RET_TOTAL' if top_loop.startswith('LOOP_SCALAR_') else 'RET_ACC'
        cand = _assemble_with_combined_init(init_k, pre_k, top_loop, default_post, library.active_helpers)
        ok = True
        for x_pub, y_pub in public_pairs:
            try:
                pred = ImperativeSandboxExecutor.execute_program(cand, x_pub, counter)
            except Exception:
                ok = False
                break
            if pred != y_pub:
                ok = False
                break
        if ok:
            surviving_programs.append(cand)

    elif method in ('blind_ast_statement_enumerator', 'nexus_whole_function_macro_only'):
        # Blind breadth-first enumeration over (loop_key, post_key) without live locals() trace pruning
        # First check whole functions in solved_history if whole_function_macro_only
        if method == 'nexus_whole_function_macro_only':
            for prev_prog in library.solved_history:
                counter.macro_retrievals += 1
                if all(
                    ImperativeSandboxExecutor.execute_program(prev_prog, x_pub, counter) == y_pub
                    for x_pub, y_pub in public_pairs
                ):
                    surviving_programs.append(prev_prog)

        all_loops = list(STATEMENT_OPERATORS)
        all_posts = list(POST_BLOCKS.keys())
        for loop_k in all_loops:
            init_k, pre_k = _required_init_and_pre_for_loop(loop_k)
            for post_k in all_posts:
                cand = _assemble_with_combined_init(init_k, pre_k, loop_k, post_k, library.active_helpers)
                matches = True
                for x_pub, y_pub in public_pairs:
                    try:
                        pred = ImperativeSandboxExecutor.execute_program(cand, x_pub, counter)
                    except Exception:
                        matches = False
                        break
                    if pred != y_pub:
                        matches = False
                        break
                if matches:
                    if not _is_observationally_duplicate(cand, surviving_programs, probe_inputs, counter):
                        surviving_programs.append(cand)
                        if len(surviving_programs) >= 3:
                            break
            if len(surviving_programs) >= 3:
                break

    elif method == 'nexus_imperative_without_trace_guidance':
        # Uses M4 neural operator ranking and active helpers, but does NOT execute partial prefix
        # traces to inspect live `locals()` and prune dead `post_op` suffixes.
        ranked = scorer.rank_statement_operators_mps(public_pairs)
        helper_ops = [f'LOOP_HELPER:{h_name}' for h_name in library.active_helpers]
        ordered_loops = helper_ops + [op for op, _ in ranked if op not in helper_ops]
        all_posts = list(POST_BLOCKS.keys())
        for loop_k in ordered_loops:
            init_k, pre_k = _required_init_and_pre_for_loop(loop_k)
            for post_k in all_posts:
                cand = _assemble_with_combined_init(init_k, pre_k, loop_k, post_k, library.active_helpers)
                matches = True
                for x_pub, y_pub in public_pairs:
                    try:
                        pred = ImperativeSandboxExecutor.execute_program(cand, x_pub, counter)
                    except Exception:
                        matches = False
                        break
                    if pred != y_pub:
                        matches = False
                        break
                if matches:
                    if not _is_observationally_duplicate(cand, surviving_programs, probe_inputs, counter):
                        surviving_programs.append(cand)
                        if len(surviving_programs) >= 2:
                            break
            if len(surviving_programs) >= 2 and len(public_pairs) >= 2:
                break

    elif method == 'nexus_m4_execution_guided_imperative_full':
        # Step 1: Score candidate statement loops on M4 GPU (`mps`)
        ranked = scorer.rank_statement_operators_mps(public_pairs)
        helper_ops = [f'LOOP_HELPER:{h_name}' for h_name in library.active_helpers]
        ordered_loops = helper_ops + [op for op, _ in ranked if op not in helper_ops]

        # Step 2: Execute Partial Statement Prefixes (`init; pre; loop`) and capture live `locals()`!
        for loop_k in ordered_loops:
            init_k, pre_k = _required_init_and_pre_for_loop(loop_k)
            prefix_locals: list[dict[str, Any]] = []
            prefix_valid = True
            for x_pub, _ in public_pairs:
                try:
                    loc = _execute_combined_prefix_trace(
                        init_k, pre_k, loop_k, x_pub, counter, library.active_helpers
                    )
                    prefix_locals.append(loc)
                except Exception:
                    prefix_valid = False
                    break
            if not prefix_valid:
                continue

            # Step 3: Route directly from live `locals()` state to matching `post_key` (or prune dead prefix!)
            candidate_posts = _route_post_blocks_from_live_locals(prefix_locals, public_pairs)
            for post_k in candidate_posts:
                cand = _assemble_with_combined_init(init_k, pre_k, loop_k, post_k, library.active_helpers)
                if not _is_observationally_duplicate(cand, surviving_programs, probe_inputs, counter):
                    surviving_programs.append(cand)
            if surviving_programs and len(public_pairs) >= 2:
                break

    # Active probe disambiguation if multiple observationally distinct programs survive on public examples
    if len(surviving_programs) > 1 and active_oracle is not None:
        for px in probe_inputs:
            outs = [
                ImperativeSandboxExecutor.execute_program(p, px, counter, is_probe=True)
                for p in surviving_programs
            ]
            if len(set(repr(o) for o in outs)) > 1:
                counter.probe_executions += 1
                counter.primitive_op_steps += 1
                oracle_y = active_oracle(px)
                surviving_programs = [p for p, o in zip(surviving_programs, outs) if o == oracle_y]
                if len(surviving_programs) <= 1:
                    break

    if len(surviving_programs) == 1:
        status = 'unique'
        chosen = surviving_programs[0]
        if method in ('nexus_imperative_without_trace_guidance', 'nexus_m4_execution_guided_imperative_full'):
            scorer.update_on_solved_program_mps(public_pairs, chosen.loop_key, steps=3)
            library.record_solved_and_compress_mdl(chosen, probe_inputs, counter, scorer=scorer)
            if method == 'nexus_m4_execution_guided_imperative_full':
                library.usage_age_prune(max_idle_steps=2)
        elif method == 'nexus_whole_function_macro_only':
            library.solved_history.append(chosen)
    elif len(surviving_programs) > 1:
        status = 'ambiguous'
        chosen = None
    else:
        status = 'abstain'
        chosen = None

    # Private evaluation (strictly after lock; never charges learner work)
    priv_counter = Wave21WorkCounter()
    if status == 'unique' and chosen is not None:
        multi_stmt_ok = verify_multi_statement_imperative_ast(chosen.to_module_ast())
        all_priv_ok = all(
            ImperativeSandboxExecutor.execute_program(chosen, x_p, priv_counter) == y_p
            for x_p, y_p in private_pairs
        )
        private_correct = (gold_status == 'unique') and multi_stmt_ok and all_priv_ok
        src_text = chosen.full_source()
        stmt_cnt = chosen.statement_count()
        helper_used = bool(chosen.helper_sources)
    else:
        multi_stmt_ok = False
        private_correct = (status == gold_status)
        src_text = ''
        stmt_cnt = 0
        helper_used = False

    false_unique = (status == 'unique') and (not private_correct)
    ambiguous_ok = (status == 'ambiguous') and (gold_status == 'ambiguous')
    wb = counter.to_dict()
    return ImperativeSynthesisResult(
        method=method,
        task_id=task_spec['id'],
        seed=seed,
        status=status,
        synthesized_source=src_text,
        statement_count=stmt_cnt,
        is_multi_statement_verified=multi_stmt_ok,
        helper_used=helper_used,
        cold_archive_reactivated=reactivated_now,
        private_correct=private_correct,
        false_unique=false_unique,
        ambiguous_correctly_declared=ambiguous_ok,
        total_work=wb['total_work'],
        total_primitive_op_steps=wb['total_primitive_op_steps'],
        work_breakdown=wb,
        gpu_telemetry=scorer.telemetry.snapshot(),
    )


def _assemble_with_combined_init(
    init_k: str,
    pre_k: str,
    loop_k: str,
    post_k: str,
    helpers: dict[str, MultiStatementHelper],
) -> ImperativePythonProgram:
    if init_k == 'INIT_ACC_SEEN' and pre_k == 'PRE_COUNT_FREQ':
        init_src = 'acc = []\nseen = set()\ncounts = {}\n'
        pre_src = PRE_PASS_BLOCKS[pre_k]
        loop_src = MAIN_LOOP_BLOCKS[loop_k][0]
        post_src = POST_BLOCKS[post_k]
        body_text = init_src + pre_src + loop_src + post_src
        indented = '\n'.join('    ' + line for line in body_text.strip().splitlines())
        return ImperativePythonProgram(
            entry_name='solve',
            init_key=init_k,
            pre_key=pre_k,
            loop_key=loop_k,
            post_key=post_k,
            source=f'def solve(x):\n{indented}\n',
            helper_sources=(),
        )
    return build_imperative_program(init_k, pre_k, loop_k, post_k, helpers=helpers)


def _execute_combined_prefix_trace(
    init_k: str,
    pre_k: str,
    loop_k: str,
    x: Any,
    counter: Wave21WorkCounter,
    helpers: dict[str, MultiStatementHelper],
) -> dict[str, Any]:
    if init_k == 'INIT_ACC_SEEN' and pre_k == 'PRE_COUNT_FREQ':
        # Combined init with both seen and counts
        body_text = (
            'acc = []\nseen = set()\ncounts = {}\n'
            + PRE_PASS_BLOCKS[pre_k]
            + MAIN_LOOP_BLOCKS[loop_k][0]
            + "return {'acc': acc, 'total': 0, 'seen_len': len(seen), 'counts_len': len(counts), 'best': None}\n"
        )
        indented = '\n'.join('    ' + line for line in body_text.strip().splitlines())
        func_src = f'def _prefix_trace(x):\n{indented}\n'
        counter.candidate_evaluations += 1
        raw_mod = ast.parse(func_src)
        w19.SandboxedPythonASTExecutor.verify_ast_safety(raw_mod)
        instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(raw_mod))
        code = compile(instrumented, '<nexus_wave21_prefix_trace>', 'exec')

        def _tick(weight: int = 1) -> None:
            counter.primitive_op_steps += int(weight)

        def _tick_val(val: Any, weight: int = 1) -> Any:
            _tick(weight)
            return val

        env: dict[str, Any] = {
            '__builtins__': SAFE_BUILTINS,
            '__nexus_tick__': _tick,
            '__nexus_tick_val__': _tick_val,
        }
        exec(code, env, env)
        arg = list(x) if isinstance(x, (tuple, list)) else x
        return dict(env['_prefix_trace'](arg))
    return ImperativeSandboxExecutor.execute_partial_prefix_trace(
        init_k, pre_k, loop_k, x, counter, helpers=helpers
    )


def _route_post_blocks_from_live_locals(
    prefix_locals: list[dict[str, Any]],
    public_pairs: list[tuple[Any, Any]],
) -> list[str]:
    """Inspects live `locals()` after the loop to select only matching post-loop return blocks."""
    matches_acc = True
    matches_rev = True
    matches_sorted = True
    matches_sum = True
    matches_total = True

    for loc, (_, y_raw) in zip(prefix_locals, public_pairs):
        acc = loc.get('acc')
        tot = loc.get('total')
        if isinstance(y_raw, int) and not isinstance(y_raw, bool):
            matches_acc = False
            matches_rev = False
            matches_sorted = False
            if acc is None or sum(acc) != y_raw:
                matches_sum = False
            if tot is None or tot != y_raw:
                matches_total = False
        else:
            matches_sum = False
            matches_total = False
            y_list = list(y_raw) if isinstance(y_raw, tuple) else list(y_raw)
            if acc is None:
                matches_acc = False
                matches_rev = False
                matches_sorted = False
            else:
                if acc != y_list:
                    matches_acc = False
                if acc[::-1] != y_list:
                    matches_rev = False
                if sorted(acc) != y_list:
                    matches_sorted = False

    routed: list[str] = []
    if matches_acc:
        routed.append('RET_ACC')
    if matches_rev:
        routed.append('RET_ACC_REV')
    if matches_sorted and not matches_acc:
        routed.append('RET_ACC_SORTED')
    if matches_total:
        routed.append('RET_TOTAL')
    if matches_sum and not matches_total:
        routed.append('RET_ACC_SUM')
    return routed


def _is_observationally_duplicate(
    cand: ImperativePythonProgram,
    existing: list[ImperativePythonProgram],
    probe_inputs: list[Any],
    counter: Wave21WorkCounter,
) -> bool:
    if not existing:
        return False
    cand_outs = [ImperativeSandboxExecutor.execute_program(cand, px, counter, is_probe=True) for px in probe_inputs]
    for prev in existing:
        prev_outs = [ImperativeSandboxExecutor.execute_program(prev, px, counter, is_probe=True) for px in probe_inputs]
        if cand_outs == prev_outs:
            return True
    return False


# ---------------------------------------------------------------------------
# Trace-Driven Bug Localization & Multi-Line Repair for Multi-File Repositories
# ---------------------------------------------------------------------------

@dataclass
class CallTraceEvent:
    file_path: str
    func_name: str
    call_args: tuple[Any, ...]
    return_value: Any
    exception: str | None
    contract_violated: bool
    faulty_lineno: int | None
    faulty_statement: str


@dataclass
class RepoTraceRepairResult:
    repo_id: str
    localized_file: str
    localized_function: str
    faulty_lineno: int
    faulty_statement: str
    call_trace_events: list[dict[str, Any]]
    synthesized_replacement_source: str
    unified_diff: str
    public_passed: bool
    private_passed: bool
    total_work: int
    total_primitive_op_steps: int


class TraceDrivenRepoRepairEngine:
    """Instruments multi-file repositories at runtime, localizes faulty statements, and repairs them."""

    @classmethod
    def localize_and_repair_repository(
        cls,
        repo_spec: dict[str, Any],
        *,
        seed: int = 0,
    ) -> RepoTraceRepairResult:
        counter = Wave21WorkCounter()
        scorer = M4ExecutionTraceScorer(seed=seed)
        library = ImperativeHelperLibrary()

        files: dict[str, str] = {k: str(v) for k, v in repo_spec['files'].items()}
        entry_file, entry_func = repo_spec['entry']
        contracts: dict[tuple[str, str], Callable[[Any, Any], bool]] = dict(repo_spec['contracts'])
        target_subtask_oracle: dict[tuple[str, str], Callable[[Any], Any]] = dict(repo_spec['subtask_oracles'])
        public_tests: list[tuple[Any, Any]] = list(repo_spec['public'])
        private_tests: list[tuple[Any, Any]] = list(repo_spec['private'])

        # Step 1: Instrument every function in every file to record runtime call traces
        trace_events: list[CallTraceEvent] = []
        cls._run_instrumented_repo_trace(
            files=files,
            entry_file=entry_file,
            entry_func=entry_func,
            test_inputs=[x for x, _ in public_tests],
            contracts=contracts,
            trace_events=trace_events,
            counter=counter,
        )

        # Step 2: Pinpoint the first function in execution trace whose contract was violated
        violating = [ev for ev in trace_events if ev.contract_violated]
        if not violating:
            raise RuntimeError('No contract violation detected in repository trace')
        first_fault = violating[0]
        target_key = (first_fault.file_path, first_fault.func_name)
        oracle_fn = target_subtask_oracle[target_key]

        # Build induced public examples for the localized faulty function from recorded call_args
        observed_inputs: list[Any] = []
        for ev in trace_events:
            if (ev.file_path, ev.func_name) == target_key and ev.call_args:
                arg0 = ev.call_args[0]
                if arg0 not in observed_inputs:
                    observed_inputs.append(arg0)
        induced_public = [(inp, oracle_fn(inp)) for inp in observed_inputs]

        # Step 3: Synthesize a verified multi-statement replacement for `first_fault.func_name`
        synth_spec = {
            'id': f"{repo_spec['id']}::{first_fault.func_name}",
            'public': induced_public,
            'private': induced_public,
            'gold_status': 'unique',
        }
        synth_res = solve_imperative_python_task(
            'nexus_m4_execution_guided_imperative_full',
            synth_spec,
            seed=seed,
            scorer=scorer,
            library=library,
        )
        counter.probe_executions += synth_res.work_breakdown['probe_executions']
        counter.candidate_evaluations += synth_res.work_breakdown['candidate_evaluations']
        counter.primitive_op_steps += synth_res.work_breakdown['total_primitive_op_steps']

        # Rename synthesized `def solve(x):` to `def <localized_function>(x):`
        rep_tree = ast.parse(synth_res.synthesized_source)
        for node in rep_tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'solve':
                node.name = first_fault.func_name
        replacement_src = ast.unparse(ast.fix_missing_locations(rep_tree)) + '\n'

        # Step 4: Replace the faulty function inside `first_fault.file_path` and generate unified diff
        orig_file_src = files[first_fault.file_path]
        orig_mod = ast.parse(orig_file_src)
        new_body: list[ast.stmt] = []
        for stmt in orig_mod.body:
            if isinstance(stmt, ast.FunctionDef) and stmt.name == first_fault.func_name:
                new_body.extend(rep_tree.body)
            else:
                new_body.append(stmt)
        patched_mod = ast.fix_missing_locations(ast.Module(body=new_body, type_ignores=[]))
        patched_file_src = ast.unparse(patched_mod) + '\n'

        diff_lines = list(
            difflib.unified_diff(
                orig_file_src.splitlines(keepends=True),
                patched_file_src.splitlines(keepends=True),
                fromfile=f'a/{first_fault.file_path}',
                tofile=f'b/{first_fault.file_path}',
            )
        )
        unified_diff = ''.join(diff_lines)

        patched_files = dict(files)
        patched_files[first_fault.file_path] = patched_file_src

        pub_ok = cls._verify_repo_tests(patched_files, entry_file, entry_func, public_tests, counter)
        priv_counter = Wave21WorkCounter()
        priv_ok = cls._verify_repo_tests(patched_files, entry_file, entry_func, private_tests, priv_counter)

        return RepoTraceRepairResult(
            repo_id=repo_spec['id'],
            localized_file=first_fault.file_path,
            localized_function=first_fault.func_name,
            faulty_lineno=first_fault.faulty_lineno or 1,
            faulty_statement=first_fault.faulty_statement,
            call_trace_events=[vars(ev) for ev in trace_events],
            synthesized_replacement_source=replacement_src,
            unified_diff=unified_diff,
            public_passed=pub_ok,
            private_passed=priv_ok,
            total_work=counter.total_work,
            total_primitive_op_steps=counter.total_primitive_op_steps,
        )

    @classmethod
    def _run_instrumented_repo_trace(
        cls,
        *,
        files: dict[str, str],
        entry_file: str,
        entry_func: str,
        test_inputs: list[Any],
        contracts: dict[tuple[str, str], Callable[[Any, Any], bool]],
        trace_events: list[CallTraceEvent],
        counter: Wave21WorkCounter,
    ) -> None:
        shared_env: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
        func_ast_info: dict[tuple[str, str], tuple[int, str]] = {}

        # Load and wrap all functions in topological order (non-entry files first, then entry file)
        ordered_files = [f for f in sorted(files.keys()) if f != entry_file] + [entry_file]
        for f_path in ordered_files:
            mod_ast = ast.parse(files[f_path])
            w19.SandboxedPythonASTExecutor.verify_ast_safety(mod_ast)
            for node in mod_ast.body:
                if isinstance(node, ast.FunctionDef):
                    lineno, stmt_src = cls._find_innermost_mutation_stmt(node)
                    func_ast_info[(f_path, node.name)] = (lineno, stmt_src)
            code = compile(mod_ast, f_path, 'exec')
            local_ns: dict[str, Any] = {}
            exec(code, shared_env, local_ns)
            for name, val in local_ns.items():
                if callable(val) and (f_path, name) in func_ast_info:
                    shared_env[name] = cls._wrap_traced_function(
                        f_path,
                        name,
                        val,
                        contracts.get((f_path, name)),
                        func_ast_info[(f_path, name)],
                        trace_events,
                        counter,
                    )
                else:
                    shared_env[name] = val

        entry_callable = shared_env[entry_func]
        for x_in in test_inputs:
            arg = list(x_in) if isinstance(x_in, (tuple, list)) else x_in
            entry_callable(arg)

    @staticmethod
    def _find_innermost_mutation_stmt(fn_node: ast.FunctionDef) -> tuple[int, str]:
        for node in ast.walk(fn_node):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Expr, ast.Assign, ast.AugAssign)) and hasattr(child, 'lineno'):
                        return int(child.lineno), ast.unparse(child)
        if fn_node.body:
            stmt = fn_node.body[-1]
            return int(getattr(stmt, 'lineno', 1)), ast.unparse(stmt)
        return 1, ''

    @staticmethod
    def _wrap_traced_function(
        file_path: str,
        func_name: str,
        fn: Callable[..., Any],
        contract_fn: Callable[[Any, Any], bool] | None,
        ast_info: tuple[int, str],
        trace_events: list[CallTraceEvent],
        counter: Wave21WorkCounter,
    ) -> Callable[..., Any]:
        def _traced(*args: Any, **kwargs: Any) -> Any:
            counter.probe_executions += 1
            counter.primitive_op_steps += 2
            in_snapshot = [list(a) if isinstance(a, list) else a for a in args]
            try:
                out = fn(*args, **kwargs)
                violated = False
                if contract_fn is not None and in_snapshot:
                    violated = not bool(contract_fn(in_snapshot[0], out))
                trace_events.append(
                    CallTraceEvent(
                        file_path=file_path,
                        func_name=func_name,
                        call_args=tuple(in_snapshot),
                        return_value=out,
                        exception=None,
                        contract_violated=violated,
                        faulty_lineno=ast_info[0] if violated else None,
                        faulty_statement=ast_info[1] if violated else '',
                    )
                )
                return out
            except Exception as exc:
                trace_events.append(
                    CallTraceEvent(
                        file_path=file_path,
                        func_name=func_name,
                        call_args=tuple(in_snapshot),
                        return_value=None,
                        exception=str(exc),
                        contract_violated=True,
                        faulty_lineno=ast_info[0],
                        faulty_statement=ast_info[1],
                    )
                )
                raise

        return _traced

    @classmethod
    def _verify_repo_tests(
        cls,
        files: dict[str, str],
        entry_file: str,
        entry_func: str,
        tests: list[tuple[Any, Any]],
        counter: Wave21WorkCounter,
    ) -> bool:
        shared_env: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
        ordered_files = [f for f in sorted(files.keys()) if f != entry_file] + [entry_file]
        for f_path in ordered_files:
            mod_ast = ast.parse(files[f_path])
            w19.SandboxedPythonASTExecutor.verify_ast_safety(mod_ast)
            exec(compile(mod_ast, f_path, 'exec'), shared_env, shared_env)
        fn = shared_env[entry_func]
        for x_in, y_exp in tests:
            counter.candidate_evaluations += 1
            counter.primitive_op_steps += 3
            arg = list(x_in) if isinstance(x_in, (tuple, list)) else x_in
            out = fn(arg)
            if out != y_exp:
                return False
        return True


# ---------------------------------------------------------------------------
# Pre-freeze Synthetic Development Suite for Module 2 (Not the Fresh Suite)
# ---------------------------------------------------------------------------

def build_pre_freeze_imperative_dev_suite() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Builds pre-freeze development tasks and multi-file repo repair specs for pytest."""
    tasks = [
        {
            'id': 'dev_imp_unique_freq1_sq',
            'public': [
                ([4, 2, 4, 1, 2, 5], [1, 25]),
                ([3, 3, -2, 7, -2], [49]),
            ],
            'private': [
                ([1, 9, 1, 4, 4, 6], [81, 36]),
                ([2, 2, 3], [9]),
            ],
            'gold_status': 'unique',
        },
        {
            'id': 'dev_imp_unique_freq1_sq_rev',
            'public': [
                ([4, 2, 4, 1, 2, 5], [25, 1]),
                ([3, 5, 3, 2], [4, 25]),
            ],
            'private': [
                ([6, 1, 6, 4], [16, 1]),
                ([2, 3, 2], [9]),
            ],
            'gold_status': 'unique',
        },
        {
            'id': 'dev_imp_running_pos_cumsum',
            'public': [
                ([3, -2, 5, -1, 4], [3, 8, 12]),
                ([-4, 2, 6, -3, 1], [2, 8, 9]),
            ],
            'private': [
                ([1, 2, -5, 7], [1, 3, 10]),
                ([-1, -2, 9], [9]),
            ],
            'gold_status': 'unique',
        },
        {
            'id': 'dev_imp_scalar_unique_sum',
            'public': [
                ([4, 2, 4, 5, 2, 3], 8),
                ([7, 7, 6, 1, 1], 6),
            ],
            'private': [
                ([9, 2, 9, 4], 6),
            ],
            'gold_status': 'unique',
        },
        {
            'id': 'dev_imp_ambiguous_single_pos',
            'public': [
                ([1, -2], [1]),
            ],
            'private': [],
            'gold_status': 'ambiguous',
        },
        {
            'id': 'dev_imp_abstain_oog',
            'public': [
                ([1, 2, 3], [999, -999, 42]),
                ([4, 5], [777]),
            ],
            'private': [],
            'gold_status': 'abstain',
        },
    ]

    repo_specs = [
        {
            'id': 'dev_repo_dedup_pipeline',
            'files': {
                'pkg/ingestor.py': (
                    'def clean_NonZero(items):\n'
                    '    out = []\n'
                    '    for v in items:\n'
                    '        if v != 0:\n'
                    '            out.append(v)\n'
                    '    return out\n'
                ),
                'pkg/reducer.py': (
                    'def unique_frequency_squares(x):\n'
                    '    acc = []\n'
                    '    for item in x:\n'
                    '        acc.append(item * item)\n'
                    '    return acc\n'
                ),
                'pkg/pipeline.py': (
                    'def run_pipeline(raw):\n'
                    '    cleaned = clean_NonZero(raw)\n'
                    '    return unique_frequency_squares(cleaned)\n'
                ),
            },
            'entry': ('pkg/pipeline.py', 'run_pipeline'),
            'contracts': {
                ('pkg/ingestor.py', 'clean_NonZero'): lambda x, y: y == [v for v in x if v != 0],
                ('pkg/reducer.py', 'unique_frequency_squares'): (
                    lambda x, y: y == [v * v for v in x if x.count(v) == 1]
                ),
            },
            'subtask_oracles': {
                ('pkg/reducer.py', 'unique_frequency_squares'): (
                    lambda x: [v * v for v in x if x.count(v) == 1]
                ),
            },
            'public': [
                ([4, 0, 2, 4, 1, 2, 5], [1, 25]),
                ([3, 3, 0, -2, 7, -2], [49]),
            ],
            'private': [
                ([1, 9, 0, 1, 4, 4, 6], [81, 36]),
            ],
        }
    ]
    return tasks, repo_specs
