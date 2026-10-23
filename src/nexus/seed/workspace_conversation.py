"""Local file/procedure workspace over the existing Conversation and Session journal.

Reuses assistant_benchmark_v2 skeletons, ParameterizedAdapterTemplate capsules,
PersistentLocalRuntime and ExecutionBackedResponseRenderer. No generated-Python
execution path and no second memory store. Persistence is not learning-to-learn.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
from pathlib import Path

from nexus.evolution1.catalogue import digest

from .assistant_benchmark_v2 import SCHEMA, bind, intent_prompt, skeleton, validate_intent
from .real_data_adapter_learning import (ExecutionBackedResponseRenderer, ParameterizedAdapterTemplate,
    SchemaProfileAndBindingValidator)

CHAT_SYSTEM = (
    'You are NEXUS Seed, a local assistant. Answer conversationally from this prompt only. '
    'You cannot run tools or change files from this prompt. Do not claim a file was written, '
    'a program ran, or a procedure was saved. If the user wants a spreadsheet transform, say '
    'they should name a local CSV and ask for grouped totals or individual rows.'
)
UNSAFE = ('delete my', 'rm -', 'os.system', '__import__', 'buy stock', 'buy stocks',
          'send email', 'http://', 'https://', 'eval(', 'exec(', 'subprocess', 'format disk')
DATA_SUM = ('summarize', 'summary', 'totals', 'total ', 'grouped', 'group by', 'per region', 'by region')
DATA_ROWS = ('individual', 'records', 'row-level', 'each row', 'line item', 'list the', 'list records')
ORDER_ASC = ('smallest', 'ascending', 'low to high', 'asc')
ORDER_DESC = ('largest', 'descending', 'high to low', 'desc')
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
        'Correct the last transform (order or minimum) or apply it to another file.',
        'Save, inspect, reuse or delete a procedure. Restart keeps explicit saves.',
        'Ask a question in ordinary language; model text is not an executed result.',
    ])
    return (
        'I can teach finite object words and list programs, move objects on the 6×6 world, '
        'and run two vetted CSV transforms (grouped totals or filtered rows) without changing '
        'the source file. '+model+' Saving a procedure stores its AST; that is reuse, not '
        'learning-to-learn.'
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

    def dispatch(self):
        if self.session.stopped or self.session.cancelled.is_set():
            raise ValueError('cancel_or_resume_required')
        if any(p in self.text for p in UNSAFE):
            self.ws['pending_clarification'] = None
            self.card('Unsupported request', dict(executed=False, source='workspace_policy'))
            return 'That request is outside the supported local tools. No file was changed and no program ran.', 'clarification', False
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
        paths = self.paths()
        repeating = any(p in self.text for p in REPEAT)
        correcting = self._is_correction()
        intent = self.heuristic_intent()
        if repeating:
            return self.repeat(paths)
        if correcting and self.ws['last_intent'] is not None:
            return self.correct(paths)
        if paths and (intent or self._looks_like_file_only(paths)):
            if intent:
                return self.execute_intent(intent, paths[0], change='Selected '+Path(paths[0]).name+' and ran the requested transform.')
            return self.select_file(paths[0])
        if intent:
            if not self.ws['selected_file']:
                return self.clarify('file', 'Which local CSV should I use? Name the file; I will not guess.')
            return self.execute_intent(intent, self.ws['selected_file'])
        if paths:
            return self.select_file(paths[0])
        if self._looks_like_data() and not self.ws['selected_file']:
            return self.clarify('file', 'I need a local CSV before I can group totals or list rows.')
        if self._looks_like_data() and self.ws['selected_file']:
            parsed = self.model_intent(self.ws['selected_file'])
            if parsed is None:
                return self.clarify('grain', 'Should I compute grouped totals or list individual rows? I can also apply a minimum or sort order.')
            if parsed['op'] in ('clarify', 'unsupported'):
                self.ws['pending_clarification'] = dict(kind='grain', detail='totals_or_rows')
                status = 'clarification' if parsed['op'] == 'clarify' else 'clarification'
                return ('Please say whether you want grouped totals or individual rows, and any minimum or sort order.'
                        if parsed['op'] == 'clarify' else
                        'That data request is outside the two supported CSV operations. Nothing ran.'), status, False
            return self.execute_intent(parsed, self.ws['selected_file'])
        return self.ordinary_chat()

    def _answer_clarification(self):
        pending = self.ws['pending_clarification']
        if not pending:
            return None
        if pending['kind'] == 'file':
            paths = self.paths()
            if not paths:
                return None
            self.ws['pending_clarification'] = None
            intent = self.heuristic_intent() or self.ws['last_intent']
            if intent:
                return self.execute_intent(intent, paths[0], change='Applied the pending request to '+Path(paths[0]).name+'.')
            return self.select_file(paths[0])
        if pending['kind'] in ('grain', 'order'):
            intent = self.heuristic_intent()
            if not intent:
                return None
            self.ws['pending_clarification'] = None
            target = self.paths()[0] if self.paths() else self.ws['selected_file']
            if not target:
                return self.clarify('file', 'Which local CSV should I use?')
            return self.execute_intent(intent, target)
        return None

    def _looks_like_file_only(self, paths):
        return bool(paths) and not self.heuristic_intent() and (
            any(p in self.text for p in FILE_HINT) or self.text.endswith('.csv') or self.text.startswith(('use ', 'open ', 'load ', 'select ')))

    def _looks_like_data(self):
        return any(p in self.text for p in DATA_SUM + DATA_ROWS + ('amount', 'csv', 'filter', 'minimum', 'at least', 'region'))

    def _is_correction(self):
        if self.text.startswith(('actually', 'instead', 'no,', 'wait')):
            return True
        return self.ws['last_intent'] is not None and (
            any(p in self.text for p in ORDER_ASC + ORDER_DESC) or
            re.search(r'(?:at least|minimum|min(?:imum)?(?: of)?)\s+-?\d+', self.text))

    def paths(self):
        found = []
        for match in PATH_RE.finditer(self.raw):
            token = next(g for g in match.groups() if g)
            found.append(token)
        return found

    def heuristic_intent(self):
        op = None
        if any(p in self.text for p in DATA_ROWS) or ('rows' in self.text and 'group' not in self.text):
            op = 'rows'
        elif any(p in self.text for p in DATA_SUM):
            op = 'sum'
        order = None
        if any(p in self.text for p in ORDER_ASC):
            order = 'asc'
        elif any(p in self.text for p in ORDER_DESC):
            order = 'desc'
        minimum = None
        bound = re.search(r'(?:at least|minimum|min(?:imum)?(?: of)?)\s+(-?\d+(?:\.\d+)?)', self.text)
        if bound:
            minimum = float(bound.group(1))
        if op is None:
            return None
        prior = self.ws['last_intent'] or {}
        return dict(op=op, min=minimum if minimum is not None else prior.get('min'),
                    order=order or prior.get('order') or 'desc')

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
        target = paths[0] if paths else self.ws['selected_file']
        if not target:
            return self.clarify('file', 'Which other file should I apply the last procedure to?')
        if len(paths) > 1:
            return self.clarify('file', 'I see more than one file. Which one should I use?')
        intent = self.ws['last_intent']
        if intent is None:
            return self.reuse_procedure(path_text=target)
        note = 'Applied the same procedure to '+Path(target).name+'.'
        return self.execute_intent(intent, target, change=note)

    def correct(self, paths):
        intent = dict(self.ws['last_intent'])
        if any(p in self.text for p in ORDER_ASC):
            intent['order'] = 'asc'
        elif any(p in self.text for p in ORDER_DESC):
            intent['order'] = 'desc'
        bound = re.search(r'(?:at least|minimum|min(?:imum)?(?: of)?)\s+(-?\d+(?:\.\d+)?)', self.text)
        if bound:
            intent['min'] = float(bound.group(1))
        target = paths[0] if paths else self.ws['selected_file']
        if not target:
            return self.clarify('file', 'Which file should I apply that correction to?')
        note = 'Changed last procedure to op={op}, min={min}, order={order}.'.format(**intent)
        return self.execute_intent(intent, target, change=note)

    def what_changed(self):
        note = self.ws['last_correction']
        data = dict(last_correction=note, last_intent=self.ws['last_intent'],
                    selected_file=self.ws['selected_file'], last_output_path=self.ws['last_output_path'],
                    last_procedure_id=self.ws['last_procedure_id'], executed=False)
        self.card('Workspace changes', data)
        if not note:
            return 'No correction has been applied yet. I have not changed a procedure in this conversation.', 'reply', False
        return note + ' Model-generated chat is not listed here; only execution-backed procedure edits are.', 'reply', False

    def ordinary_chat(self):
        runtime = self.store.ensure_runtime()
        if runtime is None:
            reason = self.store.runtime_status()['reason'] or 'local_model_unavailable'
            self.card('Local model unavailable', dict(source='runtime_status', reason=reason, executed=False))
            return (
                'No local pretrained model is available, so I cannot run live ordinary chat. '
                + reason + ' Teaching words/skills and the two CSV tools still work. '
                'This is not a template standing in for inference.'
            ), 'clarification', False
        history = []
        for turn in self.conversation.view()['messages'][-4:]:
            history.append('User: '+turn['user'][:400])
            history.append('Assistant: '+turn['assistant'][:400])
        prompt = ('<|im_start|>system\n'+CHAT_SYSTEM+'<|im_end|>\n')
        if history:
            prompt += '<|im_start|>user\nRecent conversation:\n'+'\n'.join(history)+'<|im_end|>\n'
        prompt += '<|im_start|>user\n'+self.raw.strip()+'<|im_end|>\n<|im_start|>assistant\n'
        reply = self.complete(runtime, prompt, None)
        text = reply['content'].strip() or 'I do not have a completion for that.'
        self.card('Model-generated reply', dict(
            source='model_generated', executed=False, inference_ran=reply['telemetry'].get('inference_ran'),
            application_cache_hit=reply['telemetry'].get('application_cache_hit')))
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

    def execute_intent(self, intent, path_text, change=None, capsule=None, saved_explicit=None):
        if self.session.stopped or self.session.cancelled.is_set():
            raise ValueError('cancel')
        path = self.resolve_source(path_text)
        if path is None:
            return self.clarify('file', 'I could not open that CSV. Nothing ran.')
        rows, profiles = self.load_table(path)
        if rows is None:
            return 'That CSV is empty or unreadable. Nothing ran.', 'error', False
        try:
            intent = validate_intent(dict(op=intent['op'], min=intent.get('min'), order=intent.get('order', 'desc')))
        except ValueError:
            return self.clarify('grain', 'I need grouped totals or individual rows, with an optional minimum and sort order.')
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
        preview_ops = [step.get('op') for step in program.ops]
        self.card('Requested transformation preview', dict(
            source='transformation_preview', operations=preview_ops, intent=intent,
            input_file=path.name, source_file_unchanged=True, executed=False))
        if self.session.cancelled.is_set():
            raise ValueError('cancel')
        output = program.execute(rows)
        json.dumps(output, allow_nan=False)
        if type(output) is not list or any(type(row) is not dict for row in output):
            return 'The adapter returned an invalid result shape. The source file is unchanged.', 'error', False
        source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        output_path = self.store.outputs_dir() / (path.stem + '-' + digest(output)[:10] + '.json')
        output_path.write_text(json.dumps(output, allow_nan=False, indent=2), encoding='utf-8')
        receipt = digest(output)
        rendered = ExecutionBackedResponseRenderer.render(path.stem, output, receipt)
        self.ws.update(selected_file=str(path), last_intent=intent, last_output_path=str(output_path),
                       last_source_sha=source_sha, pending_clarification=None,
                       last_correction=change or ('Executed '+intent['op']+' on '+path.name+'.'),
                       last_saved_explicit=bool(capsule and capsule.get('saved_explicitly')))
        if saved_explicit is not None:
            self.ws['last_saved_explicit'] = saved_explicit
        if capsule and capsule.get('saved_explicitly'):
            self.ws['last_procedure_id'] = capsule['id']
        self.card('Execution-backed result', dict(
            source='execution_backed', executed=True, row_count=len(output), preview=output[:5],
            output_path=str(output_path), source_file=str(path), source_file_unchanged=True,
            receipt=receipt, response=rendered, saved_explicitly=bool(capsule and capsule.get('saved_explicitly')),
            autonomously_discovered=False))
        return (
            rendered + ' Wrote '+str(output_path)+'. The source CSV was not modified. '
            'This result is execution-backed, not model-generated.'
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
        if self.ws['last_intent'] is None or not self.ws['selected_file']:
            return 'There is no executed procedure to save yet. Run a CSV transform first. Nothing was stored.', 'clarification', False
        intent = self.ws['last_intent']
        shape = [intent['op'], intent['min'] is not None, intent['order']]
        ops = skeleton(intent)
        identifier = digest(['explicit', shape, self.ws['last_source_sha']])[:16]
        record = dict(
            id=identifier, name=intent['op']+'-'+intent['order'], saved_explicitly=True,
            autonomously_discovered=False, task_kind=intent['op'], shape=shape, skeleton_ops=ops,
            types=dict(key='text', metric='numeric'),
            preconditions=dict(format='csv', unique_text_column=True, unique_numeric_column=True),
            provenance=dict(session_id=self.conversation.session_id, source_sha256=self.ws['last_source_sha'],
                            source_file=str(Path(self.ws['selected_file']).name), revision='explicit_save'),
            validation_scope='Same-schema CSV with one text and one numeric column; grain, filter presence and order must match the saved shape.',
            intent=intent, learning_to_learn=False)
        path = self.store.procedures_dir() / (identifier + '.json')
        path.write_text(json.dumps(record, allow_nan=False, indent=2), encoding='utf-8')
        self.ws['last_procedure_id'] = identifier
        self.ws['last_saved_explicit'] = True
        self.ws['last_correction'] = 'Explicitly saved procedure '+identifier+'. This is stored reuse, not an autonomously discovered abstraction or learning-to-learn.'
        self.card('Saved procedure', dict(id=identifier, path=str(path), saved_explicitly=True,
                                          autonomously_discovered=False, skeleton_ops=ops, executed=False))
        return 'Saved procedure '+identifier+' with its actual AST. Persistence is reuse, not learning-to-learn.', 'success', False

    def _load_capsule(self, identifier=None):
        identifier = identifier or self.ws['last_procedure_id']
        if not identifier:
            explicit=[]
            for path in self.store.procedures_dir().glob('*.json'):
                try:
                    data=json.loads(path.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    continue
                if data.get('saved_explicitly') and data.get('id'):
                    explicit.append(data['id'])
            if len(explicit)==1:
                identifier=explicit[0]
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
        target = path_text or (self.paths()[0] if self.paths() else self.ws['selected_file'])
        if not target:
            return self.clarify('file', 'Which CSV should I apply the saved procedure to?')
        return self.execute_intent(capsule['intent'], target, change='Reused explicitly saved procedure '+capsule['id']+'.',
                                   capsule=capsule, saved_explicit=True)

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
