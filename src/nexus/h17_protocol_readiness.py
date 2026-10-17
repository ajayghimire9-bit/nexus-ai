"""Source-only contracts for a future H17 lock; no execution entry point.

No concrete experimental seeds/physics are selected. Binary audits hash bytes
only, never deserialize checkpoints. Native replay checks consume records.
"""
import hashlib
from pathlib import Path
import struct

from nexus.h16_selection_mechanism_diagnosis import (
    ARMS, integer, load_json, number, require, vector, verify_provenance,
)
from nexus.h17_occupancy_feasibility import DraftGrid, SOURCES, budget

BASE = '5436893dc8a361f0894e848cd68fac23a921e98c'
CONFIG = 'configs/h17_occupancy_draft.json'
FEASIBILITY = 'docs/NEXUS_H17_OCCUPANCY_DEPENDENCE_FEASIBILITY.md'
FEASIBILITY_SHA = '22ecb63550edbe50281ba1834e987ac453e29b44b4f805468b97a9dfb2b00278'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if type(b) is dict:
        return set(a) == set(b) and all(strict_equal(a[k], b[k]) for k in b)
    if type(b) is list:
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def seed_keys():
    """Symbolic key schema only. Intentional reuse is represented by ONE key.

    Reset/L0/generator redraw exclude source/arm: all sources share reset/L0;
    both redraw generators share their stream. Scoring/replay adds no draws.
    Model-init key is paired between arms, as in the H10 recipe.
    """
    keys = []
    for s in range(10):
        keys.extend((kind, s) for kind in ('model_init', 'continue_batches',
                                          'reset', 'reference_actions', 'l0', 'diagnostic_redraw'))
        keys.extend(('generator_redraw', s, j) for j in range(1, 12))
        for p in range(3):
            keys.extend(('source_reset', s, p, j) for j in range(6))
            keys.append(('source_behavior', s, p))
        keys.extend(('target_train_reset', s, j) for j in range(6))
        keys.extend([('target_train_behavior', s), ('target_val_behavior', s)])
        keys.extend(('target_val_reset', s, j) for j in range(2))
    require(len(keys) == len(set(keys)), 'symbolic seed key collision')
    return tuple(keys)


def validate_seed_mapping(entries, closed_ids):
    """Validate a supplied future map; never generate or save actual seeds."""
    require(type(entries) is list, 'missing seed mapping')
    require(type(closed_ids) in (set, frozenset) and all(type(v) is int for v in closed_ids), 'invalid closed seed registry')
    indexed, used = {}, set()
    for row in entries:
        require(type(row) is dict and set(row) == {'key', 'value'}, 'seed mapping schema')
        require(type(row['key']) is list and row['key'], 'seed key schema')
        key = tuple(row['key'])
        require(type(key[0]) is str and all(type(x) is int for x in key[1:]), 'seed key types')
        value = integer(row['value'])
        require(0 <= value < 2**32, 'seed outside uint32 range')
        require(key not in indexed and value not in used, 'seed alias/duplicate')
        require(value not in closed_ids, 'seed overlaps closed registry')
        indexed[key] = value
        used.add(value)
    require(set(indexed) == set(seed_keys()), 'incomplete or extra symbolic seed grid')
    return indexed


def native_snapshot(record):
    """Proposed stronger contract; existing H16 float32 checks are unchanged."""
    require(type(record['state_reset_seed']) is int, 'reset seed type')
    require(record['obs_dtype'] == 'float32' and record['state_dtype'] == 'float64', 'native dtype mismatch')
    require(type(record['later_t']) is int and record['later_t'] == 12, 'unplanned replay time')
    require(type(record['elapsed_steps']) is int and record['elapsed_steps'] == 12, 'elapsed step mismatch')
    require(record['terminated'] is False and record['truncated'] is False, 'ended trajectory')
    require(record['state_source'] in SOURCES, 'unknown state source')
    require(type(record['prefix_actions']) is list and len(record['prefix_actions']) == 12 and
            all(type(a) is int and a in (0, 1, 2) for a in record['prefix_actions']), 'action-prefix mismatch')
    vector(record['prefix_rewards'], 12)
    for field in ('reset_obs', 'observation', 'reset_state', 'state'):
        vector(record[field], 2)


def validate_native_replay(reference, replayed):
    """Compare supplied observations f32 and native states/rewards f64 bitwise."""
    native_snapshot(reference)
    native_snapshot(replayed)
    require(set(reference) == set(replayed), 'replay schema mismatch')
    fields = ('reset_obs', 'observation', 'reset_state', 'state', 'prefix_rewards')
    for key in reference:
        if key in fields:
            fmt = '>f' if key in ('reset_obs', 'observation') else '>d'
            a = [struct.pack(fmt, number(v)) for v in reference[key]]
            b = [struct.pack(fmt, number(v)) for v in replayed[key]]
            require(a == b, f'native replay mismatch: {key}')
        else:
            require(reference[key] == replayed[key], f'replay metadata mismatch: {key}')
    return True


def validate_checkpoint_manifest(entries, root):
    """Hash-only audit of exactly20 future files; missing never means skip.

    This cannot attest to tensor contents or loaded-model/RMS equivalence.
    A future runner must additionally hash live tensors before/after inference.
    """
    require(type(entries) is list and len(entries) == 20, 'incomplete checkpoint manifest')
    expected = {(s, a) for s in range(10) for a in ARMS}
    seen, paths = set(), set()
    root = Path(root).resolve()
    for row in entries:
        key = (integer(row['seed']), row['arm'])
        require(key in expected and key not in seen, 'duplicate/unplanned checkpoint')
        require(type(row['path']) is str and not Path(row['path']).is_absolute(), 'relative checkpoint path required')
        path = (root/row['path']).resolve()
        require(path.is_relative_to(root) and path not in paths, 'checkpoint path escape/reuse')
        require(strict_equal(row['architecture'], dict(obs_dim=2, n_actions=3, hidden=[64,64], arch='mlp', kind='residual')), 'checkpoint architecture metadata drift')
        rms = row['normalization']
        vector(rms['mean'], 2)
        require(all(v >= 0 for v in vector(rms['var'], 2)) and number(rms['count']) > 0, 'invalid normalization')
        require(type(row['sha256']) is str and len(row['sha256']) == 64 and
                all(c in '0123456789abcdef' for c in row['sha256']), 'invalid checkpoint hash')
        require(path.is_file(), f'missing required checkpoint: {path}')
        require(sha(path) == row['sha256'], f'checkpoint hash mismatch: {path}')
        seen.add(key)
        paths.add(path)
    require(seen == expected, 'incomplete checkpoint grid')
    return True


def validate_draft(cfg):
    """An unresolved draft cannot be upgraded to a locked experiment here."""
    expected = dict(schema_version=1, status='draft_not_locked', base_sha=BASE,
                    n_training_pairs=10, sources=list(SOURCES), resets_per_pair=1,
                    later_times=[12], horizon=16, candidates=16,
                    primary='equal_controller_mean_D_minus_reference_D',
                    interval='student_t_95_df9_critical_2.262', practical_margin=0.0,
                    interpretation='directional_joint_state_library_dependence_only',
                    coupling='trajectory_l0_shared_across_sources_independent_diagnostic_redraw',
                    proposed_time_cap_s=300, proposed_real_steps=62360,
                    proposed_imagined_transitions=174080,
                    restoration='reset_stored_prefix_float32_observation_and_native_float64_state')
    for key, value in expected.items():
        require(strict_equal(cfg.get(key), value), f'draft setting drift: {key}')
    unresolved = ('target_physics', 'physics_exclusion_manifest', 'seed_mapping', 'checkpoint_manifest')
    require(set(cfg) == set(expected) | set(unresolved), 'draft schema drift')
    require(all(cfg[k] is None for k in unresolved), 'registration requires separate lock; do not fill this draft')
    grid = DraftGrid(tuple(cfg['sources']), cfg['resets_per_pair'], tuple(cfg['later_times']))
    counts = budget(grid)
    require(counts['total_real'] == cfg['proposed_real_steps'] and
            counts['total_imagined'] == cfg['proposed_imagined_transitions'], 'budget drift')
    return counts


def review(root):
    root = Path(root)
    parent = verify_provenance(root)
    require(sha(root/FEASIBILITY) == FEASIBILITY_SHA, 'feasibility report changed')
    cfg = load_json(root/CONFIG)
    counts = validate_draft(cfg)
    return dict(status='not_lock_ready', locked=False, authorized=False,
                candidate_budget=counts, draft_config_sha256=sha(root/CONFIG),
                feasibility_sha256=FEASIBILITY_SHA, base_sha=BASE,
                symbolic_seed_keys=len(seed_keys()),
                outstanding=['unused_physics_registration_and_complete_exclusion_registry',
                             'concrete_fresh_seed_mapping_and_closed_stream_audit',
                             'future_runner_checkpoint_tensor_and_dataset_manifests',
                             'guarded_runner_with_native_state_and_reward_runtime_gates',
                             'independent_protocol_lock_review_before_authorization'],
                ledger_used_s=parent['ledger_used_s'], ledger_remaining_s=parent['ledger_remaining_s'],
                new_environment_steps=0, new_imagined_transitions=0,
                model_inference_calls=0, training_updates=0)
