"""GENESIS FastAPI application entrypoint."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.streaming import AgentEventEmitter, send_events
from backend.config import settings, setup_logging
from backend.db.database import init_db
from backend.db.models import HealthResponse
from backend.skills import create_skill_system

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    await setup_logging()

    # Ensure required directories exist
    Path("data").mkdir(exist_ok=True)
    Path("generated_skills").mkdir(exist_ok=True)

    await init_db()

    # Initialize skill registry and skill tree
    registry, skill_tree = await create_skill_system()
    app.state.skill_registry = registry
    app.state.skill_tree = skill_tree
    core_count = sum(1 for s in registry.skills.values() if s.is_core)
    gen_count = len(registry.skills) - core_count
    logger.info(
        "Skill system ready: %d skills (%d core, %d generated)",
        len(registry.skills), core_count, gen_count,
    )

    # Clean up stale test files from previous runs
    for stale in Path("generated_skills").glob("_test_*.py"):
        try:
            stale.unlink()
            logger.info("Removed stale test file: %s", stale)
        except OSError as exc:
            logger.warning("Failed to remove stale test file %s: %s", stale, exc)

    # Check if agent graph is available yet (Session 2)
    try:
        from backend.agent.graph import run_agent  # noqa: F401

        logger.info("Agent graph loaded")
    except ImportError:
        logger.warning("Agent graph not yet implemented — WebSocket will return placeholder events")

    logger.info("GENESIS server ready on %s:%s", settings.HOST, settings.PORT)
    yield
    logger.info("GENESIS server shutting down")


app = FastAPI(title="GENESIS", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming agent execution events.

    Accepts JSON messages of the form ``{"task": "..."}``.
    Each task spawns an agent run (or a placeholder if the agent graph
    hasn't been implemented yet) and streams events back.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue

            task = data.get("task", "").strip()
            if not task:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "No task provided"})
                )
                continue

            emitter = AgentEventEmitter()

            # Try to import the real agent graph (Session 2)
            try:
                from backend.agent.graph import run_agent

                agent_coro = run_agent(task, emitter)
            except ImportError:

                async def _placeholder(t: str, em: AgentEventEmitter) -> None:
                    await em.emit_status(f"Received task: {t}", status="planning")
                    await em.emit_status(
                        "Agent graph not yet implemented — this is a placeholder response.",
                        status="executing",
                    )
                    await em.emit_complete(
                        "Infrastructure is working. Agent coming in Session 2."
                    )

                agent_coro = _placeholder(task, emitter)

            # Run agent + event sender concurrently
            sender_task = asyncio.create_task(send_events(websocket, emitter))
            agent_task = asyncio.create_task(agent_coro)

            try:
                await asyncio.gather(agent_task, sender_task)
            except Exception:
                logger.exception("Error during agent execution")
                await emitter.close()
                await sender_task

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
