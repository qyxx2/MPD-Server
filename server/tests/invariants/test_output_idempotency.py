"""F9: external effect, outer failure, retry and committed replay are distinct."""

import asyncio
import json
import sqlite3

import httpx
import pytest
from pydantic import ValidationError

from server.app.main import app
from server.app.repositories import database
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.idempotency_service import IdempotencyService
from server.tests.api.test_system_output_mutations import output_api
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start

__all__ = ["output_api"]


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("failure", ["terminal", "schema", "outer", "cancel", "commit"])
def test_output_external_effect_outer_failure_retry_and_replay(output_api, monkeypatch, enabled, failure):
    client, player, service, manager, calls, events, path = output_api
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        await service.pause()
        await service.seek(17)
        player._outputs[0].enabled = not enabled
        before = await authority_snapshot(service)
        status, entries, outputs = await player.status(), await player.queue_entries(), await player.outputs()
        key = "output-key"
        repository = IdempotencyRepository(path)
        body = {"mode": "NAS_DAC", "enabled": enabled}
        headers = {"Idempotency-Key": key}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            with monkeypatch.context() as fault:
                if failure == "terminal":
                    def trigger(connection):
                        connection.execute("""
                            CREATE TRIGGER fail_output_terminal AFTER INSERT ON idempotency_records
                            WHEN NEW.idempotency_key = 'output-key'
                            BEGIN SELECT RAISE(ABORT, 'output terminal failed'); END
                        """)
                    await database.run_transaction(path, trigger)
                elif failure == "schema":
                    ensure = manager.set_enabled
                    async def invalid_receipt(mode, requested_enabled):
                        receipt = (await ensure(mode, requested_enabled)).model_copy(deep=True)
                        receipt.states[0].status = "PREPARING"
                        return receipt
                    fault.setattr(manager, "set_enabled", invalid_receipt)
                elif failure in {"outer", "cancel"}:
                    consume = IdempotencyService._response_content
                    async def fail_after_response(response):
                        content = await consume(response)
                        assert json.loads(content)["last_request"]["status"] == "SUCCEEDED"
                        assert events == []
                        if failure == "cancel":
                            asyncio.current_task().cancel()
                            await asyncio.sleep(0)
                        raise RuntimeError("outer response consumption failed after effect")
                    fault.setattr(IdempotencyService, "_response_content", staticmethod(fail_after_response))
                elif failure == "commit":
                    class FailCommit(sqlite3.Connection):
                        def commit(self):
                            assert self.execute(
                                "SELECT COUNT(*) FROM idempotency_records WHERE idempotency_key = ?", (key,),
                            ).fetchone()[0] == 1
                            assert events == []
                            raise sqlite3.OperationalError("output outer commit failed")
                    def connect(database_path):
                        connection = sqlite3.connect(database_path, factory=FailCommit)
                        connection.execute("PRAGMA foreign_keys = ON")
                        return connection
                    fault.setattr(database, "_connect", connect)
                calls.clear()
                error = {
                    "terminal": sqlite3.IntegrityError, "schema": ValidationError,
                    "outer": RuntimeError, "cancel": asyncio.CancelledError,
                    "commit": sqlite3.OperationalError,
                }[failure]
                with pytest.raises(error) as caught:
                    await http.put("/api/system/output", json=body, headers=headers)
                if failure == "schema":
                    assert caught.value.errors()[0]["loc"] == ("states", 0, "status")
            if failure == "terminal":
                await database.run_transaction(path, lambda connection: connection.execute("DROP TRIGGER fail_output_terminal"))
            assert await repository.get_by_key(key) is None
            assert events == []
            assert calls.count("set_output_enabled") == 1
            assert await authority_snapshot(service) == before
            assert await player.status() == status
            assert await player.queue_entries() == entries
            assert await player.outputs() == [outputs[0].model_copy(update={"enabled": enabled}), outputs[1]]
            # Failure does not masquerade as SQLite undo of the external device.
            observed = (await http.get("/api/system/output")).json()
            assert observed["states"][0]["status"] == ("ACTIVE" if enabled else "INACTIVE")
            assert observed["states"][0]["stale"] is False
            assert observed["last_request"]["status"] == "SWITCH_FAILED"
            assert observed["last_request"]["errorCode"] == "OUTPUT_TRANSACTION_FAILED"
            calls.clear()
            retried = await http.put("/api/system/output", json=body, headers=headers)
            assert retried.status_code == 200, retried.text
            assert retried.json()["last_request"]["status"] == "SUCCEEDED"
            assert "outputs" in calls
            assert "set_output_enabled" not in calls
            assert events == []  # No new actual change; no durable delivery promise.
            terminal = await repository.get_by_key(key)
            assert terminal.response_body == retried.text
            calls.clear()
            player.disconnect()  # Committed replay must not depend on fresh MPD availability.
            replay = await http.put("/api/system/output", json={"enabled": enabled, "mode": "NAS_DAC"}, headers=headers)
            assert replay.status_code == 200
            assert replay.content == retried.content
            assert calls == events == []
            player.reconnect()
            assert await authority_snapshot(service) == before
            assert await player.status() == status
            assert await player.queue_entries() == entries

    asyncio.run(scenario())


@pytest.mark.parametrize("publisher_failure", [None, "exception", "cancel"])
def test_committed_output_replay_never_recontrols_or_renotifies(output_api, monkeypatch, caplog, publisher_failure):
    client, player, service, manager, calls, _events, path = output_api
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        repository = IdempotencyRepository(path)
        committed_events = []

        class Publisher:
            async def publish(self, event):
                terminal = await asyncio.wait_for(asyncio.create_task(repository.get_by_key("output-key")), 3)
                assert terminal is not None
                assert json.loads(terminal.response_body)["states"][0]["status"] == "ACTIVE"
                committed_events.append(event)
                if publisher_failure == "exception":
                    raise RuntimeError("output delivery failed after commit")
                if publisher_failure == "cancel":
                    asyncio.current_task().cancel()
                    await asyncio.sleep(0)

        monkeypatch.setattr(manager, "event_publisher", Publisher())
        headers = {"Idempotency-Key": "output-key"}
        body = {"mode": "NAS_DAC", "enabled": True}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            calls.clear()
            if publisher_failure == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await http.put("/api/system/output", json=body, headers=headers)
            else:
                response = await http.put("/api/system/output", json=body, headers=headers)
                assert response.status_code == 200
            terminal = await repository.get_by_key("output-key")
            assert terminal is not None
            assert calls.count("set_output_enabled") == 1
            assert len(committed_events) == 1
            assert (await manager.get_state()).last_request.status == "SUCCEEDED"
            assert await authority_snapshot(service) == before
            calls.clear()
            player.disconnect()
            replay = await http.put("/api/system/output", json=body, headers=headers)
            assert replay.status_code == terminal.response_status == 200
            assert replay.text == terminal.response_body
            assert calls == []
            assert len(committed_events) == 1
            player.reconnect()
            assert await authority_snapshot(service) == before
            assert (await player.outputs())[0].enabled is True
        if publisher_failure == "exception":
            assert "Post-commit notification failed" in caplog.text
            assert "output delivery failed after commit" in caplog.text

    asyncio.run(scenario())
