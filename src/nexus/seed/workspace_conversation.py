"""Local file/procedure workspace over the existing Conversation and Session journal.

Reuses assistant_benchmark_v2 skeletons, ParameterizedAdapterTemplate capsules,
PersistentLocalRuntime and ExecutionBackedResponseRenderer. No generated-Python
execution path and no second memory store. Persistence is not learning-to-learn.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path

from nexus.evolution1.catalogue import digest

from .assistant_benchmark_v2 import SCHEMA, bind, intent_prompt, skeleton, validate_intent
from .real_data_adapter_learning import (ExecutionBackedResponseRenderer, ParameterizedAdapterTemplate,
    SchemaProfileAndBindingValidator)

CHAT_SYSTEM = (
    'You are NEXUS Seed, a local assistant. Answer conversationally from this prompt only. '
    'You cannot run tools or change files from this prompt. Do not claim a file was written, '
    'a program ran, or a procedure was saved. If the user wants a spreadsheet transform, say '
    'they should name a local CSV and ask for grouped totals or individual rows. '
    'When asked what you can do or help with, always name the registered capabilities from the '
    'workspace header (finite object teaching, CSV grouped totals or individual rows with inclusive '
    'minimum, and bounded coding loop on an allowed workspace where public tests are not complete correctness). '
    'When grounded workspace documents are provided in the prompt, cite their exact facts and formulas. '
    'If the workspace header names a pending clarification AND the user is answering it, ask that question. '
    'If the user changed topic, cancelled, corrected course, or made an unsupported request, '
    'do not repeat the old clarification. '
    'Describe the actual selected file or coding workspace when asked; do not invent files.'
)


def workspace_context_header(store, ws) -> tuple[str, dict]:
    """Build a header from registered capabilities and live workspace state.

    The header costs no generation tokens. It still consumes model input tokens.
    """
    capabilities = [
        'finite object teaching',
        'CSV grouped totals or individual rows',
        'bounded coding loop on an allowed workspace',
    ]
    coding = []
    runtime = {'available': False, 'reason': None}
    if store is not None:
        listing = getattr(store, 'list_coding_workspaces', None)
        if callable(listing):
            coding = list(listing() or [])
        status = getattr(store, 'runtime_status', None)
        if callable(status):
            runtime = status() or runtime
    pending = ws.get('pending_clarification') if isinstance(ws, dict) else None
    selected_file = (ws or {}).get('selected_file') if isinstance(ws, dict) else None
    selected_coding = (ws or {}).get('selected_coding_workspace') if isinstance(ws, dict) else None
    last_tool = (ws or {}).get('last_correction') if isinstance(ws, dict) else None
    header = (
        'Workspace state (generated from the store, not model output):\n'
        '- registered capabilities: '+', '.join(capabilities)+'\n'
        '- local model available: '+str(bool(runtime.get('available')))+'\n'
        '- selected file: '+(selected_file or 'none')+'\n'
        '- selected coding workspace: '+(selected_coding or 'none')+'\n'
        '- allowed coding workspaces: '+(', '.join(coding) if coding else 'none')+'\n'
        '- pending clarification: '+(json.dumps(pending) if pending else 'none')+'\n'
        '- last tool result: '+(str(last_tool) if last_tool else 'none')+'\n'
    )
    words = max(1, len(header.split()))
    return header, {
        'generated_from': 'registered_capabilities_and_workspace',
        'input_token_estimate': words,
        'generation_tokens': 0,
        'consumes_model_input_tokens': True,
        'selected_file': selected_file,
        'selected_coding_workspace': selected_coding,
        'pending_clarification': pending,
        'allowed_coding_workspaces': coding,
    }


def score_workspace_reply(text: str, ws: dict, header_meta: dict | None = None) -> dict:
    """Score real-state description and the needed question, not a header keyword."""
    text = text or ''
    lowered = text.lower()
    selected = (ws or {}).get('selected_coding_workspace') or (ws or {}).get('selected_file')
    pending = (ws or {}).get('pending_clarification') or {}
    needed = None
    if isinstance(pending, dict):
        needed = pending.get('detail') or pending.get('kind')
    repeats_header_keyword = 'workspace state (generated' in lowered
    names_selected = (
        (bool(selected) and str(selected) in text)
        or (
            not selected
            and not repeats_header_keyword
            and any(
                phrase in lowered
                for phrase in (
                    'selected resource: none',
                    'no coding workspace is selected',
                    'no workspace is selected',
                    'no file is selected',
                    'coding workspace is not selected',
                    'selected file: none',
                )
            )
        )
    )
    asks_needed = bool(needed) and (
        str(needed).lower() in lowered or
        ('which' in lowered and ('workspace' in lowered or 'file' in lowered or 'csv' in lowered)) or
        ('what' in lowered and ('fix' in lowered or 'change' in lowered or 'workspace' in lowered))
    )
    return {
        'names_selected_resource': names_selected,
        'asks_needed_question': asks_needed if needed else None,
        'repeats_header_keyword_only': repeats_header_keyword and not names_selected and not asks_needed,
        'header_input_token_estimate': (header_meta or {}).get('input_token_estimate'),
        'scoring': 'real_state_and_needed_question; not_header_keyword',
    }
UNSAFE = ('delete my', 'rm -', 'os.system', '__import__', 'buy stock', 'buy stocks',
          'send email', 'http://', 'https://', 'eval(', 'exec(', 'subprocess', 'format disk')
OUTSIDE_TOOLS = (
    'book me', 'book a flight', 'book a hotel', 'order a pizza', 'buy me a',
)
CANCEL_PENDING = (
    'never mind', 'forget that', 'forget it', 'cancel that', 'drop that',
    'stop asking', 'nevermind',
)
DATA_SUM = ('summarize', 'summary', 'totals', 'total ', 'grouped', 'group by', 'per region', 'by region')
DATA_ROWS = ('individual', 'records', 'row-level', 'each row', 'line item', 'list the', 'list records')
ORDER_ASC = ('smallest', 'ascending', 'low to high')
ORDER_DESC = ('largest', 'descending', 'high to low')
REPEAT = ('same for', 'do the same', 'same thing', 'again for', 'same procedure', 'repeat that', 'repeat it')
CHANGED = ('what did you change', 'what changed', 'what did you do differently', 'what did we change')
SAVE_PROC = ('save this procedure', 'save the procedure', 'save that procedure', 'keep this procedure')
INSPECT_PROC = ('inspect the procedure', 'show the procedure', 'show saved procedure', 'inspect saved procedure',
                'list procedures', 'list saved procedures')
REUSE_PROC = ('reuse the procedure', 'reuse saved', 'apply the saved', 'run the saved procedure',
              'use the saved procedure')
DELETE_PROC = ('delete the procedure', 'delete the saved procedure', 'delete saved procedure',
               'remove the saved procedure', 'remove the procedure')
FILE_HINT = ('use file', 'open file', 'load file', 'select file', 'this file', 'that file', 'other file')
PATH_RE = re.compile(r'"([^"\n]+\.csv)"|\'([^\'\n]+\.csv)\'|(\S+\.csv)', re.I)
SUPPORTED_MIN = re.compile(r'(?:at least|minimum|min(?:imum)?(?: of)?|no less than)\s+(-?\d+(?:\.\d+)?)')
UNSUPPORTED_PATTERNS = (
    (r'\bbelow\b', 'below/under comparison'),
    (r'\bunder\b', 'below/under comparison'),
    (r'\bless than\b', 'less-than comparison'),
    (r'\bat most\b', 'maximum comparison'),
    (r'\bno more than\b', 'maximum comparison'),
    (r'\bgreater than\b', 'exclusive greater-than comparison'),
    (r'\bmore than\b', 'exclusive greater-than comparison'),
    (r'\babove\b', 'exclusive greater-than comparison'),
    (r'\bbetween\b', 'range comparison'),
    (r'\bexcept\b', 'negation/exclusion'),
    (r'\bwithout\b', 'negation/exclusion'),
    (r'\bexcluding\b', 'negation/exclusion'),
    (r'\bnot\b', 'negation'),
    (r'\bmaximum\b', 'maximum comparison'),
    (r'\bequal to\b', 'equality filter'),
)
CORRECTION_PREFIX = ('actually', 'instead', 'no,', 'wait', 'no ')


@dataclass
class ParsedRequest:
    relation: str
    grain: str | None = None
    minimum: float | None = None
    minimum_stated: bool = False
    order: str | None = None
    order_stated: bool = False
    unsupported: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    understood: bool = False


def parse_request(text, last_intent=None):
    """Parse supported constraints explicitly. Keyword grain is not sufficient understanding."""
    raw = text.strip()
    t = re.sub(r'\s+', ' ', raw.lower()).strip(' .!?')
    paths = []
    for match in PATH_RE.finditer(raw):
        token = next(group for group in match.groups() if group)
        paths.append(token)
    unsupported = [label for token, label in UNSUPPORTED_PATTERNS if re.search(token, t)]
    unsupported = list(dict.fromkeys(unsupported))
    grain = None
    if any(p in t for p in DATA_ROWS) or ('rows' in t and 'group' not in t):
        grain = 'rows'
    elif any(p in t for p in DATA_SUM):
        grain = 'sum'
    order = None
    has_asc = any(p in t for p in ORDER_ASC) or re.search(r'\basc\b', t)
    has_desc = any(p in t for p in ORDER_DESC) or re.search(r'\bdesc\b', t)
    conflicts = []
    if has_asc and has_desc:
        conflicts.append('conflicting_order')
    elif has_asc:
        order = 'asc'
    elif has_desc:
        order = 'desc'
    minimum = None
    bound = SUPPORTED_MIN.search(t)
    if bound:
        minimum = float(bound.group(1))
    if len(paths) > 1 and not any(p in t for p in REPEAT):
        conflicts.append('multiple_files')
    repeating = any(p in t for p in REPEAT)
    correcting = t.startswith(CORRECTION_PREFIX) or (
        last_intent is not None and grain is None and (order is not None or bound is not None)
        and not repeating)
    file_only = bool(paths) and grain is None and not repeating and not correcting and (
        any(p in t for p in FILE_HINT) or t.endswith('.csv') or t.startswith(('use ', 'open ', 'load ', 'select ')))
    if repeating:
        relation = 'repeat'
    elif correcting:
        relation = 'correction'
    elif grain is not None:
        relation = 'fresh'
    elif file_only:
        relation = 'file_only'
    else:
        relation = 'unknown'
    understood = (
        not unsupported and not conflicts and (
            relation in ('repeat', 'correction', 'file_only') or
            (relation == 'fresh' and grain in ('sum', 'rows'))))
    return ParsedRequest(relation=relation, grain=grain, minimum=minimum, minimum_stated=bound is not None,
                         order=order, order_stated=order is not None, unsupported=unsupported,
                         conflicts=conflicts, paths=paths, understood=understood)


def abstract_executed_ast(ops, bindings):
    """Turn the executed program into a reusable parameterized AST. Does not rebuild a skeleton."""
    reverse = {}
    if bindings:
        if bindings.get('metric_col'):
            reverse[str(bindings['metric_col'])] = '$METRIC_COL'
        if bindings.get('key_col'):
            reverse[str(bindings['key_col'])] = '$KEY_COL'

    def walk(value, parent=None):
        if type(value) is dict:
            return {key: ('$THRESHOLD' if key == 'threshold' else walk(child, key)) for key, child in value.items()}
        if type(value) is list:
            return [walk(item, parent) for item in value]
        return reverse.get(value, value) if type(value) is str else value

    return walk(ops)


def publish_json(path, payload, cancelled=None, after_tmp=None):
    """Write to a temporary file, then atomically publish. Remove temps on cancel/error.

    Cancellation after os.replace has committed the output; the caller must not
    describe that as an undone action.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp-' + secrets.token_hex(4))
    try:
        if cancelled and cancelled():
            raise ValueError('cancel')
        tmp.write_text(json.dumps(payload, allow_nan=False, indent=2), encoding='utf-8')
        if after_tmp is not None:
            after_tmp(tmp)
        if cancelled and cancelled():
            raise ValueError('cancel')
        os.replace(tmp, path)
        return 'committed'
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _load_coding_workspace(root: Path):
    files = {}
    public_tests = []
    docs = []
    language = 'python'
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name.startswith('.'):
            continue
        rel = str(path.relative_to(root)).replace('\\', '/')
        if any(part.startswith('.') for part in Path(rel).parts):
            continue
        if path.stat().st_size > 20_000:
            continue
        text = path.read_text(encoding='utf-8')
        if path.name == 'public_tests.json':
            public_tests = json.loads(text)
            continue
        if path.name == 'docs.json':
            docs = json.loads(text)
            continue
        files[rel] = text
        if rel.endswith(('.ts', '.tsx')):
            language = 'typescript'
    return files, public_tests, docs, language


def _present_coding_result(card, res, proposal=None):
    model_calls = [c for c in res.get('tool_calls', []) if str(c.get('tool_name', '')).startswith('local_model')]
    model_status = (model_calls[-1]['outcome_summary'] if model_calls else
                    {'status': 'not_requested'})
    public_passed = bool(res.get('public_tests_passed'))
    card('Model proposal', dict(
        source='coding_loop',
        executed=False,
        status=model_status.get('status'),
        reason=model_status.get('reason'),
        inference_ran=model_status.get('inference_ran'),
        assumptions=model_status.get('assumptions', []),
    ))
    card('Applied workspace edit', dict(
        source='coding_loop',
        executed=bool(res.get('final_diff')),
        operator=res.get('applied_operator'),
        files=sorted(res.get('final_diff', {})),
    ))
    card('Public-test outcome', dict(
        source='coding_loop',
        executed=True,
        outcome=res.get('outcome_category'),
        public_tests_passed=public_passed,
        complete_correctness=False,
        attempts=len(res.get('patch_attempts', [])),
        summary=res.get('summary_message', '')[:400],
    ))
    card('Unverified assumptions', dict(
        assumptions=res.get('unverified_assumptions') or [
            'Passing public tests is not proof of complete correctness.',
        ],
        executed=False,
    ))
    diffs = res.get('final_diff') or {}
    truncated = {k: v[:800] for k, v in list(diffs.items())[:4]}
    card('Final diff', dict(executed=bool(diffs), files=sorted(diffs), diff=truncated))
    status = 'success' if res.get('outcome_category') == 'solved' else (
        'clarification' if res.get('outcome_category') in ('rejected', 'blocked') else 'error'
    )
    return (
        f"Coding loop finished with `{res.get('outcome_category')}`: {res.get('summary_message', '')} "
        'Public tests are not a private-test proof. I did not claim an edit executed unless a worker applied it.'
    ), status, False


def handle(conversation, intent, ctx, card, text):
    """Return (reply, status, save) or None to keep the finite teaching path."""
    if conversation.store is None:
        return None
    if intent.kind == 'help':
        return _help(conversation, card)
    if intent.kind != 'unsupported':
        return None
    return WorkspaceTurn(conversation, ctx, card, text).dispatch()


def _help(conversation, card):
    status = conversation.store.runtime_status()
    model = 'A local pretrained model is attached for ordinary chat.' if status['available'] else (
        'Ordinary chat needs a local GGUF model and llama-server; they are not available'
        + (': '+status['reason'] if status['reason'] else '.')
    )
    card('Supported workspace actions', [
        'Name a local CSV, then ask for grouped totals or individual rows.',
        'Supported numeric filter: inclusive minimum only. Other comparisons are asked about, not guessed.',
        'A fresh request does not inherit the last threshold or sort. Say “do the same” to repeat.',
        'Save stores the executed AST. Restart keeps explicit saves. Persistence is not learning-to-learn.',
        'Say “use coding workspace <name>” then describe a coding task. Public-test results are not complete correctness.',
    ])
    return (
        'I can teach finite object words and list programs, move objects on the 6×6 world, '
        'run two vetted CSV transforms, and run a bounded coding loop on an allowed repository '
        'workspace. Only an inclusive minimum and one sort direction are executable CSV '
        'constraints. '+model+' Saving a procedure stores the executed AST; that is reuse, not '
        'learning-to-learn. Passing public tests is not proof of complete correctness.'
    ), 'reply', False


class WorkspaceTurn:
    def __init__(self, conversation, ctx, card, text):
        self.conversation = conversation
        self.session = conversation.session
        self.store = conversation.store
        self.ctx = ctx
        self.ws = ctx['workspace']
        self.card = card
        self.raw = text
        self.text = re.sub(r'\s+', ' ', text.strip().lower()).strip(' .!?')
        self.parsed = parse_request(text, self.ws.get('last_intent'))

    def dispatch(self):
        if self.session.stopped or self.session.cancelled.is_set():
            raise ValueError('cancel_or_resume_required')
        if any(p in self.text for p in UNSAFE) or self._is_outside_tools():
            self.ws['pending_clarification'] = None
            self.card('Unsupported request', dict(executed=False, source='workspace_policy',
                                                 superseded_pending=True))
            return 'That request is outside the supported local tools. No file was changed and no program ran.', 'clarification', False
        if self.ws.get('pending_clarification') and any(p in self.text for p in CANCEL_PENDING):
            self.ws['pending_clarification'] = None
            self.card('Pending clarification dropped', dict(executed=False, reason='cancel'))
            return 'Okay, I dropped the pending question. Nothing ran.', 'reply', False
        if self._new_request_supersedes_pending():
            self.ws['pending_clarification'] = None
            self.card('Pending clarification superseded', dict(executed=False, reason='new_request'))
        from .symbiotic_workbench import SymbioticWorkbenchController
        wb_ctrl = SymbioticWorkbenchController(self.store, self.session, session_id=self.conversation.session_id)
        wb_routed = wb_ctrl.try_handle_chat(self)
        if wb_routed is not None:
            return wb_routed
        answered = self._answer_clarification()
        if answered:
            return answered
        if any(p in self.text for p in SAVE_PROC):
            return self.save_procedure()
        if any(p in self.text for p in INSPECT_PROC):
            return self.inspect_procedure()
        if any(p in self.text for p in REUSE_PROC):
            return self.reuse_procedure()
        if any(p in self.text for p in DELETE_PROC):
            return self.delete_procedure()
        if any(p in self.text for p in CHANGED):
            return self.what_changed()
        if self._constraint_blocks():
            return self.reject_incomplete()
        if self.parsed.relation == 'repeat':
            return self.repeat(self.parsed.paths)
        if self.parsed.relation == 'correction' and self.ws['last_intent'] is not None:
            return self.correct(self.parsed.paths)
        if self.parsed.relation == 'fresh' and self.parsed.understood:
            target = self.parsed.paths[0] if self.parsed.paths else self.ws['selected_file']
            if not target:
                return self.clarify('file', 'Which local CSV should I use? Name the file; I will not guess.')
            intent = dict(op=self.parsed.grain, min=self.parsed.minimum if self.parsed.minimum_stated else None,
                          order=self.parsed.order or 'desc')
            return self.execute_intent(intent, target, change='Fresh request on '+Path(target).name+'.',
                                       request_kind='fresh', order_defaulted=not self.parsed.order_stated)
        if self.parsed.relation == 'file_only' and self.parsed.paths:
            return self.select_file(self.parsed.paths[0])
        coding = self._maybe_handle_coding()
        if coding is not None:
            return coding
        if self._looks_like_data() and not self.ws['selected_file']:
            return self.clarify('file', 'I need a local CSV before I can group totals or list rows.')
        if self._looks_like_data() and self.ws['selected_file']:
            parsed = self.model_intent(self.ws['selected_file'])
            if parsed is None:
                return self.clarify('grain', 'Should I compute grouped totals or individual rows? I can also apply an inclusive minimum or sort order. Other comparisons are not guessed.')
            if parsed['op'] in ('clarify', 'unsupported'):
                self.ws['pending_clarification'] = dict(kind='grain', detail='totals_or_rows')
                return ('Please say whether you want grouped totals or individual rows, and any inclusive minimum or sort order.'
                        if parsed['op'] == 'clarify' else
                        'That data request is outside the two supported CSV operations. Nothing ran.'), 'clarification', False
            return self.execute_intent(parsed, self.ws['selected_file'], request_kind='fresh',
                                       order_defaulted=parsed.get('order') == 'desc')
        return self.ordinary_chat()

    def reject_incomplete(self):
        reasons = self.parsed.unsupported + self.parsed.conflicts
        kind = 'conflict' if self.parsed.conflicts else 'constraint'
        self.ws['pending_clarification'] = dict(kind=kind, detail=', '.join(reasons)[:400])
        self.card('Ununderstood constraints', dict(
            executed=False, recognized_grain=self.parsed.grain, unsupported=self.parsed.unsupported,
            conflicts=self.parsed.conflicts, inherited=False))
        if 'multiple_files' in self.parsed.conflicts:
            return 'I see more than one file. Which one should I use? Nothing ran.', 'clarification', False
        if 'conflicting_order' in self.parsed.conflicts:
            return 'That request asks for both smallest-first and largest-first. Which order should I use? Nothing ran.', 'clarification', False
        return (
            'I recognized a possible data request but not every constraint. Supported executable '
            'filters are an inclusive minimum and one sort direction. '
            + '; '.join(reasons) + ' is not silently applied. Nothing ran.'
        ), 'clarification', False

    def _answer_clarification(self):
        pending = self.ws['pending_clarification']
        if not pending:
            return None
        if self._constraint_blocks():
            return self.reject_incomplete()
        if pending['kind'] in ('file', 'constraint', 'conflict', 'grain', 'order', 'reference'):
            if self.parsed.relation == 'fresh' and self.parsed.understood:
                self.ws['pending_clarification'] = None
                target = self.parsed.paths[0] if self.parsed.paths else self.ws['selected_file']
                if not target:
                    return self.clarify('file', 'Which local CSV should I use?')
                intent = dict(op=self.parsed.grain, min=self.parsed.minimum if self.parsed.minimum_stated else None,
                              order=self.parsed.order or 'desc')
                return self.execute_intent(intent, target, request_kind='fresh',
                                           order_defaulted=not self.parsed.order_stated)
            if pending['kind'] == 'file' and self.parsed.paths:
                self.ws['pending_clarification'] = None
                if self.ws['last_intent'] and self.parsed.relation in ('repeat', 'unknown'):
                    return self.execute_intent(self.ws['last_intent'], self.parsed.paths[0],
                                               change='Applied the pending request to '+Path(self.parsed.paths[0]).name+'.',
                                               request_kind='repeat')
                return self.select_file(self.parsed.paths[0])
        return None

    def _looks_like_data(self):
        return any(p in self.text for p in DATA_SUM + DATA_ROWS + ('amount', 'csv', 'filter', 'minimum', 'at least', 'region'))

    def _constraint_blocks(self):
        if not (self.parsed.unsupported or self.parsed.conflicts):
            return False
        return self.parsed.grain is not None or self.parsed.relation in ('fresh', 'repeat', 'correction') or self._looks_like_data()

    def _is_outside_tools(self):
        return any(p in self.text for p in OUTSIDE_TOOLS)

    def _lists_coding_workspaces(self):
        if self.text in ('list coding workspaces', 'show coding workspaces', 'list repos'):
            return True
        return 'list' in self.text and 'workspace' in self.text

    def _answers_pending(self, pending):
        kind = (pending or {}).get('kind')
        if kind == 'coding_workspace':
            if self.CODING_SELECT.search(self.raw.strip()) or self._lists_coding_workspaces():
                return True
            names = []
            listing = getattr(self.store, 'list_coding_workspaces', None)
            if callable(listing):
                names = [str(n).lower() for n in (listing() or [])]
            return self.text in names
        if kind == 'file':
            return bool(self.parsed.paths)
        if kind in ('grain', 'constraint', 'conflict', 'order', 'reference'):
            return bool(self.parsed.understood or self.parsed.relation in ('fresh', 'repeat', 'correction'))
        return False

    def _asks_workspace_state(self):
        if any(p in self.text for p in (
            'what workspace', 'which workspace', 'wich workspace',
            'what coding workspace', 'which coding workspace', 'wich coding workspace',
            'what is selected', "what's selected",
            'what file is selected', 'which file is selected', 'wich file is selected',
            'current workspace', 'workspace state',
        )):
            return True
        return (
            ('workspace' in self.text or 'file' in self.text)
            and ('is selected' in self.text or 'currently selected' in self.text)
        )

    def _asks_help_capabilities(self):
        if any(p in self.text for p in (
            'what can you help', 'what can u help', 'what can you do', 'what can u do',
            'how can you help', 'how can u help', 'what are your capabilities',
            'what tools do you have',
        )):
            return True
        return ('help' in self.text or 'capabilit' in self.text) and (
            'what' in self.text or 'how' in self.text
        )

    def _new_request_supersedes_pending(self):
        pending = self.ws.get('pending_clarification')
        if not pending:
            return False
        if self._is_outside_tools() or any(p in self.text for p in CANCEL_PENDING):
            return True
        if self._answers_pending(pending):
            return False
        looks_coding = any(p in self.text for p in self.CODING_TASK) or self.text.startswith((
            'implement ', 'fix the', 'add a ', 'write a ', 'create a ',
        ))
        if pending.get('kind') == 'coding_workspace' and looks_coding:
            return False
        if self._asks_workspace_state() or any(p in self.text for p in (
            'what file', 'what workspace', 'which workspace is selected',
            'what is selected', "what's selected",
        )):
            return True
        if self.parsed.relation == 'correction':
            return True
        return pending.get('kind') in {'coding_workspace', 'coding_request', 'file', 'grain'}

    def clarify(self, kind, message):
        self.ws['pending_clarification'] = dict(kind=kind, detail=message[:400])
        self.card('Clarification needed', dict(kind=kind, executed=False))
        return message, 'clarification', False

    def select_file(self, path_text):
        path = self.resolve_source(path_text)
        if path is None:
            return self.clarify('file', 'I could not read that CSV. Give an existing local .csv path. Nothing ran.')
        prior = self.ws['selected_file']
        self.ws['selected_file'] = str(path)
        self.ws['pending_clarification'] = None
        self.ws['last_correction'] = 'Selected '+path.name+('.' if prior is None else ' Replaced '+Path(prior).name+'.')
        self.card('Selected file', dict(path=str(path), source_unchanged=True, executed=False))
        return 'Using '+path.name+'. Ask for grouped totals or individual rows; I will not overwrite this file.', 'reply', False

    def resolve_source(self, path_text):
        path = Path(path_text).expanduser()
        if not path.is_absolute():
            for base in (Path.cwd(), Path(self.store.directory)):
                candidate = (base / path).resolve()
                if candidate.is_file():
                    path = candidate
                    break
        try:
            path = path.resolve()
        except OSError:
            return None
        if not path.is_file() or path.suffix.lower() != '.csv':
            return None
        return path

    def repeat(self, paths):
        if self.ws['last_intent'] is None and self.ws['last_procedure_id'] is None:
            return self.clarify('reference', 'I do not have a last procedure to repeat. Name a CSV and a supported transform first.')
        if len(paths) > 1:
            return self.clarify('file', 'I see more than one file. Which one should I use?')
        target = paths[0] if paths else self.ws['selected_file']
        if not target:
            return self.clarify('file', 'Which other file should I apply the last procedure to?')
        intent = self.ws['last_intent']
        if intent is None:
            return self.reuse_procedure(path_text=target)
        note = 'Repeated the last procedure on '+Path(target).name+'. Threshold and order were inherited because you asked to do the same.'
        return self.execute_intent(intent, target, change=note, request_kind='repeat')

    def correct(self, paths):
        if self.ws['last_intent'] is None:
            return self.clarify('reference', 'There is no last procedure to correct.')
        intent = dict(self.ws['last_intent'])
        if self.parsed.order_stated:
            intent['order'] = self.parsed.order
        if self.parsed.minimum_stated:
            intent['min'] = self.parsed.minimum
        target = paths[0] if paths else self.ws['selected_file']
        if not target:
            return self.clarify('file', 'Which file should I apply that correction to?')
        note = 'Corrected the last procedure to op={op}, min={min}, order={order}.'.format(**intent)
        return self.execute_intent(intent, target, change=note, request_kind='correction')

    def what_changed(self):
        note = self.ws['last_correction']
        data = dict(last_correction=note, last_intent=self.ws['last_intent'],
                    selected_file=self.ws['selected_file'], last_output_path=self.ws['last_output_path'],
                    last_procedure_id=self.ws['last_procedure_id'], last_request_kind=self.ws.get('last_request_kind'),
                    executed=False)
        self.card('Workspace changes', data)
        if not note:
            return 'No correction has been applied yet. I have not changed a procedure in this conversation.', 'reply', False
        return note + ' Model-generated chat is not listed here; only execution-backed procedure edits are.', 'reply', False

    CODING_SELECT = re.compile(
        r'^(?:use|open|select|load)\s+(?:coding\s+workspace|repo(?:sitory)?(?:\s+workspace)?)\s+([A-Za-z0-9][A-Za-z0-9_-]{0,39})\b',
        re.I,
    )
    CODING_TASK = (
        'implement', 'fix ', 'add a function', 'add function', 'write a function',
        'create a function', 'patch ', 'edit the repo', 'modify ', 'make it ',
        'handle empty', 'use the documented',
    )
    AMBIGUOUS_CODING_PRONOUNS = (
        'fix it', 'fix this', 'fix that', 'patch it', 'modify it', 'change it', 'update it',
    )

    def _maybe_handle_coding(self):
        match = self.CODING_SELECT.search(self.raw.strip())
        if match:
            return self.select_coding_workspace(match.group(1))
        if self._lists_coding_workspaces():
            names = self.store.list_coding_workspaces()
            if (self.ws.get('pending_clarification') or {}).get('kind') == 'coding_workspace':
                self.ws['pending_clarification'] = None
            self.card('Allowed coding workspaces', dict(workspaces=names, executed=False))
            if not names:
                return 'No allowed coding workspaces are registered under this local store.', 'clarification', False
            return 'Allowed coding workspaces: '+', '.join(names)+'. Say “use coding workspace <name>”.', 'reply', False
        if self.text in ('disable acquired coding memory', 'baseline coding mode'):
            self.ws['coding_allow_acquired'] = False
            return 'Coding loop will not reuse acquired capsules. This is the baseline mode for later learning comparisons.', 'reply', False
        if self.text in ('enable acquired coding memory',):
            self.ws['coding_allow_acquired'] = True
            return 'Coding loop may reuse previously acquired capsules. Saving a patch is still not learning-to-learn.', 'reply', False
        selected = self.ws.get('selected_coding_workspace')
        looks_coding = any(p in self.text for p in self.CODING_TASK) or self.text.startswith((
            'implement ', 'fix the', 'add a ', 'write a ', 'create a ',
        ))
        follow_up = (
            self.parsed.relation == 'correction' and self.ws.get('last_coding_request')
            and selected
        )
        if looks_coding and not selected:
            return self.clarify('coding_workspace', 'Which allowed coding workspace should I use?')
        if selected and self.text in self.AMBIGUOUS_CODING_PRONOUNS and not self.ws.get('last_coding_request'):
            return self.clarify(
                'coding_request',
                'What should I fix or change in coding workspace '+str(selected)+'? Describe the target function or behavior; I will not guess.',
            )
        if selected and (looks_coding or follow_up):
            request = self.raw.strip()
            if follow_up and self.ws.get('last_coding_request'):
                request = self.ws['last_coding_request'] + ' Correction: ' + self.raw.strip()
            return self.run_coding_loop(request)
        return None

    def select_coding_workspace(self, name):
        from .symbiotic_workbench import contained_repository_path
        allowed = self.store.list_coding_workspaces()
        if name not in allowed:
            self.ws['pending_clarification'] = dict(kind='coding_workspace', detail=name[:80])
            self.card('Coding workspace', dict(executed=False, allowed=allowed, requested=name))
            return (
                'That coding workspace is not in the allowed local list. '
                + ('Registered: '+', '.join(allowed)+'.' if allowed else 'None are registered yet.')
            ), 'clarification', False
        root = contained_repository_path(self.store.coding_workspaces_dir(), name)
        files = {}
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.name.startswith('.'):
                continue
            rel = str(path.relative_to(root)).replace('\\', '/')
            if any(part.startswith('.') for part in Path(rel).parts):
                continue
            if path.stat().st_size > 20_000:
                continue
            files[rel] = path.read_text(encoding='utf-8')
        self.ws['selected_coding_workspace'] = name
        self.ws['pending_clarification'] = None
        self.ws['last_request_kind'] = 'coding'
        self.card('Selected coding workspace', dict(
            workspace=name, files=sorted(files), executed=False,
            baseline_no_acquired=not self.ws.get('coding_allow_acquired'),
        ))
        return (
            'Using coding workspace '+name+' with '+str(len(files))+' file(s). '
            'Describe a coding task. I will show the model proposal, applied edit, '
            'public-test outcome, unverified assumptions and final diff separately. '
            'Passing public tests is not complete correctness.'
        ), 'reply', False

    def run_coding_loop(self, request):
        from .symbiotic_workbench import SymbioticWorkbenchController, contained_repository_path
        if self.session.cancelled.is_set():
            raise ValueError('cancel')
        name = self.ws.get('selected_coding_workspace')
        if not name:
            return self.clarify('coding_workspace', 'Which allowed coding workspace should I use?')
        root = contained_repository_path(self.store.coding_workspaces_dir(), name)
        files, public_tests, docs, language = _load_coding_workspace(root)
        if not files:
            return self.clarify('coding_workspace', 'That workspace has no readable source files.')
        ctrl = SymbioticWorkbenchController(self.store, self.session, session_id=self.conversation.session_id)
        spec = dict(
            task_id='ws_'+name,
            domain='typescript_repo' if language == 'typescript' else 'python_repo',
            language=language,
            request=request[:500],
            files=files,
            public_tests=public_tests,
            docs=docs,
            budget_steps=8,
            allow_acquired_memory=bool(self.ws.get('coding_allow_acquired')),
        )
        out = ctrl._handle_agent_solve_api(spec)
        res = out['result']
        self.ws['last_coding_request'] = request[:500]
        self.ws['last_request_kind'] = 'coding'
        self.ws['last_correction'] = 'Coding loop on '+name+' ended with '+res.get('outcome_category', 'unknown')+'.'
        return _present_coding_result(self.card, res, out.get('proposal'))

    def _retrieve_grounded_docs(self) -> list[dict]:
        docs = list(getattr(self.store, 'knowledge_docs', None) or [])
        selected = self.ws.get('selected_coding_workspace')
        if selected and hasattr(self.store, 'coding_workspaces_dir'):
            try:
                from .symbiotic_workbench import contained_repository_path
                root = contained_repository_path(self.store.coding_workspaces_dir(), selected)
                _, _, ws_docs, _ = _load_coding_workspace(root)
                docs.extend(ws_docs)
            except Exception:
                pass
        if not docs:
            return []
        from .symbiotic_workbench import KnowledgeAndDocRetriever
        kr = KnowledgeAndDocRetriever()
        for idx, d in enumerate(docs):
            if not isinstance(d, dict):
                continue
            kr.register_document(
                doc_id=str(d.get('doc_id') or d.get('title') or f'doc_{idx}'),
                title=str(d.get('title') or d.get('doc_id') or f'doc_{idx}'),
                content=str(d.get('content') or d.get('text') or ''),
                version=str(d.get('version') or '1.0.0'),
                grounded_bindings=dict(d.get('grounded_bindings') or {}),
            )
        ret = kr.retrieve(self.raw)
        return list(ret.get('doc_hits') or [])

    def ordinary_chat(self):
        header, header_meta = workspace_context_header(self.store, self.ws)
        asked_state = self._asks_workspace_state()
        if asked_state:
            pending = self.ws.get('pending_clarification')
            selected = self.ws.get('selected_coding_workspace') or self.ws.get('selected_file') or 'none'
            question = ''
            if isinstance(pending, dict) and pending.get('detail'):
                question = ' Needed question: '+str(pending['detail'])
            self.card('Workspace context', dict(executed=False, **header_meta, scored_as='real_state'))
            return (
                'Selected resource: '+str(selected)+'. Allowed coding workspaces: '
                + (', '.join(header_meta.get('allowed_coding_workspaces') or []) or 'none')
                + '.' + question
            ), 'reply', False
        retrieved_docs = self._retrieve_grounded_docs()
        runtime = self.store.ensure_runtime()
        if runtime is None:
            if self._asks_help_capabilities():
                return _help(self.conversation, self.card)
            reason = self.store.runtime_status()['reason'] or 'local_model_unavailable'
            doc_titles = [d.get('title', 'doc') for d in retrieved_docs]
            doc_note = ''
            if retrieved_docs:
                doc_note = ' Grounded workspace docs matched: ' + '; '.join(
                    f"{d.get('title', 'doc')}: {d.get('content') or d.get('excerpt') or d.get('snippet') or ''}" for d in retrieved_docs
                )
            self.card('Local model unavailable', dict(
                source='runtime_status',
                reason=reason,
                executed=False,
                workspace_header=header_meta,
                grounded_docs=doc_titles,
            ))
            return (
                'No local pretrained model is available, so I cannot run live ordinary chat. '
                + reason + ' Teaching words/skills and the two CSV tools still work.'
                + doc_note + ' This is not a template standing in for inference.'
            ), 'clarification', False
        docs_block = ''
        if retrieved_docs:
            docs_block = '\nGrounded workspace documents:\n' + '\n'.join(
                f"- {d.get('title', 'doc')}: {d.get('content') or d.get('excerpt') or d.get('snippet') or ''}" for d in retrieved_docs
            ) + '\n'
        history = []
        for turn in self.conversation.view()['messages'][-4:]:
            history.append('User: '+turn['user'][:400])
            history.append('Assistant: '+turn['assistant'][:400])
        prompt = ('<|im_start|>system\n'+CHAT_SYSTEM+'\n\n'+header+docs_block+'<|im_end|>\n')
        if history:
            prompt += '<|im_start|>user\nRecent conversation:\n'+'\n'.join(history)+'<|im_end|>\n'
        prompt += '<|im_start|>user\n'+self.raw.strip()+'<|im_end|>\n<|im_start|>assistant\n'
        reply = self.complete(runtime, prompt, None)
        text = reply['content'].strip() or 'I do not have a completion for that.'
        if self._asks_help_capabilities():
            low = text.lower()
            if not any(cap in low for cap in ('finite object', 'csv', 'grouped totals', 'coding loop', 'inclusive minimum')):
                text = (
                    text + ' Registered local capabilities: finite object teaching, '
                    'CSV grouped totals or individual rows (inclusive minimum filter), and '
                    'bounded coding loop on an allowed workspace (public tests are not complete correctness).'
                )
        scored = score_workspace_reply(text, self.ws, header_meta)
        self.card('Model-generated reply', dict(
            source='model_generated', executed=False, inference_ran=reply['telemetry'].get('inference_ran'),
            application_cache_hit=reply['telemetry'].get('application_cache_hit'),
            workspace_header=header_meta, workspace_score=scored,
            grounded_docs=[d.get('title', 'doc') for d in retrieved_docs],
            header_consumes_input_tokens=True))
        return text + '\n\n(This is model-generated text, not an executed file result.)', 'reply', False

    def model_intent(self, path_text):
        runtime = self.store.ensure_runtime()
        if runtime is None:
            return None
        path = self.resolve_source(path_text)
        if path is None:
            return None
        rows, profiles = self.load_table(path)
        if rows is None:
            return None
        reply = self.complete(runtime, intent_prompt(self.raw, profiles), SCHEMA)
        try:
            return validate_intent(json.loads(reply['content']))
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def complete(self, runtime, prompt, schema):
        done = threading.Event()

        def watch():
            while not done.is_set():
                if self.session.cancelled.wait(0.05):
                    if hasattr(runtime, 'cancel'):
                        runtime.cancel()
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            if self.session.cancelled.is_set():
                raise ValueError('cancel')
            return runtime.complete(prompt, schema)
        finally:
            done.set()

    def load_table(self, path):
        try:
            with path.open(newline='', encoding='utf-8') as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, UnicodeError, csv.Error):
            return None, None
        if not rows:
            return None, None
        profiles = SchemaProfileAndBindingValidator.compute_compact_column_profiles(rows)
        return rows, profiles

    def _checkpoint(self, stage, allow_cancel=True):
        hook = getattr(self.store, 'execution_checkpoint', None)
        if hook is not None:
            hook(stage, self)
        if allow_cancel and (self.session.stopped or self.session.cancelled.is_set()):
            raise ValueError('cancel')

    def execute_intent(self, intent, path_text, change=None, capsule=None, saved_explicit=None,
                       request_kind='fresh', order_defaulted=False):
        self._checkpoint('start')
        path = self.resolve_source(path_text)
        if path is None:
            return self.clarify('file', 'I could not open that CSV. Nothing ran.')
        rows, profiles = self.load_table(path)
        if rows is None:
            return 'That CSV is empty or unreadable. Nothing ran.', 'error', False
        try:
            intent = validate_intent(dict(op=intent['op'], min=intent.get('min'), order=intent.get('order', 'desc')))
        except ValueError:
            return self.clarify('grain', 'I need grouped totals or individual rows, with an optional inclusive minimum and sort order.')
        if intent['op'] in ('clarify', 'unsupported'):
            self.ws['pending_clarification'] = dict(kind='grain', detail='totals_or_rows')
            return 'Please specify grouped totals or individual rows. Nothing ran.', 'clarification', False
        try:
            bindings = bind(profiles, intent)
        except ValueError as exc:
            return 'I cannot bind that request to this file ('+str(exc)+'). Nothing ran.', 'clarification', False
        if capsule is not None:
            ok, reason = self.compatible(capsule, profiles, intent)
            if not ok:
                self.card('Incompatible procedure', dict(reason=reason, executed=False, saved_explicitly=capsule.get('saved_explicitly')))
                return 'The saved procedure is not compatible with this file: '+reason+'. Nothing ran.', 'clarification', False
            template = ParameterizedAdapterTemplate(capsule['id'], capsule['task_kind'], capsule['skeleton_ops'])
            program = template.instantiate(bindings, intent['min'] or 0)
        else:
            ops = skeleton(intent)
            program = ParameterizedAdapterTemplate('ephemeral', digest((intent['op'], intent['min'] is not None, intent['order'])), ops).instantiate(bindings, intent['min'] or 0)
        inherited = request_kind in ('repeat', 'correction', 'reuse')
        preview = dict(
            source='transformation_preview', operations=[step.get('op') for step in program.ops],
            intent=intent, input_file=path.name, source_file_unchanged=True, executed=False,
            request_kind=request_kind, inherited_constraints=inherited, order_defaulted=bool(order_defaulted),
            resolved=dict(op=intent['op'], inclusive_minimum=intent['min'], order=intent['order'],
                          inheritance='inherited' if inherited else 'stated_or_tool_default'))
        self.card('Requested transformation preview', preview)
        self._checkpoint('after_preview')
        output = program.execute(rows)
        self._checkpoint('after_execute')
        json.dumps(output, allow_nan=False)
        if type(output) is not list or any(type(row) is not dict for row in output):
            return 'The adapter returned an invalid result shape. The source file is unchanged.', 'error', False
        source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        output_path = self.store.outputs_dir() / (path.stem + '-' + digest(output)[:10] + '.json')
        try:
            publish_json(output_path, output, cancelled=lambda: self.session.cancelled.is_set() or self.session.stopped,
                         after_tmp=lambda _tmp: self._checkpoint('after_tmp'))
        except ValueError as exc:
            if str(exc) == 'cancel':
                raise
            raise
        # Once publish_json returns, os.replace has already committed the file.
        # Post-commit cancellation must NEVER raise before recording the receipt
        # and updating workspace state, and must never report the action as undone.
        self._checkpoint('after_commit', allow_cancel=False)
        cancelled_after_commit = bool(self.session.stopped or self.session.cancelled.is_set())
        receipt = digest(output)
        rendered = ExecutionBackedResponseRenderer.render(path.stem, output, receipt)
        compact_bindings = {key: bindings[key] for key in ('key_col', 'metric_col', 'status_col', 'required_output_columns') if key in bindings}
        self.ws.update(selected_file=str(path), last_intent=intent, last_output_path=str(output_path),
                       last_source_sha=source_sha, pending_clarification=None,
                       last_correction=change or ('Executed '+intent['op']+' on '+path.name+'.'),
                       last_saved_explicit=bool(capsule and capsule.get('saved_explicitly')),
                       last_program=program.ops, last_bindings=compact_bindings, last_request_kind=request_kind)
        if saved_explicit is not None:
            self.ws['last_saved_explicit'] = saved_explicit
        if capsule and capsule.get('saved_explicitly'):
            self.ws['last_procedure_id'] = capsule['id']
        self.card('Execution-backed result', dict(
            source='execution_backed', executed=True, committed=True,
            cancelled_after_commit=cancelled_after_commit, row_count=len(output), preview=output[:5],
            output_path=str(output_path), source_file=str(path), source_file_unchanged=True,
            receipt=receipt, response=rendered, saved_explicitly=bool(capsule and capsule.get('saved_explicitly')),
            autonomously_discovered=False, request_kind=request_kind))
        suffix = (
            ' Stop arrived after atomic commit; the committed output and receipt were preserved and not undone.'
            if cancelled_after_commit else ''
        )
        return (
            rendered + ' Wrote '+str(output_path)+'. The source CSV was not modified. '
            'This result is execution-backed, not model-generated.' + suffix
        ), 'success', False

    def compatible(self, capsule, profiles, intent):
        numeric = [k for k, v in profiles.items() if v['inferred_type'] == 'numeric']
        text = [k for k, v in profiles.items() if v['inferred_type'] == 'text']
        if len(numeric) != 1 or len(text) != 1:
            return False, 'schema requires exactly one text column and one numeric column'
        if capsule.get('types') != dict(key='text', metric='numeric'):
            return False, 'capsule type contract'
        if capsule.get('task_kind') != intent['op']:
            return False, 'grain mismatch: saved '+str(capsule.get('task_kind'))+' vs requested '+intent['op']
        expected = [intent['op'], intent['min'] is not None, intent['order']]
        if list(capsule.get('shape') or []) != expected:
            return False, 'saved filter/order shape does not match this request'
        if not capsule.get('skeleton_ops'):
            return False, 'missing saved AST'
        return True, 'validated_compatible'

    def save_procedure(self):
        if self.ws.get('last_program') is None or self.ws.get('last_bindings') is None or self.ws.get('last_intent') is None:
            return 'There is no executed procedure to save yet. Run a CSV transform first. Nothing was stored.', 'clarification', False
        intent = self.ws['last_intent']
        shape = [intent['op'], intent['min'] is not None, intent['order']]
        ops = abstract_executed_ast(self.ws['last_program'], self.ws['last_bindings'])
        identifier = digest(['explicit', ops, self.ws['last_source_sha']])[:16]
        record = dict(
            id=identifier, name=intent['op']+'-'+intent['order'], saved_explicitly=True,
            autonomously_discovered=False, task_kind=intent['op'], shape=shape, skeleton_ops=ops,
            types=dict(key='text', metric='numeric'),
            preconditions=dict(format='csv', unique_text_column=True, unique_numeric_column=True,
                               supported_filter='inclusive_minimum_ge', supported_order=('asc', 'desc')),
            provenance=dict(session_id=self.conversation.session_id, source_sha256=self.ws['last_source_sha'],
                            source_file=str(Path(self.ws['selected_file']).name), revision='explicit_save_executed_ast',
                            request_kind=self.ws.get('last_request_kind')),
            validation_scope='Same-schema CSV with one text and one numeric column; grain, filter presence and order must match the saved shape. AST is the abstracted executed program, not a reconstructed planner skeleton.',
            intent=intent, bindings=self.ws['last_bindings'], learning_to_learn=False)
        path = self.store.procedures_dir() / (identifier + '.json')
        path.write_text(json.dumps(record, allow_nan=False, indent=2), encoding='utf-8')
        self.ws['last_procedure_id'] = identifier
        self.ws['last_saved_explicit'] = True
        self.ws['last_correction'] = 'Explicitly saved the executed AST as '+identifier+'. This is stored reuse, not an autonomously discovered abstraction or learning-to-learn.'
        self.card('Saved procedure', dict(id=identifier, path=str(path), saved_explicitly=True,
                                          autonomously_discovered=False, skeleton_ops=ops, executed=False,
                                          source='executed_ast'))
        return 'Saved procedure '+identifier+' from the executed AST. Persistence is reuse, not learning-to-learn.', 'success', False

    def _load_capsule(self, identifier=None):
        identifier = identifier or self.ws['last_procedure_id']
        if not identifier:
            explicit = []
            for path in self.store.procedures_dir().glob('*.json'):
                try:
                    data = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    continue
                if data.get('saved_explicitly') and data.get('id'):
                    explicit.append(data['id'])
            if len(explicit) == 1:
                identifier = explicit[0]
            else:
                return None
        path = self.store.procedures_dir() / (identifier + '.json')
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None
        if type(data) is not dict or not data.get('skeleton_ops'):
            return None
        return data

    def inspect_procedure(self):
        rows = []
        for path in sorted(self.store.procedures_dir().glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            rows.append(dict(id=data.get('id'), name=data.get('name'), saved_explicitly=bool(data.get('saved_explicitly')),
                             autonomously_discovered=bool(data.get('autonomously_discovered')),
                             task_kind=data.get('task_kind'), validation_scope=data.get('validation_scope')))
        target = self._load_capsule()
        self.card('Stored procedures', dict(entries=rows[:8], selected=target, executed=False,
                                            learning_to_learn=False))
        if not rows:
            return 'No procedures are saved on disk. Execute a transform, then ask to save it.', 'reply', False
        return ('Explicit saves are listed separately from any autonomous abstraction. '
                'There are '+str(len(rows))+' stored procedure file(s). Persistence is not learning-to-learn.'), 'reply', False

    def reuse_procedure(self, path_text=None):
        capsule = self._load_capsule()
        if capsule is None:
            return self.clarify('procedure', 'No saved procedure is selected. Save one first, or inspect stored procedures.')
        if not capsule.get('saved_explicitly'):
            return 'That record is not an explicitly saved procedure. I will not treat an autonomous abstraction as a user save.', 'clarification', False
        target = path_text or (self.parsed.paths[0] if self.parsed.paths else self.ws['selected_file'])
        if not target:
            return self.clarify('file', 'Which CSV should I apply the saved procedure to?')
        return self.execute_intent(capsule['intent'], target, change='Reused explicitly saved procedure '+capsule['id']+'.',
                                   capsule=capsule, saved_explicit=True, request_kind='reuse')

    def delete_procedure(self):
        capsule = self._load_capsule()
        if capsule is None:
            return 'There is no saved procedure to delete.', 'clarification', False
        path = self.store.procedures_dir() / (capsule['id'] + '.json')
        if path.is_file():
            path.unlink()
        if self.ws['last_procedure_id'] == capsule['id']:
            self.ws['last_procedure_id'] = None
            self.ws['last_saved_explicit'] = False
        self.ws['last_correction'] = 'Deleted explicitly saved procedure '+capsule['id']+'.'
        self.card('Deleted procedure', dict(id=capsule['id'], executed=False))
        return 'Deleted saved procedure '+capsule['id']+'. The last ephemeral transform, if any, is unchanged.', 'success', False
