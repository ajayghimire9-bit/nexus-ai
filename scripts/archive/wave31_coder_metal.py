"""Wave 31 coder smoke on Apple-Silicon Metal (development, NOT LOCKED). Owner grant 2026-10-26: Metal enabled for
the 8/16-task smoke; the 7B coder is allowed only if Metal brings the 16-task smoke well under 10 minutes.

Same tasks (wave30 dev seed 751), prompt (v4) and attempt loop as the Wave 30 CPU diagnosis, so only the backend /
checkpoint changes. Telemetry: backend actually used, llama-server's Metal offload log lines, generated tokens/s,
and the GPU 'Device Utilization %' sampled from ioreg (no sudo) while the smoke runs.
Owner's 4 failure buckets: unparsable (unparsable / invalid_spec / too_long), runtime_error, public_demo_miss
(fails_public), held_out_miss (fits_public_wrong_heldout)."""
import argparse, json, os, re, subprocess, sys, threading, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MODELS = {"instruct": ROOT / ".models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
          "coder": Path("/Users/ajayghimire/Projects/nexus-ai/.models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"),
          "coder7b": Path("/Users/ajayghimire/Projects/nexus-ai/.models/qwen2.5-coder-7b-instruct-q4_k_m.gguf")}
BUCKET4 = {"unparsable": "unparsable", "invalid_spec": "unparsable", "too_long": "unparsable",
           "runtime_error": "runtime_error", "fails_public": "public_demo_miss",
           "fits_public_wrong_heldout": "held_out_miss", "correct": "correct"}


def gpu_util():
    out = subprocess.run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"], capture_output=True, text=True).stdout
    m = re.search(r'"Device Utilization %"=(\d+)', out)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="coder"); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--max-rss-mib", type=int, default=4096)
    a = ap.parse_args()
    os.environ["NEXUS_QWEN15_PATH"] = str(MODELS[a.model])
    os.environ.setdefault("NEXUS_METAL_LEDGER", str(ROOT / "runs/experimental/wave24-agi/wave31_metal_ledger.json"))
    from nexus.wave24_qwen_engine import QwenEngine
    from nexus.wave30_arms import stream
    from nexus.wave30_coder import solve_a2_v4
    from nexus.wave30_harness import verify_kernel_pin
    verify_kernel_pin()
    import nexus.seed.metal_model_runtime as MR
    log_path = ROOT / f"runs/experimental/wave24-agi/wave31_llama_server_{a.model}_n{a.n}.log"
    _init = MR.PersistentMetalRuntime.__init__
    MR.PersistentMetalRuntime.__init__ = lambda self, c, g, log_path=log_path: _init(self, c, g, log_path=str(log_path))
    idle = [gpu_util() for _ in range(3)]
    t0 = time.perf_counter()
    eng = QwenEngine(max_tokens=160, grant_config={"reason": "wave31 coder smoke (owner Metal grant 2026-10-26)",
                                                   "max_rss_mib": a.max_rss_mib, "max_wall_seconds_per_call": 60.0,
                                                   "max_session_metal_seconds": 1800.0})
    samples, stop = [], threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append(gpu_util()); stop.wait(0.5)
    rows, meta = [], {}
    try:
        meta = eng.start()
        th = threading.Thread(target=sampler, daemon=True); th.start()
        for i, t in enumerate(stream(751)[:a.n]):
            att = solve_a2_v4(eng, t["public"], t["query"], t["answer"], seed=i)
            rows.append(dict(task=i, family=t["family"], attempts=att, final=att[-1]["bucket"]))
            print(i, t["family"], [x["bucket"] for x in att], flush=True)
    finally:
        stop.set()
        log = ""
        try:
            lp = getattr(eng.rt, "log_path", None) or getattr(eng.rt, "stderr_path", None)
            log = Path(lp).read_text(errors="replace") if lp else ""
        except Exception:
            pass
        tel = eng.telemetry(); eng.close()
        wall = time.perf_counter() - t0
        with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as f:
            f.write(json.dumps(dict(run=f"wave31-coder-metal-{a.model}-n{a.n}", wall_s=wall, status="COMPLETE",
                                    backend=tel["backend"])) + "\n")
    s = [x for x in samples if x is not None]
    offload = [ln.strip() for ln in log.splitlines() if re.search(r"offload|Metal|MTL|GPU", ln)][:12]
    rep = dict(model=MODELS[a.model].name, backend=tel["backend"], n_tasks=len(rows), smoke_wall_s=round(wall, 1),
               llm_wall_s=round(tel["wall_s"], 1), generated_tokens=tel["generated_tokens"], input_tokens=tel["input_tokens"],
               generated_tok_per_s=round(tel["generated_tokens"] / max(1e-9, tel["wall_s"]), 2),
               gpu_util_idle=idle, gpu_util_during=dict(n=len(s), mean=round(sum(s) / max(1, len(s)), 1), max=max(s or [0])),
               server_log_metal_lines=offload, start_meta={k: v for k, v in meta.items() if k in ("backend", "n_gpu_layers")},
               attempt_buckets=dict(Counter(BUCKET4[x["bucket"]] for r in rows for x in r["attempts"])),
               final_buckets=dict(Counter(BUCKET4[r["final"]] for r in rows)))
    Path(ROOT / f"artifacts/wave31_coder_metal_{a.model}_n{a.n}.json").write_text(json.dumps(dict(report=rep, rows=rows), default=repr))
    print(json.dumps(rep, default=repr))


if __name__ == "__main__":
    main()
