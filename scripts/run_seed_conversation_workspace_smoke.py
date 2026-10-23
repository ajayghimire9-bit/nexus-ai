"""Development live-conversation probe. Not a versioned benchmark and not confirmation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))


def main(directory: Path) -> dict:
    from nexus.seed.lab import SeedWorkspace
    from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig
    from tests.test_seed_workspace_conversation import SAMPLE_A, execution_card, model_ready, write_csv
    import uuid

    report = dict(kind='development_smoke_not_confirmation', live_inference=False,
                  closed_artifacts_untouched=True, protocol='not_a_benchmark')
    if not model_ready():
        cfg = RuntimeConfig.from_environment()
        report.update(reason='local_model_unavailable', model_path=cfg.model_path)
        print(json.dumps(report, indent=2))
        return report
    cfg = RuntimeConfig.from_environment()
    runtime = PersistentLocalRuntime(cfg)
    workspace = SeedWorkspace(directory, local_runtime=runtime)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    path = write_csv(directory / 'smoke.csv', SAMPLE_A)
    try:
        executed = workspace.dispatch(dict(session_id=sid, request=dict(
            op='chat_send', text='Summarize amounts by region using '+str(path),
            id=uuid.uuid4().hex)))['response']
        chat = workspace.dispatch(dict(session_id=sid, request=dict(
            op='chat_send', text='Reply with a short greeting only.',
            id=uuid.uuid4().hex)))['response']
        report.update(
            live_inference=True,
            execution_backed=execution_card(executed)['executed'],
            model_generated=chat['chat']['messages'][-1]['cards'][0]['data']['source'] == 'model_generated',
            inference_ran=chat['chat']['messages'][-1]['cards'][0]['data'].get('inference_ran'),
            reply=chat['text'][:240],
            model_file=Path(cfg.model_path).name,
        )
    finally:
        runtime.close()
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'runs' / 'seed-conversation-workspace-smoke'
    target.mkdir(parents=True, exist_ok=True)
    main(target)
