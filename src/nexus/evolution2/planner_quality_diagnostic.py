"""E2.25 source-only quality-representation diagnostic, not a new proposer.

Reuses E2.24 scoring/accounting and E1 catalogue/candidate generation.
Fits small diagnostic ridge regressions; no neural training or collection.
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory import SupportBatch, describe_support
from nexus.core.strategy_memory_decide_bench import _task, family_context, obs_from_source, support_from_source
from nexus.evolution1.catalogue import digest, plan_bound
from nexus.evolution1.toy_loop import ANCHORS, VARIANTS, features
from nexus.evolution2.evidence_arbitration_bench import OFFSETS, ROOT, SOURCE, score_table, sha
from nexus.evolution2.methods import make_methods
from nexus.evolution2.observation_memory import FamilyNormalizer, load_source_train_obs
from nexus.evolution2.observation_memory_bench import _run_task
from nexus.evolution2.planner_adapter import generate_candidates

RESULTS = ROOT / "artifacts/evolution2_25_planner_quality.json"
PROTOCOL = ROOT / "docs/NEXUS_E2_25_PLANNER_QUALITY.md"
BASE = "e9a03b96921d1340a521f148cbcece3dfff368d8"
METHODS = ("paired_mean", "observation_kernel", "context_config_ridge", "candidate_context_ridge")
RIDGE = 1.0
MARGIN = 0.01
CAP_S = 60.0


def validate_source_separation(seed_sets):
    if set(seed_sets)!={0,1} or not all(seed_sets.values()) or set(seed_sets[0]) & set(seed_sets[1]):
        raise ValueError("overlapping_or_missing_source_episodes")
    return True


@dataclass(frozen=True, slots=True)
class PublicQualityContext:
    family: str
    observation: np.ndarray
    support: SupportBatch
    candidate_seed: int
    anchors: tuple[float, float]


def candidate_descriptor(variant, context, seed):
    bound = plan_bound(variant, context.n_actions, 1536)
    actions = generate_candidates(variant, bound.candidates_per_root, context.n_actions, seed)
    centered = actions.astype(np.float64) - (context.n_actions-1)/2
    sums = centered.mean(axis=1)
    first = np.asarray([np.mean(actions[:,0]==a) for a in range(3)])
    out = np.r_[first, sums.mean(), sums.std(), sums.min(), sums.max(),
                np.mean(actions[:,1:] != actions[:,:-1])]
    return out, digest(actions.tolist())


def quality_features(public, variant, normalizer, *, candidates):
    """No outcome table, task ID, hidden physics, or evaluator is accepted."""
    if type(public) is not PublicQualityContext:
        raise TypeError("public_quality_context_required")
    context = family_context(public.family)
    obs = normalizer.embed(public.observation)
    padded = np.pad(obs,(0,6-len(obs)))
    task = np.r_[1.,padded,describe_support(public.support,context),public.anchors]
    arm = np.asarray(features(variant,context))
    if candidates:
        descriptor,_ = candidate_descriptor(variant,context,public.candidate_seed)
        arm = np.r_[arm,descriptor]
    phi = np.outer(task,arm).reshape(-1)
    if not np.isfinite(phi).all():
        raise ValueError("nonfinite_quality_features")
    return phi


def fit_ridge(x,y):
    """Antisymmetric pairs, RMS scaling fitted only on training rows."""
    from nexus.nn.ridge import fit_ridge as fit
    return fit(x,y,ridge=RIDGE)


def predict_ridge(model, x):
    from nexus.nn.ridge import predict_ridge as predict
    return predict(model,x)


def collect_source_proxy(deadline):
    """Reproduce source contexts only. Full tables stay evaluator-owned."""
    records = []
    states = calls = 0
    for family in ("pendulum","acrobot"):
        for bundle in (0,1):
            for offset in OFFSETS:
                if time.perf_counter() >= deadline:
                    raise TimeoutError("source_only_cap")
                task_id = f"cal:{family}:{bundle}:{offset}"
                support = support_from_source(family,bundle,start=offset)
                obs = obs_from_source(family,bundle,offset)
                task = _task(task_id,"train",family,bundle,support,obs)
                seed = 7 + int(digest(task_id)[:8],16)%1000
                truth,cost = score_table(task,seed)
                receipt = _run_task(make_methods(7)["persistent_adaptive"],task,unit=truth,update=True)
                revealed = dict(zip(receipt["variants"],receipt["scores"]))
                public = PublicQualityContext(family,obs,support,seed,tuple(revealed[a.fingerprint] for a in ANCHORS))
                records.append({"family":family,"bundle":bundle,"offset":offset,"public":public,
                                "revealed":revealed,"truth":{v.fingerprint:s for v,s in truth.items()}})
                states += cost["imagined_transitions"]
                calls += cost["fake_step_calls"]
    return records,{"proxy_states":states,"fake_step_calls":calls,"catalogue_scores":192,
                    "source_receipts":96,"real_interactions":0}


def evaluate_fold(bank, queries, normalizer, *, family, held_bundle, deadline):
    """Fit only revealed training receipts; predict before reading query truth."""
    if any(r["family"]!=family or r["bundle"]==held_bundle for r in bank):
        raise ValueError("held_bundle_in_training")
    if any(r["family"]!=family or r["bundle"]!=held_bundle for r in queries):
        raise ValueError("query_split_mismatch")
    ids = {v.fingerprint:v for v in VARIANTS}
    pairs = list(itertools.combinations([v.fingerprint for v in VARIANTS],2))
    bank_pairs = {pair:[r for r in bank if all(fp in r["revealed"] for fp in pair)] for pair in pairs}
    supported = [pair for pair in pairs if bank_pairs[pair]]
    models = {}
    n_train = None
    for mode in (False,True):
        x,y = [],[]
        for r in bank:
            phis = {fp:quality_features(r["public"],ids[fp],normalizer,candidates=mode) for fp in r["revealed"]}
            for a,b in pairs:
                if a in phis and b in phis:
                    x.append(phis[a]-phis[b]); y.append(r["revealed"][a]-r["revealed"][b])
        models[mode] = fit_ridge(x,y)
        n_train = len(y)
    emb = np.stack([normalizer.embed(r["public"].observation) for r in bank])
    d = [np.linalg.norm(a-b) for i,a in enumerate(emb) for b in emb[i+1:]]
    length = max(float(np.median(d)),1e-3)
    rows = []
    for q in queries:
        if time.perf_counter() >= deadline:
            raise TimeoutError("fold_cap")
        all_phi = {mode:{fp:quality_features(q["public"],ids[fp],normalizer,candidates=mode) for fp in ids}
                   for mode in (False,True)}
        for a,b in supported:
            paired = bank_pairs[(a,b)]
            deltas = np.asarray([r["revealed"][a]-r["revealed"][b] for r in paired])
            distances = np.asarray([np.linalg.norm(normalizer.embed(r["public"].observation)-
                                                   normalizer.embed(q["public"].observation)) for r in paired])
            logw = -(distances/length)**2
            weights = np.exp(logw-np.max(logw)); weights /= weights.sum()
            predictions = {"paired_mean":float(np.mean(deltas)),"observation_kernel":float(weights @ deltas),
                           "context_config_ridge":predict_ridge(models[False],all_phi[False][a]-all_phi[False][b]),
                           "candidate_context_ridge":predict_ridge(models[True],all_phi[True][a]-all_phi[True][b])}
            # Query outcomes enter here, AFTER producing all four predictions.
            actual = q["truth"][a]-q["truth"][b]
            rows.append({"family":family,"held_bundle":held_bundle,"offset":q["offset"],
                         "arms":[a,b],"actual_delta":actual,"predictions":predictions})
    return rows,{"family":family,"held_bundle":held_bundle,"training_bundle":1-held_bundle,
                 "training_contexts":len(bank),"training_pairs":n_train,
                 "supported_pairs":[list(p) for p in supported],"unsupported_pair_count":66-len(supported),
                 "kernel_length_train_only":length,
                 "parameter_counts":{str(k):len(v[1]) for k,v in models.items()},
                 "model_hashes":{str(k):digest([v[0].tolist(),v[1].tolist()]) for k,v in models.items()}}


def summarize(rows):
    out = {}
    for name in METHODS:
        errors = [abs(r["predictions"][name]-r["actual_delta"]) for r in rows]
        eligible = [r for r in rows if abs(r["actual_delta"]) >= MARGIN]
        abstain = [abs(r["predictions"][name]) < MARGIN for r in eligible]
        loss = [0.5 if s else float(np.sign(r["predictions"][name])!=np.sign(r["actual_delta"]))
                for r,s in zip(eligible,abstain)]
        out[name] = {"mae":float(np.mean(errors)),"sign_loss":float(np.mean(loss)) if loss else None,
                     "abstention_rate":float(np.mean(abstain)) if abstain else None,
                     "n_pairs":len(rows),"n_meaningful_pairs":len(eligible)}
    return out


def validate(payload):
    receipts = payload["source_receipts"]
    expected_contexts = {(f,b,o) for f in ("pendulum","acrobot") for b in (0,1) for o in OFFSETS}
    keys = [(r["family"],r["bundle"],r["offset"]) for r in receipts]
    if len(keys)!=16 or set(keys)!=expected_contexts:
        raise ValueError("incomplete_source_contexts")
    valid_ids = {v.fingerprint for v in VARIANTS}
    for r in receipts:
        if (len(r["revealed"])!=6 or not set(r["revealed"])<=valid_ids
                or not {a.fingerprint for a in ANCHORS}<=set(r["revealed"])):
            raise ValueError("invalid_six_receipt_context")
        for v in r["revealed"].values():
            if type(v) not in (int,float) or not math.isfinite(v):
                raise ValueError("nonfinite_source_receipt")
    folds = payload["folds"]
    if len(folds)!=4 or {(r["family"],r["held_bundle"]) for r in folds} != {(f,b) for f in ("pendulum","acrobot") for b in (0,1)}:
        raise ValueError("incomplete_folds")
    expected = set()
    for fold in folds:
        bank = [r for r in receipts if r["family"]==fold["family"] and r["bundle"]!=fold["held_bundle"]]
        required = {pair for pair in itertools.combinations([v.fingerprint for v in VARIANTS],2)
                    if any(set(pair)<=set(r["revealed"]) for r in bank)}
        declared = [tuple(p) for p in fold["supported_pairs"]]
        if len(declared)!=len(set(declared)) or set(declared)!=required:
            raise ValueError("incomplete_supported_pairs")
        if fold["training_contexts"]!=4 or fold["training_pairs"]!=60:
            raise ValueError("unmatched_source_receipts")
        for offset in OFFSETS:
            for a,b in fold["supported_pairs"]:
                expected.add((fold["family"],fold["held_bundle"],offset,a,b))
    actual = []
    for r in payload["rows"]:
        actual.append((r["family"],r["held_bundle"],r["offset"],*r["arms"]))
        if set(r["predictions"])!=set(METHODS): raise ValueError("missing_method")
        for v in [r["actual_delta"],*r["predictions"].values()]:
            if type(v) not in (int,float) or not math.isfinite(v): raise ValueError("nonfinite_metric")
    if len(actual)!=len(set(actual)) or set(actual)!=expected: raise ValueError("incomplete_pair_grid")
    return True


def run():
    t0,cpu0 = time.perf_counter(),time.process_time()
    deadline = t0+CAP_S
    old = {str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"artifacts").glob("*.json") if p!=RESULTS}
    separation = {}
    for family in ("pendulum","acrobot"):
        seeds = {}
        for bundle in (0,1):
            with np.load(SOURCE/family/f"bundle{bundle}_train.npz") as data:
                seeds[bundle] = set(np.asarray(data["env_seeds"]).reshape(-1).tolist())
        validate_source_separation(seeds)
        separation[family] = {"disjoint":True,"episode_counts":{str(k):len(v) for k,v in seeds.items()}}
    records,resources = collect_source_proxy(deadline)
    rows,folds = [],[]
    for family in ("pendulum","acrobot"):
        for held in (0,1):
            bank = [r for r in records if r["family"]==family and r["bundle"]!=held]
            queries = [r for r in records if r["family"]==family and r["bundle"]==held]
            norm = FamilyNormalizer.fit(family,load_source_train_obs(family,(1-held,)))
            block,fold = evaluate_fold(bank,queries,norm,family=family,held_bundle=held,deadline=deadline)
            fold["context_metrics"] = [{"offset":o,"metrics":summarize([r for r in block if r["offset"]==o])} for o in OFFSETS]
            rows.extend(block); folds.append(fold)
    # First average pairs within contexts, contexts within folds, then folds.
    summaries = {}
    for family in ("pendulum","acrobot","pooled"):
        cells = [summarize([r for r in rows if r["family"]==f and r["held_bundle"]==b and r["offset"]==o])
                 for f in ("pendulum","acrobot") if family=="pooled" or f==family for b in (0,1) for o in OFFSETS]
        summaries[family] = {m:{k:(float(np.mean([s[m][k] for s in cells]))
                                  if all(s[m][k] is not None for s in cells) else None)
                                for k in ("mae","sign_loss","abstention_rate")} for m in METHODS}
    checks = {}
    for family,s in summaries.items():
        candidate = s["candidate_context_ridge"]
        checks[family] = (candidate["mae"] <= 0.9*min(s[m]["mae"] for m in METHODS[:2])
                          and candidate["mae"] <= 0.95*s["context_config_ridge"]["mae"]
                          and candidate["sign_loss"] is not None
                          and all(s[m]["sign_loss"] is not None for m in METHODS[:2])
                          and candidate["sign_loss"] <= min(s[m]["sign_loss"] for m in METHODS[:2]))
    if not all(sha(ROOT/p)==h for p,h in old.items()): raise RuntimeError("historical_artifact_changed")
    payload = {"declared_complete":False,"scientific":False,"base_sha":BASE,
               "execution_sha":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
               "protocol_sha256":sha(PROTOCOL),"implementation_sha256":sha(Path(__file__)),
               "tracked_diff_before_results":subprocess.check_output(["git","diff","HEAD","--stat"],cwd=ROOT,text=True),
               "source_episode_separation":separation,
               "historical_artifacts_sha256":old,"historical_artifacts_preserved":True,
               "source_sha256":{str(p.relative_to(ROOT)):sha(p) for p in SOURCE.glob("*/bundle[01]_train.npz")},
               "source_receipts":[{"family":r["family"],"bundle":r["bundle"],"offset":r["offset"],
                                   "candidate_seed":r["public"].candidate_seed,"revealed":r["revealed"],
                                   "planning_obs":r["public"].observation.tolist(),
                                   "support_hash":digest({k:{"shape":list(a.shape),"dtype":str(a.dtype),"data":a.tolist()}
                                                          for k,a in vars(r["public"].support).items()}),
                                   "candidate_hashes":{v.fingerprint:candidate_descriptor(v,family_context(r["family"]),
                                                                                r["public"].candidate_seed)[1]
                                                       for v in VARIANTS}} for r in records],
               "rows":rows,"folds":folds,"summary":summaries,"screen_by_family":checks,
               "screen_pass":all(checks.values()),"cap_s":CAP_S,
               "resources":{**resources,"wall_s":time.perf_counter()-t0,"cpu_s":time.process_time()-cpu0,
                            "ridge_fits":8,"real_interactions":0,"neural_training":False},
               "scientific_ledger":{"used_s":327.869,"remaining_s":3272.131},
               "limitations":["Inspected source-only proxy data; not scientific confirmation.",
                              "Two default-physics source bundles per family, not independent physics replicates.",
                              "All methods fit only identical six-receipt labels per source context.",
                              "Oracle unit scaling inherited from E2.24; no new control evaluation.",
                              "No controller integration or promotion, even if descriptive screen passes."]}
    validate(payload); payload["declared_complete"] = True
    return payload


def write_artifact(path=RESULTS):
    path = Path(path)
    if path.exists(): raise FileExistsError("preserve_previous_e225_result")
    t0 = time.perf_counter()
    try:
        p = run(); encoded=json.dumps(p,indent=2,allow_nan=False)+"\n"
    except Exception as e:
        path.write_text(json.dumps({"declared_complete":False,"failure":f"{type(e).__name__}: {e}",
                                    "wall_s":time.perf_counter()-t0,"real_interactions":0})+"\n")
        raise
    path.write_text(encoded)
    return p
