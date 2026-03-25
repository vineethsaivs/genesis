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

    Events use flat structure with ``"event"`` as the discriminator key,
    matching the frontend ``AgentEvent`` TypeScript interface.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit_status(self, message: str, *, status: str = "executing") -> None:
        """Emit a generic status update."""
        await self._queue.put({
            "event": "agent_status",
            "status": status,
            "message": message,
        })

    async def emit_evolution_start(self, skill_name: str, trigger_task: str) -> None:
        """Signal that the agent is evolving a new skill."""
        await self._queue.put({
            "event": "evolution_start",
            "skill_name": skill_name,
            "message": f"Evolving new skill: {skill_name}",
        })

    async def emit_code_chunk(self, chunk: str, skill_name: str = "") -> None:
        """Stream a chunk of generated code."""
        await self._queue.put({
            "event": "code_stream",
            "chunk": chunk,
            "skill_name": skill_name,
        })

    async def emit_test_result(
        self, passed: bool, detail: str = "", skill_name: str = ""
    ) -> None:
        """Report test execution outcome."""
        await self._queue.put({
            "event": "test_result",
            "passed": passed,
            "details": detail,
            "skill_name": skill_name,
        })

    async def emit_skill_tree_update(
        self, node: dict, edge: dict | None = None
    ) -> None:
        """Push a new skill-tree node (and optional edge) to the frontend."""
        payload: dict = {"event": "skill_tree_update", "node": node}
        if edge is not None:
            payload["edge"] = edge
        await self._queue.put(payload)

    async def emit_complete(self, response: str = "Task complete") -> None:
        """Signal that the agent has finished, then enqueue the sentinel."""
        await self._queue.put({
            "event": "task_complete",
            "response": response,
            "status": "idle",
        })
        await self._queue.put(None)

    async def emit_error(self, message: str) -> None:
        """Emit an error event."""
        await self._queue.put({
            "event": "error",
            "message": message,
        })

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
