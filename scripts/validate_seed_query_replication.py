"""Validate unchanged captured data after the resource-count validator correction.

Does not execute the scientific adapter, instantiate worlds or import Torch.
The original invalid execution receipt and declared_complete=false stay intact.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed import query_replication as qr
from nexus.evolution1.catalogue import digest


def validate_capture(root=ROOT):
    c=json.loads((root/'configs/seed_query_replication.json').read_text())
    raw_path=root/'artifacts/seed_query_replication.json';r=json.loads(raw_path.read_text());h=r['host_receipt']
    if r['declared_complete'] is not False or h['status']!='invalid_integrity' or h['failure']!='ValueError: query_execution_resource_grid':raise ValueError('unexpected_original_failure')
    if (r['execution_sha']!=h['revision'] or r['config_file_sha256']!=h['dataset_hashes']['config']
        or r['config_file_sha256']!=hashlib.sha256((root/'configs/seed_query_replication.json').read_bytes()).hexdigest()
        or h['dataset_hashes']['protocol']!=hashlib.sha256((root/'docs/NEXUS_SEED_QUERY_REPLICATION_PROTOCOL.md').read_bytes()).hexdigest()):raise ValueError('capture_provenance')
    # Completion is assessed on an isolated in-memory COPY. Never edit the raw.
    candidate=deepcopy(r);candidate['declared_complete']=True;p=qr.source_pack(root,c)
    output=dict(adapter='seed_query_replication_v1',study=candidate,resources=r['resources'],model=dict(schema='unchanged_query_replication_v1',**r['frozen_after']))
    qr.validate_output(output,c,h['resource_upper_bounds'],p)
    if h['wall_s']>c['max_wall_s'] or r['resources']['cpu_s']>c['max_wall_s'] or h['peak_sampled_rss_mb']>h['resource_upper_bounds']['memory_mb']:raise ValueError('captured_resource_limit')
    before=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    return dict(schema='seed_query_offline_validation_v1',status='complete_offline_validation_of_unchanged_capture',
        raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),original_status=h['status'],original_failure=h['failure'],
        execution_sha=r['execution_sha'],validation_revision=before,validated_complete=True,scientific_rerun=False,
        analysis_sha256=digest(r['analysis']),config_file_sha256=r['config_file_sha256'],protocol_file_sha256=h['dataset_hashes']['protocol'],
        parameter_counts=qr.checkpoint_parameter_count(root,c),scientific_execution=False,
        validator_sha256=hashlib.sha256((root/'scripts/validate_seed_query_replication.py').read_bytes()).hexdigest(),
        audit_module_sha256=hashlib.sha256((root/'src/nexus/seed/query_replication.py').read_bytes()).hexdigest(),
        correction='Removed incorrect hard-coded40487 total; verified frozen JSON weights contain30278+2209=32487 parameters. No metric, threshold, selection, data or resource cap changed.')


if __name__=='__main__':print(json.dumps(validate_capture(),indent=2))
