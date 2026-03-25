"""Evolver node — generates new MCP tool code via LLM and streams it line-by-line."""

import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None  # type: ignore[assignment,misc]

try:
    from backend.agent.state import AgentState
except ImportError:
    AgentState = dict  # type: ignore[assignment,misc]

try:
    from backend.config import DEFAULT_LLM_PROVIDER, DEFAULT_MODEL
except ImportError:
    DEFAULT_LLM_PROVIDER = "openai"
    DEFAULT_MODEL = "gpt-4o-mini"

try:
    from backend.skills.templates import CATEGORY_IMPORTS, TOOL_GENERATION_SYSTEM_PROMPT
except ImportError:
    TOOL_GENERATION_SYSTEM_PROMPT = (
        "Generate a Python MCP tool module. "
        "CRITICAL: The import MUST be 'from mcp.server.fastmcp import FastMCP'. "
        "NEVER use 'from fastmcp import register_tool' or 'from fastmcp import FastMCP' — those do NOT work. "
        "Use httpx for HTTP, async functions, type hints, docstrings, "
        "and include test_ functions. Export SKILL_ID, SKILL_NAME, SKILL_DESCRIPTION, SKILL_CATEGORY."
    )
    CATEGORY_IMPORTS = {}

logger = logging.getLogger(__name__)

CATEGORY_PARENT_MAP: dict[str, str] = {
    "web": "web_search",
    "browser": "browser_tool",
    "data": "text_analysis",
    "api": "web_search",
    "file": "file_io",
    "analysis": "text_analysis",
}


def _get_llm(temperature: float = 0.7) -> Any:
    """Instantiate an LLM client with cascading provider fallback.

    Args:
        temperature: Sampling temperature for the LLM.

    Returns:
        A LangChain chat model instance.

    Raises:
        RuntimeError: If no LLM provider is available.
    """
    providers: list[tuple[str, Any, str]] = []

    if DEFAULT_LLM_PROVIDER == "openai" and ChatOpenAI is not None:
        providers.append(("openai", ChatOpenAI, DEFAULT_MODEL))
    if DEFAULT_LLM_PROVIDER == "anthropic" and ChatAnthropic is not None:
        providers.append(("anthropic", ChatAnthropic, DEFAULT_MODEL))

    # Fallback chain regardless of configured provider
    if ChatOpenAI is not None and not any(p[0] == "openai" for p in providers):
        providers.append(("openai", ChatOpenAI, "gpt-4o-mini"))
    if ChatAnthropic is not None and not any(p[0] == "anthropic" for p in providers):
        providers.append(("anthropic", ChatAnthropic, "claude-sonnet-4-20250514"))

    for name, cls, model in providers:
        try:
            return cls(model=model, temperature=temperature)
        except Exception as exc:
            logger.warning("Failed to instantiate %s LLM: %s", name, exc)

    raise RuntimeError(
        "No LLM provider available. Install langchain-openai or langchain-anthropic "
        "and set the appropriate API key."
    )


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from generated code.

    Args:
        text: Raw LLM output that may contain ```python fences.

    Returns:
        Clean Python code string.
    """
    code = text
    if "```python" in code:
        code = code.split("```python", 1)[1]
    if "```" in code:
        code = code.rsplit("```", 1)[0]
    return code.strip()


def _build_generation_prompt(evolution_context: dict) -> str:
    """Build the user-facing prompt for code generation.

    Args:
        evolution_context: Context about what tool to generate.

    Returns:
        Formatted prompt string.
    """
    name = evolution_context.get("suggested_name", "new_tool")
    category = evolution_context.get("suggested_category", "general")
    task_context = evolution_context.get("task_context", "")
    failed_step = evolution_context.get("failed_step", {})
    last_error = evolution_context.get("last_error", "")

    imports = CATEGORY_IMPORTS.get(category, "")

    prompt = (
        f"Generate a complete Python MCP tool module with the following specifications:\n\n"
        f"Tool name: {name}\n"
        f"Category: {category}\n"
        f"Suggested imports:\n{imports}\n\n"
        f"Task context: {task_context}\n"
        f"Failed step details: {failed_step.get('action', 'N/A')}\n\n"
        f"Requirements:\n"
        f"- Module constants: SKILL_ID = \"{name}\", SKILL_NAME = \"{name}\", "
        f"SKILL_DESCRIPTION, SKILL_CATEGORY = \"{category}\"\n"
        f"- Use FastMCP for tool registration\n"
        f"- All functions must be async\n"
        f"- Include at least 2 test_ functions\n"
        f"- Return dicts with 'success' and 'result' or 'error' keys\n"
        f"- Use httpx for HTTP calls (not requests)\n"
        f"- Use logging instead of print()\n\n"
        f"CRITICAL PARAMETER RULES:\n"
        f"- The @mcp.tool() function MUST accept **kwargs as its last parameter\n"
        f"  Example: async def {name}(query: str = \"\", **kwargs) -> dict:\n"
        f"- Do NOT put @mcp.tool() on test_ functions\n"
        f"- Test functions must use mock/hardcoded data (no real network calls)\n"
    )

    if last_error:
        prompt += (
            f"\nPREVIOUS ATTEMPT FAILED with error: {last_error}\n"
            f"Fix the issue and try again. "
            f"REMINDER: The correct import is 'from mcp.server.fastmcp import FastMCP'. "
            f"NEVER use 'from fastmcp import register_tool' or 'from fastmcp import FastMCP'.\n"
        )

    return prompt


async def evolver_node(state: dict) -> dict:
    """LangGraph node that generates new tool code via LLM.

    Reads evolution_context, calls LLM to generate a complete MCP tool module,
    and streams the generated code line-by-line as events.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with new_skill_code, new_skill_metadata, and agent_events.
    """
    evolution_context = dict(state.get("evolution_context", {}))
    agent_events = list(state.get("agent_events", []))

    suggested_name = evolution_context.get("suggested_name", "new_tool")
    suggested_category = evolution_context.get("suggested_category", "general")
    retry_count = evolution_context.get("retry_count", 0)

    logger.info(
        "Evolver generating tool: %s (category=%s, attempt=%d)",
        suggested_name,
        suggested_category,
        retry_count + 1,
    )

    agent_events.append({
        "event": "agent_status",
        "status": "evolving",
        "message": f"Generating code for tool '{suggested_name}' (attempt {retry_count + 1})",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        llm = _get_llm(temperature=0.7)
        messages = [
            SystemMessage(content=TOOL_GENERATION_SYSTEM_PROMPT),
            HumanMessage(content=_build_generation_prompt(evolution_context)),
        ]

        response = await llm.ainvoke(messages)
        raw_text = response.content if hasattr(response, "content") else str(response)

        generated_code = _strip_code_fences(raw_text)

        # Stream code line-by-line as events
        for line in generated_code.split("\n"):
            agent_events.append({
                "event": "code_stream",
                "chunk": line + "\n",
                "skill_name": suggested_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Determine parent_id from category
        parent_id = CATEGORY_PARENT_MAP.get(suggested_category, "text_analysis")

        new_skill_metadata = {
            "name": suggested_name,
            "description": f"Auto-generated {suggested_category} tool: {suggested_name}",
            "category": suggested_category,
            "parent_id": parent_id,
        }

        logger.info("Evolver generated %d bytes of code for '%s'", len(generated_code), suggested_name)

        return {
            "new_skill_code": generated_code,
            "new_skill_metadata": new_skill_metadata,
            "agent_events": agent_events,
            "status": "testing",
        }

    except Exception as exc:
        logger.error("Evolver failed: %s", exc, exc_info=True)

        agent_events.append({
            "event": "agent_status",
            "status": "error",
            "message": f"Code generation failed: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "agent_events": agent_events,
            "status": "error",
        }
