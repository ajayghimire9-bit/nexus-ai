"""Verify a packaged demo without third-party dependencies or execution."""
import hashlib
import json
from pathlib import Path,PurePosixPath


def verify(root):
    root=Path(root).resolve();manifest=json.loads((root/'DEMO_MANIFEST.json').read_text())
    if manifest['version']!='nexus-learning-lab-0.2.0' or manifest['live_scientific_backend'] is not False:raise ValueError('demo_manifest_scope')
    for name,entry in manifest['files'].items():
        p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('manifest_path')
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('manifest_path_escape')
        raw=path.read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('demo_file_hash: '+name)
    return dict(valid=True,version=manifest['version'],files=len(manifest['files']),source_revision=manifest['source_revision'],live_scientific_backend=False)


if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
