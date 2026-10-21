"""Real cross-lab transfer benchmark over the unified Session/SharedBrain/E1 Journal (Step 5).

Tests one shared executable representation across all four labs:
  1. Teach and verify a transformation through Language Lab;
  2. Invoke/transfer it with different surface wording in Coding Lab;
  3. Use it inside a multi-step Reasoning problem in Reasoning Lab;
  4. Apply it toward a 6x6 World Lab goal in World Lab.

Compares three regimes across 8 seeded multi-lab episodes:
  - shared_memory_transfer: unified Session/SharedBrain/E1 Journal across all 4 labs
  - scratch_learning: re-inducing from scratch (mode='enumerate') in each downstream lab
  - isolated_labs: separate Session per lab with no shared journal or skill library
"""
from pathlib import Path
from typing import Any

from nexus.evolution1.catalogue import canonical, digest
from .core import Session
from .shared_brain import SharedBrain
from . import skill_library as lib
from . import skill_programs as ir


CROSS_LAB_CURRICULUM = (
    dict(
        episode_id=1,
        name="canonseq",
        language_phrase="Teach 'canonseq' in Language Lab: sort numbers ascending and keep unique values.",
        coding_phrase="In Coding Lab, normalize sequence by ascending unique order.",
        reasoning_phrase="In Reasoning Lab, compare whether two sensor streams have identical canonical unique order.",
        world_phrase="In World Lab, move the red square to the goal coordinates derived from canonseq.",
        program=dict(schema="list", ops=["sort", "unique"]),
        teaching=[
            dict(input=[3, 1, 3, -2, 0], output=[-2, 0, 1, 3]),
            dict(input=[4, -1, 2, 4, 1], output=[-1, 1, 2, 4]),
            dict(input=[2, 5, 2, -3, 0], output=[-3, 0, 2, 5]),
        ],
        transfer_hint=[dict(input=[1, 2], output=[1, 2])],
        checks=[
            dict(input=[5, 0, -2, 5, 3], output=[-2, 0, 3, 5]),
            dict(input=[1, 6, 1, -3, 4], output=[-3, 1, 4, 6]),
        ],
        coding_inputs=[[4, 2, 4, 1, 5], [3, 0, 3, 2, 4]],
        reasoning_pair=([5, 2, 5, 1, 3], [3, 1, 2, 5, 1]),
        world_input=[4, 2, 4, 5, 2],
    ),
    dict(
        episode_id=2,
        name="flipstep",
        language_phrase="Teach 'flipstep' in Language Lab: increment each value by 1 and reverse the sequence.",
        coding_phrase="In Coding Lab, reverse the sequence after advancing every element by one.",
        reasoning_phrase="In Reasoning Lab, deduce the leading element after flipstep transformation.",
        world_phrase="In World Lab, route the blue circle to the flipstep target cell.",
        program=dict(schema="list", ops=["increment", "reverse"]),
        teaching=[
            dict(input=[1, 3, -2, 0], output=[1, -1, 4, 2]),
            dict(input=[4, -1, 2, 1], output=[2, 3, 0, 5]),
            dict(input=[2, 0, -3, 5], output=[6, -2, 1, 3]),
        ],
        transfer_hint=[dict(input=[1], output=[2])],
        checks=[
            dict(input=[0, -2, 4, 1], output=[2, 5, -1, 1]),
            dict(input=[3, 1, -4, 2], output=[3, -3, 2, 4]),
        ],
        coding_inputs=[[1, 4, 2, 3], [0, 2, 4, 1]],
        reasoning_pair=([2, 1, 4, 3], [0, 3, 1, 2]),
        world_input=[1, 2, 3, 4],
    ),
    dict(
        episode_id=3,
        name="evenstep",
        language_phrase="Teach 'evenstep' in Language Lab: filter even integers and increment each by 1.",
        coding_phrase="In Coding Lab, extract even items and advance each by one.",
        reasoning_phrase="In Reasoning Lab, determine parity-filtered shifted values across observations.",
        world_phrase="In World Lab, navigate the red square to the evenstep waypoint.",
        program=dict(schema="list", ops=["even", "increment"]),
        teaching=[
            dict(input=[2, 3, 4, 1, 6], output=[3, 5, 7]),
            dict(input=[-2, 5, 0, 4, 3], output=[-1, 1, 5]),
            dict(input=[1, 4, 2, 7, 0], output=[5, 3, 1]),
        ],
        transfer_hint=[dict(input=[2], output=[3])],
        checks=[
            dict(input=[6, 1, 2, 3, 4], output=[7, 3, 5]),
            dict(input=[0, 3, -4, 2, 5], output=[1, -3, 3]),
        ],
        coding_inputs=[[2, 5, 4, 1, 0], [4, 3, 2, 1, 6]],
        reasoning_pair=([2, 1, 4, 3, 6], [2, 5, 4, 7, 6]),
        world_input=[2, 1, 4, 3, 2],
    ),
    dict(
        episode_id=4,
        name="steporder",
        language_phrase="Teach 'steporder' in Language Lab: increment every element and sort ascending.",
        coding_phrase="In Coding Lab, produce sorted values after a +1 offset.",
        reasoning_phrase="In Reasoning Lab, verify minimum and maximum bounds under steporder.",
        world_phrase="In World Lab, move the blue circle to the steporder coordinates.",
        program=dict(schema="list", ops=["increment", "sort"]),
        teaching=[
            dict(input=[3, -1, 1, 0], output=[0, 1, 2, 4]),
            dict(input=[4, 0, -2, 2], output=[-1, 1, 3, 5]),
            dict(input=[1, 5, -3, 2], output=[-2, 2, 3, 6]),
        ],
        transfer_hint=[dict(input=[1, 2], output=[2, 3])],
        checks=[
            dict(input=[2, -2, 4, 0], output=[-1, 1, 3, 5]),
            dict(input=[5, 1, -1, 3], output=[0, 2, 4, 6]),
        ],
        coding_inputs=[[3, 0, 2, 1], [4, 1, 3, 0]],
        reasoning_pair=([3, 1, 2, 0], [2, 0, 3, 1]),
        world_input=[3, 1, 4, 2],
    ),
    dict(
        episode_id=5,
        name="evenset",
        language_phrase="Teach 'evenset' in Language Lab: keep only even numbers and remove duplicates.",
        coding_phrase="In Coding Lab, deduplicate even values while preserving first appearance.",
        reasoning_phrase="In Reasoning Lab, count distinct even magnitudes via evenset.",
        world_phrase="In World Lab, move the red square to the evenset goal cell.",
        program=dict(schema="list", ops=["even", "unique"]),
        teaching=[
            dict(input=[4, 1, 4, 2, 3, 2], output=[4, 2]),
            dict(input=[2, 5, 0, 2, 4, 0], output=[2, 0, 4]),
            dict(input=[-2, 3, -2, 6, 1, 4], output=[-2, 6, 4]),
        ],
        transfer_hint=[dict(input=[2, 4], output=[2, 4])],
        checks=[
            dict(input=[6, 2, 6, 1, 4, 2], output=[6, 2, 4]),
            dict(input=[0, 4, 3, 0, 2, 4], output=[0, 4, 2]),
        ],
        coding_inputs=[[4, 2, 4, 1, 2], [2, 4, 2, 3, 0]],
        reasoning_pair=([4, 1, 4, 2, 3], [4, 2, 4, 5, 2]),
        world_input=[4, 1, 4, 2, 2],
    ),
    dict(
        episode_id=6,
        name="stepset",
        language_phrase="Teach 'stepset' in Language Lab: increment elements by 1 and remove duplicates.",
        coding_phrase="In Coding Lab, shift elements by +1 and keep first-appearance unique values.",
        reasoning_phrase="In Reasoning Lab, check unique shifted invariants with stepset.",
        world_phrase="In World Lab, guide the blue circle to the stepset cell.",
        program=dict(schema="list", ops=["increment", "unique"]),
        teaching=[
            dict(input=[2, 0, 2, 3, 0], output=[3, 1, 4]),
            dict(input=[4, 1, 4, -1, 2], output=[5, 2, 0, 3]),
            dict(input=[1, 3, 1, 0, 3], output=[2, 4, 1]),
        ],
        transfer_hint=[dict(input=[1, 2], output=[2, 3])],
        checks=[
            dict(input=[3, 2, 3, 0, 2], output=[4, 3, 1]),
            dict(input=[0, 4, 0, 1, 2], output=[1, 5, 2, 3]),
        ],
        coding_inputs=[[2, 1, 2, 4, 1], [3, 0, 3, 2, 0]],
        reasoning_pair=([1, 3, 1, 2], [1, 3, 3, 2]),
        world_input=[2, 1, 2, 3, 1],
    ),
    dict(
        episode_id=7,
        name="descorder",
        language_phrase="Teach 'descorder' in Language Lab: sort numbers in descending order.",
        coding_phrase="In Coding Lab, rank sequence elements from largest to smallest.",
        reasoning_phrase="In Reasoning Lab, identify top-2 magnitudes using descorder.",
        world_phrase="In World Lab, move the red square to the descorder target coordinates.",
        program=dict(schema="list", ops=["sort", "reverse"]),
        teaching=[
            dict(input=[1, 4, -2, 3], output=[4, 3, 1, -2]),
            dict(input=[0, 5, 2, -1], output=[5, 2, 0, -1]),
            dict(input=[3, -3, 1, 4], output=[4, 3, 1, -3]),
        ],
        transfer_hint=[dict(input=[1, 2], output=[2, 1])],
        checks=[
            dict(input=[2, 6, 0, -1], output=[6, 2, 0, -1]),
            dict(input=[-2, 4, 1, 3], output=[4, 3, 1, -2]),
        ],
        coding_inputs=[[2, 5, 1, 4], [1, 3, 0, 4]],
        reasoning_pair=([1, 4, 2, 5], [5, 2, 4, 1]),
        world_input=[1, 4, 2, 3],
    ),
    dict(
        episode_id=8,
        name="uniqueflip",
        language_phrase="Teach 'uniqueflip' in Language Lab: deduplicate preserving first appearance, then reverse.",
        coding_phrase="In Coding Lab, reverse the first-occurrence deduplicated list.",
        reasoning_phrase="In Reasoning Lab, compare reversed unique trajectories via uniqueflip.",
        world_phrase="In World Lab, move the blue circle to the uniqueflip coordinates.",
        program=dict(schema="list", ops=["unique", "reverse"]),
        teaching=[
            dict(input=[3, 1, 3, 2, 0], output=[0, 2, 1, 3]),
            dict(input=[4, 2, 4, 1, 2], output=[1, 2, 4]),
            dict(input=[1, 5, 1, 3, 2], output=[2, 3, 5, 1]),
        ],
        transfer_hint=[dict(input=[1, 2], output=[2, 1])],
        checks=[
            dict(input=[2, 4, 2, 0, 3], output=[3, 0, 4, 2]),
            dict(input=[5, 1, 5, 2, 4], output=[4, 2, 1, 5]),
        ],
        coding_inputs=[[3, 2, 3, 1, 4], [4, 1, 4, 2, 3]],
        reasoning_pair=([2, 4, 2, 1, 3], [2, 4, 4, 1, 3]),
        world_input=[3, 2, 3, 4, 1],
    ),
)


def _goal_coords_from_output(out: list[int]) -> tuple[int, int]:
    if not out:
        return (2, 2)
    gx = abs(out[0]) % 6
    gy = abs(out[-1] if len(out) > 1 else out[0] + 1) % 6
    if (gx, gy) == (1, 1):
        gx = 4
    return gx, gy


def run_cross_lab_transfer_study() -> dict[str, Any]:
    """Execute the 8-episode cross-lab transfer benchmark comparing shared memory, scratch, and isolated labs."""
    episodes_out = []

    totals = {
        "shared_memory_transfer": dict(
            downstream_candidate_evaluations=0,
            downstream_correct=0,
            downstream_total=0,
            world_goals_reached=0,
        ),
        "scratch_learning": dict(
            downstream_candidate_evaluations=0,
            downstream_correct=0,
            downstream_total=0,
            world_goals_reached=0,
        ),
        "isolated_labs": dict(
            downstream_candidate_evaluations=0,
            downstream_correct=0,
            downstream_total=0,
            world_goals_reached=0,
        ),
    }

    for ep in CROSS_LAB_CURRICULUM:
        name = ep["name"]
        true_prog = ep["program"]
        ref_phrase = "o2" if ep["episode_id"] % 2 == 1 else "o3"

        # ------------------------------------------------------------------
        # Regime 1: shared_memory_transfer (single shared Session & SharedBrain)
        # ------------------------------------------------------------------
        shared_session = Session()
        shared_brain = SharedBrain(shared_session)

        # 1a. Teach and verify in Language Lab
        teach_res = shared_brain.request(
            dict(
                op="lab_teach",
                lab="language",
                name=name,
                schema="list",
                examples=ep["teaching"],
                mode="enumerate",
                supersedes=None,
            )
        )
        check_res = shared_brain.request(
            dict(
                op="lab_check",
                name=name,
                attempt=teach_res["result"]["attempt"],
                checks=ep["checks"],
            )
        )
        assert check_res["result"]["status"] == "accepted"

        # 1b. Coding Lab: transfer via reuse_first & execute on unseen coding inputs
        coding_rebind = shared_brain.request(
            dict(
                op="lab_teach",
                lab="coding",
                name=name + "code",
                schema="list",
                examples=ep["transfer_hint"],
                mode="reuse_first",
                supersedes=None,
            )
        )
        shared_coding_evals = lib.state(shared_session)["teaching"][coding_rebind["result"]["attempt"]][
            "candidate_evaluations"
        ]
        shared_coding_outs = [
            shared_brain.request(dict(op="lab_run", lab="coding", name=name, input=inp))["result"]["output"]
            for inp in ep["coding_inputs"]
        ]
        exp_coding_outs = [ir.run(true_prog, inp) for inp in ep["coding_inputs"]]
        shared_coding_ok = int(shared_coding_outs == exp_coding_outs)

        # 1c. Reasoning Lab: use shared representation to solve relational invariant query
        r_a, r_b = ep["reasoning_pair"]
        out_a = shared_brain.request(dict(op="lab_run", lab="reasoning", name=name, input=r_a))["result"]["output"]
        out_b = shared_brain.request(dict(op="lab_run", lab="reasoning", name=name, input=r_b))["result"]["output"]
        shared_reasoning_ans = (out_a == out_b, out_a[0] if out_a else None)
        exp_reasoning_ans = (
            ir.run(true_prog, r_a) == ir.run(true_prog, r_b),
            ir.run(true_prog, r_a)[0] if ir.run(true_prog, r_a) else None,
        )
        shared_reasoning_ok = int(shared_reasoning_ans == exp_reasoning_ans)

        # 1d. World Lab: compute goal cell using shared representation and execute world trajectory
        w_out = shared_brain.request(dict(op="lab_run", lab="world", name=name, input=ep["world_input"]))["result"][
            "output"
        ]
        gx, gy = _goal_coords_from_output(w_out)
        exp_gx, exp_gy = _goal_coords_from_output(ir.run(true_prog, ep["world_input"]))
        world_act = shared_brain.request(dict(op="lab_goal", reference=ref_phrase, x=gx, y=gy))
        shared_world_ok = int(
            (gx, gy) == (exp_gx, exp_gy) and world_act["result"]["status"] in ("acted", "already_at_goal")
        )

        shared_down_evals = shared_coding_evals  # 1 evaluation via reuse_first in Coding, 0 re-search in Reasoning/World
        totals["shared_memory_transfer"]["downstream_candidate_evaluations"] += shared_down_evals
        totals["shared_memory_transfer"]["downstream_correct"] += (
            shared_coding_ok + shared_reasoning_ok + shared_world_ok
        )
        totals["shared_memory_transfer"]["downstream_total"] += 3
        totals["shared_memory_transfer"]["world_goals_reached"] += shared_world_ok

        # ------------------------------------------------------------------
        # Regime 2: scratch_learning (enumerate from scratch in each downstream lab)
        # ------------------------------------------------------------------
        scratch_evals = 0
        scratch_correct = 0
        scratch_world_ok = 0
        for d_lab in ("coding", "reasoning", "world"):
            s_sess = Session()
            s_brain = SharedBrain(s_sess)
            t_res = s_brain.request(
                dict(
                    op="lab_teach",
                    lab=d_lab,
                    name=name,
                    schema="list",
                    examples=ep["teaching"],
                    mode="enumerate",
                    supersedes=None,
                )
            )
            t_rec = lib.state(s_sess)["teaching"][t_res["result"]["attempt"]]
            scratch_evals += t_rec["candidate_evaluations"]
            c_res = s_brain.request(
                dict(
                    op="lab_check",
                    name=name,
                    attempt=t_res["result"]["attempt"],
                    checks=ep["checks"],
                )
            )
            if c_res["result"]["status"] == "accepted":
                if d_lab == "coding":
                    outs = [
                        s_brain.request(dict(op="lab_run", lab="coding", name=name, input=inp))["result"]["output"]
                        for inp in ep["coding_inputs"]
                    ]
                    scratch_correct += int(outs == exp_coding_outs)
                elif d_lab == "reasoning":
                    oa = s_brain.request(dict(op="lab_run", lab="reasoning", name=name, input=r_a))["result"]["output"]
                    ob = s_brain.request(dict(op="lab_run", lab="reasoning", name=name, input=r_b))["result"]["output"]
                    scratch_correct += int((oa == ob, oa[0] if oa else None) == exp_reasoning_ans)
                else:
                    wo = s_brain.request(dict(op="lab_run", lab="world", name=name, input=ep["world_input"]))["result"][
                        "output"
                    ]
                    sgx, sgy = _goal_coords_from_output(wo)
                    w_act = s_brain.request(dict(op="lab_goal", reference=ref_phrase, x=sgx, y=sgy))
                    ok_w = int(
                        (sgx, sgy) == (exp_gx, exp_gy) and w_act["result"]["status"] in ("acted", "already_at_goal")
                    )
                    scratch_correct += ok_w
                    scratch_world_ok = ok_w

        totals["scratch_learning"]["downstream_candidate_evaluations"] += scratch_evals
        totals["scratch_learning"]["downstream_correct"] += scratch_correct
        totals["scratch_learning"]["downstream_total"] += 3
        totals["scratch_learning"]["world_goals_reached"] += scratch_world_ok

        # ------------------------------------------------------------------
        # Regime 3: isolated_labs (separate Session per lab; Language Lab skill
        # is invisible to Coding, Reasoning, and World Labs, leaving only a
        # single ambiguous example in each isolated downstream lab)
        # ------------------------------------------------------------------
        lang_isolated = Session()
        lang_brain = SharedBrain(lang_isolated)
        t_iso = lang_brain.request(
            dict(
                op="lab_teach",
                lab="language",
                name=name,
                schema="list",
                examples=ep["teaching"],
                mode="enumerate",
                supersedes=None,
            )
        )
        lang_brain.request(
            dict(op="lab_check", name=name, attempt=t_iso["result"]["attempt"], checks=ep["checks"])
        )

        iso_evals = 0
        iso_correct = 0
        iso_world_ok = 0
        for d_lab in ("coding", "reasoning", "world"):
            i_sess = Session()
            i_brain = SharedBrain(i_sess)
            # In isolated labs, the skill taught in Language Lab is absent from i_sess,
            # and a 1-example invocation in the isolated lab remains ambiguous (len(candidates) > 1).
            t_d = i_brain.request(
                dict(
                    op="lab_teach",
                    lab=d_lab,
                    name=name,
                    schema="list",
                    examples=ep["transfer_hint"],
                    mode="reuse_first",
                    supersedes=None,
                )
            )
            t_rec = lib.state(i_sess)["teaching"][t_d["result"]["attempt"]]
            iso_evals += t_rec["candidate_evaluations"]
            if t_d["result"]["candidate_count"] == 1:
                c_d = i_brain.request(
                    dict(op="lab_check", name=name, attempt=t_d["result"]["attempt"], checks=ep["checks"])
                )
                if c_d["result"]["status"] == "accepted":
                    iso_correct += 1
                    if d_lab == "world":
                        iso_world_ok = 1

        totals["isolated_labs"]["downstream_candidate_evaluations"] += iso_evals
        totals["isolated_labs"]["downstream_correct"] += iso_correct
        totals["isolated_labs"]["downstream_total"] += 3
        totals["isolated_labs"]["world_goals_reached"] += iso_world_ok

        episodes_out.append(
            dict(
                episode_id=ep["episode_id"],
                name=name,
                program=true_prog,
                shared_memory=dict(
                    downstream_evaluations=shared_down_evals,
                    downstream_accuracy=round((shared_coding_ok + shared_reasoning_ok + shared_world_ok) / 3.0, 6),
                    world_goal_reached=bool(shared_world_ok),
                    journal_events=len(shared_session.journal.snapshot()),
                ),
                scratch_learning=dict(
                    downstream_evaluations=scratch_evals,
                    downstream_accuracy=round(scratch_correct / 3.0, 6),
                    world_goal_reached=bool(scratch_world_ok),
                ),
                isolated_labs=dict(
                    downstream_evaluations=iso_evals,
                    downstream_accuracy=round(iso_correct / 3.0, 6),
                    world_goal_reached=bool(iso_world_ok),
                ),
            )
        )

    n_ep = len(CROSS_LAB_CURRICULUM)
    summary = {}
    for regime, row in totals.items():
        summary[regime] = dict(
            mean_downstream_evaluations=round(row["downstream_candidate_evaluations"] / n_ep, 6),
            total_downstream_evaluations=row["downstream_candidate_evaluations"],
            downstream_accuracy=round(row["downstream_correct"] / row["downstream_total"], 6),
            world_goal_completion_rate=round(row["world_goals_reached"] / n_ep, 6),
        )

    eval_reduction_vs_scratch = round(
        (
            summary["scratch_learning"]["mean_downstream_evaluations"]
            - summary["shared_memory_transfer"]["mean_downstream_evaluations"]
        )
        / summary["scratch_learning"]["mean_downstream_evaluations"],
        6,
    )
    acc_gain_vs_isolated = round(
        summary["shared_memory_transfer"]["downstream_accuracy"]
        - summary["isolated_labs"]["downstream_accuracy"],
        6,
    )

    return dict(
        schema="seed_cross_lab_transfer_v1",
        episodes=episodes_out,
        summary=summary,
        evaluation_reduction_vs_scratch=eval_reduction_vs_scratch,
        accuracy_gain_vs_isolated=acc_gain_vs_isolated,
        passed=(
            summary["shared_memory_transfer"]["downstream_accuracy"] == 1.0
            and summary["shared_memory_transfer"]["world_goal_completion_rate"] == 1.0
            and eval_reduction_vs_scratch >= 0.90
            and acc_gain_vs_isolated >= 0.50
        ),
    )
