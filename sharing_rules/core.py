"""A pure-Python model of a federated data structure with sharing rules.

Independent **instances** (nodes) share **records** with each other under
configurable **sharing rules**. The whole point is to make one question a
queryable fact:

    what does each instance PHYSICALLY hold — and therefore, what could a
    subpoena to that operator compel?

The crux is the sharing *mode*:

  * DUPLICATE — a real copy lands on each allowed instance. It lives there,
    independently, and is reachable by a subpoena to that instance. Revoking the
    share does NOT recall the copy (best-effort purge only) — you cannot fully
    un-share a copy.
  * REFERENCE — the record stays only on its origin; other instances resolve a
    pointer at read time. Nothing is held elsewhere, so a subpoena to a viewing
    instance reaches nothing, and revocation is immediate (the origin simply
    stops serving it).

Pure standard library: this is a reference model to reason and test with.
"""
from __future__ import annotations

import copy as _copy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional


class Scope(Enum):
    """WHO a record may reach."""
    PRIVATE = 'private'      # origin only
    HANDSHAKE = 'handshake'  # instances with an accepted handshake to the origin
    ALLOWLIST = 'allowlist'  # an explicit set of instance ids
    PUBLIC = 'public'        # every instance in the network


class Mode(Enum):
    """HOW a record reaches an allowed instance."""
    REFERENCE = 'reference'  # origin-held; others resolve a pointer, hold nothing
    DUPLICATE = 'duplicate'  # a copy is placed on each allowed instance


@dataclass(frozen=True)
class SharingRule:
    scope: Scope
    mode: Mode
    allow: frozenset = frozenset()   # instance ids, only meaningful for ALLOWLIST

    @staticmethod
    def of(scope, mode, allow=()):
        return SharingRule(Scope(scope) if isinstance(scope, str) else scope,
                           Mode(mode) if isinstance(mode, str) else mode,
                           frozenset(allow))


@dataclass
class Record:
    id: str
    origin: str            # instance id that created it
    payload: object
    rule: SharingRule
    is_copy: bool = False  # True for a duplicated copy living on a non-origin


class Instance:
    """A node. Its store is what PHYSICALLY lives here."""

    def __init__(self, iid: str):
        self.id = iid
        self.originals: dict[str, Record] = {}   # records this instance created
        self.copies: dict[str, Record] = {}      # duplicates received from elsewhere

    def __repr__(self):
        return f'Instance({self.id!r})'


class Network:
    """The substrate: instances + handshake trust edges + the sharing router.

    A central "cloud" needs no special type here — it is just an instance that
    others handshake with and share to. If records are shared to it by DUPLICATE
    it accumulates copies (and subpoena exposure); by REFERENCE it holds only
    pointers.
    """

    def __init__(self):
        self.instances: dict[str, Instance] = {}
        self._handshakes: set[frozenset] = set()   # {frozenset({a, b}), ...}
        self._records: dict[str, Record] = {}      # canonical originals, by id

    # ── topology ────────────────────────────────────────────────────────────
    def add_instance(self, iid: str) -> Instance:
        inst = self.instances.get(iid)
        if inst is None:
            inst = Instance(iid)
            self.instances[iid] = inst
        return inst

    def add_handshake(self, a: str, b: str) -> None:
        """Establish mutual trust between two instances, then let existing
        DUPLICATE shares flow to the newly-trusted instance."""
        self.add_instance(a); self.add_instance(b)
        self._handshakes.add(frozenset({a, b}))
        self._propagate_all()

    def remove_handshake(self, a: str, b: str) -> None:
        """Break trust. REFERENCE access disappears at once (it is computed
        live); DUPLICATE copies already delivered LINGER until purged — the
        model refuses to pretend a copy can be recalled."""
        self._handshakes.discard(frozenset({a, b}))
        # deliberately no purge here — see purge_duplicates()

    def has_handshake(self, a: str, b: str) -> bool:
        return frozenset({a, b}) in self._handshakes

    # ── records + sharing ───────────────────────────────────────────────────
    def add_record(self, rid: str, origin: str, payload, rule: SharingRule) -> Record:
        self.add_instance(origin)
        rec = Record(id=rid, origin=origin, payload=payload, rule=rule)
        self._records[rid] = rec
        self.instances[origin].originals[rid] = rec
        self._propagate(rec)
        return rec

    def set_rule(self, rid: str, rule: SharingRule) -> None:
        """Change a record's sharing rule. Reference visibility follows
        immediately; duplicate copies already out there linger until purged."""
        self._records[rid].rule = rule
        self._propagate(self._records[rid])

    def unshare(self, rid: str) -> None:
        """Stop sharing entirely (origin-only). Same lingering-copy caveat."""
        rec = self._records[rid]
        self.set_rule(rid, replace(rec.rule, scope=Scope.PRIVATE))

    def allowed_targets(self, rec: Record) -> set[str]:
        """Instance ids (excluding the origin) the rule currently permits."""
        others = [i for i in self.instances if i != rec.origin]
        s = rec.rule.scope
        if s is Scope.PRIVATE:
            return set()
        if s is Scope.PUBLIC:
            return set(others)
        if s is Scope.ALLOWLIST:
            return set(others) & set(rec.rule.allow)
        if s is Scope.HANDSHAKE:
            return {i for i in others if self.has_handshake(rec.origin, i)}
        raise ValueError(s)

    def _propagate(self, rec: Record) -> None:
        """Materialize DUPLICATE copies onto every currently-allowed target that
        does not already hold one. Never removes copies (that is purge's job),
        and never stores anything for REFERENCE (those are resolved live)."""
        if rec.rule.mode is not Mode.DUPLICATE:
            return
        for tid in self.allowed_targets(rec):
            tgt = self.instances[tid]
            if rec.id not in tgt.copies:
                tgt.copies[rec.id] = Record(id=rec.id, origin=rec.origin,
                                            payload=_copy.deepcopy(rec.payload),
                                            rule=rec.rule, is_copy=True)

    def _propagate_all(self) -> None:
        for rec in self._records.values():
            self._propagate(rec)

    def purge_duplicates(self, rid: Optional[str] = None) -> int:
        """Best-effort recall: delete duplicate copies that the rule no longer
        allows (a real operator's takedown request). Returns how many were
        removed. This is the ONLY way a copy leaves an instance — and in the
        real world it is not guaranteed to succeed, which is the point."""
        removed = 0
        records = [self._records[rid]] if rid else list(self._records.values())
        for rec in records:
            allowed = self.allowed_targets(rec) if rec.rule.mode is Mode.DUPLICATE else set()
            for inst in self.instances.values():
                if inst.id == rec.origin:
                    continue
                if rec.id in inst.copies and inst.id not in allowed:
                    del inst.copies[rec.id]
                    removed += 1
        return removed

    # ── queries: seeing vs. holding ─────────────────────────────────────────
    def holdings(self, iid: str) -> dict[str, str]:
        """What PHYSICALLY lives on this instance: {record_id: 'origin'|'copy'}.
        This is the subpoena-exposure set — what a subpoena to this operator
        could compel. References are absent by construction."""
        inst = self.instances[iid]
        out = {rid: 'origin' for rid in inst.originals}
        out.update({rid: 'copy' for rid in inst.copies})
        return out

    # A subpoena to an operator reaches exactly what that operator holds.
    subpoena_exposure = holdings

    def visible_to(self, iid: str) -> dict[str, str]:
        """What this instance can READ: its holdings, plus REFERENCE records it
        is currently allowed to resolve from their origin. A duplicate copy that
        lingers after revocation is still visible here — because it is still
        physically held; that is the copy problem made concrete."""
        seen = dict(self.holdings(iid))
        for rec in self._records.values():
            if rec.id in seen:
                continue
            if rec.rule.mode is Mode.REFERENCE and iid in self.allowed_targets(rec):
                seen[rec.id] = 'reference'
        return seen

    def can_read(self, iid: str, rid: str) -> bool:
        return rid in self.visible_to(iid)
