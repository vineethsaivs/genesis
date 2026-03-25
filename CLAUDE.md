# GENESIS - Self-Evolving AI Agent

## Project
A self-evolving AI agent that writes its own MCP tools and visualizes evolution via a live skill tree.

## Tech Stack
- Backend: Python 3.11+, FastAPI, LangGraph, FastMCP 3.x, browser-use, httpx
- Frontend: React + Vite + TypeScript, Tailwind CSS v4, react-force-graph-2d
- DB: SQLite via aiosqlite
- Search: Serper API (REST, no SDK)
- Package manager: uv (Python), npm (JS)

## Architecture
- backend/agent/ — LangGraph nodes (planner, executor, evaluator, evolver, sandbox, registrar)
- backend/skills/ — Skill registry, skill tree, core tools
- backend/api/ — FastAPI routes + WebSocket streaming
- backend/db/ — SQLite persistence
- frontend/src/ — React dashboard with skill tree viz

## Code Rules
- ALL Python functions must be async
- Full type hints on every function
- Docstrings on all public functions
- Use httpx (not requests) for HTTP calls
- Use Pydantic models for API schemas
- Never use print() — use logging module
- Snake_case for Python, camelCase for TypeScript
- Imports: stdlib → third-party → local (blank line between each)

## Testing
- pytest with pytest-asyncio
- Run: uv run pytest tests/ -v

## Common Commands
- Dev server: uv run uvicorn backend.main:app --reload --port 8000
- Frontend: cd frontend && npm run dev
- Install: uv sync

## IMPORTANT
- Generated skills go in generated_skills/ directory
- Core tools are in backend/skills/core_tools/
- Serper API: POST https://google.serper.dev/search with X-API-KEY header
- browser-use requires OpenAI API key specifically
- The WebSocket at /ws/agent streams JSON events to the React frontend
- Skill tree data format must match react-force-graph-2d: {nodes: [...], links: [...]}