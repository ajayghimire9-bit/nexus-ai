"""Optional MPS proposal ordering over the frozen Wave17 exact solver.

Neural scores order hypotheses; only the interpreter and public evidence certify
them. The frozen solver's code object is rebound to explicit, task-local cache
and enumerator factories, avoiding both a copied solver and global monkeypatches.
No historical module, evaluator, private labels or external model is modified.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import math
import time
from types import FunctionType

from . import wave17_exact_cache_boundary_learner as exact

VarNode = exact.VarNode
ConstNode = exact.ConstNode
PrimOpNode = exact.PrimOpNode
EvolvedMacroNode = exact.EvolvedMacroNode
PiecewiseProgramAST = exact.PiecewiseProgramAST
PiecewiseBranch = exact.PiecewiseBranch
TypeTag = exact.TypeTag
OpCounter = exact.OpCounter
FilterSeqNode = exact.FilterSeqNode
MapReplaceTokNode = exact.MapReplaceTokNode
StateRecord = exact.StateRecord
eval_expr_ast = exact.eval_expr_ast
eval_program = exact.eval_program
walk = exact.walk
PUBLIC_BUDGET = exact.PUBLIC_BUDGET
WORK_KEYS = exact.WORK_KEYS + ('neural_proposer_work',)
PRIMITIVE_KEYS = exact.PRIMITIVE_KEYS
METHODS = ('standalone_m4_neural_baseline', 'equal_typed_scratch',
           'ordinary_persistent_memoization', 'nexus_whole_macro_only',
           'nexus_typed_without_pruning', 'nexus_m4_neuro_symbolic_full')
POLICY_LABELS = ('PREPEND_TOK', 'APPEND_TOK', 'REVERSE', 'TAIL', 'DROP_LAST',
                 'FILTER_NEQ', 'MAP_REPLACE', 'ROT_LEFT', 'ROT_RIGHT', 'SWAP_ENDS',
                 'GUARD_PARITY_TRANSFORM', 'BOUNDARY_EQ_INVOLUTION',
                 'THRESHOLD_FILTER_COMMIT', 'PIECEWISE_PRIORITY_ROUTER')
FEATURE_DIM = 24
HIDDEN_DIM = 32
MAX_PUBLIC_SEQUENCE_LENGTH = 128
LEARNING_RATE = .003
ONLINE_STEPS = 3


def _primitive(node, name):
    return isinstance(node, exact.legacy.PrimOpNode) and node.op_name == name


def _token_const(node):
    return isinstance(node, ConstNode) and node.out_type == TypeTag.TOK


def is_dynamic_const_free(node):
    if isinstance(node, ConstNode):
        return node.out_type != TypeTag.TOK
    if isinstance(node, FilterSeqNode) or _primitive(node, 'FILTER_NEQ'):
        return is_dynamic_const_free(node.args[0])
    if isinstance(node, (exact.legacy.PrimOpNode, EvolvedMacroNode)):
        return all(is_dynamic_const_free(a) for a in node.args)
    return True


def _wrapper_child(node):
    if _primitive(node, 'PREPEND_TOK') and _token_const(node.args[0]):
        return node.args[1]
    if _primitive(node, 'APPEND_TOK') and _token_const(node.args[1]):
        return node.args[0]
    if _primitive(node, 'REVERSE'):
        return node.args[0]
    return None


def canonical_order(node):
    """One terminating normal-form preference; never two opposing rewrite loops."""
    child = _wrapper_child(node)
    preferred = child is not None and is_dynamic_const_free(child)
    return (not preferred, exact.search_nodes(node), repr(exact.ast_key(node)))


def _rewrite_candidates(node):
    if isinstance(node, EvolvedMacroNode):
        return [node]  # Never change an existing macro's meaning or identity.
    result = [node]
    if not isinstance(node, exact.legacy.PrimOpNode):
        return result
    if node.op_name == 'APPEND_TOK':
        left, right = node.args
        if _primitive(left, 'PREPEND_TOK') and _token_const(left.args[0]):
            c, z = left.args
            result.append(PrimOpNode('PREPEND_TOK', (c,
                PrimOpNode('APPEND_TOK', (z, right), TypeTag.SEQ)), TypeTag.SEQ))
    if node.op_name == 'PREPEND_TOK':
        left, right = node.args
        if _primitive(right, 'APPEND_TOK') and _token_const(right.args[1]):
            z, c = right.args
            result.append(PrimOpNode('APPEND_TOK', (
                PrimOpNode('PREPEND_TOK', (left, z), TypeTag.SEQ), c), TypeTag.SEQ))
    if node.op_name == 'FILTER_NEQ':
        seq, removed = node.args
        if (_primitive(seq, 'PREPEND_TOK') and _token_const(seq.args[0])
                and _token_const(removed) and seq.args[0].value != removed.value):
            result.append(PrimOpNode('PREPEND_TOK', (seq.args[0],
                FilterSeqNode(seq.args[1], removed)), TypeTag.SEQ))
        if (_primitive(seq, 'APPEND_TOK') and _token_const(seq.args[1])
                and _token_const(removed) and seq.args[1].value != removed.value):
            result.append(PrimOpNode('APPEND_TOK', (
                FilterSeqNode(seq.args[0], removed), seq.args[1]), TypeTag.SEQ))
    return result


def canonicalize_expr_ast(node, obs_init, op_counter=None, *, require_support=True,
                          receipt=None):
    """Conservative verified rewrites, including the empty boundary.

    Only the algebraic commutations above are proposed. A finite signature alone
    never licenses a new identity. Every executed verification is charged.
    require_support=False is used while enumerating partial transforms; it still
    requires exact equality to the original on every public and boundary input.
    """
    receipt = receipt if receipt is not None else {'evals': 0}
    if isinstance(node, EvolvedMacroNode):
        return node
    if isinstance(node, exact.legacy.PrimOpNode):
        children = tuple(canonicalize_expr_ast(a, obs_init, op_counter,
            require_support=False, receipt=receipt) for a in node.args)
        rebuilt = PrimOpNode(node.op_name, children, node.out_type)
    else:
        return node
    candidates = _rewrite_candidates(rebuilt)
    candidate = min(candidates, key=canonical_order)
    if exact.ast_key(candidate) == exact.ast_key(node):
        return node
    pairs = [(exact.canonical_input(x), exact.canonical_input(y)) for x, y in obs_init]
    boundaries = (exact.INTEGER_BOUNDARY_INPUTS if pairs and type(pairs[0][0]) is int
                  else exact.CANONICAL_BOUNDARY_INPUTS)
    # A typed scalar child must not be evaluated with sequence inputs.
    inputs = [x for x, _ in pairs] + list(boundaries)
    def execute(tree, x):
        receipt['evals'] = receipt.get('evals', 0) + 1
        return eval_expr_ast(tree, x, op_counter)
    try:
        for x in inputs:
            if execute(candidate, x) != execute(node, x):
                return node
        if require_support:
            for x, y in pairs:
                if x != y and execute(candidate, x) != y:
                    return node
    except (TypeError, ValueError, IndexError):
        return node
    return candidate


@dataclass
class NeuralTelemetry:
    gpu_device: str = 'mps'
    mps_available: bool = False
    gpu_forward_passes: int = 0
    gpu_encoder_calls: int = 0
    gpu_online_update_steps: int = 0
    gpu_wall_ms: float = 0.
    neural_proposer_work: int = 0
    dense_linear_macs: int = 0
    gpu_allocated_peak_bytes: int = 0
    gpu_driver_peak_bytes: int = 0
    head_expansions: int = 0

    def snapshot(self):
        return dict(vars(self))


def require_mps():
    import torch
    if not torch.backends.mps.is_available():
        raise RuntimeError('MPS_REQUIRED_NO_SILENT_CPU_FALLBACK')
    return torch, torch.device('mps')


def encode_task_observations_mps(pairs, telemetry):
    """Public observations only. Token IDs are arbitrary local equality codes.

    GPU computes24 structural statistics. No learned/token/task identifiers are
    features; CPU only encodes ragged raw observations to padded numeric tensors.
    The public-input packing work is charged separately from neural forwards.
    """
    torch, device = require_mps()
    if not pairs:
        raise ValueError('empty_public_observations')
    pairs = [(exact.canonical_input(x), exact.canonical_input(y)) for x, y in pairs]
    scalar = type(pairs[0][0]) in (int, bool)
    integer = [[float(x), float(y)] for x, y in pairs] if scalar else [[0., 0.]]*len(pairs)
    if scalar:
        seqs = [((), ()) for _ in pairs]
    else:
        seqs = pairs
        if any(max(len(x),len(y)) > MAX_PUBLIC_SEQUENCE_LENGTH for x,y in seqs):
            raise ValueError('neural_feature_input_limit_no_silent_truncation')
    vocab = {token: i+1 for i, token in enumerate(sorted({v for x, y in seqs for v in x+y}))}
    width = max(1, max(max(len(x), len(y)) for x, y in seqs))
    raw_x = [[vocab[v] for v in x]+[0]*(width-len(x)) for x, _ in seqs]
    raw_y = [[vocab[v] for v in y]+[0]*(width-len(y)) for _, y in seqs]
    telemetry.neural_proposer_work += len(pairs)*(2*width+2)
    torch.mps.synchronize();start = time.perf_counter()
    x = torch.tensor(raw_x, dtype=torch.float32, device=device)
    y = torch.tensor(raw_y, dtype=torch.float32, device=device)
    ints = torch.tensor(integer, dtype=torch.float32, device=device)
    nx = (x != 0).sum(1).float();ny = (y != 0).sum(1).float();delta = ny-nx
    ids = torch.arange(width, device=device)[None, :].expand(len(pairs), -1)
    rev_ids = (nx.long()[:, None]-1-ids).clamp(0, width-1)
    rev_x = x.gather(1, rev_ids);valid = ids < nx[:, None]
    end_x = x.gather(1, (nx.long()-1).clamp(0)[:, None]).squeeze(1)
    end_y = y.gather(1, (ny.long()-1).clamp(0)[:, None]).squeeze(1)
    present_x = (x[:, :, None] == y[:, None, :]) & (x[:, :, None] != 0) & (y[:, None, :] != 0)
    deleted = ((x != 0) & ~present_x.any(2)).float().sum(1)/nx.clamp(min=1)
    added = ((y != 0) & ~present_x.any(1)).float().sum(1)/ny.clamp(min=1)
    diff = ints[:, 1]-ints[:, 0]
    state = any('=' in token for token in vocab)
    ones = nx.new_tensor(1.)
    f = torch.stack((ones*int(scalar), ones*int(not scalar), ones*int(state),
        nx.mean()/16, ny.mean()/16, delta.min()/16, delta.max()/16,
        delta.mean()/16, delta.var(unbiased=False)/256,
        (x[:, 0] == y[:, 0]).float().mean(), (end_x == end_y).float().mean(),
        (((rev_x == y) | ~valid).all(1) & (nx == ny)).float().mean(),
        deleted.mean(), added.mean(), ((deleted > 0) & (added > 0)).float().mean(),
        ((x[:, 0] == end_x) & (nx > 1)).float().mean(),
        ((y[:, 0] == end_y) & (ny > 1)).float().mean(),
        (nx == 0).float().mean(), (ny == 0).float().mean(),
        (ints[:, 0].remainder(2) == 0).float().mean()*int(scalar),
        (ints[:, 1].remainder(2) == ints[:, 0].remainder(2)).float().mean()*int(scalar),
        diff.mean()/16, diff.var(unbiased=False)/256,
        (diff == 0).float().mean()*int(scalar)))
    if f.shape != (FEATURE_DIM,) or not bool(torch.isfinite(f).all().item()):
        raise ValueError('invalid_residual_features')
    torch.mps.synchronize()
    telemetry.gpu_wall_ms += (time.perf_counter()-start)*1000
    telemetry.gpu_encoder_calls += 1
    return f[None, :]


class M4NeuroSymbolicProposer:
    """A real torch module owned here, with no CPU inference fallback.

    Dynamic head expansion preserves old parameters AND AdamW moments. Features
    and multi-label targets use only public evidence and publicly verified ASTs.
    No held-out accuracy feeds the optimizer. Scores are never proof of truth.
    """
    def __init__(self, seed=0):
        torch, self.device = require_mps()
        self.torch = torch;self.seed = seed
        self.telemetry = NeuralTelemetry(mps_available=True)
        # Initialization on CPU is scoped; every neural forward/update is MPS.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.network = torch.nn.Sequential(torch.nn.Linear(FEATURE_DIM, HIDDEN_DIM),
                torch.nn.GELU(), torch.nn.LayerNorm(HIDDEN_DIM),
                torch.nn.Linear(HIDDEN_DIM, len(POLICY_LABELS))).to(self.device)
        self.labels = list(POLICY_LABELS)
        self.optimizer = torch.optim.AdamW(self.network.parameters(), lr=LEARNING_RATE,
                                           weight_decay=.01, foreach=False)
        self.last_features = None;self.probabilities = {};self.training_receipts = []
        self._candidate_scores = {}

    @property
    def macro_head_output_dimension(self):
        return len(self.labels)-len(POLICY_LABELS)

    def _measure_start(self):
        self.torch.mps.synchronize()
        return time.perf_counter()

    def _measure_end(self, start):
        torch = self.torch;torch.mps.synchronize()
        self.telemetry.gpu_wall_ms += (time.perf_counter()-start)*1000
        self.telemetry.gpu_allocated_peak_bytes = max(self.telemetry.gpu_allocated_peak_bytes,
            torch.mps.current_allocated_memory())
        self.telemetry.gpu_driver_peak_bytes = max(self.telemetry.gpu_driver_peak_bytes,
            torch.mps.driver_allocated_memory())

    def _forward(self, features):
        self.telemetry.gpu_forward_passes += 1
        self.telemetry.neural_proposer_work += 1
        self.telemetry.dense_linear_macs += features.shape[0]*(FEATURE_DIM*HIDDEN_DIM+HIDDEN_DIM*len(self.labels))
        return self.network(features)

    def encode_and_rank(self, pairs):
        self._candidate_scores = {}
        self.last_features = encode_task_observations_mps(pairs, self.telemetry)
        start = self._measure_start()
        with self.torch.no_grad():
            probabilities = self._forward(self.last_features).sigmoid()[0].cpu().tolist()
        self.probabilities = dict(zip(self.labels, probabilities))
        self._measure_end(start)
        return dict(self.probabilities)

    def expand_macro(self, macro_id):
        name = 'macro:'+macro_id
        if name in self.labels:
            return False
        torch = self.torch;old = self.network[-1];start = self._measure_start()
        init_seed = int.from_bytes(hashlib.sha256((str(self.seed)+name).encode()).digest()[:4], 'big')
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(init_seed)
            new = torch.nn.Linear(HIDDEN_DIM, len(self.labels)+1).to(self.device)
        with torch.no_grad():
            new.weight[:-1].copy_(old.weight);new.bias[:-1].copy_(old.bias)
        for before, after in ((old.weight, new.weight), (old.bias, new.bias)):
            for group in self.optimizer.param_groups:
                group['params'] = [after if p is before else p for p in group['params']]
            old_state = self.optimizer.state.pop(before, {})
            new_state = {}
            for key, value in old_state.items():
                if key in ('exp_avg', 'exp_avg_sq', 'max_exp_avg_sq'):
                    expanded = torch.zeros_like(after);expanded[:-1].copy_(value)
                    new_state[key] = expanded
                else:
                    new_state[key] = value.clone() if hasattr(value, 'clone') else value
            self.optimizer.state[after] = new_state
        self.network[-1] = new;self.labels.append(name)
        self.telemetry.head_expansions += 1;self.telemetry.neural_proposer_work += 1
        self._measure_end(start)
        return True

    def update_proposer_on_mps(self, program, schema_tags=()):
        if self.last_features is None:
            raise ValueError('missing_preanswer_features')
        torch = self.torch
        used = set(schema_tags)
        for branch in program.branches:
            for root in (branch.guard, branch.transform):
                for node in walk(root):
                    if isinstance(node, EvolvedMacroNode):
                        used.add('macro:'+node.macro_id)
                    elif isinstance(node, exact.legacy.PrimOpNode):
                        used.add(node.op_name)
        start = self._measure_start()
        target = torch.tensor([[float(name in used) for name in self.labels]],
                              dtype=torch.float32, device=self.device)
        losses = []
        for _ in range(ONLINE_STEPS):
            self.optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                self._forward(self.last_features.detach()), target)
            if not bool(torch.isfinite(loss).item()):
                raise FloatingPointError('nonfinite_neural_loss')
            loss.backward();self.optimizer.step()
            self.telemetry.gpu_online_update_steps += 1
            self.telemetry.neural_proposer_work += 1
            losses.append(float(loss.detach().cpu()))
        self.training_receipts.append(dict(labels=sorted(used), losses=losses,
                                           feedback='public_verified_ast_only'))
        self._measure_end(start)

    def candidate_score(self, node):
        key = exact.ast_key(node)
        if key in self._candidate_scores:
            return self._candidate_scores[key]
        labels = []
        for n in walk(node):
            self.telemetry.neural_proposer_work += 1
            if isinstance(n, EvolvedMacroNode):
                labels.append('macro:'+n.macro_id)
            elif isinstance(n, exact.legacy.PrimOpNode) and n.op_name in self.probabilities:
                labels.append(n.op_name)
        value = (sum(math.log(max(1e-9, self.probabilities.get(k, .5))) for k in labels)/len(labels)
                 if labels else 0.)
        self._candidate_scores[key] = value
        return value


def constant_free_core_table(pairs, compression_counter):
    """Bounded sizes4..5; signature lookup is observational, never a theorem."""
    counters = exact.new_counters()
    for name in ('synth', 'archive', 'probe', 'gate', 'compression'):
        counters[name+'_ops'] = compression_counter
    cache = exact.ExactCache(list(pairs), counters)
    if cache.kind != TypeTag.SEQ:
        return {}, cache, 0
    enum = exact.TypedProgramEnumerator(cache.kind, (), (0,1,2), cache)
    table = {}
    levels = enum.atomic_levels()
    for _ in range(4):  # yields sizes2,3,4,5, never requests size6
        for node in next(levels):
            if 4 <= node.ast_nodes() <= 5 and is_dynamic_const_free(node):
                key = cache.signature(node)
                if key not in table or canonical_order(node) < canonical_order(table[key]):
                    table[key] = node
    return table, cache, sum(counters[k+'_evals'] for k in ('synth','archive','probe'))


class CanonicalMacroLibrary(exact.MacroLibrary):
    def compress_solved_programs_mdl(self, latest, structure_discovered, compression_counter):
        """Canonical exact subtrees, plus a metered finite peeled-core lookup.

        Only constant affixes are stripped. Reverse peeling uses the exact child
        AST. The finite signature table retrieves proposals, not equivalence
        proofs. Every promoted core is an existing constant-free expression.
        """
        if not self.use_macro_evolution or not structure_discovered:
            return 0, ()
        pairs = getattr(self, 'task_pairs', ())
        receipt = {'evals': 0}
        branches = tuple(PiecewiseBranch(b.guard, canonicalize_expr_ast(b.transform,
            pairs, compression_counter, require_support=False, receipt=receipt)) for b in latest.branches)
        canonical = PiecewiseProgramAST(branches, latest.default)
        evals, invented = super().compress_solved_programs_mdl(canonical,
            structure_discovered, compression_counter)
        if not self.use_internal_subtree:
            return evals+receipt['evals'], invented
        # Syntactic extraction already counts distinct task support. Record
        # peeled canonical cores separately, using the same MDL owner/events.
        pending = self.__dict__.setdefault('pending_peeled_cores', [])
        new_peeled = False
        for branch in branches:
            child = _wrapper_child(branch.transform)
            if (child is None or isinstance(child, EvolvedMacroNode)
                    or not is_dynamic_const_free(child) or not 4 <= child.ast_nodes() <= 5):
                continue
            if any(op.macro_node.body_ast.canonical_key() == child.canonical_key()
                   for op in self.operators.values()):
                continue
            pending.append((self.step, child))
            new_peeled = True
        if not new_peeled or len({s for s, _ in pending}) < 2:
            return evals+receipt['evals'], invented
        table, core_cache, table_cost = constant_free_core_table(pairs, compression_counter)
        receipt['evals'] += table_cost
        for step_id, raw_child in pending:
            before = core_cache.counters['synth_evals']
            signature = core_cache.signature(raw_child)
            receipt['evals'] += core_cache.counters['synth_evals']-before
            # An alternative table representative is an evidence-supported
            # hypothesis; it does not establish arbitrary-input equivalence.
            child = table.get(signature, raw_child)
            key = ('peeled', exact.ast_key(child))
            seen = self.__dict__.setdefault('peeled_core_support', {}).setdefault(key, set())
            if step_id in seen:
                continue
            seen.add(step_id)
            compression_counter.steps += 1;receipt['evals'] += 1
            if len(seen) >= 2:
                kind = 'seq_macro' if child.out_type == TypeTag.SEQ else 'int_macro'
                before = set(self.operators)
                op, _ = self.promote_ast_subtree(child, kind)
                if op is not None:
                    op.uses = max(op.uses, len(seen));op.is_mdl_subtree = True
                    self.mdl_subtree_names.add(op.name);self.mdl_pinned_names.add(op.name)
                    if op.name not in before:
                        invented = tuple(invented)+(op.name,)
        return evals+receipt['evals'], invented


def _bound_solver(cache_factory, enumerator_factory):
    """Task-local DI over trusted frozen code; zero historical/global mutation."""
    original = exact.TypedEqualCapabilityLearner.solve_unfamiliar_task
    namespace = dict(original.__globals__)
    namespace.update(ExactCache=cache_factory, TypedProgramEnumerator=enumerator_factory)
    return FunctionType(original.__code__, namespace, original.__name__,
                        original.__defaults__, original.__closure__)


class Wave18Learner:
    def __init__(self, method, seed=0):
        if method not in METHODS:
            raise ValueError('unknown_wave18_method')
        self.public_method = method
        self.method = 'nexus_typed_full' if method == 'nexus_m4_neuro_symbolic_full' else method
        neural = method in (METHODS[0], 'nexus_typed_without_pruning', METHODS[-1])
        self.proposer = M4NeuroSymbolicProposer(seed) if neural else None
        self.library = self.make_library();self.last_diagnostics = {}

    def make_library(self):
        flag_method = 'equal_typed_scratch' if self.public_method == METHODS[0] else self.method
        base = exact.TypedEqualCapabilityLearner(flag_method).library
        if self.proposer is None:
            return base
        lib = CanonicalMacroLibrary(**{f.name:getattr(base,f.name) for f in fields(base)})
        lib.setup()
        return lib

    def _neural_baseline(self, env, public_budget):
        # Deliberately limited top-k decoder, not a claim about LLM ability.
        # No evaluator/gold fields, private rows or forced baseline failures.
        slots = ['alpha', 'beta', 'gamma', 'delta', 'epsilon']
        slots += [s for s in env.extra_public_slots if not s.startswith('confirm_')][:3]
        rows = [env.public_read(s) for s in slots[:public_budget]]
        fields = sorted(set.intersection(*(set(r)-{'payload','echo','slot','stamp','tick','kind'} for r in rows)))
        if len(fields) != 1:
            raise ValueError('baseline_ambiguous_output_channel')
        pairs = [(exact.canonical_input(r['payload']), exact.canonical_input(r[fields[0]])) for r in rows]
        counters = exact.new_counters();cache = exact.ExactCache(pairs, counters)
        tokens, ints = exact.extract_constants(pairs)
        enum = exact.TypedProgramEnumerator(cache.kind, tokens, ints, cache)
        self.proposer.encode_and_rank(pairs)
        candidates = cache.deduplicate(enum.wrappers(enum.x)+enum.base())
        candidates = sorted(candidates, key=self._neural_decode_order)[:16]
        guards = enum.guards();programs = []
        for node in candidates:
            for guard in guards:
                program = PiecewiseProgramAST((PiecewiseBranch(guard, node),), enum.x)
                errors = 0
                for x, y in pairs:
                    counters['synth_evals'] += 1
                    errors += eval_program(program, x, counters['synth_ops']) != y
                programs.append((errors, repr(exact.ast_key(node)), repr(exact.ast_key(guard)), program))
        program = min(programs, key=_program_rank)[3]
        report = exact.legacy.empty_cost_report('equal_typed_scratch', 'unique',
            (len(rows),0,len(rows)), {}, [], self.library)
        report.status='unique';report.public_consistent=not min(programs,key=_program_rank)[0]
        report.program_ast=program.to_dict();report.admitted_field=fields[0]
        report.public_observations=[dict(slot=s,input=x,observed_output=y) for s,(x,y) in zip(slots,pairs)]
        report.probe_work=len(rows);report.channel_invariance_evals=len(rows)
        report.public_env_probes=len(rows);report.synthesis_evals=counters['synth_evals']
        report.synth_primitive_op_steps=counters['synth_ops'].steps
        self.last_diagnostics={'cached_coverage_mask_errors':0,'uncertified_neural_decode':True,
                               'baseline_top_k':16,'private_labels_used':False}
        return report

    def _proposal_order(self, node):
        score = self.proposer.candidate_score(node) if self.proposer is not None else 0.
        # Ascending syntax cost, then neural ordering, then fixed canonical order.
        return exact.search_nodes(node), -score, canonical_order(node)

    def _neural_decode_order(self, node):
        return -self.proposer.candidate_score(node), canonical_order(node)

    def solve_unfamiliar_task(self, env, public_budget):
        if type(public_budget) is not int or not 8 <= public_budget <= PUBLIC_BUDGET:
            raise ValueError('invalid_public_budget')
        start = time.perf_counter()
        before = self.proposer.telemetry.snapshot() if self.proposer else NeuralTelemetry(gpu_device='none').snapshot()
        canonical_receipt = {'evals':0};canonical_ops = OpCounter()
        owner = self

        class TaskCache(exact.ExactCache):
            def __init__(self, pairs, counters):
                super().__init__(pairs, counters)
                owner.library.task_pairs = self.pairs
                if owner.proposer is not None:
                    owner.proposer.encode_and_rank(self.pairs)

            def transform(self, node):
                if owner.proposer is None:
                    return super().transform(node)
                outputs = tuple(self.predict(node, x) for x, y in self.pairs)
                strict = {i for i, (x, y) in enumerate(self.pairs) if x != y}
                coverage = frozenset(i for i in strict if outputs[i] == self.pairs[i][1])
                if len(coverage) >= exact.MIN_BRANCH_SUPPORT:
                    signature = self.signature(node)
                    if signature not in self.partial or canonical_order(node) < canonical_order(self.partial[signature][0]):
                        category = self.category(node)
                        for i in strict:
                            actual = eval_expr_ast(node, self.pairs[i][0], self.counters[category+'_ops'])
                            self.counters[category+'_evals'] += 1;self.audit_evals += 1
                            if (i in coverage) != (actual == self.pairs[i][1]):
                                self.errors += 1
                            assert (i in coverage) == (actual == self.pairs[i][1]), 'cached_coverage_corruption'
                        self.partial[signature] = (node, coverage)
                return outputs, coverage

            def deduplicate(self, nodes):
                if owner.proposer is None:
                    return super().deduplicate(nodes)
                syntax = set();signatures = set();result = []
                for node in sorted(nodes, key=canonical_order):
                    original_key = exact.ast_key(node)
                    if original_key in syntax:
                        continue
                    syntax.add(original_key)
                    signature = self.signature(node)
                    if signature not in signatures:
                        signatures.add(signature);result.append(node)
                return sorted(result, key=owner._proposal_order)

        class ProposalEnumerator(exact.TypedProgramEnumerator):
            def _needs_piecewise(self):
                strict = [(x, y) for x, y in self.cache.pairs if x != y]
                if len(strict) < 2 * exact.MIN_BRANCH_SUPPORT:
                    return False
                for t in self.tokens:
                    if t in self.filter_tokens:
                        continue
                    added_no_delete = sum(t in (set(y) - set(x)) and set(x) <= set(y) for x, y in strict)
                    absent_other = sum(t not in y and (len(y) >= len(x) or bool(set(y) - set(x))) for x, y in strict)
                    if added_no_delete >= exact.MIN_BRANCH_SUPPORT and absent_other >= exact.MIN_BRANCH_SUPPORT:
                        return True
                return False

            def _piecewise_cover_ready(self):
                if not self._needs_piecewise():
                    return False
                strict_idx = frozenset(i for i, (x, y) in enumerate(self.cache.pairs) if x != y)
                masks = [cov for _, cov in self.cache.partial.values()
                         if len(cov) >= exact.MIN_BRANCH_SUPPORT and len(strict_idx - cov) >= exact.MIN_BRANCH_SUPPORT]
                return any(ca | cb == strict_idx for ca in masks for cb in masks)

            def support_proposal(self, node, min_matches=1):
                category = self.cache.category(node)
                strict = [(x, y) for x, y in self.cache.pairs if x != y]
                if not strict:
                    return True
                needed = min(min_matches, len(strict))
                matches = 0
                total = len(strict)
                for idx, (x, y) in enumerate(strict):
                    children = tuple(ConstNode(self.cache.predict(a, x), a.out_type) for a in node.args)
                    value = eval_expr_ast(PrimOpNode(node.op_name, children, node.out_type), (), self.cache.counters[category+'_ops'])
                    self.cache.counters[category+'_evals'] += 1
                    if value == y:
                        matches += 1
                        if matches >= needed:
                            return True
                    elif matches + (total - idx - 1) < needed:
                        return False
                return False

            def atomic_levels(self):
                if owner.proposer is None or self.kind != TypeTag.SEQ:
                    yield from super().atomic_levels()
                    return
                strict = [(x, y) for x, y in self.cache.pairs if x != y]
                min_sup = min(exact.MIN_BRANCH_SUPPORT, len(strict)) if strict else 1
                active_seq = [op.macro_node for name, op in owner.library.operators.items()
                              if op.macro_node.out_type == TypeTag.SEQ and is_dynamic_const_free(op.macro_node)
                              and (not owner.library.use_pruning or name in owner.library.mdl_subtree_names)]
                by_size = {1: [self.x] + active_seq + [ConstNode((), TypeTag.SEQ)]}
                seen = {self.cache.signature(n) for n in by_size[1]}
                token_nodes = [ConstNode(t, TypeTag.TOK) for t in self.tokens]
                prepend_tokens = [ConstNode(t, TypeTag.TOK) for t in self.tokens
                                  if t == '' or sum(bool(y and (y[0] == t or y[-1] == t)) for _, y in strict) >= min_sup]
                append_tokens = [ConstNode(t, TypeTag.TOK) for t in self.tokens
                                 if t == '' or sum(bool(y and (y[-1] == t or y[0] == t)) for _, y in strict) >= min_sup]
                filter_nodes = [ConstNode(t, TypeTag.TOK) for t in self.tokens if t in self.filter_tokens]
                token_ops = [PrimOpNode('HEAD', (self.x,), TypeTag.TOK), PrimOpNode('LAST', (self.x,), TypeTag.TOK)]
                for size in range(2, 8):
                    if size >= 4 and self._piecewise_cover_ready():
                        return
                    candidates = []
                    for core_size, cores in list(by_size.items()):
                        for core in cores:
                            has_macro = any(isinstance(n, EvolvedMacroNode) for n in walk(core))
                            if has_macro and size > 4:
                                continue
                            const_free = is_dynamic_const_free(core)
                            if core_size + 1 == size:
                                if const_free:
                                    candidates.extend(PrimOpNode(op, (core,), TypeTag.SEQ) for op in exact.UNARY)
                                    candidates.append(exact.DedupAdjSeqNode(core))
                                elif _primitive(core, 'PREPEND_TOK') or _primitive(core, 'APPEND_TOK'):
                                    candidates.append(PrimOpNode('REVERSE', (core,), TypeTag.SEQ))
                            if core_size + 2 == size:
                                for c in prepend_tokens:
                                    candidates.append(PrimOpNode('PREPEND_TOK', (c, core), TypeTag.SEQ))
                                for c in append_tokens:
                                    candidates.append(PrimOpNode('APPEND_TOK', (core, c), TypeTag.SEQ))
                                if const_free and self.loop_free(core):
                                    for c in filter_nodes:
                                        candidates.append(FilterSeqNode(core, c))
                            if core_size + 3 == size and size <= 5 and const_free and not has_macro:
                                for c in token_ops:
                                    candidates.extend((PrimOpNode('APPEND_TOK', (core, c), TypeTag.SEQ),
                                                       PrimOpNode('PREPEND_TOK', (c, core), TypeTag.SEQ)))
                                if self.loop_free(core):
                                    for a in token_nodes:
                                        for b in token_nodes:
                                            if (a.value, b.value) in self.replace_pairs:
                                                candidates.append(MapReplaceTokNode(core, a, b))
                    if size <= 5:
                        for left_size, lefts in by_size.items():
                            for a in lefts:
                                if not is_dynamic_const_free(a) or any(isinstance(n, EvolvedMacroNode) for n in walk(a)):
                                    continue
                                for b in by_size.get(size - left_size - 1, ()):
                                    if not is_dynamic_const_free(b) or any(isinstance(n, EvolvedMacroNode) for n in walk(b)):
                                        continue
                                    if not strict or any(abs(len(self.cache.predict(a, x)) + len(self.cache.predict(b, x)) - len(y)) <= 7 - size for x, y in strict):
                                        candidates.append(PrimOpNode('CONCAT', (a, b), TypeTag.SEQ))
                    if size >= 6:
                        needed = len(strict) if (size == 7 and not self._needs_piecewise()) else min_sup
                        candidates = [n for n in candidates if self.support_proposal(n, needed)]
                    by_size[size] = []
                    for node in self.cache.deduplicate(candidates):
                        signature = self.cache.signature(node)
                        if signature not in seen:
                            seen.add(signature);by_size[size].append(node)
                    yield by_size[size]

        if self.public_method == METHODS[0]:
            report = self._neural_baseline(env, public_budget)
        else:
            report = _bound_solver(TaskCache, ProposalEnumerator)(self, env, public_budget)
        if self.proposer is not None and self.public_method != METHODS[0] and report.status == 'unique':
            # Targets are locked PUBLIC-consistent programs. The evaluator has
            # not yet locked its world or revealed any private outcome here.
            program = exact.piecewise_from_dict(report.program_ast)
            for op in self.library.operators.values():
                if op.name in self.library.mdl_pinned_names:
                    self.proposer.expand_macro(op.macro_node.macro_id)
            self.proposer.update_proposer_on_mps(program, self.library.relational_schemas)
        after = self.proposer.telemetry.snapshot() if self.proposer else before
        row = exact.report_to_row(report)
        row['method'] = self.public_method
        row['compression_evals'] += canonical_receipt['evals']
        row['compression_primitive_op_steps'] += canonical_ops.steps
        row['neural_proposer_work'] = after['neural_proposer_work']-before['neural_proposer_work']
        row['total_work'] = sum(int(row[k]) for k in WORK_KEYS)
        row['total_primitive_op_steps'] = sum(int(row[k]) for k in PRIMITIVE_KEYS)
        row['gpu'] = {k:after[k]-before[k] if type(after[k]) in (int,float) and k not in
                      ('gpu_allocated_peak_bytes','gpu_driver_peak_bytes') else after[k] for k in after}
        row['gpu']['mps_available'] = bool(after['mps_available'])
        row['total_wall_s'] = time.perf_counter()-start
        row['support_gate'] = self.last_diagnostics
        if self.proposer is not None:
            row['neural_policy_labels'] = list(self.proposer.labels)
            row['neural_training_receipts'] = self.proposer.training_receipts[-1:] if report.status=='unique' else []
        return row


def _program_rank(value):
    return value[:3]
