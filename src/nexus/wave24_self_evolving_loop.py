"""AZR preparation: procedural worlds, metered source self-play and certificates.

Imports no world models, simulator, LLM runtime or historical assessment bank.
Reuses ridge, E1 Journal and canonical digest; typed AST skills are journal views,
not a duplicate agent/memory framework. No scientific benchmark runs on import.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import product, combinations, islice
import json
import math
import random
import time
import zlib
from typing import Any

from nexus.evolution1.catalogue import digest
from nexus.evolution1.fixtures import Journal
from nexus.nn.ridge import fit_ridge, predict_ridge
from nexus.wave24_quotient_core import (
    Expr, Grammar, Operator, WorkMeter, WorkExhausted, ExactEnumerator,
    GoalCheck, SearchResult, apply, constant, eval_expr, freeze, unfreeze, primitive_cost,
    eval_expr_steps, solve, variable,
    validate_program, verify_certificate,
    ParametricSkillMacro, typed_hole, skill_wire, skill_from_wire,
    expanded_skill_call,
    expression_wire,
    PopperianTwinVerifier,
    ExhaustiveASTEnumerator, unfold_workspace_expr, expression_from_wire,
    NoetherConservationGate, atomic_signature, structural_mass, locus_mask,
)
from nexus.wave24_auto_laws import (AutoOperatorFingerprinter, structural_measure, OpenPythonToolboxAdapter,
                                   JOB_TAGS, universal_job_tags)


@dataclass(frozen=True)
class BehavioralDiff:
    error_shape: str
    features: tuple
    passing: tuple
    failing: tuple
    preferred_roles: tuple


class BehavioralDiffController:
    """Public-output error shapes; no domain labels, query answer or oracle."""
    def __init__(self, roles=None, *, max_proposals=16):
        if type(max_proposals) is not int or not 0 <= max_proposals <= 64:
            raise ValueError("bounded behavioral proposal count required")
        self.roles, self.max_proposals = roles or {}, max_proposals
        self.proposed = 0
        self.partial_sources, self.seen = {}, set()
    @staticmethod
    def classify_error_shape(sigma_pub_candidate, Y_pub, *, meter=None):
        predicted, target = tuple(sigma_pub_candidate), tuple(Y_pub)
        if not target or len(predicted) != len(target):
            raise ValueError("aligned nonempty public output vectors required")
        if meter is not None:
            meter.charge("behavioral_diff_work_units", len(target))
        passing = tuple(i for i, (a, b) in enumerate(zip(predicted, target)) if freeze(a) == freeze(b))
        failing = tuple(i for i in range(len(target)) if i not in passing)
        def same_shape(a, b):
            if type(a) is not type(b):
                return False
            if isinstance(a, dict):
                return {freeze(k) for k in a} == {freeze(k) for k in b}
            return not isinstance(a, (tuple, list, str)) or len(a) == len(b)
        partial = float(0 < len(passing) < len(target))
        excess = sum(type(a) is type(b) and structural_measure(a) > structural_measure(b)
                     for a, b in zip(predicted, target))/len(target) if failing else 0.
        residual = sum(same_shape(predicted[i], target[i]) for i in failing)/len(target)
        dead = float(bool(failing) and not passing and excess == 0 and residual == 0)
        shape = ("EXACT_PUBLIC_FIT" if not failing else "PARTIAL_SUBSET_MATCH" if partial else
                 "MEASURE_EXCESS" if excess else "SAME_SHAPE_RESIDUAL" if residual else "DEAD_UNCORRELATED")
        preferred = {"MEASURE_EXCESS": ("PROJ_IDEMPOTENT", "CONTRACTIVE_STEP"),
            "SAME_SHAPE_RESIDUAL": ("PRESERVING_STEP", "INVOLUTION_DUAL"),
            "PARTIAL_SUBSET_MATCH": ("STABILIZING_GUARD", "CONDITIONAL_BRANCH_SPLIT")}.get(shape, ())
        return BehavioralDiff(shape, (partial, float(excess), float(residual), dead), passing, failing, preferred)

    def conditional_branch_split(self, grammar, public_io, candidate, guards, *, meter):
        """Find an actually declared boolean separator, not an invented rule.

        No guard in the toolbox means abstention. Returning a split does not
        grant a new conditional production or a free expansion of the grammar.
        """
        outputs = [eval_expr(candidate, x, grammar.ops, meter) for x, _ in public_io]
        diff = self.classify_error_shape(outputs, [y for _, y in public_io], meter=meter)
        if diff.error_shape != "PARTIAL_SUBSET_MATCH":
            return None
        for guard in sorted(guards, key=lambda e: (primitive_cost(e, grammar.ops), repr(e.key()))):
            validate_program(guard, grammar)
            if guard.sort != "BOOL":
                continue
            truth = tuple(eval_expr(guard, x, grammar.ops, meter) for x, _ in public_io)
            if all(type(t) is bool and t == (i in diff.passing) for i, t in enumerate(truth)):
                return dict(guard=guard, D_pass=tuple(public_io[i] for i in diff.passing),
                            D_fail=tuple(public_io[i] for i in diff.failing), true_means_pass=True)
            if all(type(t) is bool and t == (i in diff.failing) for i, t in enumerate(truth)):
                return dict(guard=guard, D_pass=tuple(public_io[i] for i in diff.passing),
                            D_fail=tuple(public_io[i] for i in diff.failing), true_means_pass=False)
        return None

    def corrective_wrappers(self, grammar, candidate, public_io, roles, *, meter):
        """Domain-neutral proposals. The caller must verify ALL public IO."""
        prediction = [eval_expr(candidate, x, grammar.ops, meter) for x, _ in public_io]
        diff = self.classify_error_shape(prediction, [y for _, y in public_io], meter=meter)
        proposals = []
        for op in grammar.operators:
            if op.inputs != (candidate.sort,):
                continue
            role = roles.get(op.name)
            preferred = role is not None and (role.primary in diff.preferred_roles or role.shift in diff.preferred_roles)
            proposals.append((not preferred, op.name, apply(op, candidate)))
        return tuple(e for _, _, e in sorted(proposals))

    def repair_proposals(self, expr, outputs, grammar, public_io, enum, meter):
        if self.proposed >= self.max_proposals:
            return ()
        diff = self.classify_error_shape(outputs[:-1], [y for _, y in public_io], meter=meter)
        if diff.error_shape == "PARTIAL_SUBSET_MATCH" and len(self.partial_sources) < 8:
            self.partial_sources[expr.key()] = expr
        guards = tuple(g for (cost, sort), group in enum.pool.items() if sort == "BOOL" for g in group)
        candidates = []
        sources = list(self.partial_sources.values()) if grammar.conditionals and guards else [expr]
        for source in sources:
            for wrapper in self.corrective_wrappers(grammar, source, public_io, self.roles, meter=meter):
                proposals = [wrapper]
                if grammar.conditionals and guards and wrapper.sort == source.sort:
                    split = self.conditional_branch_split(grammar, public_io, source, guards, meter=meter)
                    if split is not None:
                        yes, no = (source, wrapper) if split["true_means_pass"] else (wrapper, source)
                        proposals.append(Expr("if", source.sort, None, (split["guard"], yes, no)))
                for candidate in proposals:
                    if candidate.key() in self.seen or enum.cost(candidate) > enum.bound or not enum.admissible(candidate):
                        continue
                    self.seen.add(candidate.key())
                    self.proposed += 1
                    meter.charge("behavioral_proposal_work_units")
                    candidates.append(candidate)
                    if self.proposed >= self.max_proposals:
                        return tuple(candidates)
        return tuple(candidates)


def behavioral_execution_features(expr, grammar, outputs, public_targets, meter=None):
    return (*execution_features(expr, grammar),
            *BehavioralDiffController.classify_error_shape(outputs, public_targets, meter=meter).features)


class PhenotypeAffinityCompass:
    """Public-only, header-free compression heuristic; never a pruning law.

    Raw NCD is symmetrized by the smaller concatenation size and clipped: short
    finite strings do NOT give a mathematical metric or a semantic oracle.
    Exact equality is zero. Canonical type tags prevent missing/None and
    bool/int/list/tuple aliases; 'header-free' refers to DEFLATE framing only.
    """
    def __init__(self, meter=None):
        self.meter = meter if meter is not None else WorkMeter()
        self._compressed = {}

    @staticmethod
    def canon_bytes(value):
        return json.dumps(freeze(value), ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")

    @staticmethod
    def _tokens(value):
        if isinstance(value, dict):
            return [PhenotypeAffinityCompass.canon_bytes(("key", k)) for k in value] + [
                t for v in value.values() for t in PhenotypeAffinityCompass._tokens(v)]
        if isinstance(value, (tuple, list)):
            return [t for v in value for t in PhenotypeAffinityCompass._tokens(v)]
        if isinstance(value, str):
            return [PhenotypeAffinityCompass.canon_bytes(c) for c in value]
        return [PhenotypeAffinityCompass.canon_bytes(value)]

    def raw_complexity(self, data):
        if type(data) is not bytes:
            raise ValueError("canonical bytes required")
        self.meter.charge("compass_work_units")
        if data not in self._compressed:
            self.meter.charge("compass_work_units", len(data)+1)
            compressor = zlib.compressobj(level=6, wbits=-15)
            result = len(compressor.compress(data)+compressor.flush())
            if len(self._compressed) < 512:
                self._compressed[data] = result
            return result
        return self._compressed[data]

    def phenotype_distance(self, sigma_pub_candidate, Y_pub):
        candidate, target = tuple(sigma_pub_candidate), tuple(Y_pub)
        if not target or len(candidate) != len(target):
            raise ValueError("aligned nonempty public vectors required")
        a, b = self.canon_bytes(candidate), self.canon_bytes(target)
        self.meter.charge("compass_work_units", len(a)+len(b))
        if a == b:
            return 0.
        ca, cb = self.raw_complexity(a), self.raw_complexity(b)
        cab = min(self.raw_complexity(a+b), self.raw_complexity(b+a))
        ncd = max(0., min(1., (cab-min(ca, cb))/max(1, ca, cb)))
        ta, tb = Counter(self._tokens(candidate)), Counter(self._tokens(target))
        union = sum((ta | tb).values())
        jaccard = 1.-sum((ta & tb).values())/union if union else 0.
        ma, mb = sum(structural_measure(v) for v in candidate), sum(structural_measure(v) for v in target)
        measure = abs(ma-mb)/(1.+max(ma, mb))
        self.meter.charge("compass_work_units", sum(ta.values())+sum(tb.values()))
        return max(0., min(1., .40*ncd+.40*jaccard+.20*measure))


class StigmergicWorkspaceEngine:
    """At most three public-guided hops, exact within each declared hop space.

    A slot is a PUBLIC-signature island, not a cap on query values. ALL distinct
    query outputs of a selected island survive, with minimum expanded primitive
    cost representatives. This is essential under non-injective parents. A
    stored 'query_twin_ast' is an audit convenience, never the entire class.

    The grammar is versioned: leaves are earlier executable programs, cost 1
    per hop, with a global expanded primitive cap. Uniqueness concerns the
    reached hop grammar, NOT all primitive programs of cost <= the cap or all
    hypothetical future portfolios. No target solution updates the library.
    """
    def __init__(self, b0=3, *, max_hops=3, slots=3, roles=None, skills=(), scorer=None,
                 meter=None, primitive_cap=None, twin_mutations=16, cap_multiplier=2):
        if type(b0) is not int or not 2 <= b0 <= 6 or type(max_hops) is not int or not 1 <= max_hops <= 16 or slots != 3:
            raise ValueError("fixed finite three-slot workspace bounds required")
        self.b0, self.max_hops, self.slots = b0, max_hops, slots
        self.roles, self.skills, self.scorer = roles or {}, tuple(islice(iter(skills), 4)), scorer
        if len(self.skills) > 3 or any(not isinstance(s, ParametricSkillMacro) for s in self.skills):
            raise ValueError("workspace accepts at most three typed open skills")
        self.meter = meter if meter is not None else WorkMeter()
        if cap_multiplier not in (2, 3):
            raise ValueError("explicit versioned primitive-cap multiplier required")
        self.cap_multiplier = cap_multiplier
        self.primitive_cap = cap_multiplier*b0 if primitive_cap is None else primitive_cap
        if self.primitive_cap != cap_multiplier*b0:
            raise ValueError("expanded primitive cap differs from its declared multiplier")
        self.twin_mutations = twin_mutations
        self.compass = PhenotypeAffinityCompass(self.meter)
        self.last_report = {}

    @staticmethod
    def public_key(sort, outputs):
        return (sort, tuple(freeze(y) for y in outputs[:-1]))

    def _classes(self, grammar, entries):
        """One minimum-primitive representative per FULL signature, no alpha2."""
        classes = {}
        for expr, outputs, cost in entries:
            self.meter.charge("workspace_index_work_units")
            pure = unfold_workspace_expr(expr, self.meter)
            prim = primitive_cost(pure, grammar.ops)
            key = (expr.sort, tuple(freeze(y) for y in outputs))
            order = (prim, cost, repr(pure.key()))
            if key not in classes or order < classes[key][0]:
                classes[key] = (order, pure, tuple(outputs), cost)
        return classes

    @staticmethod
    def class_digest(classes):
        return digest(sorted(((key, row[0][0]) for key, row in classes.items()), key=repr))

    def outer_role(self, pure):
        role = self.roles.get(pure.value) if pure.kind == "apply" else None
        return role.transfer_key() if role is not None else ("UNCLASSIFIED", "ANY")

    def rebalance_portfolio(self, selected, candidates, workspace, inputs, target):
        return selected

    def rank_features(self, expr, grammar, outputs, target, meter):
        return behavioral_execution_features(expr, grammar, outputs, target, meter)

    def _choose(self, grammar, entries, workspace, inputs, target):
        classes = self._classes(grammar, entries)
        old_keys = {self.public_key(e.sort, tuple(eval_expr(e, x, grammar.ops, self.meter,
                    "workspace_index_work_units") for x in inputs)) for e in workspace}
        x_key = self.public_key(grammar.input_sort, inputs)
        groups = {}
        for key, row in classes.items():
            _, pure, outputs, hop_cost = row
            public = self.public_key(pure.sort, outputs)
            if 2 <= hop_cost <= self.b0 and len(set(public[1])) > 1 and public not in old_keys | {x_key}:
                groups.setdefault(public, []).append(row)
        candidates = []
        for key, variants in groups.items():
            representative = min(variants, key=lambda r: r[0])
            pure, ys = representative[1:3]
            role_key = self.outer_role(pure)
            candidates.append(dict(key=key, outputs=ys, role=role_key,
                distance=self.compass.phenotype_distance(ys[:-1], target),
                variants=variants))
        candidates.sort(key=lambda r: (r["distance"], repr(r["key"])))
        selected = []
        if candidates:
            selected.append(("EXPLOIT", candidates[0]))
            bridges = [r for r in candidates[1:] if r["role"] != candidates[0]["role"]]
            if bridges:
                selected.append(("ROLE_BRIDGE", bridges[0]))
            remaining = [r for r in candidates if r["key"] not in {s["key"] for _, s in selected}]
            known = [tuple(inputs[:-1])] + [tuple(eval_expr(e, x, grammar.ops, self.meter,
                "workspace_index_work_units") for x in inputs[:-1]) for e in workspace]
            for r in remaining:
                r["novelty"] = min(self.compass.phenotype_distance(r["outputs"][:-1], k) for k in known)
            if remaining:
                chosen = min(remaining, key=lambda r: (-r["novelty"], -int(len(r["variants"]) > 1), repr(r["key"])))
                selected.append(("NOVELTY", chosen))
        selected = self.rebalance_portfolio(selected, candidates, workspace, inputs, target)
        keys = old_keys | {r["key"] for _, r in selected}
        # Preserve ALL query variants, including new variants of existing islands.
        # Rebinding to leaf cost 1 makes minimum primitive cost the relevant rank.
        carried = {e.key(): e for e in workspace}
        for _, pure, outputs, _ in classes.values():
            if self.public_key(pure.sort, outputs) in keys:
                carried[pure.key()] = pure
        best = {}
        for pure in carried.values():
            ys = tuple(eval_expr(pure, x, grammar.ops, self.meter, "workspace_commit_work_units") for x in inputs)
            key = (pure.sort, tuple(freeze(y) for y in ys))
            order = (primitive_cost(pure, grammar.ops), repr(pure.key()))
            if key not in best or order < best[key][0]:
                best[key] = (order, pure)
        next_workspace = tuple(best[k][1] for k in sorted(best, key=repr))
        audit = []
        for slot, r in selected:
            # Include every FULL-signature member of the selected public island.
            variants = sorted((row for key, row in classes.items() if key[0] == r["key"][0]
                               and key[1][:-1] == r["key"][1]), key=lambda row: row[0])
            audit.append(dict(slot=slot, public_signature=r["key"], role=r["role"],
                phenotype_distance=r["distance"], novelty=r.get("novelty"),
                canonical_ast=expression_wire(variants[0][1]),
                query_twin_ast=expression_wire(variants[1][1]) if len(variants) > 1 else None,
                query_variant_count=len(variants)))
        return next_workspace, audit, classes

    def run(self, grammar, task, *, trace=None, explore=False):
        inputs = tuple(x for x, _ in task.public_io)+(task.query,)
        target, workspace, hops = tuple(y for _, y in task.public_io), (), []
        started = self.meter.total
        self.last_report = dict(schema="wave24_workspace_v1" if self.cap_multiplier == 2 else "wave24_workspace_v2",
            certificate_scope="reached_hop_grammar_only",
            max_hops=self.max_hops, b_hop=self.b0, primitive_cap=self.primitive_cap, slots=3,
            target_training_tasks=0, hops=hops, compiled_candidates=[], explored_source=explore)
        labels = {}
        for x, y in task.public_io:
            key = freeze(x)
            if key in labels and labels[key] != freeze(y):
                if trace is not None:
                    trace["workspace"] = self.last_report
                return SearchResult("VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS", (), (), False)
            labels[key] = freeze(y)
        all_entries, last_goal = [], GoalCheck(target, task.output_sort)
        try:
            for hop in range(1, self.max_hops+1):
                goal, entries = GoalCheck(target, task.output_sort), []
                last_goal = goal
                def priority(expr, ys, meter):
                    if getattr(self, "canonical_only", False):
                        return ()
                    features = self.rank_features(expr, grammar, ys, target, meter)
                    if self.scorer is not None and self.scorer.models is not None:
                        return self.scorer.predict(features, meter=meter)
                    return (features[-1], features[-3], features[-2])
                enum = ExactEnumerator(grammar, inputs, self.b0, meter=self.meter, macros=self.skills,
                    evolved=True, primitive_cap=self.primitive_cap, priority=priority, workspace=workspace)
                record = dict(hop=hop, workspace=[expression_wire(e) for e in workspace],
                              complete=False, selection=[], signature_digest=None)
                hops.append(record)
                twin = PopperianTwinVerifier(self.roles, max_mutations=self.twin_mutations)
                for expr, outputs, cost in enum:
                    entries.append((expr, outputs, cost))
                    split = goal.observe(expr, outputs)
                    if goal.first is not None and trace is not None and trace.get("work_to_g1") is None:
                        trace["work_to_g1"] = self.meter.total-started
                    if goal.first is not None and twin is not None and not explore:
                        proposal = twin.search(goal.witnesses[0], grammar, task.public_io, task.query, enum, self.meter)
                        record["twin"] = twin.last_report
                        twin = None
                        if proposal is not None:
                            split = goal.observe(*proposal)
                    if split and not explore:
                        if trace is not None:
                            trace["work_to_g2"] = self.meter.total-started
                        break
                record["complete"] = enum.complete
                last_goal = goal
                all_entries.extend((unfold_workspace_expr(e, self.meter), ys, primitive_cost(e, grammar.ops))
                                   for e, ys, _ in entries)
                if goal.first is not None and not explore:
                    record["hop_witnesses"] = [expression_wire(e) for e in goal.witnesses]
                    record["witness_hop_costs"] = [enum.cost(e) for e in goal.witnesses]
                    raw = goal.result(enum.complete)
                    pure = tuple(unfold_workspace_expr(e, self.meter) for e in raw.witnesses)
                    self.last_report["compiled_candidates"] = [skill_wire(s) for e in pure for s in self.compile_trajectory(e, grammar)]
                    if enum.complete:
                        record["signature_digest"] = self.class_digest(self._classes(grammar, entries))
                        if trace is not None:
                            trace["work_to_uniqueness"] = self.meter.total-started
                    return SearchResult(raw.status, pure, raw.query_values, raw.complete, raw.root_equivalence_discharges)
                next_workspace, selection, classes = self._choose(grammar, entries, workspace, inputs, target)
                record.update(signature_digest=self.class_digest(classes), selection=selection)
                if not selection or hop == self.max_hops:
                    record["stop_reason"] = "no_new_public_signatures" if not selection else "hop_cap"
                    break
                workspace = next_workspace
            return all_entries if explore else last_goal.result(True)
        except WorkExhausted:
            self.last_report["budget_exhausted"] = True
            return all_entries if explore else last_goal.result(False)
        finally:
            if trace is not None:
                trace["workspace"] = self.last_report

    def compile_trajectory(self, program, grammar):
        """Parametric SOURCE proposals only; no implicit promotion of a target."""
        pure = unfold_workspace_expr(program, self.meter)
        found = {}
        for root in ast_nodes(pure):
            inner = root
            for depth in range(1, self.b0+1):
                self.meter.charge("workspace_compile_work_units")
                if inner.kind != "apply" or len(inner.children) != 1:
                    break
                inner = inner.children[0]
                def replace(e):
                    self.meter.charge("workspace_compile_work_units")
                    return typed_hole(e.sort) if e is inner else Expr(e.kind, e.sort, e.value, tuple(replace(c) for c in e.children))
                skill = ParametricSkillMacro(replace(root), (inner.sort,))
                if 2 <= skill.expansion_cost(grammar.ops) <= self.b0:
                    skill.validate(grammar)
                    found[skill.key()] = skill
        return tuple(found[k] for k in sorted(found, key=repr))


def verify_workspace_certificate(grammar, task, result, report, *, skills=(), meter=None):
    """Independent unquotiented recurrence at EVERY reached hop.

    Rebuilds all query variants of selected public islands and checks their
    minimum primitive costs; a one-twin/alpha2 intermediate truncation fails.
    Role/compass preferences are heuristics, not correctness premises.
    """
    meter = meter if meter is not None else WorkMeter()
    if result.status == "VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS":
        labels, contradictory = {}, False
        for x, y in task.public_io:
            if freeze(x) in labels and labels[freeze(x)] != freeze(y):
                contradictory = True
            labels[freeze(x)] = freeze(y)
        if not contradictory or result.complete or result.witnesses or result.query_values or report.get("hops") != []:
            raise ValueError("false deterministic-assumption violation")
        return True
    multiplier = {"wave24_workspace_v1": 2, "wave24_workspace_v2": 3, "wave24_workspace_v3": 3}.get(report.get("schema"))
    hop_limit = 16 if report.get("schema") == "wave24_workspace_v3" else 3
    if (multiplier is None or report.get("certificate_scope") != "reached_hop_grammar_only"
        or report.get("target_training_tasks") != 0 or report.get("explored_source") is not False
        or report.get("b_hop") not in range(2, 7) or report.get("primitive_cap") != multiplier*report["b_hop"]
        or report.get("max_hops") not in range(1, hop_limit+1) or report.get("slots") != 3):
        raise ValueError("invalid declared workspace certificate space")
    hops = report.get("hops", [])
    if not 1 <= len(hops) <= report["max_hops"]:
        raise ValueError("incomplete hop provenance")
    b0, inputs, expected = report["b_hop"], tuple(x for x, _ in task.public_io)+(task.query,), {}
    for index, hop in enumerate(hops):
        if hop["hop"] != index+1:
            raise ValueError("hop order mismatch")
        workspace = tuple(expression_from_wire(e) for e in hop["workspace"])
        actual = {}
        for pure in workspace:
            validate_program(pure, grammar)
            ys = tuple(freeze(eval_expr(pure, x, grammar.ops, meter)) for x in inputs)
            key = (pure.sort, ys)
            if key in actual:
                raise ValueError("duplicate workspace full signature")
            actual[key] = primitive_cost(pure, grammar.ops)
        if actual != expected:
            raise ValueError("workspace lost a query variant or altered primitive provenance")
        leaf_macros = bool(hop.get("leaf_macros") or report.get("leaf_macros"))
        if report.get("schema") == "wave24_workspace_v3":
            gate = None
            if hop.get("noether_applied"):
                gate = NoetherConservationGate()
                gate.fingerprint_operators(grammar.operators, inputs)
            enum = ExactEnumerator(grammar, inputs, b0, quotient=True, meter=meter, macros=skills,
                evolved=True, primitive_cap=report["primitive_cap"], workspace=workspace,
                target_public=tuple(y for _, y in task.public_io) if gate is not None else None,
                noether=gate, inner_heuristics=False, leaf_macros=leaf_macros)
        elif hop.get("noether_applied"):
            gate = NoetherConservationGate()
            gate.fingerprint_operators(grammar.operators, inputs)
            enum = ExactEnumerator(grammar, inputs, b0, quotient=False, meter=meter, macros=skills,
                evolved=True, primitive_cap=report["primitive_cap"], workspace=workspace,
                target_public=tuple(y for _, y in task.public_io), noether=gate, inner_heuristics=False,
                leaf_macros=leaf_macros)
        else:
            enum = ExhaustiveASTEnumerator(grammar, inputs, b0, meter=meter, macros=skills,
                                          evolved=True, primitive_cap=report["primitive_cap"], workspace=workspace,
                                          leaf_macros=leaf_macros)
        entries = list(enum)
        full = {}
        goal = GoalCheck([y for _, y in task.public_io], task.output_sort)
        for expr, ys, cost in entries:
            key, prim = (expr.sort, tuple(freeze(y) for y in ys)), primitive_cost(expr, grammar.ops)
            full[key] = min(prim, full.get(key, prim))
            if len(goal.values) < 2:
                goal.observe(expr, ys)
        if hop["complete"]:
            expected_digest = digest(sorted(full.items(), key=repr))
            if hop["signature_digest"] != expected_digest and not hop.get("noether_applied"):
                raise ValueError("hop closure differs from exhaustive full signatures")
        elif index != len(hops)-1 or result.status != "AMBIGUOUS_WITNESS_FOUND":
            raise ValueError("incomplete hop cannot certify uniqueness or a later hop")
        if index < len(hops)-1:
            if goal.first is not None:
                raise ValueError("continued after an already reached public goal")
            selection = hop["selection"]
            if not 1 <= len(selection) <= 3 or len({s["slot"] for s in selection}) != len(selection):
                raise ValueError("invalid workspace portfolio")
            keys = {StigmergicWorkspaceEngine.public_key(e.sort, tuple(eval_expr(e, x, grammar.ops, meter) for x in inputs)) for e in workspace}
            for selected in selection:
                public_key = tuple_tree(selected["public_signature"])
                variants = {k: p for k, p in full.items() if (k[0], k[1][:-1]) == public_key}
                if not variants or len(set(public_key[1])) <= 1 or selected["query_variant_count"] != len(variants):
                    raise ValueError("incomplete selected island variants")
                for field in ("canonical_ast", "query_twin_ast"):
                    if selected[field] is not None:
                        e = expression_from_wire(selected[field]); validate_program(e, grammar)
                        key = (e.sort, tuple(freeze(eval_expr(e, x, grammar.ops, meter)) for x in inputs))
                        if key not in variants or primitive_cost(e, grammar.ops) != variants[key]:
                            raise ValueError("island/twin not in preceding exact closure")
                keys.add(public_key)
            # Existing values remain valid even if no shorter current syntax
            # reproduces an island; it is itself already a legal leaf.
            expected = {k: p for k, p in full.items() if (k[0], k[1][:-1]) in keys}
        else:
            if hop["complete"] != result.complete:
                raise ValueError("completion flag disagrees with the reached hop")
            encoded = tuple(expression_from_wire(e) for e in hop.get("hop_witnesses", []))
            if len(encoded) != len(result.witnesses):
                raise ValueError("missing folded witness provenance")
            for folded, pure in zip(encoded, result.witnesses):
                validate_program(folded, grammar, macros=skills, workspace=workspace)
                if (enum.cost(folded) > b0 or not enum.admissible(folded)
                    or unfold_workspace_expr(folded).key() != pure.key()):
                    raise ValueError("incorrect unfolded workspace witness")
            folded_result = SearchResult(result.status, encoded, result.query_values, result.complete,
                                         result.root_equivalence_discharges)
            verify_certificate(grammar, task.public_io, task.query, task.output_sort, b0, folded_result,
                               meter=meter, macros=skills, evolved=True, primitive_cap=report["primitive_cap"], workspace=workspace)
    return True


def tuple_tree(value):
    return tuple(tuple_tree(v) for v in value) if isinstance(value, (list, tuple)) else value


class MeterView:
    """Forward all work into the same owner meter; never resets a budget."""
    def __init__(self, parent, category):
        self.parent, self.category = parent, category

    def charge(self, category="training_work_units", n=1):
        self.parent.charge(self.category, n)

    @property
    def total(self):
        return self.parent.total


@dataclass(frozen=True)
class World:
    name: str
    grammar: Grammar
    output_sort: str
    inputs: tuple
    carriers: dict


def procedural_worlds():
    """Operator semantics are supplied; no family-specific pruning is supplied.

    These deliberately small, complete finite carriers support executable
    source correctness checks, not an open-world intelligence claim.
    """
    seqs = tuple(v for n in range(4) for v in product((0, 1), repeat=n))
    strings = tuple("".join(v) for n in range(4) for v in product("ab", repeat=n))
    records = tuple({k: v for k, v in zip(("a", "b"), pair) if v != "absent"}
                    for pair in product(("absent", None, 0, 1), repeat=2))
    states = tuple(product((0, 1), repeat=2))
    bits = tuple(product((0, 1), repeat=3))

    def swap_record(d):
        return {({"a": "b", "b": "a"}[k]): v for k, v in d.items()}

    specs = (
        ("INT_SEQ", "SEQ", seqs, (lambda x: x[::-1], lambda x: x[1:] + x[:1], lambda x: tuple(sorted(x)))),
        ("STR_PARSE", "STR", strings, (lambda x: x[::-1], lambda x: x.translate(str.maketrans("ab", "ba")), lambda x: x[1:])),
        ("DICT_RECORD", "DICT", records, (swap_record, lambda d: {**d, "a": None}, lambda d: {k: v for k, v in d.items() if k != "a"})),
        ("STATE_TRANSITION", "STATE", states, (lambda s: (1-s[0], s[1]), lambda s: s[::-1], lambda s: (s[0], s[0] ^ s[1]))),
        ("BIT_CELLULAR_AUTOMATA", "BITS", bits, (lambda s: s[1:] + s[:1], lambda s: tuple(s[(i-1) % 3] ^ s[(i+1) % 3] for i in range(3)), lambda s: tuple(1-b for b in s))),
    )
    worlds = []
    for name, sort, values, functions in specs:
        ops = tuple(Operator(f"op_{i}", (sort,), sort, fn) for i, fn in enumerate(functions))
        worlds.append(World(name, Grammar(sort, ops), sort, values, {sort: values}))
    return tuple(worlds)


@dataclass(frozen=True)
class PublicTask:
    public_io: tuple
    query: Any
    output_sort: str


@dataclass(frozen=True)
class GeneratedTask:
    """Evaluator-only teacher/tier record; solver receives public_view only."""
    world: str
    teacher: Expr
    public_view: PublicTask
    teacher_query: Any
    teacher_primitive_cost: int
    tier: str
    minimum_cost: int | None


def generated_program(grammar, rng, max_cost):
    """Construct, do not search/select by evaluated learner performance."""
    expr = variable(grammar.input_sort)
    for _ in range(rng.randrange(max_cost)):
        options = [op for op in grammar.operators if op.inputs == (expr.sort,)
                   and primitive_cost(expr, grammar.ops) + op.cost <= max_cost]
        if not options:
            break
        expr = apply(rng.choice(options), expr)
    return expr


class SeededProceduralTaskGenerator:
    def __init__(self, seed, b0, *, public_count=3):
        if type(seed) is not int or seed < 0 or b0 < 2 or public_count < 1:
            raise ValueError("seed, bound and public count required")
        self.rng, self.b0, self.public_count = random.Random(seed), b0, public_count

    def sample(self, world, meter):
        meter.charge("generator_work_units")
        teacher = generated_program(world.grammar, self.rng, 2*self.b0)
        rows = self.rng.sample(list(world.inputs), min(len(world.inputs), self.public_count+1))
        public = tuple((x, eval_expr(teacher, x, world.grammar.ops, meter, "generator_work_units")) for x in rows[:-1])
        query = rows[-1]
        target = eval_expr(teacher, query, world.grammar.ops, meter, "generator_work_units")
        cost = primitive_cost(teacher, world.grammar.ops)
        # Teacher cost stratifies complexity; it does NOT prove minimum cost.
        return GeneratedTask(world.name, teacher, PublicTask(public, query, world.output_sort),
                             target, cost, "Tier-1" if cost <= self.b0 else "Tier-2", None)


class ZeroDataFrontierSelfPlay:
    """Mine source-only semantic classes, rather than reject random syntax.

    Minimality is with respect to the COMPLETE public+query signature, not
    public evidence alone. No universal nonempty-frontier claim is made for a
    grammar in which the requested band is empty or semantically saturated.
    """
    def __init__(self, seed, b0=4, *, public_count=5, allow_arrival_selfplay=False, behavioral_features=False):
        self.generator = SeededProceduralTaskGenerator(seed, b0)
        self.public_count = public_count
        self.allow_arrival_selfplay = allow_arrival_selfplay
        self.behavioral_features = behavioral_features
        self.accepted = []
        self.attempts = 0
        self.derivations = []
        self.training_rows = []
        self.diagnostics = {}

    def wake(self, world, *, attempts, meter):
        if world.name == "BIT_CELLULAR_AUTOMATA" and not self.allow_arrival_selfplay:
            raise ValueError("held-out world cannot train scorer or library")
        if type(attempts) is not int or not 0 <= attempts <= 100:
            raise ValueError("bounded source attempts required")
        view = MeterView(meter, "training_work_units")
        if self.attempts or self.accepted:
            raise ValueError("one bounded frontier mining pass per player")
        if not attempts:
            return ()
        inputs = self.generator.rng.sample(list(world.inputs), min(len(world.inputs), self.public_count+1))
        enum = ExactEnumerator(world.grammar, inputs, self.generator.b0, meter=view)
        entries = list(enum)
        if not enum.complete:
            raise ValueError("incomplete quotient cannot certify frontier minimality")
        self.derivations = entries
        groups = {}
        public_minimum = {}
        for expr, outputs, cost in entries:
            view.charge()
            signature = (expr.sort, tuple(freeze(y) for y in outputs[:-1]))
            groups.setdefault(signature, set()).add(freeze(outputs[-1]))
            public_minimum[signature] = min(cost, public_minimum.get(signature, cost))
        low = max(3, self.generator.b0-2)
        frontier = [(e, ys, c) for e, ys, c in entries
                    if e.sort == world.output_sort and low <= c <= self.generator.b0
                    and len({freeze(y) for y in ys[:-1]}) > 1]
        def diversity(expr):
            return len({n.value for n in ast_nodes(expr) if n.kind == "apply"})
        frontier.sort(key=lambda row: (
            -len(groups[(row[0].sort, tuple(freeze(y) for y in row[1][:-1]))]),
            -diversity(row[0]), row[2], repr(row[0].key())))
        for expr, outputs, cost in frontier[:attempts]:
            view.charge()
            public = PublicTask(tuple(zip(inputs[:-1], outputs[:-1])), inputs[-1], world.output_sort)
            self.accepted.append(GeneratedTask(world.name, expr, public, outputs[-1], cost, "Tier-1", cost))
        # These are derivation labels, NOT observed time-to-event labels. The
        # separate critic explicitly interprets higher values as promising.
        for task in self.accepted:
            ancestors = {n.key() for n in ast_nodes(task.teacher)}
            ancestor_tiers = {primitive_cost(n, world.grammar.ops) for n in ast_nodes(task.teacher)}
            for expr, outputs, cost in entries:
                view.charge()
                if expr.key() not in ancestors and cost not in ancestor_tiers:
                    continue
                signature = (expr.sort, tuple(freeze(y) for y in outputs[:-1]))
                targets = [y for _, y in task.public_view.public_io]
                features = (behavioral_execution_features(expr, world.grammar, outputs[:-1], targets, view)
                            if self.behavioral_features else execution_features(expr, world.grammar))
                self.training_rows.append(dict(features=features,
                    J_fit=int(expr.key() in ancestors), J_disagree=int(len(groups[signature]) >= 2),
                    purpose="training", label_semantics="source_derivation_behavioral_v3" if self.behavioral_features else "source_derivation_membership_v2"))
        self.attempts = 1
        self.diagnostics = dict(quotient_complete=enum.complete, classes=len(entries),
            frontier_classes_available=len(frontier), frontier_tasks_generated=len(self.accepted),
            training_rows_generated=len(self.training_rows), source_probe_inputs=[freeze(x) for x in inputs],
            training_rows_sha256=digest(self.training_rows),
            frontier_representatives=[expression_wire(t.teacher) for t in self.accepted],
            minimality="full_signature_only", public_irreducible_tasks=sum(
                public_minimum[(t.teacher.sort, tuple(freeze(y) for _, y in t.public_view.public_io))]
                == t.teacher_primitive_cost for t in self.accepted),
            disagreement_classes=sum(len(v) >= 2 for v in groups.values()))
        return tuple(self.accepted)

    def sleep(self, world, scorer, meter):
        """Fit ONLY from actual search traces of accepted source tasks.

        Missing disagreement events are censored, not fabricated work labels.
        Extracted ASTs remain proposals until separate shadow feedback passes.
        """
        if world.name == "BIT_CELLULAR_AUTOMATA" and not self.allow_arrival_selfplay:
            raise ValueError("held-out world cannot train scorer or library")
        if self.training_rows:
            if not isinstance(scorer, DerivationOutcomeCritic):
                raise ValueError("binary derivation labels require DerivationOutcomeCritic")
            scorer.fit(self.training_rows, meter=meter)
        return {"training_rows": len(self.training_rows), "censored": 0,
                "candidate_skills": mine_parametric_skills(self, world, meter=meter),
                "scorer_fitted": bool(self.training_rows)}

    def augment_workspace_frontier(self, world, *, meter, roles, extra_tasks=2, max_hops=3):
        """Source-only island exploration; no target labels or fifth-world run.

        The guide is an existing program-generated source task. Extra targets
        are minimum full signatures in THIS selected workspace, not claimed
        globally irreducible in the larger primitive grammar.
        """
        if world.name == "BIT_CELLULAR_AUTOMATA" or not self.accepted or not 0 <= extra_tasks <= 2:
            raise ValueError("permitted nonempty source frontier required")
        view = MeterView(meter, "training_work_units")
        engine = StigmergicWorkspaceEngine(self.generator.b0, roles=roles, meter=view, max_hops=max_hops)
        trace = {}
        entries = engine.run(world.grammar, self.accepted[0].public_view, trace=trace, explore=True)
        if engine.last_report.get("budget_exhausted"):
            raise WorkExhausted("source workspace exploration incomplete")
        classes = engine._classes(world.grammar, [*self.derivations, *entries])
        self.derivations = [(r[1], r[2], r[0][0]) for key, r in sorted(classes.items(), key=lambda kv: repr(kv[0]))]
        deep = [r for r in self.derivations if r[0].sort == world.output_sort
                and self.generator.b0 < r[2] <= 2*self.generator.b0
                and len({freeze(y) for y in r[1][:-1]}) > 1]
        deep.sort(key=lambda r: (r[2], repr(r[0].key())))
        source_inputs = tuple(x for x, _ in self.accepted[0].public_view.public_io)+(self.accepted[0].public_view.query,)
        for expr, ys, cost in deep[:extra_tasks]:
            task = PublicTask(tuple(zip(source_inputs[:-1], ys[:-1])), source_inputs[-1], world.output_sort)
            self.accepted.append(GeneratedTask(world.name, expr, task, ys[-1], cost, "source_workspace", None))
        groups = {}
        for expr, ys, _ in self.derivations:
            groups.setdefault((expr.sort, tuple(freeze(y) for y in ys[:-1])), set()).add(freeze(ys[-1]))
        self.training_rows = []
        for task in self.accepted:
            ancestors = {n.key() for n in ast_nodes(task.teacher)}
            tiers = {primitive_cost(n, world.grammar.ops) for n in ast_nodes(task.teacher)}
            for expr, ys, cost in self.derivations:
                view.charge()
                if expr.key() not in ancestors and cost not in tiers:
                    continue
                self.training_rows.append(dict(features=behavioral_execution_features(expr, world.grammar, ys[:-1],
                    [y for _, y in task.public_view.public_io], view), J_fit=int(expr.key() in ancestors),
                    J_disagree=int(len(groups[(expr.sort, tuple(freeze(y) for y in ys[:-1]))]) >= 2),
                    purpose="training", label_semantics="source_derivation_behavioral_v3"))
        compiled = {s.key(): s for task in self.accepted if task.tier == "source_workspace"
                    for s in engine.compile_trajectory(task.teacher, world.grammar)}
        self.diagnostics.update(workspace=trace["workspace"], workspace_extra_tasks=min(extra_tasks, len(deep)),
            workspace_compiled_candidates=[skill_wire(compiled[k]) for k in sorted(compiled, key=repr)],
            frontier_tasks_generated=len(self.accepted), training_rows_generated=len(self.training_rows),
            training_rows_sha256=digest(self.training_rows), classes=len(self.derivations),
            minimality="primitive_B0_frontier_plus_selected_workspace_minimum_not_global_primitive")
        return self.diagnostics


def ast_nodes(expr):
    yield expr
    for child in expr.children:
        yield from ast_nodes(child)


def mine_parametric_skills(player, world, *, meter):
    """Unary contextual anti-unification over actual canonical derivations.

    Replace a descendant with one typed hole and group identical contexts from
    distinct frontier classes/arguments. No task labels, operator names or
    family-specific templates select the pattern. Empty intervals fail closed.
    """
    view = MeterView(meter, "training_work_units")
    b0, templates = player.generator.b0, {}
    for task in player.accepted:
        for root in ast_nodes(task.teacher):
            current = root
            for depth in range(1, 4):
                if current.kind != "apply" or len(current.children) != 1:
                    break
                current = current.children[0]
                def replace(e):
                    view.charge()
                    if e is current:
                        return typed_hole(e.sort)
                    return Expr(e.kind, e.sort, e.value, tuple(replace(c) for c in e.children))
                skill = ParametricSkillMacro(replace(root), (current.sort,))
                cost = skill.expansion_cost(world.grammar.ops)
                if depth >= 2 and 3 <= cost <= b0-1:
                    key = digest(skill.key())
                    record = templates.setdefault(key, dict(skill=skill, occurrences=set(), arguments=set()))
                    record["occurrences"].add(task.teacher.key())
                    record["arguments"].add(current.key())
    candidates = []
    # A one-skill library costs two MDL units. Recheck compression whenever the
    # library size changes; never use the primitive body including hole loads.
    for key, record in sorted(templates.items()):
        skill = record["skill"]
        if len(record["occurrences"]) < 2 or skill.expansion_cost(world.grammar.ops) <= 2:
            continue
        skill.validate(world.grammar)
        inputs = [x for x, _ in player.accepted[0].public_view.public_io] + [player.accepted[0].public_view.query]
        with_skill = list(ExactEnumerator(world.grammar, inputs, b0, meter=view, macros=(skill,), mdl=True))
        mdl_costs = {(e.sort, tuple(freeze(y) for y in ys)): c for e, ys, c in with_skill}
        gains = []
        for expr, outputs, cost in player.derivations:
            view.charge()
            if expr.sort == world.output_sort and b0-1 <= cost <= b0:
                after = mdl_costs.get((expr.sort, tuple(freeze(y) for y in outputs)), cost)
                gains.append(cost-after)
        utility = sum(gains)
        candidates.append(dict(skill=skill, compression_utility=utility,
            verified_classes=len(gains), occurrence_classes=len(record["occurrences"]),
            distinct_arguments=len(record["arguments"]), primitive_expansion_cost=skill.expansion_cost(world.grammar.ops),
            mdl_call_cost=2, gate="exact_finite_source_compression_not_population_CI"))
    return tuple(sorted(candidates, key=lambda r: (-r["compression_utility"], repr(r["skill"].key()))))


def match_open_context(template, expression):
    if template.kind == "hole":
        return expression.sort == template.sort
    return (template.kind == expression.kind and template.sort == expression.sort
            and template.value == expression.value and len(template.children) == len(expression.children)
            and all(match_open_context(a, b) for a, b in zip(template.children, expression.children)))


def ratcheted_candidates(player, world, *, meter):
    """Extract actual rooted frontier contexts; the input load is not an op."""
    view, found = MeterView(meter, "training_work_units"), {}
    for task in player.accepted:
        for root in ast_nodes(task.teacher):
            current = root
            for depth in range(1, player.generator.b0+int("workspace" in player.diagnostics)):
                view.charge()
                if current.kind != "apply" or len(current.children) != 1:
                    break
                current = current.children[0]
                def replace(e):
                    view.charge()
                    return typed_hole(e.sort) if e is current else Expr(e.kind, e.sort, e.value, tuple(replace(c) for c in e.children))
                skill = ParametricSkillMacro(replace(root), (current.sort,))
                rooted = primitive_cost(skill, world.grammar.ops)
                upper = player.generator.b0+int("workspace" in player.diagnostics)
                if 2 <= skill.expansion_cost(world.grammar.ops) <= player.generator.b0 and min(3, player.generator.b0) <= rooted <= upper:
                    skill.validate(world.grammar)
                    found[skill.key()] = skill
    return tuple(found[k] for k in sorted(found, key=repr))


def source_metabolic_utility(skill, player, world, *, library_size, meter):
    """Exact FINITE descriptor-position savings, not measured CPU speedup.

    Distinct canonical source derivations are validated on the source input
    generator's finite probe carrier. Counting those uses does not create
    independent statistical tasks. Setup/extraction/search costs are charged
    separately and must be included in end-to-end break-even.
    """
    view = MeterView(meter, "training_work_units")
    occurrences = sum(match_open_context(skill.body, n)
                      for task in player.accepted for n in ast_nodes(task.teacher))
    validation_probes = len(world.inputs)
    call_rent = 1+math.ceil(math.log2(1+library_size))
    saved_positions = occurrences*validation_probes*(skill.expansion_cost(world.grammar.ops)-1)
    view.charge(n=occurrences+validation_probes)
    # Exact template validation is charged, not inferred from role similarity.
    call = skill.call(variable(skill.input_sorts[0]))
    for x in world.inputs:
        eval_expr(call, x, world.grammar.ops, view)
    return dict(rule="finite_source_descriptor_rent_v3", saved_positions=saved_positions,
                description_rent=call_rent, net_utility=saved_positions-call_rent,
                occurrence_derivations=occurrences, validation_probes=validation_probes,
                population_confidence_interval=None, physical_execution_savings_claimed=False)


def select_ratcheted_source_skills(player, world, *, max_skills, meter):
    """Bounded, source-only portfolio selection; never sees evaluation tasks."""
    if not 1 <= max_skills <= 3:
        raise ValueError("at most three skills per source layer")
    candidates = ratcheted_candidates(player, world, meter=meter)
    view = MeterView(meter, "training_work_units")
    inputs = [x for x, _ in player.accepted[0].public_view.public_io]+[player.accepted[0].public_view.query] if player.accepted else []
    best, audit = (), []
    best_key = None
    # Source frontiers have at most six candidates in the locked recipe; keep
    # this contract explicit rather than launch an unbounded architecture search.
    if len(candidates) > 12:
        raise ValueError("source portfolio proposal cap exceeded")
    for size in range(1, min(max_skills, len(candidates))+1):
        for portfolio in combinations(candidates, size):
            utilities = [source_metabolic_utility(s, player, world, library_size=size, meter=meter) for s in portfolio]
            if any(u["net_utility"] <= 0 for u in utilities):
                continue
            enum = ExactEnumerator(world.grammar, inputs, player.generator.b0, meter=view,
                macros=portfolio, evolved=True, primitive_cap=2*player.generator.b0)
            closure = list(enum)
            # Descriptor utility is primary. New reachable source signatures
            # break ties only; no held-out outcomes or teacher-query labels.
            gain = sum(u["net_utility"] for u in utilities)
            key = (-gain, -len(closure), tuple(repr(s.key()) for s in portfolio))
            audit.append(dict(skills=[digest(s.key()) for s in portfolio], net_utility=gain,
                              source_reachable_classes=len(closure)))
            if best_key is None or key < best_key:
                best_key, best = key, portfolio
    return best, dict(candidate_count=len(candidates), portfolios=audit,
                     selection_rule="positive_finite_source_rent_then_source_closure_then_canonical")


@dataclass(frozen=True)
class AlgebraicRoleFunctor:
    outer_role: tuple
    inner_role: tuple
    source_skill: str

    def key(self):
        return (self.outer_role, self.inner_role)

    @classmethod
    def lift(cls, skill, roles):
        body = skill.body
        if body.kind != "apply" or len(body.children) != 1:
            return ()
        inner = body.children[0]
        if inner.kind != "apply" or len(inner.children) != 1 or inner.children[0].kind != "hole":
            return ()
        a, b = roles[body.value], roles[inner.value]
        return tuple(cls(x, y, digest(skill.key())) for x, y in product(a.transfer_roles(), b.transfer_roles())
                     if x[0] != "UNCLASSIFIED" and y[0] != "UNCLASSIFIED")

    def instantiate(self, grammar, roles, *, meter):
        found = []
        for outer, inner in product(grammar.operators, repeat=2):
            meter.charge("setup_work_units")
            if len(outer.inputs) != 1 or len(inner.inputs) != 1 or outer.inputs[0] != inner.output:
                continue
            if self.outer_role in roles[outer.name].transfer_roles() and self.inner_role in roles[inner.name].transfer_roles():
                body = apply(outer, apply(inner, typed_hole(inner.inputs[0])))
                skill = ParametricSkillMacro(body, inner.inputs)
                skill.validate(grammar)
                found.append(skill)
        return tuple(found)


def zero_shot_role_transfer(functors, grammar, roles, probe_inputs, *, meter, max_skills=3):
    """Only role matches and unlabeled startup deduplication, no target tasks."""
    if not 1 <= max_skills <= 3:
        raise ValueError("bounded target skill layer")
    inputs = tuple(probe_inputs)
    # Exact probes prevent duplicate/identity-looking transfers on these inputs;
    # they do not certify semantics beyond them or grant any uniqueness pruning.
    seen, selected, lineage, candidates = set(), [], [], {}
    for expr in (variable(grammar.input_sort), *(apply(op, variable(grammar.input_sort)) for op in grammar.operators if op.inputs == (grammar.input_sort,))):
        outputs = tuple(freeze(eval_expr(expr, x, grammar.ops, meter, "setup_work_units")) for x in inputs)
        seen.add((expr.sort, outputs))
    for functor in functors:
        for skill in functor.instantiate(grammar, roles, meter=meter):
            if skill.input_sorts == (grammar.input_sort,):
                candidates.setdefault(skill.key(), (skill, functor))
    for key in sorted(candidates, key=repr):
        skill, functor = candidates[key]
        call = skill.call(variable(grammar.input_sort))
        signature = (call.sort, tuple(freeze(eval_expr(call, x, grammar.ops, meter, "setup_work_units")) for x in inputs))
        if signature in seen:
            continue
        seen.add(signature)
        selected.append(skill)
        lineage.append(dict(skill=skill_wire(skill), source_skill=functor.source_skill,
                            role_functor=[functor.outer_role, functor.inner_role], target_training_tasks=0))
        if len(selected) == max_skills:
            break
    return tuple(selected), tuple(lineage)


def depth_one_fits(grammar, task, meter):
    terminals = (variable(grammar.input_sort), *grammar.constants)
    def candidates():
        yield from terminals
        for op in grammar.operators:
            for children in product(*([v for v in terminals if v.sort == t] for t in op.inputs)):
                yield apply(op, *children)
    for expr in candidates():
        meter.charge("training_work_units")
        if expr.sort == task.output_sort and all(
            freeze(eval_expr(expr, x, grammar.ops, meter)) == freeze(y) for x, y in task.public_io
        ):
            return True
    return False


def source_execution_trace(grammar, task, bound, meter):
    """Actual remaining search-work labels for the two source-only heads."""
    view = MeterView(meter, "training_work_units")
    inputs = [x for x, _ in task.public_io] + [task.query]
    enum = ExactEnumerator(grammar, inputs, bound, meter=view)
    goal = GoalCheck([y for _, y in task.public_io], task.output_sort)
    start = meter.total
    entries, fit_work, split_work = [], None, None
    for expr, outputs, _ in enum:
        work = meter.total-start
        entries.append((execution_features(expr, grammar), work))
        split = goal.observe(expr, outputs)
        if goal.first is not None and fit_work is None:
            fit_work = work
        if split:
            split_work = work
            break
    rows = []
    if fit_work is not None and split_work is not None:
        rows = [dict(features=features, fit_work=max(0, fit_work-work),
                     disagree_work=max(0, split_work-work), purpose="training")
                for features, work in entries]
    return dict(training_rows=rows, witnesses=tuple(goal.witnesses),
                censored=int(fit_work is None or split_work is None))


def execution_features(expr, grammar):
    if isinstance(expr, ParametricSkillMacro):
        expr = expr.call(*(variable(t) for t in expr.input_sorts))
    nodes = []
    def visit(e):
        nodes.append(e)
        for c in e.children:
            visit(c)
    visit(expr)
    return (1., float(primitive_cost(expr, grammar.ops)), float(len(nodes)),
            float(sum(e.kind == "apply" for e in nodes)),
            float(sum(e.kind in ("map", "filter") for e in nodes)),
            float(sum(e.kind == "macro" for e in nodes)))


class DualHeadExecutionScorer:
    """Two existing ridge heads. Scores order search; never certify an answer."""
    def __init__(self, ridge=1.0, *, resource_host=None, feature_count=6):
        if ridge <= 0:
            raise ValueError("positive fixed ridge")
        self.ridge, self.models, self.source_digest = ridge, None, None
        self.resource_host = resource_host
        if feature_count not in (6, 10):
            raise ValueError("six structural or ten structural+behavioral features")
        self.feature_count = feature_count

    def fit(self, rows, *, meter, purpose="training"):
        if purpose != "training" or any(r["purpose"] != "training" for r in rows):
            raise ValueError("only source training feedback may fit scorer")
        if not rows:
            raise ValueError("nonempty observed source feedback required")
        x = [r["features"] for r in rows]
        if any(len(v) != self.feature_count for v in x):
            raise ValueError("declared structural/behavioral feature width required")
        if self.resource_host is None:
            meter.charge("training_work_units", len(rows)*self.feature_count*self.feature_count*2)
            self.models = tuple(fit_ridge(x, [r[k] for r in rows], ridge=self.ridge)
                                for k in ("fit_work", "disagree_work"))
        else:
            scale, beta = self.resource_host.update_ridge(x, [[r["fit_work"], r["disagree_work"]] for r in rows], ridge=self.ridge)
            self.models = tuple((scale, beta[:, i]) for i in range(2))
        self.source_digest = digest(rows)
        return self

    def predict(self, features, *, meter):
        if self.models is None:
            raise ValueError("source scorer not fitted")
        if len(features) != self.feature_count:
            raise ValueError("scorer feature width differs")
        if self.resource_host is not None:
            return tuple(self.resource_host.score_ridge([features], self.models, meter=meter)[0])
        meter.charge("scorer_work_units", 2*self.feature_count)
        return tuple(predict_ridge(m, features) for m in self.models)

    def fingerprint(self):
        params = None if self.models is None else [(s.tolist(), b.tolist()) for s, b in self.models]
        return digest(dict(source=self.source_digest, ridge=self.ridge, parameters=params))

    def benchmark(self, features, *, backend="cpu", repeats=10, mps_authorized=False):
        """Explicit optional benchmark; no GPU use without a new allocation.

        Caller must run through the existing EXPERIMENTAL enforcement host for
        hard CPU/RSS/wall caps. This method alone is NOT a resource sandbox.
        """
        if self.models is None or type(repeats) is not int or not 1 <= repeats <= 1000:
            raise ValueError("fitted scorer and bounded repeat count required")
        if backend not in ("cpu", "mps") or (backend == "mps" and not mps_authorized):
            raise ValueError("explicit MPS authorization required")
        import torch
        if backend == "mps" and not torch.backends.mps.is_available():
            raise ValueError("MPS unavailable; no silent fallback")
        x = torch.tensor(features, dtype=torch.float32, device=backend)
        params = [(torch.tensor(s, dtype=torch.float32, device=backend),
                   torch.tensor(b, dtype=torch.float32, device=backend)) for s, b in self.models]
        def sync():
            if backend == "mps":
                torch.mps.synchronize()
        sync()
        started = time.perf_counter()
        for _ in range(repeats):
            result = torch.stack([(x/s) @ b for s, b in params], dim=-1)
        sync()
        elapsed = time.perf_counter()-started
        return {"backend": backend, "seconds": elapsed, "repeats": repeats,
                "predictions": result.cpu().tolist(), "synchronized": backend == "mps"}


class DerivationOutcomeCritic(DualHeadExecutionScorer):
    """Binary derivation-membership/split heads using the existing ridge path.

    These labels are not timings. Negate predictions for the scheduler's
    ascending priority; predicted outcomes never become observed feedback.
    """
    def fit(self, rows, *, meter, purpose="training"):
        if purpose != "training" or not rows or any(
            r.get("purpose") != "training"
            or r.get("label_semantics") != ("source_derivation_behavioral_v3" if self.feature_count == 10 else "source_derivation_membership_v2")
            or type(r.get("J_fit")) is not int or r["J_fit"] not in (0, 1)
            or type(r.get("J_disagree")) is not int or r["J_disagree"] not in (0, 1)
            for r in rows):
            raise ValueError("observed source derivation labels required")
        converted = [dict(features=r["features"], fit_work=r["J_fit"],
                          disagree_work=r["J_disagree"], purpose="training") for r in rows]
        super().fit(converted, meter=meter, purpose=purpose)
        self.source_digest = digest(rows)
        return self

    def predict(self, features, *, meter):
        return tuple(-v for v in super().predict(features, meter=meter))

    def fingerprint(self):
        return digest(("derivation_outcome_critic_v3" if self.feature_count == 10 else "derivation_outcome_critic_v2", super().fingerprint()))


@dataclass(frozen=True)
class ShadowPair:
    task_id: str
    without_skill_work: int
    with_skill_work: int
    purpose: str = "training_shadow"


class JournalSkillView:
    """Typed AST view on the existing E1 immutable journal, not another store."""
    def __init__(self, journal=None):
        self.journal = journal if journal is not None else Journal()
        self._asts = {}

    def snapshot(self):
        import json
        ids = [json.loads(e.payload_json)["skill_id"] for e in self.journal.snapshot()
               if e.kind in ("wave24_verified_ast_skill", "wave24_injected_ast_skill")]
        quarantined = {json.loads(e.payload_json)["skill_id"] for e in self.journal.snapshot()
                       if e.kind == "wave24_skill_quarantined"}
        return tuple(self._asts[k] for k in ids if k not in quarantined)

    def quarantine(self, skill, *, source_net_utility, purpose="training_shadow"):
        if purpose != "training_shadow" or not math.isfinite(source_net_utility) or source_net_utility > 0:
            raise ValueError("quarantine requires nonpositive observed source utility")
        key = digest(skill.key())
        if key not in self._asts:
            raise ValueError("cannot quarantine an unknown skill")
        self.journal.append("wave24_skill_quarantined", dict(skill_id=key,
            source_net_utility=source_net_utility, purpose=purpose))

    def observe_source_utility(self, skill, *, source_net_utility, purpose="training_shadow"):
        """Automatically quarantine a retained skill when its source benefit ends."""
        if purpose != "training_shadow" or not math.isfinite(source_net_utility):
            raise ValueError("finite source-only utility required")
        if digest(skill.key()) not in self._asts:
            raise ValueError("unknown retained skill")
        if source_net_utility <= 0:
            self.quarantine(skill, source_net_utility=source_net_utility, purpose=purpose)
            return False
        self.journal.append("wave24_skill_utility_review", dict(skill_id=digest(skill.key()),
            source_net_utility=source_net_utility, purpose=purpose))
        return True

    def retain_stream(self, skill, grammar, *, receipt, purpose="source_stream"):
        """Finite paired SOURCE work gate, distinct from old descriptor rent/CI."""
        if purpose != "source_stream" or receipt.get("source_only") is not True:
            raise ValueError("revealed source feedback is required")
        skill.validate(grammar)
        if (receipt.get("certificate_valid") is not True or receipt.get("retention_passed") is not True
            or receipt.get("net_work_saved", 0) <= 0 or not receipt.get("task_digest")):
            return dict(accepted=False, receipt=receipt)
        key = digest(skill.key())
        if key in self._asts or len(self.snapshot()) >= 3:
            return dict(accepted=False, reason="duplicate_or_full")
        self._asts[key] = skill
        self.journal.append("wave24_verified_ast_skill", dict(skill_id=key, ast=skill_wire(skill),
            purpose=purpose, receipt=receipt, population_claim=False))
        return dict(accepted=True, receipt=receipt)

    def inject_for_audit(self, skill, grammar, *, explicitly_enabled=False):
        if not explicitly_enabled or len(self.snapshot()) >= 3:
            raise ValueError("explicit bounded development fault injection required")
        skill.validate(grammar)
        key = digest(skill.key())
        if key in self._asts:
            raise ValueError("duplicate injected shortcut")
        self._asts[key] = skill
        self.journal.append("wave24_injected_ast_skill", dict(skill_id=key, ast=skill_wire(skill),
            purpose="controlled_source_fault_injection", verified=False))

    def promote_ratcheted(self, skill, player, world, *, meter, max_skills=3, purpose="source_selfplay"):
        if purpose != "source_selfplay" or world.name == "BIT_CELLULAR_AUTOMATA":
            raise ValueError("only permitted source self-play can promote a concrete skill")
        skill.validate(world.grammar)
        if len(self.snapshot()) >= max_skills or max_skills > 3:
            raise ValueError("source layer skill cap")
        upper = player.generator.b0+int("workspace" in player.diagnostics)
        if not 2 <= skill.expansion_cost(world.grammar.ops) <= player.generator.b0 or primitive_cost(skill, world.grammar.ops) > upper:
            raise ValueError("skill not extracted inside rooted source frontier")
        utility = source_metabolic_utility(skill, player, world, library_size=len(self.snapshot())+1, meter=meter)
        if utility["net_utility"] <= 0:
            return dict(accepted=False, utility=utility)
        key = digest(skill.key())
        if key in self._asts:
            raise ValueError("duplicate retained skill")
        self._asts[key] = skill
        self.journal.append("wave24_verified_ast_skill", dict(skill_id=key, ast=skill_wire(skill),
            purpose=purpose, source_probe_digest=digest(player.diagnostics["source_probe_inputs"]), utility=utility))
        return dict(accepted=True, utility=utility)

    def install_transfer(self, skill, grammar, lineage):
        """Install a source-derived proposal, never pretend target promotion."""
        skill.validate(grammar)
        if lineage.get("target_training_tasks") != 0 or not lineage.get("source_skill"):
            raise ValueError("zero-shot source lineage required")
        key = digest(skill.key())
        if key in self._asts:
            raise ValueError("duplicate transferred proposal")
        self._asts[key] = skill
        self.journal.append("wave24_verified_ast_skill", dict(skill_id=key, ast=skill_wire(skill),
            purpose="zero_shot_role_proposal", lineage=lineage, target_benefit_claimed=False))

    def promote(self, expr, pairs, *, gain_bound, alpha=.05):
        if len(pairs) < 2 or len({p.task_id for p in pairs}) != len(pairs):
            raise ValueError("independent nonduplicate shadow tasks required")
        if any(p.purpose != "training_shadow" for p in pairs):
            raise ValueError("target or assessment feedback cannot promote skills")
        if not 0 < alpha < 1 or gain_bound <= 0:
            raise ValueError("predeclared gain bound and alpha required")
        gains = [p.without_skill_work-p.with_skill_work for p in pairs]
        if any(p.without_skill_work < 0 or p.with_skill_work < 0 for p in pairs):
            raise ValueError("negative work")
        if any(abs(g) > gain_bound for g in gains):
            raise ValueError("declared gain bound violated")
        # Bounded paired Hoeffding LCB. No normal CI or pseudo task replication.
        lcb = sum(gains)/len(gains) - 2*gain_bound*math.sqrt(math.log(1/alpha)/(2*len(gains)))
        if lcb <= 0:
            return {"accepted": False, "lcb": lcb}
        key = digest(expr.key())
        if key in self._asts:
            raise ValueError("duplicate skill")
        self._asts[key] = expr
        self.journal.append("wave24_verified_ast_skill", dict(skill_id=key, ast=expr.key(),
                            shadow_digest=digest([p.__dict__ for p in pairs]), lcb=lcb))
        return {"accepted": True, "lcb": lcb}

    @staticmethod
    def recurring_subdags(programs):
        # Count at most once per source program; repeated nodes are not tasks.
        counts, asts = Counter(), {}
        for p in programs:
            seen = set()
            def walk(e):
                if e.children:
                    k = digest(e.key())
                    seen.add(k)
                    asts[k] = e
                for c in e.children:
                    walk(c)
            walk(p)
            counts.update(seen)
        return tuple(asts[k] for k in sorted(counts) if counts[k] >= 2)


class DualHorizonVerifier:
    """Certificate A: no skill changes primitive horizon. B: explicit MDL.

    A 1-in-5 WORK-unit scheduler preserves the exact baseline iterator across
    speculative turns. Four baseline units precede each speculative unit, so
    speculative work cannot exceed 20% of shared search work. Empty speculative
    shares revert to the baseline. Setup/training are additional costs.
    """
    def __init__(self, b0, mdl_bound, *, ratchet=False, roles=None, twin_mutations=16, workspace_hops=0, workspace_cap_multiplier=2):
        if b0 < 1 or mdl_bound < 1:
            raise ValueError("positive horizons")
        self.b0, self.mdl_bound = b0, mdl_bound
        self.ratchet, self.roles, self.twin_mutations = ratchet, roles or {}, twin_mutations
        if type(workspace_hops) is not int or not 0 <= workspace_hops <= 3 or workspace_hops and not ratchet:
            raise ValueError("explicit capped ratcheted workspace mode required")
        self.workspace_hops = workspace_hops
        if workspace_cap_multiplier not in (2, 3):
            raise ValueError("explicit primitive cap multiplier required")
        self.workspace_cap_multiplier = workspace_cap_multiplier

    def fixed(self, grammar, task, skills, meter, *, scorer=None, trace=None):
        skills = tuple(skills)
        for skill in skills:
            if isinstance(skill, ParametricSkillMacro):
                skill.validate(grammar)
            else:
                validate_program(skill, grammar, macros=skills)
        if any(primitive_cost(s, grammar.ops) > self.b0 for s in skills):
            raise ValueError("skill expansion exceeds fixed primitive bound")
        inputs = [x for x, _ in task.public_io] + [task.query]
        baseline = ExactEnumerator(grammar, inputs, self.b0, meter=meter)
        # Speculative ordering cannot change baseline completeness or bounds.
        goal = GoalCheck([y for _, y in task.public_io], task.output_sort)
        started_work = meter.total
        def result(complete):
            value = goal.result(complete)
            if trace is not None and value.status.startswith("UNIQUE_QUERY"):
                trace["work_to_uniqueness"] = meter.total-started_work
            return value
        def observe(expr, outputs):
            split = goal.observe(expr, outputs)
            if trace is not None:
                if goal.first is not None and trace.get("work_to_g1") is None:
                    trace["work_to_g1"] = meter.total-started_work
                if split:
                    trace["work_to_g2"] = meter.total-started_work
            return split
        def skill_events():
            ranked = []
            class Prepaid:
                def charge(self, *args):
                    pass
            # Exact B0 closure is still covered by the resumable baseline.
            # Parametric speculation applies templates to typed intermediate
            # expressions, not only to the original x.
            proposals = []
            for skill in skills:
                if isinstance(skill, ParametricSkillMacro):
                    remaining = self.b0-skill.expansion_cost(grammar.ops)
                    from nexus.wave24_quotient_core import syntax_programs
                    # Enumeration and construction are speculative work too.
                    for argument in syntax_programs(grammar, remaining):
                        meter.charge("speculative_work_units")
                        yield None
                        if skill.input_sorts == (argument.sort,):
                            proposal = skill.call(argument)
                            if primitive_cost(proposal, grammar.ops) <= self.b0:
                                proposals.append(proposal)
                else:
                    proposals.append(skill)
            for skill in proposals:
                if scorer is None:
                    scores = (0., 0.)
                else:
                    if scorer.feature_count == 10:
                        public_outputs = []
                        for x, _ in task.public_io:
                            public_outputs.append((yield from eval_expr_steps(skill, x, grammar.ops, meter,
                                                                               "speculative_work_units")))
                        features = behavioral_execution_features(skill, grammar, public_outputs, [y for _, y in task.public_io])
                    else:
                        features = execution_features(skill, grammar)
                    # Both ridge heads + structural feature traversal are in
                    # the speculative allocation, not free ordering overhead.
                    for _ in range(2*scorer.feature_count+int(features[2])+len(task.public_io)):
                        meter.charge("speculative_work_units")
                        yield None
                    scores = scorer.predict(features, meter=Prepaid())
                ranked.append((skill, scores))
            while ranked:
                head = 0 if goal.first is None else 1
                index = min(range(len(ranked)), key=lambda i: (ranked[i][1][head], repr(ranked[i][0].key())))
                skill, _ = ranked.pop(index)
                outputs = []
                for x in inputs:
                    outputs.append((yield from eval_expr_steps(skill, x, grammar.ops, meter,
                                                               "speculative_work_units")))
                primitive = expanded_skill_call(skill) if skill.kind == "skill_call" else skill
                yield (primitive, tuple(outputs), primitive_cost(primitive, grammar.ops))
        speculative = iter(skill_events())
        exact = iter(baseline.work_events())
        spec_done, turn = False, 0
        try:
            while True:
                is_spec = turn % 5 == 4 and not spec_done
                stream = speculative if is_spec else exact
                while True:
                    try:
                        item = next(stream)
                    except StopIteration:
                        if not is_spec:
                            return result(True)
                        spec_done = True
                        break
                    if item is None:
                        break  # precisely one work unit; keep stream resumable
                    expr, outputs, _ = item
                    if observe(expr, outputs):
                        return result(False)
                turn += 1
        except WorkExhausted:
            return result(False)

    def evolved(self, grammar, task, library, meter, *, trace=None, scorer=None):
        skills = library.snapshot()
        if self.workspace_hops:
            return StigmergicWorkspaceEngine(self.b0, max_hops=self.workspace_hops, roles=self.roles,
                skills=skills, scorer=scorer, meter=meter, twin_mutations=self.twin_mutations,
                cap_multiplier=self.workspace_cap_multiplier).run(grammar, task, trace=trace)
        if self.ratchet:
            def priority(expr, public_outputs, cost_meter):
                features = behavioral_execution_features(expr, grammar, public_outputs, [y for _, y in task.public_io], cost_meter)
                if scorer is not None and scorer.models is not None:
                    return scorer.predict(features, meter=cost_meter)
                return (features[-1], features[-3], features[-2])
            return solve(grammar, task.public_io, task.query, task.output_sort,
                self.b0, meter=meter, macros=skills, evolved=True, primitive_cap=2*self.b0,
                priority=priority, proposal_controller=BehavioralDiffController(self.roles),
                twin_verifier=PopperianTwinVerifier(self.roles, max_mutations=self.twin_mutations), trace=trace)
        result = solve(grammar, task.public_io, task.query, task.output_sort,
                       self.mdl_bound, meter=meter, macros=skills, mdl=True, trace=trace)
        return result

    def audit_deep(self, grammar, task, evolved_result, meter, *, library=None):
        # Public observations alone are the synthesis task. A long teacher is
        # insufficient if ANY short program fits them, regardless of its query.
        shallow = solve(grammar, task.public_io, task.query, task.output_sort, self.b0,
                        quotient=False, meter=meter)
        definitive = evolved_result.status in ("AMBIGUOUS_WITNESS_FOUND", "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE")
        certified = False
        if definitive:
            certified = verify_certificate(grammar, task.public_io, task.query, task.output_sort,
                                           self.mdl_bound, evolved_result, meter=meter,
                                           macros=() if library is None else library.snapshot(), mdl=True)
        return {"static": shallow, "evolved": evolved_result,
                "horizon_expansion_demonstrated": shallow.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
                    and certified and bool(evolved_result.witnesses)
                    and all(primitive_cost(e, grammar.ops) > self.b0 for e in evolved_result.witnesses)}


def source_shadow_pairs(world, tasks, skill, *, b0, meter):
    """Independent source-only paired work measurements for skill hygiene.

    Caller must supply disjoint source-shadow tasks; generated target/final
    tasks have no accepted purpose here. Duplicate support fingerprints fail.
    """
    pairs, seen = [], set()
    verifier = DualHorizonVerifier(b0, b0)
    for record in tasks:
        if record["purpose"] != "training_shadow" or record["world"] != world.name:
            raise ValueError("source-only matched shadow tasks required")
        task = record["task"]
        task_id = digest((world.name, [(freeze(x), freeze(y)) for x, y in task.public_io], freeze(task.query)))
        if task_id in seen:
            raise ValueError("duplicate shadow support/query task")
        seen.add(task_id)
        before = meter.total
        baseline = verifier.fixed(world.grammar, task, (), MeterView(meter, "training_work_units"))
        baseline_work = meter.total-before
        before = meter.total
        with_skill = verifier.fixed(world.grammar, task, (skill,), MeterView(meter, "training_work_units"))
        skill_work = meter.total-before
        if baseline.status != with_skill.status or "UNKNOWN" in baseline.status:
            raise ValueError("shadow run incomplete or certificate mismatch")
        pairs.append(ShadowPair(task_id, baseline_work, skill_work))
    return tuple(pairs)


@dataclass(frozen=True)
class FrozenSourceState:
    """Boundary object. Freezing does not freeze a global live agent."""
    skill_keys: tuple
    scorer_fingerprint: str
    source_worlds: tuple

    @classmethod
    def capture(cls, library, scorer, worlds):
        names = tuple(w.name for w in worlds)
        if "BIT_CELLULAR_AUTOMATA" in names:
            raise ValueError("fifth world must remain source-unseen")
        return cls(tuple(s.key() for s in library.snapshot()), scorer.fingerprint(), names)

    def verify(self, library, scorer):
        if self.skill_keys != tuple(s.key() for s in library.snapshot()) or self.scorer_fingerprint != scorer.fingerprint():
            raise ValueError("frozen source state changed during target evaluation")
        return True


def stratified_procedural_bank(worlds, *, seed, b0, per_tier, max_attempts, meter):
    """Deterministic locked algorithm, no hand-authored post-freeze task list.

    Deep cases require exhaustive proof that no B0 program fits the public
    evidence. Alias rejection is a declared tier-definition check, never
    selection by proposed-method success. Empty strata are INCOMPLETE, not a
    reason to increase a bound, change a seed, or retry an assessment.
    """
    if type(per_tier) is not int or not 1 <= per_tier <= 100 or type(max_attempts) is not int or not 1 <= max_attempts <= 1000:
        raise ValueError("bounded task and attempt counts required")
    generator = SeededProceduralTaskGenerator(seed, b0, public_count=5)
    bank, rejections, seen = [], Counter(), set()
    for world in worlds:
        counts = Counter()
        for _ in range(max_attempts):
            if counts["Tier-1"] == counts["Tier-2"] == per_tier:
                break
            task = generator.sample(world, meter)
            if counts[task.tier] >= per_tier:
                rejections["filled_tier"] += 1
                continue
            view = task.public_view
            key = digest((world.name, [(freeze(x), freeze(y)) for x, y in view.public_io], freeze(view.query)))
            if key in seen:
                rejections["duplicate"] += 1
                continue
            if task.tier == "Tier-2":
                shallow = solve(world.grammar, view.public_io, view.query, view.output_sort,
                                b0, quotient=False, meter=MeterView(meter, "generator_work_units"))
                if shallow.status != "NO_PROGRAM_IN_BOUNDED_GRAMMAR":
                    rejections["shallow_alias_or_incomplete"] += 1
                    continue
            seen.add(key)
            counts[task.tier] += 1
            bank.append(task)
    expected = len(worlds)*2*per_tier
    return {"status": "COMPLETE" if len(bank) == expected else "INCOMPLETE",
            "expected": expected, "tasks": tuple(bank), "rejections": dict(rejections)}


METHODS = ("exhaustive_primitive_baseline", "stage2_exact_quotient_baseline",
           "stage3_quotient_plus_auto_laws", "stage4_zero_data_selfplay_fixed_bound",
           "stage5_self_evolving_dual_horizon")


def run_method(method, world, task, *, b0, meter, laws=None, library=None, scorer=None, mdl_bound=None, trace=None,
               ratchet=False, roles=None, twin_mutations=16, workspace_hops=0, workspace_cap_multiplier=2):
    """No task bank loading, training, seed generation or execution on import."""
    if method not in METHODS:
        raise ValueError("unknown ablation")
    if method == METHODS[0]:
        return solve(world.grammar, task.public_io, task.query, task.output_sort, b0,
                     quotient=False, meter=meter, trace=trace)
    if method == METHODS[1]:
        return solve(world.grammar, task.public_io, task.query, task.output_sort, b0, meter=meter, trace=trace)
    if method == METHODS[2]:
        if laws is None:
            raise ValueError("metered setup laws required")
        return solve(world.grammar, task.public_io, task.query, task.output_sort, b0, meter=meter, laws=laws, trace=trace)
    if library is None:
        raise ValueError("explicit frozen source library required")
    verifier = DualHorizonVerifier(b0, mdl_bound or b0, ratchet=ratchet, roles=roles, twin_mutations=twin_mutations,
                                  workspace_hops=workspace_hops, workspace_cap_multiplier=workspace_cap_multiplier)
    if method == METHODS[3]:
        return verifier.fixed(world.grammar, task, library.snapshot(), meter, scorer=scorer, trace=trace)
    return verifier.evolved(world.grammar, task, library, meter, trace=trace, scorer=scorer)


def horizon_break_even(setup, training, proposed, baseline):
    if len(proposed) != len(baseline) or not proposed:
        raise ValueError("paired nonempty Horizon-N grid required")
    values = [setup, training, *proposed, *baseline]
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError("nonnegative metered integer costs required")
    first = None
    running_p, running_b = setup+training, 0
    for n, (p, b) in enumerate(zip(proposed, baseline), 1):
        running_p += p
        running_b += b
        if first is None and running_p < running_b:
            first = n
    return dict(N=len(proposed), proposed_total=running_p, baseline_total=running_b,
                strict_break_even=running_p < running_b, first_observed_break_even=first)


class OpenToolboxLearningEngine:
    """Bounded ingestion -> source mapping -> solve -> certify -> consolidate.

    Reuses the exact core, source player, ridge, and E1 journal. No import of
    environments, live model runtime or arbitrary generated code is involved.
    In frozen mode neither a solved target nor its outcome can update memory.
    Roles are proposals; UNIQUE always means the declared bounded grammar.
    """
    def __init__(self, *, b0=3, meter=None, frozen=False, max_source_cycles=4):
        if not 2 <= b0 <= 6 or not 1 <= max_source_cycles <= 4:
            raise ValueError("bounded engine horizon and cycle count")
        self.b0, self.meter, self.frozen = b0, meter if meter is not None else WorkMeter(), frozen
        self.max_source_cycles, self.source_cycles = max_source_cycles, 0
        self.toolbox = None
        self.library, self.critic = JournalSkillView(), DerivationOutcomeCritic(feature_count=10)
        self.functors = ()
        self.history = Journal()

    def enter_toolbox(self, callables, seed_inputs, *, conditionals=False, constants=()):
        if self.toolbox is not None:
            raise ValueError("create a separate bounded engine for another toolbox")
        self.toolbox = OpenPythonToolboxAdapter().ingest(callables, seed_inputs, meter=self.meter,
                                                       conditionals=conditionals, constants=constants)
        self.history.append("wave24_toolbox_entered", dict(operators=[(op.name, op.inputs, op.output) for op in self.toolbox.grammar.operators],
            probe_digest=digest(self.toolbox.probe_log), frozen=self.frozen))
        return self.toolbox

    def learn_source(self, *, seed=0, task_limit=6):
        if self.frozen:
            raise ValueError("frozen target engine cannot train on target tasks")
        if self.toolbox is None or self.source_cycles >= self.max_source_cycles or not 1 <= task_limit <= 6:
            raise ValueError("toolbox and remaining bounded source cycle required")
        self.source_cycles += 1  # failed attempts consume the cycle too
        g = self.toolbox.grammar
        if len(self.toolbox.seed_inputs) < 3:
            raise ValueError("source mining requires separate public/query input probes")
        world = World("OPEN_SOURCE", g, g.input_sort, self.toolbox.seed_inputs, {})
        player = ZeroDataFrontierSelfPlay(seed, self.b0, public_count=2, behavioral_features=True)
        player.wake(world, attempts=task_limit, meter=self.meter)
        if player.accepted:
            player.augment_workspace_frontier(world, meter=self.meter, roles=self.toolbox.roles)
        if player.training_rows:
            self.critic.fit(player.training_rows, meter=self.meter)
        for retained in self.library.snapshot():
            utility = source_metabolic_utility(retained, player, world,
                library_size=len(self.library.snapshot()), meter=self.meter)
            self.library.observe_source_utility(retained, source_net_utility=utility["net_utility"])
        chosen, portfolio = select_ratcheted_source_skills(player, world, max_skills=3, meter=self.meter)
        for skill in chosen:
            if digest(skill.key()) not in self.library._asts and len(self.library.snapshot()) < 3:
                self.library.promote_ratcheted(skill, player, world, meter=self.meter)
        schemas = {}
        for skill in self.library.snapshot():
            for functor in AlgebraicRoleFunctor.lift(skill, self.toolbox.roles):
                schemas[functor.key()] = functor
        self.functors = tuple(schemas[k] for k in sorted(schemas))
        report = dict(source_tasks=len(player.accepted), training_rows=len(player.training_rows),
                      skills=len(self.library.snapshot()), functors=len(self.functors), portfolio=portfolio,
                      role_probes_only=False, no_external_task_query_answer_used=True)
        self.history.append("wave24_source_consolidation", report)
        return report

    def solve_and_learn(self, public_io, query, *, output_sort=None):
        """Source-only consolidation of a certified derivation, not a reward.

        The generated source curriculum executes the program on toolbox seed
        inputs. It does NOT treat the program's answer to an unobserved external
        query as ground-truth feedback. Frozen evaluation must use solve_public.
        """
        if self.frozen or self.source_cycles >= self.max_source_cycles:
            raise ValueError("source consolidation is forbidden or exhausted")
        self.source_cycles += 1  # failed/ambiguous attempts consume their cycle too
        result = self.solve_public(public_io, query, output_sort=output_sort)
        if result.status != "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE":
            return result, dict(consolidated=False, reason="no complete unique bounded derivation")
        g, inputs = self.toolbox.grammar, self.toolbox.seed_inputs
        view = MeterView(self.meter, "training_work_units")
        def expand(e):
            view.charge()
            if e.kind == "skill_call":
                return expand(expanded_skill_call(e, view))
            return Expr(e.kind, e.sort, e.value, tuple(expand(c) for c in e.children))
        program = expand(result.witnesses[0])
        outputs = tuple(eval_expr(program, x, g.ops, view) for x in inputs)
        task = GeneratedTask("OPEN_SOURCE", program, PublicTask(tuple(zip(inputs[:-1], outputs[:-1])), inputs[-1], program.sort),
                             outputs[-1], primitive_cost(program, g.ops), "source_derivation", None)
        world = World("OPEN_SOURCE", g, program.sort, inputs, {})
        player = ZeroDataFrontierSelfPlay(0, self.b0, behavioral_features=True)
        player.accepted = [task]
        player.derivations = list(ExactEnumerator(g, inputs, self.b0, meter=view))
        player.diagnostics = dict(source_probe_inputs=[freeze(x) for x in inputs])
        ancestors = {n.key() for n in ast_nodes(program)}
        groups = {}
        for expr, ys, cost in player.derivations:
            groups.setdefault((expr.sort, tuple(freeze(v) for v in ys[:-1])), set()).add(freeze(ys[-1]))
        rows = [dict(features=behavioral_execution_features(expr, g, ys[:-1], outputs[:-1], view),
                     J_fit=int(expr.key() in ancestors), J_disagree=int(len(groups[(expr.sort, tuple(freeze(v) for v in ys[:-1]))]) > 1),
                     label_semantics="source_derivation_behavioral_v3", purpose="training")
                for expr, ys, cost in player.derivations][:128]
        if rows:
            self.critic.fit(rows, meter=self.meter)
        skills, _ = select_ratcheted_source_skills(player, world, max_skills=3, meter=self.meter)
        for skill in skills:
            if digest(skill.key()) not in self.library._asts and len(self.library.snapshot()) < 3:
                self.library.promote_ratcheted(skill, player, world, meter=self.meter)
        schemas = {f.key(): f for s in self.library.snapshot() for f in AlgebraicRoleFunctor.lift(s, self.toolbox.roles)}
        self.functors = tuple(schemas[k] for k in sorted(schemas))
        report = dict(consolidated=True, source_rows=len(rows), retained_skills=len(self.library.snapshot()),
                      external_query_answer_used=False, predicted_reward_used_as_observed=False,
                      claim="program-defined source derivation; not validated external-task generalization")
        self.history.append("wave24_source_solved_program", dict(report, public_digest=digest(public_io)))
        return result, report

    def receive_source_functors(self, functors):
        if self.toolbox is None or self.library.snapshot():
            raise ValueError("empty entered target toolbox required")
        skills, lineage = zero_shot_role_transfer(functors, self.toolbox.grammar, self.toolbox.roles,
                                                self.toolbox.seed_inputs, meter=self.meter)
        for skill, record in zip(skills, lineage):
            self.library.install_transfer(skill, self.toolbox.grammar, record)
        self.history.append("wave24_zero_shot_transfer", dict(lineage=lineage, target_training_tasks=0))
        return dict(transferred_skills=len(skills), target_training_tasks=0)

    def solve_public(self, public_io, query, *, output_sort=None):
        if self.toolbox is None:
            raise ValueError("enter a toolbox first")
        before = (tuple(s.key() for s in self.library.snapshot()), self.critic.fingerprint())
        g = self.toolbox.grammar
        task = PublicTask(tuple(public_io), query, output_sort or OpenPythonToolboxAdapter.sort_of(public_io[0][1]))
        trace = {}
        result = DualHorizonVerifier(self.b0, self.b0, ratchet=True, roles=self.toolbox.roles, workspace_hops=3).evolved(
            g, task, self.library, self.meter, scorer=self.critic if self.critic.models is not None else None, trace=trace)
        if result.status != "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED":
            verify_workspace_certificate(g, task, result, trace["workspace"],
                                         meter=self.meter, skills=self.library.snapshot())
        after = (tuple(s.key() for s in self.library.snapshot()), self.critic.fingerprint())
        if before != after:
            raise ValueError("solving silently changed the frozen learner/library")
        self.history.append("wave24_public_solve", dict(status=result.status, public_digest=digest(task.public_io),
            trace=trace, complete=result.complete, bounded_claim_only=True, consolidated_target_feedback=False))
        return result


class UniversalPhenotypeCompass(PhenotypeAffinityCompass):
    """The existing metered cross-type compass; no new distance or oracle."""


class SymptomJobCritic(DerivationOutcomeCritic):
    """Ten features: bias, four public symptoms, five empirical job indicators."""
    def __init__(self, ridge=1., *, resource_host=None):
        super().__init__(ridge, feature_count=10, resource_host=resource_host)

    def fit(self, rows, *, meter, purpose="training"):
        if purpose != "training" or not rows or any(r.get("label_semantics") != "source_symptom_job_v1" for r in rows):
            raise ValueError("actual source symptom/action feedback required")
        converted = [dict(r, label_semantics="source_derivation_behavioral_v3") for r in rows]
        super().fit(converted, meter=meter, purpose=purpose)
        self.source_digest = digest(rows)
        return self

    def fingerprint(self):
        return digest(("symptom_job_critic_v1", super().fingerprint()))


class HomeostaticMetabolicController:
    """Conserved 100-ATP pool over at most six active shortcuts."""

    K_MAX = 6
    TOTAL = 100.0

    def __init__(self):
        self.delta_w = {}
        self.beta = 1.0
        self.rho = 0.20
        self.freeze_events = 0
        self.drift_events = 0
        self.evicted = []
        self.shadow_rejected = 0
        self.history = []
        self.atp = self._default_atp()

    @staticmethod
    def _default_atp():
        raw = [30.0, 20.0, 15.0, 15.0, 12.0, 8.0]
        return {f"slot_{i}": v for i, v in enumerate(raw)}

    def observe(self, skill_key, delta_w):
        key = str(skill_key)
        self.delta_w[key] = self.delta_w.get(key, 0.0)+float(delta_w)
        if self.delta_w[key] < 0:
            self.evict(key, reason="negative_counterfactual_utility")
        else:
            self.rebalance()
        return self.snapshot()

    def evict(self, skill_key, *, reason="drift"):
        key = str(skill_key)
        self.delta_w.pop(key, None)
        self.evicted.append(dict(skill=key, reason=reason))
        if reason == "negative_counterfactual_utility":
            self.drift_events += 0  # eviction prevents a drift event
        self.rebalance()

    def reject_shadow(self):
        self.shadow_rejected += 1

    def rebalance(self):
        ranked = sorted(((w, k) for k, w in self.delta_w.items() if w >= 0), reverse=True)[:self.K_MAX]
        masses = []
        if ranked:
            mx = max(w for w, _ in ranked) or 1.0
            for w, key in ranked:
                masses.append((key, math.exp(self.beta*(w/mx))))
        while len(masses) < self.K_MAX:
            masses.append((f"explore_{len(masses)}", math.exp(-self.beta)))
        total = sum(m for _, m in masses) or 1.0
        atp = {k: self.TOTAL*(m/total) for k, m in masses}
        entropy = self._normalized_entropy(atp)
        if entropy < 0.25:
            self.beta = max(0.15, self.beta*0.7)
            self.rho = max(0.15, self.rho)
            atp, entropy = self._retune(masses)
        elif entropy > 0.98:
            self.beta = min(4.0, self.beta*1.15)
            atp, entropy = self._retune(masses)
        if abs(sum(atp.values())-self.TOTAL) > 1e-9:
            scale = self.TOTAL/sum(atp.values())
            atp = {k: v*scale for k, v in atp.items()}
        if not 0.25 <= self._normalized_entropy(atp) <= 0.98:
            atp = self._default_atp()
        self.atp = atp
        snap = self.snapshot()
        self.history.append(snap)
        return snap

    def _retune(self, masses):
        total = sum(m for _, m in masses) or 1.0
        atp = {k: self.TOTAL*(m/total) for k, m in masses}
        return atp, self._normalized_entropy(atp)

    @staticmethod
    def _normalized_entropy(atp):
        values = [max(v, 0.0) for v in atp.values()]
        total = sum(values) or 1.0
        probs = [v/total for v in values if v > 0]
        if len(probs) <= 1:
            return 0.0
        h = -sum(p*math.log(p) for p in probs)
        return h/math.log(len(probs))

    def snapshot(self):
        entropy = self._normalized_entropy(self.atp)
        return dict(atp_total_sum=sum(self.atp.values()), normalized_atp_entropy=entropy,
            active_shortcut_count=sum(1 for k in self.atp if not str(k).startswith("explore") and not str(k).startswith("slot_")),
            evicted_poisoned_shortcuts=len(self.evicted), shadow_rejected_weight_updates=self.shadow_rejected,
            metabolic_freeze_events=self.freeze_events, metabolic_drift_events=self.drift_events,
            beta=self.beta, rho=self.rho)

    def assert_stable(self):
        snap = self.snapshot()
        if abs(snap["atp_total_sum"]-self.TOTAL) >= 1e-6:
            raise ValueError("ATP conservation violated")
        if not 0.25 <= snap["normalized_atp_entropy"] <= 0.98:
            raise ValueError("ATP entropy left the homeostatic band")
        return snap


class ShadowRollbackGuard:
    """Commit a critic update only when it strictly reduces shadow rank/work."""

    def __init__(self):
        self.traces = []

    def record(self, features, work):
        self.traces.append(dict(features=tuple(features), work=int(work)))
        self.traces = self.traces[-32:]

    def shadow_work(self, critic, meter):
        if critic.models is None or not self.traces:
            return 10**9
        total = 0
        for row in self.traces:
            pred = critic.predict(row["features"], meter=meter)
            total += int(round(-pred[0]*1000))+int(round(-pred[1]*1000))
        return total

    def accept(self, before_critic, after_critic, meter):
        if not self.traces or before_critic.models is None:
            return True
        return self.shadow_work(after_critic, meter) < self.shadow_work(before_critic, meter)


class SymptomToActionDoctor:
    """Learns a source-only symptom/job priority, not a rule for certification."""
    def __init__(self, critic=None):
        self.critic = critic if critic is not None else SymptomJobCritic()
        self.rows = []
        self.guard = ShadowRollbackGuard()
        self.last_agenda = ()

    @staticmethod
    def diagnose(sigma_pub_cand, Y_pub, *, meter=None):
        if meter is not None:
            meter.charge("task_boundary_doctor_work_units", 1)
        diff = BehavioralDiffController.classify_error_shape(sigma_pub_cand, Y_pub, meter=None)
        partial, excess, residual, dead = diff.features
        return (excess, partial, residual, dead, diff.preferred_roles)

    def features(self, outputs, target, jobs, *, meter):
        symptoms = self.diagnose(outputs, target, meter=None)[:4]
        return (1., *symptoms, *(float(job in jobs) for job in JOB_TAGS))

    def rank_agenda(self, grammar, roles, X_pub, Y_pub, *, meter):
        diagnosis = self.diagnose(X_pub, Y_pub, meter=meter)
        preferred = set(diagnosis[4])
        scored = []
        for op in grammar.operators:
            role = roles.get(op.name)
            tags = universal_job_tags(role) if role is not None else ()
            hit = 0 if role is not None and (role.primary in preferred or role.shift in preferred) else 1
            scored.append((hit, op.name))
        self.last_agenda = tuple(name for _, name in sorted(scored))
        return self.last_agenda

    def learn_source(self, grammar, task, roles, *, meter, frozen=False, max_rows=16):
        if frozen:
            raise ValueError("target symptoms cannot train the doctor")
        inputs = tuple(x for x, _ in task.public_io)+(task.query,)
        entries = list(ExactEnumerator(grammar, inputs, 2, meter=MeterView(meter, "training_work_units"),
                                       inner_heuristics=False))
        groups = {}
        for e, ys, _ in entries:
            groups.setdefault((e.sort, tuple(freeze(y) for y in ys[:-1])), set()).add(freeze(ys[-1]))
        target = tuple(y for _, y in task.public_io)
        new = []
        for e, ys, _ in entries:
            if e.sort != task.output_sort:
                continue
            before = sum(abs(structural_mass(a)-structural_mass(b)) for a, b in zip(ys[:-1], target))
            for op in grammar.operators:
                if op.inputs != (e.sort,) or op.output != task.output_sort:
                    continue
                outputs = tuple(op.call((y,), meter, "training_work_units") for y in ys)
                after = sum(abs(structural_mass(a)-structural_mass(b)) for a, b in zip(outputs[:-1], target))
                jobs = universal_job_tags(roles[op.name])
                feats = self.features(ys[:-1], target, jobs, meter=meter)
                new.append(dict(features=feats,
                    J_fit=int(after < before), J_disagree=int(len(groups[(e.sort, tuple(freeze(y) for y in ys[:-1]))]) > 1),
                    purpose="training", label_semantics="source_symptom_job_v1"))
                self.guard.record(feats, after)
                if len(new) == max_rows:
                    break
            if len(new) == max_rows:
                break
        self.rows = (self.rows+new)[-128:]
        committed = False
        if new:
            from copy import deepcopy
            before_models = None if self.critic.models is None else deepcopy(self.critic.models)
            before = SymptomJobCritic(self.critic.ridge, resource_host=getattr(self.critic, "resource_host", None))
            before.models = before_models
            self.critic.fit(self.rows, meter=meter)
            if not self.guard.accept(before, self.critic, MeterView(meter, "training_work_units")):
                self.critic.models = before_models
                if getattr(self, "metabolic", None) is not None:
                    self.metabolic.reject_shadow()
            else:
                committed = True
        return dict(new_rows=len(new), retained_rows=len(self.rows), feedback_sha256=digest(self.rows),
                    actual_public_operator_feedback=True, target_training_rows=0,
                    weight_update_committed=committed)


class ScratchpadWorkspaceEngine(StigmergicWorkspaceEngine):
    """Lyapunov variable-depth workspace; hop-1 exact spine before speculation."""
    def __init__(self, b0=3, *, doctor=None, speculative_share=.20, canonical_only=False,
                 max_hops=16, max_task_work_budget=1_000_000, use_noether=None, spine_first=False, **kwargs):
        if not .15 <= speculative_share <= .35:
            raise ValueError("bounded stream exploration share required")
        kwargs.setdefault("max_hops", max_hops)
        super().__init__(b0, cap_multiplier=3, **kwargs)
        self.doctor, self.speculative_share = doctor, speculative_share
        self.canonical_only = bool(canonical_only)
        self.max_task_work_budget = int(max_task_work_budget)
        self.compass = UniversalPhenotypeCompass(self.meter)
        self.use_noether = (not self.canonical_only) if use_noether is None else bool(use_noether)
        self.noether = NoetherConservationGate() if self.use_noether else None
        self.phase_b = False
        self.spine_first = bool(spine_first)
        self.spine_hop = False

    def outer_role(self, pure):
        role = self.roles.get(pure.value) if pure.kind == "apply" else None
        tags = universal_job_tags(role) if role is not None else ()
        return (tags[0], "EMPIRICAL") if tags else ("UNCLASSIFIED", "ANY")

    def rank_features(self, expr, grammar, outputs, target, meter):
        return super().rank_features(expr, grammar, outputs, target, meter)

    def _choose(self, grammar, entries, workspace, inputs, target):
        classes = self._classes(grammar, entries)
        old_keys = {self.public_key(e.sort, tuple(eval_expr(e, x, grammar.ops, self.meter,
                    "workspace_index_work_units") for x in inputs)) for e in workspace}
        x_key = self.public_key(grammar.input_sort, inputs)
        groups = {}
        for key, row in classes.items():
            _, pure, outputs, hop_cost = row
            public = self.public_key(pure.sort, outputs)
            if 2 <= hop_cost <= self.b0 and len(set(public[1])) > 1 and public not in old_keys | {x_key}:
                groups.setdefault(public, []).append(row)
        candidates = []
        for key, variants in groups.items():
            representative = min(variants, key=lambda r: r[0])
            pure, ys = representative[1:3]
            role_key = self.outer_role(pure)
            deficit = sum(abs(structural_mass(a)-structural_mass(b)) for a, b in zip(ys[:-1], target))
            candidates.append(dict(key=key, outputs=ys, role=role_key,
                atomic_deficit=deficit, variants=variants))
        candidates.sort(key=lambda r: (r["atomic_deficit"], repr(r["key"])))
        frontier = candidates[:12]
        for row in frontier:
            if self.phase_b or self.canonical_only or self.spine_hop:
                row["distance"] = float(row["atomic_deficit"])
            else:
                row["distance"] = self.compass.phenotype_distance(row["outputs"][:-1], target)
        for row in candidates[12:]:
            row["distance"] = float(row["atomic_deficit"])
        # Lyapunov exploit is atomic deficit; compass only reorders the rest of the top-12.
        candidates.sort(key=lambda r: (r["atomic_deficit"], r["distance"], repr(r["key"])))
        selected = []
        if candidates:
            selected.append(("EXPLOIT", candidates[0]))
            bridges = [r for r in candidates[1:] if r["role"] != candidates[0]["role"]]
            if bridges:
                selected.append(("ROLE_BRIDGE", bridges[0]))
            remaining = [r for r in candidates if r["key"] not in {s["key"] for _, s in selected}]
            known = [tuple(inputs[:-1])] + [tuple(eval_expr(e, x, grammar.ops, self.meter,
                "workspace_index_work_units") for x in inputs[:-1]) for e in workspace]
            for r in remaining:
                r["novelty"] = min(sum(abs(structural_mass(a)-structural_mass(b))
                                       for a, b in zip(r["outputs"][:-1], k)) for k in known)
            if remaining:
                chosen = min(remaining, key=lambda r: (-r["novelty"], -int(len(r["variants"]) > 1), repr(r["key"])))
                selected.append(("NOVELTY", chosen))
        selected = self.rebalance_portfolio(selected, candidates, workspace, inputs, target)
        keys = old_keys | {r["key"] for _, r in selected}
        carried = {e.key(): e for e in workspace}
        for _, pure, outputs, _ in classes.values():
            if self.public_key(pure.sort, outputs) in keys:
                carried[pure.key()] = pure
        best = {}
        for pure in carried.values():
            ys = tuple(eval_expr(pure, x, grammar.ops, self.meter, "workspace_commit_work_units") for x in inputs)
            key = (pure.sort, tuple(freeze(y) for y in ys))
            order = (primitive_cost(pure, grammar.ops), repr(pure.key()))
            if key not in best or order < best[key][0]:
                best[key] = (order, pure)
        next_workspace = tuple(best[k][1] for k in sorted(best, key=repr))
        audit = []
        for slot, r in selected:
            variants = sorted((row for key, row in classes.items() if key[0] == r["key"][0]
                               and key[1][:-1] == r["key"][1]), key=lambda row: row[0])
            audit.append(dict(slot=slot, public_signature=r["key"], role=r["role"],
                phenotype_distance=r["distance"], novelty=r.get("novelty"),
                outputs=r["outputs"], atomic_deficit=r.get("atomic_deficit"),
                canonical_ast=expression_wire(variants[0][1]),
                query_twin_ast=expression_wire(variants[1][1]) if len(variants) > 1 else None,
                query_variant_count=len(variants)))
        return next_workspace, audit, classes

    def rebalance_portfolio(self, selected, candidates, workspace, inputs, target):
        if self.speculative_share < .30 or len(candidates) <= len(selected):
            return selected
        chosen = {r["key"] for _, r in selected}
        remaining = [r for r in candidates if r["key"] not in chosen]
        known = [tuple(inputs[:-1])]+[tuple(eval_expr(e, x, self._grammar.ops, self.meter,
                   "workspace_policy_work_units") for x in inputs[:-1]) for e in workspace]
        for r in remaining:
            r["novelty"] = min(abs(structural_mass(r["outputs"][:-1])-structural_mass(w)) if False else
                               sum(abs(structural_mass(a)-structural_mass(b)) for a,b in zip(r["outputs"][:-1], w))
                               for w in known)
        alternative = min(remaining, key=lambda r: (-r["novelty"], repr(r["key"])))
        kept = [(s, r) for s, r in selected if s != "EXPLOIT"]
        return (kept+[("NOVELTY_EXPLORATORY", alternative)])[:3]

    def _state_key(self, outputs, role):
        masses = tuple(structural_mass(v) for v in outputs)
        loci = tuple(locus_mask(v) for v in outputs)
        return (role[0] if role else "UNCLASSIFIED", masses, loci)

    def run(self, grammar, task, *, trace=None, explore=False):
        self._grammar = grammar
        inputs = tuple(x for x, _ in task.public_io)+(task.query,)
        target, workspace, hops = tuple(y for _, y in task.public_io), (), []
        started = self.meter.total
        X_pub = tuple(x for x, _ in task.public_io)
        domain = tuple(x for x, _ in task.public_io)+(task.query,)
        if self.noether is not None:
            self.noether.fingerprint_operators(grammar.operators, domain, meter=self.meter)
        if self.doctor is not None and not self.canonical_only and not self.spine_first:
            self.doctor.rank_agenda(grammar, self.roles, X_pub, target, meter=self.meter)
        self.last_report = dict(schema="wave24_workspace_v3",
            certificate_scope="reached_hop_grammar_only",
            max_hops=self.max_hops, b_hop=self.b0, primitive_cap=self.primitive_cap, slots=3,
            target_training_tasks=0, hops=hops, compiled_candidates=[], explored_source=explore,
            lyapunov=True, hop_stop_reason=None, noether_applied=self.noether is not None,
            leaf_macros=True)
        labels = {}
        for x, y in task.public_io:
            key = freeze(x)
            if key in labels and labels[key] != freeze(y):
                if trace is not None:
                    trace["workspace"] = self.last_report
                return SearchResult("VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS", (), (), False)
            labels[key] = freeze(y)
        all_entries, last_goal = [], GoalCheck(target, task.output_sort)
        best_E, seen_states = float("inf"), set()
        try:
            hop = 0
            while True:
                hop += 1
                if hop > self.max_hops:
                    self.last_report["hop_stop_reason"] = "hop_budget"
                    break
                if self.meter.total-started >= self.max_task_work_budget:
                    self.last_report["hop_stop_reason"] = "work_budget"
                    break
                self.phase_b = False
                self.spine_hop = self.spine_first and hop == 1
                if hop == 2 and self.spine_first:
                    if self.doctor is not None and not self.canonical_only:
                        self.doctor.rank_agenda(grammar, self.roles, X_pub, target, meter=self.meter)
                goal, entries = GoalCheck(target, task.output_sort), []
                last_goal = goal
                agenda = () if self.spine_hop or self.phase_b or self.canonical_only or self.doctor is None else self.doctor.last_agenda
                enum = ExactEnumerator(grammar, inputs, self.b0, meter=self.meter, macros=self.skills,
                    evolved=True, primitive_cap=self.primitive_cap, workspace=workspace,
                    target_public=target, noether=self.noether,
                    inner_heuristics=False, operator_agenda=agenda, leaf_macros=True)
                record = dict(hop=hop, workspace=[expression_wire(e) for e in workspace],
                              complete=False, selection=[], signature_digest=None,
                              noether_applied=enum.noether is not None,
                              leaf_macros=True)
                hops.append(record)
                twin = PopperianTwinVerifier(self.roles, max_mutations=self.twin_mutations)
                for expr, outputs, cost in enum:
                    entries.append((expr, outputs, cost))
                    split = goal.observe(expr, outputs)
                    if goal.first is not None and trace is not None and trace.get("work_to_g1") is None:
                        trace["work_to_g1"] = self.meter.total-started
                    if goal.first is not None:
                        self.phase_b = True
                    if goal.first is not None and twin is not None and not explore:
                        proposal = twin.search(goal.witnesses[0], grammar, task.public_io, task.query, enum, self.meter)
                        record["twin"] = twin.last_report
                        twin = None
                        if proposal is not None:
                            split = goal.observe(*proposal)
                    if split and not explore:
                        if trace is not None:
                            trace["work_to_g2"] = self.meter.total-started
                        break
                record["complete"] = enum.complete
                last_goal = goal
                all_entries.extend((unfold_workspace_expr(e, self.meter), ys, primitive_cost(e, grammar.ops))
                                   for e, ys, _ in entries)
                if goal.first is not None and not explore:
                    record["hop_witnesses"] = [expression_wire(e) for e in goal.witnesses]
                    record["witness_hop_costs"] = [enum.cost(e) for e in goal.witnesses]
                    raw = goal.result(enum.complete)
                    pure = tuple(unfold_workspace_expr(e, self.meter) for e in raw.witnesses)
                    self.last_report["compiled_candidates"] = [skill_wire(s) for e in pure for s in self.compile_trajectory(e, grammar)]
                    if enum.complete:
                        record["signature_digest"] = self.class_digest(self._classes(grammar, entries))
                        if trace is not None:
                            trace["work_to_uniqueness"] = self.meter.total-started
                    self.last_report["hop_stop_reason"] = "solved"
                    return SearchResult(raw.status, pure, raw.query_values, raw.complete, raw.root_equivalence_discharges)
                next_workspace, selection, classes = self._choose(grammar, entries, workspace, inputs, target)
                record.update(signature_digest=self.class_digest(classes), selection=selection)
                if not selection:
                    record["stop_reason"] = "no_new_public_signatures"
                    self.last_report["hop_stop_reason"] = "no_new_public_signatures"
                    break
                hop_E = min((row.get("atomic_deficit", row.get("phenotype_distance", best_E))
                             for row in selection), default=best_E)
                novel = False
                for row in selection:
                    outputs = row.get("outputs") or ()
                    public = outputs[:-1] if outputs else row.get("public_signature", (None, ()))[1]
                    state = self._state_key(public, row.get("role"))
                    if state not in seen_states:
                        novel = True
                    seen_states.add(state)
                progressed = hop_E < best_E - 1e-6
                if hop >= 3 and not progressed and not novel:
                    record["stop_reason"] = "lyapunov_converged"
                    self.last_report["hop_stop_reason"] = "lyapunov_converged"
                    break
                best_E = min(best_E, hop_E)
                workspace = next_workspace
            return all_entries if explore else last_goal.result(True)
        except WorkExhausted:
            self.last_report["budget_exhausted"] = True
            return all_entries if explore else last_goal.result(False)
        finally:
            self.last_report["noether_applied"] = any(bool(h.get("noether_applied")) for h in hops)
            if trace is not None:
                trace["workspace"] = self.last_report


@dataclass(frozen=True)
class JobTagRecipe:
    outer_job: str
    inner_job: str
    source_skill: str

    def key(self):
        return (self.outer_job, self.inner_job)


class JobTagRecipeEngine:
    """Source-provenanced job schemas on the existing typed macro contract."""
    def __init__(self):
        self.recipes = {}

    def remember(self, skill, roles, *, source_domain, purpose="training"):
        if purpose != "training" or source_domain == "BIT_CELLULAR_AUTOMATA":
            raise ValueError("fifth-world or assessment outcomes cannot update recipes")
        for outer in ast_nodes(skill.body):
            if outer.kind != "apply" or len(outer.children) != 1:
                continue
            inner = outer.children[0]
            if inner.kind != "apply" or len(inner.children) != 1:
                continue
            for a, b in product(universal_job_tags(roles[outer.value]), universal_job_tags(roles[inner.value])):
                recipe = JobTagRecipe(a, b, digest(skill.key()))
                self.recipes.setdefault(recipe.key(), recipe)

    def instantiate(self, grammar, roles, probe_inputs, *, meter):
        proposals, seen = {}, set()
        for recipe in sorted(self.recipes.values(), key=lambda r: r.key()):
            for outer, inner in product(grammar.operators, repeat=2):
                meter.charge("recipe_transfer_work_units")
                if (len(outer.inputs) != 1 or len(inner.inputs) != 1 or outer.inputs[0] != inner.output
                    or inner.inputs != (grammar.input_sort,)):
                    continue
                if recipe.outer_job in universal_job_tags(roles[outer.name]) and recipe.inner_job in universal_job_tags(roles[inner.name]):
                    skill = ParametricSkillMacro(apply(outer, apply(inner, typed_hole(grammar.input_sort))), (grammar.input_sort,))
                    proposals.setdefault(skill.key(), (skill, recipe))
        for expr in (variable(grammar.input_sort), *(apply(o, variable(grammar.input_sort)) for o in grammar.operators if o.inputs == (grammar.input_sort,))):
            seen.add((expr.sort, tuple(freeze(eval_expr(expr, x, grammar.ops, meter, "recipe_transfer_work_units")) for x in probe_inputs)))
        chosen, lineage = [], []
        for key in sorted(proposals, key=repr):
            skill, recipe = proposals[key]; call = skill.call(variable(grammar.input_sort))
            signature = (skill.sort, tuple(freeze(eval_expr(call, x, grammar.ops, meter, "recipe_transfer_work_units")) for x in probe_inputs))
            if signature in seen:
                continue
            seen.add(signature); chosen.append(skill)
            lineage.append(dict(skill=skill_wire(skill), source_skill=recipe.source_skill,
                job_recipe=[recipe.outer_job, recipe.inner_job], target_training_tasks=0))
            if len(chosen) == 3:
                break
        return tuple(chosen), lineage


class ClosedLoopSelfAuditor:
    """Measured SOURCE work credit; quarantine removes active search overhead only."""
    def __init__(self):
        self.utility = {}
        self.window = []
        self.speculative_share = .20
        self.adjustments = []
        self.journal = Journal()

    def record_usage(self, library, skill, *, without_work, with_work, overhead_work=0, source=True):
        if not source or any(type(v) is not int or v < 0 for v in (without_work, with_work, overhead_work)):
            raise ValueError("nonnegative observed source work required")
        key = digest(skill.key())
        net = without_work-with_work-overhead_work
        self.utility[key] = self.utility.get(key, 0)+net
        self.journal.append("wave24_actual_skill_work", dict(skill=key, without=without_work,
            with_skill=with_work, overhead=overhead_work, cumulative=self.utility[key]))
        if self.utility[key] < 0:
            library.quarantine(skill, source_net_utility=self.utility[key])
            return False
        return True

    def observe_task(self, *, unresolved, hops, source=True):
        if not source:
            return  # no tuning on target success/failure
        self.window = (self.window+[bool(unresolved or hops > 1)])[-3:]
        if len(self.window) >= 2 and sum(self.window)/len(self.window) >= 2/3 and self.speculative_share < .35:
            before = self.speculative_share
            self.speculative_share = min(.35, round(before+.05, 2))
            entry = dict(before=before, after=self.speculative_share, window=list(self.window),
                rule="source_stall_rate_ge_two_thirds", effect="replace_exploit_with_additional_novelty_at_rho_ge_point30")
            self.adjustments.append(entry); self.journal.append("wave24_stream_policy_adjustment", entry)


class AutonomousToolInventor:
    """Actual pure Python helper compilation from inferred typed programs.

    This invents COMPOSITE helpers over supplied primitives, not previously
    unavailable semantics. Optional LLM output must use the same typed AST
    encoding and a separately authorized resource host; it never executes code
    strings or imports. The CPU route is deterministic and used in this run.
    """
    def __init__(self, resource_host=None):
        self.resource_host = resource_host
        self.promoted = []

    @staticmethod
    def open_skill(program, grammar):
        pure = unfold_workspace_expr(program)
        def replace(e):
            return typed_hole(e.sort) if e.kind == "var" else Expr(e.kind, e.sort, e.value, tuple(replace(c) for c in e.children))
        skill = ParametricSkillMacro(replace(pure), (grammar.input_sort,))
        skill.validate(grammar)
        if not 2 <= skill.expansion_cost(grammar.ops) <= 8:
            raise ValueError("helper must contain 2..8 original primitive operations")
        return skill

    @staticmethod
    def compile_callable(skill, grammar):
        import ast
        skill.validate(grammar)
        def render(e):
            if e.kind == "hole" and e.value == 0:
                return ast.Name(id="z", ctx=ast.Load())
            if e.kind == "const":
                # literal_eval constructs only data; no repr/eval execution.
                return ast.parse(repr(e.value), mode="eval").body
            if e.kind == "apply" and e.value in grammar.ops:
                return ast.Call(func=ast.Name(id=e.value, ctx=ast.Load()), args=[render(c) for c in e.children], keywords=[])
            raise ValueError("helper compiler accepts only typed pure application trees")
        tree = ast.fix_missing_locations(ast.Module(body=[ast.FunctionDef(name="invented_tool",
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="z")], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[ast.Return(value=render(skill.body))], decorator_list=[])], type_ignores=[]))
        allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Call, ast.Name, ast.Load,
                   ast.Constant, ast.Tuple, ast.List, ast.Dict, ast.UnaryOp, ast.USub)
        if any(not isinstance(n, allowed) for n in ast.walk(tree)):
            raise ValueError("forbidden generated Python syntax")
        namespace = {"__builtins__": {}, **{o.name: o.fn for o in grammar.operators}}
        exec(compile(tree, "<nexus-vetted-helper>", "exec"), namespace)
        return namespace["invented_tool"], ast.unparse(tree)

    def propose(self, grammar, task, program, *, meter, use_runtime=False):
        if use_runtime:
            if self.resource_host is None or not self.resource_host.allocation.llm_approved:
                raise ValueError("LLM helper proposal requires a separate exact runtime allocation")
            response = self.resource_host.query_runtime("Propose a typed pure AST using only supplied operators; no source code.", {})
            program = expression_from_wire(json.loads(response["content"]))
            validate_program(program, grammar)
        skill = self.open_skill(program, grammar)
        meter.charge("tool_generation_work_units", sum(1 for _ in ast_nodes(skill.body)))
        function, source = self.compile_callable(skill, grammar)
        from nexus.wave24_resource_host import verify_pure_helper_isolated
        inputs = tuple(x for x, _ in task.public_io)+(task.query,)
        isolated = verify_pure_helper_isolated(function, inputs, meter=meter)
        expected = tuple(eval_expr(skill.call(variable(grammar.input_sort)), x, grammar.ops, meter,
                                   "tool_verification_work_units") for x in inputs)
        if tuple(map(freeze, isolated["outputs"])) != tuple(map(freeze, expected)):
            raise ValueError("compiled helper differs from its exact primitive expansion")
        if any(freeze(y) != freeze(z) for y, (_, z) in zip(expected[:-1], task.public_io)):
            raise ValueError("helper does not fit public observations")
        return dict(skill=skill, function=function, python_source=source,
            source_sha256=digest(source), isolation={k:v for k,v in isolated.items() if k != "outputs"},
            primitive_expansion_cost=skill.expansion_cost(grammar.ops), composite_only=True)

    def register(self, proposal, grammar, roles, probe_inputs, *, meter, observed_source_passed=False):
        if not observed_source_passed:
            raise ValueError("an observed source acceptance gate is required before toolbox mutation")
        name = "op_"+str(len(grammar.operators))
        op = Operator(name, proposal["skill"].input_sorts, proposal["skill"].sort,
                      proposal["function"], proposal["primitive_expansion_cost"])
        updated = Grammar(grammar.input_sort, (*grammar.operators, op), grammar.constants, grammar.bindings, grammar.conditionals)
        new_role = AutoOperatorFingerprinter().fingerprint_roles((op,), {grammar.input_sort: tuple(probe_inputs)}, meter=meter)[name]
        self.promoted.append(dict(name=name, python_source=proposal["python_source"], source_sha256=proposal["source_sha256"],
            skill=skill_wire(proposal["skill"]), charged_primitive_cost=op.cost, job_tags=universal_job_tags(new_role),
            composite_only=True))
        return updated, dict(roles, **{name:new_role})


class DualMemoryLearner:
    """One bounded source stream, reusing the E1 journal, macro view and ridge.

    Public solves and later revealed source feedback are separate operations.
    A frozen domain cannot tune, fit, promote, invent, or alter recipes.
    """
    def __init__(self, *, meter=None, resource_host=None, max_source_updates=16):
        if type(max_source_updates) is not int or not 1 <= max_source_updates <= 16:
            raise ValueError("bounded source-update count required")
        self.meter = meter if meter is not None else WorkMeter()
        self.doctor = SymptomToActionDoctor(SymptomJobCritic(resource_host=resource_host))
        self.doctor.metabolic = None
        self.recipes, self.auditor = JobTagRecipeEngine(), ClosedLoopSelfAuditor()
        self.inventor = AutonomousToolInventor(resource_host)
        self.metabolic = HomeostaticMetabolicController()
        self.doctor.metabolic = self.metabolic
        self.contexts, self.last = {}, {}
        self.updates, self.max_updates, self.history = 0, max_source_updates, Journal()

    def enter(self, domain, grammar, roles, probe_inputs, *, frozen=False):
        if domain in self.contexts or domain == "BIT_CELLULAR_AUTOMATA" and not frozen:
            raise ValueError("domain already entered or fifth-world training requested")
        if set(roles) != set(grammar.ops):
            raise ValueError("startup role provenance is incomplete")
        self.contexts[domain] = dict(grammar=grammar, roles=roles, probes=tuple(probe_inputs), frozen=bool(frozen),
            library=JournalSkillView(), protected=[])

    def import_recipes(self, domain):
        c = self.contexts[domain]
        if c["library"].snapshot():
            raise ValueError("target recipe import requires an empty library")
        skills, lineage = self.recipes.instantiate(c["grammar"], c["roles"], c["probes"], meter=self.meter)
        for skill, record in zip(skills, lineage):
            c["library"].install_transfer(skill, c["grammar"], record)
        return lineage

    def _evaluate(self, c, task, skills, *, guided=True):
        trace, before = {}, self.meter.total
        # Tier-1 spine: hop-1 exact quotient + library before any hop-2+ speculation.
        # Adaptive may continue Lyapunov hops only after this reservation completes.
        result = ScratchpadWorkspaceEngine(roles=c["roles"], skills=skills, meter=self.meter,
            doctor=self.doctor if guided else None, scorer=None,
            speculative_share=self.auditor.speculative_share, canonical_only=not guided,
            use_noether=bool(guided), spine_first=bool(guided),
            max_hops=16 if guided else 3).run(c["grammar"], task, trace=trace)
        search_work = self.meter.total-before
        valid = None
        if result.status != "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED":
            valid = verify_workspace_certificate(c["grammar"], task, result, trace["workspace"],
                                                skills=skills, meter=self.meter)
        hops = len(trace.get("workspace", {}).get("hops") or ())
        return result, dict(trace=trace, search_work=search_work, verification_work=self.meter.total-before-search_work,
                            total_work=self.meter.total-before, certificate_valid=valid,
                            spine_reserved=True, spine_hops=min(1, hops))

    def solve_task(self, domain, task, *, invent=False, guided=True):
        c = self.contexts[domain]
        before = self.fingerprint()
        result, report = self._evaluate(c, task, c["library"].snapshot(), guided=guided)
        report.update(task_digest=digest((task.public_io, task.query)), library_before=[skill_wire(s) for s in c["library"].snapshot()],
            critic_before=self.doctor.critic.fingerprint(), source_learning_performed=False,
            decision_total_work=report["total_work"], tool_generation_work=0)
        # Generate a candidate only. No target helper can be registered.
        proposal = None
        if invent:
            if c["frozen"]:
                raise ValueError("frozen target cannot propose/promote task-tailored tools")
            if result.witnesses and len(report["trace"]["workspace"]["hops"]) > 1:
                generation_start = self.meter.total
                proposal = self.inventor.propose(c["grammar"], task, result.witnesses[0], meter=self.meter)
                report["tool_proposed"] = {k:v for k,v in proposal.items() if k not in ("function", "skill")}
                report["tool_generation_work"] = self.meter.total-generation_start
                report["total_work"] += report["tool_generation_work"]
        if self.fingerprint() != before:
            raise ValueError("answer-free solve changed learned state")
        self.last[domain] = dict(task=task, result=result, report=report, proposal=proposal, consumed=False)
        self.history.append("wave24_locked_stream_solve", dict(domain=domain, task=report["task_digest"], status=result.status,
            trace=report["trace"], frozen=c["frozen"]))
        return result, report

    def learn_last_source(self, domain, *, observed_query):
        c, item = self.contexts[domain], self.last.get(domain)
        if c["frozen"] or domain == "BIT_CELLULAR_AUTOMATA" or item is None or item["consumed"] or self.updates >= self.max_updates:
            raise ValueError("missing permitted one-use source feedback or update budget")
        item["consumed"] = True; self.updates += 1
        task, result, report = item["task"], item["result"], item["report"]
        before = self.meter.total
        accepted, receipt = False, None
        correct = result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE" and tuple(map(freeze, result.query_values)) == (freeze(observed_query),)
        if correct:
            try:
                skill = self.inventor.open_skill(result.witnesses[0], c["grammar"])
                self.meter.charge("learning_proposal_work_units", sum(1 for _ in ast_nodes(skill.body)))
            except ValueError:
                skill = None
            if skill is not None and digest(skill.key()) not in c["library"]._asts and len(c["library"].snapshot()) < 3:
                proposal_work = self.meter.total-before
                trial, trial_report = self._evaluate(c, task, (*c["library"].snapshot(), skill))
                retention_start = self.meter.total
                retention = True
                for old_task, old_answer in c["protected"][-3:]:
                    prior, _ = self._evaluate(c, old_task, (*c["library"].snapshot(), skill))
                    retention &= prior.status.startswith("UNIQUE_QUERY") and tuple(map(freeze, prior.query_values)) == (freeze(old_answer),)
                candidate_ok = trial.status.startswith("UNIQUE_QUERY") and tuple(map(freeze, trial.query_values)) == (freeze(observed_query),)
                overhead = proposal_work+self.meter.total-retention_start+report["tool_generation_work"]
                receipt = dict(source_only=True, certificate_valid=trial_report["certificate_valid"] is True and candidate_ok,
                    retention_passed=bool(retention), task_digest=report["task_digest"],
                    without_work=report["decision_total_work"], with_work=trial_report["total_work"], proposal_work=overhead,
                    net_work_saved=report["decision_total_work"]-trial_report["total_work"]-overhead,
                    interpretation="finite paired source work; not a confidence interval")
                decision = c["library"].retain_stream(skill, c["grammar"], receipt=receipt)
                accepted = decision["accepted"]
                if accepted:
                    self.recipes.remember(skill, c["roles"], source_domain=domain)
                    self.auditor.record_usage(c["library"], skill, without_work=report["decision_total_work"],
                        with_work=trial_report["total_work"], overhead_work=overhead)
                    self.metabolic.observe(digest(skill.key()), receipt["net_work_saved"])
                    if item["proposal"] is not None:
                        c["grammar"], c["roles"] = self.inventor.register(item["proposal"], c["grammar"], c["roles"],
                            c["probes"], meter=self.meter, observed_source_passed=True)
            c["protected"].append((task, observed_query))
        feedback = self.doctor.learn_source(c["grammar"], task, c["roles"], meter=self.meter)
        hops = len(report["trace"]["workspace"]["hops"])
        self.auditor.observe_task(unresolved=not correct, hops=hops)
        learned = dict(accepted=accepted, correct_before_update=correct, receipt=receipt, doctor=feedback,
            learning_work=self.meter.total-before, critic_after=self.doctor.critic.fingerprint(),
            active_skills=len(c["library"].snapshot()), source_updates=self.updates)
        self.history.append("wave24_revealed_source_update", dict(domain=domain, task=report["task_digest"], **learned))
        return learned

    def audit_shortcuts(self, domain, task):
        c = self.contexts[domain]
        if c["frozen"]:
            raise ValueError("target feedback cannot tune shortcut retention")
        records = []
        for skill in tuple(c["library"].snapshot()):
            active = c["library"].snapshot()
            without, a = self._evaluate(c, task, tuple(s for s in active if s.key() != skill.key()))
            with_skill, b = self._evaluate(c, task, active)
            comparable = (without.status == with_skill.status and without.query_values == with_skill.query_values
                          and a["certificate_valid"] is True and b["certificate_valid"] is True)
            if not comparable:
                records.append(dict(skill=digest(skill.key()), quarantined=False, incomparable=True)); continue
            kept = self.auditor.record_usage(c["library"], skill, without_work=a["total_work"], with_work=b["total_work"])
            if kept:
                self.metabolic.observe(digest(skill.key()), a["total_work"]-b["total_work"])
            else:
                self.metabolic.evict(digest(skill.key()), reason="negative_counterfactual_utility")
            records.append(dict(skill=digest(skill.key()), quarantined=not kept, without=a["total_work"], with_skill=b["total_work"]))
        return records

    def fingerprint(self):
        return digest(dict(critic=self.doctor.critic.fingerprint(), recipes=[r.__dict__ for r in self.recipes.recipes.values()],
            libraries={d:[skill_wire(s) for s in c["library"].snapshot()] for d,c in self.contexts.items()},
            grammar_ops={d:[(o.name,o.inputs,o.output,o.cost) for o in c["grammar"].operators] for d,c in self.contexts.items()},
            rho=self.auditor.speculative_share, updates=self.updates))

    def export_state(self):
        from dataclasses import asdict
        body = dict(schema="wave24_dual_memory_v1", fingerprint=self.fingerprint(), source_rows=self.doctor.rows,
            critic_source_digest=self.doctor.critic.source_digest, source_updates=self.updates,
            doctor_guard=self.doctor.guard.traces,
            critic_parameters=None if self.doctor.critic.models is None else [(s.tolist(),b.tolist()) for s,b in self.doctor.critic.models],
            recipes=[r.__dict__ for r in self.recipes.recipes.values()],
            libraries={d:[skill_wire(s) for s in c["library"].snapshot()] for d,c in self.contexts.items()},
            exploration_share=self.auditor.speculative_share,
            grammar_descriptors={d:[(o.name,o.inputs,o.output,o.cost) for o in c["grammar"].operators] for d,c in self.contexts.items()},
            role_digests={d:digest({name:r.probe_digest for name,r in c["roles"].items()}) for d,c in self.contexts.items()},
            journal_heads=[self.history.snapshot()[-1].fingerprint] if self.history.snapshot() else [],
            history=[asdict(e) for e in self.history.snapshot()],
            domain_journals={d:[asdict(e) for e in c["library"].journal.snapshot()] for d,c in self.contexts.items()},
            all_skills={d:{k:skill_wire(s) for k,s in c["library"]._asts.items()} for d,c in self.contexts.items()},
            protected={d:[dict(public=[[freeze(x),freeze(y)] for x,y in t.public_io], query=freeze(t.query),
                output_sort=t.output_sort, observed=freeze(answer)) for t,answer in c["protected"]] for d,c in self.contexts.items()},
            auditor=dict(utility=self.auditor.utility,window=self.auditor.window,adjustments=self.auditor.adjustments,
                journal=[asdict(e) for e in self.auditor.journal.snapshot()]),invented_tools=self.inventor.promoted)
        return dict(body, state_sha256=digest(body))

    def restore_state(self, record, *, expected_digest):
        """Transactionally validate before installing the checkpoint."""
        if any(c["library"].snapshot() for c in self.contexts.values()) or self.updates:
            raise ValueError("restore requires a fresh entered learner")
        staged = DualMemoryLearner(meter=self.meter, resource_host=self.doctor.critic.resource_host,
                                   max_source_updates=self.max_updates)
        for domain, c in self.contexts.items():
            staged.enter(domain,c["grammar"],c["roles"],c["probes"],frozen=c["frozen"])
        staged._restore_state_checked(record,expected_digest=expected_digest)
        self.contexts,self.doctor,self.recipes,self.auditor = staged.contexts,staged.doctor,staged.recipes,staged.auditor
        self.updates,self.history,self.inventor = staged.updates,staged.history,staged.inventor
        return True

    def _restore_state_checked(self, record, *, expected_digest):
        """Restore data against owner-supplied matching toolboxes; never unpickle code."""
        copy = dict(record); claimed = copy.pop("state_sha256", None)
        if claimed != expected_digest or claimed != digest(copy) or record.get("schema") != "wave24_dual_memory_v1":
            raise ValueError("state digest differs from the external checkpoint anchor")
        if any(c["library"].snapshot() for c in self.contexts.values()) or self.updates:
            raise ValueError("restore requires a fresh entered learner")
        if set(record["libraries"]) != set(self.contexts):
            raise ValueError("restored domain set differs")
        for domain, c in self.contexts.items():
            descriptors = [(o.name,o.inputs,o.output,o.cost) for o in c["grammar"].operators]
            if digest(descriptors) != digest(record["grammar_descriptors"][domain]) or digest({n:r.probe_digest for n,r in c["roles"].items()}) != record["role_digests"][domain]:
                raise ValueError("restore toolbox provenance differs")
            if len(record["libraries"][domain]) > 3:
                raise ValueError("checkpoint exceeds the skill cap")
            for wire in record["libraries"][domain]:
                skill = skill_from_wire(wire); skill.validate(c["grammar"])
                key = digest(skill.key()); c["library"]._asts[key] = skill
                c["library"].journal.append("wave24_verified_ast_skill", dict(skill_id=key, ast=wire, purpose="anchored_restore"))
        import numpy as np
        self.doctor.rows = record["source_rows"]
        self.doctor.guard.traces = [dict(features=tuple(row["features"]), work=int(row["work"]))
                                    for row in record.get("doctor_guard", ())]
        if len(self.doctor.rows) > 128 or any(r.get("label_semantics") != "source_symptom_job_v1" for r in self.doctor.rows):
            raise ValueError("invalid source feedback checkpoint")
        self.doctor.critic.source_digest = record["critic_source_digest"]
        if self.doctor.critic.source_digest is not None and self.doctor.critic.source_digest != digest(self.doctor.rows):
            raise ValueError("restored source labels do not match the critic")
        params = record["critic_parameters"]
        self.doctor.critic.models = None if params is None else tuple((np.asarray(s),np.asarray(b)) for s,b in params)
        if params is not None and (len(params) != 2 or any(s.shape != (10,) or b.shape != (10,) or not np.isfinite(s).all() or not np.isfinite(b).all() or not (s>0).all() for s,b in self.doctor.critic.models)):
            raise ValueError("invalid persisted critic parameters")
        self.recipes.recipes = {r.key():r for r in (JobTagRecipe(**row) for row in record["recipes"])}
        self.auditor.speculative_share = record["exploration_share"]
        self.updates = record["source_updates"]
        if not .15 <= self.auditor.speculative_share <= .35 or not 0 <= self.updates <= self.max_updates:
            raise ValueError("persisted resource/policy bounds differ")
        if self.fingerprint() != record["fingerprint"]:
            raise ValueError("restored learner fingerprint differs")
        from nexus.evolution1.fixtures import Event, verify_journal
        def restored_journal(rows, expected_head=None):
            events=tuple(Event(**row) for row in rows)
            verify_journal(events,expected_head=expected_head,expected_count=len(rows))
            journal=Journal();journal._events=events
            return journal
        self.history=restored_journal(record["history"],record["journal_heads"][0] if record["journal_heads"] else "0"*64)
        for domain,c in self.contexts.items():
            library=c["library"]
            library._asts={k:skill_from_wire(v) for k,v in record["all_skills"][domain].items()}
            for key,skill in library._asts.items():
                skill.validate(c["grammar"])
                if key!=digest(skill.key()):raise ValueError("archived skill digest differs")
            library.journal=restored_journal(record["domain_journals"][domain])
            if digest([skill_wire(s) for s in library.snapshot()])!=digest(record["libraries"][domain]):
                raise ValueError("restored archive/active set differs")
            c["protected"]=[(PublicTask(tuple((unfreeze(x),unfreeze(y)) for x,y in row["public"]),
                unfreeze(row["query"]),row["output_sort"]),unfreeze(row["observed"])) for row in record["protected"][domain]]
        audit=record["auditor"]
        self.auditor.utility=dict(audit["utility"]);self.auditor.window=list(audit["window"])
        self.auditor.adjustments=list(audit["adjustments"]);self.auditor.journal=restored_journal(audit["journal"])
        self.inventor.promoted=list(record["invented_tools"])
        self.history.append("wave24_anchored_restore", dict(state_digest=claimed, prior_heads=record["journal_heads"]))
        return True
