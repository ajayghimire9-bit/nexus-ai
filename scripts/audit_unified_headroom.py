"""Bounded frozen-source inference, no fit or environment construction."""
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from nexus.core.strategy_memory_decide_bench import _task, obs_from_source, support_from_source
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution2.fit_clock import LOCKED_ARRAYS
from nexus.evolution2.generated_strategies import universe, leaf
from nexus.evolution2.persist_reset_path import disposable_model
from nexus.evolution2.unified_source_bench import ROOT, proxy_table

CONFIG = ROOT / "configs/unified_headroom_audit.json"
OUTPUT = ROOT / "artifacts/unified_headroom_audit.json"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_file(path, expected):
    if not path.is_file(): raise FileNotFoundError("required_frozen_file_missing:" + str(path))
    actual = sha(path)
    if actual != expected: raise ValueError("frozen_file_hash_mismatch:" + str(path))
    return actual


def tensor_hash(model):
    h = hashlib.sha256()
    for name, value in sorted(model.net.state_dict().items()):
        a = value.detach().cpu().numpy()
        h.update(name.encode()); h.update(str((a.shape, a.dtype)).encode()); h.update(a.tobytes())
    for name, value in sorted({**model.obs_rms.state_dict(), "epsilon":model.obs_rms.epsilon}.items()):
        a = np.asarray(value)
        h.update(name.encode()); h.update(str((a.shape,a.dtype)).encode()); h.update(a.tobytes())
    return h.hexdigest()


def summarize(rows, config):
    import math
    if any(type(r[k]) is not int for r in rows for k in ("model_bundle","query_bundle","offset")):
        raise ValueError("invalid_cell_identifier")
    expected = set(itertools.product(config["families"], config["model_bundles"], config["offsets"]))
    keys = [(r["family"],r["model_bundle"],r["offset"]) for r in rows]
    if len(keys) != len(expected) or set(keys) != expected: raise ValueError("incomplete_headroom_grid")
    for r in rows:
        if r["query_bundle"] != 1-r["model_bundle"]: raise ValueError("same_bundle_query")
        for k in ("anchor_best_raw", "grammar_best_raw", "headroom"):
            if type(r[k]) not in (int,float) or not math.isfinite(r[k]): raise ValueError("nonfinite_headroom")
        if not math.isclose(r["grammar_best_raw"]-r["anchor_best_raw"],r["headroom"],abs_tol=1e-12):
            raise ValueError("headroom_arithmetic")
        if r["headroom"] < -1e-12: raise ValueError("oracle_missing_anchor")
    counts = {f: sum(r["headroom"] >= config["minimum_raw_headroom"] for r in rows if r["family"]==f)
              for f in config["families"]}
    return {"eligible_by_family": counts, "eligible_total": sum(counts.values()),
        "screen_pass": sum(counts.values()) >= config["minimum_eligible_states"] and
                       all(n >= config["minimum_per_family"] for n in counts.values()),
        "mean_headroom_by_family": {f: sum(r["headroom"] for r in rows if r["family"]==f)/8 for f in counts},
        "no_positive_headroom_states": sum(r["headroom"] <= 1e-12 for r in rows)}


def run():
    c = json.loads(CONFIG.read_text())
    if c != {"version":"frozen_source_headroom_v1","families":["pendulum","acrobot"],
             "model_bundles":[0,1],"query_bundle_rule":"opposite_bundle","offsets":[0,32,64,96],
             "candidate_seed_base":700,"common_probe_horizon":16,"cap_s":60,"real_interaction_cap":0,
             "neural_state_cap":590592,"minimum_raw_headroom":1.,"minimum_eligible_states":4,"minimum_per_family":2}:
        raise ValueError("locked_config_mismatch")
    t0, cpu0 = time.perf_counter(), time.process_time()
    old = {str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"artifacts").rglob("*.json") if p!=OUTPUT}
    p = {"declared_complete":False,"scientific":False,"config":c,"rows":[],"provenance":[],
         "resources":{"neural_model_calls":0,"neural_model_states":0,"ledger_reports":[],
                      "real_interactions":0,"fits":0,"optimizer_updates":0},
         "historical_artifacts_sha256":old,"config_sha256":sha(CONFIG)}
    try:
        manifest = json.loads((ROOT/"artifacts/evolution2_fit_clock_run.json").read_text())
        expected_fits = set(itertools.product(c["families"],c["model_bundles"]))
        selected = [r for r in manifest["fits"] if (r["family"],r["bundle"]) in expected_fits]
        if len(selected)!=4 or {(r["family"],r["bundle"]) for r in selected}!=expected_fits:
            raise ValueError("incomplete_frozen_fit_manifest")
        p["fit_manifest_sha256"] = sha(ROOT/"artifacts/evolution2_fit_clock_run.json")
        # All file preconditions precede loading any model or scoring a state.
        for r in selected:
            verify_file(ROOT/r["path"],r["sha256"])
        arrays = [r for r in LOCKED_ARRAYS if r["bundle"] in c["model_bundles"]]
        p["source_array_sha256"] = {r["path"]:verify_file(ROOT/r["path"],r["sha256"]) for r in arrays}
        for f in c["families"]:
            episodes = []
            for b in c["model_bundles"]:
                with np.load(ROOT/f"artifacts/evolution2_source_arrays/{f}/bundle{b}_train.npz") as data:
                    episodes.append(set(data["env_seeds"].reshape(-1).tolist()))
            if episodes[0] & episodes[1]: raise ValueError("cross_bundle_episode_overlap")
        for r in selected:
            f,b = r["family"],r["bundle"]
            model = disposable_model(f,b)
            if str(model.device)!="cpu" or model.kind!="residual" or model.net.arch!="mlp" or tuple(model.net.hidden)!=(64,64):
                raise ValueError("unexpected_frozen_architecture_or_device")
            model.net.eval()
            for param in model.net.parameters(): param.requires_grad_(False)
            initial = tensor_hash(model)
            for o in c["offsets"]:
                if time.perf_counter()-t0 >= c["cap_s"]: raise TimeoutError("headroom_time_cap")
                task = _task(f"headroom:{f}:{b}:{o}","train",f,1-b,
                    support_from_source(f,1-b,start=o),obs_from_source(f,1-b,o))
                table, behaviors = proxy_table(task,c["candidate_seed_base"]+o,t0+c["cap_s"],p["resources"],
                    frozen_model=model,counter_names=("neural_model_calls","neural_model_states"))
                if p["resources"]["neural_model_states"] > c["neural_state_cap"]:
                    raise ValueError("neural_state_cap")
                anchor = max(behaviors[leaf(a).fingerprint]["raw_proxy"] for a in ANCHORS)
                best = max(v["raw_proxy"] for v in behaviors.values())
                p["rows"].append({"family":f,"model_bundle":b,"query_bundle":1-b,"offset":o,
                    "anchor_best_raw":anchor,"grammar_best_raw":best,"headroom":best-anchor,
                    "strategies":{s.fingerprint:{**behaviors[s.fingerprint],"unit":table[s]} for s in universe()}})
            after = tensor_hash(model)
            verify_file(ROOT/r["path"],r["sha256"])
            if after != initial: raise ValueError("frozen_model_state_changed")
            p["provenance"].append({**r,"state_before":initial,"state_after":after,"unchanged":True})
        p["summary"] = summarize(p["rows"],c)
        if len(p["resources"]["ledger_reports"])!=16 or any(r["status"]!="complete_execution" for r in p["resources"]["ledger_reports"]):
            raise ValueError("incomplete_model_accounting")
        if any(sha(ROOT/name)!=h for name,h in old.items()): raise ValueError("historical_file_changed")
        if time.perf_counter()-t0 >= c["cap_s"]: raise TimeoutError("headroom_time_cap")
        p["declared_complete"] = True
    except Exception as exc:
        p["failure"] = f"{type(exc).__name__}: {exc}"
    p["resources"].update(wall_s=time.perf_counter()-t0,cpu_s=time.process_time()-cpu0)
    start = json.loads((ROOT/"artifacts/unified_e225_e30_recovery.json").read_text())["session_ledger"]["used_after_s"]
    p["session_ledger"] = {"used_before_s":start,"used_after_s":start+p["resources"]["wall_s"],
        "remaining_after_s":3600-start-p["resources"]["wall_s"]}
    return p


if __name__ == "__main__":
    if OUTPUT.exists(): raise FileExistsError("preserve_previous_headroom_capture")
    if subprocess.check_output(["git","diff","HEAD","--name-only"],cwd=ROOT,text=True).strip():
        raise RuntimeError("commit_protocol_first")
    p = run()
    p["execution_sha"] = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    p["code_sha256"] = {name:sha(ROOT/name) for name in (
        "scripts/audit_unified_headroom.py","src/nexus/evolution2/unified_source_bench.py",
        "src/nexus/evolution2/generated_strategies.py","docs/NEXUS_UNIFIED_HEADROOM_AUDIT.md")}
    with OUTPUT.open("x") as out:
        json.dump(p,out,indent=2,allow_nan=False); out.write("\n")
    print(json.dumps({"complete":p["declared_complete"],"failure":p.get("failure"),"summary":p.get("summary"),
        "resources":{k:v for k,v in p["resources"].items() if k!="ledger_reports"}}))
