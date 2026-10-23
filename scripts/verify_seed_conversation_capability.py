"""Replay saved CSV references without new model inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def verify(artifact: Path, config_path: Path | None = None, files_dir: Path | None = None) -> dict:
    from nexus.seed.assistant_benchmark_v2 import reference
    from nexus.seed.conversation_capability import load_manifest, write_files

    artifact = Path(artifact)
    payload = json.loads(artifact.read_text(encoding='utf-8'))
    manifest_path = Path(config_path) if config_path else (ROOT / 'configs/seed_conversation_capability_v1.json')
    manifest = load_manifest(manifest_path)
    task_map = {t['id']: t for t in manifest['csv_tasks']}

    resolved_files_dir = Path(files_dir) if files_dir else (artifact.parent / 'files')
    paths: dict[str, Path] = {}
    if resolved_files_dir.is_dir():
        for spec in manifest['files']:
            candidate = resolved_files_dir / (spec['id'] + '.csv')
            if candidate.is_file():
                paths[spec['id']] = candidate
    if len(paths) != len(manifest['files']):
        from tempfile import TemporaryDirectory
        tmp_dir = TemporaryDirectory()
        paths = write_files(Path(tmp_dir.name), manifest['files'])

    mismatches = []
    csv_rows = [row for row in payload['records'] if row.get('kind') == 'csv_trial']
    for row in csv_rows:
        task_id = row['task_id']
        if task_id not in task_map:
            mismatches.append(task_id + ':' + row['method'] + ':unknown_task_id')
            continue
        task = task_map[task_id]
        expected_spec = task['expected']
        file_path = paths[task['file']]
        expected_status, independent_ref_output = reference(file_path, expected_spec)

        scored = row['scored']
        if scored.get('expected_status') != expected_status:
            mismatches.append(task_id + ':' + row['method'] + ':expected_status_mismatch')
        if scored.get('reference_output') != independent_ref_output:
            mismatches.append(task_id + ':' + row['method'] + ':reference_output_tampered')
        if expected_spec['op'] in ('clarify', 'unsupported'):
            ok = (not scored['executed']) and scored.get('observed_status') in ('clarification', 'unsupported', 'error')
        else:
            ok = bool(scored['executed']) and scored['output'] == independent_ref_output
        if bool(ok) != bool(scored['correct']):
            mismatches.append(task_id + ':' + row['method'])
    rebuilt = {}
    for row in csv_rows:
        rebuilt.setdefault(row['method'], {'correct': 0, 'n': 0})
        rebuilt[row['method']]['n'] += 1
        rebuilt[row['method']]['correct'] += int(row['scored']['correct'])
    match = rebuilt == payload['summary']['csv_correctness']
    report = dict(valid=match and not mismatches, mismatches=mismatches,
                  rebuilt_csv_correctness=rebuilt, model_inference=False,
                  independent_reference_reconstructed=True)
    print(json.dumps(report, indent=2))
    if not report['valid']:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    verify(Path(sys.argv[1]))

