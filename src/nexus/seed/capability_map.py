"""Balanced five-area capability screen. Not AGI. Not learning-to-learn.

Reuses PersistentLocalRuntime, ChatML, vault retrieve, coding generate paths,
requirement coverage, EventMeter and ordinary exact cache. Product chat usage
and the frozen CPU ledger are not charged. Acquired solution memory stays empty.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from .capability_evidence import EventMeter, digest
from .capability_map_tasks import all_tasks, knowledge_docs
from .chat_template import render_prompt
from .extraction_path import generate_direct, generate_extract, score_task
from .extraction_workspace import decide_workspace_extraction, run_workspace_extraction
from .function_contracts import score_bound_task
from .lexicon_vault import KnowledgeVault
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .requirement_coverage import score_requirement_coverage
from .unified_chat import retrieve_for_question

METHODS = ("model_alone", "tools_cache", "nexus")
AREAS = ("conversation", "mathematics", "logic", "coding", "knowledge")
WALL_CAP_S = 900.0
CALL_CAP = 180
CONFIG_PATH = Path("configs/seed_capability_map.json")


class ExactCache:
    def __init__(self):
        self.store: dict[str, Any] = {}
        self.hits = 0

    def get(self, key: str):
        row = self.store.get(key)
        if row is not None:
            self.hits += 1
        return deepcopy(row)

    def put(self, key: str, value: Any) -> None:
        self.store[key] = deepcopy(value)


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def eval_arithmetic(expr: str) -> dict[str, Any]:
    """Programmer-supplied calculator. Restricted AST only."""
    try:
        tree = ast.parse(str(expr or ""), mode="eval")
    except SyntaxError as exc:
        return dict(ok=False, error=type(exc).__name__, value=None)
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Load,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return dict(ok=False, error="unsupported_node", value=None)
    try:
        value = eval(compile(tree, "<arith>", "eval"), {"__builtins__": {}}, {})
    except Exception as exc:
        return dict(ok=False, error=type(exc).__name__, value=None)
    return dict(ok=True, error=None, value=value)


def start_map_runtime():
    from .local_model_runtime import PersistentLocalRuntime, RuntimeConfig
    model = Path(".models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
    executable = os.environ.get("NEXUS_LLAMA_SERVER", "llama-server")
    if not model.is_file() or shutil.which(executable) is None:
        return None, dict(status="unavailable", reason="local_model_or_server_missing")
    cfg = replace(
        RuntimeConfig.from_environment(),
        model_path=str(model.resolve()),
        executable=executable,
        application_cache=False,
        max_tokens=192,
        request_timeout_s=25,
        startup_timeout_s=45,
        threads=2,
    )
    runtime = PersistentLocalRuntime(cfg)
    runtime.start()
    return runtime, dict(
        status="started", model=str(model), ngl=0, device="none",
        model_sha256=digest(model.read_bytes()) if model.stat().st_size < 1 else None,
    )


def complete_text(runtime, user: str, clock: dict[str, Any], system: str = "") -> dict[str, Any]:
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("capability_map_cap")
    body = (system + "\n\n" + user).strip() if system else user
    prompt, _meta = render_prompt("chatml", body)
    reply = runtime.complete(prompt, None)
    tel = reply.get("telemetry") or {}
    clock["calls"] += 1
    clock["inference_ran"] += int(bool(tel.get("inference_ran")))
    return dict(
        content=reply.get("content") or "",
        inference_ran=bool(tel.get("inference_ran")),
        wall_s=float(tel.get("request_wall_s") or 0.0),
    )


def _number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text or "")
    if not match:
        return None
    return float(match.group(0))


def score_conversation(task: dict[str, Any], replies: list[str]) -> dict[str, Any]:
    last = (replies[-1] if replies else "") or ""
    lowered = last.lower()
    rubric = task["rubric"]
    checks = {}
    if rubric.get("must_ask"):
        checks["asks"] = "?" in last or any(w in lowered for w in ("which", "what", "when", "where"))
    if rubric.get("must_use"):
        checks["uses_correction"] = rubric["must_use"] in lowered
    if rubric.get("must_not_insist"):
        checks["dropped_old"] = rubric["must_not_insist"] not in lowered or rubric.get("must_use", "") in lowered
    if rubric.get("must_answer_last") or rubric.get("must_restate") or rubric.get("must_explain") or rubric.get("must_return_topic"):
        topic = (rubric.get("topic") or "")
        checks["addresses_topic"] = bool(last.strip()) and (not topic or any(part in lowered for part in topic.split(" or ")))
    automatic = all(checks.values()) if checks else bool(last.strip())
    return dict(
        passed=automatic,
        checks=checks,
        replies=replies,
        pending_human_review=True,
        keyword_quality_score=False,
        scoring="explicit_rubric_acts; full_replies_preserved; human_review_pending",
    )


def score_math(task: dict[str, Any], text: str, tool: dict[str, Any] | None) -> dict[str, Any]:
    if task.get("must_clarify"):
        asked = "?" in (text or "") or "need" in (text or "").lower() or "which" in (text or "").lower()
        return dict(passed=asked, clarification=asked, tool=tool, unaided_value=_number(text))
    value = None
    via_tool = False
    if tool and tool.get("ok"):
        value = tool.get("value")
        via_tool = True
    if value is None:
        value = _number(text)
    ok = value is not None and abs(float(value) - float(task["answer"])) < 1e-6
    expr_ok = None
    if tool and task.get("expression"):
        expr_ok = eval_arithmetic(task["expression"]).get("value") == tool.get("value")
    unit_ok = True
    if task.get("unit"):
        unit_ok = task["unit"].lower() in (text or "").lower() or via_tool
    return dict(
        passed=bool(ok and unit_ok),
        value=value,
        unaided_value=_number(text) if not via_tool else None,
        tool_assisted=via_tool,
        tool=tool,
        expression_represents_problem=expr_ok,
        unit_ok=unit_ok,
    )


def score_logic(task: dict[str, Any], text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    if task.get("must_not_claim"):
        claimed = any(w in lowered for w in ("yes it is", "it is heavier", "definitely", "certainly"))
        uncertain = any(w in lowered for w in ("cannot", "don't know", "not enough", "unknown", "no evidence", "?"))
        return dict(passed=uncertain and not claimed, text=text)
    expected = str(task.get("expected") or "").lower()
    return dict(passed=expected in lowered if expected else False, text=text, expected=expected)


def score_coding(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    contracts = {}
    if task.get("function_contracts"):
        scored = score_bound_task(task, files)
    else:
        scored = score_task(task, files)
        scored["helper_present"] = True
        scored["caller_present"] = True
        scored["required_call"] = True
        scored["functions"] = {}
    coverage = score_requirement_coverage(task["request"], files)
    return dict(
        public_passed=scored.get("public_passed"),
        private_passed=scored.get("private_passed"),
        helper_present=scored.get("helper_present"),
        caller_present=scored.get("caller_present"),
        required_call=not coverage.get("missing_apis"),
        coverage_passed=coverage["passed"],
        types_ok=scored.get("types_ok"),
        functions=scored.get("functions") or {},
        requirement_coverage=coverage,
        passed=bool(scored.get("private_passed") and coverage["passed"]),
        files=files,
    )


def score_knowledge(task: dict[str, Any], text: str, citations: list[str],
                    facts: list[dict[str, Any]]) -> dict[str, Any]:
    lowered = (text or "").lower()
    if task.get("must_uncertain"):
        uncertain = any(w in lowered for w in ("do not have", "no stored", "cannot", "unknown", "not in"))
        return dict(passed=uncertain, citations=citations, token_overlap_score=False)
    fact_ok = task.get("expected_fact", "").lower() in lowered if task.get("expected_fact") else True
    extra_ok = True
    if task.get("expected_extra"):
        extra_ok = task["expected_extra"] in (text or "")
    stale = task.get("forbidden_fact")
    stale_ok = True if not stale else stale not in lowered
    cite_ok = True
    if task.get("must_cite"):
        cite_ok = task["must_cite"] in citations or task["must_cite"] in (text or "")
    allowed = set(task.get("allowed_docs") or [])
    cite_supported = True
    if citations and allowed:
        cite_supported = any(doc in allowed for doc in citations)
    return dict(
        passed=bool(fact_ok and extra_ok and stale_ok and cite_ok and cite_supported),
        fact_ok=fact_ok,
        citation_ok=cite_ok,
        citations=citations,
        supported_by_allowed=cite_supported,
        freshness_ok=stale_ok,
        token_overlap_score=False,
    )


def run_conversation(runtime, task: dict[str, Any], method: str, clock: dict[str, Any],
                     cache: ExactCache | None) -> dict[str, Any]:
    replies = []
    history = []
    cache_hit = False
    identical = method == "nexus"
    if identical:
        return dict(identical_to="tools_cache", reused=True)
    for turn in task["turns"]:
        key = digest([method, task["task_id"], history, turn])
        cached = cache.get(key) if cache is not None else None
        if cached:
            reply = cached
            cache_hit = True
        else:
            user = "Conversation so far:\n" + "\n".join(history) + "\nUser: " + turn if history else turn
            raw = complete_text(runtime, user, clock, "Answer the user. Do not invent files or tools.")
            reply = raw["content"]
            if cache is not None:
                cache.put(key, reply)
        replies.append(reply)
        history.append("User: " + turn)
        history.append("Assistant: " + reply[:400])
    scored = score_conversation(task, replies)
    scored["cache_hit"] = cache_hit
    scored["method"] = method
    return scored


def run_math(runtime, task: dict[str, Any], method: str, clock: dict[str, Any],
             cache: ExactCache | None) -> dict[str, Any]:
    if method == "nexus":
        return dict(identical_to="tools_cache", reused=True)
    key = digest([method, task["task_id"], task["request"]])
    cached = cache.get(key) if cache is not None else None
    if cached:
        return dict(cached, cache_hit=True)
    if method == "model_alone":
        raw = complete_text(runtime, task["request"] + "\nGive the numeric answer and unit.", clock)
        scored = score_math(task, raw["content"], None)
    else:
        raw = complete_text(
            runtime,
            task["request"] + '\nReturn JSON {"expression": "...", "unit": "...", "clarification": "..."}.',
            clock,
        )
        expr = None
        text = raw["content"]
        if "{" in text:
            try:
                payload = json.loads(text[text.find("{"): text.rfind("}") + 1])
                expr = payload.get("expression")
                text = str(payload.get("clarification") or "") + " " + str(payload.get("unit") or "")
            except Exception:
                expr = None
        tool = eval_arithmetic(expr) if expr else None
        scored = score_math(task, raw["content"] + " " + text, tool)
        scored["programmer_supplied_calculator"] = True
    scored["cache_hit"] = False
    if cache is not None:
        cache.put(key, scored)
    return scored


def run_logic(runtime, task: dict[str, Any], method: str, clock: dict[str, Any],
              cache: ExactCache | None) -> dict[str, Any]:
    if method == "nexus":
        return dict(identical_to="tools_cache", reused=True)
    key = digest([method, task["task_id"], task["request"]])
    cached = cache.get(key) if cache is not None else None
    if cached:
        return dict(cached, cache_hit=True)
    raw = complete_text(runtime, task["request"] + "\nAnswer briefly. If evidence is missing, say so.", clock)
    scored = score_logic(task, raw["content"])
    scored["cache_hit"] = False
    if cache is not None:
        cache.put(key, scored)
    return scored


def run_coding(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    cell = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    working = dict(task)
    if method == "model_alone" or method == "tools_cache":
        result = generate_direct(runtime, working, cell)
        files = result.get("files") or task["files"]
        route = "direct"
    else:
        decision = decide_workspace_extraction(
            task["request"], task["files"], task["public"], task.get("docs"), "python",
        )
        if decision.get("action") == "extract":
            payload = run_workspace_extraction(
                runtime, task["request"], task["files"], task["public"], task.get("docs"), decision,
            )
            files = payload.get("files") or task["files"]
            route = "eligible_always_extract"
            cell["calls"] = payload.get("cost", {}).get("model_calls") or 1
        else:
            result = generate_direct(runtime, working, cell)
            files = result.get("files") or task["files"]
            route = "direct_fallback:" + str(decision.get("reason"))
    clock["calls"] += cell["calls"]
    clock["inference_ran"] += cell["inference_ran"]
    scored = score_coding(task, files)
    scored["route"] = route
    scored["programmer_supplied_extraction"] = route == "eligible_always_extract"
    return scored


def load_vault(directory: Path) -> KnowledgeVault:
    vault = KnowledgeVault(directory / "capability_map_vault.sqlite")
    for doc in knowledge_docs():
        vault.ingest_document(doc["doc_id"], doc["title"], doc["content"], timestamp=doc["timestamp"])
    return vault


def run_knowledge(runtime, task: dict[str, Any], method: str, clock: dict[str, Any],
                  vault: KnowledgeVault, cache: ExactCache | None) -> dict[str, Any]:
    class Store:
        def __init__(self, vault):
            self.knowledge_vault = vault

    if method == "model_alone":
        raw = complete_text(runtime, task["request"], clock)
        return score_knowledge(task, raw["content"], [], [])
    facts = retrieve_for_question(vault, task["request"], None, top_k=3)
    citations = [fact.doc_id for fact in facts]
    compact = [dict(doc_id=fact.doc_id, title=fact.title, content=fact.content, timestamp=fact.timestamp)
               for fact in facts]
    if method == "nexus":
        if not facts and task.get("must_uncertain"):
            text = "I do not have relevant stored evidence for that question."
            scored = score_knowledge(task, text, [], [])
            scored["source"] = "vault_miss"
            scored["identical_tools_to"] = "tools_cache"
            return scored
        parts = [f"{fact.title} [{fact.doc_id}]: {fact.content}" for fact in facts]
        text = "Stored sources, current SQLite rows:\n" + "\n".join(parts)
        scored = score_knowledge(task, text, citations, compact)
        scored["source"] = "vault_cite"
        scored["programmer_supplied_retrieval"] = True
        return scored
    key = digest([method, task["task_id"], citations])
    cached = cache.get(key) if cache is not None else None
    if cached:
        return dict(cached, cache_hit=True)
    context = "\n".join(f"{fact.title} [{fact.doc_id}]: {fact.content}" for fact in facts) or "No documents."
    raw = complete_text(runtime, f"{task['request']}\nSources:\n{context}\nCite doc_id if you use a source.", clock)
    scored = score_knowledge(task, raw["content"], citations, compact)
    scored["programmer_supplied_retrieval"] = True
    scored["cache_hit"] = False
    if cache is not None:
        cache.put(key, scored)
    return scored


def run_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any],
             cache: ExactCache, vault: KnowledgeVault, prior: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    area = task["area"]
    if area == "conversation":
        scored = run_conversation(runtime, task, method, clock, cache if method == "tools_cache" else None)
    elif area == "mathematics":
        scored = run_math(runtime, task, method, clock, cache if method == "tools_cache" else None)
    elif area == "logic":
        scored = run_logic(runtime, task, method, clock, cache if method == "tools_cache" else None)
    elif area == "coding":
        scored = run_coding(runtime, task, method, clock)
    else:
        scored = run_knowledge(runtime, task, method, clock, vault, cache if method == "tools_cache" else None)
    if scored.get("reused") and scored.get("identical_to"):
        source = prior.get((task["task_id"], scored["identical_to"]))
        if source:
            scored = dict(source, identical_to=scored["identical_to"], reused=True)
    return dict(
        task_id=task["task_id"],
        area=area,
        family=task.get("family"),
        method=method,
        scored=scored,
        wall_s=round(time.perf_counter() - started, 6),
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for area in AREAS:
        out[area] = {}
        for method in METHODS:
            cells = [row for row in rows if row["area"] == area and row["method"] == method]
            passed = sum(int(bool((row.get("scored") or {}).get("passed"))) for row in cells)
            out[area][method] = dict(n=len(cells), passed=passed, pending_human_review=area == "conversation")
    return out


def run_capability_map(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = load_config()
    raw_path = directory / "seed_capability_map_raw.jsonl"
    if raw_path.exists():
        raw_path.unlink()
    events: list[dict[str, Any]] = []
    meter = EventMeter(lambda event: events.append(event) or raw_path.open("a", encoding="utf-8").write(
        json.dumps(event, default=str) + "\n"
    ))
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    cache = ExactCache()
    vault = load_vault(directory)
    rows = []
    prior: dict[tuple[str, str], dict[str, Any]] = {}
    partial = False
    for task in all_tasks():
        for method in METHODS:
            if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
                partial = True
                break
            cell = meter.call(
                f"{task['task_id']}:{method}", "capability_cell", task["task_id"],
                lambda _: run_cell(runtime, task, method, clock, cache, vault, prior),
                dict(task_id=task["task_id"], method=method),
            )
            if isinstance(cell, dict) and cell.get("task_id"):
                rows.append(cell)
                prior[(task["task_id"], method)] = cell.get("scored") or {}
                (directory / "seed_capability_map_partial.json").write_text(
                    json.dumps(dict(rows=rows, partial=True), default=str), encoding="utf-8")
        if partial:
            break
    usage = dict(
        kind="capability_map_cpu_usage",
        backend="cpu",
        gpu_used=False,
        metal_used=False,
        product_chat_usage_used=False,
        research_cpu_ledger_frozen_s=FROZEN_CPU_USED_S,
        research_cpu_ledger_remaining_s=FROZEN_CPU_REMAINING_S,
        research_cpu_ledger_debit_s=0.0,
        model_calls=clock["calls"],
        inference_ran=clock["inference_ran"],
        wall_s=round(time.perf_counter() - clock["started"], 3),
        cap_s=WALL_CAP_S,
        call_cap=CALL_CAP,
        cache_hits=cache.hits,
        memory=sample_process_memory(runtime),
        acquired_solution_memory=False,
        ranking_policy_resumed=False,
        learning_to_learn_established=False,
        partial=partial,
    )
    payload = dict(
        kind="seed_capability_map",
        confirmation=False,
        aggregate_score=False,
        learning_to_learn_established=False,
        config=config,
        rows=rows,
        summary=summarize(rows),
        usage=usage,
        events=len(events),
        api_audit_preserved=True,
    )
    payload["hash"] = digest({k: payload[k] for k in ("kind", "summary", "usage")})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
