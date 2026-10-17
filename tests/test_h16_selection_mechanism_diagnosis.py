"""Only stored numbers and synthetic arrays; no environments or model calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nexus import h16_selection_mechanism_diagnosis as m

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def raw():
    return m.load_json(ROOT / m.RAW)


def test_provenance_and_consumed_allocation():
    out = m.verify_provenance(ROOT)
    assert out['base_sha'] == m.BASE
    assert out['ledger_used_s'] == 305.842
    assert out['ledger_remaining_s'] == 3294.158
    assert out['pre_run_allocation_sha256'] != out['input_hashes'][m.ALLOCATION]


def test_registered_primary_reconstructed_from_candidates(raw):
    out = m.reconstruct(raw)
    assert out['primary']['mean'] == pytest.approx(0.022889688336460212, abs=1e-14)
    assert out['primary']['lo'] == pytest.approx(-0.014210807366461443, abs=1e-14)
    assert out['primary']['hi'] == pytest.approx(0.05999018403938187, abs=1e-14)
    assert out['primary']['n'] == 10 and out['primary']['df'] == 9
    assert out['positive_seeds'] == 6
    assert out['registered_label'] == m.LABEL
    assert out['grid']['nested_states'] == 80


def test_nested_states_not_independent_replications(raw):
    out = m.reconstruct(raw)
    for seed in m.SEEDS:
        eight = [r['metrics']['primary'] for r in out['raw_diagnostics'] if r['seed'] == seed]
        assert len(eight) == 8
        assert m.mean(eight) == out['primary']['per_seed'][seed]
    for phase in ('8', '12'):
        assert out['exploratory_phases'][phase]['primary']['n'] == 10
    with pytest.raises(ValueError, match='ten independent'):
        m.interval([r['metrics']['primary'] for r in out['raw_diagnostics']])


def test_order_invariance_of_nested_grid(raw):
    expected = m.reconstruct(raw)
    raw['cells'].reverse()
    for cell in raw['cells']:
        cell['later_states'].reverse()
    assert m.reconstruct(raw) == expected


def toy_library():
    seq = [[i % 3] + [0]*14 + [i % 3] for i in range(16)]
    values = list(range(16))
    scores_mt = [0]*16
    scores_mt[13] = 2
    scores_sc = [0]*16
    scores_sc[11] = 2
    return dict(sequences=seq, library_fingerprint=m.fingerprint(seq),
                realized=values, reward_traces=[[v]+[0]*15 for v in values],
                oracle=15, predicted_scores=dict(multitask=scores_mt, scratch=scores_sc),
                selected=dict(multitask=dict(index=13, action=1), scratch=dict(index=11, action=2)),
                selected_return=dict(multitask=13, scratch=11),
                regret=dict(multitask=2, scratch=4))


def test_selection_regret_oracle_cancellation_and_first_action():
    out = m.library_metrics(toy_library())
    assert out['oracle'] == 15
    assert out['advantage'] == 2
    assert out['arms']['multitask']['regret'] == 2
    # Best saved sequence starting with action1 is index13, action2 is index14.
    assert out['arms']['multitask']['first_action_regret'] == 2
    assert out['arms']['scratch']['first_action_regret'] == 1
    shifted = toy_library()
    shifted['realized'] = [v+100 for v in shifted['realized']]
    shifted['reward_traces'] = [[v]+[0]*15 for v in shifted['realized']]
    shifted['oracle'] += 100
    shifted['selected_return'] = {a: v+100 for a, v in shifted['selected_return'].items()}
    assert m.library_metrics(shifted)['advantage'] == out['advantage']


def test_first_maximum_tie_handling():
    lib = toy_library()
    lib['predicted_scores']['multitask'][14] = 2
    assert m.library_metrics(lib)['arms']['multitask']['selected_index'] == 13
    assert m.ranks([4, 4, 9]) == [0.5, 0.5, 2]
    assert m.spearman([4, 4, 9], [1, 1, 3]) == pytest.approx(1)
    with pytest.raises(ValueError, match='undefined'):
        m.spearman([1, 1, 1], [1, 2, 3])


@pytest.mark.parametrize('mutation', ['seed', 'duplicate_seed', 'state', 'duplicate_state',
                                      'phase', 'library', 'arm', 'extra_seed'])
def test_missing_duplicate_grid_rejected(raw, mutation):
    cell = raw['cells'][0]
    row = cell['later_states'][0]
    if mutation == 'seed':
        raw['cells'].pop()
    elif mutation == 'duplicate_seed':
        raw['cells'][1] = copy.deepcopy(cell)
    elif mutation == 'extra_seed':
        raw['cells'].append(copy.deepcopy(cell))
    elif mutation == 'state':
        cell['later_states'].pop()
    elif mutation == 'duplicate_state':
        cell['later_states'][1] = copy.deepcopy(row)
    elif mutation == 'phase':
        cell['later_states'] = [r for r in cell['later_states'] if r['later_t'] == 8]
    elif mutation == 'library':
        del row['libraries']['redraw']
    elif mutation == 'arm':
        del row['libraries']['l0']['predicted_scores']['scratch']
    with pytest.raises(ValueError):
        m.reconstruct(raw)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True, '1.0'])
def test_nonfinite_and_wrong_numeric_types_rejected(raw, bad):
    raw['cells'][0]['later_states'][0]['libraries']['l0']['predicted_scores']['scratch'][0] = bad
    with pytest.raises(ValueError):
        m.reconstruct(raw)


@pytest.mark.parametrize('mutation', ['candidate', 'scores', 'returns', 'trace', 'scalar', 'prefix', 'fingerprint'])
def test_candidate_alignment_and_saved_value_drift_rejected(raw, mutation):
    row = raw['cells'][0]['later_states'][0]
    lib = row['libraries']['redraw']
    if mutation == 'candidate':
        lib['sequences'][0][0] = (lib['sequences'][0][0]+1) % 3
    elif mutation == 'scores':
        lib['predicted_scores']['multitask'] = [100.0] + [-100.0]*15
        # Guaranteed different from saved selection, even if saved index is0.
        idx = lib['selected']['multitask']['index']
        lib['predicted_scores']['multitask'][idx] = -200.0
    elif mutation == 'returns':
        lib['realized'].reverse()
    elif mutation == 'trace':
        lib['reward_traces'][0][0] += 1
    elif mutation == 'scalar':
        row['s_mt_redraw'] += 1
    elif mutation == 'prefix':
        row['prefix_actions'][0] = (row['prefix_actions'][0]+1) % 3
    elif mutation == 'fingerprint':
        lib['library_fingerprint'] = '0'*64
    with pytest.raises(ValueError):
        m.reconstruct(raw)


def test_missing_metric_is_not_silently_dropped(raw):
    del raw['cells'][0]['later_states'][0]['libraries']['redraw']['realized']
    with pytest.raises(KeyError):
        m.reconstruct(raw)


def test_duplicate_json_keys_rejected(tmp_path):
    file = tmp_path/'duplicate.json'
    file.write_text('{"seed": 1, "seed": 2}')
    with pytest.raises(ValueError, match='duplicate JSON'):
        m.load_json(file)


def test_artifact_hash_drift_rejected(tmp_path):
    (tmp_path/'artifacts').mkdir()
    (tmp_path/m.RAW).write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        m.verify_provenance(tmp_path)


def test_full_analysis_blocks_neural_simulator_training_imports():
    # A clean subprocess tests import AND complete analysis, not just AST flags.
    program = '''
import importlib.abc, json, sys
sys.path.insert(0, sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'torch', 'gym', 'gymnasium') or fullname.startswith(('nexus.world', 'nexus.tasks', 'nexus.rl')):
            raise AssertionError('forbidden import: '+fullname)
sys.meta_path.insert(0, Block())
from nexus.h16_selection_mechanism_diagnosis import analyze
out = analyze(sys.argv[2])
assert out['new_environment_steps'] == out['new_imagined_transitions'] == out['training_updates'] == out['new_model_inference_calls'] == 0
print(out['registered_label'])
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(ROOT/'src'), str(ROOT)],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == m.LABEL
