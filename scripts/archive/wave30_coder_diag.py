"""A2 diagnosis smoke suite: 8 dev tasks (seed 751), up to 4 attempts, buckets per attempt. Development only.
  --model instruct|coder   --variant orig|fewshot"""
import argparse, json, os, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
ap = argparse.ArgumentParser(); ap.add_argument("--model", default="instruct"); ap.add_argument("--variant", default="orig")
a = ap.parse_args()
MODELS = {"instruct": ROOT / ".models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
          "coder": Path("/Users/ajayghimire/Projects/nexus-ai/.models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")}
os.environ["NEXUS_QWEN15_PATH"] = str(MODELS[a.model])
from nexus.wave24_qwen_engine import QwenEngine
from nexus.wave30_arms import stream
from nexus.wave30_coder import solve_a2_diag, solve_a2_v3, solve_a2_v4
from nexus.wave30_harness import verify_kernel_pin
verify_kernel_pin()
t0 = time.perf_counter()
eng = QwenEngine(max_tokens=160)
rows = []
try:
    eng.start()
    for i, t in enumerate(stream(751)[:8]):
        att = (solve_a2_v3(eng, t["public"], t["query"], t["answer"], seed=i) if a.variant == "v3" else solve_a2_v4(eng, t["public"], t["query"], t["answer"], seed=i) if a.variant == "v4" else
               solve_a2_diag(eng, t["public"], t["query"], t["answer"], seed=i, variant=a.variant))
        rows.append(dict(task=i, family=t["family"], attempts=att, final=att[-1]["bucket"]))
        print(i, t["family"], [x["bucket"] for x in att], flush=True)
finally:
    tel = eng.telemetry(); eng.close()
    with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as f:
        f.write(json.dumps(dict(run=f"wave30-coder-diag-{a.model}-{a.variant}", wall_s=time.perf_counter() - t0,
                                status="COMPLETE", backend=tel["backend"])) + "\n")
rep = dict(model=MODELS[a.model].name, variant=a.variant, backend=tel["backend"],
           attempt_buckets=dict(Counter(x["bucket"] for r in rows for x in r["attempts"])),
           final_buckets=dict(Counter(r["final"] for r in rows)), input_tokens=tel["input_tokens"],
           generated_tokens=tel["generated_tokens"], llm_wall_s=round(tel["wall_s"], 1),
           s_per_generated_token=round(tel["wall_s"] / max(1, tel["generated_tokens"]), 3))
Path(ROOT / f"artifacts/wave30_coder_diag_{a.model}_{a.variant}.json").write_text(json.dumps(dict(report=rep, rows=rows), default=repr))
print(json.dumps(rep))
