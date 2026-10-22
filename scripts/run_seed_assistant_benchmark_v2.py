"""One-shot persistent local-model study with an actor-aware resource supervisor."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
CONFIG=ROOT/'configs/seed_assistant_benchmark_v2.json'
PROTOCOL=ROOT/'docs/NEXUS_SEED_ASSISTANT_BENCHMARK_V2_PROTOCOL.md'


def read_records(path):
    if not path.exists():return []
    records=[]
    for i,line in enumerate(path.read_bytes().splitlines()):
        try:records.append(json.loads(line))
        except ValueError:records.append(dict(kind='invalid_record',line=i,bytes=len(line)))
    return records


def worker(args,config):
    from nexus.seed.experimental import Sandbox
    from nexus.seed.local_model_runtime import file_hash
    directory=Path(args.directory).resolve()
    expected=ROOT/'runs/experimental/attempts/seed-assistant-benchmark-v2-1'
    if directory!=expected.resolve() or not (directory/'registration.json').is_file():
        raise ValueError('registered host-owned worker directory required')
    registration=json.loads((directory/'registration.json').read_text())
    reserved=Sandbox(ROOT).records('reserved')
    if not any(r['run_id']==registration['run_id'] and r.get('registration')==registration for r in reserved):
        raise ValueError('durable resource reservation required')
    if (registration['config_sha256']!=file_hash(CONFIG) or registration['protocol_sha256']!=file_hash(PROTOCOL)
            or registration['source_sha']!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()):
        raise ValueError('worker source/configuration provenance mismatch')
    from nexus.seed.assistant_benchmark_v2 import run,intent_prompt,SCHEMA,validate_intent
    from nexus.seed.local_model_runtime import RuntimeConfig,PersistentLocalRuntime
    resource.setrlimit(resource.RLIMIT_CPU,(config['cpu_s'],config['cpu_s']))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(20_000_000,20_000_000))
    cfg=RuntimeConfig(model_path=args.model,executable=args.executable,**config['runtime'])
    directory=Path(args.directory)
    with (directory/'raw.jsonl').open('x') as stream:
        def emit(record):
            stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        # Technical integration check only, using a published source example.
        with PersistentLocalRuntime(cfg,directory/'integration-server.log') as runtime:
            if runtime.metadata['model_sha256']!=config['model_sha256']:
                raise ValueError('integration model hash mismatch')
            prompt=intent_prompt('Sum amounts per region, at least 5, largest first',
                                 {'region':{'inferred_type':'text'},'amount':{'inferred_type':'numeric'}})
            one=runtime.complete(prompt,SCHEMA)
            parsed=validate_intent(json.loads(one['content']))
            two=runtime.complete(prompt,SCHEMA)
            metadata=dict(runtime.metadata,settings=dict(runtime.metadata['settings'],model_path=Path(args.model).name))
            emit(dict(kind='live_integration',metadata=metadata,first=one,second=two,parsed=parsed,
                      passed=one['telemetry']['inference_ran'] is True and
                             two['telemetry']['generated_tokens']==0 and two['telemetry']['application_cache_hit']))
        run(config,cfg,directory,emit)


def process_snapshot(worker_pid):
    output=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,time='],text=True,timeout=2)
    rows={}
    for line in output.splitlines():
        bits=line.split()
        if len(bits)!=4:continue
        pid,ppid,rss=map(int,bits[:3]);clock=bits[3]
        days=0
        if '-' in clock:
            day,clock=clock.split('-');days=int(day)
        nums=list(map(float,clock.split(':')))
        cpu=days*86400+sum(x*60**i for i,x in enumerate(reversed(nums)))
        rows[pid]=(ppid,rss,cpu)
    included={worker_pid}
    while True:
        grown=included|{pid for pid,(ppid,_,_) in rows.items() if ppid in included}
        if grown==included:break
        included=grown
    # Host Python included in memory; sampler ps excluded. Shared pages may be
    # counted more than once. RSS is NOT unique physical memory or GGUF size.
    memory_pids=included|{os.getpid()}
    rss=sum(rows[p][1] for p in memory_pids if p in rows)/1024
    return rss,{p:rows[p][2] for p in included if p in rows}


def host(args,config):
    from nexus.seed.experimental import Sandbox,write_new
    from nexus.seed.local_model_runtime import file_hash
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
        raise ValueError('precommitted clean branch required')
    if file_hash(args.model)!=config['model_sha256']:raise ValueError('model weight hash mismatch')
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='main':
        raise ValueError('research branch required')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    run_id='seed-assistant-benchmark-v2-1'
    sandbox=Sandbox(ROOT)
    with sandbox.locked():
        if any(r['run_id']==run_id for r in sandbox.records('reserved')):raise ValueError('one-shot run already consumed')
        grants=sandbox.records('grant')
        carried=grants[0]['carried_used_s'] if grants else config['carried_used_s']
        known=carried+sandbox.used_s()
        if known<config['carried_used_s']:
            sandbox.debit('assistant-v2-carry-reconciliation',config['carried_used_s']-known,
                          'Carry forward latest explicitly recorded ledger; not a refund/reset',
                          'artifacts/seed_open_primitive_transfer.json session_used_s')
        used=carried+sandbox.used_s()
        if used+config['wall_s']>3600 or config['wall_s']>900:raise ValueError('standing session allowance exceeded')
        caps=dict(wall_s=config['wall_s'],cpu_s=config['cpu_s'],memory_mb=config['memory_mb'],
                  real_steps=0,imagined_transitions=0,updates=0)
        config_hash=file_hash(CONFIG);protocol_hash=file_hash(PROTOCOL)
        sandbox.grant(run_id,'standing-human-grant-2026-10-16',
                      'Owner-requested persistent CPU assistant study; exact config '+config_hash,
                      caps,3600,carried,memory_policy='sampled_rss')
        directory=sandbox.directory/'attempts'/run_id;directory.mkdir()
        registration=dict(run_id=run_id,source_sha=revision,config_sha256=config_hash,
                          protocol_sha256=protocol_hash,model_sha256=config['model_sha256'],
                          carried_used_s=used,cap=caps,authorization='standing human grant; owner current task',
                          executable_name=Path(args.executable).name)
        write_new(directory/'registration.json',registration)
        sandbox.append('reserved',dict(run_id=run_id,wall_cap_s=config['wall_s'],
                       spec={'id':run_id,'mode':'exploration','recipe':{'adapter':'seed_assistant_benchmark_v2'}},
                       registration=registration))
        before=resource.getrusage(resource.RUSAGE_CHILDREN)
        before_self=resource.getrusage(resource.RUSAGE_SELF)
        started=time.monotonic();peak=0;cpu_seen={};samples=[];reason=None
        command=[sys.executable,'-B',__file__,'--worker','--model',str(Path(args.model).resolve()),
                 '--executable',args.executable,'--directory',str(directory)]
        with (directory/'worker.log').open('xb') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,start_new_session=True,
                env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1'))
            try:
                while process.poll() is None:
                    rss,cpus=process_snapshot(process.pid);peak=max(peak,rss)
                    for pid,cpu in cpus.items():cpu_seen[pid]=max(cpu_seen.get(pid,0),cpu)
                    elapsed=time.monotonic()-started;cpu=sum(cpu_seen.values())
                    samples.append(dict(wall_s=elapsed,aggregate_rss_mb=rss,sampled_descendant_cpu_s=cpu))
                    if elapsed>=config['wall_s']:reason='wall_cap'
                    elif cpu>=config['cpu_s']:reason='sampled_aggregate_cpu_cap'
                    elif rss>config['memory_mb']:reason='aggregate_rss_cap'
                    if reason:
                        os.killpg(process.pid,signal.SIGKILL);break
                    time.sleep(.1)
            except Exception as exc:
                reason='supervisor_error:'+type(exc).__name__
            finally:
                if process.poll() is None:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                process.wait()
        wall=time.monotonic()-started
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        after_self=resource.getrusage(resource.RUSAGE_SELF)
        final_cpu=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime)+(after_self.ru_utime+after_self.ru_stime)-(before_self.ru_utime+before_self.ru_stime)
        if final_cpu>config['cpu_s']:reason=reason or 'post_execution_cpu_cap'
        charged=math.ceil(wall)+1
        sandbox.append('settled',dict(run_id=run_id,charged_wall_s=charged,
                       status='complete_development' if process.returncode==0 and not reason else 'incomplete'))
        records=read_records(directory/'raw.jsonl')
        spec=importlib.util.spec_from_file_location('assistant_independent_verifier',ROOT/'scripts/verify_seed_assistant_benchmark_v2.py')
        verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
        summary=verifier.reconstruct(records,config)
        if reason or process.returncode!=0:
            summary['declared_complete']=False;summary['passed']=False;summary['verdict']='INCOMPLETE'
        destination=ROOT/'artifacts'
        raw_name='seed_assistant_benchmark_v2_raw.jsonl'
        with (destination/raw_name).open('xb') as output:output.write((directory/'raw.jsonl').read_bytes() if (directory/'raw.jsonl').exists() else b'')
        inputs_name='seed_assistant_benchmark_v2_inputs';inputs=destination/inputs_name;inputs.mkdir()
        for path in directory.glob('*.csv'):shutil.copyfile(path,inputs/path.name)
        meter=dict(wall_s=wall,charged_wall_s=charged,peak_sampled_aggregate_rss_mb=peak,
                   aggregate_waited_cpu_s=final_cpu,
                   descendant_cpu_waited_s=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime),
                   cpu_policy='single-thread CPU servers; per-worker inherited RLIMIT_CPU plus sampled aggregate watchdog',
                   memory_definition='sum host Python, worker Python and server RSS; shared pages can be double-counted',
                   sample_period_s=.1,samples=samples,stop_reason=reason,worker_returncode=process.returncode,
                   session_used_s=carried+sandbox.used_s(),session_remaining_s=3600-carried-sandbox.used_s())
        result=dict(schema=config['schema'],registration=registration,summary=summary,resources=meter,
                    raw_file=raw_name,raw_sha256=file_hash(destination/raw_name),inputs_directory=inputs_name)
        write_new(destination/'seed_assistant_benchmark_v2.json',result)
        print(json.dumps(dict(summary=summary,resources={k:v for k,v in meter.items() if k!='samples'}),indent=2))


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--model',required=True)
    p.add_argument('--executable',default='llama-server');p.add_argument('--worker',action='store_true')
    p.add_argument('--directory');args=p.parse_args();config=json.loads(CONFIG.read_text())
    if args.worker:worker(args,config)
    else:host(args,config)


if __name__=='__main__':main()
