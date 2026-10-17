"""Recorded-data H16 analysis; standard library only, no world-package import.

The world package eagerly imports neural/planning code. Keep this audit outside
it so importing or executing the audit cannot start inference or simulation.
All intervals except the reconstructed registered primary are exploratory.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess

BASE = '9474ec63bafbe03adb2b9557c03edfdca650a385'
AUTHORIZATION = '834bb633e7977ea6922a8ad9f1adcc091eccae58'
RAW = 'artifacts/h16_same_state_library.json'
ALLOCATION = 'configs/mcc_same_state_library_allocation.json'
LEDGER = 'artifacts/research_session_h16_same_state_library_usage.json'
HASHES = {
    RAW: '96be8b401a06f48e8eab190058f58a82f6dc1f2eebc6c2fe46f31da1e4bc4625',
    'configs/mcc_same_state_library.yaml': 'e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c',
    'docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md': 'f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7',
    ALLOCATION: '079b9379b1c87536086c50a1cf5f5204f1fcffbb6c2606fa988a6d7290f077ab',
    LEDGER: 'ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117',
}
SEEDS = tuple(range(10))
STATES = tuple(range(4))
TIMES = (8, 12)
LIBRARIES = ('l0', 'redraw')
ARMS = ('multitask', 'scratch')
LABEL = 'h16_same_state_library_effect_not_established'
ATOL = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'nonfinite/non-numeric value')
    return value


def integer(value):
    require(type(value) is int, 'expected integer ID/action')
    return value


def close(left, right):
    require(abs(number(left) - number(right)) <= ATOL, 'saved/reconstructed value mismatch')


def mean(values):
    values = list(values)
    require(bool(values), 'empty metric')
    return math.fsum(number(v) for v in values) / len(values)


def interval(values):
    """Match locked H16 df9 critical value 2.262, not a normal interval."""
    values = list(values)
    require(len(values) == 10, 'interval requires ten independent seed means')
    mu = mean(values)
    se = statistics.stdev(values) / math.sqrt(10)
    return dict(mean=mu, lo=mu - 2.262 * se, hi=mu + 2.262 * se,
                se=se, n=10, df=9, interval='student_t_95', per_seed=values)


def ranks(values):
    """Average ranks for exact ties; unlike the legacy ordinal argsort helper."""
    values = [number(v) for v in values]
    out = [0.0] * len(values)
    order = sorted(range(len(values)), key=values.__getitem__)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for i in order[start:end]:
            out[i] = (start + end - 1) / 2
        start = end
    return out


def spearman(left, right):
    require(len(left) == len(right) and len(left) > 1, 'unaligned ranking vectors')
    a, b = ranks(left), ranks(right)
    a = [x - mean(a) for x in a]
    b = [x - mean(b) for x in b]
    den = math.sqrt(math.fsum(x*x for x in a) * math.fsum(x*x for x in b))
    require(den > 0, 'undefined constant-vector Spearman; do not silently drop cell')
    return math.fsum(x*y for x, y in zip(a, b)) / den


def fingerprint(sequences):
    # Archived NumPy int64 native-endian bytes; execution used little endian.
    return hashlib.sha256(struct.pack('<256q', *(a for row in sequences for a in row))).hexdigest()


def vector(values, length):
    require(type(values) is list and len(values) == length, 'vector shape mismatch')
    return [number(v) for v in values]


def library_metrics(lib):
    """Reconstruct from score/return vectors, then verify redundant saved fields."""
    seq = lib['sequences']
    require(type(seq) is list and len(seq) == 16, 'candidate shape mismatch')
    for row in seq:
        require(type(row) is list and len(row) == 16, 'candidate shape mismatch')
        require(all(integer(a) in (0, 1, 2) for a in row), 'invalid action')
    require(fingerprint(seq) == lib['library_fingerprint'], 'candidate fingerprint mismatch')
    values = vector(lib['realized'], 16)
    traces = lib['reward_traces']
    require(type(traces) is list and len(traces) == 16, 'reward trace shape mismatch')
    for value, trace in zip(values, traces):
        close(value, math.fsum(vector(trace, 16)))
    oracle = max(values)
    close(oracle, lib['oracle'])
    for key in ('predicted_scores', 'selected', 'selected_return', 'regret'):
        require(set(lib[key]) == set(ARMS), 'missing/extra arm')
    out = dict(oracle=oracle, sequence_diversity=len({tuple(row) for row in seq}),
               first_action_diversity=len({row[0] for row in seq}),
               actual_ties=16-len(set(values)), arms={})
    for arm in ARMS:
        scores = vector(lib['predicted_scores'][arm], 16)
        index = max(range(16), key=scores.__getitem__)  # first maximum, as NumPy argmax
        action = seq[index][0]
        require(integer(lib['selected'][arm]['index']) == index, 'selected index mismatch')
        require(integer(lib['selected'][arm]['action']) == action, 'selected action mismatch')
        selected = values[index]
        regret = oracle - selected
        close(selected, lib['selected_return'][arm])
        close(regret, lib['regret'][arm])
        sorted_scores = sorted(scores, reverse=True)
        out['arms'][arm] = dict(
            selected_return=selected, regret=regret, spearman=spearman(scores, values),
            top1=float(selected == oracle),
            first_action_regret=oracle-max(v for row, v in zip(seq, values) if row[0] == action),
            score_margin=sorted_scores[0]-sorted_scores[1],
            score_range=max(scores)-min(scores), score_ties=16-len(set(scores)),
            selected_index=index, selected_action=action,
        )
    mt, sc = (out['arms'][a] for a in ARMS)
    out['advantage'] = mt['selected_return'] - sc['selected_return']
    close(out['advantage'], sc['regret'] - mt['regret'])
    out['action_disagreement'] = float(mt['selected_action'] != sc['selected_action'])
    out['selection_disagreement'] = float(mt['selected_index'] != sc['selected_index'])
    return out


def state_metrics(row, seed):
    require(integer(row['seed']) == seed, 'nested seed mismatch')
    k, t = integer(row['state_index']), integer(row['later_t'])
    require(k in STATES and t in TIMES, 'unplanned nested state')
    require(integer(row['state_seed']) == 78100000 + 10*seed + k, 'reset seed mismatch')
    require(integer(row['prefix_seed']) == 78200000 + 10*seed + k, 'prefix seed mismatch')
    require(integer(row['elapsed_steps']) == t, 'elapsed steps mismatch')
    actions = row['prefix_actions']
    require(len(actions) == t and all(integer(a) in (0, 1, 2) for a in actions), 'prefix mismatch')
    vector(row['prefix_rewards'], t)
    for field in ('reset_obs', 'reset_state', 'later_obs', 'later_state'):
        vector(row[field], 2)
    require(set(row['libraries']) == set(LIBRARIES), 'missing/extra library')
    libs = {}
    for name in LIBRARIES:
        lib = row['libraries'][name]
        expected = 78300000 + 10*seed + k if name == 'l0' else 78600000 + 10000*seed + 100*k + t
        require(integer(lib['candidate_seed']) == expected, 'candidate seed mismatch')
        libs[name] = library_metrics(lib)
        for arm, short in (('multitask', 'mt'), ('scratch', 'sc')):
            close(libs[name]['arms'][arm]['selected_return'], row[f's_{short}_{name}'])
    opportunity = libs['l0']['oracle'] - libs['redraw']['oracle']
    metrics = dict(primary=libs['l0']['advantage'] - libs['redraw']['advantage'],
                   opportunity=opportunity)
    for name, lib in libs.items():
        for key in ('oracle', 'advantage', 'sequence_diversity', 'first_action_diversity',
                    'action_disagreement', 'selection_disagreement', 'actual_ties'):
            metrics[f'{name}.{key}'] = lib[key]
        for arm in ARMS:
            for key, value in lib['arms'][arm].items():
                metrics[f'{name}.{arm}.{key}'] = value
    for arm in ARMS:
        gain = libs['l0']['arms'][arm]['selected_return'] - libs['redraw']['arms'][arm]['selected_return']
        regret_gain = libs['redraw']['arms'][arm]['regret'] - libs['l0']['arms'][arm]['regret']
        close(gain, opportunity + regret_gain)
        metrics[f'{arm}.l0_minus_redraw_return'] = gain
        metrics[f'{arm}.redraw_minus_l0_regret'] = regret_gain
    return dict(seed=seed, state_index=k, later_t=t, metrics=metrics)


def reconstruct(payload):
    require(payload['complete'] is True, 'incomplete artifact')
    cells = payload['cells']
    require(type(cells) is list and len(cells) == 10, 'missing/duplicate seed grid')
    seeds = [integer(cell['seed']) for cell in cells]
    require(set(seeds) == set(SEEDS) and len(set(seeds)) == 10, 'missing/duplicate seed grid')
    rows = []
    for cell in sorted(cells, key=lambda c: c['seed']):
        seed = cell['seed']
        states = cell['later_states']
        require(type(states) is list and len(states) == 8, 'missing/duplicate nested-state grid')
        keys = [(integer(r['state_index']), integer(r['later_t'])) for r in states]
        require(set(keys) == {(k, t) for k in STATES for t in TIMES}, 'missing/duplicate nested-state grid')
        lookup = {(r['state_index'], r['later_t']): r for r in states}
        for k in STATES:
            a, b = (lookup[k, t] for t in TIMES)
            for field in ('reset_obs', 'reset_state', 'state_seed', 'prefix_seed'):
                require(a[field] == b[field], 'reset alignment mismatch')
            for field in ('prefix_actions', 'prefix_rewards'):
                require(a[field] == b[field][:8], 'prefix alignment mismatch')
            for field in ('candidate_seed', 'library_fingerprint', 'sequences'):
                require(a['libraries']['l0'][field] == b['libraries']['l0'][field], 'L0 alignment mismatch')
        rows.extend(state_metrics(r, seed) for r in sorted(states, key=lambda r: (r['state_index'], r['later_t'])))

    def summarize(subset):
        return {key: interval([mean(r['metrics'][key] for r in subset if r['seed'] == s)
                               for s in SEEDS]) for key in rows[0]['metrics']}

    summary = summarize(rows)
    primary = summary['primary']
    # Independent raw reconstruction must agree with the frozen registered result.
    official = payload['groups']['primary']
    for actual, saved in zip(primary['per_seed'], vector(official['per_seed'], 10)):
        close(actual, saved)
    for key in ('mean', 'lo', 'hi', 'se'):
        close(primary[key], official['interval'][key])
    require(official['interval']['n'] == 10 and official['interval']['df'] == 9, 'registered replication mismatch')
    label = ('h16_l0_helps_multitask_relative_same_state' if primary['lo'] > 0 else
             'h16_redraw_helps_multitask_relative_same_state' if primary['hi'] < 0 else LABEL)
    require(payload['label'] == label == LABEL, 'registered label mismatch')
    phases = {str(t): summarize([r for r in rows if r['later_t'] == t]) for t in TIMES}
    phase_difference = interval([b-a for a, b in zip(phases['8']['primary']['per_seed'], phases['12']['primary']['per_seed'])])
    reference = {str(k): summarize([r for r in rows if r['state_index'] == k])['primary'] for k in STATES}
    loo_seeds = {str(s): mean(v for i, v in enumerate(primary['per_seed']) if i != s) for s in SEEDS}
    loo_states = {str(k): summarize([r for r in rows if r['state_index'] != k])['primary'] for k in STATES}
    return dict(complete=True, registered_label=label, primary=primary,
                positive_seeds=sum(v > 0 for v in primary['per_seed']),
                exploratory_summary=summary, exploratory_phases=phases,
                exploratory_phase12_minus8=phase_difference,
                exploratory_reference_index=reference, leave_one_seed_out_means=loo_seeds,
                exploratory_leave_one_reference_index_out=loo_states, raw_diagnostics=rows,
                grid=dict(seeds=10, reference_prefixes=40, nested_states=80,
                          libraries=160, arm_library_cells=320, recorded_candidate_trajectories=2560))


def load_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, f'duplicate JSON key: {key}')
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def verify_provenance(root):
    root = Path(root)
    for file, digest in HASHES.items():
        require(hashlib.sha256((root/file).read_bytes()).hexdigest() == digest, f'hash mismatch: {file}')
    payload = load_json(root/RAW)
    for file, digest in {**payload['parents'], **payload['code_hashes']}.items():
        require(hashlib.sha256((root/file).read_bytes()).hexdigest() == digest, f'parent/code hash mismatch: {file}')
    config, protocol = list(HASHES)[1:3]
    require(payload['config_sha256'] == HASHES[config] and payload['protocol_sha256'] == HASHES[protocol], 'raw lock mismatch')
    require(payload['implementation_sha'] == AUTHORIZATION and payload['source_dirty'] is False, 'execution revision mismatch')
    git = lambda *args: subprocess.check_output(['git', *args], cwd=root)
    git('merge-base', '--is-ancestor', AUTHORIZATION, BASE)
    git('merge-base', '--is-ancestor', BASE, 'HEAD')
    historical = git('show', f'{AUTHORIZATION}:{ALLOCATION}')
    require(hashlib.sha256(historical).hexdigest() == payload['allocation_sha256'], 'pre-run allocation hash mismatch')
    allocation, ledger = load_json(root/ALLOCATION), load_json(root/LEDGER)
    require(allocation['authorized'] is True and allocation['consumed'] is True and allocation['closed'] is True and type(allocation['runs']) is int and allocation['runs'] == 1, 'allocation not consumed/closed')
    require(ledger['consumed'] is True and ledger['status'] == 'complete' and ledger['raw_sha256'] == HASHES[RAW], 'usage mismatch')
    require(ledger['ledger']['consumed_total_s'] == 305.842 and ledger['remaining_session_allowance_s'] == 3294.158, 'session ledger changed')
    for key, value in dict(new_environment_interactions=84000, imagined_transitions=81920).items():
        require(payload[key] == value, 'historical budget mismatch')
    return dict(base_sha=BASE, authorization_sha=AUTHORIZATION, input_hashes=HASHES,
                pre_run_allocation_sha256=payload['allocation_sha256'],
                verified_parent_and_code_hashes={**payload['parents'], **payload['code_hashes']},
                source_revision=git('rev-parse', 'HEAD').decode().strip(),
                source_tree_dirty=bool(git('status', '--porcelain').strip()),
                analysis_module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                ledger_used_s=305.842, ledger_remaining_s=3294.158)


def analyze(root):
    provenance = verify_provenance(root)
    result = reconstruct(load_json(Path(root)/RAW))
    result.update(provenance=provenance, scope='exploratory_recorded_data_only',
                  new_environment_steps=0, new_imagined_transitions=0,
                  new_model_inference_calls=0, training_updates=0)
    return result
