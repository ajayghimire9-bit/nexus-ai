"""Replay saved CSV references without new model inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def verify(artifact: Path) -> dict:
    from nexus.seed.assistant_benchmark_v2 import reference
    payload = json.loads(Path(artifact).read_text(encoding='utf-8'))
    mismatches = []
    csv_rows = [row for row in payload['records'] if row.get('kind') == 'csv_trial']
    for row in csv_rows:
        scored = row['scored']
        expected = None
        # Reconstruct from recorded reference_output / executed flag only.
        if scored['expected_status'] in ('clarify', 'unsupported'):
            ok = (not scored['executed']) and scored['correct'] is True
        else:
            ok = scored['reference_output'] == scored['output'] if scored['executed'] else scored['correct'] is False or scored['expected_status'] in ('clarify', 'unsupported')
        if bool(ok) != bool(scored['correct']) and scored['expected_status'] not in ('clarify', 'unsupported'):
            mismatches.append(row['task_id'] + ':' + row['method'])
    rebuilt = {}
    for row in csv_rows:
        rebuilt.setdefault(row['method'], {'correct': 0, 'n': 0})
        rebuilt[row['method']]['n'] += 1
        rebuilt[row['method']]['correct'] += int(row['scored']['correct'])
    match = rebuilt == payload['summary']['csv_correctness']
    report = dict(valid=match and not mismatches, mismatches=mismatches,
                  rebuilt_csv_correctness=rebuilt, model_inference=False)
    print(json.dumps(report, indent=2))
    if not report['valid']:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
