"""One registered saved-source diagnosis through the existing bounded host."""
import hashlib
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.experimental import Sandbox, read, write_new


def main():
    destination=ROOT/'artifacts/seed_update_diagnosis.json'
    if destination.exists():raise ValueError('diagnosis_already_recorded')
    c=read(ROOT/'configs/seed_update_diagnosis.json');host=Sandbox(ROOT)
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    with host.locked():
        prior=host.records('grant')
        carried=prior[0]['carried_used_s'] if prior else c['carried_used_s']
        if abs(carried+host.used_s()-c['carried_used_s'])>1e-8:
            raise ValueError('carried_ledger_mismatch')
        grant='seed-source-update-diagnosis'
        host.grant(grant,'human standing grant 2026-10-16',
            'One committed source-only diagnosis; no new interaction or outer fitting',
            dict(wall_s=30,cpu_s=30,memory_mb=2048,real_steps=0,imagined_transitions=0,updates=0),
            3600,carried,memory_policy='sampled_rss')
        spec=dict(id='seed-source-update-diagnosis-1',mode='exploration',recipe=dict(
            adapter='seed_update_diagnosis_v1',config_path='configs/seed_update_diagnosis.json',
            config_sha256=sha(ROOT/'configs/seed_update_diagnosis.json'),
            protocol_path='docs/NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md',
            protocol_sha256=sha(ROOT/'docs/NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md')),
            train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
        result=host.execute(spec,grant)
        debit=math.ceil(result['wall_s'])+1
        host.debit('source-diagnosis-conservative-carry',debit-result['wall_s'],
                   'Conservative whole-second dispatch accounting','seed-source-update-diagnosis-1')
    worker=result.get('worker') or {};r=worker.get('study') or dict(declared_complete=False,config=c)
    r.update(execution_sha=result['revision'],host_receipt={k:v for k,v in result.items() if k!='worker'},
        resources=worker.get('resources'),execution_debit_s=debit,
        session_used_s=c['carried_used_s']+debit,session_remaining_s=c['carried_remaining_s']-debit,
        config_file_sha256=sha(ROOT/'configs/seed_update_diagnosis.json'))
    r['declared_complete']=result['status']=='complete_development' and r['declared_complete'] is True
    write_new(destination,r)
    import json
    print(json.dumps({k:r.get(k) for k in ('declared_complete','analysis','resources','execution_debit_s')},indent=2))
    if not r['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
