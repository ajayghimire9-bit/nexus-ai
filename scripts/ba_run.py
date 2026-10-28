"""ba confirmation runner (NOT LOCKED): ONE (project, arm) per call - per-project checkpointing; every call is far below the
900 s cap because each arm runs under an in-process alarm (ARM_ALARM_S) that records TIMED_OUT instead of being killed.
  python scripts/ba_run.py val|val_b|test INDEX ARM          ARM: NEXUS_Confirmed | NEXUS_U5 | Fixed_Policy | Conventional
Paired arms on identical projects (the same generator / sealed blob, the same crash schedule and spot-check seeds).
Seeds: the one-use ba range is claimed whole by the first call of the split; each (project, arm) runs once (no rerun:
an existing result file or ledger row refuses). A crash is that arm's outcome (CRASHED, not correct) and evaluation of the
other projects continues. test: only with NEXUS_SEALED_HARNESS_TOKEN after a passed gate; reads only vault blobs whose
sha256 match artifacts/ba_test_vault/MANIFEST.json. Writes artifacts/ba_<split>/p<INDEX>_<ARM>.json."""
import hashlib, json, os, signal, sys, traceback
from pathlib import Path
sys.path.insert(0, "scripts")
from u5_run import learners
from nexus import ba_seeds, ba_platform as BP, seed_registry as R  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("NEXUS_Confirmed", "NEXUS_U5", "Fixed_Policy", "Conventional")
ARM_ALARM_S = 780


class ArmTimeout(Exception):
    pass


def _alarm(*_):
    raise ArmTimeout


def growth_policy(fr):
    if fr.get("growth_rule") in (None, "none"):
        return None
    from nexus import oc_learner as OL
    sys.path.insert(0, str(ROOT / "scripts"))
    import ba_eps
    return {"Learned_Growth_Rule": lambda: ba_eps.policy("learned"), "Hand_Designed_Growth_Rule": lambda: OL.hand_policy,
            "Shuffled_Growth_Rule": lambda: ba_eps.policy("shuffled"), "Random_Growth_Rule": lambda: OL.random_policy}[fr["growth_rule"]]()


def main():
    split, idx, arm_name = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    assert arm_name in ARMS
    fr = json.loads((ROOT / "artifacts/ba_freeze.json").read_text())
    if split == "val_b" and not fr.get("revision"):
        raise SystemExit("val_b only after one disclosed revision")
    if split == "test":
        gate = ROOT / ("artifacts/ba_val_b/gate.json" if fr.get("revision") else "artifacts/ba_val/gate.json")
        if not json.loads(gate.read_text())["passed"]:
            raise SystemExit("validation gate not passed: the sealed test stays closed")
    out = ROOT / f"artifacts/ba_{split}" / f"p{idx}_{arm_name}.json"
    if out.exists():
        raise SystemExit("this (project, arm) already ran: no rerun")
    seeds = list(R.REGISTRY[("ba", split)])
    if not any(tuple(r["key"]) == ("ba", split) for r in R._spent() if "override" not in r):
        R.claim("ba", split, seeds, run_id=f"ba-{split}")
    s = seeds[idx]
    if split == "test":
        if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
            raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
        man = json.loads((ROOT / "artifacts/ba_test_vault/MANIFEST.json").read_text())
        rel = f"ba_test/{idx}.json"
        blob = (Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != man["files"][rel]:
            raise SystemExit("vault blob does not match the manifest")
        P = BP.PL.Project.from_json(blob.decode())
    else:
        P = BP.Project(s, split)
    nx, _ = learners()
    L = nx["NEXUS_U5"][0]
    if arm_name == "NEXUS_Confirmed":
        arm = BP.NexusArmBounded(arm_name, L)
        arm.growth = growth_policy(fr)
    elif arm_name == "NEXUS_U5":
        arm = BP.NexusArm(arm_name, L)
    elif arm_name == "Fixed_Policy":
        arm = BP.FixedArm(arm_name)
    else:
        arm = BP.FixedArm(arm_name, monitored=False, handle_units=False)
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(ARM_ALARM_S)
    try:
        r = BP.run_project(P, arm)
        status = "COMPLETE"
    except ArmTimeout:
        r = dict(arm=arm_name, project=s, domain=P.domain, fault=P.fault, outcome="TIMED_OUT", completed=False, data_ok=False,
                 silent=False, human_repairs=0, independently_correct=False)
        status = "COMPLETE"
    except Exception as e:                                           # noqa: BLE001
        r = dict(arm=arm_name, project=s, domain=P.domain, fault=P.fault, outcome="CRASHED", completed=False, data_ok=False,
                 silent=False, human_repairs=0, independently_correct=False,
                 error=type(e).__name__ if split == "test" else traceback.format_exc())
        status = "CRASHED"
    finally:
        signal.alarm(0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(split=split, index=idx, seed=s, arm=arm_name, status=status, result=r), indent=1, default=str))
    print(s, r["domain"], r["fault"], arm_name, "OK" if r["data_ok"] else "BAD", "indep" if r["independently_correct"] else "-",
          "silent" if r["silent"] else "", "human", r["human_repairs"], r["outcome"], flush=True)


if __name__ == "__main__":
    main()
