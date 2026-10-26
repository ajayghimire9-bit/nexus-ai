"""R3 (NOT LOCKED): coder-proposed solutions with independent checking and selection, vs an equally resourced coder-only
control and NEXUS search alone, on held-out families (F3 string / 2-op, F4 counter outputs).
Coder: qwen2.5-coder-7b-instruct Q4_K_M on Apple M4 Metal (owner Metal grant 2026-10-26; backend verified per run).
Proposal budget: up to 3 attempts per task, temperature 0 then 0.7, feedback = the first failing PUBLIC demo only (no query
answer, no checker verdicts). Output space: a JSON list (<= 4) of op names from a menu of exactly the 18 G_P primitives.
Arms on identical tasks:
  Coder-only   : answers with the coder program whenever it fits all public demos (no certificate)
  Coder+NEXUS  : the same proposal, checked by Checker v3 over the matched scope (exhaustive_UNIQUE / AMBIGUOUS / ABSTAIN);
                 if the coder finds no fitting program, fall back to NEXUS Fresh-v3 search (charged)
  Fresh-v3     : NEXUS search alone (sandboxed child, OS meter)
Native units: coder tokens (in / out), Metal wall seconds, checker + solver retired instructions."""
import json, os, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MODEL = Path("/Users/ajayghimire/Projects/nexus-ai/.models/qwen2.5-coder-7b-instruct-q4_k_m.gguf")
MENU = [("proj_a", "list of records -> list of their 'a' fields"), ("proj_b", "list of records -> list of their 'b' fields"),
        ("chars", "string -> list of characters"), ("join_chars", "list of characters -> string"),
        ("cells", "grid -> list of its cell values, row by row"), ("reach0", "graph -> sorted node ids reachable from node 0"),
        ("degrees", "graph -> counter {node: out-degree}"), ("objects", "grid -> connected same-colour objects (background 0)"),
        ("object_sizes", "objects -> list of object sizes"), ("count", "list -> counter {value: count}"),
        ("top1", "counter -> counter keeping only the most frequent entry"), ("keys", "counter -> sorted list of keys"),
        ("sort", "list -> sorted ascending"), ("dedupe_runs", "list -> drop consecutive duplicates"),
        ("rotate1", "list -> rotate left by 1"), ("prefix_sum", "ints -> running sums"),
        ("diff", "ints -> differences of neighbours"), ("running_max", "ints -> running maximum")]
SYSTEM = ("You compose programs from a fixed menu of operations. Each operation transforms the value produced by the "
          "previous one, starting from the input. Reply with ONLY a JSON list of 1 to 4 operation names, e.g. "
          '["chars", "sort"].\nOperations:\n' + "\n".join(f"- {n}: {d}" for n, d in MENU))


def main():
    os.environ["NEXUS_QWEN15_PATH"] = str(MODEL)
    os.environ.setdefault("NEXUS_METAL_LEDGER", str(ROOT / "runs/experimental/wave24-agi/wave31_metal_ledger.json"))
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave31_grammar as G
    from nexus import wave34_tasks as T4
    from nexus import checker_kernel_v2 as V
    from nexus.wave24_qwen_engine import QwenEngine
    R.claim("wave36", "dev", list(R.REGISTRY[("wave36", "dev")]), run_id="w36-coder-dev", record=False)
    spec = dict(zip([n for n, _ in MENU], G.G_P))
    tasks = T4.family_stream(T4.F3, "r3dev", 2, "F3") + T4.family_stream(T4.F4, "r3dev", 2, "F4")
    ev = E.Evaluator(depth=4, checker=3)
    eng = QwenEngine(max_tokens=60, grant_config={"reason": "wave36 R3 coder track", "max_rss_mib": 7168,
                                                  "max_wall_seconds_per_call": 60.0, "max_session_metal_seconds": 1800.0})
    t0 = time.perf_counter()
    rows = []
    try:
        meta = eng.start()
        for k, t in enumerate(tasks):
            prog, fb, att = None, "", 0
            for att in range(1, 4):
                user = "Examples (input -> output):\n" + "\n".join(f"{json.dumps(x)} -> {json.dumps(y)}" for x, y in t["public"]) + \
                       ("\n" + fb if fb else "") + "\nProgram:"
                text, _row = eng.complete(SYSTEM, user, temperature=0.0 if att == 1 else 0.7, seed=k * 10 + att,
                                          purpose="w36-R3", prefix="[", stop=("<|im_end|>", "\n\n", "]"))
                # accept quoted or bare names (the 7B coder writes bare names; the first run's quoted-only parser was a bug)
                names = re.findall(r'[a-z_][a-z_0-9]*', text.split("]")[0])
                if not names or len(names) > 4 or any(n not in spec for n in names):
                    fb = "Use only operation names from the menu, 1 to 4 of them."
                    continue
                cand = [dict(spec[n]) for n in names]
                bad = next(((x, y) for x, y in t["public"] if V.key(V.run(cand, x)[0]) != V.key(y)), None)
                if bad is None:
                    prog = cand
                    break
                got = V.run(cand, bad[0])[0]
                fb = f"Your program {json.dumps(names)} gave {json.dumps(got)} for input {json.dumps(bad[0])}; expected {json.dumps(bad[1])}."
            r = dict(family=t["category"], core=t["core"], attempts=att, coder_fit=prog is not None)
            if prog is not None:
                ans = V.run(prog, t["query"])[0]
                r["coder_only_correct"] = V.key(ans) == V.key(t["answer"])
                evd = {"checker_version": 3, "public": t["public"], "query": t["query"], "claimed_answer": ans, "candidate": prog,
                       "scope": G.matched_scope(4), "lemmas": [], "proofs": [], "trace": {}}
                m = {}
                v = ev._check(evd, m)
                r.update(nexus_label=v["label"], nexus_correct=v["label"] == "exhaustive_UNIQUE" and r["coder_only_correct"],
                         nexus_check_instr=m.get("eval_instr", 0), fallback=False)
            else:
                r.update(coder_only_correct=False)
            rows.append(r)
            print(k, t["category"], "/".join(t["core"]), "fit" if prog else "miss", r.get("nexus_label"), r["coder_only_correct"], flush=True)
    finally:
        tel = eng.telemetry(); eng.close()
    wall = time.perf_counter() - t0
    # NEXUS fallback (coder misses) and Fresh-v3 on every task, in the sandbox, OS-metered
    ch = E.Child("0")
    for k, (t, r) in enumerate(zip(tasks, rows)):
        f = ev.solve(ch, t, "Fresh", "matched", [], f"r3:{k}", {"matched_depth": 4, "checker": 3})
        r.update(fresh_label=f["label"], fresh_correct=f["correct"], fresh_work=f["ext"]["evaluator_work"])
        if not r["coder_fit"]:
            r.update(nexus_label=f["label"], nexus_correct=f["correct"], nexus_check_instr=f["ext"]["evaluator_work"], fallback=True)
    ch.close()
    out = dict(model=MODEL.name, backend=tel["backend"], metal_wall_s=round(tel["wall_s"], 1), coder_wall_s=round(wall, 1),
               tokens_in=tel["input_tokens"], tokens_out=tel["generated_tokens"], n=len(rows), rows=rows)
    for fam in ("F3", "F4", "ALL"):
        rs = [r for r in rows if fam == "ALL" or r["family"] == fam]
        out[fam] = dict(n=len(rs), coder_fit=sum(r["coder_fit"] for r in rs),
                        coder_only_correct=sum(r["coder_only_correct"] for r in rs),
                        coder_only_wrong=sum(r["coder_fit"] and not r["coder_only_correct"] for r in rs),
                        nexus_correct=sum(r["nexus_correct"] for r in rs),
                        nexus_wrong=sum(r["nexus_label"] == "exhaustive_UNIQUE" and not r["nexus_correct"] for r in rs),
                        nexus_ambiguous=sum(r["nexus_label"] == "AMBIGUOUS" for r in rs),
                        fresh_correct=sum(r["fresh_correct"] for r in rs),
                        nexus_instr=sum(r["nexus_check_instr"] for r in rs), fresh_instr=sum(r["fresh_work"] for r in rs))
    (ROOT / "artifacts/wave36_coder_dev.json").write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run="w36-coder-dev", wall_s=time.perf_counter() - t0, status="COMPLETE", backend=tel["backend"]))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}))


if __name__ == "__main__":
    main()
