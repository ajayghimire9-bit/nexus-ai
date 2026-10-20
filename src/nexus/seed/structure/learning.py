"""Source-only conflict induction; exactly one nested validation decision per edit."""
from dataclasses import dataclass
from collections import defaultdict
import statistics as st
from nexus.evolution1.catalogue import digest
from .features import evaluate, grammar, complexity


@dataclass(frozen=True)
class Example:
    episode: str
    state: object
    action: int
    outcome: bool

    def __post_init__(self):
        if type(self.episode) is not str or self.action not in (0, 1) or type(self.action) is not int or type(self.outcome) is not bool: raise ValueError('observed_example')


def base(x):
    # No task IDs, arbitrary names, source tags, timestamps or outcomes.
    attrs = x.state.current[0]['attributes'] if x.state.current else {}
    return (x.action, attrs.get('flag'))


def key(x, features): return base(x) + tuple(evaluate(p, x.state, x.state.current[0]['id']) for p in features)


def fit_table(rows, features):
    groups = defaultdict(list)
    for x in rows: groups[key(x, features)].append(int(x.outcome))
    return {k: st.mean(v) for k, v in groups.items()}


def predict_table(model, x, features): return model.get(key(x, features), .5)


def errors(rows, model, features): return [(predict_table(model, x, features)-int(x.outcome))**2 for x in rows]


def conflicts(rows):
    groups = defaultdict(list)
    for x in rows: groups[base(x)].append(x)
    found = []
    for k, group in groups.items():
        zero = {x.episode for x in group if not x.outcome}; one = {x.episode for x in group if x.outcome}
        # Recurrence, not just one contradictory pair in a single episode.
        if len(zero) >= 2 and len(one) >= 2:
            found.append(dict(base=list(k), zero=sorted(zero), one=sorted(one)))
    return found


def induce(train, validation, *, candidates=None, margin=.02, penalty=.001, cap=90, retained=(), baseline_features=()):
    if {x.episode for x in train} & {x.episode for x in validation}: raise ValueError('source_validation_overlap')
    baseline_features=list(baseline_features)
    old = fit_table(train, baseline_features); recurrence = conflicts(train)
    candidates = grammar() if candidates is None else candidates
    if len(candidates) > cap: raise ValueError('candidate_cap')
    records = []
    if not recurrence: return dict(accepted=False, feature=None, reason='no_recurrent_conflict', proposals=[], candidates_evaluated=0)
    for p in candidates:
        model = fit_table(train, baseline_features+[p]); loss = st.mean(errors(train, model, baseline_features+[p]))
        records.append(dict(feature=p, fit_brier=loss, objective=loss+penalty*complexity(p), complexity=complexity(p)))
    chosen = min(records, key=lambda r: (r['objective'], r['complexity'], digest(r['feature'])))
    p = chosen['feature']; new = fit_table(train, baseline_features+[p])
    before = st.mean(errors(validation, old, baseline_features)); after = st.mean(errors(validation, new, baseline_features+[p]))
    forgetting = (st.mean(errors(retained, new, baseline_features+[p]))-st.mean(errors(retained, old, baseline_features))) if retained else 0.
    accepted = before-after >= margin and forgetting <= .01
    for record in records:
        record['status']=('retained' if accepted else 'validation_rejected') if record is chosen else 'training_rejected'
    return dict(accepted=accepted, feature=p if accepted else None, proposed_feature=p,
                reason='accepted' if accepted else 'validation_or_retention_rejected',
                before=before, after=after, forgetting=forgetting, recurrence=recurrence,
                validation_episodes=sorted(x.episode for x in validation),
                train_episodes=sorted(x.episode for x in train), proposals=records,
                candidates_evaluated=len(records), validation_candidates=1,
                validation_used_once=True)
