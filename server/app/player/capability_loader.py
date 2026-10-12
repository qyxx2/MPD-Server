"""Load explicit endpoint-bound proof without running capability probes."""
import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter

from server.app.player.capabilities import OPERATION_COMMANDS, MPDCapabilities
from server.app.services.mpd_connection_service import MPDConnectionAddress

VersionReader = Callable[[str, int], Awaitable[str | None]]


class CapabilityEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    endpoint: MPDConnectionAddress
    mpd_version: str
    result: dict


async def read_endpoint_version(host: str, port: int) -> str | None:
    """A bounded greeting-only connection: no password or MPD commands sent."""
    writer = None
    try:
        async with asyncio.timeout(3):
            reader, writer = await asyncio.open_connection(host, port)
            greeting = (await reader.readline()).decode('utf-8').rstrip('\r\n')
            if not greeting.startswith('OK MPD '):
                return None
            return greeting.removeprefix('OK MPD ') or None
    except (TimeoutError, OSError, UnicodeError, ValueError):
        return None
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (TimeoutError, OSError):
                pass


async def load_capabilities(
    path: Path | None, *, host: str, port: int,
    version_reader: VersionReader | None = None,
) -> MPDCapabilities:
    empty = MPDCapabilities.from_commands(set())
    if path is None:
        return empty
    try:
        proof = CapabilityEvidence.model_validate(json.loads(path.read_text()))
        allowed = set(MPDCapabilities.__dataclass_fields__)
        if set(proof.result) - allowed:
            raise ValueError('Unknown capability field')
        capabilities = TypeAdapter(MPDCapabilities).validate_python(proof.result)
        if (not proof.mpd_version or capabilities.version != proof.mpd_version or
                capabilities.verified_operations - OPERATION_COMMANDS.keys()):
            raise ValueError('Invalid capability version or operations')
    except (OSError, ValueError, TypeError):
        # A historical bare result must be explicitly rebound, never inferred.
        raise ValueError('Invalid MPD capability evidence; endpoint/version envelope required') from None
    if proof.endpoint != MPDConnectionAddress(host=host, port=port):
        return empty
    observed_version = await (version_reader or read_endpoint_version)(host, port)
    return capabilities if observed_version == proof.mpd_version else empty
