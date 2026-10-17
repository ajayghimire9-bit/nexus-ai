"""Source-only synthesis of the seven closed cross-environment transfer rungs.

No collection. No retune. No new shared-trunk, FiLM, low-budget, or
target-family variant. Not learning-to-learn. Not AGI.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from nexus.world.planning_value import sha
from nexus.world.xenv_context_code import XEnvContextCodeNet
from nexus.world.xenv_deep_trunk import XEnvDeepNet
from nexus.world.xenv_residual_context import RESIDUAL_PAD, XEnvResidualContextNet
from nexus.world.xenv_transfer import HIDDEN, XEnvNet

PROTOCOL = Path('docs/NEXUS_XENV_TRANSFER_FAILURE_SYNTHESIS.md')
OUTPUT = Path('artifacts/xenv_transfer_failure_synthesis.json')
FAMILIES_MCC_TARGET = dict(cartpole=(4, 2), acrobot=(6, 3), mountaincar=(2, 3), mcc=(2, 3))
RUNGS = (
    dict(id=1, name='shared_layer', artifact='artifacts/xenv_transfer_pilot.json',
         report='docs/NEXUS_XENV_TRANSFER_PILOT_RESULTS.md',
         label='xenv_shared_layer_not_established', architecture='one 64→64 tanh',
         prior_train=512, env_cap=44000, target='MCC'),
    dict(id=2, name='deep_trunk', artifact='artifacts/xenv_deep_trunk.json',
         report='docs/NEXUS_XENV_DEEP_TRUNK_RESULTS.md',
         label='xenv_deep_trunk_not_established', architecture='two 64→64 tanh',
         prior_train=512, env_cap=44000, target='MCC'),
    dict(id=3, name='occupancy_film', artifact='artifacts/xenv_context_code.json',
         report='docs/NEXUS_XENV_CONTEXT_CODE_RESULTS.md',
         label='xenv_context_code_not_established', architecture='shared + occupancy FiLM',
         prior_train=512, env_cap=44000, target='MCC'),
    dict(id=4, name='residual_film', artifact='artifacts/xenv_residual_context.json',
         report='docs/NEXUS_XENV_RESIDUAL_CONTEXT_RESULTS.md',
         label='xenv_residual_context_not_established', architecture='shared + residual FiLM',
         prior_train=512, env_cap=44000, target='MCC'),
    dict(id=5, name='prior_scale', artifact='artifacts/xenv_prior_scale.json',
         report='docs/NEXUS_XENV_PRIOR_SCALE_RESULTS.md',
         label='xenv_prior_scale_not_established', architecture='one 64→64 tanh, 2× prior',
         prior_train=1024, env_cap=63200, target='MCC'),
    dict(id=6, name='low_budget', artifact='artifacts/xenv_low_budget.json',
         report='docs/NEXUS_XENV_LOW_BUDGET_RESULTS.md',
         label='xenv_low_budget_not_established', architecture='one 64→64 tanh, 2× prior, 128-only',
         prior_train=1024, env_cap=63200, target='MCC'),
    dict(id=7, name='cartpole_target', artifact='artifacts/xenv_cartpole_target.json',
         report='docs/NEXUS_XENV_CARTPOLE_TARGET_RESULTS.md',
         label='xenv_cartpole_target_not_established', architecture='one 64→64 tanh, CartPole target',
         prior_train=512, env_cap=44000, target='CartPole'),
)


def _param_groups(net):
    shared = family = other = 0
    for name, param in net.named_parameters():
        n = int(param.numel())
        if 'shared' in name:
            shared += n
        elif any(key in name for key in ('in_heads', 'in_proj', 'state_heads', 'term_heads')):
            family += n
        else:
            other += n
    return dict(total=shared + family + other, shared=shared, family=family, other=other)


def architecture_inventory():
    return dict(
        hidden=HIDDEN,
        residual_pad=int(RESIDUAL_PAD),
        family_interfaces=dict(
            cartpole=dict(obs_dim=4, n_actions=2, gym_id='CartPole-v1'),
            acrobot=dict(obs_dim=6, n_actions=3, gym_id='Acrobot-v1'),
            mountaincar=dict(obs_dim=2, n_actions=3, gym_id='MountainCar-v0'),
            mountaincar_continuous=dict(obs_dim=2, n_actions=3, gym_id='MountainCarContinuous-v0'),
        ),
        parameter_counts=dict(
            rung1_shared_layer=_param_groups(XEnvNet(FAMILIES_MCC_TARGET, seed=0)),
            rung2_deep_trunk=_param_groups(XEnvDeepNet(FAMILIES_MCC_TARGET, seed=0)),
            rung3_occupancy_film=_param_groups(XEnvContextCodeNet(FAMILIES_MCC_TARGET, seed=0)),
            rung4_residual_film=_param_groups(XEnvResidualContextNet(FAMILIES_MCC_TARGET, seed=0)),
        ),
        what_is_shared=(
            'After a family-specific Linear(obs+onehot → 64) and tanh, every family '
            'passes through the same Linear(64 → 64) and tanh. Residual FiLM also '
            'shares ctx_enc/film; occupancy FiLM shares those without residual. '
            'State and termination heads stay family-specific. The residual loss '
            'is family-native s′−s.'
        ),
        what_is_not_shared=(
            'Observation coordinates, action cardinalities and meanings, reward '
            'functions, and the target-family input/output heads. Those heads are '
            'never pretrained on the target family.'
        ),
    )


def _interval(row):
    return dict(mean=float(row['mean']), lo=float(row['lo']), hi=float(row['hi']),
                n=int(row['n']), df=int(row.get('df', 9)))


def _corr(cells, budget):
    ret = [float(c['returns']['xenv'][budget]) - float(c['returns']['scratch'][budget])
           for c in cells]
    mae = [float(c['mae']['xenv'][budget]) - float(c['mae']['scratch'][budget])
           for c in cells]
    if float(np.std(ret)) == 0.0 or float(np.std(mae)) == 0.0:
        return None
    return float(np.corrcoef(ret, mae)[0, 1])


def load_rung(spec):
    payload = json.loads(Path(spec['artifact']).read_text())
    if payload.get('complete') is not True:
        raise ValueError(f"{spec['artifact']} is not a complete committed result")
    if payload['label'] != spec['label']:
        raise ValueError(f"{spec['artifact']} label drifted")
    if payload.get('claims_learning_to_learn') is not False or payload.get('is_agi') is not False:
        raise ValueError(f"{spec['artifact']} forbidden claim flags drifted")
    groups = payload['groups']
    primary = _interval(groups['primary']['interval'])
    per_budget = {b: _interval(groups['per_budget_return_gain'][b])
                  for b in groups['per_budget_return_gain']}
    mae = {b: _interval(groups['mae_gain'][b]) for b in groups['mae_gain']}
    row = dict(
        id=spec['id'], name=spec['name'], label=payload['label'],
        architecture=spec['architecture'], target_family=spec['target'],
        target_physics=list(payload['target_physics']),
        holdout_rule=payload['holdout_rule'],
        primary=primary, per_budget_return_gain=per_budget, mae_gain=mae,
        wall_clock_s=float(payload['wall_clock_s']),
        env_steps=int(payload['counts']['env_steps']),
        env_cap=spec['env_cap'], prior_train=spec['prior_train'],
        imagined=int(payload['counts']['model_states']),
        artifact_sha256=sha(spec['artifact']), report_sha256=sha(spec['report']),
        n_seeds_primary_positive=sum(1 for x in groups['primary']['per_seed'] if x > 0),
        exploratory_return_mae_corr={b: _corr(payload['cells'], b) for b in ('128', '1024')},
        claims_learning_to_learn=False, is_agi=False,
    )
    if spec['name'] == 'cartpole_target':
        row['ceiling_at_200'] = {
            b: {arm: sum(1 for c in payload['cells'] if float(c['returns'][arm][b]) >= 199.5)
                for arm in ('xenv', 'scratch', 'reference')}
            for b in ('128', '1024')}
    if 'context_diagnostics' in groups:
        row['nearest_source_ratio_mean'] = float(
            groups['context_diagnostics']['nearest_source_ratio_mean'])
    return row


def comparison_table():
    return [load_rung(spec) for spec in RUNGS]


def bottleneck():
    return dict(
        statement=(
            'The shared object was a hidden-layer weight matrix sitting between '
            'incompatible family embeddings, while the loss and the output heads '
            'remained family-native. There is no common dynamical coordinate for '
            'those weights to represent.'
        ),
        status='supported_interpretation',
        not_a_trained_label=True,
        discarded_as_established_cause=(
            'Starvation at 2× prior, occupancy-only context, residual-aware '
            'context, trunk depth, scarce-target 128-only primary, and '
            'MCC-specificity were each tested and not established.'
        ),
        not_established=(
            'Cross-family harm, a successful transfer mechanism, and learning-to-learn.'
        ),
    )


def next_direction():
    return dict(
        name='family_native_interface_adaptation',
        hypothesis=(
            'Limited-experience adaptation should estimate a quantity that lives in '
            'the target family\'s own coordinates (observation RMS, residual scale, '
            'or a low-dimensional same-family physics code) and apply it to a '
            'family-local residual world model. It should not share hidden weights '
            'across CartPole, Acrobot, MountainCar, and MountainCarContinuous.'
        ),
        why_not_another_xenv_variant=(
            'Seven matched rungs already closed shared-trunk depth, FiLM occupancy, '
            'FiLM residual, 2× prior, 128-only primary, and a second target family.'
        ),
        supporting_established_evidence=(
            'V0.6.6: source observation RMS transferred on CartPole with a random '
            'net (B−A +222.4 [173.0, 271.7]); a pretrained encoder given that RMS '
            'hurt (D−B −223.1 [−294.0, −152.3]). MCC/MountainCar/Acrobot lookahead '
            'transferred with separately trained family models, not shared trunks.'
        ),
        falsifier=(
            'On unused same-family physics that is not a closed xenv holdout, a '
            'family-native RMS or residual-scale adapter at budget 128 fails the '
            'predeclared rule adapter−scratch mean>0 and CI lower bound>0.'
        ),
        minimal_future_experiment=(
            'Lock a within-family MountainCarContinuous residual world model. '
            'Treatment: source-MCC observation RMS or a 1–3d residual-scale inferred '
            'from support s′−s in MCC coordinates only. Control: matched scratch '
            'with fresh RMS. Primary: 128-transition H=16 return, ten seeds, '
            'student-t 95%, lo>0. New unused physics. Caps ≤600 s / ≤44,000 / local '
            'CPU. No cross-family weights, no FiLM trunk, no closed holdout reuse. '
            'Not authorized by this synthesis.'
        ),
        claims_learning_to_learn=False,
        is_agi=False,
    )


def analyze():
    rows = comparison_table()
    if len(rows) != 7:
        raise ValueError('synthesis must cover all seven closed rungs')
    if any(row['label'].endswith('beats_scratch') for row in rows):
        raise ValueError('synthesis must not promote a closed rung to established')
    if any(row['primary']['lo'] > 0 for row in rows):
        raise ValueError('no closed primary excluded 0; do not invent establishment')
    return dict(
        complete=True,
        authorized=False,
        new_environment_steps=0,
        new_imagined_transitions=0,
        starting_sha='dbeebccc556a01f563dd835519e5a2333ddb0868',
        rungs=rows,
        architecture=architecture_inventory(),
        bottleneck=bottleneck(),
        next_direction=next_direction(),
        protocol_sha256=sha(PROTOCOL) if PROTOCOL.exists() else None,
        claims_learning_to_learn=False,
        is_agi=False,
        note='Source-only and existing-artifact analysis. No collection.',
    )


def prep():
    report = analyze()
    if report['new_environment_steps'] != 0:
        raise RuntimeError('synthesis must not collect')
    return report
