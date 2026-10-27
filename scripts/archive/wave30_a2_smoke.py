"""A2 development smoke on dev seed 751 (16 tasks). Development diagnostic only."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import checker_kernel as K
from nexus.wave24_qwen_engine import QwenEngine
from nexus.wave30_arms import stream
from nexus.wave30_coder import solve_a2
from nexus.wave30_harness import verify_kernel_pin
verify_kernel_pin()
t0 = time.perf_counter()
eng = QwenEngine(max_tokens=160)
rows = []
try:
    eng.start()
    for i, t in enumerate(stream(751)):
        r = solve_a2(eng, t["public"], t["query"], seed=i)
        r.update(correct=r["answer"] is not None and K.key(r["answer"]) == K.key(t["answer"]), family=t["family"])
        rows.append(r)
        print(i, t["family"], r["label"], r["correct"], r["attempts"], r["tokens"], flush=True)
finally:
    tel = eng.telemetry()
    eng.close()
    with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as f:
        f.write(json.dumps(dict(run="wave30-a2-smoke", wall_s=time.perf_counter() - t0, status="COMPLETE",
                                seeds=[751], backend=tel["backend"])) + "\n")
Path(ROOT / "artifacts/wave30_a2_smoke_dev.json").write_text(json.dumps(dict(rows=rows, telemetry=tel), default=repr))
print(json.dumps(dict(correct=sum(r["correct"] for r in rows), n=len(rows),
                      labels={l: sum(r["label"] == l for r in rows) for l in {r["label"] for r in rows}},
                      work=sum(r["work"] for r in rows), backend=tel["backend"], model=tel["model"],
                      generated_tokens=tel["generated_tokens"], input_tokens=tel["input_tokens"],
                      llm_wall_s=round(tel["wall_s"], 1))))
