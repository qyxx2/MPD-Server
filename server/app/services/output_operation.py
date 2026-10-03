from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

T = TypeVar("T")


class OutputOperationLifecycle(Protocol):
    def on_commit(self, callback: Callable[[], object | Awaitable[object]]) -> None: ...

    def on_rollback(self, callback: Callable[[], None]) -> None: ...


class OutputOperationRunner(Protocol):
    async def __call__(
        self, operation: Callable[[OutputOperationLifecycle], Awaitable[T]],
    ) -> T: ...
