from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import uuid4

import anyio
from fastapi import WebSocket, WebSocketDisconnect

from server.app.models.realtime import FullStateSnapshot
from server.app.services.realtime_coordinator import (
    RealtimeCoordinator,
    RealtimeSubscription,
)
from server.app.services.state_service import StateService

logger = logging.getLogger(__name__)


class RealtimeConnections:
    """Subscribe before capture; sockets only deliver authoritative Service reads."""

    def __init__(
        self, *, state_service: StateService, coordinator: RealtimeCoordinator,
        snapshot_encoder: Callable[[FullStateSnapshot], dict], send_timeout: float = 10,
    ) -> None:
        self._state = state_service
        self._coordinator = coordinator
        self._snapshot_encoder = snapshot_encoder
        self._send_timeout = send_timeout
        self._connections: dict[str, RealtimeSubscription] = {}

    async def disconnect(self, connection_id: str) -> None:
        subscription = self._connections.pop(connection_id, None)
        if subscription is not None:
            self._coordinator.unsubscribe(subscription)

    async def connect(self, socket: WebSocket) -> None:
        connection_id = str(uuid4())
        tasks = []
        close_code = None
        await socket.accept()
        try:
            try:
                subscription = await self._coordinator.subscribe_committed()
                self._connections[connection_id] = subscription
                snapshot = await self._state.get_full_snapshot()
                state = self._snapshot_encoder(snapshot)
            except Exception:
                logger.exception("Realtime initial snapshot unavailable connection=%s", connection_id)
                close_code = 1011
                return

            async def send():
                if not subscription.valid:
                    raise RuntimeError("realtime subscription invalidated")
                await asyncio.wait_for(socket.send_json({
                    "type": "snapshot", "protocol_version": 1,
                    "epoch": snapshot.epoch, "sequence": snapshot.sequence, "state": state,
                }), self._send_timeout)
                waterline = snapshot.sequence
                while True:
                    notification = await subscription.receive()
                    if notification.sequence <= waterline:
                        continue
                    await asyncio.wait_for(socket.send_json({
                        "type": "invalidate", "protocol_version": 1,
                        "epoch": notification.epoch, "sequence": notification.sequence,
                        "domains": sorted(notification.domains),
                        "revisions": notification.revisions,
                    }), self._send_timeout)
                    waterline = notification.sequence

            async def receive_disconnect():
                while (await socket.receive())["type"] != "websocket.disconnect":
                    pass

            async def watch_invalidation():
                await subscription.invalidated.wait()
                raise RuntimeError("realtime subscription invalidated")

            tasks = [asyncio.create_task(send()), asyncio.create_task(receive_disconnect()),
                     asyncio.create_task(watch_invalidation())]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Realtime delivery failed connection=%s", connection_id)
            close_code = 1013
        finally:
            # ASGI uses level cancellation: protect the cleanup checkpoint from
            # repeated cancel-scope delivery while child tasks release resources.
            with anyio.CancelScope(shield=True):
                await self.disconnect(connection_id)
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if close_code is not None:
                    try:
                        await asyncio.wait_for(socket.close(code=close_code), self._send_timeout)
                    except Exception:
                        logger.exception("Realtime close failed connection=%s", connection_id)
