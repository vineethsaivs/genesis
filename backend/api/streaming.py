"""WebSocket event emitter for streaming agent progress to the frontend."""

import asyncio
import json
import logging

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class AgentEventEmitter:
    """Queues structured events for delivery over a WebSocket connection.

    Each public method puts a typed dict onto an internal asyncio.Queue.
    A companion `send_events` coroutine drains the queue and writes JSON
    frames to the WebSocket.  Passing ``None`` (the sentinel) terminates
    the send loop.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit_status(self, message: str, *, status: str = "running") -> None:
        """Emit a generic status update."""
        await self._queue.put({"type": "status", "message": message, "status": status})

    async def emit_evolution_start(self, skill_name: str, trigger_task: str) -> None:
        """Signal that the agent is evolving a new skill."""
        await self._queue.put({
            "type": "evolution_start",
            "data": {"skill_name": skill_name, "trigger_task": trigger_task},
        })

    async def emit_code_chunk(self, chunk: str) -> None:
        """Stream a chunk of generated code."""
        await self._queue.put({"type": "code_chunk", "data": {"chunk": chunk}})

    async def emit_test_result(self, passed: bool, detail: str = "") -> None:
        """Report test execution outcome."""
        await self._queue.put({
            "type": "test_result",
            "data": {"passed": passed, "detail": detail},
        })

    async def emit_skill_tree_update(self, tree: dict) -> None:
        """Push the latest skill-tree graph to the frontend."""
        await self._queue.put({"type": "skill_tree_update", "data": tree})

    async def emit_complete(self, message: str = "Task complete") -> None:
        """Signal that the agent has finished, then enqueue the sentinel."""
        await self._queue.put({"type": "complete", "message": message, "status": "complete"})
        await self._queue.put(None)

    async def close(self) -> None:
        """Force-close by injecting the sentinel."""
        await self._queue.put(None)

    # -- internal -----------------------------------------------------------

    @property
    def queue(self) -> asyncio.Queue[dict | None]:
        """Expose queue for the send loop."""
        return self._queue


async def send_events(websocket: WebSocket, emitter: AgentEventEmitter) -> None:
    """Drain *emitter*'s queue and send each event as JSON over *websocket*.

    Terminates when it receives ``None`` (the sentinel).
    """
    while True:
        event = await emitter.queue.get()
        if event is None:
            break
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(event))
        except Exception:
            logger.exception("Error sending WebSocket event")
            break
