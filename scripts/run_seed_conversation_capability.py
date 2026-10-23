"""Run the locked conversation-capability development evaluation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main(directory: Path) -> Path:
    from nexus.seed.conversation_capability import load_manifest, run, summarize
    manifest = load_manifest(ROOT / 'configs/seed_conversation_capability_v1.json')
    records = run(manifest, directory)
    artifact = directory / 'seed_conversation_capability_v1.json'
    payload = dict(study_id=manifest['study_id'], scientific=False,
                   kind='source_development_evaluation_not_confirmation',
                   records=records, summary=summarize(records),
                   learning_to_learn=False, agi=False)
    directory.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2), encoding='utf-8')
    print(json.dumps(payload['summary'], indent=2))
    print('wrote', artifact)
    return artifact


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'artifacts' / 'seed_conversation_capability_v1'
    if target.suffix == '.json':
        directory = target.parent
    else:
        directory = target
    main(directory)
