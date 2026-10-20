"""One registered saved-source diagnosis through the existing bounded host."""
import hashlib
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.experimental import Sandbox, read, write_new


def execute_study(config_name,protocol_name,artifact_name,adapter,identifier):
    """Shared host entry; adapters and paths are checked by the trusted host."""
    destination=ROOT/'artifacts'/artifact_name
    if destination.exists():raise ValueError('diagnosis_already_recorded')
    config_path=ROOT/'configs'/config_name
    protocol_path=ROOT/'docs'/protocol_name
    c=read(config_path);host=Sandbox(ROOT)
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    with host.locked():
        prior=host.records('grant')
        carried=prior[0]['carried_used_s'] if prior else c['carried_used_s']
        if abs(carried+host.used_s()-c['carried_used_s'])>1e-8:
            raise ValueError('carried_ledger_mismatch')
        grant=identifier
        host.grant(grant,'human standing grant 2026-10-16',
            'One committed source study; only its explicitly planned updates and collection',
            dict(wall_s=c['max_wall_s'],cpu_s=c['max_wall_s'],memory_mb=2048,real_steps=c.get('max_authored_steps',0),imagined_transitions=c.get('max_imagined_transitions',0),updates=c.get('max_outer_updates',0)),
            3600,carried,memory_policy='sampled_rss')
        spec=dict(id=identifier,mode='exploration',recipe=dict(
            adapter=adapter,config_path=str(config_path.relative_to(ROOT)),
            config_sha256=sha(config_path),protocol_path=str(protocol_path.relative_to(ROOT)),
            protocol_sha256=sha(protocol_path)),
            train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
        result=host.execute(spec,grant)
        debit=math.ceil(result['wall_s'])+1
        host.debit(identifier+'-carry',debit-result['wall_s'],
                   'Conservative whole-second dispatch accounting',identifier)
    worker=result.get('worker') or {};r=worker.get('study')
    if r is None:
        progress=host.directory/'attempts'/identifier/'progress.json'
        r=read(progress) if progress.exists() else dict(declared_complete=False,config=c)
    r.update(execution_sha=result['revision'],host_receipt={k:v for k,v in result.items() if k!='worker'},
        resources=worker.get('resources'),execution_debit_s=debit,
        session_used_s=c['carried_used_s']+debit,session_remaining_s=c['carried_remaining_s']-debit,
        config_file_sha256=sha(config_path),runtime=worker.get('runtime'))
    r['registration']=next(row for row in host.records('reserved') if row['run_id']==identifier)
    r['declared_complete']=result['status']=='complete_development' and r['declared_complete'] is True
    write_new(destination,r)
    import json
    print(json.dumps({k:r.get(k) for k in ('declared_complete','analysis','resources','execution_debit_s')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


def main():
    execute_study('seed_update_diagnosis.json','NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md',
        'seed_update_diagnosis.json','seed_update_diagnosis_v1','seed-source-update-diagnosis-1')


if __name__=='__main__':main()
