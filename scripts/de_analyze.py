"""Stages 1-3 analysis (NOT LOCKED): pure post-processing of artifacts into the reported tables.
  python scripts/de_analyze.py stage1 | stage2 | stage3 FILE"""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def stage1():
    r = json.load(open(ROOT / "artifacts/de_stage1_regression.json"))
    print("suite | collected | passed | failed")
    for s, v in r["suites"].items():
        print(f"  {s:45s} {v['collected']:4d} {v['passed']:4d} {v['failed'] + v['errors']:3d}")
    tot = sum(v["passed"] for v in r["suites"].values()), sum(v["collected"] for v in r["suites"].values())
    print(f"  TOTAL {tot[0]}/{tot[1]} pass; revision {r['revision'][:7]}; v5 pin {r['kernel_pins']['v5'][:12]}")


def stage2():
    r = json.load(open(ROOT / "artifacts/de_stage2_proof.json"))
    ps = list(r["projects"].values())
    print(f"broken pipeline | expected reason | caught | exact reason | exit 0 + non-empty  (over {len(ps)} dev projects)")
    for n in ps[0]["rows"]:
        rs = [p["rows"][n] for p in ps]
        print(f"  {n:46s} {str(rs[0]['expected']):26s} {sum(x['caught'] for x in rs)}/{len(rs)}   "
              f"{sum(bool(x['exact']) for x in rs) if rs[0]['expected'] else '-'}/{len(rs)}   {sum(x['silent'] for x in rs)}/{len(rs)}")
    print("  STAGE 2", "PASS" if r["stage2_pass"] else "FAIL")


def binom_sign(wins, losses):
    n = wins + losses
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n if n else 1.0


def stage3(path):
    r = json.load(open(path))
    P = r["projects"]
    arms = list(next(iter(P.values()))["arms"])
    agg = {}
    for a in arms:
        rows = [p["arms"][a] for p in P.values()]
        sc = [x["scorecard"] for x in rows]
        agg[a] = dict(
            n=len(rows),
            correct=sum(s["1_correctness"]["independently_checked_correct"] for s in sc),
            silent=sum(s["1_correctness"]["silent_data_errors"] for s in sc),
            seen_ok=sum(s["1_correctness"]["seen_batches_correct"] for s in sc),
            heldout_ok=sum(s["1_correctness"]["heldout_batch3_correct"] for s in sc),
            unresolved=sum(s["1_correctness"]["unresolved_ambiguity"] for s in sc),
            finished=sum(s["2_completion"]["finished"] for s in sc), hard=sum(s["2_completion"]["hard_failures"] for s in sc),
            abstain=sum(s["2_completion"]["explicit_abstentions"] for s in sc),
            fresh=sum(s["3_reliability"]["freshness_violations"] for s in sc),
            idem=sum(s["3_reliability"]["idempotent"] for s in sc), rec=sum(s["3_reliability"]["crash_recovered"] for s in sc),
            rec_s=sum(s["3_reliability"]["recovery_s"] for s in sc) / len(sc),
            dup=sum(s["3_reliability"]["duplicate_side_effects"] for s in sc),
            proposals=sum(s["4_cost"]["proposer_calls"] for s in sc), runs=sum(s["4_cost"]["pipeline_runs"] for s in sc),
            check_runs=sum(s["4_cost"]["check_runs"] for s in sc), exec_cpu=sum(s["4_cost"]["exec_cpu_s"] for s in sc),
            check_cpu=sum(s["4_cost"]["check_cpu_s"] for s in sc), agent_cpu=sum(s["4_cost"]["agent_cpu_s"] for s in sc),
            wasted=sum(s["4_cost"]["wasted_cpu_s"] for s in sc), io=sum(s["4_cost"]["io_bytes"] for s in sc),
            dev_cpu=sum(s["4_cost"]["development_cpu_s"] for s in sc),
            op=sum(s["4_cost"]["operating_cpu_wall_s_per_batch"] for s in sc) / len(sc),
            clar=sum(s["5_human_dependence"]["clarifications"] for s in sc),
            unnec=sum(s["5_human_dependence"]["unnecessary_clarifications"] for s in sc),
            repairs=sum(s["5_human_dependence"]["engineering_repairs"] for s in sc),
            ops=sum(s["5_human_dependence"]["operational_interventions"] for s in sc),
            reasons=sorted({d for s in sc for d in s["1_correctness"]["diagnoses"]}))
    genuine = sum(len(p["genuine_questions"]) for p in P.values())
    held = [p["heldout"] for p in P.values()]
    n = len(P)
    print(f"projects {n}; genuine ambiguities in the data {genuine}; projects with held-out names "
          f"{sum(bool(h['names']) for h in held)}, held-out currencies {sum(bool(h['currencies']) for h in held)}, "
          f"held-out units {sum(bool(h['units']) for h in held)}, text deletion flag {sum(h['text_flag'] for h in held)}")
    rows = [
        ("1 Correctness", "independently checked correct", "correct", "{}/" + str(n)),
        ("", "silent data errors", "silent", "{}"), ("", "seen batches 1-2 correct", "seen_ok", "{}/" + str(n)),
        ("", "held-out batch 3 correct", "heldout_ok", "{}/" + str(n)), ("", "unresolved ambiguity", "unresolved", "{}/" + str(genuine)),
        ("2 Completion", "finished (submitted)", "finished", "{}/" + str(n)), ("", "hard failures", "hard", "{}"),
        ("", "explicit abstentions", "abstain", "{}"),
        ("3 Reliability", "freshness SLA violations", "fresh", "{}"), ("", "idempotent under rerun", "idem", "{}/" + str(n)),
        ("", "crash recovered", "rec", "{}/" + str(n)), ("", "mean recovery wall s", "rec_s", "{:.3f}"),
        ("", "duplicate side effects (rows)", "dup", "{}"),
        ("4 Cost", "proposer calls (model calls = 0)", "proposals", "{}"), ("", "pipeline executions", "runs", "{}"),
        ("", "check executions", "check_runs", "{}"), ("", "pipeline execution CPU s", "exec_cpu", "{:.2f}"),
        ("", "independent checking CPU s", "check_cpu", "{:.2f}"), ("", "agent process CPU s", "agent_cpu", "{:.2f}"),
        ("", "wasted work (rejected attempts) CPU s", "wasted", "{:.2f}"), ("", "storage / IO written MB", "io", "MB"),
        ("", "learning overhead", None, "0 (disabled)"), ("", "full development CPU s (all of the above)", "dev_cpu", "{:.2f}"),
        ("", "operating cost: mean wall s per batch run", "op", "{:.3f}"),
        ("5 Human dependence", "ASK_CLARIFICATION calls", "clar", "{}"), ("", "unnecessary clarifications", "unnec", "{}"),
        ("", "human engineering repairs", "repairs", "{}"), ("", "operational interventions", "ops", "{}"),
        ("6 Learning benefit", "vs Fresh / vs Placebo", None, "n/a: 0-history baseline (Stage 6+)"),
        ("7 Generalization", "split", None, "sealed test (held-out pools)" if "test" in str(path) else Path(path).stem),
    ]
    head = " | ".join(f"{a[:34]:>34s}" for a in arms)
    print(f"{'measure':20s} {'metric':42s} | {head}")
    for m, lab, key, fmt in rows:
        cells = []
        for a in arms:
            if key is None:
                cells.append(fmt)
            elif fmt == "MB":
                cells.append(f"{agg[a][key] / 2**20:.2f}")
            else:
                cells.append(fmt.format(agg[a][key]))
        print(f"{m:20s} {lab:42s} | " + " | ".join(f"{c[:34]:>34s}" for c in cells))
    c, nx = "Conventional_Agent_No_NEXUS_Checks", "NEXUS_Engineer_No_History"
    w = sum(P[p]["arms"][nx]["scorecard"]["1_correctness"]["independently_checked_correct"] and not
            P[p]["arms"][c]["scorecard"]["1_correctness"]["independently_checked_correct"] for p in P)
    l = sum(P[p]["arms"][c]["scorecard"]["1_correctness"]["independently_checked_correct"] and not
            P[p]["arms"][nx]["scorecard"]["1_correctness"]["independently_checked_correct"] for p in P)
    print(f"paired projects: NEXUS correct & Conventional wrong {w}, reverse {l}; one-sided sign test p = {binom_sign(w, l):.4f}")
    print("conventional diagnoses seen:", ", ".join(agg[c]["reasons"]))
    print("NEXUS diagnoses seen:", ", ".join(agg[nx]["reasons"]) or "none")
    return agg


if __name__ == "__main__":
    k = sys.argv[1]
    {"stage1": stage1, "stage2": stage2}.get(k, lambda: stage3(sys.argv[2]))()
