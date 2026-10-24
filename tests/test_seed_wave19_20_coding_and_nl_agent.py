"""Unit and M4-GPU integration tests for Wave 19 (Python AST Coding) & Wave 20 (Grounded NL Agent)."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import pytest

from nexus.seed import wave18_m4_gpu_neuro_symbolic_learner as w18
from nexus.seed import wave19_python_ast_code_evolver as w19
from nexus.seed import wave20_grounded_nl_conversation_agent as w20
from nexus.seed.mechanism_wave18_fresh_assessment import fresh_specs
from scripts.run_wave17_exact_cache_assessment import PublicWorld

ROOT = Path(__file__).resolve().parents[1]


def test_wave19_20_static_hygiene_and_untouched_runtime():
    for rel in (
        'src/nexus/seed/wave19_python_ast_code_evolver.py',
        'src/nexus/seed/wave20_grounded_nl_conversation_agent.py',
    ):
        source = (ROOT / rel).read_text()
        tree = ast.parse(source)
        assert not any(isinstance(n, ast.Lambda) for n in ast.walk(tree)), rel
    solve = next(
        n for n in ast.walk(ast.parse((ROOT / 'src/nexus/seed/wave19_python_ast_code_evolver.py').read_text()))
        if isinstance(n, ast.FunctionDef) and n.name == 'solve_unfamiliar_task'
    )
    assert [a.arg for a in solve.args.args] == ['self', 'env', 'public_budget']
    runtime_sha = hashlib.sha256((ROOT / 'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest()
    assert runtime_sha == '5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781'


def test_native_python_ast_for_loop_synthesis_and_sandbox_safety():
    fn = w19.make_loop_filter_map_function(
        'solve', skip_token='kora', prefix_token='zelin', drop_last=True, rot_left=True
    )
    assert any(isinstance(n, ast.For) for n in ast.walk(fn))
    prog = w19.SynthesizedPythonProgram(entry_name='solve', main_func=fn)
    ops = w19.OpCounter()
    out = w19.SandboxedPythonASTExecutor.execute(prog, ('alor', 'kora', 'bren', 'cyra'), ops)
    assert out == ('zelin', 'bren', 'alor')
    assert ops.steps > 0

    # Unsafe AST constructs must be rejected before compilation
    unsafe_mod = ast.parse('import os\ndef solve(x):\n    return x\n')
    with pytest.raises(ValueError, match='forbidden_ast_construct'):
        w19.SandboxedPythonASTExecutor.verify_ast_safety(unsafe_mod)

    # Step limit enforcement on runaway loops
    infinite_fn = ast.parse('def solve(x):\n    while True:\n        x = x\n').body[0]
    inf_prog = w19.SynthesizedPythonProgram(entry_name='solve', main_func=infinite_fn)
    with pytest.raises(w19.SandboxStepLimitExceeded):
        w19.SandboxedPythonASTExecutor.execute(inf_prog, (1, 2, 3), max_steps=40)


def test_mdl_python_helper_function_invention_and_mps_head_expansion():
    lib = w19.PythonASTHelperLibrary()
    proposer = w19.M4PythonASTProposer(seed=7)
    x_tup = w19._call('tuple', w19._name('x'))
    core_ast = ast.Subscript(
        value=x_tup,
        slice=ast.Slice(lower=w19._const(1), upper=w19._const(-1), step=None),
        ctx=ast.Load(),
    )
    core_dump = w19.canonical_ast_dump(core_ast)

    lib.begin_task()
    fn1 = w19.make_expr_function(
        'solve', 'x',
        ast.BinOp(left=ast.Tuple(elts=[w19._const('p1')], ctx=ast.Load()), op=ast.Add(), right=core_ast),
    )
    p1 = w19.SynthesizedPythonProgram('solve', fn1, (), 'EVEN_LEN', core_dump, core_ast, 'sequence')
    ops = w19.OpCounter()
    evals1, inv1 = lib.compress_solved_functions_mdl(p1, ops)
    assert inv1 == () and evals1 > 0

    lib.begin_task()
    fn2 = w19.make_expr_function(
        'solve', 'x',
        ast.BinOp(left=core_ast, op=ast.Add(), right=ast.Tuple(elts=[w19._const('s2')], ctx=ast.Load())),
    )
    p2 = w19.SynthesizedPythonProgram('solve', fn2, (), 'EVEN_LEN', core_dump, core_ast, 'sequence')
    evals2, inv2 = lib.compress_solved_functions_mdl(p2, ops)
    assert inv2 == ('helper_0',) and 'helper_0' in lib.active_helpers
    assert proposer.expand_helper_head('helper_0')
    assert 'helper:helper_0' in proposer.labels

    # Execute a main function that calls the invented `helper_0(x)` inside `ast.Module`
    helper_def = lib.active_helpers['helper_0'].func_ast
    caller_fn = w19.make_expr_function(
        'solve', 'x',
        ast.BinOp(
            left=ast.Tuple(elts=[w19._const('reused')], ctx=ast.Load()),
            op=ast.Add(),
            right=w19._call('helper_0', w19._name('x')),
        ),
    )
    combined = w19.SynthesizedPythonProgram('solve', caller_fn, (helper_def,))
    assert 'def helper_0(x):' in combined.to_source()
    assert w19.SandboxedPythonASTExecutor.execute(combined, ('a', 'b', 'c', 'd')) == ('reused', 'b', 'c')


def test_multi_file_repository_fault_localization_and_patching():
    repo = {
        'pkg/normalizer.py': (
            'def normalize_tokens(x):\n'
            '    return tuple(x)[::-1]\n'  # Bug: reverses instead of dropping last and rotating left
        ),
        'pkg/validator.py': (
            'def validate_non_empty(x):\n'
            '    return len(x) > 0\n'
        ),
        'pkg/pipeline.py': (
            'from pkg.normalizer import normalize_tokens\n'
            'from pkg.validator import validate_non_empty\n'
            'def run_pipeline(x):\n'
            '    if not validate_non_empty(x):\n'
            '        return ()\n'
            '    return (\'zelin\',) + normalize_tokens(x)\n'
        ),
    }
    tests = [
        (('a', 'b', 'c', 'd'), ('zelin', 'b', 'c', 'a')),
        (('p', 'q', 'r'), ('zelin', 'q', 'p')),
    ]
    ops = w19.OpCounter()
    result = w19.MultiFileRepoPatcher.localize_and_patch(
        repo, 'pkg/pipeline.py', 'run_pipeline', tests, op_counter=ops
    )
    assert result['patched'] is True
    assert result['localized_file'] == 'pkg/normalizer.py'
    assert result['localized_function'] == 'normalize_tokens'
    assert '--- a/pkg/normalizer.py' in result['unified_diff']
    assert '+++ b/pkg/normalizer.py' in result['unified_diff']
    private_out = w19.MultiFileRepoPatcher.execute_repo_call(
        result['patched_repo'], 'pkg/pipeline.py', 'run_pipeline', ('u', 'v', 'w', 'x')
    )
    assert private_out == ('zelin', 'v', 'w', 'u')


def test_wave19_complete_python_ast_benchmark_mps():
    specs = fresh_specs()
    rows = []
    for seed in (0, 1, 2):
        for method in w19.WAVE19_METHODS:
            learner = w19.Wave19PythonASTLearner(method, seed)
            for spec in specs:
                part = spec['seeds'][seed]
                world = PublicWorld(part)
                row = learner.solve_unfamiliar_task(world, 24)
                world.lock()
                correct = row['status'] == spec['gold']
                if row['status'] == 'unique':
                    correct = correct and all(
                        w19.SandboxedPythonASTExecutor.execute(row['program_ast'], x) == w18.exact.canonical_input(y)
                        for x, y in part['private']
                    )
                row.update(seed=seed, task_id=spec['id'], gold=spec['gold'], private_correct=correct)
                rows.append(row)
    totals = {
        m: {
            k: sum(int(r[k]) for r in rows if r['method'] == m)
            for k in ('private_correct', 'total_work', 'total_primitive_op_steps',
                      'helper_function_invented', 'helper_function_reused', 'cold_archive_reactivated')
        }
        for m in w19.WAVE19_METHODS
    }
    full = totals['nexus_m4_python_ast_full']
    whole = totals['nexus_whole_function_only']
    no_prune = totals['nexus_ast_without_pruning']
    assert full['private_correct'] == 54
    assert full['helper_function_invented'] >= 3
    assert full['helper_function_reused'] >= 9
    assert full['cold_archive_reactivated'] >= 3
    assert full['total_work'] < whole['total_work']
    assert full['total_primitive_op_steps'] < whole['total_primitive_op_steps']
    assert full['total_work'] < no_prune['total_work']
    assert full['total_primitive_op_steps'] < no_prune['total_primitive_op_steps']


def test_wave20_grounded_conversation_cross_domain_and_zero_hallucinations():
    agent = w20.Wave20GroundedConversationAgent(seed=0)

    # Turn 1 & Turn 2: Teach the agent two Python sequence tasks sharing the core so `helper_0` is invented
    r1 = agent.handle_user_turn(
        "Write code for python function: ['a', 'kora', 'b', 'c'] -> ['zelin', 'b', 'a'], "
        "['b', 'c', 'kora'] -> ['b', 'c', 'kora'], "
        "['d', 'e', 'kora', 'f', 'g', 'h'] -> ['zelin', 'e', 'f', 'g', 'd'] "
        "and apply to ['p', 'kora', 'q', 'r']"
    )
    assert r1.status == 'verified_answer'
    assert r1.verified_output == ('zelin', 'q', 'p')
    assert r1.hallucinated_claims == 0

    r2 = agent.handle_user_turn(
        "Write code for python function: ['a', 'kora', 'b', 'c'] -> ['b', 'a', 'mavu'], "
        "['b', 'c', 'kora'] -> ['b', 'c', 'kora'], "
        "['d', 'e', 'kora', 'f', 'g', 'h'] -> ['e', 'f', 'g', 'd', 'mavu'] "
        "and apply to ['p', 'kora', 'q', 'r']"
    )
    assert r2.status == 'verified_answer'
    assert r2.verified_output == ('q', 'p', 'mavu')
    assert 'helper_0' in agent.code_learner.library.active_helpers

    # Turn 3: Cross-domain transfer — invoke the learned `helper_0` inside a STATE commit policy!
    r3 = agent.handle_user_turn(
        "In cross-domain state controller with mode=armed retries=1 commit=verified_tok "
        "and helper transformation, evaluate on ['x1', 'kora', 'x2', 'x3']"
    )
    assert r3.status == 'verified_answer'
    assert r3.cross_domain_reused is True
    assert r3.verified_output == ('verified_tok', 'x2', 'x1')
    assert r3.hallucinated_claims == 0

    # Turn 4: State precondition blocked when retries > 2
    r4 = agent.handle_user_turn(
        "In state controller with mode=armed retries=5 commit=verified_tok, evaluate on ['x1', 'x2']"
    )
    assert r4.status == 'verified_answer'
    assert r4.verified_output == ('STATE_BLOCKED', ('x1', 'x2'))

    # Turn 5 & Turn 6: Active epistemic clarification in English on ambiguous examples, then resolution
    r5 = agent.handle_user_turn(
        "Given ['a', 'b', 'c'] -> ['a', 'b', 'c', 'luma'] and ['a', 'b', 'c', 'd'] -> ['a', 'b', 'c', 'd'], "
        "what is ['u', 'v', 'w', 'z', 'q']?"
    )
    assert r5.status == 'clarification_requested'
    assert 'Epistemic clarification required' in r5.english_response
    assert r5.distinguishing_probe == ('u', 'v', 'w', 'z', 'q')

    r6 = agent.handle_user_turn("Clarification: ['u', 'v', 'w', 'z', 'q'] -> ['u', 'v', 'w', 'z', 'q', 'luma']")
    assert r6.status == 'verified_answer'
    assert r6.verified_output == ('u', 'v', 'w', 'z', 'q', 'luma')
    assert r6.hallucinated_claims == 0

    # Turn 7: Multi-file repository bug localization & patching via natural-English turn
    repo = {
        'pkg/normalizer.py': 'def normalize_tokens(x):\n    return tuple(x)[::-1]\n',
        'pkg/pipeline.py': (
            'from pkg.normalizer import normalize_tokens\n'
            'def run_pipeline(x):\n'
            '    return (\'patched\',) + normalize_tokens(x)\n'
        ),
    }
    r7 = agent.handle_user_turn(
        "Please localize and patch the repository bug so ['a', 'b', 'c', 'd'] -> ['patched', 'b', 'c', 'a'] "
        "and ['p', 'q', 'r'] -> ['patched', 'q', 'p'], and evaluate on ['m', 'n', 'o', 'p']",
        context={'repo_files': repo, 'repo_entry': ('pkg/pipeline.py', 'run_pipeline')},
    )
    assert r7.status == 'verified_answer'
    assert r7.verified_output == ('patched', 'n', 'o', 'm')
    assert '--- a/pkg/normalizer.py' in r7.unified_diff

    # Turn 8: Unverified external world-knowledge query -> explicit English abstention (0 hallucinations)
    r8 = agent.handle_user_turn("What is the current stock price of Acme Corp and the weather in Tokyo?")
    assert r8.status == 'abstain'
    assert r8.hallucinated_claims == 0
    assert 'abstain rather than hallucinate' in r8.english_response
