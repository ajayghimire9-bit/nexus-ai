"""Owner-controlled local development host, not an OS security sandbox.

Reuses E1 canonical hashes/Journal. Candidates never receive grants, assessment
paths, or the host's ledger. Only vetted typed workers are dispatched; no eval,
pickle, shell commands, runtime installs, or automatic stable-code promotion.
"""
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from nexus.evolution1.catalogue import canonical, digest
from nexus.evolution1.fixtures import Event, Journal, verify_journal

ROLES = ('train', 'development', 'validation', 'confirmation')
NAME = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
CAPS = ('wall_s', 'cpu_s', 'memory_mb', 'real_steps', 'imagined_transitions', 'updates')


def number(value, minimum=0, maximum=1e12):
    if type(value) not in (float, int) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('finite_numeric_value_required')
    return value


def name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError('simple_identifier_required')
    return value


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 10_000_000:
        raise ValueError('small_regular_json_required')
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise ValueError('symlink_directory')
    with path.open('x', encoding='utf-8') as f:
        f.write(canonical(value))
        f.flush()
        os.fsync(f.fileno())
    path.chmod(0o600)


def data_rows(data):
    if type(data) is not dict or set(data) != {'rows'} or type(data['rows']) is not list or not 2 <= len(data['rows']) <= 10000:
        raise ValueError('dataset_rows_schema')
    width = None
    ids = set()
    for row in data['rows']:
        if type(row) is not dict or set(row) != {'id', 'x', 'y'}:
            raise ValueError('dataset_row_schema')
        key = name(row['id'])
        if key in ids or type(row['x']) is not list or not 1 <= len(row['x']) <= 128:
            raise ValueError('duplicate_or_invalid_row')
        ids.add(key)
        width = width or len(row['x'])
        if len(row['x']) != width:
            raise ValueError('inconsistent_width')
        for value in row['x'] + [row['y']]:
            number(value, -1e6, 1e6)
    return width, ids


def recipe(value):
    fields = {'hidden', 'activation', 'optimizer', 'learning_rate', 'updates', 'seed'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('typed_recipe_required')
    h = value['hidden']
    if type(h) is not list or len(h) > 4 or any(type(n) is not int or not 1 <= n <= 256 for n in h):
        raise ValueError('bounded_architecture_required')
    if value['activation'] not in ('tanh', 'relu', 'silu') or value['optimizer'] not in ('adam', 'sgd'):
        raise ValueError('vetted_operator_required')
    number(value['learning_rate'], 1e-6, 1)
    if type(value['updates']) is not int or not 1 <= value['updates'] <= 100000:
        raise ValueError('bounded_update_count_required')
    if type(value['seed']) is not int or not 0 <= value['seed'] < 2**31:
        raise ValueError('seed_required')
    return value


def frozen_protocol(repository, protocol, model_hash, assessment_hash):
    fields = {'commit','path','sha256','candidate_sha256','assessment_sha256'}
    if type(protocol) is not dict or set(protocol) != fields:
        raise ValueError('frozen_confirmation_protocol_required')
    if (type(protocol['commit']) is not str or not re.fullmatch('[0-9a-f]{40}',protocol['commit']) or
        type(protocol['path']) is not str or Path(protocol['path']).is_absolute() or '..' in Path(protocol['path']).parts):
        raise ValueError('committed_protocol_reference_required')
    try:
        content = subprocess.check_output(['git','show',protocol['commit']+':'+protocol['path']],cwd=repository,stderr=subprocess.PIPE)
        subprocess.run(['git','merge-base','--is-ancestor',protocol['commit'],'HEAD'],cwd=repository,check=True,capture_output=True)
        locked = json.loads(content)
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise ValueError('invalid_committed_protocol') from exc
    if (hashlib.sha256(content).hexdigest() != protocol['sha256'] or
        protocol['candidate_sha256'] != model_hash or protocol['assessment_sha256'] != assessment_hash or
        type(locked) is not dict or locked.get('schema') != 'experimental_confirmation_v1' or
        locked.get('candidate_sha256') != model_hash or locked.get('assessment_sha256') != assessment_hash or
        locked.get('primary_metric') != 'mse' or type(locked.get('independent_unit')) is not str or
        not locked['independent_unit'].strip()):
        raise ValueError('protocol_binding_mismatch')
    number(locked.get('success_mse_at_most'))
    return locked


class Sandbox:
    def __init__(self, repository, directory=None):
        self.repository = Path(repository).resolve()
        self.directory = Path(directory or self.repository/'runs/experimental').resolve()
        if self.directory == self.repository or not (self.repository/'AGENTS.md').is_file():
            raise ValueError('repository_and_private_run_directory_required')
        if any(self.directory.is_relative_to(self.repository/p) for p in ('artifacts','configs','docs','src','.git')):
            raise ValueError('private_run_store_cannot_be_historical_or_source_tree')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    @contextmanager
    def locked(self):
        with (self.directory/'host.lock').open('a') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise ValueError('host_busy_no_parallel_budget_spending') from e
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def events(self):
        events = []
        for i, path in enumerate(sorted((self.directory/'events').glob('*.json'))):
            if path.name != f'{i:06}.json':
                raise ValueError('journal_gap')
            events.append(Event(**read(path)))
        verify_journal(events)
        return events

    def append(self, kind, payload):
        old = self.events()
        journal = Journal()
        for event in old:
            journal.append(event.kind, json.loads(event.payload_json))
        event = journal.append(kind, {'host_mode': 'experimental_local', **payload})
        write_new(self.directory/'events'/f'{len(old):06}.json', asdict(event))
        return event.fingerprint

    def records(self, kind):
        return [json.loads(e.payload_json) for e in self.events() if e.kind == kind]

    def register(self, identifier, role, path, owner, provenance):
        name(identifier)
        if role not in ROLES or not owner.strip() or not provenance.strip():
            raise ValueError('owner_role_and_collection_provenance_required')
        data = read(path)
        width, ids = data_rows(data)
        for existing in (self.directory/'datasets').glob('*.json'):
            record = read(existing)
            _, prior = data_rows(record['data'])
            observations = {digest({'x':r['x'],'y':r['y']}) for r in record['data']['rows']}
            if prior & ids or observations & {digest({'x':r['x'],'y':r['y']}) for r in data['rows']}:
                raise ValueError('dataset_overlap_or_relabeling')
        record = dict(id=identifier, role=role, owner=owner, provenance=provenance,
                      data=data, data_sha256=digest(data), width=width)
        write_new(self.directory/'datasets'/f'{identifier}.json', record)
        self.append('dataset_registered', {k: v for k, v in record.items() if k != 'data'})
        return record['data_sha256']

    def dataset(self, identifier, role):
        row = read(self.directory/'datasets'/f'{name(identifier)}.json')
        if row['role'] != role or row['data_sha256'] != digest(row['data']):
            raise ValueError('dataset_role_or_hash_mismatch')
        data_rows(row['data'])
        # Registration is independently anchored in the immutable host journal.
        if not any(r['id'] == identifier and r['role'] == role and r['data_sha256'] == row['data_sha256']
                   for r in self.records('dataset_registered')):
            raise ValueError('unregistered_dataset')
        return row

    def grant(self, identifier, owner, reason, caps, session_limit_s, carried_used_s,
              device='cpu', memory_policy='kernel'):
        name(identifier)
        if set(caps) != set(CAPS) or not owner.strip() or not reason.strip():
            raise ValueError('explicit_owner_budget_required')
        for k, v in caps.items():
            number(v, .001 if k=='wall_s' else 1 if k in ('cpu_s','memory_mb') else 0)
        if any(type(caps[k]) is not int for k in ('cpu_s', 'memory_mb', 'real_steps', 'imagined_transitions', 'updates')):
            raise ValueError('integer_work_caps_required')
        number(session_limit_s, 1)
        number(carried_used_s)
        prior = self.records('grant')
        if prior and carried_used_s != prior[0]['carried_used_s']:
            raise ValueError('cannot_reset_carried_session_usage')
        if device not in ('cpu', 'gpu'):
            raise ValueError('device_schema')
        if memory_policy not in ('kernel','sampled_rss'):
            raise ValueError('explicit_memory_enforcement_policy')
        row = dict(id=identifier, owner=owner, reason=reason, caps=caps, device=device,
                   session_limit_s=session_limit_s, carried_used_s=carried_used_s,
                   memory_policy=memory_policy)
        write_new(self.directory/'grants'/f'{identifier}.json', row)
        self.append('grant', row)
        return digest(row)

    def used_s(self):
        reserved = {r['run_id']: r for r in self.records('reserved')}
        settled = {r['run_id']: r for r in self.records('settled')}
        return sum(settled[k]['charged_wall_s'] if k in settled else v['wall_cap_s']
                   for k, v in reserved.items())

    def fork(self, identifier):
        name(identifier)
        path = self.directory/'candidates'/identifier
        branch = 'codex/experimental-'+identifier
        subprocess.run(['git', 'worktree', 'add', '-b', branch, str(path), 'HEAD'],
                       cwd=self.repository, check=True, capture_output=True)
        self.append('workspace_created', dict(id=identifier, path=str(path), branch=branch))
        return str(path)

    def execute(self, spec, grant_id):
        """Call under locked(). Budget reservation is durable BEFORE dispatch."""
        fields = {'id', 'mode', 'recipe', 'train', 'development', 'model_run', 'assessment', 'protocol', 'gate'}
        if type(spec) is not dict or set(spec) != fields:
            raise ValueError('lightweight_manifest_schema')
        run_id = name(spec['id'])
        mode = spec['mode']
        if mode not in ('exploration', 'validation', 'confirmation'):
            raise ValueError('explicit_evidence_mode_required')
        if any(r['run_id'] == run_id for r in self.records('reserved')):
            raise ValueError('run_id_already_consumed')
        grant = read(self.directory/'grants'/f'{name(grant_id)}.json')
        if not any(digest({k: v for k, v in r.items() if k != 'host_mode'}) == digest(grant)
                   for r in self.records('grant')):
            raise ValueError('grant_hash_mismatch')
        if grant['device'] != 'cpu':
            raise ValueError('gpu_memory_enforcement_backend_unavailable_no_execution')
        if grant['memory_policy']=='kernel' and not sys.platform.startswith('linux'):
            raise ValueError('kernel_memory_enforcement_unavailable_explicit_sampled_rss_approval_required')
        caps = grant['caps']
        remaining = grant['session_limit_s'] - grant['carried_used_s'] - self.used_s()
        if remaining <= 0:
            raise ValueError('session_budget_exhausted')
        inputs = {}
        dataset_hashes = {}
        if mode == 'exploration':
            recipe(spec['recipe'])
            if any(spec[k] is not None for k in ('model_run', 'assessment', 'protocol', 'gate')):
                raise ValueError('exploration_cannot_access_assessment')
            for k, role in (('train', 'train'), ('development', 'development')):
                row = self.dataset(spec[k], role)
                inputs[k] = row['data']
                dataset_hashes[k] = row['data_sha256']
            if spec['recipe']['updates'] > caps['updates']:
                raise ValueError('update_cap')
            if data_rows(inputs['train'])[0] != data_rows(inputs['development'])[0]:
                raise ValueError('input_width_mismatch')
        else:
            if any(spec[k] is not None for k in ('train', 'development', 'recipe')):
                raise ValueError('assessment_no_training')
            row = self.dataset(spec['assessment'], mode)
            if any(row['data_sha256'] in r['dataset_hashes'].values()
                   for r in self.records('reserved') if r['mode'] != 'exploration'):
                raise ValueError('assessment_consumed_even_if_previous_run_failed')
            result = self.result(spec['model_run'])
            if result['mode'] != 'exploration' or result['status'] != 'complete_development':
                raise ValueError('complete_candidate_required')
            inputs = dict(assessment=row['data'], model=result['worker']['model'])
            incumbent = self.incumbent()
            inputs['baseline_model'] = self.result(incumbent)['worker']['model'] if incumbent else None
            inputs['baseline_run'] = incumbent
            dataset_hashes['assessment'] = row['data_sha256']
            if mode == 'validation':
                if type(spec['gate']) is not dict or set(spec['gate']) != {'minimum_gain','maximum_regression'}:
                    raise ValueError('predeclared_validation_gate_required')
                for value in spec['gate'].values():
                    number(value)
            elif spec['gate'] is not None:
                raise ValueError('confirmation_cannot_promote')
            if mode == 'confirmation':
                protocol = spec['protocol']
                if type(protocol) is not dict or set(protocol) != {'commit', 'path', 'sha256', 'candidate_sha256', 'assessment_sha256'}:
                    raise ValueError('frozen_confirmation_protocol_required')
                if subprocess.check_output(['git','diff','HEAD','--','src','scripts'],cwd=self.repository):
                    raise ValueError('confirmation_requires_committed_implementation')
                frozen_protocol(self.repository,protocol,digest(inputs['model']),row['data_sha256'])
            elif spec['protocol'] is not None:
                raise ValueError('unexpected_protocol')
        directory = self.directory/'attempts'/run_id
        directory.mkdir(parents=True, mode=0o700)
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.repository, text=True).strip()
        sources = {p: hashlib.sha256((self.repository/p).read_bytes()).hexdigest() for p in (
            'src/nexus/seed/experimental.py', 'src/nexus/seed/experimental_worker.py',
            'src/nexus/nn/factory.py', 'src/nexus/nn/activations.py')}
        wall_cap = min(caps['wall_s'], remaining)
        request = dict(mode=mode, recipe=spec['recipe'], inputs=inputs, caps=caps,
                       memory_policy=grant['memory_policy'])
        write_new(directory/'input.json', request)
        self.append('reserved', dict(run_id=run_id, mode=mode, spec=spec, spec_sha256=digest(spec),
                    grant=grant_id, dataset_hashes=dataset_hashes, wall_cap_s=wall_cap,
                    revision=revision, source_hashes=sources,
                    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=self.repository))))
        started = time.monotonic()
        reason = None
        proc = None
        rss_mb = 0.0
        output = None
        try:
            env = {k: v for k, v in os.environ.items() if k in ('PATH','SYSTEMROOT','TMPDIR','PYTHONPATH')}
            env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                       CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
            env['PYTHONPATH'] = str(self.repository/'src')+os.pathsep+env.get('PYTHONPATH','')
            with (directory/'stdout.txt').open('xb') as out, (directory/'stderr.txt').open('xb') as err:
                proc = subprocess.Popen([sys.executable, '-m', 'nexus.seed.experimental_worker',
                       str(directory/'input.json'), str(directory/'output.json')],
                       cwd=directory, env=env, stdout=out, stderr=err, start_new_session=True)
                while proc.poll() is None:
                    elapsed = time.monotonic()-started
                    sample = subprocess.run(['ps','-o','rss=','-p',str(proc.pid)], capture_output=True, text=True, timeout=.2)
                    if sample.stdout.strip():
                        rss_mb = max(rss_mb, float(sample.stdout.strip())/1024)
                    if elapsed >= wall_cap or rss_mb > caps['memory_mb']:
                        reason = 'wall_cap' if elapsed >= wall_cap else 'memory_cap'
                        os.killpg(proc.pid, signal.SIGKILL)
                        break
                    time.sleep(.03)
                proc.wait()
            if reason is None and proc.returncode:
                reason = 'worker_failed_or_cpu_limit'
            if reason is None:
                output = read(directory/'output.json')
                validate_output(output, spec, caps, inputs)
                if mode != 'exploration' and digest(output['model']) != digest(inputs['model']):
                    raise ValueError('assessment_changed_frozen_model')
                if any(hashlib.sha256((self.repository/p).read_bytes()).hexdigest() != h for p,h in sources.items()):
                    raise ValueError('source_changed_during_execution')
        except Exception as exc:
            reason = type(exc).__name__+': '+str(exc)
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        elapsed = time.monotonic()-started
        failure_status = 'incomplete_execution' if reason in ('wall_cap','memory_cap','worker_failed_or_cpu_limit') else 'invalid_integrity'
        result = dict(id=run_id, mode=mode, status=('complete_development' if mode=='exploration'
                      else 'complete_assessment') if reason is None else failure_status,
                      scientific_claim='development_only' if mode != 'confirmation' else 'registered_assessment_not_automatic_success',
                      failure=reason, wall_s=elapsed, peak_sampled_rss_mb=rss_mb,
                      charged_wall_s=elapsed, grant=grant_id, spec_sha256=digest(spec), revision=revision,
                      dataset_hashes=dataset_hashes, worker=output,
                      baseline_run=inputs.get('baseline_run'), memory_policy=grant['memory_policy'],
                      resource_upper_bounds=caps)
        write_new(directory/'result.json', result)
        self.append('settled', dict(run_id=run_id, charged_wall_s=elapsed,
                    result_sha256=digest(result), status=result['status']))
        return result

    def result(self, identifier):
        row = read(self.directory/'attempts'/f'{name(identifier)}'/'result.json')
        if not any(r['run_id']==identifier and r['result_sha256']==digest(row) for r in self.records('settled')):
            raise ValueError('result_integrity')
        return row

    def retain(self, assessment_run):
        """Change a sandbox pointer only. Never writes weights or Git stable refs."""
        candidate = self.result(assessment_run)
        if candidate['mode'] != 'validation' or candidate['status'] != 'complete_assessment':
            raise ValueError('independent_validation_required')
        if any(r['assessment']==assessment_run for r in self.records('retention_decision')):
            raise ValueError('assessment_promotion_already_decided')
        spec = next(r['spec'] for r in self.records('reserved') if r['run_id']==assessment_run)
        model_run = spec['model_run']
        metrics = candidate['worker']['metrics']
        minimum_gain = spec['gate']['minimum_gain']
        maximum_regression = spec['gate']['maximum_regression']
        if candidate['baseline_run'] != self.incumbent():
            raise ValueError('incumbent_changed_fresh_validation_required')
        accepted = metrics['baseline_mse']-metrics['mse'] > minimum_gain and metrics['worst_error_increase'] <= maximum_regression
        prior = self.incumbent()
        self.append('retention_decision', dict(assessment=assessment_run, accepted=accepted,
                    previous=prior, incumbent=model_run if accepted else prior,
                    minimum_gain=minimum_gain, maximum_regression=maximum_regression))
        return accepted

    def incumbent(self):
        rows = [json.loads(e.payload_json) for e in self.events() if e.kind in ('retention_decision','rollback')]
        return rows[-1]['incumbent'] if rows else None

    def rollback(self):
        current = self.incumbent()
        accepted = [r for r in self.records('retention_decision') if r['accepted'] and r['incumbent']==current]
        if not current or not accepted:
            raise ValueError('no_accepted_incumbent')
        previous = accepted[-1]['previous']
        if previous is not None:
            self.result(previous)
        self.append('rollback', dict(previous=current, incumbent=previous))
        return previous

    def view(self):
        rows = []
        for reserved in self.records('reserved'):
            try:
                row = self.result(reserved['run_id'])
                worker = row.get('worker') or {}
                rows.append(dict(id=row['id'], mode=row['mode'], status=row['status'], failure=row['failure'],
                    wall_s=row['wall_s'], memory_mb=row['peak_sampled_rss_mb'], revision=row['revision'],
                    metrics=worker.get('metrics'), curve=worker.get('curve', []),
                    resources=worker.get('resources'), model_sha256=digest(worker['model']) if 'model' in worker else None))
            except FileNotFoundError:
                rows.append(dict(id=reserved['run_id'],mode=reserved['mode'],status='reserved_or_interrupted',
                                 wall_s=reserved['wall_cap_s'],curve=[]))
        return dict(kind='experimental_local_evidence_separate_from_historical_research', experiments=rows,
                    incumbent=self.incumbent(), charged_wall_s=self.used_s(),
                    grants=self.records('grant'), security_sandbox=False, auto_promotion=False)


def validate_output(output, spec, caps, inputs=None):
    expected = {'metrics','curve','resources','model','runtime'}
    if type(output) is not dict or set(output) != expected:
        raise ValueError('complete_worker_output_required')
    metrics = output['metrics']
    if type(metrics) is not dict or set(metrics) != {'mse','baseline_mse','worst_error_increase'}:
        raise ValueError('required_metrics_missing')
    for key, value in metrics.items():
        number(value, -1e12 if key=='worst_error_increase' else 0)
    runtime = output['runtime']
    if (type(runtime) is not dict or set(runtime) != {'python','torch','device','threads'} or
        runtime['device'] != 'cpu' or type(runtime['threads']) is not int or runtime['threads']!=1 or
        not all(type(runtime[k]) is str and runtime[k] for k in ('python','torch'))):
        raise ValueError('runtime_provenance_required')
    work = output['resources']
    if set(work) != {'updates','real_steps','imagined_transitions','cpu_s','parameter_count',
                     'training_examples','development_examples','assessment_examples','network_forwards'}:
        raise ValueError('resource_schema')
    for k, value in work.items():
        number(value)
        if k != 'cpu_s' and type(value) is not int:
            raise ValueError('integer_resource_count')
        if k in caps and value > caps[k]:
            raise ValueError('reported_resource_cap')
    expected_updates = spec['recipe']['updates'] if spec['mode']=='exploration' else 0
    if work['updates'] != expected_updates or work['real_steps'] or work['imagined_transitions']:
        raise ValueError('unmetered_or_incomplete_operations')
    if inputs is not None:
        expected_counts = dict(
            training_examples=len(inputs['train']['rows'])*expected_updates if expected_updates else 0,
            development_examples=len(inputs['development']['rows'])*(expected_updates+1) if expected_updates else 0,
            assessment_examples=len(inputs['assessment']['rows']) if not expected_updates else 0,
            network_forwards=3*expected_updates+1+int(bool(inputs.get('baseline_model'))))
        if any(work[k] != n for k,n in expected_counts.items()):
            raise ValueError('incomplete_or_unmatched_example_accounting')
    if len(output['curve']) != expected_updates:
        raise ValueError('incomplete_learning_curve')
    for i, point in enumerate(output['curve'], 1):
        if set(point) != {'update','train_mse','development_mse'} or point['update'] != i:
            raise ValueError('learning_curve_grid')
        number(point['train_mse']); number(point['development_mse'])
    model = output['model']
    if type(model) is not dict or set(model) != {'schema','recipe','width','state'} or model['schema'] != 'experimental_numeric_mlp_v1':
        raise ValueError('complete_model_required')
    recipe(model['recipe'])
    if spec['mode']=='exploration' and model['recipe']!=spec['recipe']:
        raise ValueError('recipe_changed_during_execution')
    if type(model['width']) is not int or not 1 <= model['width'] <= 128 or type(model['state']) is not dict or not model['state']:
        raise ValueError('model_shape_schema')
    def finite_tree(value):
        if type(value) is list:
            if not value:
                raise ValueError('empty_model_tensor')
            for item in value:
                finite_tree(item)
        else:
            number(value, -1e12)
    for value in model['state'].values():
        finite_tree(value)
    digest(output)  # recursively rejects nonfinite values
