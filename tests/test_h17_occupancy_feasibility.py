"""Static arithmetic/synthetic-record checks. No simulator or model imports."""
import copy
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from nexus import h17_occupancy_feasibility as m
from nexus.h16_selection_mechanism_diagnosis import verify_provenance

ROOT = Path(__file__).resolve().parents[1]


def rows(grid=m.DraftGrid()):
    out = []
    for s in range(10):
        for k in range(grid.resets):
            for t in grid.times:
                for i, source in enumerate(grid.sources):
                    # The expected interaction is mean(1,2,3,4)=2.5;
                    # state/time effects cancel before the seed average.
                    d = i + s/100 + k/10 + t/1000
                    out.append(dict(seed=s, reset_id=k, later_t=t, state_source=source,
                                    selected_returns=dict(l0=dict(multitask=d, scratch=0),
                                                          redraw=dict(multitask=0, scratch=0))))
    return out


def test_parent_integrity_and_unchanged_closed_ledger():
    p = verify_provenance(ROOT)
    assert (p['ledger_used_s'], p['ledger_remaining_s']) == (305.842, 3294.158)


def test_latest_diagnosis_and_master_context_unchanged():
    expected = {
        'artifacts/h16_selection_mechanism_diagnosis.json': '3d5782da065e78146fba4e798c3aba8ba392ba3ed8e5b2803fcb25b59f2ddb2a',
        'docs/NEXUS_H16_SELECTION_MECHANISM_DIAGNOSIS.md': 'b84630658f5c01f396475cd89d440430a034100b2d0247b554ff62d43768839b',
        'docs/MASTER_CONTEXT.md': 'e4556b11d6e09c1102fcdc5450e4eb6b7ed03c5852e1ac869fb19e35566c41d8',
    }
    for file, digest in expected.items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == digest


def test_exact_candidate_resource_counts():
    b = m.budget()
    assert b == dict(source_collection=15360, target_training=1280, target_validation=320,
                     controller_state_generation=480, reference_state_generation=120,
                     reset_prefix_replay=19200, candidate_realization=25600,
                     total_real=62360, diagnostic_imagined=51200,
                     controller_generation_imagined=122880, total_imagined=174080,
                     comparison_states=50, within_standing_interaction_limit=True)
    assert m.budget(m.DraftGrid(times=(8, 12)))['total_real'] == 100760
    assert m.budget(m.DraftGrid(times=(8, 12)))['total_imagined'] == 225280
    assert not m.budget(m.DraftGrid(times=(8, 12)))['within_standing_interaction_limit']
    assert m.budget(m.DraftGrid(resets=2))['total_real'] == 107760
    assert m.budget(m.DraftGrid(sources=m.SOURCES[:3], times=(8, 12)))['total_real'] == 67240
    assert m.budget(m.DraftGrid(times=(8,)))['total_real'] == 55760


@pytest.mark.parametrize('grid', [m.DraftGrid(resets=0), m.DraftGrid(resets=True),
                                  m.DraftGrid(times=(12,12)), m.DraftGrid(times=(True,)),
                                  m.DraftGrid(sources=('reference','reference'))])
def test_invalid_design_dimensions_fail(grid):
    with pytest.raises(ValueError):
        m.budget(grid)


def test_primary_factorial_algebra_and_nesting():
    grid = m.DraftGrid(resets=2, times=(8,12))
    out = m.primary(rows(grid), grid)
    assert out['mean'] == pytest.approx(2.5)
    assert out['lo'] == pytest.approx(2.5)
    assert out['n'] == 10 and out['df'] == 9
    assert out['per_seed'] == pytest.approx([2.5]*10)
    assert m.primary(list(reversed(rows(grid))), grid) == out


def test_fixed_controller_weights_not_state_pooling():
    data = rows()
    for r in data:
        if r['state_source'] == 'multitask_fixed':
            r['selected_returns']['l0']['multitask'] += 4
    assert m.primary(data)['mean'] == pytest.approx(3.5)


@pytest.mark.parametrize('mutate', ['seed', 'source', 'time', 'arm', 'library', 'duplicate'])
def test_complete_expected_grid_fail_closed(mutate):
    data = rows()
    if mutate == 'seed':
        data = [r for r in data if r['seed'] != 9]
    elif mutate == 'source':
        data = [r for r in data if r['state_source'] != 'scratch_redraw']
    elif mutate == 'time':
        data[0]['later_t'] = 8
    elif mutate == 'arm':
        del data[0]['selected_returns']['l0']['scratch']
    elif mutate == 'library':
        del data[0]['selected_returns']['redraw']
    else:
        data.append(copy.deepcopy(data[0]))
    with pytest.raises(ValueError):
        m.primary(data)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, '1'])
def test_nonfinite_or_non_numeric_is_invalid_not_inconclusive(bad):
    data = rows()
    data[0]['selected_returns']['l0']['multitask'] = bad
    with pytest.raises(ValueError):
        m.primary(data)


def arm_views():
    data = dict(seed=0, reset_id=0, later_t=12, state_source='reference',
                observation=[0.,0.], state=[0.,0.], prefix_actions=[0]*12,
                l0_id='toy_l0', redraw_id='toy_redraw', libraries={})
    for lib in ('l0','redraw'):
        data['libraries'][lib] = dict(sequences=[[i%3]*16 for i in range(16)],
                                      realized=list(range(16)))
    mt, sc = copy.deepcopy(data), copy.deepcopy(data)
    mt['scores'] = dict(l0=list(range(16)), redraw=list(reversed(range(16))))
    sc['scores'] = dict(l0=list(reversed(range(16))), redraw=list(range(16)))
    return mt, sc


def test_same_state_pairing_primary_and_oracle_cancellation():
    mt, sc = arm_views()
    assert m.paired_cell(mt,sc) == 30
    for arm in (mt,sc):
        for lib in arm['libraries'].values():
            lib['realized'] = [v+100 for v in lib['realized']]
    assert m.paired_cell(mt,sc) == 30


@pytest.mark.parametrize('field', ['observation','state','state_source','l0_id','libraries'])
def test_wrong_comparison_pair_rejected(field):
    mt, sc = arm_views()
    sc[field] = 'unpaired'
    with pytest.raises(ValueError, match='pairing'):
        m.paired_cell(mt,sc)


def snapshot():
    return dict(state_reset_seed=0, later_t=12, elapsed_steps=12, terminated=False, truncated=False,
                obs_dtype='float32', state_dtype='float32',
                reset_obs=[0.,0.], reset_state=[0.,0.], observation=[1.,2.], state=[1.,2.],
                prefix_actions=[0]*12, prefix_rewards=[-1.]*12)


def test_replay_contract_is_a_record_check_not_simulation():
    ref = snapshot()
    assert m.replay_contract(ref,copy.deepcopy(ref))


@pytest.mark.parametrize('field,value', [('elapsed_steps',11),('terminated',True),
                                       ('state_reset_seed',1),
                                       ('truncated',True),('state',[1.,3.]),
                                       ('prefix_actions',[0]*11),('prefix_rewards',[-2.]*12),
                                       ('state_dtype','float64')])
def test_replay_contract_fails_closed(field,value):
    ref, replayed = snapshot(), snapshot()
    replayed[field] = value
    with pytest.raises(ValueError):
        m.replay_contract(ref,replayed)


def test_feasibility_import_and_mock_contracts_without_scientific_stack():
    program = '''
import importlib.abc, sys
sys.path.insert(0,sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('numpy','torch','gym','gymnasium') or fullname.startswith(('nexus.world','nexus.tasks','nexus.rl')):
   raise AssertionError('forbidden import: '+fullname)
sys.meta_path.insert(0,Block())
from nexus import h17_occupancy_feasibility as m
assert m.budget()['total_real'] == 62360
assert not hasattr(m,'execute')
assert not hasattr(m,'make_env')
'''
    subprocess.run([sys.executable,'-I','-B','-c',program,str(ROOT/'src')],check=True)
