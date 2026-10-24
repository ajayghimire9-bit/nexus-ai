"""Source-only checks. No closed or fresh assessment definitions are imported.

The MPS and complete source gate require a separately approved GPU allocation.
They are deliberately not skipped or relabeled as passed when not executed.
"""
import ast
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path

import pytest

from nexus.seed import wave17_exact_cache_boundary_learner as old
from nexus.seed import wave18_m4_gpu_neuro_symbolic_learner as new

ROOT = Path(__file__).resolve().parents[1]
X = old.VarNode()
TOKEN = old.TypeTag.TOK
SEQ = old.TypeTag.SEQ


def unary(op, child=X):
    return old.PrimOpNode(op, (child,), SEQ)


def prepend(c, child):
    return old.PrimOpNode('PREPEND_TOK', (old.ConstNode(c, TOKEN), child), SEQ)


def append(child, c):
    return old.PrimOpNode('APPEND_TOK', (child, old.ConstNode(c, TOKEN)), SEQ)


def source_pairs(node):
    xs = list(old.CANONICAL_BOUNDARY_INPUTS)+[('',), ('a',''), ('','b'), ('a','b','a','c','b')]
    return [(x, old.eval_expr_ast(node, x)) for x in xs]


def test_historical_files_and_local_dependency_injection():
    p = ROOT/'src/nexus/seed/local_model_runtime.py'
    assert hashlib.sha256(p.read_bytes()).hexdigest() == '5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781'
    tree = ast.parse((ROOT/'src/nexus/seed/wave18_m4_gpu_neuro_symbolic_learner.py').read_text())
    assert not any(isinstance(n, ast.Lambda) for n in ast.walk(tree))
    solve = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name=='solve_unfamiliar_task')
    assert [a.arg for a in solve.args.args] == ['self','env','public_budget']
    before = old.TypedEqualCapabilityLearner.solve_unfamiliar_task.__globals__['ExactCache']
    bound = new._bound_solver(old.ExactCache, old.TypedProgramEnumerator)
    assert bound.__code__ is old.TypedEqualCapabilityLearner.solve_unfamiliar_task.__code__
    assert bound.__globals__ is not old.TypedEqualCapabilityLearner.solve_unfamiliar_task.__globals__
    assert old.TypedEqualCapabilityLearner.solve_unfamiliar_task.__globals__['ExactCache'] is before


def test_affix_outward_rewrite_exposes_exact_size_five_core():
    core = old.PrimOpNode('APPEND_TOK', (unary('TAIL'),
        old.PrimOpNode('HEAD', (X,), TOKEN)), SEQ)
    inward = old.PrimOpNode('APPEND_TOK', (prepend('public_marker',unary('TAIL')),
        old.PrimOpNode('HEAD',(X,),TOKEN)), SEQ)
    receipt={'evals':0};counter=old.OpCounter()
    result=new.canonicalize_expr_ast(inward, source_pairs(inward),counter,receipt=receipt)
    assert old.ast_key(result)==old.ast_key(prepend('public_marker',core))
    assert core.ast_nodes()==5 and new.is_dynamic_const_free(core)
    assert receipt['evals']>0 and counter.steps>0


def test_four_structural_families_preserve_empty_and_nonempty_semantics():
    # Native SWAP_ENDS is size2, not an artificially padded size5 expression.
    families = [unary('ROT_LEFT'),unary('ROT_RIGHT'),unary('SWAP_ENDS'),
        unary('REVERSE',old.PrimOpNode('APPEND_TOK',(
            unary('TAIL'),old.PrimOpNode('HEAD',(X,),TOKEN)),SEQ))]
    count=0
    for core,c,d in itertools.product(families, ('','a','new_marker'),('','b','discard')):
        trees=[old.PrimOpNode('APPEND_TOK',(prepend(c,core),old.PrimOpNode('HEAD',(X,),TOKEN)),SEQ),
               old.PrimOpNode('PREPEND_TOK',(old.PrimOpNode('LAST',(X,),TOKEN),append(core,c)),SEQ),
               old.FilterSeqNode(prepend(c,core),old.ConstNode(d,TOKEN))]
        for tree in trees:
            pairs=source_pairs(tree);counter=old.OpCounter();receipt={'evals':0}
            canonical=new.canonicalize_expr_ast(tree,pairs,counter,receipt=receipt)
            again=new.canonicalize_expr_ast(canonical,pairs,counter,receipt=receipt)
            assert old.ast_key(again)==old.ast_key(canonical)
            for x,y in pairs:
                assert old.eval_expr_ast(canonical,x)==y
                count+=1
    assert count>=500


def test_filter_must_not_float_a_deleted_prefix():
    tree=old.FilterSeqNode(prepend('same',X),old.ConstNode('same',TOKEN))
    canonical=new.canonicalize_expr_ast(tree,source_pairs(tree))
    assert old.ast_key(canonical)==old.ast_key(tree)
    assert old.eval_expr_ast(canonical,())==()


def test_observed_support_is_not_replaced_by_a_boundary_signature():
    node=prepend('marker',unary('TAIL'))
    pairs=[(('different','observed'),('deliberately','inconsistent'))]
    canonical=new.canonicalize_expr_ast(node,pairs)
    assert old.ast_key(canonical)==old.ast_key(node)
    assert old.eval_expr_ast(node,pairs[0][0])!=pairs[0][1]


def test_constant_free_core_table_is_metered_and_bounded():
    core=old.PrimOpNode('APPEND_TOK',(unary('TAIL'),old.PrimOpNode('HEAD',(X,),TOKEN)),SEQ)
    pairs=source_pairs(core);counter=old.OpCounter()
    table,cache,evals=new.constant_free_core_table(pairs,counter)
    assert evals>0 and counter.steps>0 and table
    assert all(4<=n.ast_nodes()<=5 and new.is_dynamic_const_free(n) for n in table.values())
    assert cache.signature(core) in table


def test_non_neural_solver_uses_same_frozen_program_and_costs():
    from scripts.run_wave17_exact_cache_assessment import PublicWorld
    node=unary('REVERSE')
    xs=[('a','b','c','d'),('b','c','d'),('x','y'),('b','c','d','e','f'),
        ('a','b','b','a'),('d','e','f'),('x','y','z','q'),('t','u','v')]
    part={'public':[(x,x[::-1] if len(x)%2==0 else x) for x in xs], 'confirm_count':2}
    old_learner=old.TypedEqualCapabilityLearner('equal_typed_scratch')
    world_a=PublicWorld(part);old_report=old_learner.solve_unfamiliar_task(world_a,24)
    world_b=PublicWorld(part);new_report=new.Wave18Learner('equal_typed_scratch').solve_unfamiliar_task(world_b,24)
    assert old_report.program_ast==new_report['program_ast']
    assert old_report.total_work==new_report['total_work']
    assert old_report.total_primitive_op_steps==new_report['total_primitive_op_steps']
    assert world_a.reads==world_b.reads and new_report['neural_proposer_work']==0
    assert new_report['gpu']['gpu_forward_passes']==0


def test_saved_verifier_rejects_missing_planned_seeds_and_methods():
    from scripts.verify_wave18_m4_neuro_symbolic import verify_payload
    from nexus.seed.capability_evidence import digest
    manifest=[dict(id='source_validation_'+str(i),split='source',gold='unique') for i in range(18)]
    fields=('mapping_correct','private_correct','false_unique','cold_archive_reactivated',
            'ambiguous_correctly_declared','total_work','total_primitive_op_steps','n')
    payload=dict(kind='source_only_missing_grid_test',complete=True,methods=list(new.METHODS),
        seeds=[0,1],assessment=[],task_manifest=manifest,
        totals={'suite':{m:{k:0 for k in fields} for m in new.METHODS},
                'source':{m:{k:0 for k in fields} for m in new.METHODS}},gates={'passed':False})
    payload['hash']=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    checked=verify_payload(payload,manifest)
    assert not checked['valid'] and 'incomplete_grid' in checked['errors']
    assert 'locked_axes' in checked['errors']


def test_policy_has_no_private_or_task_label_update_arguments():
    import inspect
    parameters=inspect.signature(new.M4NeuroSymbolicProposer.update_proposer_on_mps).parameters
    assert list(parameters)==['self','program','schema_tags']
    assert new.WORK_KEYS==old.WORK_KEYS+('neural_proposer_work',)
    assert new.PRIMITIVE_KEYS==old.PRIMITIVE_KEYS


def test_canonical_library_constructor_uses_declared_owner_fields_only():
    owner=new.Wave18Learner.__new__(new.Wave18Learner)
    owner.public_method='nexus_m4_neuro_symbolic_full';owner.method='nexus_typed_full'
    owner.proposer=object()  # Only a branch flag; no fake neural result is scored.
    library=owner.make_library()
    assert isinstance(library,new.CanonicalMacroLibrary)
    assert library.relational_schemas=={} and library.mdl_events==set()


def test_mps_encoder_and_actual_dynamic_head_optimizer_continuity():
    torch,device=new.require_mps()
    proposer=new.M4NeuroSymbolicProposer(11)
    pairs=source_pairs(prepend('marker',unary('TAIL')))
    proposer.encode_and_rank(pairs)
    assert proposer.last_features.shape==(1,24) and proposer.last_features.device.type=='mps'
    assert all(p.device.type=='mps' for p in proposer.network.parameters())
    program=old.PiecewiseProgramAST((old.PiecewiseBranch(old.ConstNode(True,old.TypeTag.BOOL),
        prepend('marker',unary('TAIL'))),),X)
    proposer.update_proposer_on_mps(program)
    head=proposer.network[-1]
    weights=head.weight.detach().cpu().clone()
    moments=proposer.optimizer.state[head.weight]['exp_avg'].detach().cpu().clone()
    step=proposer.optimizer.state[head.weight]['step'].clone()
    assert proposer.expand_macro('source_l1') and proposer.expand_macro('source_l2')
    assert not proposer.expand_macro('source_l1')
    assert proposer.macro_head_output_dimension==2
    new_head=proposer.network[-1]
    assert torch.equal(weights,new_head.weight[:-2].detach().cpu())
    assert torch.equal(moments,proposer.optimizer.state[new_head.weight]['exp_avg'][:-2].detach().cpu())
    assert torch.equal(step,proposer.optimizer.state[new_head.weight]['step'])
    assert proposer.telemetry.gpu_online_update_steps==3
    assert proposer.telemetry.gpu_forward_passes==4
    print('W18_GPU_TELEMETRY',json.dumps(proposer.telemetry.snapshot(),sort_keys=True))


def test_mps_updates_are_public_ast_feedback_not_private_accuracy():
    torch,_=new.require_mps();proposer=new.M4NeuroSymbolicProposer(31)
    pairs=source_pairs(prepend('source_only',X));proposer.encode_and_rank(pairs)
    frozen={k:v.detach().cpu().clone() for k,v in proposer.network.state_dict().items()}
    program=old.PiecewiseProgramAST((old.PiecewiseBranch(old.ConstNode(True,old.TypeTag.BOOL),
        prepend('source_only',X)),),X)
    proposer.update_proposer_on_mps(program)
    assert any(not torch.equal(frozen[k],v.detach().cpu()) for k,v in proposer.network.state_dict().items())
    assert all(r['feedback']=='public_verified_ast_only' for r in proposer.training_receipts)
    assert len(proposer.training_receipts[-1]['losses'])==3
    # There is no API argument for target/private accuracy, labels or task IDs.
    import inspect
    assert list(inspect.signature(proposer.update_proposer_on_mps).parameters)==['program','schema_tags']
    print('W18_GPU_TELEMETRY',json.dumps(proposer.telemetry.snapshot(),sort_keys=True))


def test_mps_identical_seed_replays_with_explicit_tolerance():
    torch,_=new.require_mps();pairs=source_pairs(append(unary('REVERSE'),'source_marker'))
    a=new.M4NeuroSymbolicProposer(91);b=new.M4NeuroSymbolicProposer(91)
    pa=a.encode_and_rank(pairs);pb=b.encode_and_rank(pairs)
    assert max(abs(pa[k]-pb[k]) for k in pa)<1e-6
    print('W18_GPU_TELEMETRY',json.dumps(a.telemetry.snapshot(),sort_keys=True))
    print('W18_GPU_TELEMETRY',json.dumps(b.telemetry.snapshot(),sort_keys=True))


def test_complete_source_gate_mps(tmp_path):
    """Measured gate, not a forced result. Failure blocks the physical freeze."""
    from test_seed_wave17_boundary_and_cache_invariance import source_specs
    from scripts.run_wave17_exact_cache_assessment import PublicWorld
    specs=source_specs();rows=[]
    path=Path(os.environ.get('NEXUS_WAVE18_SOURCE_ROWS',str(tmp_path/'wave18_source_rows.jsonl')))
    stream=path.open('x')
    for seed in (0,1,2):
        for method in new.METHODS:
            learner=new.Wave18Learner(method,seed)
            for spec in specs:
                part=spec['seeds'][seed];world=PublicWorld(part)
                row=learner.solve_unfamiliar_task(world,24);world.lock()
                correct=row['status']==spec['gold']
                if row['status']=='unique':
                    correct=correct and all(old.eval_program(row['program_ast'],x)==old.canonical_input(y) for x,y in part['private'])
                row.update(source_seed=seed,task_id=spec['id'],gold=spec['gold'],private_correct=correct)
                rows.append(row)
                stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
    stream.close()
    (tmp_path/'wave18_source_gate.json').write_text(json.dumps(rows))
    assert len(rows)==324
    totals={m:{k:sum(int(r[k]) for r in rows if r['method']==m) for k in
        ('private_correct','total_work','total_primitive_op_steps')} for m in new.METHODS}
    full=totals[new.METHODS[-1]];whole=totals['nexus_whole_macro_only']
    print('W18_SOURCE_GATE_TOTALS',json.dumps(totals,sort_keys=True))
    assert full['private_correct']==54
    for metric in ('total_work','total_primitive_op_steps'):
        assert full[metric]<=.8*whole[metric],(metric,totals)
        for method in new.METHODS[:-1]:
            if totals[method]['private_correct']==54:
                assert full[metric]<totals[method][metric],(metric,totals)
    # Neural-only performance is reported; it is never manipulated to ensure
    # failure. If it ties or wins, preserve that contrary evidence.
