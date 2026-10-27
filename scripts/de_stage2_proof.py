"""Stage 2 pass-condition test (NOT LOCKED): the independent evaluator against deliberately broken pipelines on every dev
project. Each broken pipeline is the shared generator (de_template) with exactly ONE decision wrong; all of them exit 0 and
write non-empty tables (silent corruption). Pass = the correct pipeline is judged correct on every project (no false alarm)
AND each of the 8 required broken pipelines is caught with its exact predeclared diagnostic reason on every project.
Supplementary single-bug classes (timestamp text order, missing FX, silent drop, lateness ignored, dimension append, and a
LUCKY guess that happens to be right) are reported too. Writes artifacts/de_stage2_proof.json + example pipelines."""
import json, shutil, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import de_env as E, de_evaluator as V, de_template as T, seed_registry as R
from nexus.wave31_evaluator import ledger_append

REQUIRED = [  # (name, decision flips, expected reason)
    ("1 fan-out join double counting", {"revenue_join": "join_sum"}, "FANOUT_DOUBLE_COUNT"),
    ("2 dropping late corrections", {"cdc_incremental": "watermark"}, "DROPPED_LATE_CHANGES"),
    ("3 updates applied out of event-time order", {"cdc_apply": "seq_order"}, "ARRIVAL_ORDER_APPLY"),
    ("4 ignoring soft deletes", {"deletes": "hard_only"}, "IGNORED_SOFT_DELETES"),
    ("5 unit mismatch", {"units": "assume_kg"}, "UNIT_MISMATCH"),
    ("6 non-idempotent duplicate append on rerun", {"bronze_dedup": "append"}, "NON_IDEMPOTENT_RERUN"),
    ("7 malformed rows coerced to 0", {"weight_parse": "coerce_zero"}, "MALFORMED_ZERO_FILLED"),
    ("8 guessing an ambiguous business rule", "GUESS_WRONG", "GUESSED_AMBIGUOUS_RULE"),
]
SUPPLEMENT = [
    ("S1 timestamps compared as text", {"ts_parse": "text"}, "TEXT_TIMESTAMP_ORDER"),
    ("S2 no currency conversion", {"fx": "none"}, "NO_CURRENCY_CONVERSION"),
    ("S3 malformed rows silently dropped", {"weight_parse": "drop_silent"}, "MALFORMED_DROPPED"),
    ("S4 lateness window ignored", {"sla_window": "ignore"}, "LATENESS_WINDOW_IGNORED"),
    ("S5 dimension snapshot appended", {"dims_load": "append"}, "NON_IDEMPOTENT_RERUN"),
    ("S6 lucky guess (right answer, never asked)", "GUESS_RIGHT", "UNASKED_AMBIGUITY"),
]


def bundle(dirp, spec, choice, clar):
    dirp.mkdir(parents=True)
    (dirp / "pipeline.py").write_text(T.emit(choice))
    (dirp / "config.json").write_text(json.dumps(T.config_from_spec(spec, clar), sort_keys=True))


def main():
    seeds = list(R.REGISTRY[("de1", "dev")])[:6]
    R.claim("de1", "dev", seeds, run_id="de1-dev", record=False)
    t0, out = time.perf_counter(), {}
    for seed in seeds:
        p = E.make_project(seed, "dev")
        w = Path(tempfile.mkdtemp(prefix="de2_"))
        E.write_project(p, w / "inputs", w / "truth")
        truth = json.loads((w / "truth/truth.json").read_text())
        spec = json.loads((w / "inputs/docs/spec.json").read_text())
        rows = {}
        for name, flips, want in [("0 correct pipeline (asks)", {}, None)] + REQUIRED + SUPPLEMENT:
            sh = V.Stakeholder(truth)
            choice, clar = T.correct_choice(), {}
            if isinstance(flips, dict):
                choice.update(flips)
                clar = {q: sh.ask(*q.split(":", 1)) for q in truth["answers"]}
            else:   # guessing: no clarification; policies set to the wrong (or, for the lucky row, the right) answers
                right = flips == "GUESS_RIGHT"
                a = truth["answers"]
                cv = a.get("carrier_volume:CANCELLED")
                if cv:
                    choice["carrier_uncovered"] = cv if right else ("exclude" if cv == "include" else "include")
                sb = [v for k, v in a.items() if k.startswith("status_bucket:")]
                if sb:
                    choice["bucket_uncovered"] = sb[0] if right else next(x for x in ("open", "fulfilled", "cancelled") if x != sb[0])
            bd = w / "bundles" / name.split()[0]
            bundle(bd, spec, choice, clar)
            if seed == seeds[0]:
                shutil.copy(bd / "pipeline.py", ROOT / f"artifacts/de_stage2/pipeline_{name.split()[0]}.py")
            r = V.evaluate(truth, V.run_protocol(bd, w / "inputs", w / "work"), sh.log)
            rows[name] = dict(expected=want, caught=not r["correct"], exact=(want in r["reasons"]) if want else None,
                              silent=r["exits_ok"] and r["nonempty"], correct=r["correct"], reasons=r["reasons"],
                              idempotent=r["idempotent"], recovered=r["recovered"], exits=r["exits"])
        out[p["project"]] = dict(rows=rows, twists=truth["twists"], features=truth["features"])
        shutil.rmtree(w)
        print(p["project"], "correct ok:", rows["0 correct pipeline (asks)"]["correct"],
              "required caught+exact:", sum(rows[n]["caught"] and rows[n]["exact"] for n, _, _ in REQUIRED), "/8", flush=True)
    req_ok = all(out[pj]["rows"][n]["caught"] and out[pj]["rows"][n]["exact"] and out[pj]["rows"][n]["silent"]
                 for pj in out for n, _, _ in REQUIRED)
    corr_ok = all(out[pj]["rows"]["0 correct pipeline (asks)"]["correct"] for pj in out)
    res = dict(projects=out, required_pass=req_ok, correct_pass=corr_ok, stage2_pass=req_ok and corr_ok,
               evaluator_sha256=__import__("hashlib").sha256((ROOT / "src/nexus/de_evaluator.py").read_bytes()).hexdigest())
    (ROOT / "artifacts/de_stage2_proof.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    ledger_append(dict(run="de-stage2-proof", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    print("STAGE 2 PASS" if res["stage2_pass"] else "STAGE 2 FAIL", "%.0fs" % (time.perf_counter() - t0))


if __name__ == "__main__":
    main()
