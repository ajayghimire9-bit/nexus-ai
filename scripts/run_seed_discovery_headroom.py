"""One bounded symbolic preflight through the existing Sandbox/E1 ledger.

Reuses the persistent-assistant supervisor's process-tree meter. Does not start
a model server, modify its runtime, or run a retained-abstraction comparison.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nexus.seed.experimental import Sandbox, write_new
from nexus.seed.local_model_runtime import file_hash
from nexus.seed.discovery_headroom import run, summarize

CONFIG = ROOT/'configs/seed_discovery_headroom.json'
PROTOCOL = ROOT/'docs/NEXUS_SEED_DISCOVERY_HEADROOM_PROTOCOL.md'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def load_meter():
    spec = importlib.util.spec_from_file_location('existing_assistant_supervisor', ROOT/'scripts/run_seed_assistant_benchmark_v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.process_snapshot


def worker(config, directory):
    expected = ROOT/'runs/experimental/attempts'/config['id']
    if directory.resolve() != expected.resolve():
        raise ValueError('host_owned_attempt_required')
    registration = json.loads((directory/'registration.json').read_text())
    if not any(r['run_id'] == config['id'] and r.get('registration') == registration
               for r in Sandbox(ROOT).records('reserved')):
        raise ValueError('durable_reservation_required')
    if registration['source_sha'] != git('rev-parse', 'HEAD') or registration['config_sha256'] != file_hash(CONFIG):
        raise ValueError('stale_registration')
    if registration['protocol_sha256'] != file_hash(PROTOCOL):
        raise ValueError('stale_protocol')
    resource.setrlimit(resource.RLIMIT_CPU, (config['cpu_s'], config['cpu_s']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20*1024*1024, 20*1024*1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with (directory/'raw.jsonl').open('x') as f:
        def emit(row):
            f.write(json.dumps(row, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
        run(config, emit)


def host(config):
    if git('status', '--porcelain') or git('branch', '--show-current') == 'main':
        raise ValueError('clean_committed_research_branch_required')
    if file_hash(ROOT/'src/nexus/seed/local_model_runtime.py') != config['runtime_source_sha256']:
        raise ValueError('persistent_runtime_changed')
    meter = load_meter()
    sandbox = Sandbox(ROOT)
    with sandbox.locked():
        if any(r['run_id'] == config['id'] for r in sandbox.records('reserved')):
            raise ValueError('consumed_one_run_no_retry')
        grants = sandbox.records('grant')
        carry = grants[0]['carried_used_s'] if grants else config['carried_used_s']
        used = carry + sandbox.used_s()
        if used < config['carried_used_s']:
            raise ValueError('ledger_gap_reconcile_explicitly_before_run')
        if used + config['wall_s'] > 3600 or config['wall_s'] > 900:
            raise ValueError('session_cap')
        caps = dict(wall_s=config['wall_s'], cpu_s=config['cpu_s'], memory_mb=config['memory_mb'],
                    real_steps=140, imagined_transitions=0, updates=0)
        sandbox.grant(config['id'], 'standing-human-grant-2026-10-16',
                      'Owner-requested baseline-first source workload preflight '+file_hash(CONFIG),
                      caps, 3600, carry, memory_policy='sampled_rss')
        directory = sandbox.directory/'attempts'/config['id']; directory.mkdir()
        registration = dict(source_sha=git('rev-parse', 'HEAD'), config_sha256=file_hash(CONFIG),
                            protocol_sha256=file_hash(PROTOCOL), runtime_source_sha256=config['runtime_source_sha256'],
                            carried_used_s=used, caps=caps, mode=config['mode'])
        write_new(directory/'registration.json', registration)
        sandbox.append('reserved', dict(run_id=config['id'], wall_cap_s=config['wall_s'],
                       registration=registration, spec=dict(mode='exploration', recipe=dict(adapter='discovery_headroom'))))
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic(); peak = 0.; cpus = {}; stop = None
        with (directory/'worker.log').open('xb') as log:
            proc = subprocess.Popen([sys.executable, '-B', __file__, '--worker', '--directory', str(directory)],
                                    cwd=ROOT, stdout=log, stderr=log, start_new_session=True,
                                    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
            try:
                while proc.poll() is None:
                    rss, samples = meter(proc.pid); peak = max(peak, rss)
                    for pid, cpu in samples.items(): cpus[pid] = max(cpus.get(pid, 0), cpu)
                    if time.monotonic()-started >= config['wall_s']: stop = 'wall_cap'
                    elif sum(cpus.values()) >= config['cpu_s']: stop = 'cpu_cap'
                    elif peak >= config['memory_mb']: stop = 'memory_cap'
                    if stop: break
                    time.sleep(.1)
            except Exception as exc:
                stop = 'supervisor_error:'+type(exc).__name__
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        wall = time.monotonic()-started
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
        if cpu > config['cpu_s']: stop = stop or 'post_cpu_cap'
        charge = math.ceil(wall)+1
        sandbox.append('settled', dict(run_id=config['id'], charged_wall_s=charge,
                       status='incomplete' if stop or proc.returncode else 'complete_development'))
        data = (directory/'raw.jsonl').read_bytes() if (directory/'raw.jsonl').exists() else b''
        records = []
        for line in data.splitlines():
            try: records.append(json.loads(line))
            except ValueError: stop = stop or 'invalid_raw_tail'
        try: summary = summarize(records, config)
        except Exception as exc:
            summary = dict(declared_complete=False, verdict='INVALID', error=type(exc).__name__)
        if stop or proc.returncode:
            summary.update(declared_complete=False, verdict='INCOMPLETE', ready_for_learning_study=False)
        raw = ROOT/'artifacts/seed_discovery_headroom_raw.jsonl'
        with raw.open('xb') as f: f.write(data)
        result = dict(registration=registration, summary=summary, raw_sha256=file_hash(raw),
                      resources=dict(wall_s=wall, worker_cpu_s=cpu, charged_wall_s=charge,
                                     peak_sampled_aggregate_rss_mb=peak, stop_reason=stop,
                                     worker_returncode=proc.returncode, model_calls=0, new_environment_steps=0,
                                     session_used_s=carry+sandbox.used_s(),
                                     session_remaining_s=3600-carry-sandbox.used_s(),
                                     memory_policy='100 ms summed host/worker RSS; shared pages can double count'))
        write_new(ROOT/'artifacts/seed_discovery_headroom.json', result)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); p.add_argument('--worker', action='store_true'); p.add_argument('--directory')
    args = p.parse_args(); config = json.loads(CONFIG.read_text())
    if args.worker: worker(config, Path(args.directory))
    else: host(config)
