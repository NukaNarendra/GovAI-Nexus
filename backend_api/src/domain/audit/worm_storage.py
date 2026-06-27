import json
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.infrastructure.database.models.audit_log import AuditLog
from src.infrastructure.database.repository.audit_repo import AuditLogRepository


class WORMStorageError(Exception):
    pass


class CryptographicChainBrokenError(WORMStorageError):
    pass


class ImmutabilityViolationError(WORMStorageError):
    pass


class WORMStorageManager:
    def __init__(self, repository: AuditLogRepository):
        self.repository = repository
        self._genesis_hash = "0" * 64
        self.export_chunk_size = 5000

    async def _get_latest_chain_hash(self, db: AsyncSession) -> str:
        query = (
            select(AuditLog.cryptographic_hash)
            .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
            .limit(1)
        )
        result = await db.execute(query)
        last_hash = result.scalar_one_or_none()
        return last_hash if last_hash else self._genesis_hash

    async def append_immutable_record(
        self, db: AsyncSession, log_entry: AuditLog
    ) -> AuditLog:
        if (
            log_entry.id is not None
            and await self.repository.get(db, log_entry.id) is not None
        ):
            raise ImmutabilityViolationError(
                "Attempted to overwrite an existing WORM record. This is strictly forbidden."
            )

        previous_hash = await self._get_latest_chain_hash(db)

        log_entry.seal_log(prev_hash=previous_hash)

        try:
            db.add(log_entry)
            await db.flush()
            return log_entry
        except IntegrityError as e:
            await db.rollback()
            raise WORMStorageError(
                f"Failed to append record. Cryptographic hash collision or database constraint violated: {str(e)}"
            )
        except Exception as e:
            await db.rollback()
            raise WORMStorageError(
                f"Unexpected error appending to WORM storage: {str(e)}"
            )

    async def _prevent_mutations(self) -> None:
        raise ImmutabilityViolationError(
            "WORM storage enforces append-only operations. Updates and Deletions are mathematically prohibited."
        )

    async def verify_ledger_integrity(
        self,
        db: AsyncSession,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> Dict[str, Any]:
        query = (
            select(AuditLog)
            .where(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .order_by(asc(AuditLog.timestamp), asc(AuditLog.id))
        )

        result = await db.execute(query)
        logs = list(result.scalars().all())

        if not logs:
            return {
                "status": "CLEAN",
                "records_scanned": 0,
                "tampered_records": [],
                "chain_breaks": [],
            }

        tampered_records = []
        chain_breaks = []

        for i in range(len(logs)):
            current_log = logs[i]

            if not current_log.verify_integrity():
                tampered_records.append(
                    {
                        "id": current_log.id,
                        "timestamp": current_log.timestamp.isoformat(),
                        "recorded_hash": current_log.cryptographic_hash,
                        "computed_hash": current_log.calculate_hash(
                            current_log.previous_hash
                        ),
                    }
                )

            if i > 0:
                previous_log = logs[i - 1]
                if current_log.previous_hash != previous_log.cryptographic_hash:
                    chain_breaks.append(
                        {
                            "previous_record_id": previous_log.id,
                            "current_record_id": current_log.id,
                            "expected_previous_hash": previous_log.cryptographic_hash,
                            "actual_previous_hash_stored": current_log.previous_hash,
                        }
                    )

        status = "COMPROMISED" if (tampered_records or chain_breaks) else "CLEAN"

        return {
            "status": status,
            "records_scanned": len(logs),
            "tampered_records": tampered_records,
            "chain_breaks": chain_breaks,
            "scan_timestamp": datetime.datetime.utcnow().isoformat(),
        }

    async def generate_auditor_export(
        self,
        db: AsyncSession,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> Dict[str, Any]:
        integrity_check = await self.verify_ledger_integrity(db, start_date, end_date)

        if integrity_check["status"] != "CLEAN":
            raise CryptographicChainBrokenError(
                "Cannot generate certified export. Ledger integrity validation failed. "
                f"Tampered records: {len(integrity_check['tampered_records'])}. "
                f"Chain breaks: {len(integrity_check['chain_breaks'])}."
            )

        query = (
            select(AuditLog)
            .where(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .order_by(asc(AuditLog.timestamp), asc(AuditLog.id))
        )

        result = await db.execute(query)
        logs = list(result.scalars().all())

        manifest_hash = hashlib.sha256()
        exported_records = []

        for log in logs:
            record_dict = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "event_type": log.event_type.value
                if hasattr(log.event_type, "value")
                else log.event_type,
                "severity": log.severity.value
                if hasattr(log.severity, "value")
                else log.severity,
                "actor_id": log.actor_id,
                "resource_id": log.resource_id,
                "action_details": log.action_details,
                "previous_hash": log.previous_hash,
                "cryptographic_hash": log.cryptographic_hash,
            }
            exported_records.append(record_dict)

            record_bytes = json.dumps(record_dict, sort_keys=True).encode("utf-8")
            manifest_hash.update(record_bytes)

        export_metadata = {
            "export_id": str(uuid.uuid4()),
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_records": len(exported_records),
            "manifest_cryptographic_signature": manifest_hash.hexdigest(),
            "certified_by": "NEUROLEARN_GOVERNANCE_OS_WORM_ENGINE",
            "integrity_status": "VERIFIED_CLEAN",
        }

        return {"metadata": export_metadata, "records": exported_records}

    async def run_nightly_integrity_job(self, db: AsyncSession) -> Dict[str, Any]:
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(days=1)
        return await self.verify_ledger_integrity(db, start_time, end_time)
