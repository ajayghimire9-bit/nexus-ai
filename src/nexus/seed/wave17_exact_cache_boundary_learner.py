"""Bounded typed synthesis using one interpreter, exact whole-expression caches.

Reuses Wave14's immutable AST, macro/MDL ownership and report contracts. Historical
interpreters, experiments, models and ledgers are never modified or patched.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter

from . import wave14_piecewise_archive_learner as legacy
from .wave14_piecewise_archive_learner import (
    VarNode, ConstNode, EvolvedMacroNode, PiecewiseBranch,
    PiecewiseProgramAST, TypeTag, OpCounter, WORK_KEYS, PRIMITIVE_KEYS,
    WAVE14_METHODS, MIN_BRANCH_SUPPORT, report_to_row)

CANONICAL_BOUNDARY_INPUTS=((),('a',),('a','b'),('a','a'),('a','b','c'),('a','b','c','d'))
INTEGER_BOUNDARY_INPUTS=(-4,-3,-2,-1,0,1,2,3,4)
UNARY=('DROP_LAST','INIT','REVERSE','ROT_LEFT','ROT_RIGHT','SWAP_ENDS','TAIL')
PUBLIC_BUDGET=24
EXTENDED_OPS=('FILTER_NEQ','MAP_REPLACE','DEDUP_ADJ','TOK_IN_SEQ','INT_ADD','INT_SUB',
    'INT_MUL','INT_NEG','INT_ABS','BOOL_NOT','ROT_LEFT','ROT_RIGHT','SWAP_ENDS')


class PrimOpNode(legacy.PrimOpNode):
    def __post_init__(self):
        if self.op_name not in legacy.ALLOWED_PRIM_OPCODES+EXTENDED_OPS:
            raise ValueError('disallowed_primitive:'+self.op_name)


def expr_ast_from_dict(raw):
    kind=raw['node_kind'];out=TypeTag(raw['out_type'])
    if kind=='VarNode':return VarNode(out)
    if kind=='ConstNode':return ConstNode(tuple(raw['value']) if out==TypeTag.SEQ else raw['value'],out)
    if kind=='PrimOpNode':return PrimOpNode(raw['op_name'],tuple(expr_ast_from_dict(a) for a in raw['args']),out)
    if kind=='EvolvedMacroNode':
        return EvolvedMacroNode(raw['macro_id'],expr_ast_from_dict(raw['body_ast']),
            tuple(expr_ast_from_dict(a) for a in raw['args']),out,raw.get('layer',1))
    raise ValueError('invalid_node_kind')


def piecewise_from_dict(raw):
    return PiecewiseProgramAST(tuple(PiecewiseBranch(expr_ast_from_dict(b['guard']),
        expr_ast_from_dict(b['transform'])) for b in raw['branches']),expr_ast_from_dict(raw['default']))


@dataclass(frozen=True)
class StateRecord:
    slots: tuple

    def tokens(self):
        return tuple(str(k)+'='+str(v) for k,v in sorted(self.slots))


def canonical_input(value):
    if isinstance(value,StateRecord):return value.tokens()
    if isinstance(value,dict):return StateRecord(tuple(value.items())).tokens()
    if type(value) in (int,bool):return value
    if isinstance(value,(tuple,list)):return tuple(str(v) for v in value)
    raise TypeError('unsupported_runtime_input')


class FilterSeqNode(PrimOpNode):
    def __init__(self,seq_expr,keep_neq_tok,val_type=TypeTag.SEQ):
        super().__init__('FILTER_NEQ',(seq_expr,keep_neq_tok),val_type)


class MapReplaceTokNode(PrimOpNode):
    def __init__(self,seq_expr,target_tok,replacement_tok,val_type=TypeTag.SEQ):
        super().__init__('MAP_REPLACE',(seq_expr,target_tok,replacement_tok),val_type)


class DedupAdjSeqNode(PrimOpNode):
    def __init__(self,seq_expr,val_type=TypeTag.SEQ):
        super().__init__('DEDUP_ADJ',(seq_expr,),val_type)


class HasTokNode(PrimOpNode):
    def __init__(self,token,seq_expr):
        super().__init__('TOK_IN_SEQ',(token,seq_expr),TypeTag.BOOL)


def eval_expr_ast(node,x,op_counter=None):
    """Single semantic authority; canonicalize input exactly once per root call."""
    return _eval_expr_ast(node,canonical_input(x),op_counter)


def _eval_expr_ast(node,x,op_counter):
    if isinstance(node,VarNode):return x
    if isinstance(node,ConstNode):
        if node.out_type==TypeTag.SEQ:return tuple(node.value)
        if node.out_type==TypeTag.INT:return int(node.value)
        if node.out_type==TypeTag.BOOL:return bool(node.value)
        return str(node.value)
    if isinstance(node,EvolvedMacroNode):
        bound=_eval_expr_ast(node.args[0],x,op_counter) if len(node.args)==1 else x
        return _eval_expr_ast(node.body_ast,bound,op_counter)
    if not isinstance(node,legacy.PrimOpNode):raise TypeError('non_typed_ast')
    op=node.op_name
    if op=='IF_THEN_ELSE':
        if op_counter is not None:op_counter.steps+=1
        cond=_eval_expr_ast(node.args[0],x,op_counter)
        return _eval_expr_ast(node.args[1] if cond else node.args[2],x,op_counter)
    values=tuple(_eval_expr_ast(a,x,op_counter) for a in node.args)
    if op in ('FILTER_NEQ','MAP_REPLACE','DEDUP_ADJ','TOK_IN_SEQ'):
        seq=values[1] if op=='TOK_IN_SEQ' else values[0]
        result=[];last=None;seen=False
        for token in seq:
            if op_counter is not None:op_counter.steps+=1
            if op=='TOK_IN_SEQ':
                if token==values[0]:return True
            elif op=='FILTER_NEQ':
                if token!=values[1]:result.append(token)
            elif op=='MAP_REPLACE':result.append(values[2] if token==values[1] else token)
            elif not seen or token!=last:result.append(token)
            last=token;seen=True
        return False if op=='TOK_IN_SEQ' else tuple(result)
    if op in ('INT_ADD','INT_SUB','INT_MUL','INT_NEG','INT_ABS','BOOL_NOT','ROT_LEFT','ROT_RIGHT','SWAP_ENDS'):
        if op_counter is not None:op_counter.steps+=1
        if op=='INT_ADD':return values[0]+values[1]
        if op=='INT_SUB':return values[0]-values[1]
        if op=='INT_MUL':return values[0]*values[1]
        if op=='INT_NEG':return -values[0]
        if op=='INT_ABS':return abs(values[0])
        if op=='BOOL_NOT':return not values[0]
        seq=values[0]
        if op=='ROT_LEFT':return seq[1:]+seq[:1]
        if op=='ROT_RIGHT':return seq[-1:]+seq[:-1]
        return seq[-1:]+seq[1:-1]+seq[:1] if len(seq)>1 else seq
    return eval_prim_op(op,values,op_counter)


def eval_prim_op(op,values,counter):
    """Wave14 primitive semantics, without allocating temporary constant ASTs.

    Differential source tests compare outputs AND executed op counts against
    the unmodified historical interpreter, including the empty-token sentinel.
    """
    if counter is not None:counter.steps+=1
    a=values[0]
    if op=='HEAD':return a[0] if a else ''
    if op=='LAST':return a[-1] if a else ''
    if op=='TAIL':return a[1:]
    if op in ('INIT','DROP_LAST'):return a[:-1]
    if op=='REVERSE':return a[::-1]
    if op=='CONCAT':return a+values[1]
    if op=='APPEND_TOK':return a+(str(values[1]),) if str(values[1])!='' else a
    if op=='PREPEND_TOK':return (str(a),)+values[1] if str(a)!='' else values[1]
    if op=='LEN':return len(a)
    if op=='MOD2':return int(a)%2
    if op=='TOK_EQ':return bool(str(a)!='' and str(values[1])!='' and str(a)==str(values[1]))
    if op=='SEQ_EQ':return a==values[1]
    if op=='INT_EQ':return int(a)==int(values[1])
    if op=='INT_GE':return int(a)>=int(values[1])
    raise ValueError('unhandled_primitive:'+op)


def eval_program(program,x,counter=None):
    if isinstance(program,dict):program=piecewise_from_dict(program)
    for branch in program.branches:
        if eval_expr_ast(branch.guard,x,counter):return eval_expr_ast(branch.transform,x,counter)
    return eval_expr_ast(program.default,x,counter)


def ast_key(node):
    # Serialized args are included, unlike the historical macro canonical_key.
    if isinstance(node,EvolvedMacroNode):return ('macro',node.macro_id,ast_key(node.body_ast),tuple(ast_key(a) for a in node.args))
    if isinstance(node,legacy.PrimOpNode):return ('DROP_LAST' if node.op_name=='INIT' else node.op_name,
        node.out_type.value,tuple(ast_key(a) for a in node.args))
    if isinstance(node,VarNode):return ('x',node.out_type.value)
    return ('const',node.out_type.value,repr(node.value))


def search_nodes(node):
    """Macro-call syntax cost, distinct from expanded executed primitive work."""
    if isinstance(node,EvolvedMacroNode):return 1
    if isinstance(node,legacy.PrimOpNode):return 1+sum(search_nodes(a) for a in node.args)
    return 1


def order(node):return (search_nodes(node),repr(ast_key(node)))


def walk(node):
    yield node
    if isinstance(node,EvolvedMacroNode):
        yield from walk(node.body_ast)
        for a in node.args:yield from walk(a)
    elif isinstance(node,legacy.PrimOpNode):
        for a in node.args:yield from walk(a)


class ExactCache:
    def __init__(self,pairs,counters):
        self.pairs=list(pairs);self.counters=counters;self.memo={};self.partial={}
        self.cold_ids=set();self.audit_evals=0;self.errors=0;self.mask_checks=0
        self.partial_version=len(pairs)
        self.kind=TypeTag.INT if type(pairs[0][0]) is int else TypeTag.BOOL if type(pairs[0][0]) is bool else TypeTag.SEQ
        self.boundaries=INTEGER_BOUNDARY_INPUTS if self.kind==TypeTag.INT else (False,True) if self.kind==TypeTag.BOOL else CANONICAL_BOUNDARY_INPUTS

    def category(self,node):
        return 'archive' if any(isinstance(n,EvolvedMacroNode) and n.macro_id in self.cold_ids for n in walk(node)) else 'synth'

    def predict(self,node,x,category=None):
        category=category or self.category(node);x=canonical_input(x)
        key=(ast_key(node),type(x).__name__,x)
        if key not in self.memo:
            self.memo[key]=eval_expr_ast(node,x,self.counters[category+'_ops'])
            self.counters[category+'_evals']+=1
        return self.memo[key]

    def signature(self,node):
        return (node.out_type.value,tuple(self.predict(node,x) for x in self.boundaries),
                tuple(self.predict(node,x) for x,y in self.pairs))

    def transform(self,node):
        outputs=tuple(self.predict(node,x) for x,y in self.pairs)
        strict={i for i,(x,y) in enumerate(self.pairs) if x!=y}
        coverage=frozenset(i for i in strict if outputs[i]==self.pairs[i][1])
        if coverage:
            signature=self.signature(node)
            if signature not in self.partial or order(node)<order(self.partial[signature][0]):
                category=self.category(node)
                for i in strict:
                    # Intentionally independent, noncached interpreter execution.
                    actual=eval_expr_ast(node,self.pairs[i][0],self.counters[category+'_ops'])
                    self.counters[category+'_evals']+=1;self.audit_evals+=1
                    if (i in coverage)!=(actual==self.pairs[i][1]):self.errors+=1
                    assert (i in coverage)==(actual==self.pairs[i][1]),'cached_coverage_corruption'
                self.partial[signature]=(node,coverage)
        return outputs,coverage

    def deduplicate(self,nodes):
        # Exact syntax duplicates need no execution. Boundary collisions still
        # require every task input; boundary-only equivalence is never enough.
        seen=set();syntax=set();result=[]
        for node in sorted(nodes,key=order):
            key=ast_key(node)
            if key in syntax:continue
            syntax.add(key)
            signature=self.signature(node)
            if signature not in seen:seen.add(signature);result.append(node)
        return result

    def refresh_partial(self):
        # Public clarification changes the observation set. Never carry a mask
        # with indices/strictness from an earlier observation version forward.
        if self.partial_version==len(self.pairs):return
        self.partial_version=len(self.pairs)
        nodes=[node for node,_ in self.partial.values()]
        self.partial={}
        for node in nodes:self.transform(node)


def extract_constants(pairs):
    if type(pairs[0][0]) is bool:return (), (0,1)
    if type(pairs[0][0]) is int:
        return (),tuple(sorted({0,1,2}|{abs(y-x) for x,y in pairs if type(y) is int and abs(y-x)<=8}))
    tokens=[]
    for x,y in pairs:
        for token in y:
            if token not in x and token not in tokens:tokens.append(token)
        removed=Counter(x)-Counter(y)
        for token in removed:
            if token not in tokens:tokens.append(token)
    old=legacy.extract_task_constants([dict(input=list(x),observed_output=list(y)) for x,y in pairs])
    return tuple(tokens),tuple(sorted(set(old.ints)|(set((0,1,2)))))


class TypedProgramEnumerator:
    def __init__(self,kind,tokens,ints,cache):
        self.kind=kind;self.tokens=tokens;self.ints=ints;self.cache=cache
        self.x=VarNode(kind)
        self.filter_tokens=set();self.replace_pairs=set()
        if kind==TypeTag.SEQ:
            for x,y in cache.pairs:
                if x==y:continue
                removed=set(x)-set(y);added=(set(y)-set(x))&set(tokens)
                if len(y)<len(x):self.filter_tokens.update(removed)
                self.replace_pairs.update((a,b) for a in removed for b in added)

    def loop_free(self,node):
        return not any(isinstance(n,PrimOpNode) and n.op_name in ('FILTER_NEQ','MAP_REPLACE') for n in walk(node))

    def guards(self):
        x=self.x
        scalar=x if self.kind==TypeTag.INT else PrimOpNode('LEN',(x,),TypeTag.INT)
        result=[ConstNode(True,TypeTag.BOOL)]
        if self.kind==TypeTag.BOOL:return [x,PrimOpNode('BOOL_NOT',(x,),TypeTag.BOOL),result[0]]
        for value in (0,1):
            result.append(PrimOpNode('INT_EQ',(PrimOpNode('MOD2',(scalar,),TypeTag.INT),ConstNode(value,TypeTag.INT)),TypeTag.BOOL))
        for value in self.ints:
            for op in ('INT_EQ','INT_GE'):
                result.append(PrimOpNode(op,(scalar,ConstNode(value,TypeTag.INT)),TypeTag.BOOL))
        if self.kind==TypeTag.SEQ:
            result.extend((PrimOpNode('SEQ_EQ',(x,PrimOpNode('REVERSE',(x,),TypeTag.SEQ)),TypeTag.BOOL),
                PrimOpNode('TOK_EQ',(PrimOpNode('HEAD',(x,),TypeTag.TOK),PrimOpNode('LAST',(x,),TypeTag.TOK)),TypeTag.BOOL)))
            result.extend(HasTokNode(ConstNode(t,TypeTag.TOK),x) for t in self.tokens)
        return self.cache.deduplicate(result)

    def base(self):
        if self.kind==TypeTag.INT:return [PrimOpNode(op,(self.x,),TypeTag.INT) for op in ('INT_NEG','INT_ABS')]
        if self.kind==TypeTag.BOOL:return [PrimOpNode('BOOL_NOT',(self.x,),TypeTag.BOOL)]
        return [PrimOpNode(op,(self.x,),TypeTag.SEQ) for op in UNARY]+[DedupAdjSeqNode(self.x)]

    def wrappers(self,node):
        if self.kind==TypeTag.INT:
            return [node]+[PrimOpNode(op,(node,ConstNode(v,TypeTag.INT)),TypeTag.INT) for v in self.ints for op in ('INT_ADD','INT_SUB','INT_MUL')]
        if self.kind==TypeTag.BOOL:return [node,PrimOpNode('BOOL_NOT',(node,),TypeTag.BOOL)]
        result=[node]+[PrimOpNode(op,(node,),TypeTag.SEQ) for op in UNARY]+[DedupAdjSeqNode(node)]
        for token in self.tokens:
            c=ConstNode(token,TypeTag.TOK)
            result.extend((PrimOpNode('APPEND_TOK',(node,c),TypeTag.SEQ),PrimOpNode('PREPEND_TOK',(c,node),TypeTag.SEQ)))
            if token in self.filter_tokens:result.append(FilterSeqNode(node,c))
        return result

    def atomic_levels(self):
        if self.kind!=TypeTag.SEQ:
            nodes=self.wrappers(self.x)
            for base in self.base():nodes.extend(self.wrappers(base))
            yield self.cache.deduplicate(nodes)
            return
        by_size={1:[self.x,ConstNode((),TypeTag.SEQ)]}
        seen={self.cache.signature(n) for n in by_size[1]}
        token_nodes=[ConstNode(t,TypeTag.TOK) for t in self.tokens]
        token_ops=[PrimOpNode('HEAD',(self.x,),TypeTag.TOK),PrimOpNode('LAST',(self.x,),TypeTag.TOK)]
        for size in range(2,8):
            candidates=[]
            for core_size,cores in list(by_size.items()):
                for core in cores:
                    if core_size+1==size:
                        candidates.extend(PrimOpNode(op,(core,),TypeTag.SEQ) for op in UNARY)
                        candidates.append(DedupAdjSeqNode(core))
                    if core_size+2==size:
                        for c in token_nodes:
                            candidates.extend((PrimOpNode('APPEND_TOK',(core,c),TypeTag.SEQ),PrimOpNode('PREPEND_TOK',(c,core),TypeTag.SEQ)))
                            if c.value in self.filter_tokens and self.loop_free(core):candidates.append(FilterSeqNode(core,c))
                    if core_size+3==size and size<=5:
                        for c in token_ops:
                            candidates.extend((PrimOpNode('APPEND_TOK',(core,c),TypeTag.SEQ),PrimOpNode('PREPEND_TOK',(c,core),TypeTag.SEQ)))
                        for a in token_nodes:
                            for b in token_nodes:
                                if (a.value,b.value) in self.replace_pairs and self.loop_free(core):
                                    candidates.append(MapReplaceTokNode(core,a,b))
            if size<=5:
                for left_size,lefts in by_size.items():
                    for a in lefts:
                        for b in by_size.get(size-left_size-1,()):candidates.append(PrimOpNode('CONCAT',(a,b),TypeTag.SEQ))
            # A large outer wrapper is only a proposal if its EXACT primitive
            # application to already-exact child outputs matches at least one
            # strict public row. This is a necessary support test, not a stored
            # coverage mask. Every surviving tree is interpreted in full below.
            if size>=6:candidates=[n for n in candidates if self.support_proposal(n)]
            by_size[size]=[]
            for node in self.cache.deduplicate(candidates):
                signature=self.cache.signature(node)
                if signature not in seen:
                    seen.add(signature);by_size[size].append(node)
            yield by_size[size]

    def support_proposal(self,node):
        category=self.cache.category(node)
        for x,y in self.cache.pairs:
            if x==y:continue
            children=tuple(ConstNode(self.cache.predict(a,x),a.out_type) for a in node.args)
            value=eval_expr_ast(PrimOpNode(node.op_name,children,node.out_type),(),self.cache.counters[category+'_ops'])
            self.cache.counters[category+'_evals']+=1
            if value==y:return True
        return False

    def atomic(self):
        return [node for level in self.atomic_levels() for node in level]


def select_max_entropy_probe(guards,probes,cache):
    best=None;score=0
    for slot,x in sorted(probes):
        positive=sum(bool(cache.predict(g,x,'probe')) for g in guards)
        balance=min(positive,len(guards)-positive)
        if balance>score:best=(slot,x);score=balance
    return best,score


class MacroLibrary(legacy.TypedMacroLibrary):
    def setup(self):
        if hasattr(self,'relational_schemas'):return
        self.relational_schemas={};self.cold_transform_index={};self.cold_guard_index={}
        self.cold_by_id={};self.variable_cold=set();self.index_profiles={}
        self.index_work=0;self.index_counter=OpCounter();self.reactivated_names=[]
        self.mdl_counts={};self.mdl_events=set();self.mdl_subtree_names=set();self.mdl_reviewed_steps=set()

    def begin_task(self):
        self.setup();self.index_work=0;self.index_counter.steps=0;self.reactivated_names=[]
        return super().begin_task()

    def promote_ast_subtree(self,subtree_ast,kind,layer=1):
        # Reuse ownership/MDL, correcting the historical SEQ-only macro ABI.
        body=subtree_ast.body_ast if isinstance(subtree_ast,EvolvedMacroNode) else subtree_ast
        if any(op.macro_node.body_ast.canonical_key()==body.canonical_key() for op in self.cold_archive.values()):
            # Promotion/compression is not a backdoor archive reactivation.
            # Only reactivate_locked may restore an explicitly referenced macro.
            return None,0
        op,cost=super().promote_ast_subtree(subtree_ast,kind,layer)
        if op is not None:
            body=op.macro_node.body_ast
            inputs=[n.out_type for n in walk(body) if isinstance(n,VarNode)]
            input_kind=inputs[0] if inputs else TypeTag.SEQ
            old=op.macro_node
            op.macro_node=EvolvedMacroNode(old.macro_id,body,(VarNode(input_kind),),body.out_type,old.layer)
        return op,cost

    def reactivate_locked(self,program):
        referenced={n.macro_id for b in program.branches for root in (b.guard,b.transform)
            for n in walk(root) if isinstance(n,EvolvedMacroNode)}
        restored=[]
        for identifier in sorted(referenced):
            name=self.cold_by_id.get(identifier)
            if name in self.cold_archive:
                legacy._reactivate(self,self.cold_archive[name]);restored.append(identifier)
        self.reactivated_names=restored
        return restored

    def compress_solved_programs_mdl(self,latest,structure_discovered,compression_counter):
        """Incremental event-triggered use of the existing structural MDL rule.

        Count distinct solved tasks, not repeated reviews of old programs.
        A newly supported internal operator receives its actual >=2-task tenure.
        """
        if not self.use_macro_evolution or not structure_discovered:return 0,()
        if self.step in self.mdl_reviewed_steps:return 0,()
        self.mdl_reviewed_steps.add(self.step)
        self.solved_program_history.append(latest)
        roots=[n for b in latest.branches for n in (b.guard,b.transform)]
        internals=[]
        if self.use_internal_subtree:
            for root in roots:internals.extend(legacy.iter_internal_subtrees(root))
        internal_keys={n.canonical_key() for n in internals}
        per_task={};evals=0
        for node in roots+internals:
            evals+=1;compression_counter.steps+=1
            if node.ast_nodes()<2:continue
            key=node.canonical_key()
            if key not in per_task:per_task[key]=[node,0]
            per_task[key][1]+=1
        invented=[]
        for key,(node,occurrences) in per_task.items():
            row=self.mdl_counts.setdefault(key,dict(node=node,tasks=0,occurrences=0,internal_tasks=0))
            row['tasks']+=1;row['occurrences']+=occurrences
            row['internal_tasks']+=int(key in internal_keys)
            if row['tasks']<2:continue
            internal=row['internal_tasks']>=2
            event=(key,internal)
            if event in self.mdl_events:continue
            # Same task-support arm of the inherited MDL rule; >=2 distinct
            # tasks supplies support even when the literal storage gain is zero.
            self.mdl_events.add(event)
            kind='bool_macro' if node.out_type==TypeTag.BOOL else 'int_macro' if node.out_type==TypeTag.INT else 'seq_macro'
            previous=set(self.operators)
            op,_=self.promote_ast_subtree(node,kind,2 if any(isinstance(n,EvolvedMacroNode) for n in walk(node)) else 1)
            if op is not None:
                op.uses=max(op.uses,row['tasks']);self.mdl_pinned_names.add(op.name)
                if internal:
                    self.mdl_subtree_names.add(op.name);op.is_mdl_subtree=True
                if op.name not in previous:invented.append(op.name)
        return evals,tuple(invented)

    def prioritize_guards(self,guards):
        # Learned source schemas affect topology order, never the candidate set.
        preferred=set()
        if 'GUARD_PARITY_TRANSFORM' in self.relational_schemas:preferred.add('MOD2')
        if 'BOUNDARY_EQ_INVOLUTION' in self.relational_schemas:preferred.update(('TOK_EQ','SEQ_EQ'))
        if 'THRESHOLD_FILTER_COMMIT' in self.relational_schemas:preferred.update(('TOK_IN_SEQ','INT_GE'))
        def priority(node):
            matched=any(isinstance(n,PrimOpNode) and n.op_name in preferred for n in walk(node))
            return (not matched,order(node))
        return sorted(guards,key=priority)

    def usage_age_prune(self,*args,**kwargs):
        self.setup()
        for name in self.mdl_subtree_names:
            if name in self.operators:self.operators[name].uses=max(2,self.operators[name].uses)
        demoted=super().usage_age_prune(*args,**kwargs)
        for name in demoted:
            op=self.cold_archive[name];node=op.macro_node;self.cold_by_id[node.macro_id]=name
            if name not in self.index_profiles:
                inputs=INTEGER_BOUNDARY_INPUTS if any(isinstance(n,VarNode) and n.out_type==TypeTag.INT for n in walk(node)) else CANONICAL_BOUNDARY_INPUTS
                values=tuple(eval_expr_ast(node,x,self.index_counter) for x in inputs)
                self.index_work+=len(inputs);self.index_profiles[name]=(inputs,values)
            inputs,values=self.index_profiles[name]
            if node.out_type==TypeTag.BOOL:self.cold_guard_index.setdefault(tuple(values),set()).add(name)
            elif node.out_type==TypeTag.SEQ:
                nominal=eval_expr_ast(node,('a','b','c','d'),self.index_counter)
                self.index_work+=1
                self.cold_transform_index.setdefault(len(nominal)-4,set()).add(name)
                if any(isinstance(n,PrimOpNode) and n.op_name in ('FILTER_NEQ','DEDUP_ADJ','CONCAT','MAP_REPLACE') for n in walk(node)):
                    self.variable_cold.add(name)
                if sum(isinstance(n,PrimOpNode) and n.op_name in ('TAIL','DROP_LAST','INIT') for n in walk(node))>2:self.variable_cold.add(name)
            else:self.cold_transform_index.setdefault('integer',set()).add(name)
        return demoted

    def lookup(self,pairs,kind):
        self.setup();strict=[(x,y) for x,y in pairs if x!=y]
        guards=[op.macro_node for op in self.cold_archive.values() if op.kind=='bool_macro' and any(isinstance(n,VarNode) and n.out_type==kind for n in walk(op.macro_node))]
        # Hash probes retrieve buckets; public verification, not signatures,
        # determines coverage. Domain/variable-size fallback is conservative.
        names=set();lookups=0
        if kind==TypeTag.INT:
            names.update(self.cold_transform_index.get('integer',()));lookups+=1
        elif strict:
            x,y=max(strict,key=longest_pair);delta=len(y)-len(x)
            for key in (delta-1,delta,delta+1):names.update(self.cold_transform_index.get(key,()));lookups+=1
            names.update(self.variable_cold)
            if len(x)<3:names.update(self.cold_archive)
        nodes=[self.cold_archive[n].macro_node for n in sorted(names) if n in self.cold_archive and self.cold_archive[n].kind!='bool_macro']
        self.index_work+=lookups+len(guards)
        return guards,nodes

    def distill(self,program,kind):
        if not self.use_schemas:return 0
        cost=0;tags=set()
        if len(program.branches)>1:tags.add('PIECEWISE_PRIORITY_ROUTER')
        for b in program.branches:
            for n in walk(b.guard):
                cost+=1
                if isinstance(n,PrimOpNode) and n.op_name=='MOD2':tags.add('GUARD_PARITY_TRANSFORM')
                if isinstance(n,PrimOpNode) and n.op_name in ('TOK_EQ','SEQ_EQ'):tags.add('BOUNDARY_EQ_INVOLUTION')
                if isinstance(n,PrimOpNode) and n.op_name in ('TOK_IN_SEQ','INT_GE'):tags.add('THRESHOLD_FILTER_COMMIT')
        domain=kind.value if isinstance(kind,TypeTag) else kind
        for tag in tags:self.relational_schemas.setdefault(tag,set()).add(domain)
        return cost+len(tags)


def longest_pair(pair):return (len(pair[0]),pair[0],pair[1])


def new_counters():
    result={name+'_ops':OpCounter() for name in ('synth','archive','probe','gate','compression')}
    result.update({name+'_evals':0 for name in ('synth','archive','probe')})
    return result


class TypedEqualCapabilityLearner:
    """Same macro/MDL owner, new typed observation adapter; never sees task specs."""
    def __init__(self,method):
        if method not in WAVE14_METHODS:raise ValueError('unknown_method')
        self.method=method;self.library=self.make_library();self.last_diagnostics={}

    def make_library(self):
        base=legacy.TypedEqualCapabilityLearner._make_library(self.method)
        lib=MacroLibrary(**vars(base));lib.setup();return lib

    def solve_unfamiliar_task(self,env,public_budget):
        if type(public_budget) is not int or not 8<=public_budget<=PUBLIC_BUDGET:
            raise ValueError('public_budget_must_be_between_8_and_24')
        if self.method=='equal_typed_scratch':self.library=self.make_library()
        lib=self.library;lib.begin_task();c=new_counters();reads=0;observations=[]
        cold_before={op.macro_node.macro_id for op in lib.cold_archive.values()}
        slots=['alpha','beta','gamma','delta','epsilon']
        extras=list(getattr(env,'extra_public_slots',{}))
        initial=slots+[s for s in extras if not s.startswith('confirm_')][:3]
        records=[]
        for slot in initial[:public_budget]:records.append(env.public_read(slot));reads+=1
        metadata={'payload','echo','slot','stamp','tick','kind'}
        fields=set.intersection(*(set(r)-metadata for r in records))
        compatible=[]
        for field in sorted(fields):
            try:
                pairs=[(canonical_input(r['payload']),canonical_input(r[field])) for r in records]
                if all(type(x)==type(y) for x,y in pairs):compatible.append((field,pairs))
            except (TypeError,ValueError):continue
        report=legacy.empty_cost_report(self.method,'ambiguous',(reads,0,len(records)),{},[],lib)
        if len(compatible)!=1:
            report.probe_work=reads+len(records);report.total_work=report.probe_work
            self.last_diagnostics=dict(cached_coverage_mask_errors=0,piecewise_evaluations=0,piecewise_primitive_steps=0,epistemic_clarification_required=True)
            return report
        field,pairs=compatible[0];cache=ExactCache(pairs,c)
        default=VarNode(cache.kind);tokens,ints=extract_constants(pairs)
        enum=TypedProgramEnumerator(cache.kind,tokens,ints,cache)
        enum_guards=lib.prioritize_guards(enum.guards());diag=dict(cached_coverage_mask_errors=0,piecewise_evaluations=0,piecewise_primitive_steps=0,epistemic_clarification_required=False)
        remaining=[(s,canonical_input(env.extra_public_slots[s])) for s in extras if s not in initial]

        def observe(slot):
            nonlocal reads
            raw=env.public_read(slot);reads+=1
            pair=(canonical_input(raw['payload']),canonical_input(raw[field]));cache.pairs.append(pair)
            observations.append(dict(slot=slot,input=pair[0],observed_output=pair[1]))
            return pair

        def consistent(program):
            return all((cache.predict(program.branches[0].transform,x) if cache.predict(program.branches[0].guard,x) else x)==y for x,y in cache.pairs)

        def single(transforms,guards):
            for transform in cache.deduplicate(transforms):
                strict={i for i,(x,y) in enumerate(cache.pairs) if x!=y}
                outputs,coverage=cache.transform(transform)
                if coverage!=strict:continue
                base_guards=[g for g in enum_guards if isinstance(g,ConstNode) or
                    any(isinstance(n,PrimOpNode) and n.op_name=='MOD2' for n in walk(g))]
                found=[]
                for guard in lib.prioritize_guards(cache.deduplicate(guards+base_guards)):
                    program=PiecewiseProgramAST((PiecewiseBranch(guard,transform),),default)
                    cache.mask_checks+=1
                    if consistent(program):found.append(program)
                if found:
                    # Tier availability controls proposal cost. Certification
                    # still considers ALL primitive guards, so an early-tier
                    # proposal cannot hide a competing clarification hypothesis.
                    found=[]
                    for guard in lib.prioritize_guards(cache.deduplicate(guards+enum_guards)):
                        candidate=PiecewiseProgramAST((PiecewiseBranch(guard,transform),),default)
                        cache.mask_checks+=1
                        if consistent(candidate):found.append(candidate)
                while len(found)>1:
                    probe,score=select_max_entropy_probe([p.branches[0].guard for p in found],
                        [p for p in remaining if not p[0].startswith('confirm_')],cache)
                    if score==0 or reads>=public_budget:
                        diag['epistemic_clarification_required']=True
                        return None,True
                    remaining.remove(probe);observe(probe[0])
                    found=[p for p in found if consistent(p)]
                if found:
                    # Separate public confirmation, never evaluator/private rows.
                    confirm=[p for p in remaining if p[0].startswith('confirm_')][:2]
                    for probe in confirm:
                        if reads>=public_budget:break
                        remaining.remove(probe);observe(probe[0])
                    if consistent(found[0]):return found[0],False
            return None,False

        active=[op.macro_node for op in lib.operators.values() if op.kind!='bool_macro' and op.macro_node.out_type==cache.kind]
        active_g=[op.macro_node for op in lib.operators.values() if op.kind=='bool_macro' and any(isinstance(n,VarNode) and n.out_type==cache.kind for n in walk(op.macro_node))]
        gate_work=len(lib.operators)
        program=None;ambiguous=False
        if lib.use_memoization:
            for entry in lib.memoized_programs.values():
                # Memoization is an ordinary proposal, not privileged evidence.
                if len(entry.program.branches)==1:
                    branch=entry.program.branches[0]
                    if branch.transform.out_type==cache.kind:
                        program,ambiguous=single([branch.transform],[branch.guard])
                        if program or ambiguous:break
        if program is None:program,ambiguous=single(enum.base(),[])
        if program is None and not ambiguous and active:
            program,ambiguous=single([n for m in active for n in enum.wrappers(m)],active_g)
        cold_g,cold=lib.lookup(cache.pairs,cache.kind) if lib.use_cold_archive and program is None and not ambiguous else ([],[])
        cache.cold_ids.update(n.macro_id for n in cold+cold_g)
        if program is None and not ambiguous and (cold or cold_g):
            program,ambiguous=single(enum.base()+[n for m in active+cold for n in enum.wrappers(m)],active_g+cold_g)
        if program is None and not ambiguous:
            tokens,ints=extract_constants(cache.pairs)
            enum=TypedProgramEnumerator(cache.kind,tokens,ints,cache)
            enum_guards=lib.prioritize_guards(enum.guards())
            for level in enum.atomic_levels():
                program,ambiguous=single(level,active_g+cold_g+enum_guards)
                if program or ambiguous:break
        if program is None and not ambiguous:
            cache.refresh_partial()
            strict=frozenset(i for i,(x,y) in enumerate(cache.pairs) if x!=y)
            by_mask={}
            for node,mask in cache.partial.values():by_mask.setdefault(mask,[]).append(node)
            covers=[]
            for ca,aa in by_mask.items():
                for cb,bb in by_mask.items():
                    cache.mask_checks+=1
                    if len(ca)>=MIN_BRANCH_SUPPORT and len(strict-ca)>=MIN_BRANCH_SUPPORT and ca|cb==strict:covers.append((aa,bb))
            diag['aborted_before_piecewise']=not bool(covers)
            if covers:
                before=c['synth_evals']+c['archive_evals'];before_ops=c['synth_ops'].steps+c['archive_ops'].steps
                for slot,x in list(remaining):
                    if slot.startswith('confirm_'):continue
                    if reads>=public_budget:break
                    observe(slot);remaining.remove((slot,x))
                guards=cache.deduplicate(enum_guards+active_g+cold_g)
                import itertools
                candidates=(pair for aa,bb in covers for pair in itertools.product(aa,bb))
                for a,b in candidates:
                    oa,ca=cache.transform(a);ob,cb=cache.transform(b)
                    strict_full={i for i,(x,y) in enumerate(cache.pairs) if x!=y}
                    if len(ca)<2 or len(strict_full-ca)<2 or ca|cb!=strict_full:continue
                    for g1 in guards:
                        m1={i for i,(x,y) in enumerate(cache.pairs) if cache.predict(g1,x)}
                        if len(m1&strict_full)<2 or any(oa[i]!=cache.pairs[i][1] for i in m1):continue
                        residual=strict_full-m1
                        if len(residual)<2:continue
                        for g2 in guards:
                            cache.mask_checks+=1
                            m2={i for i,(x,y) in enumerate(cache.pairs) if cache.predict(g2,x)}-m1
                            if m2!=residual or any(ob[i]!=cache.pairs[i][1] for i in m2):continue
                            program=PiecewiseProgramAST((PiecewiseBranch(g1,a),PiecewiseBranch(g2,b)),default);break
                        if program:break
                    if program:break
                if program:
                    # Fresh public confirmation is not reused to fit branches.
                    confirmations=[p for p in remaining if p[0].startswith('confirm_')]
                    for slot,x in confirmations:
                        if reads>=public_budget:break
                        _x,y=observe(slot);remaining.remove((slot,x))
                        c['synth_evals']+=1
                        if eval_program(program,x,c['synth_ops'])!=y:
                            program=None;break
                diag['piecewise_evaluations']=c['synth_evals']+c['archive_evals']-before
                diag['piecewise_primitive_steps']=c['synth_ops'].steps+c['archive_ops'].steps-before_ops
        used=[];invented=[];compile_cost=0;comp_evals=0;schema_cost=0;cold_used=False
        if program is not None:
            cold_used=bool(lib.reactivate_locked(program))
            for branch in program.branches:
                for root in (branch.guard,branch.transform):
                    for node in walk(root):
                        if isinstance(node,EvolvedMacroNode):
                            used.append(node.macro_id)
                    kind='bool_macro' if root.out_type==TypeTag.BOOL else 'seq_macro' if root.out_type==TypeTag.SEQ else 'int_macro'
                    op,cost=lib.promote_ast_subtree(root,kind,layer=2 if any(isinstance(n,EvolvedMacroNode) for n in walk(root)) else 1)
                    compile_cost+=cost
                    if op and op.uses==1:invented.append(op.name)
            lib.register_memoized_program(program)
            comp_evals,extra=lib.compress_solved_programs_mdl(program,True,c['compression_ops'])
            domain='LOGIC' if len(program.branches)>1 else 'STATE' if isinstance(records[0]['payload'],(StateRecord,dict)) else cache.kind
            invented.extend(extra);schema_cost=lib.distill(program,domain)
        status='unique' if program else 'ambiguous' if ambiguous else 'abstain'
        report.status=status;report.ambiguous=ambiguous;report.oog_abstained=status=='abstain';report.admitted_field=field if program else None
        report.program_ast=(program or PiecewiseProgramAST((),default)).to_dict()
        report.program_ast['domain_kind']='integer' if cache.kind==TypeTag.INT else 'sequence'
        report.public_observations=[dict(slot=initial[i],input=x,observed_output=y) for i,(x,y) in enumerate(pairs)]+observations
        report.public_consistent=bool(program);report.public_env_probes=reads;report.channel_invariance_evals=len(records)
        report.probe_work=reads+len(records)+c['probe_evals'];report.gate_evals=gate_work
        report.synthesis_evals=c['synth_evals']+cache.mask_checks;report.archive_lookup_evals=c['archive_evals']+lib.index_work
        report.const_extraction_work=len(pairs);report.schema_distill_cost=schema_cost;report.compile_cost=compile_cost;report.compression_evals=comp_evals
        for name,field in [('synth','synth_primitive_op_steps'),('archive','archive_primitive_op_steps'),('probe','probe_primitive_op_steps'),('gate','gate_primitive_op_steps'),('compression','compression_primitive_op_steps')]:setattr(report,field,c[name+'_ops'].steps)
        report.archive_primitive_op_steps+=lib.index_counter.steps
        report.total_work=sum(getattr(report,k) for k in WORK_KEYS);report.total_primitive_op_steps=sum(getattr(report,k) for k in PRIMITIVE_KEYS)
        report.cold_archive_reactivated=cold_used;report.sub_macro_reused=bool(used);report.used_operators=tuple(used);report.invented_macros=tuple(invented)
        report.subtree_macro_invented=bool(extra) if program else False
        report.max_hierarchy_depth=legacy.max_hierarchy_depth(program) if program else 0
        report.active_library_size=len(lib.operators);report.cold_archive_size=len(lib.cold_archive)
        # Refresh masks before serialization; counts below include that audit.
        cache.refresh_partial()
        report.synthesis_evals=c['synth_evals']+cache.mask_checks
        report.archive_lookup_evals=c['archive_evals']+lib.index_work
        report.synth_primitive_op_steps=c['synth_ops'].steps
        report.archive_primitive_op_steps=c['archive_ops'].steps+lib.index_counter.steps
        report.total_work=sum(getattr(report,k) for k in WORK_KEYS)
        report.total_primitive_op_steps=sum(getattr(report,k) for k in PRIMITIVE_KEYS)
        diag.update(cached_coverage_mask_errors=cache.errors,coverage_assertion_evals=cache.audit_evals,
            initial_pairs=[(x,y) for x,y in pairs],evaluated_partial_transforms=[dict(ast=n.to_dict(),coverage=sorted(cov)) for n,cov in cache.partial.values()],
            coverage_pairs=list(cache.pairs),schemas={k:sorted(v) for k,v in lib.relational_schemas.items()},public_reads=reads,
            cold_before=sorted(cold_before),cold_used=sorted(set(used)&cold_before),
            mdl_subtrees=sorted(lib.mdl_subtree_names),
            active_after=sorted(op.macro_node.macro_id for op in lib.operators.values()))
        self.last_diagnostics=diag;report.trace=[dict(phase='exact_cache',**diag)]
        return report


_FIXTURE_SEMANTICS_CACHE={}


def validate_task_fixture_semantics(task_spec):
    # Evaluator-only content-keyed memoization; any changed label, AST or seed
    # changes the key. Return a copy so callers cannot mutate an audit receipt.
    key=repr(task_spec)
    if key not in _FIXTURE_SEMANTICS_CACHE:
        result=_validate_task_fixture_semantics(task_spec)
        if len(_FIXTURE_SEMANTICS_CACHE)>=128:_FIXTURE_SEMANTICS_CACHE.pop(next(iter(_FIXTURE_SEMANTICS_CACHE)))
        _FIXTURE_SEMANTICS_CACHE[key]=(result['valid'],tuple(result['errors']))
    valid,errors=_FIXTURE_SEMANTICS_CACHE[key]
    return dict(valid=valid,errors=list(errors))


def _validate_task_fixture_semantics(task_spec):
    """Evaluator-only: explicit AST and rows; never called by the inner learner."""
    errors=[];gold=task_spec['gold'];target=task_spec.get('target_ast')
    if gold=='unique' and target is None:errors.append('missing_target_ast')
    for seed,part in task_spec['seeds'].items():
        pairs=part['public']+part['private']
        if gold=='unique' and target is not None:
            program=piecewise_from_dict(target) if isinstance(target,dict) else target
            for x,y in pairs:
                if eval_program(program,canonical_input(x))!=canonical_input(y):errors.append('fixture_semantics:'+str(seed))
            for branch in program.branches:
                index=program.branches.index(branch)
                count=sum(bool(eval_expr_ast(branch.guard,canonical_input(x))) and
                    not any(eval_expr_ast(b.guard,canonical_input(x)) for b in program.branches[:index]) and
                    eval_expr_ast(branch.transform,canonical_input(x))!=canonical_input(x) for x,y in part['public'])
                if count<max(MIN_BRANCH_SUPPORT,task_spec.get('min_branch_support',MIN_BRANCH_SUPPORT)):
                    errors.append('branch_support:'+str(seed))
            if not task_spec.get('allow_empty_tokens',False):
                for x,y in pairs:
                    cx=canonical_input(x);cy=canonical_input(y)
                    if isinstance(cy,tuple) and '' in cy and '' not in cx:errors.append('unintended_empty_token:'+str(seed))
            def projection_depth(node):
                children=node.args if isinstance(node,legacy.PrimOpNode) else (node.body_ast,) if isinstance(node,EvolvedMacroNode) else ()
                return (int(isinstance(node,legacy.PrimOpNode) and node.op_name in ('TAIL','DROP_LAST','INIT'))+
                    max((projection_depth(child) for child in children),default=0))
            roots=[b.transform for b in program.branches]
            if any(projection_depth(n)>=2 for n in roots):
                if any(type(x) not in (int,bool) and len(canonical_input(x))<3 for x,y in pairs):errors.append('nested_projection_short_input:'+str(seed))
        if gold=='ambiguous':
            witnesses=task_spec.get('ambiguous_witnesses',())
            if len(witnesses)<2:errors.append('missing_ambiguity_witnesses')
            elif not all(all(eval_program(p,x)==canonical_input(y) for x,y in part['public']) for p in witnesses):
                errors.append('ambiguity_public_disagreement:'+str(seed))
            elif not any(eval_program(witnesses[0],x)!=eval_program(witnesses[1],x) for x,y in part['private']):
                errors.append('ambiguity_no_private_separation:'+str(seed))
        if gold=='abstain':
            cache=ExactCache([(canonical_input(x),canonical_input(y)) for x,y in pairs],new_counters())
            tokens,ints=extract_constants(cache.pairs)
            enum=TypedProgramEnumerator(cache.kind,tokens,ints,cache)
            strict=frozenset(i for i,(x,y) in enumerate(cache.pairs) if x!=y)
            masks=[]
            for node in enum.base()+enum.atomic():
                _,cov=cache.transform(node)
                if cov:masks.append(cov)
            # Conservative sufficient certificate for this bounded two-branch
            # grammar. Refuse to certify OOG if any one/two transforms cover it.
            if any(a|b==strict for a in masks for b in masks):errors.append('oog_not_certified:'+str(seed))
    if set(map(int,task_spec['seeds']))!={0,1,2}:errors.append('fixture_seed_grid')
    return dict(valid=not errors,errors=errors)
