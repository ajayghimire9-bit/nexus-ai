"""Optional facade over the existing Session journal; no second database.

Inspection and prediction are pure. Only explicit owner requests append data.
Replay validates typed records; it never steps a world or trains a neural model.
"""
import copy
import json
from .state import State, observe, token
from .features import evaluate, validate
from .mechanisms import mechanism, execute, plan
from .learning import Example, induce, fit_table, predict_table, key
from .investigation import learn, run as run_investigation
from nexus.evolution1.catalogue import digest


def initial():
    return dict(state=State(), examples={}, used_validation=[], mechanisms={}, numeric={}, features=[],
                investigations=[], investigations_performed=[], changes=[], versions=[], costs=dict(search_candidates=0, validation_candidates=0,observed_history_reads=0))


def apply(view, command):
    if type(command) is not dict or set(command) != {'op', 'data'}: raise ValueError('structure_record_schema')
    op, data = command['op'], command['data']
    if type(data) is not dict: raise ValueError('typed_structure_data')
    out = copy.deepcopy(view)
    if op == 'reset' and set(data) == {'episode'}:
        token(data['episode'])
        if data['episode'] in {e.episode for e in out['examples'].values()} or data['episode'] == out['state'].episode: raise ValueError('unique_episode_identity')
        out['state'] = State(episode=data['episode'])
    elif op == 'observe' and set(data) == {'observation'}:
        out['state'] = observe(out['state'], data['observation'])
    elif op == 'example' and set(data) == {'id', 'action', 'outcome', 'role'}:
        token(data['id'])
        if data['role'] not in ('source', 'source_validation') or data['id'] in out['examples'] or len(out['examples']) >= 96 or not out['state'].current: raise ValueError('source_example_contract')
        example = Example(out['state'].episode, copy.deepcopy(out['state']), data['action'], data['outcome'])
        out['examples'][data['id']] = example
        out.setdefault('roles', {})[data['id']] = data['role']
    elif op == 'install' and set(data) == {'mechanism'}:
        p = mechanism(data['mechanism'])
        if p['origin'] != 'supplied' or p['id'] in out['mechanisms'] or len(out['mechanisms']) >= 16: raise ValueError('supplied_install_only')
        out['mechanisms'][p['id']] = p
    elif op=='numeric' and set(data)=={'id','checkpoint','evidence'}:
        from .neural import NumericResidual
        token(data['id'])
        if data['id'] in out['numeric'] or len(out['numeric'])>=4 or type(data['evidence']) is not list or not data['evidence'] or len(data['evidence'])>64 or any(type(x) is not str or len(x)>128 for x in data['evidence']):raise ValueError('numeric_provenance_and_cap')
        NumericResidual.load(data['checkpoint'])
        out['numeric'][data['id']]=copy.deepcopy(data)
    elif op == 'review' and set(data) == {'train', 'validation', 'result'}:
        train, validation = data['train'], data['validation']
        if type(train) is not list or type(validation) is not list or len(set(train)) != len(train) or len(set(validation)) != len(validation) or not train or not validation: raise ValueError('review_partitions')
        if any(x not in out['examples'] for x in train+validation): raise ValueError('missing_source_evidence')
        if any(out['roles'][x] != 'source' for x in train) or any(out['roles'][x] != 'source_validation' for x in validation): raise ValueError('review_feedback_boundary')
        if set(validation) & set(out['used_validation']): raise ValueError('one_use_validation')
        if sum('result' in x for x in out['changes'])>=8:raise ValueError('review_attempt_cap_includes_rejections')
        if len(out['features']) >= 8: raise ValueError('feature_library_cap')
        expected = induce([out['examples'][x] for x in train], [out['examples'][x] for x in validation],baseline_features=out['features'])
        if digest(expected) != digest(data['result']): raise ValueError('review_evidence_mismatch')
        out['versions'].append(copy.deepcopy(out['features']))
        if expected['accepted']: out['features'].append(expected['feature'])
        out['used_validation'] += validation
        out['changes'].append(copy.deepcopy(data))
        out['costs']['search_candidates'] += expected['candidates_evaluated']
        out['costs']['validation_candidates'] += expected.get('validation_candidates', 0)
    elif op == 'investigation' and set(data) == {'source_ids', 'probes', 'program'}:
        if len(out['investigations']) >= 8: raise ValueError('investigation_library_cap')
        traces = investigation_traces(out,data['source_ids'],data['probes'])
        if digest(learn(traces)) != digest(data['program']): raise ValueError('investigation_evidence_mismatch')
        out['investigations'].append(copy.deepcopy(data))
    elif op == 'rollback' and data == {}:
        if not out['versions']: raise ValueError('no_prior_library')
        out['features'] = out['versions'].pop()
        out['changes'].append(dict(reason='explicit_rollback'))
    elif op == 'investigation_use' and set(data)=={'index','budget','result'}:
        expected=investigate(out,data['index'],data['budget'])
        if digest(expected)!=digest(data['result']):raise ValueError('investigation_replay')
        out['investigations_performed'].append(copy.deepcopy(data))
        out['costs']['observed_history_reads']+=expected['observed_history_reads']
    else: raise ValueError('structure_operation_schema')
    return out


def replay(session):
    out = initial(); count = 0
    for event in session.journal.snapshot():
        if event.kind == 'seed_structure':
            out = apply(out, json.loads(event.payload_json)); count += 1
    if count > 384: raise ValueError('structure_journal_cap')
    return out


def validate_event(payload, session):
    if sum(e.kind == 'seed_structure' for e in session.journal.snapshot()) >= 384: raise ValueError('structure_journal_cap')
    apply(replay(session), payload)


def investigation_traces(view, ids, probes):
    if type(ids) is not list or len(ids)!=len(set(ids)) or any(i not in view['examples'] or view['roles'][i]!='source' for i in ids): raise ValueError('investigation_source_only')
    if type(probes) is not list or not 1<=len(probes)<=16: raise ValueError('bound_probe_vocabulary')
    for p in probes:validate(p)
    rows=[]
    for i in ids:
        x=view['examples'][i];answers=[evaluate(p,x.state,x.state.current[0]['id']) for p in probes]
        if any(type(a) is not bool for a in answers):raise ValueError('unknown_source_probe')
        rows.append(dict(role='source',episode=x.episode,answers=answers,hypothesis=int(x.outcome)))
    return rows


def investigate(view,index,budget):
    if type(index) is not int or not 0<=index<len(view['investigations']):raise ValueError('known_investigation')
    item=view['investigations'][index]
    def probe(i):
        if not view['state'].current:raise ValueError('observe_before_probe')
        return evaluate(item['probes'][i],view['state'],view['state'].current[0]['id'])
    result=run_investigation(item['program'],probe,budget=budget)
    result['observed_history_reads']=result['real_probes'];result['real_probes']=0
    result['transcript']=[dict(t,real=False,source='observed_history') for t in result['transcript']]
    return result


def inspect(session):
    v = replay(session)
    return dict(optional=True, experimental=True, state=v['state'].wire(), features=v['features'],
                derived=[dict(binding=e['id'],feature=p,value=evaluate(p,v['state'],e['id']),source='inferred') for e in v['state'].current for p in v['features']],
                mechanisms=list(v['mechanisms'].values()), investigations=v['investigations'],
                numeric=[dict(id=k,checkpoint_sha256=digest(p['checkpoint']),evidence=p['evidence']) for k,p in v['numeric'].items()],
                investigations_performed=v['investigations_performed'],
                changes=v['changes'], evidence=list(v['examples']), costs=v['costs'],
                library_sha256=digest(dict(features=v['features'], mechanisms=v['mechanisms'], numeric=v['numeric'], investigations=v['investigations'])))


def request(session, wire):
    op = wire.get('op')
    if op == 'structure_inspect' and set(wire) == {'op'}: return inspect(session)
    if session.stopped or session.cancelled.is_set(): raise ValueError('seed_stopped')
    v = replay(session)
    if op=='structure_predict_numeric' and set(wire)=={'op','id','binding','inputs','output','supplied_prediction'}:
        from .neural import NumericResidual,execute_numeric
        if wire['id'] not in v['numeric']:raise ValueError('known_numeric_mechanism')
        result=execute_numeric(NumericResidual.load(v['numeric'][wire['id']]['checkpoint']),v['state'],wire['binding'],wire['inputs'],wire['output'],wire['supplied_prediction'])
        if 'state' in result:result['state']=result['state'].wire()
        return result
    if op in ('structure_predict', 'structure_plan'):
        if op == 'structure_predict' and set(wire) == {'op', 'action'}:
            rows = [e for k, e in v['examples'].items() if v['roles'][k] == 'source']
            x = Example(v['state'].episode, v['state'], wire['action'], False)
            model=fit_table(rows,v['features'])
            return dict(probability=predict_table(model, x, v['features']),
                        hypothetical=True, outcome='bernoulli', known=key(x,v['features']) in model)
        if op == 'structure_plan' and set(wire) == {'op', 'binding', 'goal'}:
            return plan(v['state'], list(v['mechanisms'].values()), wire['binding'], wire['goal'])
        raise ValueError('typed_structure_query')
    names = {'structure_reset': ('reset', {'episode'}), 'structure_observe': ('observe', {'observation'}),
             'structure_example': ('example', {'id', 'action', 'outcome', 'role'}),
             'structure_install': ('install', {'mechanism'}), 'structure_rollback': ('rollback', set())}
    names['structure_install_numeric']=('numeric',{'id','checkpoint','evidence'})
    if op in names:
        kind, fields = names[op]
        if set(wire) != fields | {'op'}: raise ValueError('typed_structure_request')
        payload = dict(op=kind, data={k:wire[k] for k in fields})
    elif op == 'structure_review' and set(wire) == {'op', 'train', 'validation'}:
        # Validate IDs and roles before fitting, never expose final rows here.
        for name in ('train', 'validation'):
            if type(wire[name]) is not list or any(x not in v['examples'] for x in wire[name]): raise ValueError('review_evidence')
        if any(v['roles'][x] != 'source' for x in wire['train']) or any(v['roles'][x] != 'source_validation' for x in wire['validation']) or set(wire['validation']) & set(v['used_validation']): raise ValueError('review_feedback_boundary')
        result = induce([v['examples'][x] for x in wire['train']], [v['examples'][x] for x in wire['validation']],baseline_features=v['features'])
        payload = dict(op='review', data=dict(train=wire['train'], validation=wire['validation'], result=result))
    elif op == 'structure_learn_investigation' and set(wire) == {'op', 'source_ids', 'probes'}:
        traces=investigation_traces(v,wire['source_ids'],wire['probes'])
        payload = dict(op='investigation', data=dict(source_ids=wire['source_ids'],probes=wire['probes'], program=learn(traces)))
    elif op == 'structure_investigate' and set(wire) == {'op', 'index', 'budget'}:
        # These read already observed history; they are metered retrievals, not
        # claimed new environment interactions. External run(callback) meters
        # real probes separately when a real observation backend is provided.
        result=investigate(v,wire['index'],wire['budget'])
        payload=dict(op='investigation_use',data=dict(index=wire['index'],budget=wire['budget'],result=result))
    else: raise ValueError('typed_structure_request')
    validate_event(payload, session)
    session.event('seed_structure', payload)
    return inspect(session)
