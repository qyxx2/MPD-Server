from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .database import run_transaction


@dataclass(frozen=True)
class IdempotencyRecord:
    operation_scope: str
    idempotency_key: str
    payload_hash: str
    response_status: int
    response_body: str
    created_at: datetime


class IdempotencyRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    async def get_by_key(self, idempotency_key: str) -> IdempotencyRecord | None:
        async def operation(connection):
            row = connection.execute(
                """
                SELECT operation_scope, idempotency_key, payload_hash,
                       response_status, response_body, created_at
                FROM idempotency_records
                WHERE idempotency_key = ?
                ORDER BY created_at
                LIMIT 1
                """,
                (idempotency_key,),
            ).fetchone()
            return self._record_from_row(row) if row is not None else None

        return await run_transaction(self.path, operation)

    async def create(
        self,
        *,
        operation_scope: str,
        idempotency_key: str,
        payload_hash: str,
        response_status: int,
        response_body: str,
    ) -> IdempotencyRecord:
        created_at = datetime.now(timezone.utc)

        async def operation(connection):
            connection.execute(
                """
                INSERT INTO idempotency_records(
                    operation_scope, idempotency_key, payload_hash,
                    response_status, response_body, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_scope,
                    idempotency_key,
                    payload_hash,
                    response_status,
                    response_body,
                    created_at.isoformat(),
                ),
            )
            return IdempotencyRecord(
                operation_scope=operation_scope,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                response_status=response_status,
                response_body=response_body,
                created_at=created_at,
            )

        return await run_transaction(self.path, operation)

    @staticmethod
    def _record_from_row(row) -> IdempotencyRecord:
        return IdempotencyRecord(
            operation_scope=row[0],
            idempotency_key=row[1],
            payload_hash=row[2],
            response_status=row[3],
            response_body=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
