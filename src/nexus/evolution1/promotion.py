"""Synthetic promotion/rollback message contract, not scientific authority.

No checkpoints, files, real policy state or execution permissions are modified.
HMAC illustrates an independent test auditor; same-process secrets are not a
secure boundary. Production audit signing/attestation is intentionally absent.
"""
from dataclasses import dataclass
import hashlib
import hmac

from .catalogue import CATALOGUE_DIGEST,ContractError,canonical,catalogue,digest


def _hash(value):
    if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ContractError('invalid_state_reference')


@dataclass(frozen=True)
class FixtureSnapshot:
    variant_id: str
    rng_state_hash: str
    context_state_hash: str
    memory_state_hash: str

    def __post_init__(self):
        if type(self.variant_id) is not str or self.variant_id not in {v.fingerprint for v in catalogue()}:
            raise ContractError('unknown_variant')
        for v in (self.rng_state_hash,self.context_state_hash,self.memory_state_hash):_hash(v)

    def payload(self):
        return dict(variant_id=self.variant_id,rng_state_hash=self.rng_state_hash,
                    context_state_hash=self.context_state_hash,memory_state_hash=self.memory_state_hash)

    @property
    def fingerprint(self):return digest(self.payload())


@dataclass(frozen=True)
class FixtureAudit:
    candidate_hash: str
    training_journal_head: str
    decision: str
    signature: str

    def __post_init__(self):
        for value in (self.candidate_hash,self.training_journal_head,self.signature):_hash(value)
        if type(self.decision) is not str or self.decision not in {'pass','reject','incomplete','invalid'}:
            raise ContractError('invalid_audit_decision')


def _message(candidate_hash,head,decision):
    return canonical(dict(mode='synthetic_fixture_only',catalogue=CATALOGUE_DIGEST,
                          candidate_hash=candidate_hash,training_journal_head=head,decision=decision)).encode()


class FixtureAuditor:
    def __init__(self,test_key):
        if type(test_key) is not bytes or len(test_key)<16:raise ContractError('invalid_fixture_key')
        self._key=test_key

    def attest(self,snapshot,training_journal_head,decision):
        if type(snapshot) is not FixtureSnapshot:raise ContractError('invalid_snapshot')
        _hash(training_journal_head)
        if type(decision) is not str or decision not in {'pass','reject','incomplete','invalid'}:
            raise ContractError('invalid_audit_decision')
        msg=_message(snapshot.fingerprint,training_journal_head,decision)
        return FixtureAudit(snapshot.fingerprint,training_journal_head,decision,hmac.new(self._key,msg,hashlib.sha256).hexdigest())


class FixturePromotionHarness:
    def __init__(self,initial,test_key):
        if type(initial) is not FixtureSnapshot:raise ContractError('invalid_snapshot')
        FixtureAuditor(test_key)
        self._key=test_key;self._history=(initial,);self._used_audits=set()
        self._archive=(initial,);self._events=()

    @property
    def incumbent(self):return self._history[-1]

    @property
    def archived_snapshots(self):return self._archive

    @property
    def events(self):return self._events

    def promote_for_test(self,candidate,training_journal_head,audit):
        if type(candidate) is not FixtureSnapshot or type(audit) is not FixtureAudit:raise ContractError('independent_fixture_audit_required')
        _hash(training_journal_head)
        msg=_message(audit.candidate_hash,audit.training_journal_head,audit.decision)
        expected=hmac.new(self._key,msg,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,audit.signature):raise ContractError('invalid_fixture_signature')
        if audit.signature in self._used_audits:raise ContractError('audit_replay')
        if audit.candidate_hash!=candidate.fingerprint or audit.training_journal_head!=training_journal_head:
            raise ContractError('audit_binding_mismatch')
        if audit.decision!='pass':raise ContractError('fixture_audit_not_passed')
        self._used_audits.add(audit.signature);self._history+=(candidate,)
        self._archive+=(candidate,)
        self._events+=(('promoted',candidate.fingerprint,audit.signature),)

    def rollback_for_test(self):
        if len(self._history)<2:raise ContractError('no_fixture_rollback')
        previous=self._history[-2]
        self._history=self._history[:-1]
        self._events+=(('rolled_back',previous.fingerprint,None),)
        return previous
