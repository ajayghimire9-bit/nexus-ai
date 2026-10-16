"""MountainCarContinuous confirmation protocol locks."""
from __future__ import annotations
from nexus.tasks.mountaincar_continuous_family import (
    mcc_default,
    mcc_lookahead_confirmation,
    mcc_lookahead_development,
    mcc_physics_key,
)
from nexus.world import mountaincar_continuous_lookahead as base
from nexus.world import mountaincar_continuous_lookahead_confirm as m


def test_confirmation_holdout_avoids_source_and_development():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.0016,0.0012,0.09),(0.0038,0.0019,0.05),(0.0029,0.0015,0.08)]
    closed={mcc_physics_key(mcc_default())}
    closed|={mcc_physics_key(s) for s in mcc_lookahead_development()}
    assert all(k not in closed for k in hold)
    specs=mcc_lookahead_confirmation()
    assert [tuple(mcc_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='bc7c74c781c9e24f'
    assert cfg['candidate_horizon']==16 and cfg['n_candidates']==16
    assert cfg['retune_from_development'] is False
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    assert cfg['acrobot_copy'] is False and cfg['mountaincar_copy'] is False
    assert cfg['reset_base']==32000000 and cfg['step_seed_base']==32100000
    assert cfg['train_collect_base']==340000 and cfg['val_collect_base']==345000
    ours={base.reset_seed(cfg,s,t) for s in range(10) for t in range(3)}
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='mountaincar_continuous_lookahead_transfer_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='mountaincar_continuous_lookahead_transfer_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='mountaincar_continuous_lookahead_transfer_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_budget_matches_the_locked_caps():
    cfg=m.load_config()
    counts=m.budget(cfg)
    assert counts['episode_max']==cfg['env_cap']==24800
    assert counts['model_states_max']==cfg['model_cap']==6162000
    assert counts['train']==12800 and counts['control_max']==12000
    assert counts['time_cap_s']==300 and counts['training_updates']==200
    assert counts['lookahead_imagined_per_step']==771 and counts['h16_imagined_per_step']==256


def test_one_run_allocation_is_authorized_and_binds_the_locked_hashes():
    from pathlib import Path
    import json
    from nexus.world.planning_value import sha
    cfg=m.load_config()
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['retune_from_development'] is False and record['mountaincar_copy'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    m.require_allocation(cfg)
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])>=cfg['time_cap_s']
    assert float(usage['ledger']['consumed_before_this_run_s'])==108.341
    assert int(usage['retries'])==0
