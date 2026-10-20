"""Independent stdlib saved-data analysis; no model imports or new execution."""
import hashlib
import json
import math
from pathlib import Path
import statistics as stats
ROOT=Path(__file__).resolve().parents[1]


def analyze(root=ROOT):
    root=Path(root);config=root/'configs/seed_memory_aware.json';c=json.loads(config.read_text())
    raw=root/'artifacts/seed_memory_aware.json';r=json.loads(raw.read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if r['declared_complete'] is not True or r['config']!=c or r['config_sha256']!=sha(config) or r['new_real_steps']!=0 or r['episode_ids']!=c['expected_episode_ids']:raise ValueError('registered_source_grid')
    if sha(root/c['source_result'])!=c['source_sha256'] or sha(root/c['parent_model'])!=c['parent_sha256'] or r['model_work']['frozen_core'] is not True:raise ValueError('frozen_source_provenance')
    if r['model_work']['imagined_candidate_rows']>c['max_imagined_transitions'] or r['command_wall_s']>c['max_wall_s']:raise ValueError('resource_cap')
    if [s['seed'] for s in r['seeds']]!=c['controller_seeds']:raise ValueError('seed_grid')
    summary={}
    def numbers(values):
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('finite_numeric_metrics')
    for s in r['seeds']:
        if sha(root/s['checkpoint'])!=s['sha256']:raise ValueError('controller_checkpoint_hash')
        numbers([s['parameter_change']])
        if len(s['training'])!=c['meta_updates'] or [t['update'] for t in s['training']]!=list(range(1,c['meta_updates']+1)):raise ValueError('update_grid')
        for t in s['training']:numbers([t['objective'],t['gradient_norm']])
    for split in c['expected_episode_ids']:
        values={m:[] for m in ('learned','fixed_protected','replay_sgd')};forget={m:[] for m in values}
        for s in r['seeds']:
            rows=s['evaluation'][split]
            if [e['source_episode_seed'] for e in rows]!=c['expected_episode_ids'][split]:raise ValueError('episode_grid')
            for row in rows:
                if set(row['methods'])!=set(values):raise ValueError('method_grid')
                for metrics in row['methods'].values():
                    if set(metrics)!={'objective','query_learning_curve','query_auc','forgetting','theta_norm'} or len(metrics['query_learning_curve'])!=c['support_rows']:raise ValueError('metric_grid')
                    numbers([v for k,v in metrics.items() if k!='query_learning_curve']+metrics['query_learning_curve'])
                    if not math.isclose(stats.mean(metrics['query_learning_curve']),metrics['query_auc'],rel_tol=1e-6,abs_tol=1e-7):raise ValueError('curve_arithmetic')
            for m in values:
                values[m].append(stats.mean(e['methods'][m]['query_auc'] for e in rows))
                forget[m].append(stats.mean(e['methods'][m]['forgetting'] for e in rows))
        contrasts={}
        for baseline in ('fixed_protected','replay_sgd'):
            paired=[b-a for a,b in zip(values['learned'],values[baseline])];mean=stats.mean(paired)
            half=4.302652729*stats.stdev(paired)/math.sqrt(3)
            contrasts[baseline]=dict(mean_reduction=mean,ci95=[mean-half,mean+half],paired_values=paired,
                relative_reduction=mean/stats.mean(values[baseline]))
        summary[split]=dict(query_auc={m:dict(mean=stats.mean(v),per_controller_seed=v) for m,v in values.items()},
            forgetting={m:stats.mean(v) for m,v in forget.items()},contrasts=contrasts)
    audit=summary['audit']
    screen=all(v['relative_reduction']>=c['screen_fraction'] for v in audit['contrasts'].values()) and audit['forgetting']['learned']<=audit['forgetting']['fixed_protected']
    return dict(schema='seed_memory_aware_analysis_v1',raw_sha256=sha(raw),config_sha256=sha(config),
        splits=summary,practical_screen_passed=screen,decision='screen_passed_development_only' if screen else 'practical_learning_rule_improvement_not_established',
        statistical_unit='controller_training_seed_conditional_on_one_frozen_core_and_source_bank',
        independent_decoder_replicates=1,controller_optimizer_seeds=3,
        limitations=['source assessment already belongs to inspected source bank, not confirmation',
                    'fixed replay step.2 is unstable for these feature scales and is not a strong tuned baseline',
                    'GUI functional checks are not controlled decision-quality evidence',
                    'meaning-channel plasticity transfer not evaluated',
                    'no new control or all-action ranking comparison'])


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
