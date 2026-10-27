"""R2 development comparisons B and C (NOT LOCKED; de4/dev only), adapted from scripts/r1_dev_compare.py (unchanged): the
correct R2 pipeline with ONE wrong decision (every wrong option of all 18 decisions), the world's own incidents and class,
deployed directly; NexusOpsR2 with mode B0 | B1 and ordering C0 | C1 | C2. Identical event-level reconciliation, observations
and caps for every arm. Primary per the frozen rule: end-to-end correct cases; then total operator CPU over ALL cases.
---- R1 docstring ----
R1 development comparisons A and B (NOT LOCKED; de3/dev only, reusable; no claims).
A  conformance + metamorphic: single-fault mutants (every wrong option of every decision applied to the correct pipeline) and
   correct-option combinations, on dev worlds. Arms, each with its own stop-at-first-failure verify:
     A0 Stage 4 NEXUS suite over the post-fix grow (s4_checks, no monitor)
     A1 Stage 4 suite + replay_conformance + ack_durability over grow_obs
     A2 A1 + chunk_invariance
   Metrics: mutants rejected, false rejections of correct combinations, verify CPU; and the evidence label per mutant.
B  own-pipeline localisation and repair in operations: the correct pipeline with ONE wrong decision is deployed directly
   (no build), NexusOpsR1 in mode B0 (existing search strategy) vs B1 (provenance + shrinking + typed CEGIS).
   Metrics: self-detected, end-to-end correct, true decision in the suspect set / rank, full verifications, operator CPU.
  python scripts/r1_dev_compare.py A|B OUT.json [--seeds 951,952] [--mutants d=o,...]"""
import argparse, json, shutil, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import r1_seeds  # noqa: F401
from nexus import r2_seeds  # noqa: F401
from nexus import r1_checks as RC, r2_env as RE, r2_template as RT, r2_ops as RO, s4_checks as C, s5_ops as O
from nexus.wave31_evaluator import ledger_append
import r2_run as RUN

CORRECT_COMBOS = [{}, {"commit_protocol": "transactional", "gold_maintenance": "full_recompute"}]


def mutants():
    out = []
    for d, opts in RT.DECISIONS.items():
        for o in opts:
            if o not in RT.CORRECT[d]:
                out.append((d, o))
    return out


def part_a(seeds, outp):
    res, t0 = {}, time.perf_counter()
    for seed in seeds:
        w = RE.make_world(seed, "dev")
        enc = RE.encode(w, "build")
        work = Path(tempfile.mkdtemp(prefix="r1A_"))
        RE.write_log(enc, work / "vis", 8, archive=True)
        full = work / "vis" / "log"
        rows = []
        cases = [("correct", dict(RT.correct_choice(), **c)) for c in CORRECT_COMBOS] + \
                [(f"{d}={o}", dict(RT.correct_choice(), **{d: o})) for d, o in mutants()]
        for name, ch in cases:
            b = work / "b"
            b.mkdir(exist_ok=True)
            (b / "pipeline.py").write_text(RT.emit(ch))
            (b / "config.json").write_text(json.dumps(RT.config_from_spec(w["spec"])))
            row = dict(case=name)
            for arm in ("A0", "A1", "A2"):
                runner = C.Runner()
                if arm == "A0":
                    r = C.verify(b, w["spec"], full, work / "v", runner, suite=C.NEXUS)
                    label = None
                else:
                    suite = RC.NEXUS if arm == "A2" else [c for c in RC.NEXUS if c != "chunk_invariance"]
                    r = RC.verify(b, w["spec"], full, work / "v", runner, suite=suite)
                    label = RC.outcome(RC.evidence(r, RC.LAST.get("conformance", {}), suite)) if arm == "A2" else None
                bad = next((x["check"] for x in r if not x["ok"]), None)
                row[arm] = dict(rejected=bad is not None, by=bad, cpu_s=round(runner.cpu_s, 3), runs=runner.runs, label=label)
                shutil.rmtree(work / "v", ignore_errors=True)
            rows.append(row)
            print(seed, name, {a: (row[a]["by"], row[a]["cpu_s"]) for a in ("A0", "A1", "A2")}, "%.0fs" % (time.perf_counter() - t0), flush=True)
        res[w["spec"]["project"]] = rows
        shutil.rmtree(work, ignore_errors=True)
    Path(outp).write_text(json.dumps(dict(part="A", projects=res), indent=1, sort_keys=True))
    ledger_append(dict(run="r2-dev-compare-A", wall_s=time.perf_counter() - t0, status="COMPLETE"))


def part_b(seeds, outp, muts, modes=("B0", "B1"), c_mode="C0"):
    res, t0 = {}, time.perf_counter()
    if Path(outp).exists():
        res = json.loads(Path(outp).read_text())["projects"]
    for seed in seeds:
        w = RE.make_world(seed, "dev")
        for d, o in muts:
            for mode in modes:
                key = f"{w['spec']['project']}|{d}={o}|{mode}|{c_mode}"
                if key in res:
                    continue
                work = Path(tempfile.mkdtemp(prefix="r1B_"))
                ch = dict(RT.correct_choice(), **{d: o})
                b = work / "b"
                b.mkdir()
                (b / "pipeline.py").write_text(RT.emit(ch))
                (b / "config.json").write_text(json.dumps(RT.config_from_spec(w["spec"])))
                op = RO.NexusOpsR2("NEXUS_Fresh", detector=RUN.OP_DETECTOR, seed=seed, spec=w["spec"], mode=mode)
                op.c_mode = c_mode
                w0 = time.perf_counter()
                r = RUN.ops_once(w, "dev", seed, b, ch, op, work, "b")
                loc = [e for e in r["ledger"] if e["kind"] in ("own_pipeline_localised", "own_pipeline_unrepaired")]
                ranks = [e["suspects"].index(d) if d in e["suspects"] else None for e in loc]
                final_choice = next((a[1] for a in reversed(r["actions"]) if a[0] == "redeploy"), {})
                res[key] = dict(project=w["spec"]["project"], mutant=f"{d}={o}", mode=mode, c_mode=c_mode, correct=r["eval"]["correct"],
                                data_ok=r["eval"]["data_ok"], silent=r["eval"]["silent"], self_detected=r["eval"]["self_detected"],
                                escalations=r["cost"]["escalations"], localisations=len(loc), true_in_suspects=[x is not None for x in ranks],
                                rank=ranks, suspect_sizes=[len(e["suspects"]) for e in loc],
                                full_verifications=r["cost"].get("full_verifications", 0), shadow_tests=r["cost"]["shadow_tests"],
                                cheap_checks=r["cost"].get("cheap_checks", 0), shrink_tests=r["cost"].get("shrink_tests", 0),
                                operator_cpu_s=round(r["cost"]["agent_cpu_s"] + r["cost"]["shadow_cpu_s"], 3),
                                localisation_cpu_s=round(r["cost"].get("localisation_cpu_s", 0.0), 3),
                                repaired_to=final_choice.get(d) if final_choice else None, incidents=r["incidents"],
                                wall_s=round(time.perf_counter() - w0, 1))
                O._rm(work)
                Path(outp).write_text(json.dumps(dict(part="B", projects=res), indent=1, sort_keys=True))
                x = res[key]
                print(key, x["correct"], x["self_detected"], x["rank"], x["full_verifications"], x["operator_cpu_s"], x["wall_s"],
                      "%.0fs" % (time.perf_counter() - t0), flush=True)
                if time.perf_counter() - t0 > 820:
                    ledger_append(dict(run=f"r2-dev-compare-{c_mode}", wall_s=time.perf_counter() - t0, status="CHECKPOINT"))
                    return
    ledger_append(dict(run=f"r2-dev-compare-{c_mode}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part"); ap.add_argument("out"); ap.add_argument("--seeds", default="951,952,953")
    ap.add_argument("--mutants", default=""); ap.add_argument("--modes", default="B0,B1"); ap.add_argument("--c-mode", default="C0")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    if a.part == "A":
        part_a(seeds, a.out)
    else:
        muts = [tuple(x.split("=")) for x in a.mutants.split(",")] if a.mutants else mutants()
        part_b(seeds, a.out, muts, tuple(a.modes.split(",")), a.c_mode)
