"""Compositional semantic specification parsing, messy-data specs, and scientific law discovery.

1. SemanticSpecParser: a compositional clause grammar (not keyword overlap)
   mapping natural-language requirements to (a) an ordered list of stage
   options over the generic skeleton vocabulary, (b) edge-case pre/post
   conditions ("if the list is empty return 0") that become extra test
   oracles, and (c) output-type constraints. Candidates are verified on the
   examples AND the extracted oracles before an answer is locked.
2. Wild spec tasks: hand-written requirements over messy records/series with
   reference implementations used only for hidden grading.
3. Law discovery: symbolic regression over physical-law forms with fitted
   constants and MDL model selection on noisy public points; graded on hidden
   points.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from itertools import product

from nexus.wave24_domains import vkey
from nexus.wave24_skeletons import SkeletonSpec, instantiate


# --------------------------------------------------------------------------- semantic parser
# Each clause pattern: regex -> list of stage options (skeleton specs or special ops).
CLAUSES = [
    (r"\b(ignor\w*|skip\w*|drop\w*|discard\w*|exclud\w*|remov\w*|without|omit\w*|leav\w* out)\b[^.;]*?\b(missing|none|null|blank|absent)\b", ["FILTER(is_none;drop)"]),
    (r"\b(ignor\w*|skip\w*|drop\w*|discard\w*|exclud\w*|remov\w*|omit\w*|leav\w* out)\b[^.;]*?\b(nan|non[- ]?finite|invalid|corrupt\w*|bad)\b", ["KEEP_FINITE"]),
    (r"\b(ignor\w*|skip\w*|drop\w*|discard\w*|exclud\w*|remov\w*|omit\w*|leav\w* out)\b[^.;]*?\bnegative\b|\bnon[- ]negative\b", ["KEEP_NONNEG"]),
    (r"\babsolute\b|\bmagnitudes?\b", ["MAP(abs)"]),
    (r"\b(double|twice|times two)\b", ["MAP(double)"]),
    (r"\b(halve|half)\b", ["MAP(half)"]),
    (r"\bsquare(d|s)?\b(?! root)", ["MAP(square)"]),
    (r"\b(negate|flip the sign)\b", ["MAP(neg)"]),
    (r"\b(add one|increment|plus one)\b", ["MAP(inc)"]),
    (r"\b(sum\w*|total\w*|add (them|up|together)|added (up|together))\b", ["FOLD(sum)"]),
    (r"\b(largest|biggest|greatest|maximum|max|highest|peak)\b", ["FOLD(max)"]),
    (r"\b(smallest|minimum|min|lowest)\b", ["FOLD(min)"]),
    (r"\b(how many|count\w*|number of)\b", ["FOLD(count)"]),
    (r"\b(average|mean)\b", ["FOLD(mean)"]),
    (r"\b(product|multiply (them|all) together)\b", ["FOLD(prod)"]),
    (r"\bround(ed)? to (\d+|one|two|zero) decimals?\b", ["ROUND"]),
]
NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3}
EDGE = re.compile(r"\b(if|when)\b[^.;]*\b(empty|no (valid )?(values|items|readings))\b[^.;]*\breturn\s+(?P<val>-?\d+(\.\d+)?|none|zero)",
                  re.IGNORECASE)


@dataclass
class ParsedSpec:
    stages: list                 # list of lists of stage options, in order of mention
    edge_cases: list = field(default_factory=list)   # (input, expected) oracles
    rounding: int = None


class SemanticSpecParser:
    """Clause-level compositional parse: order = position of each clause in the text."""

    def parse(self, text):
        low = text.lower()
        hits = []
        for pattern, options in CLAUSES:
            for m in re.finditer(pattern, low):
                hits.append((m.start(), options, m))
        hits.sort(key=lambda h: h[0])
        stages, used_span, rounding = [], [], None
        for start, options, m in hits:
            if any(a <= start < b for a, b in used_span):
                continue
            used_span.append((m.start(), m.end()))
            if options == ["ROUND"]:
                tok = m.group(2)
                rounding = NUMBER_WORDS.get(tok, int(tok) if tok.isdigit() else 2)
                continue
            stages.append(options)
        # aggregation clauses are mentioned before filters in English ("the total of non-negative values"):
        # canonical dataflow order = cleaning/selection, then element maps, then one aggregation.
        def rank(opts):
            o = opts[0]
            return 0 if o.startswith(("FILTER", "KEEP")) else 1 if o.startswith("MAP") else 2
        stages.sort(key=rank)
        dedup = []
        for st in stages:                 # the same operation mentioned twice is one stage
            if st not in dedup:
                dedup.append(st)
        if sum(1 for st in dedup if st[0].startswith("FOLD")) > 1:
            folds = [st for st in dedup if st[0].startswith("FOLD")]
            dedup = [st for st in dedup if not st[0].startswith("FOLD")] + [sorted({o for f in folds for o in f})]
        stages = dedup
        edges = []
        m = EDGE.search(text)
        if m:
            val = m.group("val").lower()
            expected = None if val == "none" else 0 if val == "zero" else (float(val) if "." in val else int(val))
            edges.append(([], expected))
        return ParsedSpec(stages, edges, rounding)


def special(name):
    if name == "KEEP_FINITE":
        return lambda xs: [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)]
    if name == "KEEP_NONNEG":
        return lambda xs: [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0]
    raise KeyError(name)


def stage_fn(option):
    if option in ("KEEP_FINITE", "KEEP_NONNEG"):
        return special(option)
    t, rest = option.split("(", 1)
    body = rest.rstrip(")")
    slot, _, param = body.partition(";")
    return instantiate(SkeletonSpec(t, (slot,), (param,) if param else ())).fn


def compile_candidate(options, spec):
    fns = [stage_fn(o) for o in options]
    edges = list(spec.edge_cases)
    def run(x):
        for (ex, ey) in edges:
            if vkey(x) == vkey(ex):
                return ey        # extracted pre/post-condition handled explicitly (guard branch)
        v = x
        for f in fns:
            v = f(v)
        if spec.rounding is not None and isinstance(v, float):
            v = round(v, spec.rounding)
        return v
    return run


def solve_spec(task, *, meter_limit=20_000):
    """Parse -> enumerate stage-option products -> verify on examples + edge oracles. Work = evaluations."""
    parsed = SemanticSpecParser().parse(task.text)
    work, fits = len(task.text.split()), []
    for options in product(*parsed.stages) if parsed.stages else [()]:
        fn = compile_candidate(options, parsed)
        ok = True
        for x, y in list(task.examples) + parsed.edge_cases:
            work += max(1, len(options))
            try:
                if vkey(fn(x)) != vkey(y):
                    ok = False
                    break
            except Exception:
                ok = False
                break
        if ok:
            fits.append((options, fn))
        if work > meter_limit:
            break
    if not fits:
        return dict(status="NO_PROGRAM_IN_PARSED_SPACE", work=work, parsed=[list(s) for s in parsed.stages])
    answers = set()
    for _, fn in fits:
        try:
            answers.add(tuple(vkey(fn(x)) for x in task.hidden_inputs))
        except Exception:
            answers.add(("raise",))
    fn = fits[0][1]
    correct = len(answers) == 1 and all(_ok(fn, x, y) for x, y in task.hidden)
    return dict(status="UNIQUE_IN_PARSED_SPACE" if len(answers) == 1 else "AMBIGUOUS_WITNESS_FOUND", work=work,
                correct=correct, witness=list(fits[0][0]), edge_cases=len(parsed.edge_cases))


def _ok(fn, x, y):
    try:
        return vkey(fn(x)) == vkey(y)
    except Exception:
        return False


# --------------------------------------------------------------------------- wild spec tasks
@dataclass
class SpecTask:
    name: str
    text: str
    examples: tuple
    hidden: tuple
    reference: object = field(repr=False, default=None)

    @property
    def hidden_inputs(self):
        return [x for x, _ in self.hidden]


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


SPEC_LIBRARY = [
    ("total_valid", ["Compute the total of the readings, ignoring any missing values.",
                     "Add up all the measurements but skip the null entries.",
                     "Sum the values; drop blank values first."],
     lambda xs: sum(x for x in xs if x is not None)),
    ("max_magnitude", ["Return the largest absolute value in the series.",
                       "What is the maximum magnitude among the samples?"],
     lambda xs: max(abs(x) for x in xs)),
    ("mean_nonneg_rounded", ["Report the average of the readings, excluding negative ones, rounded to two decimals.",
                             "Mean of the non-negative values (remove negative readings), rounded to 2 decimals."],
     lambda xs: round(sum(x for x in xs if x >= 0) / len([x for x in xs if x >= 0]), 2)),
    ("count_finite_empty0", ["Count how many valid readings there are, discarding NaN values. If the list is empty return 0.",
                             "Number of finite samples after removing invalid entries; when empty, return 0."],
     lambda xs: len([x for x in xs if _finite(x)]) if xs else 0),
    ("energy", ["Square each sample and add them up to get the total energy.",
                "Sum of squared values."],
     lambda xs: sum(x * x for x in xs)),
    ("peak_clean", ["Ignore corrupt NaN readings, then report the peak value.",
                    "Drop the invalid samples and return the maximum."],
     lambda xs: max(x for x in xs if _finite(x))),
    ("double_total_empty0", ["Double every value and give the total. If the input is empty return 0.",
                             "Twice each element, summed; when empty, return 0."],
     lambda xs: sum(2 * x for x in xs) if xs else 0),
    ("min_nonneg", ["Find the smallest reading, skipping negative values.",
                    "Lowest non-negative measurement (exclude negative readings)."],
     lambda xs: min(x for x in xs if x >= 0)),
]


def spec_tasks(seed, *, per_spec=1, paraphrased=False):
    rng = random.Random(f"spec:{seed}")
    out = []
    for name, texts, ref in SPEC_LIBRARY:
        for k in range(per_spec):
            text = rng.choice(texts)
            def sample():
                n = rng.randint(3, 7)
                xs = [float(rng.randint(-9, 9)) for _ in range(n)]
                if "valid" in name or "clean" in name or "finite" in name:
                    xs[rng.randrange(n)] = None if "total" in name else float("nan")
                return xs
            pairs = []
            for _ in range(40):
                x = sample()
                try:
                    pairs.append((x, ref(x)))
                except Exception:
                    continue
                if len(pairs) == 7:
                    break
            hidden = pairs[3:]
            if "empty" in text.lower():
                hidden = hidden + [([], ref([]))]
            if paraphrased:
                text = paraphrase(text, rng)
            out.append(SpecTask(f"{name}#{k}", text, tuple(pairs[:3]), tuple(hidden), ref))
    return out


SYNONYMS = {
    "readings": ["measurements", "samples", "values", "data points"],
    "ignoring": ["skipping", "excluding", "leaving out"], "ignore": ["skip", "exclude", "omit"],
    "largest": ["biggest", "highest", "maximum"], "smallest": ["lowest", "minimum"],
    "total": ["sum", "overall total"], "average": ["mean"], "report": ["return", "give"],
    "compute": ["calculate", "work out"], "find": ["determine", "get"], "missing": ["absent", "null"],
}


def paraphrase(text, rng):
    """Seeded synonym substitution (held-out wording at evaluation time)."""
    words = text.split(" ")
    out = []
    for w in words:
        core = w.strip(".,;").lower()
        if core in SYNONYMS and rng.random() < 0.7:
            rep_ = rng.choice(SYNONYMS[core])
            w = w.lower().replace(core, rep_)
        out.append(w)
    return " ".join(out)


def keyword_baseline(task, *, budget=20_000):
    """Previous approach: docstring keyword retrieval over the same stage vocabulary + blind search."""
    from nexus.wave24_agi_suite import DocstringRetriever
    from nexus.wave24_domains import Tool
    vocab = sorted({o for _, opts in CLAUSES for o in opts if o != "ROUND"})
    tools = [Tool(o.replace("(", "_").replace(")", "").replace(";", "_"), stage_fn(o), o.lower()) for o in vocab]
    ranked = DocstringRetriever(tools).rank(task.text, k=4)
    names = {t.name: t for t in tools}
    work, fits = 0, []
    for depth in (1, 2, 3):
        for chain in product(ranked, repeat=depth):
            ok = True
            for x, y in task.examples:
                work += depth
                try:
                    v = x
                    for n in chain:
                        v = names[n](v)
                    if vkey(v) != vkey(y):
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
            if ok:
                fits.append(chain)
            if work > budget:
                break
        if fits:
            break
    if not fits:
        return dict(status="NO_PROGRAM", work=work, correct=False)
    chain = fits[0]
    def fn(x):
        v = x
        for n in chain:
            v = names[n](v)
        return v
    return dict(status="FOUND", work=work, correct=all(_ok(fn, x, y) for x, y in task.hidden))


# --------------------------------------------------------------------------- scientific law discovery
LAWS = [
    ("kepler_third_law", lambda a: 1.0 * a ** 1.5, (0.4, 30.0)),
    ("free_fall_distance", lambda t: 4.905 * t ** 2, (0.2, 5.0)),
    ("ohm_law", lambda i: 220.0 * i, (0.01, 2.0)),
    ("radioactive_decay", lambda t: 100.0 * math.exp(-0.3 * t), (0.0, 12.0)),
    ("pendulum_period", lambda L: 2.006 * L ** 0.5, (0.1, 3.0)),
    ("inverse_square", lambda r: 50.0 / r ** 2, (0.5, 10.0)),
    ("boyle_law", lambda v: 8.0 / v, (0.5, 8.0)),
]


def _lstsq(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-12
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def fit_forms(xs, ys, meter):
    """Candidate law forms with fitted constants; returns list of (form, params, predictor, mse)."""
    forms = []
    pos = all(x > 0 for x in xs) and all(y > 0 for y in ys)
    meter[0] += 2 * len(xs)
    a, b = _lstsq(xs, ys)
    forms.append(("linear", (a, b), lambda x, a=a, b=b: a + b * x))
    if pos:
        meter[0] += 2 * len(xs)
        la, k = _lstsq([math.log(x) for x in xs], [math.log(y) for y in ys])
        forms.append(("power", (math.exp(la), k), lambda x, c=math.exp(la), k=k: c * x ** k))
        meter[0] += 2 * len(xs)
        la2, r = _lstsq(xs, [math.log(y) for y in ys])
        forms.append(("exponential", (math.exp(la2), r), lambda x, c=math.exp(la2), r=r: c * math.exp(r * x)))
        meter[0] += 2 * len(xs)
        a3, b3 = _lstsq([math.log(x) for x in xs], ys)
        forms.append(("logarithmic", (a3, b3), lambda x, a=a3, b=b3: a + b * math.log(x)))
    out = []
    for name, params, f in forms:
        meter[0] += len(xs)
        mse = sum((f(x) - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
        out.append((name, params, f, mse))
    return out


def law_tasks(seed, *, n_public=8, n_hidden=6, noise=0.02):
    rng = random.Random(f"laws:{seed}")
    tasks = []
    for name, law, (lo, hi) in LAWS:
        xs = sorted(rng.uniform(lo, hi) for _ in range(n_public + n_hidden))
        pub = [x for i, x in enumerate(xs) if i % 7 not in (3, 6)][:n_public]
        hid = [x for x in xs if x not in pub][:n_hidden]
        noisy = [(x, law(x) * (1 + rng.gauss(0, noise))) for x in pub]
        tasks.append(dict(name=name, public=noisy, hidden=[(x, law(x)) for x in hid]))
    return tasks


def discover_law(task, *, select="mdl"):
    meter = [0]
    xs, ys = [x for x, _ in task["public"]], [y for _, y in task["public"]]
    forms = fit_forms(xs, ys, meter) if select == "mdl" else fit_forms(xs, ys, meter)[:1]
    n = len(xs)
    def score(f):
        rel = sum(((f[2](x) - y) / (abs(y) + 1e-9)) ** 2 for x, y in zip(xs, ys)) / n
        return n * math.log(rel + 1e-12) + 2 * len(f[1]) * math.log(n)   # MDL / BIC in relative error
    best = min(forms, key=score)
    rel_err = max(abs(best[2](x) - y) / abs(y) for x, y in task["hidden"])
    return dict(form=best[0], params=[round(p, 4) for p in best[1]], work=meter[0], hidden_max_rel_error=rel_err,
                correct=rel_err < 0.05)
