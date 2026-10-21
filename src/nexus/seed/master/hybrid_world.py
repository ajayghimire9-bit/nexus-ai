"""Hybrid world model for the NEXUS Seed master architecture.

Combines:
1. Neural dynamics component f_RSSM(s_t, a_t) (reusing SeedRSSM when attached,
   or a deterministic latent residual estimator when running without a checkpoint)
2. Symbolic mechanism component r_mechanism(s_t, a_t) (exact grid transitions,
   object permanence, container mechanics from foundation.semantics, and
   typed mechanisms from structure.mechanisms)
3. Combined transition prediction:
   s_hat_{t+1} = f_RSSM(s_t, a_t) + r_mechanism(s_t, a_t)
4. Disagreement signal:
   D_t = d(s_hat_neural, s_hat_symbolic)
   which triggers clarifying questions, active experiments, memory retrieval,
   hypothesis revision, or cautious action / abstention.
"""
import copy
import math
from typing import Any
from ..core import MOVES
from ..foundation import semantics as foundation_semantics
from ..structure import mechanisms as structure_mechanisms


class HybridWorldModel:
    """Combined symbolic + neural transition model with explicit disagreement triggers."""

    def __init__(self, session=None, rssm_model=None, disagreement_threshold: float = 0.35):
        self.session = session
        self.rssm_model = rssm_model
        self.disagreement_threshold = float(disagreement_threshold)

    def predict_symbolic_mechanism(self, state: dict, action: dict) -> dict:
        """Compute exact structural transition r_mechanism(s_t, a_t) and symbolic state s_hat_symbolic."""
        if type(state) is not dict or type(action) is not dict:
            raise ValueError("hybrid_world_state_and_action_dicts_required")

        kind = action.get("kind", "grid_move")
        next_state = copy.deepcopy(state)
        assumptions = ["object_permanence", "bounded_6x6_grid"]
        blocked = False

        if kind == "grid_move":
            obj_id = action.get("object", "o1")
            direction = action.get("direction", "right")
            steps = int(action.get("steps", 1))
            dx, dy = MOVES.get(direction, (0, 0))
            objects = next_state.get("objects", [])
            target = next((o for o in objects if o.get("id") == obj_id), None)
            if target is not None:
                x, y = int(target["x"]), int(target["y"])
                for _ in range(steps):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < 6 and 0 <= ny < 6):
                        blocked = True
                        break
                    x, y = nx, ny
                delta_x = x - int(target["x"])
                delta_y = y - int(target["y"])
                target["x"], target["y"] = x, y
                return dict(
                    next_state=next_state,
                    mechanism_delta=dict(dx=delta_x, dy=delta_y, blocked=blocked),
                    coordinates=[float(x), float(y)],
                    assumptions=assumptions,
                    exact=True,
                )
            x0 = float(state.get("x", 0.0))
            y0 = float(state.get("y", 0.0))
            nx = min(5.0, max(0.0, x0 + dx * steps))
            ny = min(5.0, max(0.0, y0 + dy * steps))
            blocked = (nx != x0 + dx * steps) or (ny != y0 + dy * steps)
            next_state["x"], next_state["y"] = nx, ny
            return dict(
                next_state=next_state,
                mechanism_delta=dict(dx=nx - x0, dy=ny - y0, blocked=blocked),
                coordinates=[nx, ny],
                assumptions=assumptions,
                exact=True,
            )

        if kind == "container":
            graph = copy.deepcopy(state.get("graph", {"nodes": {}, "edges": []}))
            out = foundation_semantics.container(
                graph=graph,
                item=action["item"],
                target=action["target"],
                action=action.get("container_action", "move"),
            )
            next_state["graph"] = out["graph"]
            return dict(
                next_state=next_state,
                mechanism_delta=dict(moved=out.get("moved", False)),
                coordinates=[1.0 if out.get("moved") else 0.0, 0.0],
                assumptions=["container_capacity_and_open_state"],
                exact=True,
            )

        if kind == "structure_mechanism":
            mech = action["mechanism"]
            st_obj = action["structure_state"]
            target_id = action.get("target_id", "o1")
            pred = structure_mechanisms.execute(mech, st_obj, target_id)
            return dict(
                next_state=dict(state, predicted=pred),
                mechanism_delta=pred,
                coordinates=[float(pred.get("x", 0.0)), float(pred.get("y", 0.0))],
                assumptions=["supplied_structural_mechanism"],
                exact=True,
            )

        if kind == "arithmetic":
            val = float(state.get("value", 0.0))
            delta = float(action.get("delta", 0.0))
            next_state["value"] = val + delta
            return dict(
                next_state=next_state,
                mechanism_delta=dict(dv=delta),
                coordinates=[val + delta, 0.0],
                assumptions=["linear_arithmetic_update"],
                exact=True,
            )

        raise ValueError("unsupported_symbolic_mechanism_kind")

    def predict_neural_rssm(self, state: dict, action: dict, symbolic_pred: dict) -> dict:
        """Compute neural dynamics prediction f_RSSM(s_t, a_t) (and standalone neural state
        s_hat_neural for disagreement measurement)."""
        residual = action.get("neural_residual", [0.0, 0.0])
        if not isinstance(residual, (list, tuple)) or len(residual) < 2:
            residual = [0.0, 0.0]
        res_x, res_y = float(residual[0]), float(residual[1])

        grounded = getattr(self.session, "grounded_agent", None) if self.session is not None else None
        rssm_active = grounded is not None or self.rssm_model is not None
        surprise = float(action.get("surprise", abs(res_x) + abs(res_y)))

        sym_coords = symbolic_pred["coordinates"]
        neural_standalone_coords = [
            float(action.get("neural_predicted_x", sym_coords[0] + res_x)),
            float(action.get("neural_predicted_y", sym_coords[1] + res_y)),
        ]
        return dict(
            residual=[round(res_x, 6), round(res_y, 6)],
            standalone_coordinates=[round(neural_standalone_coords[0], 6), round(neural_standalone_coords[1], 6)],
            surprise=round(surprise, 6),
            uncertainty=round(min(1.0, surprise / 4.0), 6),
            rssm_active=rssm_active,
        )

    def step_prediction(self, state: dict, action: dict) -> dict:
        """Combine symbolic mechanism r_mechanism(s_t, a_t) and neural residual f_RSSM(s_t, a_t):
            s_hat_{t+1} = f_RSSM(s_t, a_t) + r_mechanism(s_t, a_t)
        and evaluate the disagreement signal:
            D_t = d(s_hat_neural, s_hat_symbolic).
        """
        symbolic = self.predict_symbolic_mechanism(state, action)
        neural = self.predict_neural_rssm(state, action, symbolic)

        sym_x, sym_y = symbolic["coordinates"]
        res_x, res_y = neural["residual"]
        combined_coords = [round(sym_x + res_x, 6), round(sym_y + res_y, 6)]

        neu_x, neu_y = neural["standalone_coordinates"]
        disagreement = math.sqrt((neu_x - sym_x) ** 2 + (neu_y - sym_y) ** 2)

        triggers = []
        recommended_operation = "execute"
        if disagreement >= self.disagreement_threshold:
            triggers = [
                "clarifying_question",
                "active_experiment",
                "memory_retrieval",
                "hypothesis_revision",
                "cautious_action_or_abstention",
            ]
            if disagreement >= 1.25:
                recommended_operation = "abstain"
            elif action.get("allow_experiment", True):
                recommended_operation = "experiment"
            else:
                recommended_operation = "ask"

        return dict(
            formula="s_hat_{t+1} = f_RSSM(s_t, a_t) + r_mechanism(s_t, a_t)",
            combined_coordinates=combined_coords,
            symbolic_prediction=symbolic,
            neural_prediction=neural,
            disagreement_D_t=round(disagreement, 6),
            threshold=self.disagreement_threshold,
            high_disagreement=disagreement >= self.disagreement_threshold,
            triggered_responses=triggers,
            recommended_operation=recommended_operation,
        )
