"""Owned persistent llama.cpp CPU server; explicit response-cache accounting.

No template/codec fallback. HTTP disconnect cancels the client request; when
NEXUS owns the server it also terminates it on timeout/cancellation, ensuring
generation cannot continue unmetered. Caller must explicitly start again.
"""
from __future__ import annotations

import atexit
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import shutil
import secrets
import socket
import subprocess
import struct
import threading
import time


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def gguf_file_type(path):
    """Read the actual GGUF general.file_type, skipping tokenizer arrays."""
    with Path(path).open('rb') as f:
        def number(fmt):
            size=struct.calcsize(fmt);raw=f.read(size)
            if len(raw)!=size:raise ValueError('truncated GGUF')
            return struct.unpack(fmt,raw)[0]
        def string():
            n=number('<Q')
            if n>16_000_000:raise ValueError('GGUF string bound')
            return f.read(n).decode('utf-8')
        def value(kind,keep=False):
            if kind==8:
                n=number('<Q')
                if n>16_000_000:raise ValueError('GGUF string bound')
                if keep:return f.read(n).decode('utf-8')
                f.seek(n,1);return None
            if kind==9:
                sub=number('<I');count=number('<Q')
                if count>1_000_000 or sub==9:raise ValueError('GGUF array bound')
                for _ in range(count):value(sub)
                return None
            fmt={0:'<B',1:'<b',2:'<H',3:'<h',4:'<I',5:'<i',6:'<f',7:'<?',10:'<Q',11:'<q',12:'<d'}[kind]
            return number(fmt)
        if f.read(4)!=b'GGUF' or number('<I') not in (2,3):raise ValueError('GGUF v2/v3 model required')
        number('<Q');count=number('<Q')
        if count>10000:raise ValueError('GGUF metadata bound')
        for _ in range(count):
            key=string();kind=number('<I');v=value(kind,key=='general.file_type')
            if key=='general.file_type':return v
    return None


@dataclass(frozen=True)
class RuntimeConfig:
    model_path: str
    executable: str = 'llama-server'
    host: str = '127.0.0.1'
    port: int = 0
    context_size: int = 2048
    threads: int = 1
    backend: str = 'llama_cpp_server'
    request_timeout_s: float = 20
    startup_timeout_s: float = 30
    max_tokens: int = 128
    seed: int = 42
    application_cache: bool = True
    prompt_cache: bool = False

    def validate(self):
        if self.backend != 'llama_cpp_server' or self.host not in ('127.0.0.1', 'localhost'):
            raise ValueError('supported local CPU backend/loopback host required')
        if type(self.port) is not int or not 0 <= self.port <= 65535:
            raise ValueError('invalid port')
        if not 256 <= self.context_size <= 16384 or not 1 <= self.threads <= 4:
            raise ValueError('bounded context/CPU threads required')
        if not 0 < self.request_timeout_s <= 60 or not 0 < self.startup_timeout_s <= 60:
            raise ValueError('bounded timeouts required')
        if not 1 <= self.max_tokens <= 512:
            raise ValueError('bounded output required')
        if type(self.application_cache) is not bool or type(self.prompt_cache) is not bool:
            raise ValueError('explicit cache policies required')

    @classmethod
    def from_environment(cls):
        model = os.environ.get('NEXUS_MODEL_PATH', '.models/qwen2.5-0.5b-instruct-q4_k_m.gguf')
        return cls(model_path=model, executable=os.environ.get('NEXUS_LLAMA_SERVER', 'llama-server'),
                   host=os.environ.get('NEXUS_MODEL_HOST', '127.0.0.1'),
                   port=int(os.environ.get('NEXUS_MODEL_PORT', '0')),
                   context_size=int(os.environ.get('NEXUS_MODEL_CONTEXT', '2048')),
                   backend=os.environ.get('NEXUS_MODEL_BACKEND', 'llama_cpp_server'))


class PersistentLocalRuntime:
    def __init__(self, config, log_path=None):
        config.validate()
        self.config = config
        self.log_path = log_path
        self.process = None
        self._cache = {}
        self._lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._connection = None
        self.metadata = None
        self._cancel = threading.Event()
        self._api_key = secrets.token_urlsafe(24)
        atexit.register(self.close)

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return deepcopy(self.metadata)
        begin = time.perf_counter()
        model = Path(self.config.model_path).expanduser().resolve(strict=True)
        binary = shutil.which(self.config.executable)
        if not binary:
            raise FileNotFoundError('llama-server executable not found')
        if self.config.port:
            self.port = self.config.port
            with socket.socket() as sock:
                sock.bind((self.config.host, self.port))  # Never adopt somebody else's server.
        else:
            with socket.socket() as sock:
                sock.bind((self.config.host, 0))
                self.port = sock.getsockname()[1]
        version = subprocess.run([binary, '--version'], capture_output=True, text=True,
                                 timeout=5, check=True)
        weights_hash = file_hash(model)
        quantization_id = gguf_file_type(model)
        args = [binary, '-m', str(model), '--host', self.config.host, '--port', str(self.port),
                '-c', str(self.config.context_size), '-t', str(self.config.threads),
                '-tb', str(self.config.threads), '-np', '1', '-ngl', '0', '--device', 'none',
                '--no-op-offload', '--offline', '--no-webui', '--cache-ram', '0', '--api-key', self._api_key]
        self._log = open(self.log_path, 'ab') if self.log_path else open(os.devnull, 'ab')
        # Inherit the benchmark worker's process group: supervisor kills descendants too.
        self.process = subprocess.Popen(args, stdout=self._log, stderr=self._log,
                                        env=dict(os.environ, OMP_NUM_THREADS=str(self.config.threads)))
        self._cancel.clear()
        try:
            deadline = time.monotonic() + self.config.startup_timeout_s
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('model server exited during startup (return code '+
                                       str(self.process.poll())+'); inspect server log')
                try:
                    if self._http('GET', '/health', None, timeout=.3).get('status') == 'ok':
                        break
                except (OSError, ValueError, RuntimeError, http.client.HTTPException):
                    pass
                self._cancel.wait(.05)
            else:
                raise TimeoutError('model readiness deadline exceeded')
            self.metadata = dict(model_sha256=weights_hash, model_file=model.name,
                                 model_file_bytes=model.stat().st_size,
                                 quantization='Q4_K_M' if quantization_id == 15 else 'GGUF file type '+str(quantization_id),
                                 gguf_file_type=quantization_id, quantization_source='GGUF general.file_type metadata',
                                 runtime_version=(version.stdout + version.stderr).strip(),
                                 executable_sha256=file_hash(binary), hardware=platform.machine(),
                                 os=platform.platform(), cpu_count=os.cpu_count(), settings=asdict(self.config),
                                 cold_startup_s=time.perf_counter()-begin)
            self._cache.clear()
            return deepcopy(self.metadata)
        except BaseException:
            self.close()
            raise

    def _http(self, method, path, payload, timeout):
        conn = http.client.HTTPConnection(self.config.host, self.port, timeout=timeout)
        self._connection = conn
        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False)
            conn.request(method, path, body, {'Content-Type': 'application/json',
                                            'Authorization': 'Bearer '+self._api_key})
            response = conn.getresponse()
            raw = response.read(1_000_001)
            if response.status != 200 or len(raw) > 1_000_000:
                raise RuntimeError('runtime HTTP failure or oversized response')
            return json.loads(raw)
        finally:
            conn.close()
            self._connection = None

    def complete(self, prompt, schema):
        with self._lock:
            start = time.perf_counter()
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('persistent runtime must be started explicitly')
            key = hashlib.sha256(json.dumps([prompt, schema, self.config.max_tokens,
                                            self.config.seed], sort_keys=True).encode()).hexdigest()
            if self.config.application_cache and key in self._cache:
                prior = self._cache[key]
                return dict(content=prior['content'], telemetry=dict(
                    inference_ran=False, application_cache_hit=True, prompt_cache_tokens=None,
                    input_tokens=0, generated_tokens=0, request_wall_s=time.perf_counter()-start,
                    runtime_timings=None, creation_request_sha256=prior['request_sha256']),
                    request_sha256=key)
            payload = dict(prompt=prompt, json_schema=schema, n_predict=self.config.max_tokens,
                           temperature=0, seed=self.config.seed, cache_prompt=self.config.prompt_cache)
            timer = threading.Timer(self.config.request_timeout_s, self.cancel)
            timer.daemon = True
            timer.start()
            try:
                raw = self._http('POST', '/completion', payload, self.config.request_timeout_s)
                if self._cancel.is_set():
                    raise TimeoutError('inference cancelled or timed out')
                if type(raw.get('content')) is not str or raw.get('truncated') is True:
                    raise ValueError('missing/truncated structured completion')
                # No invented zero for unavailable telemetry. Save exact runtime fields.
                timings = raw.get('timings')
                out = dict(content=raw['content'], request_sha256=key, telemetry=dict(
                    inference_ran=True, application_cache_hit=False,
                    input_tokens=raw.get('tokens_evaluated'), generated_tokens=raw.get('tokens_predicted'),
                    prompt_cache_tokens=(timings or {}).get('cache_n'),
                    runtime_timings=timings, request_wall_s=time.perf_counter()-start,
                    creation_request_sha256=None))
                if self.config.application_cache:
                    self._cache[key] = deepcopy(out)
                return out
            except BaseException:
                self.close()
                raise
            finally:
                timer.cancel()

    def clear_cache(self):
        self._cache.clear()

    def cancel(self):
        self._cancel.set()
        conn = self._connection
        if conn and conn.sock:
            try:
                conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.close()

    def close(self):
        with self._close_lock:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.process.kill(); self.process.wait(timeout=2)
                self.process = None
            if getattr(self, '_log', None):
                self._log.close()
            self._cache.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
