# GENESIS

**A self-evolving AI agent that writes its own tools and visualizes evolution via a live skill tree.**

```
         +-----------+
         |   Task    |
         +-----+-----+
               |
         +-----v-----+
         |  Planner   |
         +-----+-----+
               |
         +-----v-----+     +------------+
         |  Executor  +---->  Evaluator  |
         +-----+-----+     +-----+------+
               |                  |
               |            +-----v------+
               |            |  Evolver   |
               |            +-----+------+
               |                  |
               |            +-----v------+
               |            |  Sandbox   |
               |            +-----+------+
               |                  |
               |            +-----v------+
               |            | Registrar  |
               |            +-----+------+
               |                  |
         +-----v------------------v------+
         |         Skill Tree            |
         +-------------------------------+
```

## Quick Start

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run the server
make dev
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, LangGraph |
| Tools | FastMCP 3.x, browser-use, httpx |
| Frontend | React + Vite + TypeScript, Tailwind CSS v4 |
| Visualization | react-force-graph-2d |
| Database | SQLite via aiosqlite |
| Search | Serper API |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/api/skills` | List all skills |
| GET | `/api/skills/{id}` | Get skill details |
| DELETE | `/api/skills/{id}` | Delete a generated skill |
| GET | `/api/skill-tree` | Skill tree graph data |
| GET | `/api/evolution-history` | Evolution event log |
| POST | `/api/task` | Submit a task |
| WS | `/ws/agent` | Stream agent events |

## Development

```bash
make test     # Run tests
make lint     # Lint check
make format   # Auto-format
make clean    # Remove caches
```

## License

MIT
