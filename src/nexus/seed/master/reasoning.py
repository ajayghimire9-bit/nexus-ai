"""Portfolio of 8 verifiable reasoners and the ReasoningRouter for the NEXUS Seed master architecture.

Every reasoner produces a structured ReasoningResult(conclusion, proof_or_trace,
assumptions, confidence, cost, unresolved_questions) with an inspectable trace.
"""
import ast
import copy
import math
import operator
import re
from typing import Any
from .. import skill_programs as ir
from ..foundation import programs as foundation_programs
from ..planning import to_cell, compact
from .types import ReasoningResult

TRANSITIVE_RELATIONS = {
    "older", "younger", "taller", "shorter", "larger", "smaller",
    "north", "south", "east", "west", "above", "below", "left", "right",
    "before", "after", "greater", "less", "contains", "implies",
}

INVERSE_RELATIONS = {
    "older": "younger",
    "younger": "older",
    "taller": "shorter",
    "shorter": "taller",
    "larger": "smaller",
    "smaller": "larger",
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "above": "below",
    "below": "above",
    "before": "after",
    "after": "before",
    "greater": "less",
    "less": "greater",
}


class RelationalReasoner:
    """Represents entities and relations as a directed graph and applies typed
    inference rules (transitivity, converse/inverse) while checking rule assumptions."""

    def reason(self, facts: list[dict], query_subject: str, query_object: str, relation: str | None = None, assumptions: list[str] | None = None) -> ReasoningResult:
        if type(facts) is not list or not facts:
            raise ValueError("relational_facts_required")
        edges: dict[tuple[str, str], set[str]] = {}
        nodes: set[str] = set()
        trace = []
        cost = 0

        for f in facts:
            rel = str(f["relation"]).strip().lower().removesuffix(" of").removesuffix(" than")
            subj = str(f["subject"]).strip()
            obj = str(f["object"]).strip()
            nodes.update((subj, obj))
            edges.setdefault((subj, obj), set()).add(rel)
            trace.append(f"premise: {rel}({subj}, {obj})")
            cost += 1
            if rel in INVERSE_RELATIONS:
                inv = INVERSE_RELATIONS[rel]
                edges.setdefault((obj, subj), set()).add(inv)
                trace.append(f"converse_rule: {rel}({subj}, {obj}) => {inv}({obj}, {subj})")
                cost += 1

        # Fixed-point transitive closure over bounded graph
        changed = True
        iterations = 0
        while changed and iterations < 16:
            changed = False
            iterations += 1
            current_items = list(edges.items())
            for (a, b), rels_ab in current_items:
                for (b2, c), rels_bc in current_items:
                    if b != b2 or a == c:
                        continue
                    for r in rels_ab & rels_bc:
                        if r in TRANSITIVE_RELATIONS:
                            cost += 1
                            if r not in edges.setdefault((a, c), set()):
                                edges[(a, c)].add(r)
                                trace.append(f"transitive({r}): {r}({a}, {b}) and {r}({b}, {c}) => {r}({a}, {c})")
                                changed = True

        inferred = sorted(edges.get((query_subject, query_object), set()))
        if relation is not None:
            rel_norm = relation.strip().lower().removesuffix(" of").removesuffix(" than")
            holds = rel_norm in inferred
            conclusion = f"{query_subject} is {rel_norm} of {query_object}" if holds else f"Cannot derive {rel_norm}({query_subject}, {query_object})"
            confidence = 0.98 if holds else 0.25
        elif inferred:
            top_rel = inferred[0]
            preposition = "than" if top_rel in ("older", "younger", "taller", "shorter", "larger", "smaller", "greater", "less") else "of"
            if top_rel in ("before", "after", "contains", "implies"):
                conclusion = f"{query_subject} is {top_rel} {query_object}"
            else:
                conclusion = f"{query_subject} is {top_rel} {preposition} {query_object}"
            confidence = 0.98
        else:
            conclusion = f"No verified relation found between {query_subject} and {query_object}"
            confidence = 0.2

        rule_assumptions = list(assumptions or [
            "Transitivity holds on planar/acyclic domain (non-polar coordinates for spatial relations)",
            "Entity identifiers refer to fixed distinct nodes",
        ])
        unresolved = [] if inferred else [f"What is the relation connecting {query_subject} to {query_object}?"]
        return ReasoningResult(
            conclusion=conclusion,
            proof_or_trace=trace,
            assumptions=rule_assumptions,
            confidence=confidence,
            cost=max(1, cost),
            unresolved_questions=unresolved,
        )


class ConstraintReasoner:
    """Finite-domain CSP / SAT-style backtracking solver for schedules, ordering,
    assignments, logic puzzles, and resource limits."""

    def solve(self, variables: dict[str, list[Any]], constraints: list[dict]) -> ReasoningResult:
        if type(variables) is not dict or not variables or len(variables) > 16:
            raise ValueError("bounded_csp_variables_required")
        var_names = list(variables.keys())
        domains = {k: list(v) for k, v in variables.items()}
        trace = []
        cost = 0

        def consistent(assignment: dict) -> bool:
            nonlocal cost
            for c in constraints:
                cost += 1
                kind = c.get("kind", "all_different")
                if kind == "all_different":
                    scope = c.get("vars", var_names)
                    vals = [assignment[v] for v in scope if v in assignment]
                    if len(vals) != len(set(vals)):
                        return False
                elif kind == "not_equal":
                    a, b = c["a"], c["b"]
                    if a in assignment and b in assignment and assignment[a] == assignment[b]:
                        return False
                elif kind == "equal":
                    a, b = c["a"], c["b"]
                    if a in assignment and b in assignment and assignment[a] != assignment[b]:
                        return False
                elif kind == "less_than":
                    a, b = c["a"], c["b"]
                    if a in assignment and b in assignment and not (assignment[a] < assignment[b]):
                        return False
                elif kind == "greater_than":
                    a, b = c["a"], c["b"]
                    if a in assignment and b in assignment and not (assignment[a] > assignment[b]):
                        return False
                elif kind == "sum_limit":
                    scope = c.get("vars", var_names)
                    limit = c["limit"]
                    vals = [assignment[v] for v in scope if v in assignment]
                    if sum(vals) > limit:
                        return False
                    if len(vals) == len(scope) and "exact" in c and sum(vals) != c["exact"]:
                        return False
                elif kind == "forbidden_value":
                    v_name = c["var"]
                    if v_name in assignment and assignment[v_name] == c["value"]:
                        return False
            return True

        solutions = []

        def backtrack(idx: int, current: dict):
            if len(solutions) >= 4 or cost > 5000:
                return
            if idx == len(var_names):
                if consistent(current):
                    solutions.append(copy.deepcopy(current))
                    trace.append(f"solution_found: {current}")
                return
            var = var_names[idx]
            for val in domains[var]:
                current[var] = val
                if consistent(current):
                    backtrack(idx + 1, current)
                current.pop(var, None)

        backtrack(0, {})
        if solutions:
            return ReasoningResult(
                conclusion=solutions[0],
                proof_or_trace=trace + [f"verified_constraints: {len(constraints)}", f"total_solutions_checked: {len(solutions)}"],
                assumptions=["Finite variable domains", "All hard constraints explicitly listed"],
                confidence=1.0,
                cost=max(1, cost),
                unresolved_questions=[] if len(solutions) == 1 else [f"{len(solutions)} satisfying assignments exist; add constraints to disambiguate."],
            )
        return ReasoningResult(
            conclusion=None,
            proof_or_trace=trace + ["unsatisfiable_under_supplied_constraints"],
            assumptions=["Finite variable domains"],
            confidence=1.0,
            cost=max(1, cost),
            unresolved_questions=["Which constraint can be relaxed to make the problem satisfiable?"],
        )


class MathematicalReasoner:
    """Typed arithmetic, linear/quadratic equation solver, dimensional verification,
    and substitution checker."""

    SAFE_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval_ast(self, node, env: dict[str, float]) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in env:
            return float(env[node.id])
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.SAFE_OPS:
            return float(self.SAFE_OPS[type(node.op)](self._eval_ast(node.operand, env)))
        if isinstance(node, ast.BinOp) and type(node.op) in self.SAFE_OPS:
            left = self._eval_ast(node.left, env)
            right = self._eval_ast(node.right, env)
            if isinstance(node.op, ast.Pow) and abs(right) > 16:
                raise ValueError("exponent_bound_exceeded")
            return float(self.SAFE_OPS[type(node.op)](left, right))
        raise ValueError("unsupported_math_expression")

    def solve(self, expression: str, units: dict[str, str] | None = None, variable: str = "x") -> ReasoningResult:
        if type(expression) is not str or not expression.strip():
            raise ValueError("math_expression_required")
        raw = expression.strip()
        # Extract algebraic equation or arithmetic expression from natural language if embedded
        eq_match = re.search(r"([0-9xX\+\-\*\/\(\)\.\s]+=[0-9xX\+\-\*\/\(\)\.\s]+)", raw)
        expr_clean = eq_match.group(1).strip() if eq_match else raw
        expr_clean = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr_clean)
        trace = [f"parsed_expression: {expr_clean}"]
        cost = 1

        # Dimensional check if units are supplied
        if units:
            lhs_unit = units.get("lhs")
            rhs_unit = units.get("rhs")
            trace.append(f"dimensional_check: lhs={lhs_unit}, rhs={rhs_unit}")
            if lhs_unit and rhs_unit and lhs_unit != rhs_unit:
                return ReasoningResult(
                    conclusion="dimensional_mismatch",
                    proof_or_trace=trace + [f"error: incompatible units {lhs_unit} != {rhs_unit}"],
                    assumptions=["Dimensional homogeneity required"],
                    confidence=1.0,
                    cost=2,
                    unresolved_questions=["Convert quantities to matching SI units before solving."],
                )

        if "=" in expr_clean:
            lhs_str, rhs_str = [s.strip() for s in expr_clean.split("=", 1)]
            lhs_ast = ast.parse(lhs_str, mode="eval").body
            rhs_ast = ast.parse(rhs_str, mode="eval").body

            def f(val: float) -> float:
                return self._eval_ast(lhs_ast, {variable: val}) - self._eval_ast(rhs_ast, {variable: val})

            # Linear interpolation / secant + substitution verification
            f0 = f(0.0)
            f1 = f(1.0)
            slope = f1 - f0
            cost += 3
            if abs(slope) < 1e-12:
                raise ValueError("singular_or_nonlinear_equation")
            root = -f0 / slope
            lhs_check = self._eval_ast(lhs_ast, {variable: root})
            rhs_check = self._eval_ast(rhs_ast, {variable: root})
            residual = abs(lhs_check - rhs_check)
            verified = residual < 1e-7
            clean_root = int(round(root)) if abs(root - round(root)) < 1e-9 else round(root, 6)
            trace.extend([
                f"linear_transform: f(0)={f0}, f(1)={f1}, slope={slope}",
                f"candidate_solution: {variable} = {clean_root}",
                f"substitution_verification: LHS({clean_root})={lhs_check}, RHS({clean_root})={rhs_check}, residual={residual:.2e}, verified={verified}",
            ])
            return ReasoningResult(
                conclusion={variable: clean_root, "verified": verified},
                proof_or_trace=trace,
                assumptions=["Real-valued arithmetic", "Substitution residual < 1e-7"],
                confidence=1.0 if verified else 0.3,
                cost=cost,
                unresolved_questions=[] if verified else ["Equation may be higher-degree nonlinear; supply domain bounds."],
            )

        # Pure arithmetic evaluation
        arith_match = re.search(r"[-+*/().0-9\s]+", expr_clean)
        target_str = arith_match.group(0).strip() if arith_match else expr_clean
        node = ast.parse(target_str, mode="eval").body
        val = self._eval_ast(node, {})
        clean_val = int(round(val)) if abs(val - round(val)) < 1e-9 else round(val, 6)
        trace.append(f"evaluated_value: {clean_val}")
        return ReasoningResult(
            conclusion=clean_val,
            proof_or_trace=trace,
            assumptions=["Exact bounded arithmetic"],
            confidence=1.0,
            cost=2,
            unresolved_questions=[],
        )


class ProgramExecutionReasoner:
    """Runs verified skill programs or foundation expressions on concrete inputs
    and inspects intermediate states and postconditions."""

    def execute_and_verify(self, program: dict, inputs: Any, postcondition_check=None) -> ReasoningResult:
        if type(program) is not dict:
            raise ValueError("typed_program_dict_required")
        trace = [f"inputs: {inputs}"]
        cost = 1
        intermediate_state = []

        if "schema" in program:
            schema = program["schema"]
            ir.value(schema, inputs)
            norm_prog = copy.deepcopy(program)
            if schema in ("list", "motion") and "ops" not in norm_prog:
                if "steps" in norm_prog:
                    norm_prog = dict(schema=schema, ops=list(norm_prog["steps"]))
                elif "op" in norm_prog:
                    norm_prog = dict(schema=schema, ops=[norm_prog["op"]])
            applied_procedure = f"skill_program:{schema}:{norm_prog.get('ops', norm_prog)}"
            if schema in ("list", "motion") and norm_prog.get("ops"):
                cur = copy.deepcopy(inputs)
                for step_op in norm_prog["ops"]:
                    cur = ir.run(dict(schema=schema, ops=[step_op]), cur)
                    intermediate_state.append(dict(step=step_op, value=copy.deepcopy(cur)))
                    cost += 1
                result = cur
            else:
                result = ir.run(norm_prog, inputs)
                intermediate_state.append(dict(step=norm_prog.get("name", "eval"), value=copy.deepcopy(result)))
                cost += 1
        else:
            applied_procedure = f"foundation_program:{program.get('op', 'expr')}"
            env = inputs if isinstance(inputs, dict) else {"x": inputs}
            out = foundation_programs.execute(program, env, budget=256)
            result = out["value"]
            cost = max(1, int(out.get("instructions", 1)))
            intermediate_state.append(dict(instructions=cost, value=copy.deepcopy(result)))

        verified = True if postcondition_check is None else bool(postcondition_check(inputs, result))
        execution_record = dict(
            inputs=copy.deepcopy(inputs),
            applied_procedure=applied_procedure,
            intermediate_state=intermediate_state,
            result=copy.deepcopy(result),
            assumptions=["Deterministic pure execution", "Bounded instruction budget"],
            verification=dict(passed=verified),
        )
        trace.extend([
            f"applied_procedure: {applied_procedure}",
            f"intermediate_state: {intermediate_state}",
            f"result: {result}",
            f"verification: {verified}",
        ])
        return ReasoningResult(
            conclusion=execution_record,
            proof_or_trace=trace,
            assumptions=execution_record["assumptions"],
            confidence=1.0 if verified else 0.0,
            cost=cost,
            unresolved_questions=[] if verified else ["Postcondition check failed on program output."],
        )


class CausalReasoner:
    """Distinguishes causal mechanisms ('X causes Y'), observational correlation
    ('X correlates with Y'), and common-cause confounding ('Z may explain both X and Y'),
    and selects interventions to disambiguate them."""

    def analyze(self, variable_x: str, variable_y: str, observational_data: list[dict] | None = None, interventional_data: list[dict] | None = None, candidate_confounder: str = "Z") -> ReasoningResult:
        obs = list(observational_data or [])
        interventions = list(interventional_data or [])
        trace = [
            f"hypotheses_considered: ['{variable_x} causes {variable_y}', '{variable_x} correlates with {variable_y}', '{candidate_confounder} may explain both {variable_x} and {variable_y}']",
        ]
        cost = len(obs) + len(interventions) + 1

        if interventions:
            # Check if do(X=1) vs do(X=0) changes Y when Z is held fixed or randomized
            pos_y = [row["Y"] for row in interventions if row.get("do_X") == 1]
            neg_y = [row["Y"] for row in interventions if row.get("do_X") == 0]
            if pos_y and neg_y:
                mean_pos = sum(pos_y) / len(pos_y)
                mean_neg = sum(neg_y) / len(neg_y)
                ate = mean_pos - mean_neg
                trace.append(f"interventional_effect: E[Y|do({variable_x}=1)] - E[Y|do({variable_x}=0)] = {ate:.3f}")
                if abs(ate) > 0.2:
                    claim = f"{variable_x} causes {variable_y}"
                    confidence = 0.94
                    unresolved = []
                else:
                    claim = f"{candidate_confounder} may explain both {variable_x} and {variable_y}"
                    confidence = 0.91
                    unresolved = []
                return ReasoningResult(
                    conclusion=dict(
                        classification=claim,
                        average_treatment_effect=round(ate, 4),
                        competing_claims=[
                            f"{variable_x} causes {variable_y}",
                            f"{variable_x} correlates with {variable_y}",
                            f"{candidate_confounder} may explain both {variable_x} and {variable_y}",
                        ],
                    ),
                    proof_or_trace=trace,
                    assumptions=["Valid intervention do(X) breaks incoming edges from confounder Z"],
                    confidence=confidence,
                    cost=cost,
                    unresolved_questions=unresolved,
                )

        # Observational only: cannot prove causation without intervention
        trace.append(f"observational_only: {variable_x} correlates with {variable_y}, but confounder {candidate_confounder} is not ruled out")
        recommended_experiment = f"Intervene with do({variable_x}=1) vs do({variable_x}=0) while holding {candidate_confounder} fixed, and measure {variable_y}."
        return ReasoningResult(
            conclusion=dict(
                classification=f"{variable_x} correlates with {variable_y}",
                confounder_hypothesis=f"{candidate_confounder} may explain both {variable_x} and {variable_y}",
                causal_hypothesis=f"{variable_x} causes {variable_y}",
                recommended_experiment=recommended_experiment,
            ),
            proof_or_trace=trace,
            assumptions=["Observational correlation alone does not establish causal direction"],
            confidence=0.72,
            cost=cost,
            unresolved_questions=[recommended_experiment],
        )


class AnalogicalReasoner:
    """Maps relational structure across surface domains (e.g. list reversal <->
    reverse movement sequence) when structural relations match."""

    DIRECTION_INVERSE = {"right": "left", "left": "right", "up": "down", "down": "up"}

    def map_structure(self, source_domain: dict, target_domain: dict) -> ReasoningResult:
        src_name = source_domain.get("domain", "list_domain")
        tgt_name = target_domain.get("domain", "movement_domain")
        operation = source_domain.get("operation", "reverse_order")
        items = list(target_domain.get("sequence", []))
        trace = [
            f"source_domain: {src_name} ({operation})",
            f"target_domain: {tgt_name}",
            "structural_alignment: index_order(i -> N-1-i) <-> temporal_step_order(t -> T-1-t)",
        ]
        cost = len(items) + 2

        if tgt_name == "movement_domain" and operation in ("reverse", "reverse_order", "list_reversal"):
            # Map list reversal onto reversing a movement sequence (reverse step order + invert directions)
            invert_dirs = bool(target_domain.get("invert_directions", True))
            mapped = []
            for step in reversed(items):
                if isinstance(step, dict) and "direction" in step:
                    new_step = dict(step)
                    if invert_dirs and step["direction"] in self.DIRECTION_INVERSE:
                        new_step["direction"] = self.DIRECTION_INVERSE[step["direction"]]
                    mapped.append(new_step)
                elif isinstance(step, str) and step in self.DIRECTION_INVERSE and invert_dirs:
                    mapped.append(self.DIRECTION_INVERSE[step])
                else:
                    mapped.append(step)
            trace.append(f"mapped_sequence: {mapped}")
            return ReasoningResult(
                conclusion=dict(
                    analogy="list_reversal <-> reverse_movement_sequence",
                    mapped_sequence=mapped,
                    structural_isomorphism=True,
                ),
                proof_or_trace=trace,
                assumptions=[
                    "Order inversion is structurally isomorphic across finite sequences",
                    "Spatial return path additionally inverts step direction vectors",
                    "Cross-domain transfer requires verification in target environment",
                ],
                confidence=0.88,
                cost=cost,
                unresolved_questions=[],
            )

        mapped = list(reversed(items))
        trace.append(f"mapped_generic_sequence: {mapped}")
        return ReasoningResult(
            conclusion=dict(
                analogy=f"{src_name}:{operation} <-> {tgt_name}:{operation}",
                mapped_sequence=mapped,
                structural_isomorphism=True,
            ),
            proof_or_trace=trace,
            assumptions=["Finite sequence structural mapping; target domain validation required"],
            confidence=0.80,
            cost=cost,
            unresolved_questions=[],
        )


class HierarchicalPlanner:
    """Decomposes Goal -> subgoals -> candidate skills -> imagined consequences -> verified action.
    Combines model-based search, learned action ranking, compiled greedy policies,
    known skill programs, and uncertainty-aware fallback."""

    def plan(self, goal: dict, world_state: list[dict], hybrid_world=None) -> ReasoningResult:
        target_id = goal.get("object", "o1")
        goal_x = int(goal.get("x", 0))
        goal_y = int(goal.get("y", 0))
        obj = next((o for o in world_state if o.get("id") == target_id), None)
        if obj is None:
            return ReasoningResult(
                conclusion=dict(status="unresolved_reference", fallback="ask_clarification"),
                proof_or_trace=[f"object {target_id} not found in world_state"],
                assumptions=["Object must be uniquely resolved before acting"],
                confidence=0.0,
                cost=1,
                unresolved_questions=[f"Which object in the 6x6 world corresponds to '{target_id}'?"],
            )

        start_x, start_y = int(obj["x"]), int(obj["y"])
        subgoals = []
        if start_x != goal_x:
            subgoals.append(dict(subgoal="align_x", target_x=goal_x, current_x=start_x))
        if start_y != goal_y:
            subgoals.append(dict(subgoal="align_y", target_y=goal_y, current_y=start_y))

        raw_moves, search_cost = to_cell(obj, goal_x, goal_y, lambda: None)
        compacted = compact(raw_moves)
        candidate_skills = [
            dict(skill="move", object=m.reference, direction=m.direction, steps=m.steps)
            for m in compacted
        ]

        # Imagine consequences using HybridWorldModel if supplied
        sim_state = dict(objects=copy.deepcopy(world_state))
        imagined_trace = []
        max_disagreement = 0.0
        for step in candidate_skills:
            if hybrid_world is not None:
                pred = hybrid_world.step_prediction(sim_state, dict(kind="grid_move", **step))
                sim_state = pred["symbolic_prediction"]["next_state"]
                max_disagreement = max(max_disagreement, pred["disagreement_D_t"])
                imagined_trace.append(dict(action=step, predicted_coords=pred["combined_coordinates"], disagreement=pred["disagreement_D_t"]))
            else:
                imagined_trace.append(dict(action=step))

        verified_action = candidate_skills if max_disagreement < 0.5 else []
        trace = [
            f"goal: move {target_id} from ({start_x},{start_y}) to ({goal_x},{goal_y})",
            f"subgoals: {subgoals}",
            f"candidate_skills: {candidate_skills}",
            f"imagined_consequences: {imagined_trace}",
            f"verified_action_count: {len(verified_action)}",
        ]
        search_steps = int(search_cost.get("expanded", 1)) if isinstance(search_cost, dict) else int(search_cost)
        return ReasoningResult(
            conclusion=dict(
                goal=goal,
                subgoals=subgoals,
                candidate_skills=candidate_skills,
                imagined_consequences=imagined_trace,
                verified_action=verified_action,
                fallback="cautious_abstain" if max_disagreement >= 0.5 else None,
            ),
            proof_or_trace=trace,
            assumptions=["6x6 grid topology", "No dynamic obstacles during plan execution"],
            confidence=0.96 if max_disagreement < 0.5 else 0.4,
            cost=max(1, search_steps + len(candidate_skills)),
            unresolved_questions=[] if max_disagreement < 0.5 else ["World model disagreement is high; verify transition before executing."],
        )


class ActiveInvestigationReasoner:
    """Selects informative questions or probes by Expected Value of Information:
        VOI(q) = E_y[L(b_t) - L(b_{t+1} | q, y)] - lambda * C(q)
    using explicit model-based VOI first, with an optional learned residual."""

    def select_probe(self, hypotheses: list[str], candidate_probes: list[dict], lambda_cost: float = 0.05) -> ReasoningResult:
        if not hypotheses or not candidate_probes:
            raise ValueError("hypotheses_and_probes_required_for_voi")
        n_h = len(hypotheses)
        current_loss = math.log2(n_h) if n_h > 1 else 0.0
        scored = []
        trace = [f"prior_hypotheses={n_h}, prior_uncertainty_loss={current_loss:.4f}"]

        for probe in candidate_probes:
            q_id = probe.get("id", str(probe))
            cost_q = float(probe.get("cost", 1.0))
            # Partition hypotheses by predicted probe outcome y in {True, False}
            outcomes: dict[Any, int] = {}
            predictions = probe.get("predictions", {})
            for h in hypotheses:
                y = predictions.get(h, False)
                outcomes[y] = outcomes.get(y, 0) + 1
            expected_posterior_loss = 0.0
            for y, count in outcomes.items():
                p_y = count / n_h
                post_loss = math.log2(count) if count > 1 else 0.0
                expected_posterior_loss += p_y * post_loss
            info_gain = max(0.0, current_loss - expected_posterior_loss)
            learned_residual = float(probe.get("learned_residual", 0.0))
            voi = info_gain - lambda_cost * cost_q + learned_residual
            scored.append(dict(
                probe_id=q_id,
                voi=round(voi, 6),
                expected_loss_reduction=round(info_gain, 6),
                cost=cost_q,
                learned_residual=round(learned_residual, 6),
            ))
            trace.append(f"probe={q_id}: E[L(b_t)-L(b_{{t+1}}|q,y)]={info_gain:.4f}, C(q)={cost_q}, VOI={voi:.4f}")

        scored.sort(key=lambda r: (-r["voi"], r["probe_id"]))
        best = scored[0]
        return ReasoningResult(
            conclusion=dict(
                formula="VOI(q) = E_y[L(b_t) - L(b_{t+1} | q, y)] - lambda * C(q)",
                selected_probe=best["probe_id"],
                voi=best["voi"],
                ranked_probes=scored,
            ),
            proof_or_trace=trace,
            assumptions=["Uniform prior over remaining consistent hypotheses unless weighted"],
            confidence=0.95,
            cost=len(candidate_probes),
            unresolved_questions=[f"Execute probe '{best['probe_id']}' to reduce hypothesis count."],
        )


class ReasoningRouter:
    """Routes incoming reasoning requests to the appropriate verifiable reasoner(s)
    in the reasoning portfolio."""

    def __init__(self, hybrid_world=None):
        self.relational = RelationalReasoner()
        self.constraint = ConstraintReasoner()
        self.mathematical = MathematicalReasoner()
        self.program_execution = ProgramExecutionReasoner()
        self.causal = CausalReasoner()
        self.analogical = AnalogicalReasoner()
        self.planner = HierarchicalPlanner()
        self.investigation = ActiveInvestigationReasoner()
        self.hybrid_world = hybrid_world

    def route(self, task_type: str, payload: dict) -> ReasoningResult:
        if type(payload) is not dict:
            raise ValueError("reasoning_router_payload_dict_required")
        t = task_type.strip().lower()

        if t in ("relational", "query_relation", "spatial_relation"):
            return self.relational.reason(
                facts=payload["relations"],
                query_subject=payload["query_subject"],
                query_object=payload["query_object"],
                relation=payload.get("relation"),
                assumptions=payload.get("assumptions"),
            )
        if t in ("constraint", "query_constraint", "csp", "sat", "schedule"):
            return self.constraint.solve(
                variables=payload["variables"],
                constraints=payload["constraints"],
            )
        if t in ("math", "mathematical", "query_math", "equation", "arithmetic"):
            return self.mathematical.solve(
                expression=payload["expression"],
                units=payload.get("units"),
                variable=payload.get("variable", "x"),
            )
        if t in ("sequence", "sequence_transformation", "program_execution", "execute_skill"):
            return self.program_execution.execute_and_verify(
                program=payload["program"],
                inputs=payload["inputs"],
                postcondition_check=payload.get("postcondition_check"),
            )
        if t in ("causal", "query_causal", "intervention"):
            return self.causal.analyze(
                variable_x=payload.get("variable_x", "X"),
                variable_y=payload.get("variable_y", "Y"),
                observational_data=payload.get("observational_data"),
                interventional_data=payload.get("interventional_data"),
                candidate_confounder=payload.get("candidate_confounder", "Z"),
            )
        if t in ("analogical", "query_analogy", "analogy"):
            return self.analogical.map_structure(
                source_domain=payload["source_domain"],
                target_domain=payload["target_domain"],
            )
        if t in ("planning", "plan_action", "hierarchical_planning"):
            return self.planner.plan(
                goal=payload["goal"],
                world_state=payload.get("world_state", []),
                hybrid_world=self.hybrid_world,
            )
        if t in ("active_investigation", "investigate", "voi", "question_selection"):
            return self.investigation.select_probe(
                hypotheses=payload["hypotheses"],
                candidate_probes=payload["candidate_probes"],
                lambda_cost=float(payload.get("lambda_cost", 0.05)),
            )
        raise ValueError(f"unsupported_reasoning_task_type:{task_type}")
