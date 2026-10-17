"""Source-only record, file-byte and schema tests; never neural execution."""
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from nexus import h17_protocol_readiness as m

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    return dict(state_reset_seed=0, state_source='reference', later_t=12,
                elapsed_steps=12, obs_dtype='float32', state_dtype='float64',
                terminated=False, truncated=False, reset_obs=[0.,0.],
                reset_state=[0.,0.], observation=[1.,2.], state=[1.,2.],
                prefix_actions=[0]*12, prefix_rewards=[-1.]*12)


def test_native_state_drift_hidden_by_float32_is_rejected():
    a, b = snapshot(), snapshot()
    assert m.validate_native_replay(a, b)
    b['state'][0] = math.nextafter(1., 2.)
    assert struct.pack('f', a['state'][0]) == struct.pack('f', b['state'][0])
    with pytest.raises(ValueError, match='native replay mismatch: state'):
        m.validate_native_replay(a, b)


@pytest.mark.parametrize('key,value', [('state_dtype','float32'), ('terminated',True),
                                      ('elapsed_steps',13), ('state_reset_seed',1),
                                      ('state_source','scratch_fixed'),
                                      ('prefix_rewards',[-2.]*12),
                                      ('prefix_actions',[1]*12)])
def test_replay_fail_closed(key, value):
    a, b = snapshot(), snapshot()
    b[key] = value
    with pytest.raises(ValueError):
        m.validate_native_replay(a, b)


def toy_map():
    # Synthetic integers for unit tests; never written as experimental seeds.
    return [dict(key=list(k), value=i) for i, k in enumerate(m.seed_keys())]


def test_symbolic_seed_couplings_and_namespaces():
    keys = m.seed_keys()
    assert len(keys) == len(set(keys)) == 480
    for seed in range(10):
        assert ('l0', seed) in keys
        assert ('reset', seed) in keys
        assert sum(k[0] == 'generator_redraw' and k[1] == seed for k in keys) == 11
    assert len(m.validate_seed_mapping(toy_map(), set())) == 480


@pytest.mark.parametrize('case', ['missing','duplicate_key','alias','closed','bool','extra'])
def test_seed_stream_rejections(case):
    rows = toy_map()
    blocked = set()
    if case == 'missing':
        rows.pop()
    elif case == 'duplicate_key':
        rows[1]['key'] = rows[0]['key']
    elif case == 'alias':
        rows[1]['value'] = rows[0]['value']
    elif case == 'closed':
        blocked.add(rows[0]['value'])
    elif case == 'bool':
        rows[0]['value'] = True
    else:
        rows.append(dict(key=['unregistered',0], value=9999))
    with pytest.raises(ValueError):
        m.validate_seed_mapping(rows, blocked)


def file_manifest(tmp_path):
    entries = []
    for seed in range(10):
        for arm in ('multitask','scratch'):
            name = f'synthetic_{seed}_{arm}.bin'
            data = f'untrained toy bytes {seed} {arm}'.encode()
            (tmp_path/name).write_bytes(data)
            entries.append(dict(seed=seed, arm=arm, path=name,
                                sha256=hashlib.sha256(data).hexdigest(),
                                architecture=dict(obs_dim=2,n_actions=3,hidden=[64,64],arch='mlp',kind='residual'),
                                normalization=dict(mean=[0.,0.],var=[1.,1.],count=1.)))
    return entries


def test_hash_only_manifest_checks_twenty_distinct_files(tmp_path):
    assert m.validate_checkpoint_manifest(file_manifest(tmp_path), tmp_path)


@pytest.mark.parametrize('case', ['missing_file','hash','missing_seed','duplicate',
                                 'path_escape','reuse','architecture','normalization'])
def test_manifest_audit_never_skips_required_file(tmp_path, case):
    entries = file_manifest(tmp_path)
    if case == 'missing_file':
        entries[0]['path'] = 'missing.bin'
    elif case == 'hash':
        entries[0]['sha256'] = '0'*64
    elif case == 'missing_seed':
        entries = [r for r in entries if r['seed'] != 9]
    elif case == 'duplicate':
        entries[1] = copy.deepcopy(entries[0])
    elif case == 'path_escape':
        entries[0]['path'] = '../outside.bin'
    elif case == 'reuse':
        entries[1]['path'] = entries[0]['path']
    elif case == 'architecture':
        entries[0]['architecture']['hidden'] = [48,48]
    else:
        entries[0]['normalization']['mean'][0] = float('nan')
    with pytest.raises(ValueError):
        m.validate_checkpoint_manifest(entries, tmp_path)


def test_unresolved_draft_is_not_a_lock_or_authorization():
    cfg = m.load_json(ROOT/m.CONFIG)
    assert m.validate_draft(cfg)['total_real'] == 62360
    out = m.review(ROOT)
    assert out['status'] == 'not_lock_ready'
    assert out['locked'] is out['authorized'] is False
    assert out['ledger_used_s'] == 305.842
    assert out['ledger_remaining_s'] == 3294.158
    assert len(out['outstanding']) == 5


@pytest.mark.parametrize('key,value', [('target_physics',[1.,2.,3.]),
                                      ('status','locked'), ('later_times',[12.]),
                                      ('n_training_pairs',True), ('proposed_real_steps',100000),
                                      ('seed_mapping',[])])
def test_draft_cannot_be_silently_registered_or_retuned(key,value):
    cfg = m.load_json(ROOT/m.CONFIG)
    cfg[key] = value
    with pytest.raises(ValueError):
        m.validate_draft(cfg)


def test_review_does_not_import_scientific_stack_or_write_inputs():
    program = '''
import importlib.abc, pathlib, sys, hashlib
sys.path.insert(0, sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('numpy','torch','gym','gymnasium') or fullname.startswith(('nexus.world','nexus.tasks','nexus.rl')):
   raise AssertionError('forbidden scientific import: '+fullname)
sys.meta_path.insert(0, Block())
from nexus.h17_protocol_readiness import review, CONFIG
root=pathlib.Path(sys.argv[2]); before=(root/CONFIG).read_bytes()
out=review(root)
assert (root/CONFIG).read_bytes()==before
assert out['new_environment_steps']==out['new_imagined_transitions']==out['model_inference_calls']==out['training_updates']==0
assert out['status']=='not_lock_ready'
'''
    subprocess.run([sys.executable,'-I','-B','-c',program,str(ROOT/'src'),str(ROOT)],check=True)
