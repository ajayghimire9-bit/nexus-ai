"""Skeleton-free hierarchical helper library learned from verified programs (v3 Piece A).

Nothing here is a hand-written control-flow template. Helpers come only from programs that
passed their verifying tests:
  1. verified solutions themselves (callable by later tasks: a solution that calls a helper
     becomes a higher-layer helper);
  2. auxiliary functions those solutions defined;
  3. anti-unified abstractions: alpha-normalised expression subtrees (loops/comprehensions,
     conditionals, accumulations, calls - whatever the verified code contains) that recur across
     >= 2 DISTINCT verified solutions, lifted to `def helper_k(v0, ...): return <expr>` and
     promoted only if every refactored solution still passes its verifying tests (re-executed and
     charged) and the total description length drops (verified compression gain, in AST nodes).
Layer: a helper whose body calls no library helper is layer 1; otherwise 1 + max(callee layer).
Retrieval is TF-IDF over the natural-language provenance of each helper (the task texts it was
verified on); IDF uses only the library's own texts and the query.
"""
from __future__ import annotations

import ast
import builtins
import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

STOP = set("""a an the of to in for and or is are be by with from that this which on as at it its into
write function python program given find check whether using list lists number numbers string strings
element elements value values return returns all each two three n k nth""".split())
BUILTIN_NAMES = set(dir(builtins))


def tokens(text):
    words = re.findall(r"[a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower().replace("_", " "))
    return [w for w in words if w not in STOP and len(w) > 1]


def node_size(node):
    return sum(1 for _ in ast.walk(node))


@dataclass
class Helper:
    name: str
    src: str
    params: tuple
    layer: int
    deps: tuple
    origin: str              # solution | aux | abstraction
    task_ids: tuple
    text: str
    digest: str
    uses: int = 0


def _digest(fn_node):
    clone = ast.parse(ast.unparse(fn_node)).body[0]
    clone.name = "_"
    return hashlib.sha256(ast.dump(clone).encode()).hexdigest()[:16]


class _Rename(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        if node.id in self.mapping:
            return ast.copy_location(ast.Name(self.mapping[node.id], node.ctx), node)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if node.name in self.mapping:
            node.name = self.mapping[node.name]
        return node


def called_names(node):
    return {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def referenced_names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# --------------------------------------------------------------------------- anti-unification
_FORBIDDEN_IN_ABSTRACTION = (ast.Yield, ast.YieldFrom, ast.Await, ast.NamedExpr, ast.Starred)


def _bound_inside(node):
    bound = set()
    for n in ast.walk(node):
        if isinstance(n, ast.comprehension):
            bound |= {x.id for x in ast.walk(n.target) if isinstance(x, ast.Name)}
        elif isinstance(n, ast.Lambda):
            bound |= {a.arg for a in n.args.args}
    return bound


def canonical(expr, global_names):
    """Alpha-normalise an expression; returns (key, free vars in source order, normalised src) or None."""
    if any(isinstance(n, _FORBIDDEN_IN_ABSTRACTION) for n in ast.walk(expr)):
        return None
    bound = _bound_inside(expr)
    order = []
    for n in sorted((n for n in ast.walk(expr) if isinstance(n, ast.Name) and n.id not in global_names),
                    key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))):
        if isinstance(n.ctx, ast.Store) and n.id not in bound:
            return None
        if n.id not in order:
            order.append(n.id)
    free = [v for v in order if v not in bound]
    names = {v: f"v{i}" for i, v in enumerate(free)}
    names.update({v: f"b{i}" for i, v in enumerate(x for x in order if x in bound)})
    norm = _Rename(names).visit(ast.parse(ast.unparse(expr), mode="eval").body)
    return ast.dump(norm, annotate_fields=False), free, ast.unparse(norm)


def imported_names(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out[(a.asname or a.name).split(".")[0]] = ast.unparse(n)
    return out


class HelperLibrary:
    def __init__(self, *, exemplar_floor=0.8, helper_floor=0.8, compose_floor=0.35, max_offer=3,
                 min_abstraction_size=8):
        # Prompt context only for near-duplicates (>= 0.8): on dev, lower-similarity exemplars from a
        # small library distracted the 1.5B model (5 dev tasks lost, 0 gained). Execution-validated
        # composition keeps the lower floor because a wrong reuse cannot pass without executing.
        self.helpers: dict[str, Helper] = {}
        self.solutions = []            # dict(task_id, func, name, tests, setup)
        self.exemplar_floor, self.helper_floor, self.compose_floor = exemplar_floor, helper_floor, compose_floor
        self.max_offer, self.min_size = max_offer, min_abstraction_size
        self.promotions, self.rejections = [], []
        self.n_abstractions = 0
        self.work = 0                  # library-maintenance work (retrieval scoring, re-verification)

    # ---------------------------------------------------------------- growth
    def add_solution(self, task, answer, *, verified_on, tests=None):
        tree = ast.parse(answer)
        defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        mapping, new_defs = {}, []
        for d in defs:
            h = self.helpers.get(d.name)
            if h is not None and h.digest == _digest(d):
                continue                       # a bundled library helper, already known
            if d.name in self.helpers or d.name in BUILTIN_NAMES:
                mapping[d.name] = f"{d.name}_t{task.task_id}"
            new_defs.append(d)
        if not new_defs:
            return []
        imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        consts = [ast.unparse(n) for n in tree.body if isinstance(n, ast.Assign)]
        added = []
        local = {mapping.get(d.name, d.name) for d in new_defs}
        for d in new_defs:
            d = _Rename(mapping).visit(ast.parse(ast.unparse(d)).body[0])
            deps = tuple(sorted((referenced_names(d) & (set(self.helpers) | local)) - {d.name}))
            body_src = "\n".join(imports + consts + [ast.unparse(d)])
            h = Helper(d.name, body_src, tuple(a.arg for a in d.args.args), 1, deps,
                       "solution" if d.name == mapping.get(task.func, task.func) else "aux",
                       (task.task_id,), task.text, _digest(d))
            self.helpers[d.name] = h
            added.append(h)
        self._relayer()
        main = mapping.get(task.func, task.func)
        self.solutions.append(dict(task_id=task.task_id, func=task.func, name=main,
                                   tests=list(tests if tests is not None else task.public), setup=task.setup,
                                   verified_on=verified_on))
        return added

    def _relayer(self):
        changed = True
        while changed:
            changed = False
            for h in self.helpers.values():
                layer = 1 + max((self.helpers[d].layer for d in h.deps if d in self.helpers), default=0)
                if layer != h.layer:
                    h.layer, changed = layer, True

    # ---------------------------------------------------------------- sources
    def closure(self, names):
        out, todo = [], list(names)
        seen = set()
        while todo:
            n = todo.pop()
            if n in seen or n not in self.helpers:
                continue
            seen.add(n)
            todo += list(self.helpers[n].deps)
        order, placed = [], set()
        def place(n):
            if n in placed:
                return
            placed.add(n)
            for d in self.helpers[n].deps:
                if d in seen:
                    place(d)
            order.append(n)
        for n in sorted(seen):
            place(n)
        return order

    def source_of(self, names):
        return "\n\n".join(self.helpers[n].src for n in self.closure(names))

    def bundle(self, code, helpers_src=""):
        """Self-contained answer: the library helpers the code (transitively) references + the code."""
        tree = ast.parse(code)
        own = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        needed = (referenced_names(tree) & set(self.helpers)) - own
        if not needed:
            return code
        for n in needed:
            self.helpers[n].uses += 1
        return self.source_of(sorted(needed)) + "\n\n" + code

    def layer_of(self, answer, func=None):
        tree = ast.parse(answer)
        lib = {n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in self.helpers
               and self.helpers[n.name].digest == _digest(n)}
        return 1 + max((self.helpers[n].layer for n in lib), default=0)

    def max_helper_layer_in(self, answer):
        tree = ast.parse(answer)
        lib = [self.helpers[n.name].layer for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name in self.helpers and self.helpers[n.name].digest == _digest(n)]
        return max(lib, default=0)

    # ---------------------------------------------------------------- retrieval
    def _idf(self, query_tokens):
        docs = [set(tokens(h.text + " " + h.name)) for h in self.helpers.values()] + [set(query_tokens)]
        df = Counter(t for d in docs for t in d)
        return {t: math.log((1 + len(docs)) / (1 + c)) + 1 for t, c in df.items()}

    def retrieve(self, task, meter):
        q = tokens(task.text)
        if not self.helpers or not q:
            return []
        memo_key = (task.task_id, len(self.helpers), self.n_abstractions)
        if getattr(self, "_memo", (None,))[0] == memo_key:
            return self._memo[1]
        meter.charge(len(self.helpers))
        idf = self._idf(q)
        def vec(ts):
            c = Counter(ts)
            return {t: c[t] * idf.get(t, 1.0) for t in c}
        qv = vec(q)
        qn = math.sqrt(sum(v * v for v in qv.values()))
        out = []
        for h in self.helpers.values():
            hv = vec(tokens(h.text + " " + h.name))
            hn = math.sqrt(sum(v * v for v in hv.values())) or 1.0
            sim = sum(qv[t] * hv.get(t, 0.0) for t in qv) / (qn * hn)
            out.append((sim, h))
        out.sort(key=lambda x: (-x[0], x[1].name))
        self._memo = (memo_key, out)
        return out

    def context(self, task, meter):
        """Prompt context (one verified exemplar + callable helper signatures) and their sources."""
        ranked = [(s, h) for s, h in self.retrieve(task, meter) if h.name != task.func]
        parts, offer = [], []
        exemplar = next(((s, h) for s, h in ranked if h.origin == "solution" and s >= self.exemplar_floor), None)
        if exemplar:
            h = exemplar[1]
            parts.append(f"A verified solution to a similar task (\"{h.text.strip()}\"):\n```python\n"
                         f"{self.source_of([h.name])}\n```")
            offer.append(h.name)
        for s, h in ranked:
            if len(offer) >= self.max_offer or s < self.helper_floor:
                break
            if h.name not in offer:
                offer.append(h.name)
        if not offer:
            return "", "", []
        sigs = ", ".join(f"{n}({', '.join(self.helpers[n].params)})" for n in offer)
        parts.append(f"These verified helper functions are already defined and may be called directly: {sigs}.")
        return "\n".join(parts) + "\n\n", self.source_of(offer), offer

    # ---------------------------------------------------------------- symbolic composition (no LLM)
    def compose(self, task, meter, *, top=3):
        """Execution-based search over library helpers: f = h(args) and f = g(h(x)) for unary helpers."""
        from nexus.wave24_mbpp import passes
        arity = len(task.public[0].args) if task.public[0].args else None
        if arity is None:
            return None
        ranked = [(s, h) for s, h in self.retrieve(task, meter)
                  if s >= self.compose_floor and h.name != task.func and h.origin != "abstraction"]
        params = ", ".join(f"a{i}" for i in range(arity))
        cands = [f"def {task.func}({params}):\n    return {h.name}({params})"
                 for _, h in ranked[:top] if len(h.params) == arity]
        if arity == 1:
            unary = [h for _, h in ranked[:top] if len(h.params) == 1]
            cands += [f"def {task.func}(a0):\n    return {g.name}({h.name}(a0))" for h in unary for g in unary
                      if g.name != h.name]
        for code in cands:
            helpers = sorted(called_names(ast.parse(code)) & set(self.helpers))
            src = self.source_of(helpers)
            meter.charge(1)
            ok, _ = passes(code, task.public, meter, setup=task.setup, helpers_src=src)
            if ok:
                return self.bundle(code)
        return None

    # ---------------------------------------------------------------- sleep: anti-unification
    def _globals(self):
        mods = {"re", "math", "cmath", "collections", "heapq", "itertools", "operator", "array", "bisect", "copy",
                "datetime", "functools", "string", "statistics", "fractions", "decimal", "sys", "random"}
        return BUILTIN_NAMES | mods | set(self.helpers)

    def _sources_for_abstraction(self):
        return [h for h in self.helpers.values() if h.origin in ("solution", "aux")]

    def _glob_for(self, tree):
        return self._globals() | set(imported_names(tree))

    def candidates(self):
        occ = defaultdict(list)        # key -> [(helper name, expr src, free vars, canonical src, size)]
        for h in self._sources_for_abstraction():
            tree = ast.parse(h.src)
            glob = self._glob_for(tree)
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == h.name)
            for node in ast.walk(fn):
                if not isinstance(node, ast.expr) or isinstance(node, (ast.Name, ast.Constant)):
                    continue
                if node_size(node) < self.min_size:
                    continue
                c = canonical(node, glob)
                if c is None or not c[1]:
                    continue
                key, free, norm_src = c
                occ[key].append((h.name, ast.unparse(node), tuple(free), norm_src, node_size(node)))
        out = []
        for key, items in occ.items():
            tasks = {t for name, *_ in items for t in self.helpers[name].task_ids}
            if len(tasks) >= 2:
                out.append((len(tasks) * items[0][4], key, items))
        out.sort(key=lambda x: (-x[0], x[1]))
        kept = []                      # keep maximal subtrees only
        for score, key, items in out:
            if any(all(any(it[0] == big[0] and it[1] in big[1] for big in k[2]) for it in items) for k in kept):
                continue
            kept.append((score, key, items))
        return kept

    def _refactor(self, hname, key, name):
        h = self.helpers[hname]
        tree = ast.parse(h.src)
        glob = self._glob_for(tree)

        class Sub(ast.NodeTransformer):
            def visit(self, node):
                if isinstance(node, ast.expr) and not isinstance(node, (ast.Name, ast.Constant)):
                    c = canonical(node, glob)
                    if c is not None and c[0] == key:
                        return ast.Call(ast.Name(name, ast.Load()), [ast.Name(v, ast.Load()) for v in c[1]], [])
                return super().visit(node)
        before = node_size(tree)
        new = ast.fix_missing_locations(Sub().visit(tree))
        return ast.unparse(new), before - node_size(new)

    def _verify_all(self, meter, touched):
        """Re-run every stored solution whose program uses a touched helper (charged)."""
        from nexus.wave24_mbpp import passes
        for sol in self.solutions:
            if sol["name"] not in self.helpers or not (set(self.closure([sol["name"]])) & touched):
                continue
            ok, _ = passes(self.source_of([sol["name"]]), sol["tests"], meter, setup=sol["setup"])
            if not ok:
                return False
        return True

    def sleep(self, meter, *, max_new=4, budget=None):
        """One sleep round: propose abstractions, refactor, re-verify every affected solution, promote."""
        start = meter.total
        promoted = []
        for score, key, items in self.candidates()[: max_new * 3]:
            if len(promoted) >= max_new or (budget is not None and meter.total - start >= budget):
                break
            name = f"helper_{self.n_abstractions + 1}"
            params = tuple(f"v{i}" for i in range(len(items[0][2])))
            src_tree = ast.parse(self.helpers[items[0][0]].src)
            imports = imported_names(src_tree)
            body = items[0][3]
            body_refs = referenced_names(ast.parse(body))
            header = sorted({imports[n] for n in body_refs if n in imports})
            helper_src = "\n".join(header + [f"def {name}({', '.join(params)}):\n    return {body}"])
            deps = tuple(sorted(body_refs & set(self.helpers)))
            refactored, gain = {}, 0
            for hname in sorted({it[0] for it in items}):
                new_src, saved = self._refactor(hname, key, name)
                refactored[hname] = new_src
                gain += saved
            gain -= node_size(ast.parse(helper_src))
            if gain <= 0:
                self.rejections.append(dict(helper=name, reason="no compression", gain=gain))
                continue
            backup = {n: (self.helpers[n].src, self.helpers[n].deps, self.helpers[n].digest) for n in refactored}
            self.helpers[name] = Helper(name, helper_src, params, 1, deps, "abstraction",
                                        tuple(sorted({t for it in items for t in self.helpers[it[0]].task_ids})),
                                        " ".join(dict.fromkeys(self.helpers[it[0]].text for it in items)),
                                        _digest(next(n for n in ast.parse(helper_src).body
                                                     if isinstance(n, ast.FunctionDef))))
            for hname, new_src in refactored.items():
                h = self.helpers[hname]
                h.src, h.deps = new_src, tuple(sorted(set(h.deps) | {name}))
                h.digest = _digest(next(n for n in ast.parse(new_src).body
                                        if isinstance(n, ast.FunctionDef) and n.name == hname))
            self._relayer()
            if not self._verify_all(meter, set(refactored)):
                for n, (src, deps_, dig) in backup.items():
                    self.helpers[n].src, self.helpers[n].deps, self.helpers[n].digest = src, deps_, dig
                del self.helpers[name]
                self._relayer()
                self.rejections.append(dict(helper=name, reason="refactor failed re-verification", gain=gain))
                continue
            self.n_abstractions += 1
            h_new = self.helpers[name]
            rec = dict(helper=name, src=helper_src, layer=h_new.layer, gain=gain, occurrences=len(items),
                       tasks=list(h_new.task_ids), refactored=sorted(refactored))
            self.promotions.append(rec)
            promoted.append(rec)
        self.work += meter.total - start
        return promoted

    # ---------------------------------------------------------------- reporting
    def summary(self):
        layers = Counter(h.layer for h in self.helpers.values())
        return dict(helpers=len(self.helpers), by_origin=dict(Counter(h.origin for h in self.helpers.values())),
                    by_layer={str(k): v for k, v in sorted(layers.items())}, abstractions=self.n_abstractions,
                    max_layer=max(layers, default=0), promotions=self.promotions, rejections=len(self.rejections))

    def to_json(self):
        return dict(helpers=[dict(name=h.name, src=h.src, params=list(h.params), layer=h.layer, deps=list(h.deps),
                                  origin=h.origin, task_ids=list(h.task_ids), text=h.text, digest=h.digest)
                             for h in self.helpers.values()],
                    solutions=[dict(task_id=s["task_id"], func=s["func"], name=s["name"],
                                    tests=[t.source for t in s["tests"]], setup=s["setup"],
                                    verified_on=s["verified_on"]) for s in self.solutions],
                    promotions=self.promotions, n_abstractions=self.n_abstractions)

    @classmethod
    def from_json(cls, data, **kw):
        from nexus.wave24_mbpp import parse_test
        lib = cls(**kw)
        for h in data["helpers"]:
            lib.helpers[h["name"]] = Helper(h["name"], h["src"], tuple(h["params"]), h["layer"], tuple(h["deps"]),
                                            h["origin"], tuple(h["task_ids"]), h["text"], h["digest"])
        lib.solutions = [dict(task_id=s["task_id"], func=s["func"], name=s["name"],
                              tests=[parse_test(t) for t in s["tests"]], setup=s["setup"],
                              verified_on=s["verified_on"]) for s in data["solutions"]]
        lib.promotions = list(data.get("promotions", []))
        lib.n_abstractions = data.get("n_abstractions", 0)
        return lib
