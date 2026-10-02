from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository


class _RollbackResponse(Exception):
    def __init__(self, response: Response) -> None:
        self.response = response


class IdempotencyService:
    def __init__(self, repository: IdempotencyRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        key = request.headers["Idempotency-Key"]
        scope = f"{request.method} {request.url.path}"
        payload_hash = self._payload_hash(await request.body())

        async def operation(_connection) -> Response:
            existing = await self._repository.get_by_key(key)
            if existing is not None:
                if (
                    existing.operation_scope != scope
                    or existing.payload_hash != payload_hash
                ):
                    return self._conflict_response()
                return Response(
                    content=existing.response_body,
                    status_code=existing.response_status,
                    media_type="application/json",
                )

            response = await call_next(request)
            content = await self._response_content(response)
            replayable = Response(
                content=content,
                status_code=response.status_code,
                media_type=response.media_type,
            )
            if response.status_code >= 400:
                raise _RollbackResponse(replayable)

            await self._repository.create(
                operation_scope=scope,
                idempotency_key=key,
                payload_hash=payload_hash,
                response_status=response.status_code,
                response_body=content.decode("utf-8"),
            )
            return replayable

        try:
            return await run_transaction(self._repository.path, operation)
        except _RollbackResponse as exc:
            return exc.response

    @staticmethod
    def _payload_hash(body: bytes) -> str:
        try:
            canonical_payload = json.dumps(
                json.loads(body),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except json.JSONDecodeError:
            canonical_payload = body
        return hashlib.sha256(canonical_payload).hexdigest()

    @staticmethod
    async def _response_content(response: Response) -> bytes:
        return b"".join([chunk async for chunk in response.body_iterator])

    @staticmethod
    def _conflict_response() -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "IDEMPOTENCY_KEY_CONFLICT",
                    "message": "Idempotency-Key was already used for a different request",
                    "details": None,
                }
            },
        )
