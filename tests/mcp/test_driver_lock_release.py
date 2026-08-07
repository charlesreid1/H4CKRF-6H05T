"""Regression: driver_lock must always release on cancel.

The MCP server acquires driver_lock around every tool call and clears
current_tool_task in a finally block. This test wires up the same
pattern in isolation and cancels the in-flight task — the lock must
be releasable within a short window.
"""

from __future__ import annotations

import asyncio

import pytest


async def _tool_call_pattern(driver_lock: asyncio.Lock, done: asyncio.Event) -> None:
    """Mirror the server's ``call_tool`` acquire/release pattern.

    The lock is acquired via ``async with``, then a long-running action is
    awaited inside. When the task is cancelled, ``async with`` must still
    release the lock, even though the coroutine did not complete normally.
    """
    async with driver_lock:
        done.set()
        # Simulate a long-running driver operation.
        await asyncio.sleep(30.0)


class TestDriverLockRelease:
    async def test_lock_releases_on_cancel_within_100ms(self) -> None:
        driver_lock = asyncio.Lock()
        done = asyncio.Event()

        task = asyncio.create_task(_tool_call_pattern(driver_lock, done))
        # Wait for the task to acquire the lock.
        await asyncio.wait_for(done.wait(), timeout=1.0)
        assert driver_lock.locked()

        # Cancel — simulating the SIGINT handler on the server side.
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # The lock should be releasable — a fresh acquisition must succeed
        # essentially immediately (< 100 ms in real terms; asyncio's clock
        # is monotonic and reliable).
        acquired = await asyncio.wait_for(driver_lock.acquire(), timeout=0.1)
        assert acquired is True
        driver_lock.release()

    async def test_lock_releases_on_exception(self) -> None:
        driver_lock = asyncio.Lock()

        async def raiser() -> None:
            async with driver_lock:
                raise RuntimeError("simulated driver failure")

        with pytest.raises(RuntimeError, match="simulated"):
            await raiser()

        # Lock is free.
        assert not driver_lock.locked()
        acquired = await asyncio.wait_for(driver_lock.acquire(), timeout=0.1)
        assert acquired
        driver_lock.release()
