"""Phase-separated study coordinator over a trusted resource-metered host.

No environment factory. Real collection still needs a separately registered
case manifest, authorization and a reviewed host implementation.
"""
from dataclasses import asdict
from copy import deepcopy
import math
from nexus.core.episode_context import EpisodeContext
from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import ExecutionReport


class SourcePrior:
    def __init__(self,training_pairs):
        self.models={};self.families={}
        for row in training_pairs:
            if row.get('phase')!='training' or row.get('kind')!='observed_full_policy_advantage' or type(row.get('advantage')) not in (int,float) or not math.isfinite(row['advantage']):raise ValueError('source_feedback_only')
            self.models.setdefault((row['family'],row['model']),[]).append(row['advantage'])
            self.families.setdefault(row['family'],[]).append(row['advantage'])
        if not self.models:raise ValueError('source_prior_required')

    def value(self,family,model,*,known_source_model):
        if type(known_source_model) is not bool:raise ValueError('known_model_flag')
        rows=self.models.get((family,model)) if known_source_model else None
        rows=rows or self.families.get(family)
        if not rows:raise ValueError('unfamiliar_family_prior_unavailable')
        return sum(rows)/len(rows)


class StagedStudy:
    def __init__(self,manifest,*,closed_seeds=()):
        if not manifest.get('registered') or not manifest.get('authorized') or not manifest.get('protocol_commit'):
            raise ValueError('fresh_collection_not_registered_or_authorized')
        if manifest.get('kind') not in ('synthetic_contract','registered_fresh_study'):raise ValueError('study_kind')
        self.manifest=deepcopy(manifest);self.closed=set(closed_seeds);self.policy=None;self.frozen=None;self.contexts={};self.prefixes={};self.probe_real=0;self.probe_imagined=0;self.consumed=False
        cases=manifest['cases'];keys=[(c['task'],c['condition'],c['episode']) for c in cases]
        if not cases or len(set(keys))!=len(keys):raise ValueError('complete_unique_case_plan')
        by_pair={}
        for case in cases:
            if any(type(case[k]) is not int or case[k]<0 for k in ('reset_seed','planner_seed','episode','probe_steps','remaining_steps')):raise ValueError('case_counts')
            if case['reset_seed'] in self.closed or case['planner_seed'] in self.closed:raise ValueError('closed_episode_seed')
            if case['probe_steps']+case['remaining_steps']!=200:raise ValueError('matched_remaining_horizon')
            by_pair.setdefault((case['task'],case['episode']),[]).append(case)
        for group in by_pair.values():
            if set(c['condition'] for c in group)!=set(manifest['conditions']):raise ValueError('missing_planned_condition')
            if len({(c['reset_seed'],c['planner_seed'],c['probe_steps'],c['remaining_steps']) for c in group})!=1:raise ValueError('unpaired_opportunities')
        for name in ('total_real_cap','total_imagined_cap','per_case_real_cap','per_case_imagined_cap'):
            if type(manifest[name]) is not int or manifest[name]<0:raise ValueError('explicit_resource_cap')
        required=sum(c['remaining_steps'] for c in cases)+sum(g[0]['probe_steps'] for g in by_pair.values())
        if required>manifest['total_real_cap'] or manifest['total_real_cap']>100000:raise ValueError('preflight_real_budget')

    def fit_source(self,training_rows,fitter,fingerprint):
        if self.policy is not None or any(r.get('phase')!='training' for r in training_rows):raise ValueError('source_fit_once')
        self.policy=fitter(tuple(training_rows));self.fingerprint=fingerprint;self.frozen=fingerprint(self.policy)
        return self.frozen

    def adapt_support(self,task,prefix,adapter,receipt,*,episode=0):
        key=(task,episode)
        if self.policy is None or key in self.contexts:raise ValueError('fit_then_adapt_once')
        sizes={c['probe_steps'] for c in self.manifest['cases'] if c['task']==task and c['episode']==episode}
        if len(sizes)!=1 or len(prefix)!=next(iter(sizes)):raise ValueError('matched_probe_budget')
        for i,row in enumerate(prefix):
            if set(row)!={'task','episode','step','phase','observation','action','next_observation','reward'} or row['step']!=i or row['task']!=task or row['episode']!=episode or row['phase']!='support':raise ValueError('chronological_support_only')
        context=EpisodeContext(len(prefix[0]['observation']),self.manifest.get('n_actions',3)) if prefix else None
        for row in prefix:context.observe(row['observation'],row['action'],row['next_observation'],row['reward'],step=row['step'])
        if type(receipt) is not ExecutionReport or receipt.status!='complete_execution' or receipt.physical_completed_reported.real_steps!=len(prefix):raise ValueError('charged_support_receipt')
        self.probe_real+=receipt.physical_completed_reported.real_steps;self.probe_imagined+=receipt.physical_completed_reported.imagined_transitions
        if self.probe_real>self.manifest['total_real_cap'] or self.probe_imagined>self.manifest['total_imagined_cap']:raise ValueError('support_resource_cap')
        safe_prefix=deepcopy(tuple(prefix));before=digest(safe_prefix)
        self.contexts[key]=adapter(self.policy,safe_prefix)
        if digest(safe_prefix)!=before:raise ValueError('adapter_modified_support')
        self.prefixes[key]=deepcopy(tuple(prefix))
        if self.fingerprint(self.policy)!=self.frozen:raise ValueError('support_changed_frozen_recipe')

    def evaluate(self,host):
        if self.consumed or self.policy is None or {(c['task'],c['episode']) for c in self.manifest['cases']}!=set(self.contexts):raise ValueError('adapt_before_evaluate_once')
        self.consumed=True;rows=[];total_real=self.probe_real;total_imagined=self.probe_imagined
        for case in self.manifest['cases']:
            if self.fingerprint(self.policy)!=self.frozen:raise ValueError('recipe_changed')
            key=(case['task'],case['episode']);context_hash=digest(self.contexts[key])
            safe_case=deepcopy(case);row,report=host(safe_case,self.policy,self.contexts[key])
            if safe_case!=case:raise ValueError('host_changed_case_protocol')
            if digest(self.contexts[key])!=context_hash:raise ValueError('evaluation_updated_context')
            if type(report) is not ExecutionReport or report.status!='complete_execution':raise ValueError('trusted_completed_resource_receipt')
            actual=report.physical_completed_reported
            if actual.real_steps!=case['remaining_steps'] or actual.real_steps>self.manifest['per_case_real_cap'] or actual.imagined_transitions>self.manifest['per_case_imagined_cap']:raise ValueError('probe_and_evaluation_cost')
            if row['support_hash']!=digest(self.prefixes[key]):raise ValueError('shared_support_prefix')
            rewards=row['evaluation_rewards'];probe=[r['reward'] for r in self.prefixes[key]]
            if len(rewards)!=case['remaining_steps'] or len(probe)!=case['probe_steps'] or not all(type(v) in (int,float) and math.isfinite(v) for v in rewards+probe):raise ValueError('complete_finite_episode')
            total_real+=actual.real_steps;total_imagined+=actual.imagined_transitions
            if total_real>self.manifest['total_real_cap'] or total_imagined>self.manifest['total_imagined_cap']:raise ValueError('study_resource_cap')
            rows.append(dict(case=case,probe_return=sum(probe),remaining_return=sum(rewards),full_accounted_return=sum(probe)+sum(rewards),
                             host_metrics=row.get('metrics',{}),resource_receipt=asdict(report)))
        if self.fingerprint(self.policy)!=self.frozen:raise ValueError('evaluation_changed_policy')
        return dict(kind=self.manifest['kind'],complete=True,manifest_sha256=digest(self.manifest),rows=rows,
                    real_steps=total_real,imagined_transitions=total_imagined,recipe_hash=self.frozen)
