"""Source-only lookahead generalization audit. No environment collection."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from nexus.world.planning_value import sha

SYNTHESIS=Path('docs/NEXUS_LOOKAHEAD_GENERALIZATION_SYNTHESIS.md')
PREP=Path('docs/NEXUS_LOOKAHEAD_GENERALIZATION_SYNTHESIS_PREP.md')
OUTPUT=Path('artifacts/lookahead_generalization_synthesis.json')
LOCKED_SYNTHESIS='2d20dae6c52b290163793865da0ac7ad98d0de208a6fe571257a5ead6c774ecc'
STARTING_SHA='57cff66fd5f8f0451fc45bcf9771a9d0bcdcf3d2'

CITED=(
    dict(name='pendulum_unmatched_development', path='artifacts/bellman_backup_control.json',
         label='bellman_backup_improves_episode_return', mean=155.647, lo=109.825, hi=201.469,
         sha256='d9bc3a0d8cb65d49c3b94061c9079ed59268238007e724f71888cf830b86b0f6',
         source='groups.return_gain.interval'),
    dict(name='pendulum_unmatched_transfer', path='artifacts/lookahead_transfer_confirmation.json',
         label='lookahead_transfer_established', mean=98.608, lo=43.258, hi=153.957,
         sha256='226e649ea34b8b7ada752143e797d43853076863a76a123f8f88de6d75298019',
         source='groups.return_gain.interval'),
    dict(name='pendulum_compute_matched', path='artifacts/pendulum_compute_matched.json',
         label='pendulum_compute_matched_lookahead_established', mean=60.182, lo=11.439, hi=108.924,
         sha256='02ae07e32c5554f2464eb1e7202854d37003aa43b78fe991326a5547fe1853e6',
         source='groups.return_gain.interval'),
    dict(name='cartpole_h3', path='artifacts/cartpole_lookahead.json',
         label='cartpole_lookahead_not_established', mean=4.000, lo=-5.048, hi=13.048,
         sha256='62cc377674bf2114027518d586306b25553752cf1986c1bad6279eac08489098',
         source='groups.return_gain.interval'),
    dict(name='cartpole_h3_hard', path='artifacts/cartpole_lookahead_hard.json',
         label='cartpole_hard_lookahead_not_established', mean=4.600, lo=-7.481, hi=16.681,
         sha256='5343590154ab212b6118f4ef291b22e851f57cb1f74e8e99516087720a90f7b7',
         source='groups.return_gain.interval'),
    dict(name='cartpole_h3_sat', path='artifacts/cartpole_lookahead_sat.json',
         label='cartpole_sat_lookahead_not_established', mean=14.000, lo=-4.621, hi=32.621,
         sha256='76fef73eb814607a4567ff6d655f4a2ea8f5134cf6b938a2f93d3bc690de7826',
         source='groups.return_gain.interval'),
    dict(name='acrobot_unmatched_development', path='artifacts/acrobot_lookahead.json',
         label='acrobot_lookahead_established', mean=27.914, lo=13.962, hi=41.867,
         sha256='83b9fbeeb2558cd47d41f44342411c5cf69cb0f6261138ee7f0f5d1e07a04e87',
         source='groups.return_gain.interval'),
    dict(name='acrobot_unmatched_transfer', path='artifacts/acrobot_lookahead_confirm.json',
         label='acrobot_lookahead_transfer_established', mean=37.961, lo=21.106, hi=54.816,
         sha256='435fdcf70c64cc79a47f4b36cd947051a24b4d4263afd0e38efb79b93ebcde5b',
         source='groups.return_gain.interval'),
    dict(name='acrobot_compute_matched', path='artifacts/acrobot_compute_matched.json',
         label='acrobot_compute_matched_lookahead_not_established', mean=12.834, lo=3.815, hi=21.853,
         sha256='ed99327d3a0f8be9501df13619957b416268ae3f3dfaa36676f93c51e256bcc2',
         source='groups.return_gain.interval'),
    dict(name='mountaincar_unmatched_development', path='artifacts/mountaincar_lookahead.json',
         label='mountaincar_lookahead_established', mean=44.092, lo=13.945, hi=74.239,
         sha256='28e19af3e986a25bd094d9a271180002f85c03c2cb9bb655cfae52ab25fa78eb',
         source='groups.return_gain.interval'),
    dict(name='mountaincar_unmatched_transfer', path='artifacts/mountaincar_lookahead_confirm.json',
         label='mountaincar_lookahead_transfer_established', mean=50.366, lo=36.493, hi=64.239,
         sha256='bbf22c1717cc82a7140d3728c9a0fa1101d0d5946ebedb447d96012080b81678',
         source='groups.return_gain.interval'),
    dict(name='mountaincar_compute_matched', path='artifacts/mountaincar_compute_matched.json',
         label='mountaincar_compute_matched_lookahead_established', mean=54.649, lo=26.611, hi=82.686,
         sha256='8a829874a5ba07d0e37e60b82efbce87afea83f04009c5f857be6e3523ca6c8f',
         source='groups.return_gain.interval'),
    dict(name='mountaincar_continuous_unmatched_development', path='artifacts/mountaincar_continuous_lookahead.json',
         label='mountaincar_continuous_lookahead_established', mean=69.758, lo=29.321, hi=110.196,
         sha256='668a9a85e121d82a830399e9c967765e3f507e9ab062195e3dee3f9dc1b49a15',
         source='groups.return_gain.interval'),
    dict(name='linear_first_action_q', path='artifacts/first_action_value.json',
         label='aligned_first_action_gain_not_established', mean=-3.535, lo=-9.840, hi=2.769,
         sha256='1ea6c5e28930b1e6670a4894862af23f2f701f0ebd1d0d4ebeebefcd43e3828a',
         source='groups.pooled.gain_vs_h16.interval'),
    dict(name='terminal_value', path='artifacts/terminal_value.json',
         label='local_first_action_inconclusive', mean=-0.221, lo=-5.881, hi=5.438,
         sha256='74dcff9c710e6108020c11b64f68b4321fc9306a8f69b9a8491af60a86f9a420',
         source='comparisons.primary.interval'),
    dict(name='action_conditioned_q', path='artifacts/action_conditioned_q_completed.json',
         label='action_conditioned_gain_not_established', mean=-4.293, lo=-15.751, hi=7.165,
         sha256='aa78514a5a2bb560089453000d8049284aafe3136c83f03c1a88de9dc01a3793',
         source='groups.pooled.gain_vs_h16.interval'),
)


def _nested(payload, path):
    cur=payload
    for key in path.split('.'):
        cur=cur[key]
    return cur


def load_cited():
    if sha(SYNTHESIS)!=LOCKED_SYNTHESIS:
        raise ValueError('synthesis document hash drifted')
    rows=[]
    for spec in CITED:
        if sha(spec['path'])!=spec['sha256']:
            raise ValueError(f'cited parent changed: {spec["path"]}')
        payload=json.loads(Path(spec['path']).read_text())
        if payload.get('label')!=spec['label']:
            raise ValueError(f'cited label drifted: {spec["name"]}')
        interval=_nested(payload, spec['source'])
        mean=float(np.round(interval['mean'], 3))
        lo=float(np.round(interval['lo'], 3))
        hi=float(np.round(interval['hi'], 3))
        if mean!=spec['mean'] or lo!=spec['lo'] or hi!=spec['hi']:
            raise ValueError(f'cited interval drifted: {spec["name"]} {mean} [{lo}, {hi}]')
        rows.append(dict(name=spec['name'], label=spec['label'], mean=mean, lo=lo, hi=hi,
                         path=spec['path'], sha256=spec['sha256']))
    return rows


def extra_search_share():
    cited={row['name']:row for row in load_cited()}
    def gap(unmatched, matched):
        closed=cited[unmatched]['mean']-cited[matched]['mean']
        return dict(unmatched=cited[unmatched]['mean'], matched=cited[matched]['mean'],
                    unpaired_points_closed=float(np.round(closed, 3)),
                    unpaired_fraction_of_unmatched=float(np.round(closed/cited[unmatched]['mean'], 3)),
                    remainder_clears_margin=cited[matched]['mean']>=25.0 and cited[matched]['lo']>0)
    return dict(acrobot=gap('acrobot_unmatched_development','acrobot_compute_matched'),
                pendulum=gap('pendulum_unmatched_development','pendulum_compute_matched'),
                mountaincar=gap('mountaincar_unmatched_development','mountaincar_compute_matched'))


def conclusions():
    share=extra_search_share()
    return dict(
        common_successful_controllers='family-specific frozen world model plus RandomShootingMPC H=16 and one-step backup of open-loop successor height on dense 200-step rewards',
        acrobot_extra_search_explains_more='unmatched Acrobot gap was only 2.914 above the 25-point margin; unpaired extra H=16 search closed 15.080 points and dropped the remainder below 25',
        extra_search_unpaired=share,
        shared_algorithm_not_shared_weights=True,
        cross_family_learning_supported=False,
        meta_learning_supported=False,
        lookahead_imagined_per_step=771,
        bottleneck='three independent successor H=16 trees; 768 of 771 imagined states are search from s-prime, not the one-step backup',
        proposed_mechanism='tree_reuse_lookahead',
        proposed_imagined_per_step=259,
        distinct_from_closed_qv=True,
        next_major_milestone='compute-efficient receding first-action backup transferred as an algorithm across families that keep their own world models',
        mountaincar_continuous_confirmation_is_this_experiment=False,
    )


def audit():
    cited=load_cited()
    payload=dict(complete=True, authorized=False, runs=0, new_environment_steps=0,
                 new_imagined_transitions=0, training_updates=0, confirmation_outcomes_read=False,
                 starting_sha=STARTING_SHA, synthesis_sha256=sha(SYNTHESIS),
                 prep_sha256=sha(PREP), cited=cited, conclusions=conclusions(),
                 label='lookahead_generalization_synthesis_source_only',
                 primary=None, practical_margin=25.0)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True)+'\n')
    return payload


def execute():
    raise PermissionError('synthesis is source-only; tree-reuse collection requires a separate authorized allocation')
