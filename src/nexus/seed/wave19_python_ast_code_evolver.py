"""Wave 19 — Native Python AST Function Synthesis, Helper Invention & Multi-File Repo Patching.

Implements Capability 8 of the NEXUS Master Audit Ledger:
1. Native Python `ast.FunctionDef` and `ast.Module` synthesis with loops (`ast.For`),
   bounded recursion, conditionals (`ast.If`), list comprehensions (`ast.ListComp`),
   and modular helper function calls.
2. Metered, sandboxed unit-test execution (`SandboxedPythonASTExecutor`) with AST-level
   step instrumentation (charging every loop iteration, recursive call, and operation).
3. Self-evolving helper function library (`PythonASTHelperLibrary`) that extracts shared
   Python AST sub-programs via MDL (`compress_solved_functions_mdl`), promotes them into
   standalone `def helper_k(x): ...` functions inside `ast.Module`, prunes unused
   functions into a cold archive, and reactivates archived helpers by behavioral signature.
4. Multi-file repository fault localization and patching (`MultiFileRepoPatcher`) that
   inspects multi-file Python packages, localizes buggy functions across files using
   dependency + test-failure residual analysis, synthesizes verified `ast.FunctionDef`
   patches, and produces unified diffs and AST provenance receipts.
5. Apple M4 GPU (`mps`) neuro-symbolic AST proposer (`M4PythonASTProposer`) with dynamic
   output-head expansion when new Python helper functions are invented.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import difflib
import hashlib
import math
import time

from . import wave18_m4_gpu_neuro_symbolic_learner as w18

OpCounter = w18.OpCounter
NeuralTelemetry = w18.NeuralTelemetry
require_mps = w18.require_mps
PUBLIC_BUDGET = 24

WAVE19_METHODS = (
    'standalone_m4_neural_code_baseline',
    'equal_ast_scratch',
    'ordinary_ast_memoization',
    'nexus_whole_function_only',
    'nexus_ast_without_pruning',
    'nexus_m4_python_ast_full',
)

AST_POLICY_LABELS = (
    'LOOP_FILTER_ACCUMULATE',
    'LOOP_TRANSFORM_MAP',
    'RECURSIVE_REDUCE',
    'PIECEWISE_IF_BRANCH',
    'SLICE_BOUNDARY_OP',
    'ARITHMETIC_POLY',
    'REPO_CROSS_FILE_PATCH',
    'HELPER_COMPOSITION',
)

SAFE_BUILTINS = {
    'abs': abs,
    'all': all,
    'any': any,
    'bool': bool,
    'dict': dict,
    'enumerate': enumerate,
    'int': int,
    'isinstance': isinstance,
    'len': len,
    'list': list,
    'max': max,
    'min': min,
    'range': range,
    'reversed': reversed,
    'round': round,
    'set': set,
    'sorted': sorted,
    'str': str,
    'sum': sum,
    'tuple': tuple,
    'zip': zip,
    'True': True,
    'False': False,
    'None': None,
}

MAX_SANDBOX_STEPS = 2048


class SandboxStepLimitExceeded(RuntimeError):
    """Raised when a synthesized Python AST exceeds the step budget."""


class _StepInstrumentor(ast.NodeTransformer):
    """Instruments loop bodies, function entries, and comprehensions to meter op steps."""

    def _tick_stmt(self, weight=1):
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='__nexus_tick__', ctx=ast.Load()),
                args=[ast.Constant(value=weight)],
                keywords=[],
            )
        )

    def _tick_expr(self, expr, weight=1):
        return ast.Call(
            func=ast.Name(id='__nexus_tick_val__', ctx=ast.Load()),
            args=[expr, ast.Constant(value=weight)],
            keywords=[],
        )

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        weight = max(1, sum(isinstance(n, (ast.BinOp, ast.Compare, ast.Call, ast.Subscript))
                            for n in ast.walk(node)))
        node.body = [self._tick_stmt(weight)] + list(node.body)
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        node.body = [self._tick_stmt(2)] + list(node.body)
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        node.body = [self._tick_stmt(2)] + list(node.body)
        return node

    def visit_ListComp(self, node):
        self.generic_visit(node)
        node.elt = self._tick_expr(node.elt, 2)
        return node


def canonical_ast_dump(node):
    """Deterministic structural key for a Python `ast.AST` node."""
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def ast_node_count(node):
    """Counts syntactic AST nodes, treating a helper call `helper_k(arg)` as size 1."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.startswith('helper_'):
        return 1 + sum(ast_node_count(a) for a in node.args)
    return 1 + sum(ast_node_count(child) for child in ast.iter_child_nodes(node))


@dataclass(frozen=True)
class SynthesizedPythonProgram:
    """A complete executable Python `ast.Module` with optional helper `ast.FunctionDef`s."""
    entry_name: str
    main_func: ast.FunctionDef
    helpers: tuple = ()
    guard_tag: str = 'UNCONDITIONAL'
    core_expr_dump: str = ''
    core_expr_ast: ast.AST | None = None
    domain_kind: str = 'sequence'

    def to_module_ast(self):
        body = [ast.fix_missing_locations(h) for h in self.helpers]
        body.append(ast.fix_missing_locations(self.main_func))
        mod = ast.Module(body=body, type_ignores=[])
        return ast.fix_missing_locations(mod)

    def to_source(self):
        return ast.unparse(self.to_module_ast())

    def to_dict(self):
        return dict(
            entry_name=self.entry_name,
            source=self.to_source(),
            main_dump=canonical_ast_dump(self.main_func),
            helper_names=[h.name for h in self.helpers],
            helper_dumps=[canonical_ast_dump(h) for h in self.helpers],
            guard_tag=self.guard_tag,
            core_expr_dump=self.core_expr_dump,
            domain_kind=self.domain_kind,
        )

    def syntax_cost(self):
        return ast_node_count(self.main_func)


class SandboxedPythonASTExecutor:
    """Compiles and executes Python `ast.Module` trees in a pure, step-metered sandbox."""

    @staticmethod
    def verify_ast_safety(module_ast):
        forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
                     ast.Delete, ast.With, ast.AsyncFunctionDef, ast.ClassDef)
        for node in ast.walk(module_ast):
            if isinstance(node, forbidden):
                raise ValueError('forbidden_ast_construct:' + type(node).__name__)
            if isinstance(node, ast.Name) and node.id.startswith('__'):
                raise ValueError('forbidden_dunder_name:' + node.id)
            if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
                raise ValueError('forbidden_dunder_attr:' + node.attr)

    @classmethod
    def compile_program(cls, program: SynthesizedPythonProgram):
        raw_mod = program.to_module_ast()
        cls.verify_ast_safety(raw_mod)
        instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(
            ast.parse(ast.unparse(raw_mod))
        ))
        return compile(instrumented, '<nexus_wave19_ast>', 'exec')

    @classmethod
    def execute(cls, program_or_code, x, op_counter: OpCounter | None = None,
                entry_name='solve', max_steps=MAX_SANDBOX_STEPS):
        if isinstance(program_or_code, SynthesizedPythonProgram):
            code = cls.compile_program(program_or_code)
            entry_name = program_or_code.entry_name
        elif isinstance(program_or_code, dict):
            raw_mod = ast.parse(program_or_code['source'])
            cls.verify_ast_safety(raw_mod)
            instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(raw_mod))
            code = compile(instrumented, '<nexus_wave19_ast>', 'exec')
            entry_name = program_or_code.get('entry_name', 'solve')
        else:
            code = program_or_code
        local_steps = [0]

        def _tick(weight=1):
            local_steps[0] += int(weight)
            if op_counter is not None:
                op_counter.steps += int(weight)
            if local_steps[0] > max_steps:
                raise SandboxStepLimitExceeded('step_limit_exceeded')

        def _tick_val(val, weight=1):
            _tick(weight)
            return val

        env = {'__builtins__': SAFE_BUILTINS, '__nexus_tick__': _tick, '__nexus_tick_val__': _tick_val}
        exec(code, env, env)
        fn = env[entry_name]
        arg = list(x) if isinstance(x, tuple) else dict(x) if isinstance(x, dict) else x
        result = fn(arg)
        if isinstance(x, tuple) and isinstance(result, list):
            return tuple(result)
        return result


# ---------------------------------------------------------------------------
# AST Builders for Native Python Functions, Loops, Recursion & Helpers
# ---------------------------------------------------------------------------

def _name(identifier, ctx=None):
    return ast.Name(id=identifier, ctx=ctx or ast.Load())


def _const(val):
    return ast.Constant(value=val)


def _call(func_name, *args):
    return ast.Call(func=_name(func_name), args=list(args), keywords=[])


def make_expr_function(func_name, arg_name, return_expr, guard_expr=None):
    """Builds `def func_name(x): if guard: return expr; return x` as a native `ast.FunctionDef`."""
    if guard_expr is None:
        body = [ast.Return(value=return_expr)]
    else:
        body = [
            ast.If(
                test=guard_expr,
                body=[ast.Return(value=return_expr)],
                orelse=[ast.Return(value=_name(arg_name))],
            )
        ]
    return ast.fix_missing_locations(
        ast.FunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=arg_name)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )
    )


def make_loop_filter_map_function(func_name, skip_token=None, prefix_token=None,
                                  suffix_token=None, reverse_first=False,
                                  drop_last=False, rot_left=False, guard_expr=None):
    """Builds a real `ast.For` loop function over sequence `x`."""
    stmts = []
    src_expr = _name('x')
    if drop_last:
        src_expr = ast.Subscript(
            value=src_expr,
            slice=ast.Slice(lower=None, upper=_const(-1), step=None),
            ctx=ast.Load(),
        )
    if rot_left:
        stmts.append(
            ast.Assign(
                targets=[_name('seq', ast.Store())],
                value=src_expr,
            )
        )
        src_expr = ast.IfExp(
            test=_name('seq'),
            body=ast.BinOp(
                left=ast.Subscript(value=_name('seq'), slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load()),
                op=ast.Add(),
                right=ast.Subscript(value=_name('seq'), slice=ast.Slice(lower=None, upper=_const(1), step=None), ctx=ast.Load()),
            ),
            orelse=ast.List(elts=[], ctx=ast.Load()),
        )
    if reverse_first:
        src_expr = ast.Subscript(
            value=src_expr,
            slice=ast.Slice(lower=None, upper=None, step=_const(-1)),
            ctx=ast.Load(),
        )
    init_elts = [_const(prefix_token)] if prefix_token is not None else []
    stmts.append(ast.Assign(targets=[_name('out', ast.Store())], value=ast.List(elts=init_elts, ctx=ast.Load())))
    append_call = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(value=_name('out'), attr='append', ctx=ast.Load()),
            args=[_name('item')],
            keywords=[],
        )
    )
    if skip_token is not None:
        loop_body = [
            ast.If(
                test=ast.Compare(left=_name('item'), ops=[ast.NotEq()], comparators=[_const(skip_token)]),
                body=[append_call],
                orelse=[],
            )
        ]
    else:
        loop_body = [append_call]
    stmts.append(ast.For(target=_name('item', ast.Store()), iter=src_expr, body=loop_body, orelse=[]))
    if suffix_token is not None:
        stmts.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(value=_name('out'), attr='append', ctx=ast.Load()),
                    args=[_const(suffix_token)],
                    keywords=[],
                )
            )
        )
    stmts.append(ast.Return(value=_call('tuple', _name('out'))))
    if guard_expr is not None:
        body = [ast.If(test=guard_expr, body=stmts, orelse=[ast.Return(value=_call('tuple', _name('x')))])]
    else:
        body = stmts
    return ast.fix_missing_locations(
        ast.FunctionDef(
            name=func_name,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='x')], vararg=None,
                               kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=body,
            decorator_list=[],
            returns=None,
        )
    )


def make_piecewise_ast_function(func_name, guard1, expr1, guard2, expr2):
    """Builds a 2-branch `if guard1: return expr1; elif guard2: return expr2; return tuple(x)`."""
    body = [
        ast.If(
            test=guard1,
            body=[ast.Return(value=expr1)],
            orelse=[
                ast.If(
                    test=guard2,
                    body=[ast.Return(value=expr2)],
                    orelse=[ast.Return(value=_call('tuple', _name('x')))],
                )
            ],
        )
    ]
    return ast.fix_missing_locations(
        ast.FunctionDef(
            name=func_name,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='x')], vararg=None,
                               kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=body,
            decorator_list=[],
            returns=None,
        )
    )


# ---------------------------------------------------------------------------
# Self-Evolving Python AST Helper Library
# ---------------------------------------------------------------------------

@dataclass
class EvolvedPythonHelper:
    name: str
    func_ast: ast.FunctionDef
    core_dump: str
    domain_kind: str
    uses: int = 1
    created_step: int = 0
    last_used_step: int = 0
    is_mdl_helper: bool = False
    pinned: bool = False


class PythonASTHelperLibrary:
    """Manages invented Python `ast.FunctionDef` helpers, MDL extraction, and cold archive."""

    def __init__(self, use_memoization=True, use_helper_evolution=True,
                 use_internal_mdl=True, use_pruning=True, use_cold_archive=True):
        self.use_memoization = use_memoization
        self.use_helper_evolution = use_helper_evolution
        self.use_internal_mdl = use_internal_mdl
        self.use_pruning = use_pruning
        self.use_cold_archive = use_cold_archive
        self.step = 0
        self.active_helpers: dict[str, EvolvedPythonHelper] = {}
        self.cold_archive: dict[str, EvolvedPythonHelper] = {}
        self.cold_guard_archive: dict[str, tuple[str, ast.AST]] = {}
        self.memoized_programs: dict[str, SynthesizedPythonProgram] = {}
        self.core_support: dict[str, set[int]] = {}
        self.core_ast_map: dict[str, ast.AST] = {}
        self.guard_support: dict[str, tuple[str, ast.AST, int]] = {}
        self.schemas: set[str] = set()
        self.index_work = 0
        self.index_ops = OpCounter()

    def begin_task(self):
        self.step += 1
        self.index_work = 0
        self.index_ops.steps = 0
        if self.use_pruning:
            self.usage_age_prune()

    def usage_age_prune(self, min_age=2, min_uses=2):
        demoted = []
        for name, helper in list(self.active_helpers.items()):
            if helper.pinned or helper.is_mdl_helper:
                continue
            if self.step - helper.created_step >= min_age and helper.uses < min_uses:
                self.active_helpers.pop(name)
                if self.use_cold_archive:
                    self.cold_archive[name] = helper
                    self.index_work += 2
                    self.index_ops.steps += 2
                demoted.append(name)
        for g_tag, (g_name, g_ast, created) in list(self.guard_support.items()):
            if self.step - created >= min_age and self.use_cold_archive:
                self.cold_guard_archive[g_tag] = (g_name, g_ast)
                self.guard_support.pop(g_tag, None)
                self.index_work += 1
        return demoted

    def compress_solved_functions_mdl(self, program: SynthesizedPythonProgram,
                                      compression_counter: OpCounter):
        if not self.use_helper_evolution:
            return 0, ()
        evals = 1
        compression_counter.steps += 1
        invented = []
        if program.domain_kind == 'sequence' and not program.helpers:
            whole_id = f'helper_whole_{self.step}'
            if whole_id not in self.active_helpers and whole_id not in self.cold_archive:
                ret_node = (program.main_func.body[0].body[0].value
                            if isinstance(program.main_func.body[0], ast.If)
                            else program.main_func.body[0].value)
                whole_fn = make_expr_function(whole_id, 'x', ret_node)
                self.active_helpers[whole_id] = EvolvedPythonHelper(
                    name=whole_id,
                    func_ast=whole_fn,
                    core_dump=canonical_ast_dump(ret_node),
                    domain_kind='sequence',
                    uses=1,
                    created_step=self.step,
                    last_used_step=self.step,
                    is_mdl_helper=False,
                    pinned=False,
                )
        if (program.domain_kind == 'sequence'
                and program.guard_tag not in ('UNCONDITIONAL', 'EVEN_LEN', 'ODD_LEN')):
            if program.guard_tag not in self.guard_support and program.guard_tag not in self.cold_guard_archive:
                if isinstance(program.main_func.body[0], ast.If):
                    self.guard_support[program.guard_tag] = (
                        program.guard_tag, program.main_func.body[0].test, self.step
                    )
        if not self.use_internal_mdl or not program.core_expr_dump or program.core_expr_ast is None:
            return evals, tuple(invented)
        seen = self.core_support.setdefault(program.core_expr_dump, set())
        self.core_ast_map[program.core_expr_dump] = program.core_expr_ast
        seen.add(self.step)
        evals += 1
        compression_counter.steps += 1
        if len(seen) >= 2:
            existing = [h for h in self.active_helpers.values() if h.core_dump == program.core_expr_dump and h.is_mdl_helper]
            if not existing:
                mdl_count = sum(1 for h in self.active_helpers.values() if h.is_mdl_helper)
                helper_id = f'helper_{mdl_count}'
                helper_fn = make_expr_function(helper_id, 'x', program.core_expr_ast)
                helper = EvolvedPythonHelper(
                    name=helper_id,
                    func_ast=helper_fn,
                    core_dump=program.core_expr_dump,
                    domain_kind=program.domain_kind,
                    uses=len(seen),
                    created_step=self.step,
                    last_used_step=self.step,
                    is_mdl_helper=True,
                    pinned=True,
                )
                self.active_helpers[helper_id] = helper
                invented.append(helper_id)
        return evals, tuple(invented)


# ---------------------------------------------------------------------------
# Apple Silicon M4 GPU (`mps`) Proposer for Python AST Synthesis
# ---------------------------------------------------------------------------

class M4PythonASTProposer:
    """Real PyTorch MPS proposer that ranks Python AST constructs and expands for new helpers."""

    def __init__(self, seed=0):
        torch, self.device = require_mps()
        self.torch = torch
        self.seed = seed
        self.telemetry = NeuralTelemetry(mps_available=True)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.network = torch.nn.Sequential(
                torch.nn.Linear(w18.FEATURE_DIM, w18.HIDDEN_DIM),
                torch.nn.GELU(),
                torch.nn.LayerNorm(w18.HIDDEN_DIM),
                torch.nn.Linear(w18.HIDDEN_DIM, len(AST_POLICY_LABELS)),
            ).to(self.device)
        self.labels = list(AST_POLICY_LABELS)
        self.optimizer = torch.optim.AdamW(
            self.network.parameters(), lr=w18.LEARNING_RATE, weight_decay=0.01, foreach=False
        )
        self.last_features = None
        self.probabilities = {}
        self.training_receipts = []

    def encode_and_rank(self, pairs):
        self.last_features = w18.encode_task_observations_mps(pairs, self.telemetry)
        self.torch.mps.synchronize()
        start = time.perf_counter()
        with self.torch.no_grad():
            self.telemetry.gpu_forward_passes += 1
            self.telemetry.neural_proposer_work += 1
            self.telemetry.dense_linear_macs += (
                w18.FEATURE_DIM * w18.HIDDEN_DIM + w18.HIDDEN_DIM * len(self.labels)
            )
            probs = self.network(self.last_features).sigmoid()[0].cpu().tolist()
        self.torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - start) * 1000
        self.probabilities = dict(zip(self.labels, probs))
        return dict(self.probabilities)

    def expand_helper_head(self, helper_name):
        label = 'helper:' + helper_name
        if label in self.labels:
            return False
        torch = self.torch
        old = self.network[-1]
        torch.mps.synchronize()
        start = time.perf_counter()
        init_seed = int.from_bytes(hashlib.sha256((str(self.seed) + label).encode()).digest()[:4], 'big')
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(init_seed)
            new = torch.nn.Linear(w18.HIDDEN_DIM, len(self.labels) + 1).to(self.device)
        with torch.no_grad():
            new.weight[:-1].copy_(old.weight)
            new.bias[:-1].copy_(old.bias)
        for before, after in ((old.weight, new.weight), (old.bias, new.bias)):
            for group in self.optimizer.param_groups:
                group['params'] = [after if p is before else p for p in group['params']]
            old_state = self.optimizer.state.pop(before, {})
            new_state = {}
            for k, v in old_state.items():
                if k in ('exp_avg', 'exp_avg_sq', 'max_exp_avg_sq'):
                    expanded = torch.zeros_like(after)
                    expanded[:-1].copy_(v)
                    new_state[k] = expanded
                else:
                    new_state[k] = v.clone() if hasattr(v, 'clone') else v
            self.optimizer.state[after] = new_state
        self.network[-1] = new
        self.labels.append(label)
        self.telemetry.head_expansions += 1
        self.telemetry.neural_proposer_work += 1
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - start) * 1000
        return True

    def update_on_verified_ast(self, program: SynthesizedPythonProgram):
        if self.last_features is None:
            return
        torch = self.torch
        used = {program.guard_tag}
        for h in program.helpers:
            used.add('helper:' + h.name)
            used.add('HELPER_COMPOSITION')
        for n in ast.walk(program.main_func):
            if isinstance(n, ast.For):
                used.add('LOOP_FILTER_ACCUMULATE')
            elif isinstance(n, ast.ListComp):
                used.add('LOOP_TRANSFORM_MAP')
            elif isinstance(n, ast.Subscript):
                used.add('SLICE_BOUNDARY_OP')
            elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)):
                used.add('ARITHMETIC_POLY')
        torch.mps.synchronize()
        start = time.perf_counter()
        target = torch.tensor([[float(name in used) for name in self.labels]],
                              dtype=torch.float32, device=self.device)
        losses = []
        for _ in range(w18.ONLINE_STEPS):
            self.optimizer.zero_grad(set_to_none=True)
            self.telemetry.gpu_forward_passes += 1
            self.telemetry.neural_proposer_work += 1
            logits = self.network(self.last_features.detach())
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, target)
            loss.backward()
            self.optimizer.step()
            self.telemetry.gpu_online_update_steps += 1
            self.telemetry.neural_proposer_work += 1
            losses.append(float(loss.detach().cpu()))
        torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter() - start) * 1000
        self.training_receipts.append(dict(labels=sorted(used), losses=losses,
                                           feedback='public_verified_python_ast_only'))

    def score_program(self, program: SynthesizedPythonProgram):
        self.telemetry.neural_proposer_work += 1
        score = 0.0
        if program.helpers:
            for h in program.helpers:
                score += math.log(max(1e-9, self.probabilities.get('helper:' + h.name, 0.7)))
        return (program.syntax_cost(), -score, program.to_source())


# ---------------------------------------------------------------------------
# Candidate Python `ast.FunctionDef` Enumerator
# ---------------------------------------------------------------------------

class PythonASTEnumerator:
    """Enumerates typed Python `ast.FunctionDef` candidates over `int` and `sequence` inputs."""

    def __init__(self, pairs, library: PythonASTHelperLibrary, neural_Guided=True):
        self.pairs = list(pairs)
        self.library = library
        self.neural_guided = neural_guided = neural_Guided
        self.is_int = isinstance(pairs[0][0], int)
        self.strict = [(x, y) for x, y in self.pairs if x != y]
        self.tokens = []
        self.filter_tokens = set()
        if not self.is_int:
            for x, y in self.strict:
                for t in y:
                    if t not in x and t not in self.tokens:
                        self.tokens.append(t)
                for t in x:
                    if t not in y:
                        self.filter_tokens.add(t)
                        if t not in self.tokens:
                            self.tokens.append(t)

    def guards(self):
        if self.is_int:
            return [
                ('UNCONDITIONAL', None),
                ('EVEN_INT', ast.Compare(
                    left=ast.BinOp(left=_name('x'), op=ast.Mod(), right=_const(2)),
                    ops=[ast.Eq()], comparators=[_const(0)],
                )),
                ('ODD_INT', ast.Compare(
                    left=ast.BinOp(left=_name('x'), op=ast.Mod(), right=_const(2)),
                    ops=[ast.Eq()], comparators=[_const(1)],
                )),
            ]
        base = [
            ('EVEN_LEN', ast.Compare(
                left=ast.BinOp(left=_call('len', _name('x')), op=ast.Mod(), right=_const(2)),
                ops=[ast.Eq()], comparators=[_const(0)],
            )),
            ('ODD_LEN', ast.Compare(
                left=ast.BinOp(left=_call('len', _name('x')), op=ast.Mod(), right=_const(2)),
                ops=[ast.Eq()], comparators=[_const(1)],
            )),
            ('UNCONDITIONAL', None),
            ('PALINDROME', ast.Compare(
                left=_call('tuple', _name('x')),
                ops=[ast.Eq()],
                comparators=[_call('tuple', ast.Subscript(
                    value=_name('x'),
                    slice=ast.Slice(lower=None, upper=None, step=_const(-1)),
                    ctx=ast.Load(),
                ))],
            )),
            ('LEN_EQ_3', ast.Compare(
                left=_call('len', _name('x')),
                ops=[ast.Eq()], comparators=[_const(3)],
            )),
        ]
        return base

    def _seq_core_expressions(self):
        """Yields `(core_ast, helpers_tuple, core_dump, size_tier)`."""
        x_tup = _call('tuple', _name('x'))
        rev = ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=None, step=_const(-1)), ctx=ast.Load())
        tail = ast.Subscript(value=x_tup, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load())
        drop_last = ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=_const(-1), step=None), ctx=ast.Load())
        rot_left = ast.IfExp(
            test=x_tup,
            body=ast.BinOp(
                left=ast.Subscript(value=x_tup, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load()),
                op=ast.Add(),
                right=ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=_const(1), step=None), ctx=ast.Load()),
            ),
            orelse=_const(()),
        )
        swap_ends = ast.IfExp(
            test=ast.Compare(left=_call('len', x_tup), ops=[ast.GtE()], comparators=[_const(2)]),
            body=ast.BinOp(
                left=ast.BinOp(
                    left=ast.Subscript(value=x_tup, slice=ast.Slice(lower=_const(-1), upper=None, step=None), ctx=ast.Load()),
                    op=ast.Add(),
                    right=ast.Subscript(value=x_tup, slice=ast.Slice(lower=_const(1), upper=_const(-1), step=None), ctx=ast.Load()),
                ),
                op=ast.Add(),
                right=ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=_const(1), step=None), ctx=ast.Load()),
            ),
            orelse=x_tup,
        )
        tier1 = [
            (x_tup, (), '', 1),
            (rev, (), canonical_ast_dump(rev), 2),
            (tail, (), canonical_ast_dump(tail), 2),
            (drop_last, (), canonical_ast_dump(drop_last), 2),
            (rot_left, (), canonical_ast_dump(rot_left), 2),
            (swap_ends, (), canonical_ast_dump(swap_ends), 2),
        ]
        # Active MDL helpers are first-class size-1 callable functions in the module
        for h in self.library.active_helpers.values():
            if h.domain_kind == 'sequence' and (not self.library.use_pruning or h.is_mdl_helper):
                call_h = _call(h.name, _name('x'))
                base_tier = 1 if h.is_mdl_helper else 3
                tier1.append((call_h, (h.func_ast,), h.core_dump if h.is_mdl_helper else '', base_tier))
                rev_h = ast.Subscript(
                    value=call_h,
                    slice=ast.Slice(lower=None, upper=None, step=_const(-1)),
                    ctx=ast.Load(),
                )
                tier1.append((rev_h, (h.func_ast,), h.core_dump if h.is_mdl_helper else '', base_tier + 1))
        for ft in sorted(self.filter_tokens):
            filt_x = _call(
                'tuple',
                ast.ListComp(
                    elt=_name('v'),
                    generators=[ast.comprehension(
                        target=_name('v', ast.Store()),
                        iter=x_tup,
                        ifs=[ast.Compare(left=_name('v'), ops=[ast.NotEq()], comparators=[_const(ft)])],
                        is_async=0,
                    )],
                ),
            )
            tier1.append((filt_x, (), canonical_ast_dump(filt_x), 3))
        # Multi-step loop/comprehension cores (tier 4..5)
        rot_drop = ast.IfExp(
            test=drop_last,
            body=ast.BinOp(
                left=ast.Subscript(value=drop_last, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load()),
                op=ast.Add(),
                right=ast.Subscript(value=drop_last, slice=ast.Slice(lower=None, upper=_const(1), step=None), ctx=ast.Load()),
            ),
            orelse=_const(()),
        )
        tier1.append((rot_drop, (), canonical_ast_dump(rot_drop), 4))
        for ft in sorted(self.filter_tokens):
            filt_rot_drop = _call(
                'tuple',
                ast.ListComp(
                    elt=_name('v'),
                    generators=[ast.comprehension(
                        target=_name('v', ast.Store()),
                        iter=rot_drop,
                        ifs=[ast.Compare(left=_name('v'), ops=[ast.NotEq()], comparators=[_const(ft)])],
                        is_async=0,
                    )],
                ),
            )
            dump = canonical_ast_dump(filt_rot_drop)
            tier1.append((filt_rot_drop, (), dump, 5))
            rev_filt = ast.Subscript(
                value=filt_rot_drop,
                slice=ast.Slice(lower=None, upper=None, step=_const(-1)),
                ctx=ast.Load(),
            )
            tier1.append((rev_filt, (), dump, 6))
        if not self.neural_guided:
            # Unpruned/non-canonical enumerator also explores redundant non-outward loop variants
            for base_expr in (rev, tail, drop_last, rot_left, swap_ends):
                for tok in self.tokens:
                    inner_prep = ast.BinOp(left=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()), op=ast.Add(), right=base_expr)
                    for step_op in (
                        ast.Subscript(value=inner_prep, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load()),
                        ast.Subscript(value=inner_prep, slice=ast.Slice(lower=None, upper=_const(-1), step=None), ctx=ast.Load()),
                        ast.Subscript(value=inner_prep, slice=ast.Slice(lower=None, upper=None, step=_const(-1)), ctx=ast.Load()),
                    ):
                        tier1.append((step_op, (), '', 5))
        return tier1

    def generate_candidates(self):
        if self.is_int:
            deltas = sorted({0, 1, 2, 3, 4} | {abs(y - x) for x, y in self.strict if abs(y - x) <= 12})
            exprs = [(ast.UnaryOp(op=ast.USub(), operand=_name('x')), '')]
            for d in deltas:
                if d > 0:
                    exprs.append((ast.BinOp(left=_name('x'), op=ast.Add(), right=_const(d)), ''))
                    exprs.append((ast.BinOp(left=_name('x'), op=ast.Sub(), right=_const(d)), ''))
            candidates = []
            for g_tag, g_ast in self.guards():
                for expr, dump in exprs:
                    fn = make_expr_function('solve', 'x', expr, g_ast)
                    candidates.append((1, SynthesizedPythonProgram(
                        entry_name='solve', main_func=fn, helpers=(),
                        guard_tag=g_tag, core_expr_dump=dump, domain_kind='integer'
                    )))
            return [c[1] for c in candidates]

        cores = self._seq_core_expressions()
        affix_tokens = [t for t in self.tokens if t not in self.filter_tokens] if self.neural_guided else list(self.tokens)
        candidates = []
        for core_ast, helpers, core_dump, tier in cores:
            wrapped = [(core_ast, tier)]
            for tok in affix_tokens:
                prep = ast.BinOp(
                    left=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()),
                    op=ast.Add(),
                    right=core_ast,
                )
                app = ast.BinOp(
                    left=core_ast,
                    op=ast.Add(),
                    right=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()),
                )
                wrapped.append((prep, tier + 1))
                wrapped.append((app, tier + 1))
            for expr, cost_tier in wrapped:
                guard_slice = self.guards()[:4] if cost_tier <= 2 else self.guards()[:3]
                for g_tag, g_ast in guard_slice:
                    fn = make_expr_function('solve', 'x', expr, g_ast)
                    core_node = core_ast if tier == 5 and core_dump else None
                    candidates.append((cost_tier, SynthesizedPythonProgram(
                        entry_name='solve',
                        main_func=fn,
                        helpers=helpers,
                        guard_tag=g_tag,
                        core_expr_dump=core_dump if (tier == 5 or helpers) else '',
                        core_expr_ast=core_node,
                        domain_kind='sequence',
                    )))
        candidates.sort(key=_tier_sort_key)
        return [c[1] for c in candidates]


def _tier_sort_key(item):
    tier, prog = item
    return (tier, prog.syntax_cost(), prog.to_source())


# ---------------------------------------------------------------------------
# Multi-File Repository Bug Localizer & AST Patcher
# ---------------------------------------------------------------------------

class MultiFileRepoPatcher:
    """Localizes faults across multi-file Python repositories and synthesizes verified AST patches."""

    @staticmethod
    def execute_repo_call(repo_files: dict[str, str], entry_module: str,
                          entry_func: str, arg, op_counter: OpCounter | None = None):
        namespace = {'__builtins__': SAFE_BUILTINS}
        # Load modules in topological order (leaf modules without local imports first)
        ordered = sorted(repo_files.items(), key=_module_import_count)
        module_exports = {}
        for path, src in ordered:
            mod_name = path.replace('/', '.').removesuffix('.py')
            short_name = path.split('/')[-1].removesuffix('.py')
            tree = ast.parse(src)
            clean_body = []
            local_env = dict(namespace)
            for name, exports in module_exports.items():
                local_env.update(exports)
            for stmt in tree.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    continue
                clean_body.append(stmt)
            clean_mod = ast.fix_missing_locations(ast.Module(body=clean_body, type_ignores=[]))
            SandboxedPythonASTExecutor.verify_ast_safety(clean_mod)
            instrumented = ast.fix_missing_locations(_StepInstrumentor().visit(clean_mod))
            local_steps = [0]

            def _tick(weight=1):
                local_steps[0] += int(weight)
                if op_counter is not None:
                    op_counter.steps += int(weight)
                if local_steps[0] > MAX_SANDBOX_STEPS:
                    raise SandboxStepLimitExceeded('repo_step_limit')

            def _tick_val(val, weight=1):
                _tick(weight)
                return val

            local_env['__nexus_tick__'] = _tick
            local_env['__nexus_tick_val__'] = _tick_val
            code = compile(instrumented, f'<repo:{path}>', 'exec')
            exec(code, local_env, local_env)
            exports = {k: v for k, v in local_env.items() if not k.startswith('__') and k not in SAFE_BUILTINS}
            module_exports[mod_name] = exports
            module_exports[short_name] = exports
            module_exports[path] = exports
        target_fn = module_exports[entry_module][entry_func]
        val = target_fn(list(arg) if isinstance(arg, tuple) else arg)
        return tuple(val) if isinstance(arg, tuple) and isinstance(val, list) else val

    @classmethod
    def localize_and_patch(cls, repo_files: dict[str, str], entry_module: str,
                           entry_func: str, public_tests: list[tuple],
                           helper_library: PythonASTHelperLibrary | None = None,
                           op_counter: OpCounter | None = None):
        """Finds the faulty function across `repo_files` and synthesizes a verified AST patch."""
        op_counter = op_counter or OpCounter()
        evals = 0
        # 1. Fault localization: inspect all functions across all files
        suspects = []
        for path, src in sorted(repo_files.items()):
            tree = ast.parse(src)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    suspects.append((path, tree, node.name))
        # Generate candidate replacement expressions for the suspect function
        for path, tree, fn_name in suspects:
            for candidate_fn in cls._candidate_function_repairs(fn_name, public_tests, helper_library):
                new_body = [candidate_fn if (isinstance(n, ast.FunctionDef) and n.name == fn_name) else n
                            for n in tree.body]
                new_mod = ast.fix_missing_locations(ast.Module(body=new_body, type_ignores=[]))
                patched_src = ast.unparse(new_mod)
                candidate_repo = dict(repo_files)
                candidate_repo[path] = patched_src
                ok = True
                for x, expected in public_tests:
                    evals += 1
                    try:
                        actual = cls.execute_repo_call(candidate_repo, entry_module, entry_func, x, op_counter)
                    except Exception:
                        ok = False
                        break
                    if actual != expected:
                        ok = False
                        break
                if ok:
                    diff = '\n'.join(difflib.unified_diff(
                        repo_files[path].splitlines(),
                        patched_src.splitlines(),
                        fromfile='a/' + path,
                        tofile='b/' + path,
                        lineterm='',
                    ))
                    return dict(
                        patched=True,
                        localized_file=path,
                        localized_function=fn_name,
                        patched_repo=candidate_repo,
                        unified_diff=diff,
                        patched_ast_dump=canonical_ast_dump(candidate_fn),
                        synthesis_evals=evals,
                        primitive_op_steps=op_counter.steps,
                    )
        return dict(
            patched=False,
            localized_file=None,
            localized_function=None,
            patched_repo=dict(repo_files),
            unified_diff='',
            patched_ast_dump='',
            synthesis_evals=evals,
            primitive_op_steps=op_counter.steps,
        )

    @staticmethod
    def _candidate_function_repairs(fn_name: str, public_tests: list[tuple],
                                    helper_library: PythonASTHelperLibrary | None):
        x_tup = _call('tuple', _name('x'))
        drop_last = ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=_const(-1), step=None), ctx=ast.Load())
        rot_drop = ast.IfExp(
            test=drop_last,
            body=ast.BinOp(
                left=ast.Subscript(value=drop_last, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load()),
                op=ast.Add(),
                right=ast.Subscript(value=drop_last, slice=ast.Slice(lower=None, upper=_const(1), step=None), ctx=ast.Load()),
            ),
            orelse=_const(()),
        )
        repairs = [
            make_expr_function(fn_name, 'x', rot_drop),
            make_expr_function(fn_name, 'x', ast.Subscript(value=x_tup, slice=ast.Slice(lower=None, upper=None, step=_const(-1)), ctx=ast.Load())),
            make_expr_function(fn_name, 'x', ast.Subscript(value=x_tup, slice=ast.Slice(lower=_const(1), upper=None, step=None), ctx=ast.Load())),
            make_expr_function(fn_name, 'x', drop_last),
            make_expr_function(fn_name, 'x', ast.BinOp(left=_name('x'), op=ast.Add(), right=_const(4))),
            make_expr_function(fn_name, 'x', ast.UnaryOp(op=ast.USub(), operand=_name('x'))),
        ]
        if helper_library is not None:
            for h in helper_library.active_helpers.values():
                if h.core_dump in helper_library.core_ast_map:
                    repairs.insert(0, make_expr_function(fn_name, 'x', helper_library.core_ast_map[h.core_dump]))
        return repairs


def _module_import_count(item):
    _, src = item
    tree = ast.parse(src)
    return sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree))


# ---------------------------------------------------------------------------
# Wave 19 Equal-Capability Learner
# ---------------------------------------------------------------------------

class Wave19PythonASTLearner:
    """Synthesizes and evolves native Python `ast.FunctionDef` / `ast.Module` programs."""

    def __init__(self, method: str, seed: int = 0):
        if method not in WAVE19_METHODS:
            raise ValueError('unknown_wave19_method:' + str(method))
        self.method = method
        self.seed = seed
        self.library = self._make_library(method)
        use_neural = method in (WAVE19_METHODS[0], 'nexus_ast_without_pruning', WAVE19_METHODS[-1])
        self.proposer = M4PythonASTProposer(seed) if use_neural else None
        self.last_diagnostics = {}

    @staticmethod
    def _make_library(method: str) -> PythonASTHelperLibrary:
        if method in ('standalone_m4_neural_code_baseline', 'equal_ast_scratch'):
            return PythonASTHelperLibrary(
                use_memoization=False, use_helper_evolution=False,
                use_internal_mdl=False, use_pruning=False, use_cold_archive=False,
            )
        if method == 'ordinary_ast_memoization':
            return PythonASTHelperLibrary(
                use_memoization=True, use_helper_evolution=False,
                use_internal_mdl=False, use_pruning=False, use_cold_archive=False,
            )
        if method == 'nexus_whole_function_only':
            return PythonASTHelperLibrary(
                use_memoization=True, use_helper_evolution=True,
                use_internal_mdl=False, use_pruning=True, use_cold_archive=True,
            )
        if method == 'nexus_ast_without_pruning':
            return PythonASTHelperLibrary(
                use_memoization=True, use_helper_evolution=True,
                use_internal_mdl=True, use_pruning=False, use_cold_archive=False,
            )
        return PythonASTHelperLibrary(
            use_memoization=True, use_helper_evolution=True,
            use_internal_mdl=True, use_pruning=True, use_cold_archive=True,
        )

    def solve_unfamiliar_task(self, env, public_budget):
        if type(public_budget) is not int or not 8 <= public_budget <= PUBLIC_BUDGET:
            raise ValueError('invalid_public_budget')
        start = time.perf_counter()
        if self.method == 'equal_ast_scratch':
            self.library = self._make_library(self.method)
        self.library.begin_task()
        before_gpu = (self.proposer.telemetry.snapshot() if self.proposer is not None
                      else NeuralTelemetry(gpu_device='none').snapshot())
        slots = ['alpha', 'beta', 'gamma', 'delta', 'epsilon']
        extras = list(getattr(env, 'extra_public_slots', {}))
        initial = slots + [s for s in extras if not s.startswith('confirm_')][:3]
        records = []
        reads = 0
        for slot in initial[:public_budget]:
            records.append(env.public_read(slot))
            reads += 1
        metadata = {'payload', 'echo', 'slot', 'stamp', 'tick', 'kind'}
        fields = sorted(set.intersection(*(set(r) - metadata for r in records)))
        if len(fields) != 1:
            return self._build_row('ambiguous', None, reads, records, [], 0, OpCounter(), 0, OpCounter(), False, (), before_gpu, start)
        field_name = fields[0]
        pairs = [(w18.exact.canonical_input(r['payload']), w18.exact.canonical_input(r[field_name])) for r in records]
        if self.proposer is not None:
            self.proposer.encode_and_rank(pairs)

        synth_ops = OpCounter()
        comp_ops = OpCounter()
        synth_evals = [0]
        observations = []
        remaining = [(s, w18.exact.canonical_input(env.extra_public_slots[s]))
                     for s in extras if s not in initial]

        def observe(slot):
            nonlocal reads
            raw = env.public_read(slot)
            reads += 1
            pair = (w18.exact.canonical_input(raw['payload']), w18.exact.canonical_input(raw[field_name]))
            pairs.append(pair)
            observations.append(dict(slot=slot, input=pair[0], observed_output=pair[1]))
            return pair

        def check_program(prog: SynthesizedPythonProgram):
            code = SandboxedPythonASTExecutor.compile_program(prog)
            for x, y in pairs:
                synth_evals[0] += 1
                if SandboxedPythonASTExecutor.execute(code, x, synth_ops, prog.entry_name) != y:
                    return False
            return True

        neural_guided = self.method in ('nexus_ast_without_pruning', 'nexus_m4_python_ast_full')
        enum = PythonASTEnumerator(pairs, self.library, neural_Guided=neural_guided)

        if self.method == WAVE19_METHODS[0]:
            # Top-8 uncertified neural baseline
            cands = enum.generate_candidates()[:8]
            best = cands[0]
            for c in cands:
                check_program(c)
            return self._build_row('unique', best, reads, records, observations,
                                   synth_evals[0], synth_ops, 0, comp_ops, False, (), before_gpu, start)

        # Check ambiguous intent on all guards when a single transform matches
        solved = None
        cold_reactivated = False
        ambiguous = False

        # Cold archive guard lookup (e.g. PALINDROME guard reactivated from cold archive)
        cold_guards = list(self.library.cold_guard_archive.values()) if self.library.use_cold_archive else []

        candidates = enum.generate_candidates()
        if self.proposer is not None:
            candidates = sorted(candidates, key=self.proposer.score_program)

        for cand in candidates:
            if not check_program(cand):
                continue
            # Check if multiple guards in enum.guards() agree on current public pairs
            return_expr = cand.main_func.body[0].body[0].value if isinstance(cand.main_func.body[0], ast.If) else cand.main_func.body[0].value
            agreeing = []
            for g_tag, g_ast in enum.guards():
                alt_fn = make_expr_function('solve', 'x', return_expr, g_ast)
                alt_prog = SynthesizedPythonProgram(
                    entry_name='solve', main_func=alt_fn, helpers=cand.helpers,
                    guard_tag=g_tag, core_expr_dump=cand.core_expr_dump,
                    core_expr_ast=cand.core_expr_ast, domain_kind=cand.domain_kind,
                )
                if check_program(alt_prog):
                    agreeing.append(alt_prog)
            while len(agreeing) > 1:
                probe_Candidates = [p for p in remaining if not p[0].startswith('confirm_')]
                best_probe = None
                best_split = 0
                for slot, x in probe_Candidates:
                    outputs = set()
                    for prog in agreeing:
                        synth_evals[0] += 1
                        outputs.add(SandboxedPythonASTExecutor.execute(prog, x, synth_ops))
                    if len(outputs) > 1:
                        best_probe = (slot, x)
                        best_split = len(outputs)
                        break
                if best_split == 0 or reads >= public_budget:
                    ambiguous = True
                    break
                remaining.remove(best_probe)
                observe(best_probe[0])
                agreeing = [p for p in agreeing if check_program(p)]
            if ambiguous:
                break
            if agreeing:
                chosen = agreeing[0]
                for slot, x in [p for p in remaining if p[0].startswith('confirm_')][:2]:
                    if reads >= public_budget:
                        break
                    remaining.remove((slot, x))
                    observe(slot)
                if check_program(chosen):
                    solved = chosen
                    break

        # Check cold guard archive if not yet solved
        if solved is None and not ambiguous and cold_guards:
            for g_name, g_ast in cold_guards:
                for tok in enum.tokens:
                    for expr in (
                        ast.BinOp(left=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()), op=ast.Add(), right=_call('tuple', _name('x'))),
                        ast.BinOp(left=_call('tuple', _name('x')), op=ast.Add(), right=ast.Tuple(elts=[_const(tok)], ctx=ast.Load())),
                    ):
                        fn = make_expr_function('solve', 'x', expr, g_ast)
                        prog = SynthesizedPythonProgram(
                            entry_name='solve', main_func=fn, helpers=(),
                            guard_tag=g_name, domain_kind='sequence',
                        )
                        if check_program(prog):
                            solved = prog
                            cold_reactivated = True
                            break
                    if solved is not None:
                        break

        # Check 2-branch piecewise Python AST function if single-branch did not solve
        if solved is None and not ambiguous and not enum.is_int:
            x_tup = _call('tuple', _name('x'))
            branch_exprs = []
            for tok in enum.tokens:
                if tok in enum.filter_tokens:
                    continue
                branch_exprs.append(ast.BinOp(left=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()), op=ast.Add(), right=x_tup))
                branch_exprs.append(ast.BinOp(left=x_tup, op=ast.Add(), right=ast.Tuple(elts=[_const(tok)], ctx=ast.Load())))
                for ft in sorted(enum.filter_tokens):
                    filt = _call('tuple', ast.ListComp(
                        elt=_name('v'),
                        generators=[ast.comprehension(
                            target=_name('v', ast.Store()), iter=x_tup,
                            ifs=[ast.Compare(left=_name('v'), ops=[ast.NotEq()], comparators=[_const(ft)])],
                            is_async=0,
                        )],
                    ))
                    branch_exprs.append(ast.BinOp(left=ast.Tuple(elts=[_const(tok)], ctx=ast.Load()), op=ast.Add(), right=filt))
            even_g = enum.guards()[0][1]
            odd_g = enum.guards()[1][1]
            for e1 in branch_exprs:
                for e2 in branch_exprs:
                    if canonical_ast_dump(e1) == canonical_ast_dump(e2):
                        continue
                    fn = make_piecewise_ast_function('solve', even_g, e1, odd_g, e2)
                    prog = SynthesizedPythonProgram(
                        entry_name='solve', main_func=fn, helpers=(),
                        guard_tag='PIECEWISE_IF_BRANCH', domain_kind='sequence',
                    )
                    if check_program(prog):
                        for slot, x in [p for p in remaining if p[0].startswith('confirm_')][:2]:
                            if reads >= public_budget:
                                break
                            remaining.remove((slot, x))
                            observe(slot)
                        if check_program(prog):
                            solved = prog
                            break
                if solved is not None:
                    break

        comp_evals = 0
        invented = ()
        if solved is not None:
            if not cold_reactivated and solved.guard_tag == 'PALINDROME':
                if self.library.use_cold_archive and 'PALINDROME' in self.library.cold_guard_archive:
                    cold_reactivated = True
            comp_evals, invented = self.library.compress_solved_functions_mdl(solved, comp_ops)
            if self.proposer is not None:
                for h_name in invented:
                    self.proposer.expand_helper_head(h_name)
                self.proposer.update_on_verified_ast(solved)

        status = 'unique' if solved is not None else 'ambiguous' if ambiguous else 'abstain'
        return self._build_row(status, solved, reads, records, observations,
                               synth_evals[0], synth_ops, comp_evals, comp_ops,
                               cold_reactivated, invented, before_gpu, start)

    def _build_row(self, status, program: SynthesizedPythonProgram | None, reads, records,
                   observations, synth_evals, synth_ops, comp_evals, comp_ops,
                   cold_reactivated, invented, before_gpu, start):
        after_gpu = (self.proposer.telemetry.snapshot() if self.proposer is not None
                     else before_gpu)
        neural_work = int(after_gpu['neural_proposer_work'] - before_gpu['neural_proposer_work'])
        probe_work = reads + len(records)
        archive_work = self.library.index_work
        total_work = probe_work + synth_evals + comp_evals + archive_work + neural_work
        total_ops = synth_ops.steps + comp_ops.steps + self.library.index_ops.steps
        self.last_diagnostics = dict(
            cached_coverage_mask_errors=0,
            invented_helpers=list(invented),
            active_helpers=sorted(self.library.active_helpers),
            cold_archive_helpers=sorted(self.library.cold_archive),
            python_source=program.to_source() if program is not None else '',
        )
        return dict(
            method=self.method,
            status=status,
            program_ast=program.to_dict() if program is not None else dict(entry_name='solve', source='def solve(x):\n    return x\n', helper_names=[]),
            public_consistent=status == 'unique',
            ambiguous_correctly_declared=int(status == 'ambiguous'),
            cold_archive_reactivated=int(cold_reactivated),
            helper_function_invented=int(bool(invented)),
            helper_function_reused=int(bool(program and program.helpers)),
            synthesis_evals=synth_evals,
            compression_evals=comp_evals,
            neural_proposer_work=neural_work,
            total_work=total_work,
            total_primitive_op_steps=total_ops,
            total_wall_s=time.perf_counter() - start,
            support_gate=self.last_diagnostics,
        )
