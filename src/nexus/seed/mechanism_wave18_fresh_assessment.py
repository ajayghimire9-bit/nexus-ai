"""Post-freeze Wave18 unseen18-task suite (`w18f_*` namespace).

Authored only after physical freeze Commit 1 (`89c2e6bc3265d0e9822ff2dd17e7254f665eaf07`).
Every task has an independent Python oracle checked against the target AST.
"""
from __future__ import annotations

from . import wave17_exact_cache_boundary_learner as w17

X = w17.VarNode(w17.TypeTag.SEQ)
IX = w17.VarNode(w17.TypeTag.INT)
SEQ = w17.TypeTag.SEQ
INT = w17.TypeTag.INT
TOK = w17.TypeTag.TOK
BOOL = w17.TypeTag.BOOL


def token(value):
    return w17.ConstNode(value, TOK)


def unary(name, child=X):
    return w17.PrimOpNode(name, (child,), SEQ)


def prepend(value, child=X):
    return w17.PrimOpNode('PREPEND_TOK', (token(value), child), SEQ)


def append(child, value):
    return w17.PrimOpNode('APPEND_TOK', (child, token(value)), SEQ)


def parity(kind=SEQ, value=0):
    scalar = IX if kind == INT else w17.PrimOpNode('LEN', (X,), INT)
    return w17.PrimOpNode('INT_EQ', (w17.PrimOpNode('MOD2', (scalar,), INT), w17.ConstNode(value, INT)), BOOL)


def program(transform, guard=None, kind=SEQ):
    guard = guard or parity(kind, 0)
    default = IX if kind == INT else X
    return w17.PiecewiseProgramAST((w17.PiecewiseBranch(guard, transform),), default)


def fresh_inputs(seed, short=False):
    alphabets = (
        ('alor', 'bren', 'cyra', 'dova', 'elix', 'faro'),
        ('gale', 'hira', 'ivon', 'jaro', 'kyle', 'lyra'),
        ('mira', 'nove', 'orin', 'pyra', 'quon', 'reva'),
    )
    a, b, c, d, e, f = alphabets[seed]
    if short:
        return [
            (a, b, c, d),
            (b, c, d),
            (c, d, e, a),
            (d, e, a),
            (a, c, c, a),
            (b, d, b),
            (e, a, b, c, d, e),
            (a, b, c, d, e),
            (b, c, d, e, f, a),
            (c, d, e, f, a),
            (d, a, a, d),
            (e, b, c, d),
            (a, f, f, a),
            (b, e, a, c, d),
            (c, a, b, d, e, f),
            (d, b, c, a, e),
            (e, c, d, b, a, f),
            (f, d, e, c, b),
            (a, d, b, e, c, f),
            (b, f, c, d, e),
            (c, e, e, c),
            (d, f, a, b, c, e),
            (e, a, d, c, b),
            (f, b, c, d, a, e),
        ]
    return [
        (a, 'kora', b, c),
        (b, c, 'kora'),
        ('kora', c, d, e),
        (d, e, a),
        (a, b, 'kora', d, e, f),
        (b, 'kora', c, d, e),
        (c, d, e, 'kora', a, b),
        (d, e, f, a, b),
        (e, 'kora', a, b, c, d),
        (f, a, 'kora', b, c),
        (a, c, d, 'kora', e, f),
        (b, d, e, f, a),
        ('kora', b, d, e, f, a),
        (c, e, 'kora', a, b),
        (d, f, a, b, 'kora', c),
        (e, a, b, c, d),
        (f, 'kora', c, d, e, a),
        (a, d, e, 'kora', f),
        (b, e, f, a, c, 'kora'),
        (c, f, a, b, d),
        (d, 'kora', b, c, e, f),
        (e, b, c, d, f),
        (f, c, 'kora', d, e, a),
        (a, e, f, b, c),
    ]


def make_spec(identifier, split, target, fn, *, short=False, integers=False, gold='unique'):
    seeds = {}
    for seed in (0, 1, 2):
        if integers:
            xs = [2 + seed, 3 + seed, 4 + seed, 5 + seed, 6 + seed, 7 + seed, 8 + seed, 9 + seed,
                  10 + seed, 11 + seed, 12 + seed, 13 + seed, 14 + seed, 15 + seed, 16 + seed, 17 + seed,
                  18 + seed, 19 + seed, 20 + seed, 21 + seed, 22 + seed, 23 + seed, 24 + seed, 25 + seed]
        else:
            xs = fresh_inputs(seed, short=short)
        public = xs[:20]
        private = xs[20:]
        seeds[seed] = dict(
            public=[(x, fn(x)) for x in public],
            private=[(x, fn(x)) for x in private],
            confirm_count=2,
        )
    spec = dict(
        id=identifier,
        split=split,
        gold=gold,
        target_ast=target.to_dict() if target else None,
        seeds=seeds,
    )
    if target is not None:
        w17.validate_task_fixture_semantics(spec)
    return spec


def fresh_specs():
    def even_swap(x):
        return (x[-1],) + x[1:-1] + (x[0],) if len(x) >= 2 and len(x) % 2 == 0 else x

    def odd_rot_left(x):
        return x[1:] + x[:1] if len(x) >= 1 and len(x) % 2 == 1 else x

    def int_add(x):
        return x + 4 if x % 2 == 0 else x

    def drop_kora(x):
        return tuple(v for v in x if v != 'kora')

    def even_filter(x):
        return drop_kora(x) if len(x) % 2 == 0 else x

    def core_fn(x):
        dropped = x[:-1]
        rotated = dropped[1:] + dropped[:1] if dropped else ()
        return tuple(v for v in rotated if v != 'kora')

    def core_prepend(x):
        return ('zelin',) + core_fn(x) if len(x) % 2 == 0 else x

    def core_append(x):
        return core_fn(x) + ('mavu',) if len(x) % 2 == 0 else x

    def core_reuse(x):
        return ('toren',) + core_fn(x) if len(x) % 2 == 0 else x

    def core_reverse(x):
        return core_fn(x)[::-1] if len(x) % 2 == 0 else x

    def core_chain(x):
        return ('sira',) + core_fn(x)[::-1] if len(x) % 2 == 0 else x

    def p1(x):
        return ('vexo',) + x if len(x) % 2 == 0 else x + ('pali',)

    def p2(x):
        return ('vexo',) + drop_kora(x) if len(x) % 2 == 0 else x + ('pali',)

    def pal(x):
        return x == x[::-1]

    def archive_intro(x):
        return x + ('rudo',) if pal(x) else x

    def even_tail(x):
        return x[1:] if len(x) % 2 == 0 else x

    def int_neg(x):
        return -x if x % 2 == 1 else x

    def even_reverse(x):
        return x[::-1] if len(x) % 2 == 0 else x

    def archive_reuse(x):
        return ('neva',) + x if pal(x) else x

    def oog(x):
        out = []
        for i in range(0, len(x), 2):
            out.extend(x[i:i+2][::-1])
        return tuple(out)

    core = w17.FilterSeqNode(unary('ROT_LEFT', unary('DROP_LAST')), token('kora'))
    pal_guard = w17.PrimOpNode('SEQ_EQ', (X, unary('REVERSE')), BOOL)
    piece1 = w17.PiecewiseProgramAST((
        w17.PiecewiseBranch(parity(), prepend('vexo', X)),
        w17.PiecewiseBranch(parity(value=1), append(X, 'pali')),
    ), X)
    piece2 = w17.PiecewiseProgramAST((
        w17.PiecewiseBranch(parity(), prepend('vexo', w17.FilterSeqNode(X, token('kora')))),
        w17.PiecewiseBranch(parity(value=1), append(X, 'pali')),
    ), X)

    cases = [
        make_spec('w18f_base_swap', 'base', program(unary('SWAP_ENDS')), even_swap, short=True),
        make_spec('w18f_base_odd_rot', 'base', program(unary('ROT_LEFT'), parity(value=1)), odd_rot_left, short=True),
        make_spec('w18f_int_add', 'int', program(w17.PrimOpNode('INT_ADD', (IX, w17.ConstNode(4, INT)), INT), kind=INT), int_add, integers=True),
        make_spec('w18f_filter_transfer', 'filter', program(w17.FilterSeqNode(X, token('kora'))), even_filter),
        make_spec('w18f_core_prepend', 'core', program(prepend('zelin', core)), core_prepend),
        make_spec('w18f_core_append', 'core', program(append(core, 'mavu')), core_append),
        make_spec('w18f_core_reuse', 'core', program(prepend('toren', core)), core_reuse),
        make_spec('w18f_core_reverse', 'core', program(unary('REVERSE', core)), core_reverse),
        make_spec('w18f_core_chain', 'l2', program(prepend('sira', unary('REVERSE', core))), core_chain),
        make_spec('w18f_piecewise_1', 'piecewise', piece1, p1, short=True),
        make_spec('w18f_piecewise_2', 'piecewise', piece2, p2),
        make_spec('w18f_archive_intro', 'archive', program(append(X, 'rudo'), pal_guard), archive_intro, short=True),
        make_spec('w18f_base_third_distractor', 'distractor', program(unary('TAIL')), even_tail, short=True),
        make_spec('w18f_int_distractor', 'distractor', program(w17.PrimOpNode('INT_NEG', (IX,), INT), parity(INT, 1), INT), int_neg, integers=True),
        make_spec('w18f_reverse_distractor', 'distractor', program(unary('REVERSE')), even_reverse, short=True),
        make_spec('w18f_archive_reuse', 'archive', program(prepend('neva', X), pal_guard), archive_reuse, short=True),
    ]

    outside = make_spec('w18f_outside_grammar', 'oog', None, oog, gold='abstain')
    for seed, part in outside['seeds'].items():
        inputs = [tuple('w18f_oog_%d_%d' % (seed, k) for k in range(n)) for n in range(6, 28)]
        part['public'] = [(x, oog(x)) for x in inputs]
        part['private'] = [(x, oog(x)) for x in inputs[-4:]]
    cases.append(outside)

    g1 = parity(value=1)
    g2 = w17.PrimOpNode('INT_EQ', (w17.PrimOpNode('LEN', (X,), INT), w17.ConstNode(3, INT)), BOOL)
    p = program(append(X, 'luma'), g1)
    q = program(append(X, 'luma'), g2)
    ambiguous = make_spec('w18f_ambiguous_intent', 'ambiguous', None, odd_rot_left, gold='ambiguous')
    for seed, part in ambiguous['seeds'].items():
        xs = [x for x in fresh_inputs(seed, short=True) if len(x) in (3, 4)]
        xs = (xs * 4)[:22]
        part['public'] = [(x, w17.eval_program(p, x)) for x in xs]
        private = [('u', 'v', 'w', 'z', 'q')]
        part['private'] = [(x, w17.eval_program(p, x)) for x in private]
    ambiguous['ambiguous_witnesses'] = [p.to_dict(), q.to_dict()]
    cases.append(ambiguous)
    return cases
