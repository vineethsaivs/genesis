---
name: genesis-backend
description: Use when working on GENESIS Python backend (FastAPI, LangGraph, MCP tools, skill registry)
---

## FastMCP Tool Pattern
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("tool_name")

@mcp.tool()
async def my_tool(param: str) -> dict:
    """Description"""
    return {"result": "..."}
```

## LangGraph Node Pattern
Every node function: async, takes AgentState, returns partial dict update.
Always append to agent_events for WebSocket streaming.

## Serper API
POST https://google.serper.dev/search
Header: X-API-KEY: {key}
Body: {"q": "query", "num": 5}

## WebSocket Event Format
{"event": "agent_status", "status": "...", "message": "..."}
{"event": "code_stream", "chunk": "...", "skill_name": "..."}
{"event": "skill_tree_update", "action": "add_node", "node": {...}, "edge": {...}}