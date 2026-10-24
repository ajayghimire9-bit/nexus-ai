"""Runner and standalone replay verifier for Wave 19 (Python AST Coding) & Wave 20 (Grounded NL Conversation)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nexus.seed import wave18_m4_gpu_neuro_symbolic_learner as w18
from nexus.seed import wave19_python_ast_code_evolver as w19
from nexus.seed import wave20_grounded_nl_conversation_agent as w20
from nexus.seed.mechanism_wave18_fresh_assessment import fresh_specs
from scripts.run_wave17_exact_cache_assessment import PublicWorld


def run_wave19_benchmark():
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
                row.update(seed=seed, task_id=spec['id'], gold=spec['gold'], private_correct=int(correct))
                rows.append(row)

    # Multi-file repository patching benchmark across 3 seeds
    repo_cases = []
    for seed in (0, 1, 2):
        tok = ('zelin', 'toren', 'sira')[seed]
        repo = {
            'pkg/normalizer.py': 'def normalize_tokens(x):\n    return tuple(x)[::-1]\n',
            'pkg/validator.py': 'def validate_non_empty(x):\n    return len(x) > 0\n',
            'pkg/pipeline.py': (
                'from pkg.normalizer import normalize_tokens\n'
                'from pkg.validator import validate_non_empty\n'
                f'def run_pipeline(x):\n    if not validate_non_empty(x):\n        return ()\n    return ({tok!r},) + normalize_tokens(x)\n'
            ),
        }
        pub = [(('a', 'b', 'c', 'd'), (tok, 'b', 'c', 'a')), (('p', 'q', 'r'), (tok, 'q', 'p'))]
        priv = [(('u', 'v', 'w', 'x'), (tok, 'v', 'w', 'u')), (('m', 'n', 'o'), (tok, 'n', 'm'))]
        patch_res = w19.MultiFileRepoPatcher.localize_and_patch(repo, 'pkg/pipeline.py', 'run_pipeline', pub)
        priv_ok = patch_res['patched'] and all(
            w19.MultiFileRepoPatcher.execute_repo_call(patch_res['patched_repo'], 'pkg/pipeline.py', 'run_pipeline', x) == y
            for x, y in priv
        )
        repo_cases.append(dict(
            seed=seed,
            patched=patch_res['patched'],
            localized_file=patch_res['localized_file'],
            localized_function=patch_res['localized_function'],
            private_correct=int(priv_ok),
            synthesis_evals=patch_res['synthesis_evals'],
            primitive_op_steps=patch_res['primitive_op_steps'],
            unified_diff=patch_res['unified_diff'],
        ))

    totals = {
        m: {
            k: sum(int(r[k]) for r in rows if r['method'] == m)
            for k in (
                'private_correct', 'total_work', 'total_primitive_op_steps',
                'helper_function_invented', 'helper_function_reused',
                'cold_archive_reactivated', 'ambiguous_correctly_declared',
            )
        }
        for m in w19.WAVE19_METHODS
    }
    full = totals['nexus_m4_python_ast_full']
    whole = totals['nexus_whole_function_only']
    no_prune = totals['nexus_ast_without_pruning']
    gates = dict(
        passed=(
            len(rows) == 324
            and full['private_correct'] == 54
            and full['ambiguous_correctly_declared'] == 3
            and full['cold_archive_reactivated'] >= 3
            and full['helper_function_invented'] >= 3
            and full['helper_function_reused'] >= 9
            and full['total_work'] < whole['total_work']
            and full['total_primitive_op_steps'] < whole['total_primitive_op_steps']
            and full['total_work'] < no_prune['total_work']
            and full['total_primitive_op_steps'] < no_prune['total_primitive_op_steps']
            and all(c['private_correct'] == 1 for c in repo_cases)
        ),
        repo_patches_solved=sum(c['private_correct'] for c in repo_cases),
        repo_patches_total=len(repo_cases),
    )
    payload = dict(
        kind='seed_wave19_python_ast_coding',
        cells=len(rows),
        totals=totals,
        repo_patching=repo_cases,
        gates=gates,
    )
    out_path = ROOT / 'artifacts/seed_wave19_python_ast_coding.json'
    out_path.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def run_wave20_benchmark():
    dialogues = []
    for seed in (0, 1, 2):
        agent = w20.Wave20GroundedConversationAgent(seed=seed)
        turns = []
        r1 = agent.handle_user_turn(
            "Write code for python function: ['a', 'kora', 'b', 'c'] -> ['zelin', 'b', 'a'], "
            "['b', 'c', 'kora'] -> ['b', 'c', 'kora'], "
            "['d', 'e', 'kora', 'f', 'g', 'h'] -> ['zelin', 'e', 'f', 'g', 'd'] "
            "and apply to ['p', 'kora', 'q', 'r']"
        )
        turns.append(('seq_code_1', r1, r1.status == 'verified_answer' and r1.verified_output == ('zelin', 'q', 'p')))

        r2 = agent.handle_user_turn(
            "Write code for python function: ['a', 'kora', 'b', 'c'] -> ['b', 'a', 'mavu'], "
            "['b', 'c', 'kora'] -> ['b', 'c', 'kora'], "
            "['d', 'e', 'kora', 'f', 'g', 'h'] -> ['e', 'f', 'g', 'd', 'mavu'] "
            "and apply to ['p', 'kora', 'q', 'r']"
        )
        turns.append(('seq_code_2_mdl_helper', r2, r2.status == 'verified_answer' and r2.verified_output == ('q', 'p', 'mavu')))

        r3 = agent.handle_user_turn(
            "In cross-domain state controller with mode=armed retries=1 commit=verified_tok "
            "and helper transformation, evaluate on ['x1', 'kora', 'x2', 'x3']"
        )
        turns.append(('cross_domain_state_helper', r3, r3.status == 'verified_answer' and r3.cross_domain_reused and r3.verified_output == ('verified_tok', 'x2', 'x1')))

        r4 = agent.handle_user_turn(
            "In state controller with mode=armed retries=5 commit=verified_tok, evaluate on ['x1', 'x2']"
        )
        turns.append(('state_precondition_block', r4, r4.status == 'verified_answer' and r4.verified_output == ('STATE_BLOCKED', ('x1', 'x2'))))

        r5 = agent.handle_user_turn(
            "Given ['a', 'b', 'c'] -> ['a', 'b', 'c', 'luma'] and ['a', 'b', 'c', 'd'] -> ['a', 'b', 'c', 'd'], "
            "what is ['u', 'v', 'w', 'z', 'q']?"
        )
        turns.append(('epistemic_clarification_ask', r5, r5.status == 'clarification_requested' and r5.distinguishing_probe == ('u', 'v', 'w', 'z', 'q')))

        r6 = agent.handle_user_turn("Clarification: ['u', 'v', 'w', 'z', 'q'] -> ['u', 'v', 'w', 'z', 'q', 'luma']")
        turns.append(('epistemic_clarification_resolve', r6, r6.status == 'verified_answer' and r6.verified_output == ('u', 'v', 'w', 'z', 'q', 'luma')))

        repo = {
            'pkg/normalizer.py': 'def normalize_tokens(x):\n    return tuple(x)[::-1]\n',
            'pkg/pipeline.py': 'from pkg.normalizer import normalize_tokens\ndef run_pipeline(x):\n    return (\'patched\',) + normalize_tokens(x)\n',
        }
        r7 = agent.handle_user_turn(
            "Please localize and patch the repository bug so ['a', 'b', 'c', 'd'] -> ['patched', 'b', 'c', 'a'] "
            "and ['p', 'q', 'r'] -> ['patched', 'q', 'p'], and evaluate on ['m', 'n', 'o', 'p']",
            context={'repo_files': repo, 'repo_entry': ('pkg/pipeline.py', 'run_pipeline')},
        )
        turns.append(('nl_repo_patch', r7, r7.status == 'verified_answer' and r7.verified_output == ('patched', 'n', 'o', 'm')))

        r8 = agent.handle_user_turn("What is the current stock price of Acme Corp and the weather in Tokyo?")
        turns.append(('oog_abstention', r8, r8.status == 'abstain' and r8.hallucinated_claims == 0))

        for name, rec, ok in turns:
            dialogues.append(dict(
                seed=seed,
                turn_id=name,
                status=rec.status,
                domain=rec.domain,
                correct=int(ok),
                cross_domain_reused=int(rec.cross_domain_reused),
                verified_claims=rec.verified_claims,
                hallucinated_claims=rec.hallucinated_claims,
                total_work=rec.total_work,
                total_primitive_op_steps=rec.total_primitive_op_steps,
                english_response=rec.english_response,
            ))

    payload = dict(
        kind='seed_wave20_grounded_nl_conversation',
        total_turns=len(dialogues),
        turns_correct=sum(d['correct'] for d in dialogues),
        total_hallucinations=sum(d['hallucinated_claims'] for d in dialogues),
        cross_domain_transfers=sum(d['cross_domain_reused'] for d in dialogues),
        clarifications_asked=sum(d['status'] == 'clarification_requested' for d in dialogues),
        oog_abstentions=sum(d['status'] == 'abstain' for d in dialogues),
        gates=dict(
            passed=(
                len(dialogues) == 24
                and sum(d['correct'] for d in dialogues) == 24
                and sum(d['hallucinated_claims'] for d in dialogues) == 0
                and sum(d['cross_domain_reused'] for d in dialogues) >= 3
            )
        ),
        dialogues=dialogues,
    )
    out_path = ROOT / 'artifacts/seed_wave20_grounded_nl_conversation.json'
    out_path.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def main():
    p19 = run_wave19_benchmark()
    p20 = run_wave20_benchmark()
    summary = dict(
        valid=bool(p19['gates']['passed'] and p20['gates']['passed']),
        wave19_gates=p19['gates'],
        wave19_totals=p19['totals'],
        wave20_gates=p20['gates'],
        wave20_turns_correct=p20['turns_correct'],
        wave20_total_turns=p20['total_turns'],
        wave20_hallucinations=p20['total_hallucinations'],
        wave19_sha256=hashlib.sha256((ROOT / 'artifacts/seed_wave19_python_ast_coding.json').read_bytes()).hexdigest(),
        wave20_sha256=hashlib.sha256((ROOT / 'artifacts/seed_wave20_grounded_nl_conversation.json').read_bytes()).hexdigest(),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
