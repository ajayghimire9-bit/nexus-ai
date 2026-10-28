"""Shared helpers for the u5 pillar experiments (NOT LOCKED): predeclared task suites, artifact I/O, node serialisation."""
import ast, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import u5_seeds  # noqa: E402,F401
from nexus import u5_construct as K, u5_world as W  # noqa: E402
from nexus import seed_registry as R  # noqa: E402

ART = ROOT / "artifacts/u5_dev"
LC = [f for f in W.FAMILIES if f[0] in "LC"]
IOT = [f for f in W.FAMILIES if f[0] == "I"]
ALL = list(W.FAMILIES)
TASK_S = 4.0                                  # per-task search budget (CPU s) in every Pillar 2-4 evaluation


def seeds(kind, idx):
    rng = list(R.REGISTRY[("u5", kind)])
    return [rng[i] for i in idx]


def suite(fams, kind, idx):
    return [W.Task(f"{f}#{s}", f, s) for f in fams for s in seeds(kind, idx)]


SRC_TRAIN = lambda: suite(LC, "tsrc", range(0, 5))      # noqa: E731  learning material (L + C only: IoT is unseen)
ADM = lambda: suite(LC, "tadm", range(0, 2))            # noqa: E731  library admission validation
DEV = lambda: suite(ALL, "tdev", range(0, 2))           # noqa: E731  pillar selection
HELD = lambda: suite(ALL, "theld", range(0, 2))         # noqa: E731  held-out report (never selects)


def node_dump(n):
    return repr(n)


def node_load(s):
    return ast.literal_eval(s)


def save(name, obj):
    (ART / name).write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))


def load(name):
    return json.loads((ART / name).read_text())


def learner_cfg(policy, P=None):
    cfg = K.default_config(policy)
    if policy != "baseline" and P:
        cfg["op_cost"] = P["op_cost"]
        if policy == "exec":
            cfg["weights"], cfg["bias"] = P["weights"], P["bias"]
    return cfg


def eval_suite(tasks, cfg, lib, engine="hybrid", budget=TASK_S):
    rows, t0 = [], time.process_time()
    for t in tasks:
        fn = K.solve_hybrid if engine == "hybrid" else K.solve
        node, st, _ = fn(t.train, t.y_train, cfg, lib, budget)
        g = W.correct_on(t, node) if node is not None else 0.0
        rows.append(dict(task=t.tid, family=t.family, solved=st["solved"], generalises=g == 1.0, gen=round(g, 4),
                         cpu_s=st["cpu_s"], size=st["size"], stage=st.get("stage")))
    return dict(rows=rows, n=len(rows), solved_train=sum(r["solved"] for r in rows), correct=sum(r["generalises"] for r in rows),
                wrong_generalisation=sum(r["solved"] and not r["generalises"] for r in rows),
                cpu_s=round(sum(r["cpu_s"] for r in rows), 3), wall_cpu_s=round(time.process_time() - t0, 3))
