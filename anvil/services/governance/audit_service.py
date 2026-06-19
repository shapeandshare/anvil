"""Hash-chained, tamper-evident audit trail service.

Records every consequential lifecycle action in a verifiable,
append-only hash chain. Each entry stores the SHA-256 hash of the
prior entry so that any insertion, alteration, or deletion is
detectable by recomputing the chain.

**Must NOT** mimic the ``TrackingService`` fire-and-forget pattern —
audit-write failure is raised, not silently swallowed (FR-011).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from .audit_action import AuditAction
from .audit_outcome import AuditOutcome
from .audit_target_type import AuditTargetType
from .chain_verify_result import ChainVerifyResult

from ...db.models.audit_event import AuditEvent
from ...db.repositories.audit_events import AuditEventRepository


def _canonical_json(obj: dict) -> str:
    """Serialise *obj* to a deterministic, compact JSON string.

    Uses sorted keys and ``separators=(",", ":")`` to produce a
    reproducible input for hash computation.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _compute_entry_hash(
    sequence: int,
    action_type: str,
    target_type: str,
    target_id: str | None,
    actor: str,
    outcome: str,
    reason: str | None,
    params_json: str | None,
    event_timestamp: str,
    prev_hash: str,
) -> str:
    """Return the hex SHA-256 hash of a canonical entry representation."""
    payload = _canonical_json(
        {
            "sequence": sequence,
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "actor": actor,
            "outcome": outcome,
            "reason": reason,
            "params_json": params_json,
            "event_timestamp": event_timestamp,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


GENESIS_PREV_HASH = "0" * 64


class AuditService:
    """Hash-chained audit trail service.

    Parameters
    ----------
    repo : AuditEventRepository
        Repository for persisting and querying audit events.
    """

    def __init__(self, repo: AuditEventRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        action_type: str,
        target_type: str,
        target_id: str | None,
        actor: str,
        outcome: str,
        reason: str | None = None,
        params: dict[str, object] | None = None,
        event_timestamp: datetime | None = None,
    ) -> AuditEvent:
        """Append a new entry to the audit chain.

        Reads the current chain tail, computes the new entry's hash,
        and persists within the same transaction as the caller's
        action.  **Raises** on failure — never silently swallows
        (FR-011).

        Parameters
        ----------
        action_type : str
            One of the :class:`AuditAction` value strings.
        target_type : str
            One of the :class:`AuditTargetType` value strings.
        target_id : str or None
            Loose reference to the target entity.
        actor : str
            Operating user/session or automated process name.
        outcome : str
            One of the :class:`AuditOutcome` value strings.
        reason : str, optional
            Human-readable explanation (esp. for rejections).
        params : dict, optional
            Structured parameters.  MUST contain references/summaries
            only — never full content bodies (FR-013).  The service
            strips/normalises before storing as JSON.
        event_timestamp : datetime, optional
            The action's timestamp.  Defaults to ``datetime.now(timezone.utc)``.

        Returns
        -------
        AuditEvent
            The persisted entry.

        Raises
        ------
        Exception
            Any persistence error is propagated to the caller so the
            surrounding transaction can be rolled back.
        """
        if event_timestamp is None:
            event_timestamp = datetime.now(datetime.UTC)

        # Determine the chain tail and compute the next sequence/hash.
        tail = await self._repo.get_tail()
        if tail is None:
            sequence = 1
            prev_hash = GENESIS_PREV_HASH
        else:
            sequence = tail.sequence + 1
            prev_hash = tail.entry_hash

        # Serialise params — strip to references/summaries only (FR-013).
        params_json: str | None = None
        if params is not None:
            # Normalise: keep only primitive / reference values.
            cleaned: dict[str, object] = {}
            for k, v in params.items():
                if isinstance(v, (str, int, float, bool)):
                    cleaned[k] = v
                elif v is None:
                    cleaned[k] = v
                else:
                    cleaned[k] = str(v)
            params_json = _canonical_json(cleaned) if cleaned else None

        ts_iso = event_timestamp.isoformat()
        entry_hash = _compute_entry_hash(
            sequence=sequence,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            outcome=outcome,
            reason=reason,
            params_json=params_json,
            event_timestamp=ts_iso,
            prev_hash=prev_hash,
        )

        event = AuditEvent(
            sequence=sequence,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            outcome=outcome,
            reason=reason,
            params_json=params_json,
            event_timestamp=event_timestamp,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        return await self._repo.append(event)

    async def verify_chain(self) -> ChainVerifyResult:
        """Verify the integrity of the entire hash chain.

        Returns
        -------
        ChainVerifyResult
            ``valid=True`` for an untouched chain; ``valid=False`` with
            the first ``break_at_sequence`` for any tampered entry.
        """
        entries = await self._repo.all_ordered()
        if not entries:
            return ChainVerifyResult(valid=True, entries_checked=0)

        expected_prev = GENESIS_PREV_HASH
        for entry in entries:
            # 1. Check prev_hash linkage.
            if entry.prev_hash != expected_prev:
                return ChainVerifyResult(
                    valid=False,
                    break_at_sequence=entry.sequence,
                    entries_checked=entry.sequence,
                )
            # 2. Recompute and check the entry's own hash.
            recomputed = _compute_entry_hash(
                sequence=entry.sequence,
                action_type=entry.action_type,
                target_type=entry.target_type,
                target_id=entry.target_id,
                actor=entry.actor,
                outcome=entry.outcome,
                reason=entry.reason,
                params_json=entry.params_json,
                event_timestamp=entry.event_timestamp.isoformat()
                if entry.event_timestamp
                else "",
                prev_hash=entry.prev_hash,
            )
            if recomputed != entry.entry_hash:
                return ChainVerifyResult(
                    valid=False,
                    break_at_sequence=entry.sequence,
                    entries_checked=entry.sequence,
                )
            expected_prev = entry.entry_hash

        return ChainVerifyResult(valid=True, entries_checked=len(entries))

    async def list_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        action_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[AuditEvent]:
        """Return filtered audit entries in chronological order."""
        return await self._repo.query(
            target_type=target_type,
            target_id=target_id,
            action_type=action_type,
            limit=limit,
            offset=offset,
        )

    async def checkpoint(self, *, actor: str, reason: str) -> AuditEvent:
        """Append a ``CHAIN_CHECKPOINT`` event.

        This is the only sanctioned way to mark archival/reset on the
        audit chain (FR-023).  Does **not** delete prior entries.
        """
        return await self.record(
            action_type=AuditAction.CHAIN_CHECKPOINT.value,
            target_type=AuditTargetType.AUDIT_CHAIN.value,
            target_id=None,
            actor=actor,
            outcome=AuditOutcome.SUCCESS.value,
            reason=reason,
        )
