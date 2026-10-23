"""Bounded product chat smoke. Live CPU llama-server only; not confirmation.

Charges chat_usage.json. Does not debit the frozen research CPU ledger or
write metal_ledger.json. A Metal backend in the tree is unused.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

PREFERRED = ROOT / ".models" / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
FALLBACK = ROOT / ".models" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
PHOTO = (
    "In 2026 the authored Seed lab recorded that photophosphorylation "
    "yields ATP inside a 6 by 6 object world."
)
CAP_S = 180.0
MAX_CALLS = 6


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_path() -> Path | None:
    env = os.environ.get("NEXUS_MODEL_PATH")
    if env and Path(env).expanduser().is_file():
        return Path(env).expanduser()
    if PREFERRED.is_file():
        return PREFERRED
    if FALLBACK.is_file():
        return FALLBACK
    return None


def _send(workspace, sid, text):
    return workspace.dispatch(dict(
        session_id=sid,
        request=dict(op="chat_send", text=text, id=uuid.uuid4().hex),
    ))["response"]


def _card(response, key, default=None):
    for card in response.get("chat", {}).get("messages", [])[-1].get("cards") or []:
        data = card.get("data") or {}
        if key in data:
            return data[key]
    return default


def main(directory: Path) -> dict:
    from nexus.seed.lab import SeedWorkspace
    from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig

    metal_paths = [
        ROOT / "artifacts" / "seed_metal_best_of_4_smoke" / "metal_ledger.json",
        ROOT / "artifacts" / "seed_metal_live_compare" / "metal_ledger.json",
    ]
    metal_before = {str(path): _sha(path) for path in metal_paths}
    started = time.perf_counter()
    report = dict(
        kind="product_chat_live_smoke",
        confirmation=False,
        learning_to_learn_established=False,
        product_backend="cpu",
        gpu_used=False,
        ngl=0,
        device="none",
        metal_used=False,
        research_cpu_ledger_frozen_s=3564.568,
        research_cpu_ledger_debit_s=0.0,
        consumes_closed_research_allowance=False,
        cap_s=CAP_S,
        max_calls=MAX_CALLS,
        steps={},
    )
    model = _model_path()
    executable = os.environ.get("NEXUS_LLAMA_SERVER", "llama-server")
    if model is None or shutil.which(executable) is None:
        report.update(status="unavailable", reason="local_model_or_server_missing")
        _write(directory, report)
        return report
    cfg = replace(
        RuntimeConfig.from_environment(),
        model_path=str(model.resolve()),
        executable=executable,
        application_cache=False,
        max_tokens=96,
        request_timeout_s=25,
        startup_timeout_s=45,
        threads=2,
    )
    runtime = PersistentLocalRuntime(cfg)
    workspace = SeedWorkspace(directory, local_runtime=runtime, runtime_config=cfg)
    sid = workspace.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
    try:
        runtime.start()
        report["startup_s"] = round(time.perf_counter() - started, 3)
        report["model_path"] = str(model)
        report["process_pid_start"] = runtime.process.pid if runtime.process else None

        greet = _send(workspace, sid, "How are you today?")
        report["steps"]["natural"] = dict(
            inference_ran=_card(greet, "inference_ran"),
            source=_card(greet, "source"),
            architecture_dump="15-component" in greet["text"],
            text=greet["text"][:240],
        )

        follow = _send(workspace, sid, "What should I remember from that?")
        report["steps"]["follow_up"] = dict(
            inference_ran=_card(follow, "inference_ran"),
            source=_card(follow, "source"),
            architecture_dump="15-component" in follow["text"],
            text=follow["text"][:240],
        )

        workspace.dispatch(dict(session_id=sid, request=dict(
            op="knowledge_save", kind="document", title="Seed photosynthetic note",
            content=PHOTO, doc_id="seed-photo-1")))
        asked = _send(workspace, sid, "What do we know about photophosphorylation?")
        report["steps"]["document"] = dict(
            cited="[seed-photo-1]" in asked["text"],
            has_atp="ATP" in asked["text"],
            model_generated=_card(asked, "source") == "model_generated",
            text=asked["text"][:240],
        )

        coding = _send(workspace, sid, "Explain this code:\n```python\ndef add(a, b):\n    return a + b\n```")
        report["steps"]["coding"] = dict(
            executed=_card(coding, "executed"),
            user_status=coding["chat"]["context"]["workspace"].get("last_user_status"),
            explained="has not been executed" in coding["text"],
            text=coding["text"][:240],
        )

        pid_before = runtime.process.pid if runtime.process else None
        armed = threading.Event()

        def fire_stop():
            armed.wait(timeout=5)
            time.sleep(0.8)
            workspace.sessions[sid].cancelled.set()
            if hasattr(runtime, "cancel"):
                runtime.cancel()

        stopper = threading.Thread(target=fire_stop, daemon=True)
        stopper.start()
        armed.set()
        stop_error = None
        stop_response = None
        try:
            stop_response = _send(
                workspace, sid,
                "Write twenty short sentences about local notebooks, one after another.",
            )
        except Exception as exc:
            stop_error = type(exc).__name__ + ": " + str(exc)[:200]
        stopper.join(timeout=5)
        process = runtime.process
        process_alive = process is not None and process.poll() is None
        stop_text = (stop_response or {}).get("text", "")
        report["steps"]["stop"] = dict(
            generation_was_running=True,
            cancelled_flag=workspace.sessions[sid].cancelled.is_set(),
            process_pid_before=pid_before,
            process_is_none=process is None,
            process_alive=process_alive,
            process_poll=None if process is None else process.poll(),
            send_error=stop_error,
            reply_status=((stop_response or {}).get("chat", {}).get("messages") or [{}])[-1].get("status"),
            charged_cancelled=(json.loads((Path(directory) / "chat_usage.json").read_text()).get("cancelled")
                               if (Path(directory) / "chat_usage.json").is_file() else None),
            text=stop_text[:240],
        )
        usage_path = Path(directory) / "chat_usage.json"
        report["chat_usage"] = json.loads(usage_path.read_text()) if usage_path.is_file() else None
        report["metal_ledgers_unchanged"] = {
            path: _sha(Path(path)) == digest for path, digest in metal_before.items()
        }
        report["metal_ledger_written_in_seed_dir"] = (Path(directory) / "metal_ledger.json").exists()
        inspector = workspace.dispatch(dict(session_id=sid, request={"op": "chat_view"}))["response"]["chat"]["inspector"]
        report["inspector"] = dict(
            product_backend=inspector.get("product_backend"),
            gpu_used=inspector.get("gpu_used"),
            metal_used=inspector.get("metal_used"),
            consumes_closed_research_allowance=inspector.get("consumes_closed_research_allowance"),
            chat_usage=inspector.get("chat_usage"),
        )
        ok = (
            report["steps"]["natural"].get("inference_ran") is True
            and report["steps"]["natural"]["architecture_dump"] is False
            and report["steps"]["document"]["cited"]
            and report["steps"]["coding"]["executed"] is False
            and report["steps"]["stop"]["cancelled_flag"]
            and report["steps"]["stop"]["process_alive"] is False
            and not report["metal_ledger_written_in_seed_dir"]
            and all(report["metal_ledgers_unchanged"].values())
        )
        report["status"] = "passed" if ok else "failed"
    finally:
        runtime.close()
        leftover = runtime.process
        report["process_cleanup"] = dict(
            process_is_none=leftover is None,
            process_alive=leftover is not None and leftover.poll() is None,
        )
        report["wall_s"] = round(time.perf_counter() - started, 3)
        if report["wall_s"] > CAP_S:
            report["status"] = "failed"
            report["reason"] = "cap_exceeded"
    _write(directory, report)
    return report


def _write(directory: Path, report: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "seed_chat_live_smoke.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_chat_live_smoke"
    main(target)
