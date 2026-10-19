"""Durable AUTHORED-fixture A→B→restart→A→C session; no simulator/model calls.

Uses existing LearningCycle, FixtureHost and cycle_checkpoint JSON. This is
not a real continual-learning study or a new memory/evaluation framework.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
STREAM=('A','B','A','C')


def run(directory,*,new=False,seed=None,method=None,blocks=2,expected_head=None):
    from nexus.evolution1.catalogue import digest
    from nexus.evolution2.cycle_checkpoint import save_cycle,load_cycle
    from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost
    if type(blocks) is not int or not 1<=blocks<=2 or seed is not None and (type(seed) is not int or not 0<=seed<=99) or method is not None and method not in ('unified','reset_memory','shuffled_memory','fixed_generation'):raise ValueError('bounded_fixture_session_options')
    folder=Path(directory)
    if new:folder.mkdir(parents=True,exist_ok=False)
    if not folder.is_dir():raise ValueError('existing_session_required')
    lock=folder/'.active';lock.mkdir()  # Fail closed on a concurrent/stale writer.
    try:
        records=sorted(folder.glob('revision-*.json'));previous=None;head=None
        for index,path in enumerate(records):
            record=json.loads(path.read_text())
            if path.name!=f'revision-{index:04d}.json' or record['previous_head']!=head or record['revision']!=index:raise ValueError('session_chain')
            raw={k:v for k,v in record.items() if k!='head'}
            if digest(raw)!=record['head']:raise ValueError('session_record_hash')
            expected_file=f'cycle-{index:04d}.json'
            if record['checkpoint']!=expected_file or hashlib.sha256((folder/expected_file).read_bytes()).hexdigest()!=record['checkpoint_sha256']:raise ValueError('session_checkpoint_hash')
            previous=record;head=record['head']
        if expected_head is not None and head!=expected_head:raise ValueError('external_session_head_mismatch')
        if new and records or not new and not records:raise ValueError('new_or_resume_session')
        if (folder/f'cycle-{len(records):04d}.json').exists():raise ValueError('orphaned_snapshot_requires_review')
        if previous:
            provenance=previous['provenance']
            if seed is not None and seed!=provenance['seed'] or method is not None and method!=provenance['method']:raise ValueError('resume_settings_must_match')
            cycle=load_cycle(folder/previous['checkpoint'],expected_sha256=previous['checkpoint_sha256'],provenance=provenance)
            host=FixtureHost(provenance['seed'],max_calls=256);host.calls=previous['host_calls'];host.failures=previous['host_failures'];cursor=previous['task_cursor']
            if type(host.calls) is not int or not 0<=host.calls<=256 or type(host.failures) is not int or not 0<=host.failures<=host.calls or type(cursor) is not int or not 0<=cursor<=4:raise ValueError('persisted_fixture_budget')
        else:
            seed=7 if seed is None else seed;method='unified' if method is None else method
            provenance=dict(kind='authored_fixture_session_v1',seed=seed,method=method,stream=list(STREAM),steps_per_task=2)
            cycle=LearningCycle(seed,method,objective='training_incumbent_progress_v1');host=FixtureHost(seed,max_calls=256);cursor=0
        if cursor==len(STREAM):raise ValueError('fixture_stream_already_complete')
        failure=None
        try:
            for _ in range(min(blocks,len(STREAM)-cursor)):
                task=STREAM[cursor];cycle.begin_task(task)
                for _ in range(2):
                    if cycle.step(host,task) is None:break
                cursor+=1
        except Exception as exc:failure=repr(exc)
        index=len(records);checkpoint=f'cycle-{index:04d}.json'
        checksum=save_cycle(cycle,folder/checkpoint,provenance=provenance)
        record=dict(revision=index,previous_head=head,provenance=provenance,task_cursor=cursor,checkpoint=checkpoint,
            checkpoint_sha256=checksum,host_calls=host.calls,host_failures=host.failures,charged_training_units=cycle.charged.cpu_units,
            remaining_choices=cycle.stream.remaining,scientific=False,new_environment_interactions=0,model_inference=0,failure=failure)
        record['head']=digest(record)
        with (folder/f'revision-{index:04d}.json').open('x') as out:json.dump(record,out,allow_nan=False,indent=2)
        if failure:raise RuntimeError('Failed fixture attempt saved: '+failure)
        return record
    finally:lock.rmdir()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--new',action='store_true');p.add_argument('--seed',type=int);p.add_argument('--method');p.add_argument('--blocks',type=int,default=2);p.add_argument('--expected-head');args=p.parse_args()
    print(json.dumps(run(args.directory,new=args.new,seed=args.seed,method=args.method,blocks=args.blocks,expected_head=args.expected_head),indent=2))
