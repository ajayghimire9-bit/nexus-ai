"""H17 draft arithmetic and record contracts, never an experiment runner.

No holdout/seed selection, model loading, scoring, simulator or authorization.
Reuse the standard-library H16 arithmetic instead of importing world code.
"""
from dataclasses import dataclass
import struct

from nexus.h16_selection_mechanism_diagnosis import (
    ARMS, LIBRARIES, close, integer, interval, mean, number, require, vector,
)

SOURCES = ('reference', 'multitask_fixed', 'scratch_fixed',
           'multitask_redraw', 'scratch_redraw')
CONTROLLERS = SOURCES[1:]


@dataclass(frozen=True)
class DraftGrid:
    """Not locked. Time12 is a proposal, not a registered evaluation seed."""
    sources: tuple = SOURCES
    resets: int = 1
    times: tuple = (12,)

    def validate(self):
        require(type(self.resets) is int and self.resets > 0, 'invalid reset count')
        require(type(self.sources) is tuple and self.sources and
                len(set(self.sources)) == len(self.sources) and
                self.sources[0] == 'reference' and set(self.sources) <= set(SOURCES),
                'invalid source grid')
        require(len(self.sources) > 1, 'need controller sources')
        require(type(self.times) is tuple and self.times and
                len(set(self.times)) == len(self.times) and
                all(type(t) is int and 0 < t <= 12 for t in self.times),
                'invalid later times')
        return self


def budget(grid=DraftGrid()):
    """Exact planned inner step counts, no caching or stochastic retries assumed."""
    grid.validate()
    groups = 10 * grid.resets
    n_sources = len(grid.sources)
    n_controllers = n_sources - 1
    last = max(grid.times)
    source = 10 * 3 * 512
    target_train, target_val = 10 * 128, 10 * 32
    controller_generation = groups * n_controllers * last
    reference_generation = groups * last
    prefix_replay = groups * n_sources * 2 * 16 * sum(grid.times)
    realization = groups * n_sources * len(grid.times) * 2 * 16 * 16
    eval_imagined = groups * n_sources * len(grid.times) * 2 * 2 * 16 * 16
    generator_imagined = controller_generation * 16 * 16
    real = source + target_train + target_val + controller_generation + reference_generation + prefix_replay + realization
    return dict(source_collection=source, target_training=target_train,
                target_validation=target_val,
                controller_state_generation=controller_generation,
                reference_state_generation=reference_generation,
                reset_prefix_replay=prefix_replay, candidate_realization=realization,
                total_real=real, diagnostic_imagined=eval_imagined,
                controller_generation_imagined=generator_imagined,
                total_imagined=eval_imagined + generator_imagined,
                comparison_states=groups*n_sources*len(grid.times),
                within_standing_interaction_limit=real <= 100000)


def selection_gap(scores_mt, scores_sc, actual):
    """Known-number toy contract only; scores are inputs, never computed here."""
    mt, sc, values = vector(scores_mt, 16), vector(scores_sc, 16), vector(actual, 16)
    i_mt = max(range(16), key=mt.__getitem__)
    i_sc = max(range(16), key=sc.__getitem__)
    oracle = max(values)
    gap = values[i_mt] - values[i_sc]
    close(gap, (oracle-values[i_sc]) - (oracle-values[i_mt]))
    return gap


def paired_cell(multitask, scratch):
    """Both record-only arm views must refer to the exact same comparison."""
    for field in ('seed', 'reset_id', 'later_t', 'state_source', 'observation',
                  'state', 'prefix_actions', 'l0_id', 'redraw_id', 'libraries'):
        require(multitask[field] == scratch[field], f'arm pairing mismatch: {field}')
    require(multitask['state_source'] in SOURCES, 'unknown state source')
    vector(multitask['observation'], 2)
    vector(multitask['state'], 2)
    require(set(multitask['libraries']) == set(LIBRARIES), 'missing/extra paired library')
    for view in (multitask, scratch):
        require(set(view['scores']) == set(LIBRARIES), 'missing/extra paired score library')
    out = {}
    for lib in LIBRARIES:
        data = multitask['libraries'][lib]
        seq = data['sequences']
        require(type(seq) is list and len(seq) == 16, 'invalid candidate matrix')
        for row in seq:
            require(type(row) is list and len(row) == 16 and
                    all(integer(a) in (0, 1, 2) for a in row), 'invalid candidate actions')
        out[lib] = selection_gap(multitask['scores'][lib], scratch['scores'][lib], data['realized'])
    return out['l0']-out['redraw']


def primary(rows, grid=DraftGrid()):
    """One prospective source-mixture x library x model contrast per seed.

    Rows are synthetic records in tests; no H17 observations exist. Equal
    controller weights are specified before results, never selected for sign.
    """
    grid.validate()
    expected = {(s, k, t, p) for s in range(10) for k in range(grid.resets)
                for t in grid.times for p in grid.sources}
    indexed = {}
    for row in rows:
        key = (integer(row['seed']), integer(row['reset_id']),
               integer(row['later_t']), row['state_source'])
        require(key in expected and key not in indexed, 'duplicate/unplanned grid cell')
        values = row['selected_returns']
        require(set(values) == set(LIBRARIES), 'missing/extra library')
        for lib in LIBRARIES:
            require(set(values[lib]) == set(ARMS), 'missing/extra model arm')
        d = ((number(values['l0']['multitask'])-number(values['l0']['scratch']))
             -(number(values['redraw']['multitask'])-number(values['redraw']['scratch'])))
        indexed[key] = d
    require(set(indexed) == expected, 'incomplete source/seed/reset/time grid')
    controllers = grid.sources[1:]
    per_seed = []
    for s in range(10):
        values = []
        for k in range(grid.resets):
            for t in grid.times:
                ref = indexed[s, k, t, 'reference']
                values.append(mean(indexed[s, k, t, p] for p in controllers)-ref)
        per_seed.append(mean(values))
    return interval(per_seed)


def snapshot_contract(record):
    """Validate supplied mock replay records; performs no reset or step.

    Proposed snapshots retain H16's float32 obs/raw-state convention. Native
    state identity requires its own later validation; do not imply it here.
    """
    t = integer(record['later_t'])
    integer(record['state_reset_seed'])
    require(t > 0 and integer(record['elapsed_steps']) == t, 'elapsed-step mismatch')
    for flag in ('terminated', 'truncated'):
        require(record[flag] is False, 'ended/incomplete trajectory')
    require(record['obs_dtype'] == record['state_dtype'] == 'float32', 'snapshot dtype drift')
    for key in ('reset_obs', 'reset_state', 'observation', 'state'):
        vector(record[key], 2)
    actions = record['prefix_actions']
    require(type(actions) is list and len(actions) == t and
            all(integer(a) in (0, 1, 2) for a in actions), 'prefix action mismatch')
    vector(record['prefix_rewards'], t)


def replay_contract(reference, replayed):
    """Bit-preserving comparison at declared float32 representation only."""
    snapshot_contract(reference)
    snapshot_contract(replayed)
    require(set(reference) == set(replayed), 'replay record schema mismatch')
    for field, value in reference.items():
        other = replayed[field]
        if field in ('reset_obs', 'reset_state', 'observation', 'state', 'prefix_rewards'):
            # Reward values retain double precision. H16 state identity is f32.
            fmt = '>d' if field == 'prefix_rewards' else '>f'
            require([struct.pack(fmt, number(v)) for v in value] ==
                    [struct.pack(fmt, number(v)) for v in other], f'replay identity mismatch: {field}')
        else:
            require(value == other, f'replay identity mismatch: {field}')
    return True
