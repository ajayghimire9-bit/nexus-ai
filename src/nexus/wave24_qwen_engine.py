"""Device-agnostic local Qwen engine for Wave 24 v3.

Apple Silicon + explicit owner grant (NEXUS_EXPLICIT_METAL_GRANT=1) -> PersistentMetalRuntime
with n_gpu_layers=-1 (all layers on the Metal GPU). Anywhere else -> PersistentLocalRuntime on
CPU. The backend actually used is recorded in every telemetry row; a CPU run is never labelled Metal.
Every generated and evaluated token is counted so LLM cost enters the work meter.

Deterministic response cache keyed by sha256(model, system, user, prefix, stop, temperature, seed,
max_tokens): a cache hit returns the identical text AND re-charges the original token counts, so
caching saves wall-clock only and never makes an arm look cheaper. Optional on-disk cache
(NEXUS_QWEN_CACHE=<path.jsonl>) makes a run replayable without the model.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

MODEL_FILES = ("qwen2.5-1.5b-instruct-q4_k_m.gguf",)
SEARCH_DIRS = (".models", "models", "~/.models", "~/models", "~/.cache/nexus/models", "/home/user/models",
               "~/Library/Caches/llama.cpp", "~/.cache/llama.cpp")


def locate_model(names=MODEL_FILES, root=None):
    """Search the repo, home caches and HuggingFace caches for local GGUF weights."""
    env = os.environ.get("NEXUS_QWEN15_PATH")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser().resolve()
    root = Path(root or Path(__file__).resolve().parents[2])
    dirs = [root / d if not d.startswith(("~", "/")) else Path(d).expanduser() for d in SEARCH_DIRS]
    hf = Path("~/.cache/huggingface/hub").expanduser()
    for d in dirs:
        for n in names:
            if (d / n).exists():
                return (d / n).resolve()
    if hf.exists():
        for n in names:
            hits = sorted(hf.glob(f"**/{n}"))
            if hits:
                return hits[0].resolve()
    raise FileNotFoundError("local Qwen2.5-1.5B-Instruct GGUF weights not found; set NEXUS_QWEN15_PATH")


def locate_server():
    env = os.environ.get("NEXUS_LLAMA_SERVER")
    for cand in ([env] if env else []) + ["llama-server", "/home/user/tools/llama.cpp/build/bin/llama-server",
                                          "/opt/homebrew/bin/llama-server"]:
        import shutil
        path = shutil.which(cand) if cand else None
        if path:
            return path
    raise FileNotFoundError("llama-server executable not found; set NEXUS_LLAMA_SERVER")


METAL_LEDGER = Path(__file__).resolve().parents[2] / "runs" / "experimental" / "wave24-agi" / "metal_ledger.json"


def chatml(system, user):
    return (f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n")


class QwenEngine:
    """One persistent llama-server process; complete() returns text + exact token telemetry."""

    def __init__(self, *, max_tokens=384, context=4096, threads=4, request_timeout_s=60.0, cache_path=None,
                 grant_config=None):
        """grant_config (optional): extra owner-grant caps (max_rss_mib, max_wall_seconds_per_call,
        max_session_metal_seconds, reason). It never authorises Metal by itself; authorisation still requires
        NEXUS_EXPLICIT_METAL_GRANT=1."""
        from nexus.seed.metal_model_runtime import ExplicitMetalGrant, apple_silicon_metal_available
        self.model = locate_model()
        self.server = locate_server()
        hw = apple_silicon_metal_available()
        cfg = {"owner": os.environ.get("USER", "owner"), "reason": "wave24 Qwen-1.5B candidate generation",
               "ledger_path": os.environ.get("NEXUS_METAL_LEDGER") or str(METAL_LEDGER)}
        cfg.update({k: v for k, v in (grant_config or {}).items() if k != "authorized"})
        grant = ExplicitMetalGrant.from_config(cfg)
        self.backend = "metal" if (hw.get("available") and grant.authorized) else "cpu"
        self.hardware = hw
        self.max_tokens, self.context, self.threads = max_tokens, context, threads
        self.timeout = request_timeout_s
        self._grant = grant
        self.rows = []
        self.rt = None
        self.enforcer = None
        self.cache = {}
        self.cache_path = cache_path or os.environ.get("NEXUS_QWEN_CACHE")
        if self.cache_path and Path(self.cache_path).exists():
            for line in Path(self.cache_path).read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["key"]] = rec

    def start(self):
        if self.rt is not None:
            return self.meta
        if self.backend == "metal":
            from nexus.seed.local_model_runtime import RuntimeConfig
            from nexus.seed.metal_model_runtime import PersistentMetalRuntime
            cfg = RuntimeConfig(model_path=str(self.model), executable=self.server, context_size=self.context,
                                threads=min(4, self.threads), max_tokens=self.max_tokens,
                                request_timeout_s=self.timeout, startup_timeout_s=60)
            from nexus.seed.metal_model_runtime import MetalGrantEnforcer
            self.rt = PersistentMetalRuntime(cfg, self._grant)
            # Every Metal request goes through the owner grant's hard RSS / per-call wall / session caps.
            self.enforcer = MetalGrantEnforcer(self._grant, runtime=self.rt)
        else:
            from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig
            cfg = RuntimeConfig(model_path=str(self.model), executable=self.server, context_size=self.context,
                                threads=min(4, self.threads), max_tokens=self.max_tokens,
                                request_timeout_s=self.timeout, startup_timeout_s=60)
            self.rt = PersistentLocalRuntime(cfg)
        self.meta = dict(self.rt.start(), backend=self.backend, n_gpu_layers=-1 if self.backend == "metal" else 0)
        return self.meta

    def _post(self, prompt, *, temperature, seed, stop):
        """One raw /completion request through the owned runtime (same path on Metal and CPU)."""
        rt = self.rt
        abort = getattr(rt, "_abort_request", None) or rt.cancel
        payload = dict(prompt=prompt, n_predict=self.max_tokens, temperature=float(temperature), seed=int(seed),
                       cache_prompt=False, stop=list(stop))
        with rt._lock:
            if rt.process is None or rt.process.poll() is not None:
                raise RuntimeError("persistent runtime must be started explicitly")
            rt._cancel.clear()
            timer = threading.Timer(self.timeout, abort)
            timer.daemon = True
            timer.start()
            try:
                raw = rt._http("POST", "/completion", payload, self.timeout)
            finally:
                timer.cancel()
        if rt._cancel.is_set():
            raise TimeoutError("inference cancelled or timed out")
        if type(raw.get("content")) is not str:
            raise ValueError("missing completion content")
        return raw

    def complete(self, system, user, *, temperature=0.0, seed=0, purpose="", prefix="", stop=("<|im_end|>",)):
        """Returns (prefix + completion, row). `prefix` pre-fills the assistant turn (e.g. a code fence)."""
        self.start()
        t0 = time.perf_counter()
        stop = tuple(stop)
        key = hashlib.sha256(json.dumps([self.model.name, system, user, prefix, list(stop), float(temperature),
                                         int(seed), self.max_tokens]).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is None:
            post = lambda: self._post(chatml(system, user) + prefix, temperature=temperature, seed=seed, stop=stop)
            raw = self.enforcer.guarded_call(post) if self.enforcer is not None else post()
            if raw.get("tokens_evaluated") is None or raw.get("tokens_predicted") is None:
                raise RuntimeError("runtime returned no token counts; refusing to charge zero LLM cost")
            hit = dict(key=key, content=raw["content"], input_tokens=int(raw["tokens_evaluated"]),
                       generated_tokens=int(raw["tokens_predicted"]), stopped_word=bool(raw.get("stopped_word") or raw.get("stop_type") == "word"))
            self.cache[key] = hit
            if self.cache_path:
                with open(self.cache_path, "a") as fh:
                    fh.write(json.dumps(hit) + "\n")
            cached = False
        else:
            cached = True
        row = dict(purpose=purpose, backend=self.backend, temperature=temperature, seed=seed, request_sha256=key,
                   input_tokens=hit["input_tokens"], generated_tokens=hit["generated_tokens"], cache_hit=cached,
                   wall_s=time.perf_counter() - t0)
        self.rows.append(row)
        text = prefix + hit["content"]
        if stop and stop[0].startswith("```") and hit.get("stopped_word"):
            text += stop[0]
        return text, row

    @staticmethod
    def work_units(row):
        """LLM cost on the shared meter: 1 unit per evaluated prompt token + 4 per generated token."""
        return row["input_tokens"] + 4 * row["generated_tokens"]

    def telemetry(self):
        return dict(backend=self.backend, model=str(self.model.name), hardware=self.hardware,
                    calls=len(self.rows), fresh_calls=sum(not r["cache_hit"] for r in self.rows),
                    charged_cache_hits=sum(r["cache_hit"] for r in self.rows), generated_tokens=sum(r["generated_tokens"] for r in self.rows),
                    input_tokens=sum(r["input_tokens"] for r in self.rows),
                    wall_s=sum(r["wall_s"] for r in self.rows),
                    max_tokens=self.max_tokens, server=self.meta if self.rt else None,
                    metal_session_remaining_s=self.enforcer.remaining_session_s() if self.enforcer else None)

    def close(self):
        if self.rt is not None:
            self.rt.close()
            self.rt = None
