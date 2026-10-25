"""Device-agnostic local Qwen engine for Wave 24 v3.

Apple Silicon + explicit owner grant (NEXUS_EXPLICIT_METAL_GRANT=1) -> PersistentMetalRuntime
with n_gpu_layers=-1 (all layers on the Metal GPU). Anywhere else -> PersistentLocalRuntime on
CPU. The backend actually used is recorded in every telemetry row; a CPU run is never labelled Metal.
Every generated and evaluated token is counted so LLM cost enters the work meter.
"""
from __future__ import annotations

import os
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


def _sampled_local_runtime():
    """CPU runtime with seeded sampling, as a subclass: the pinned shared runtime file is NOT edited."""
    import threading
    from nexus.seed.local_model_runtime import PersistentLocalRuntime

    class SampledLocalRuntime(PersistentLocalRuntime):
        def complete(self, prompt, schema, *, temperature=0.0, seed=None):
            if float(temperature) == 0.0 and (seed is None or seed == self.config.seed):
                return super().complete(prompt, schema)
            with self._lock:
                start = time.perf_counter()
                payload = dict(prompt=prompt, n_predict=self.config.max_tokens, temperature=float(temperature),
                               seed=int(self.config.seed if seed is None else seed), cache_prompt=False)
                timer = threading.Timer(self.config.request_timeout_s, self.cancel)
                timer.daemon = True
                timer.start()
                try:
                    raw = self._http("POST", "/completion", payload, self.config.request_timeout_s)
                finally:
                    timer.cancel()
                if type(raw.get("content")) is not str:
                    raise ValueError("missing completion content")
                return dict(content=raw["content"], telemetry=dict(
                    inference_ran=True, application_cache_hit=False, input_tokens=raw.get("tokens_evaluated"),
                    generated_tokens=raw.get("tokens_predicted"), runtime_timings=raw.get("timings"),
                    request_wall_s=time.perf_counter() - start))

    return SampledLocalRuntime


def chatml(system, user):
    return (f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n")


class QwenEngine:
    """One persistent llama-server process; complete() returns text + exact token telemetry."""

    def __init__(self, *, max_tokens=384, context=4096, threads=4, request_timeout_s=60.0):
        from nexus.seed.metal_model_runtime import ExplicitMetalGrant, apple_silicon_metal_available
        self.model = locate_model()
        self.server = locate_server()
        hw = apple_silicon_metal_available()
        grant = ExplicitMetalGrant.from_config({"owner": os.environ.get("USER", "owner"),
                                                "reason": "wave24 v3 Qwen-1.5B candidate generation"})
        self.backend = "metal" if (hw.get("available") and grant.authorized) else "cpu"
        self.hardware = hw
        self.max_tokens, self.context, self.threads = max_tokens, context, threads
        self.timeout = request_timeout_s
        self._grant = grant
        self.rows = []
        self.rt = None

    def start(self):
        if self.rt is not None:
            return self.meta
        if self.backend == "metal":
            from nexus.seed.local_model_runtime import RuntimeConfig
            from nexus.seed.metal_model_runtime import PersistentMetalRuntime
            cfg = RuntimeConfig(model_path=str(self.model), executable=self.server, context_size=self.context,
                                threads=min(4, self.threads), max_tokens=self.max_tokens,
                                request_timeout_s=self.timeout, startup_timeout_s=60)
            self.rt = PersistentMetalRuntime(cfg, self._grant)
        else:
            from nexus.seed.local_model_runtime import RuntimeConfig
            PersistentLocalRuntime = _sampled_local_runtime()
            cfg = RuntimeConfig(model_path=str(self.model), executable=self.server, context_size=self.context,
                                threads=min(4, self.threads), max_tokens=self.max_tokens,
                                request_timeout_s=self.timeout, startup_timeout_s=60)
            self.rt = PersistentLocalRuntime(cfg)
        self.meta = dict(self.rt.start(), backend=self.backend, n_gpu_layers=-1 if self.backend == "metal" else 0)
        return self.meta

    def complete(self, system, user, *, temperature=0.0, seed=0, purpose=""):
        self.start()
        t0 = time.perf_counter()
        out = self.rt.complete(chatml(system, user), None, temperature=temperature, seed=seed)
        tel = out.get("telemetry") or {}
        if not tel.get("application_cache_hit") and (tel.get("input_tokens") is None or tel.get("generated_tokens") is None):
            raise RuntimeError("runtime returned no token counts; refusing to charge zero LLM cost")
        row = dict(purpose=purpose, backend=self.backend, temperature=temperature, seed=seed,
                   input_tokens=tel.get("input_tokens") or 0, generated_tokens=tel.get("generated_tokens") or 0,
                   cache_hit=bool(tel.get("application_cache_hit")), wall_s=time.perf_counter() - t0)
        self.rows.append(row)
        return out["content"], row

    @staticmethod
    def work_units(row):
        """LLM cost on the shared meter: 1 unit per evaluated prompt token + 4 per generated token."""
        return row["input_tokens"] + 4 * row["generated_tokens"]

    def telemetry(self):
        return dict(backend=self.backend, model=str(self.model.name), hardware=self.hardware,
                    calls=len(self.rows), generated_tokens=sum(r["generated_tokens"] for r in self.rows),
                    input_tokens=sum(r["input_tokens"] for r in self.rows),
                    wall_s=sum(r["wall_s"] for r in self.rows), server=self.meta if self.rt else None)

    def close(self):
        if self.rt is not None:
            self.rt.close()
            self.rt = None
