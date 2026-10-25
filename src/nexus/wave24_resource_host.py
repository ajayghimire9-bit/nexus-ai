"""Owner-budgeted Wave24 device adapter and supervised EXPERIMENTAL worker.

Reuses Sandbox grant/reservation/settlement accounting and write_new. This is
not a security boundary for arbitrary code. Only the fixed Wave24 worker is
dispatched. MPS and optional llama calls require an explicit exact allocation.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict, dataclass
import marshal
import math
import multiprocessing
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import types

try:
    import torch as _torch
    _torch.set_num_threads(1)
except Exception:
    _torch = None
try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass
except Exception:
    pass

from nexus.evolution1.catalogue import digest
from nexus.seed.experimental import Sandbox, read, write_new
from nexus.seed.process_memory import _rss_kib
from nexus.wave24_quotient_core import freeze as _freeze_value, unfreeze as _unfreeze_value


def _pin_compute_threads():
    try:
        import torch
        torch.set_num_threads(1)
        if hasattr(torch, "set_num_interop_threads"):
            torch.set_num_interop_threads(1)
    except Exception:
        pass


def _spawn_helper_child(payload, conn):
    """Top-level spawn target; reconstructs a marshaled pure helper."""
    try:
        import marshal
        import resource
        import types
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        def deny(event, args):
            if event == "open" or event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.system", "os.fork", "ctypes.")):
                raise PermissionError("helper verification denies external side effects")
        sys.addaudithook(deny)
        ns = {"__builtins__": {}}
        for name, code in payload.get("globals", {}).items():
            ns[name] = types.FunctionType(marshal.loads(code), {"__builtins__": {}})
        fn = types.FunctionType(marshal.loads(payload["code"]), ns)
        conn.send(dict(ok=True, outputs=[_freeze_value(fn(x)) for x in payload["inputs"]]))
    except BaseException as exc:
        try:
            conn.send(dict(ok=False, error=type(exc).__name__+": "+str(exc)))
        except Exception:
            pass
    finally:
        conn.close()


def verify_pure_helper_isolated(function, inputs, *, meter, wall_s=2., memory_mb=1024):
    """Resource-isolated replay of a VETTED AST over trusted pure primitives.

    No hostile-Python sandbox claim: arbitrary owner callables can contain C
    extensions. AST validation is performed by the caller before this function.
    Common filesystem/network/process audit events are denied in the child.
    Outer Wave24 CPU/wall/RSS limits still apply to the entire experiment.
    Uses spawn after thread pin; never os.fork() after PyTorch/MPS init.
    """
    wall_s = 2.0 if wall_s < 2 else wall_s
    if not 0 < wall_s <= 2 or not 64 <= memory_mb <= 1024 or not 1 <= len(inputs) <= 128:
        raise ValueError("bounded helper verification allocation required")
    _pin_compute_threads()
    import marshal
    import multiprocessing
    freeze, unfreeze = _freeze_value, _unfreeze_value
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    if "spawn" not in multiprocessing.get_all_start_methods():
        raise ValueError("isolated trusted-helper backend unavailable; no in-process fallback")
    globs = {}
    for name, value in getattr(function, "__globals__", {}).items():
        if name == "__builtins__" or not callable(value) or not hasattr(value, "__code__"):
            continue
        globs[name] = marshal.dumps(value.__code__)
    payload = dict(code=marshal.dumps(function.__code__), globals=globs, inputs=list(inputs))
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    from nexus.wave24_helper_spawn import spawn_helper_child
    process = context.Process(target=spawn_helper_child, args=(payload, sender), daemon=True)
    start = time.monotonic(); peak = 0.
    meter.charge("tool_sandbox_work_units", 1+len(inputs))
    process.start(); sender.close()
    data = None
    try:
        while time.monotonic()-start <= wall_s:
            meter.charge("tool_sandbox_work_units", 0)  # deadline check; polling CPU is in actual host wall/CPU
            rss = _rss_kib(process.pid)
            if rss is not None:
                peak = max(peak, rss/1024.)
                if peak > memory_mb:
                    raise ValueError("helper RSS cap exceeded")
            if receiver.poll(.005):
                data = receiver.recv()
                break
            if not process.is_alive():
                break
        if data is None:
            raise ValueError("helper failed or exhausted its wall/CPU allocation")
        if not data.get("ok"):
            raise ValueError("isolated helper rejected: "+data.get("error", "unknown"))
        return dict(outputs=tuple(unfreeze(v) for v in data["outputs"]), wall_s=time.monotonic()-start,
            peak_rss_mib=peak, isolation="spawn_vetted_AST_trusted_primitives", external_actions_allowed=False)
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=.2)
        if process.is_alive():
            process.kill(); process.join(timeout=.2)
        receiver.close()


@dataclass(frozen=True)
class Allocation:
    owner: str
    reason: str
    wall_s: float = 30.0
    cpu_s: int = 30
    memory_mb: int = 1024
    carried_used_s: float = 3564.568
    session_limit_s: float = 3600.0
    mps_approved: bool = False
    llm_approved: bool = False
    session_refresh_s: float = 0.0

    def __post_init__(self):
        values = (self.wall_s, self.cpu_s, self.memory_mb, self.carried_used_s, self.session_limit_s, self.session_refresh_s)
        if not self.owner.strip() or not self.reason.strip() or any(not math.isfinite(v) for v in values):
            raise ValueError("explicit owner, reason and finite allocation required")
        if not 0 < self.wall_s <= 900 or type(self.cpu_s) is not int or self.cpu_s < 1:
            raise ValueError("bounded wall and integral CPU caps required")
        if type(self.memory_mb) is not int or not 64 <= self.memory_mb <= 16384:
            raise ValueError("bounded memory allocation required")
        if not 0 <= self.carried_used_s < self.session_limit_s <= 3600:
            raise ValueError("carried session allowance cannot be reset or exceeded")
        if type(self.session_refresh_s) is not float or not 0 <= self.session_refresh_s <= 60.0:
            raise ValueError("session refresh must be an explicit 0-60s owner grant")
        if self.wall_s > self.session_limit_s-self.carried_used_s and self.session_refresh_s <= 0:
            raise ValueError("allocation exceeds remaining carried session allowance")
        if self.session_refresh_s > 0 and self.wall_s > self.session_refresh_s:
            raise ValueError("allocation exceeds the owner-authorized session refresh")
        if type(self.mps_approved) is not bool or type(self.llm_approved) is not bool:
            raise ValueError("explicit device/runtime approval flags required")


def carry_recorded_dev_usage(sandbox, repository, allocation):
    """Import the versioned consumed receipt on a fresh clone, exactly once."""
    for name in ("wave24_azr_dev_24001.json", "wave24_azr_dev_frontier_v2.json", "wave24_azr_dev_role_v3.json",
                 "wave24_azr_dev_workspace_v4.json", "wave24_azr_dev_lifelong_v5.json"):
        path = Path(repository)/"docs/evidence"/name
        if not path.exists():
            continue
        recorded = read(path)
        if recorded.get("consumed") is not True:
            raise ValueError("invalid tracked consumption record")
        receipt = recorded["receipt"]
        if receipt["carried_used_s"] != allocation.carried_used_s:
            raise ValueError("recorded carried baseline cannot be reset")
        if any(r["run_id"] == receipt["run_id"] for r in sandbox.records("reserved")):
            continue  # local reservation + verification debit already count it
        identifier = "import-"+receipt["run_id"]
        if any(r["id"] == identifier for r in sandbox.records("session_debit")):
            continue
        seconds = receipt["wall_s"]+receipt["verification_wall_s"]
        sandbox.debit(identifier, seconds, "carried consumed dev receipt; not a new run", digest(recorded))


class Wave24ResourceHost:
    def __init__(self, allocation, meter, *, torch_module=None, runtime=None):
        if not isinstance(allocation, Allocation):
            raise ValueError("validated allocation required")
        if torch_module is None:
            import torch as torch_module
        try:
            torch_module.set_num_threads(1)
        except Exception:
            pass
        self.torch, self.allocation, self.meter = torch_module, allocation, meter
        self.cpu_device = self.torch.device("cpu")
        available = bool(self.torch.backends.mps.is_available())
        self.mps_device = self.torch.device("mps") if available else None
        self.runtime = runtime
        self.mps_crossover_batch_size = None
        self.calibration = []
        self.stats = dict(cpu_scoring_calls=0, mps_scoring_calls=0, cpu_wall_ms=0.,
                          mps_sync_wall_ms=0., cpu_weight_updates=0, mps_weight_updates=0,
                          cpu_tensor_operations=0, mps_tensor_operations=0,
                          runtime_calls=0, runtime_wall_ms=0., runtime_work_units=0,
                          symbolic_fallback_calls=0)

    def _op(self, device, fn):
        is_mps = str(device) == "mps"
        if is_mps and (not self.allocation.mps_approved or self.mps_device is None):
            raise ValueError("MPS requires exact approved allocation and available device")
        if is_mps:
            self.torch.mps.synchronize()
        try:
            return fn()
        finally:
            if is_mps:
                self.torch.mps.synchronize()
            self.stats["mps_tensor_operations" if is_mps else "cpu_tensor_operations"] += 1

    def _timed(self, device, fn, *, scoring=False, update=False):
        is_mps = str(device) == "mps"
        if is_mps:
            if not self.allocation.mps_approved:
                raise ValueError("MPS allocation not approved")
            self.torch.mps.synchronize()
        started = time.perf_counter()
        try:
            return fn()
        finally:
            if is_mps:
                self.torch.mps.synchronize()
            elapsed = (time.perf_counter()-started)*1000
            self.stats["mps_sync_wall_ms" if is_mps else "cpu_wall_ms"] += elapsed
            if scoring:
                self.stats["mps_scoring_calls" if is_mps else "cpu_scoring_calls"] += 1
            if update:
                self.stats["mps_weight_updates" if is_mps else "cpu_weight_updates"] += 1

    def route(self, batch_size, *, update=False):
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("positive batch size")
        can_mps = self.mps_device is not None and self.allocation.mps_approved
        if can_mps and (self.mps_crossover_batch_size is not None
                        and batch_size >= self.mps_crossover_batch_size):
            return self.mps_device
        return self.cpu_device

    def _mlp(self, values, device):
        """Each MPS tensor operation has its own synchronization wrapper."""
        t = self.torch
        op = lambda fn: self._op(device, fn)
        x = op(lambda: t.tensor(values, dtype=t.float32, device=device))
        width = len(values[0])
        # Deterministic calibration weights; no scientific task/answer inputs.
        w = op(lambda: t.full((width, 16), .03125, dtype=t.float32, device=device))
        v = op(lambda: t.full((16, 2), .0625, dtype=t.float32, device=device))
        a = op(lambda: t.full((width, width), .015625, dtype=t.float32, device=device))
        h = op(lambda: t.matmul(x, w))
        h = op(lambda: t.tanh(h))
        logits = op(lambda: t.matmul(h, v))
        bilinear = op(lambda: t.matmul(x, a))
        bilinear = op(lambda: t.mul(bilinear, x))
        bilinear = op(lambda: t.sum(bilinear, dim=1, keepdim=True))
        logits = op(lambda: t.add(logits, bilinear))
        cpu = op(lambda: logits.to("cpu"))
        return cpu.tolist()

    def calibrate_cpu_mps_threshold(self, *, repeats=2):
        if type(repeats) is not int or not 1 <= repeats <= 5:
            raise ValueError("bounded calibration repetitions")
        self.calibration = []
        for batch in (16, 64, 256, 512, 1024):
            values = [[((i+j) % 11-5)/5 for j in range(6)] for i in range(batch)]
            row = dict(batch_size=batch, cpu_ms=None, mps_sync_ms=None, max_abs_error=None)
            outputs = {}
            for label, device in (("cpu", self.cpu_device), ("mps", self.mps_device)):
                if device is None or label == "mps" and not self.allocation.mps_approved:
                    continue
                samples = []
                for _ in range(repeats):
                    # Declared arithmetic work, separate from measured timing.
                    self.meter.charge("setup_work_units", batch*(6*16+16*2+6*6))
                    key = "cpu_wall_ms" if label == "cpu" else "mps_sync_wall_ms"
                    before = self.stats[key]
                    outputs[label] = self._timed(device, lambda: self._mlp(values, device), scoring=True)
                    samples.append(self.stats[key]-before)
                row["cpu_ms" if label == "cpu" else "mps_sync_ms"] = min(samples)
            if "mps" in outputs:
                error = max(abs(a-b) for x, y in zip(outputs["cpu"], outputs["mps"]) for a, b in zip(x, y))
                row["max_abs_error"] = error
                if error > 1e-4:
                    raise ValueError("CPU/MPS scorer calibration exceeds 1e-4 tolerance")
            self.calibration.append(row)
        # Require all measured larger sizes to favor MPS; never invent a crossover.
        self.mps_crossover_batch_size = next((r["batch_size"] for i, r in enumerate(self.calibration)
            if all(v["mps_sync_ms"] is not None and v["mps_sync_ms"] < v["cpu_ms"]
                   for v in self.calibration[i:])), None)
        return dict(rows=self.calibration, mps_crossover_batch_size=self.mps_crossover_batch_size,
                    cpu_ms_by_batch={str(r["batch_size"]): r["cpu_ms"] for r in self.calibration},
                    mps_sync_ms_by_batch={str(r["batch_size"]): r["mps_sync_ms"] for r in self.calibration},
                    selected_device="mps" if self.mps_crossover_batch_size is not None else "cpu",
                    mps_available=self.mps_device is not None, mps_authorized=self.allocation.mps_approved,
                    synchronized_per_operation=True)

    def reuse_calibration(self, report, *, source_sha256):
        """Reuse a measured table without exercising an expired GPU grant.

        The saved timing is labelled cached, not billed as newly measured or
        omitted from full-cost amortization. CPU-only authorization still wins
        over a recorded crossover that favored MPS on another run.
        """
        import re
        from copy import deepcopy
        if not re.fullmatch("[0-9a-f]{64}", source_sha256):
            raise ValueError("calibration provenance hash required")
        rows = deepcopy(report["rows"])
        if [r["batch_size"] for r in rows] != [16, 64, 256, 512, 1024]:
            raise ValueError("incomplete cached calibration grid")
        if any(r["cpu_ms"] is None or r["cpu_ms"] < 0 or
               r["mps_sync_ms"] is not None and r["mps_sync_ms"] < 0 for r in rows):
            raise ValueError("invalid cached calibration timings")
        threshold = next((r["batch_size"] for i, r in enumerate(rows)
            if all(v["mps_sync_ms"] is not None and v["mps_sync_ms"] < v["cpu_ms"] for v in rows[i:])), None)
        if threshold != report["mps_crossover_batch_size"]:
            raise ValueError("cached crossover disagrees with measured table")
        self.calibration, self.mps_crossover_batch_size = rows, threshold
        self.meter.charge("setup_work_units", len(rows))
        return dict(rows=rows, mps_crossover_batch_size=threshold,
            cpu_ms_by_batch={str(r["batch_size"]): r["cpu_ms"] for r in rows},
            mps_sync_ms_by_batch={str(r["batch_size"]): r["mps_sync_ms"] for r in rows},
            selected_device=str(self.route(16)), cached=True, source_sha256=source_sha256,
            mps_available=self.mps_device is not None, mps_authorized=self.allocation.mps_approved,
            synchronized_per_operation=True, new_calibration_operations=0)

    def score_ridge(self, values, models, *, meter=None):
        if not values or len(models) != 2:
            raise ValueError("nonempty six-feature batches and two ridge heads required")
        meter = self.meter if meter is None else meter
        width = len(values[0])
        if width not in (6, 10) or any(len(v) != width for v in values):
            raise ValueError("declared scorer batch feature width required")
        meter.charge("scorer_work_units", len(values)*width*2)
        device, t = self.route(len(values)), self.torch
        def run():
            op = lambda fn: self._op(device, fn)
            x = op(lambda: t.tensor(values, dtype=t.float32, device=device))
            outputs = []
            for scale, beta in models:
                s = op(lambda: t.tensor(scale, dtype=t.float32, device=device))
                b = op(lambda: t.tensor(beta, dtype=t.float32, device=device))
                z = op(lambda: t.div(x, s))
                y = op(lambda: t.matmul(z, b))
                outputs.append(op(lambda: y.to("cpu")).tolist())
            return list(map(list, zip(*outputs)))
        return self._timed(device, run, scoring=True)

    def update_ridge(self, x_values, y_values, *, ridge=1.0):
        """Batched source-only weight update. Caller owns the data-role boundary."""
        if not x_values or len(x_values) != len(y_values) or not math.isfinite(ridge) or ridge <= 0:
            raise ValueError("bounded source batch and positive ridge required")
        device, t = self.route(len(x_values), update=True), self.torch
        width = len(x_values[0])
        if width not in (6, 10) or any(len(v) != width for v in x_values):
            raise ValueError("declared six/ten feature training matrix required")
        self.meter.charge("training_work_units", len(x_values)*width*width*2)
        def run():
            op = lambda fn: self._op(device, fn)
            x = op(lambda: t.tensor(x_values, dtype=t.float32, device=device))
            y = op(lambda: t.tensor(y_values, dtype=t.float32, device=device))
            squared = op(lambda: t.square(x))
            scale = op(lambda: t.mean(squared, dim=0))
            scale = op(lambda: t.sqrt(scale))
            small = op(lambda: t.lt(scale, 1e-8))
            ones = op(lambda: t.ones_like(scale))
            scale = op(lambda: t.where(small, ones, scale))
            z = op(lambda: t.div(x, scale))
            zt = op(lambda: t.transpose(z, 0, 1))
            lhs = op(lambda: t.matmul(zt, z))
            lhs = op(lambda: t.mul(lhs, 2.))  # existing antisymmetric ridge augmentation
            eye = op(lambda: t.eye(len(x_values[0]), dtype=t.float32, device=device))
            regularizer = op(lambda: t.mul(eye, ridge))
            lhs = op(lambda: t.add(lhs, regularizer))
            rhs = op(lambda: t.matmul(zt, y))
            rhs = op(lambda: t.mul(rhs, 2.))
            beta = op(lambda: t.linalg.solve(lhs, rhs))
            return op(lambda: scale.to("cpu")).numpy(), op(lambda: beta.to("cpu")).numpy()
        return self._timed(device, run, update=True)

    def query_runtime(self, prompt, schema=None, *, seed=0):
        if self.runtime is None:
            self.stats["symbolic_fallback_calls"] += 1
            return dict(content="", termination="pure_symbolic_no_runtime", inference_ran=False)
        if not self.allocation.llm_approved:
            raise ValueError("llama runtime requires separate explicit approval")
        # PersistentMetalRuntime.complete blocks until its nonstreaming HTTP
        # response has terminated. Partial/streaming values are refused here.
        start = time.perf_counter()
        try:
            result = self.runtime.complete(prompt, schema, temperature=0., seed=seed)
            if result.get("termination") not in ("natural_or_stop", "hit_token_cap"):
                raise ValueError("runtime response has not fully terminated")
            self.stats["runtime_work_units"] += int(result.get("telemetry", {}).get("generated_tokens") or 0)
            return result
        finally:
            self.stats["runtime_calls"] += 1
            self.stats["runtime_wall_ms"] += (time.perf_counter()-start)*1000

    @staticmethod
    def supervise(repository, request, allocation, *, run_id, directory=None):
        """One durable reservation, kernel CPU cap and parent wall/RSS watchdog.

        Memory enforcement is explicitly sampled RSS (20 ms watchdog), not a
        macOS RLIMIT_AS claim. GPU/driver virtual memory mappings are not RSS.
        Failure/kill consumes the attempt and its measured/reserved debit.
        """
        repository = Path(repository).resolve()
        sandbox = Sandbox(repository, directory or repository/"runs/experimental/wave24-azr")
        with sandbox.locked():
            carry_recorded_dev_usage(sandbox, repository, allocation)
            remaining = allocation.session_limit_s-allocation.carried_used_s-sandbox.used_s()
            if allocation.session_refresh_s > 0:
                remaining = max(remaining, allocation.session_refresh_s)
            if allocation.wall_s > remaining:
                raise ValueError("insufficient carried allowance; no session reset")
            caps = dict(wall_s=allocation.wall_s, cpu_s=allocation.cpu_s, memory_mb=allocation.memory_mb,
                        real_steps=0, imagined_transitions=0, updates=request["config"]["max_source_rows"])
            grant_id = "wave24-"+run_id
            sandbox.grant(grant_id, allocation.owner, allocation.reason, caps, allocation.session_limit_s,
                          allocation.carried_used_s, device="gpu" if allocation.mps_approved else "cpu",
                          memory_policy="sampled_rss")
            attempt = sandbox.directory/"attempts"/run_id
            attempt.mkdir(parents=True, exist_ok=False)
            write_new(attempt/"input.json", dict(request, allocation=asdict(allocation)))
            sandbox.append("reserved", dict(run_id=run_id, wall_cap_s=allocation.wall_s,
                           grant=grant_id, request_sha256=digest(request), phase="wave24_azr"))
            start, peak, failure, proc = time.monotonic(), 0., None, None
            temporary = request.get("temporary_output_directory")
            output = Path(temporary)/"worker.json" if temporary else attempt/"worker.json"
            try:
                env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1",
                           NEXUS_W24_SUPERVISED="1", NEXUS_W24_CPU_CAP=str(allocation.cpu_s))
                with (attempt/"worker.log").open("xb") as log:
                    proc = subprocess.Popen([sys.executable, str(repository/"scripts/run_wave24_azr_ruler_cegis.py"),
                        "--worker-input", str(attempt/"input.json"), "--worker-output", str(output)],
                        cwd=repository, env=env, stdout=log, stderr=log, start_new_session=True)
                    while proc.poll() is None:
                        elapsed = time.monotonic()-start
                        rss = _rss_kib(proc.pid)
                        if rss is not None:
                            peak = max(peak, rss/1024.)
                        elif proc.poll() is None:
                            failure = "rss_unreadable"
                            os.killpg(proc.pid, signal.SIGKILL)
                            break
                        if elapsed > allocation.wall_s or peak > allocation.memory_mb:
                            failure = "wall_cap" if elapsed > allocation.wall_s else "rss_cap"
                            os.killpg(proc.pid, signal.SIGKILL)
                            break
                        # Polling wait serves the watchdog; no experiment is left detached.
                        try:
                            proc.wait(timeout=.02)
                        except subprocess.TimeoutExpired:
                            pass
                    proc.wait(timeout=2)
                if proc.returncode:
                    failure = failure or "worker_exit_"+str(proc.returncode)
            finally:
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=2)
                wall = time.monotonic()-start
                sandbox.append("settled", dict(run_id=run_id, charged_wall_s=wall,
                    peak_rss_mib=peak, failure=failure, exit_code=None if proc is None else proc.returncode))
            if temporary:
                # Preserve failed/partial engineering evidence before the
                # caller's TemporaryDirectory is removed. Never artifacts/.
                shutil.copytree(temporary, attempt/"private-output", dirs_exist_ok=False)
            receipt = dict(run_id=run_id, wall_s=wall, peak_rss_mib=peak, failure=failure,
                           carried_used_s=allocation.carried_used_s, session_used_s=allocation.carried_used_s+sandbox.used_s(),
                           session_remaining_s=allocation.session_limit_s-allocation.carried_used_s-sandbox.used_s(),
                           memory_enforcement="sampled_rss_20ms", attempt_directory=str(attempt))
            write_new(attempt/"receipt.json", receipt)
            return (read(output) if output.exists() else dict(schema="wave24_azr_v1", execution_status="INCOMPLETE")), receipt
