"""Matched-budget synthetic screen. No real environment or scientific ledger."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from nexus.evolution1.catalogue import ContractError, digest
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2.methods import make_methods
from nexus.evolution2.tasks import (DEV_FAMILY, HOLDOUT_FAMILY, MODE, PROPOSALS,
                                    SHARED_PROBES, SHIFTED_FAMILY, SCIENTIFIC,
                                    TRAIN_FAMILIES, default_split, hidden_score,
                                    oracle_best, split_digest)


@dataclass(frozen=True)
class ProposalRecord:
    task_id: str
    slot: int
    method: str
    variant_id: str
    score: float
    failed: bool
    event_id: str
    mode: str = MODE
    scientific: bool = SCIENTIFIC


def feedback_event(task, slot, variant_id):
    return digest(dict(task=task.task_id, slot=int(slot), variant=variant_id, mode=MODE))


def propose_on_task(method, task, *, proposals=PROPOSALS, apply_update=True, eval_mode=False):
    if type(proposals) is not int or proposals != PROPOSALS:
        raise ContractError('matched_proposal_count_required')
    available = list(VARIANTS)
    records = []
    for slot in range(proposals):
        variant = ANCHORS[slot] if slot < SHARED_PROBES else method.choose(tuple(available), task.context)
        if variant not in available:
            raise ContractError('duplicate_or_invalid_proposal')
        score = hidden_score(task, variant)
        event_id = feedback_event(task, slot, variant.fingerprint)
        receipt = TrainingFeedback(variant.fingerprint, score, False, event_id)
        if eval_mode:
            method.update_eval(receipt, task.context)
        elif apply_update:
            method.update(receipt, task.context)
        records.append(ProposalRecord(task.task_id, slot, method.name, variant.fingerprint,
                                      score, False, event_id))
        available.remove(variant)
    return tuple(records)


def summarize_records(records, task):
    scores = [r.score for r in records]
    best = max(scores)
    _, oracle = oracle_best(task)
    return dict(task_id=task.task_id, family=task.family, role=task.role, mode=MODE,
                scientific=False, n_proposals=len(records), best=best,
                mean=sum(scores) / len(scores), regret=oracle - best, oracle=oracle,
                variants=[r.variant_id for r in records])


def _run_block(methods, tasks, *, phase, local_updates):
    out = {name: [] for name in methods}
    records = {name: [] for name in methods}
    for task in tasks:
        for name, method in methods.items():
            if phase == 'train' and method.resets:
                method.reset_task()
            eval_mode = phase != 'train'
            apply = phase == 'train'
            if eval_mode:
                actor = method.eval_clone(local_updates=local_updates)
            else:
                actor = method
            rows = propose_on_task(actor, task, apply_update=apply, eval_mode=eval_mode)
            out[name].append(summarize_records(rows, task))
            records[name].extend(rows)
    return out, records


def transfer_benefit(persistent_rows, reset_rows, key='mean'):
    if len(persistent_rows) != len(reset_rows):
        raise ContractError('unmatched_eval_rows')
    return [p[key] - r[key] for p, r in zip(persistent_rows, reset_rows)]


def classify_transfer(mean, lo, hi, n, complete=True):
    if not complete or int(n) < 1:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'e2_persistence_helps_transfer'
    if mean < 0 and hi < 0:
        return 'e2_persistence_hurts_transfer'
    return 'e2_transfer_not_established'


def run_screen(seed=7, *, local_updates=False, split=None):
    """Synthetic illustration runner. Does not consume the scientific ledger."""
    split = default_split() if split is None else split
    if any(t.family == HOLDOUT_FAMILY for t in split['train'] + split['development'] + split['shifted']):
        raise ContractError('holdout_family_consumed')
    methods = make_methods(seed)
    train_sum, train_rec = _run_block(methods, split['train'], phase='train', local_updates=False)
    frozen = methods['persistent_adaptive'].freeze()
    frozen_before_eval = dict(frozen)
    eval_methods = {
        name: method for name, method in methods.items()
    }
    dev_sum, dev_rec = _run_block(eval_methods, split['development'], phase='eval',
                                  local_updates=local_updates)
    shift_sum, shift_rec = _run_block(eval_methods, split['shifted'], phase='eval',
                                      local_updates=local_updates)
    if methods['persistent_adaptive'].learned_state()['weights'] != frozen_before_eval['weights']:
        raise ContractError('global_weights_mutated_during_eval')
    benefit = transfer_benefit(dev_sum['persistent_adaptive'], dev_sum['reset_adaptive'])
    mean = sum(benefit) / len(benefit)
    shifted_benefit = transfer_benefit(shift_sum['persistent_adaptive'], shift_sum['reset_adaptive'])
    lookups = {name: len(train_rec[name]) + len(dev_rec[name]) + len(shift_rec[name])
               for name in methods}
    if len(set(lookups.values())) != 1:
        raise ContractError('unmatched_lookup_budget')
    return dict(
        mode=MODE, scientific=False, level_tested=2,
        claims_self_improvement=False, claims_level3=False, claims_level4=False,
        note='Synthetic illustration, not a scientific result.',
        seed=int(seed), local_updates=bool(local_updates),
        split_digest=split_digest(split),
        holdout_reserved=HOLDOUT_FAMILY,
        development_family=DEV_FAMILY, shifted_family=SHIFTED_FAMILY,
        matched_proposals=PROPOSALS, matched_lookups=lookups['persistent_adaptive'],
        frozen_weights=list(frozen_before_eval['weights']),
        frozen_updates=frozen_before_eval['updates'],
        train=train_sum, development=dev_sum, shifted=shift_sum,
        persistent_minus_reset_dev=benefit,
        persistent_minus_reset_dev_mean=mean,
        persistent_minus_reset_shifted=shifted_benefit,
        illustration_label='synthetic_illustration_not_a_result',
        future_primary='mean persistent-minus-reset development best-score',
        future_labels=('e2_persistence_helps_transfer',
                       'e2_persistence_hurts_transfer',
                       'e2_transfer_not_established', 'incomplete'),
        cpu_memory=dict(adaptive_features=6, catalogue=12, proposals_per_task=PROPOSALS,
                        training_tasks=len(split['train']),
                        eval_tasks=len(split['development']) + len(split['shifted']),
                        persistent_updates=frozen_before_eval['updates'],
                        scientific_ledger_used=False),
    )


def future_protocol():
    """Design only. Not locked, not authorized, not executed."""
    return dict(
        scientific=False, authorized=False, locked=False, executed=False,
        training_families=list(TRAIN_FAMILIES),
        development_family=DEV_FAMILY,
        shifted_family=SHIFTED_FAMILY,
        untouched_holdout_family=HOLDOUT_FAMILY,
        independence_unit='synthetic_task_instance_seed_bundle',
        primary='mean_over_dev_instances(best_persistent - best_reset)',
        interval='student_t_95',
        n_proposed=10,
        df=9,
        practical_margin=0.05,
        resource_caps=dict(synthetic_lookups_per_method=10 * (6 * 4 + 2 * 4 + 2 * 4),
                           real_env_steps=0, imagined_transitions=0, wall_s=0,
                           scientific_ledger=False),
        leakage_controls=('oracle_eval_only', 'holdout_untouched',
                          'no_dev_update_to_global', 'no_h12_h16_returns'),
        negative_labels=('e2_persistence_hurts_transfer',
                         'e2_transfer_not_established', 'incomplete'),
        blocked=('H17', 'real_RL_rollout', 'scientific_ledger'),
    )
