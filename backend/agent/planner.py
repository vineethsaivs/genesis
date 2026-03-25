"""Planner node — decomposes a user task into 2-6 executable steps via LLM."""

import json
import logging
import re
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
    from backend.skills.registry import SkillRegistry
except ImportError:
    SkillRegistry = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

CORE_TOOLS_FALLBACK: list[dict[str, str]] = [
    {"name": "web_search", "description": "Search the web for information using Serper API"},
    {"name": "browser", "description": "Browse a webpage and extract its content"},
    {"name": "file_io", "description": "Read and write files on the local filesystem"},
    {"name": "calculator", "description": "Perform mathematical calculations"},
    {"name": "text_analysis", "description": "Analyze, summarize, or transform text content"},
]

PLANNER_SYSTEM_PROMPT = """You are a task planner for a SELF-EVOLVING AI agent. Given a user task, decompose it into 2-6 concrete, executable steps.

Available tools:
{tools}

STRICT TOOL MATCHING RULES — follow these exactly:
- web_search: ONLY returns Google search result snippets (title, URL, snippet text). It CANNOT fetch full page content, call APIs, or return structured data.
- browser: Fetches a single webpage's text content. CANNOT reliably extract specific structured data like tables, prices, scores, or stats from complex pages.
- calculator: Evaluates simple math expressions like '2+2' or 'sqrt(144)'. CANNOT fetch data, call APIs, or process text.
- text_analysis: Counts words and does basic keyword extraction. CANNOT summarize intelligently or analyze data.
- file_io: Reads and writes local files. CANNOT access the internet.

If a task step requires ANY of the following, you MUST set needs_new_tool to true:
- Calling a specific third-party API (weather, crypto, stocks, exchange rates, etc.)
- Scraping structured data from a specific website (HN scores, GitHub stars, product prices from a specific store)
- Any data processing that requires parsing HTML tables, JSON APIs, or specific page structures
- Anything the 5 tools above cannot RELIABLY do

Be aggressive about marking needs_new_tool=true. The whole point of this system is to create new tools. When in doubt, mark it as needing a new tool.

Output ONLY a JSON array of steps. Each step must have these fields:
- "step": integer step number starting at 1
- "action": string describing what this step does
- "tool": string name of the tool to use (use a descriptive name for the tool that SHOULD be created when needs_new_tool is true)
- "needs_new_tool": boolean, true if no existing tool can RELIABLY accomplish this
- "tool_params": object with parameters to pass to the tool

Example output:
[
  {{"step": 1, "action": "Fetch current Bitcoin price from crypto API", "tool": "crypto_price_fetcher", "needs_new_tool": true, "tool_params": {{"coin": "bitcoin", "currency": "usd"}}}},
  {{"step": 2, "action": "Format the price data for display", "tool": "text_analysis", "needs_new_tool": false, "tool_params": {{"text": "{{step_1_result}}", "operation": "summarize"}}}}
]

Rules:
- Keep plans focused: 2-6 steps maximum
- Each step should be independently executable
- Output valid JSON only, no extra text"""


def _get_llm(temperature: float = 0.0) -> Any:
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


def _parse_json_from_text(text: str) -> list[dict] | dict | None:
    """Extract JSON from LLM text that may contain markdown fences or preamble.

    Args:
        text: Raw LLM output text.

    Returns:
        Parsed JSON as a list or dict, or None on failure.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON array
    array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group())
        except json.JSONDecodeError:
            pass

    # Try extracting JSON object
    obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    return None


async def _get_available_tools() -> list[dict[str, str]]:
    """Fetch available tools from SkillRegistry, falling back to core tools.

    Returns:
        A list of tool descriptors with 'name' and 'description' keys.
    """
    if SkillRegistry is not None:
        try:
            registry = SkillRegistry()
            skills = await registry.list_skills()
            if skills:
                return skills
        except Exception as exc:
            logger.warning("Failed to list skills from registry: %s", exc)

    return CORE_TOOLS_FALLBACK


def _validate_step(step: dict, step_index: int) -> dict:
    """Validate and normalize a single plan step.

    Args:
        step: Raw step dict from LLM output.
        step_index: 1-based step number to assign if missing.

    Returns:
        Normalized step dict with all required fields.
    """
    return {
        "step": step.get("step", step_index),
        "action": step.get("action", "Execute step"),
        "tool": step.get("tool", "web_search"),
        "needs_new_tool": bool(step.get("needs_new_tool", False)),
        "tool_params": step.get("tool_params", {}),
    }


async def planner_node(state: dict) -> dict:
    """LangGraph node that decomposes a user task into an executable plan.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with plan, current_step, status, and agent_events.
    """
    task = state.get("task", "")
    agent_events = list(state.get("agent_events", []))

    try:
        tools = await _get_available_tools()
        tool_descriptions = "\n".join(
            f"- {t['name']}: {t['description']}" for t in tools
        )

        llm = _get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(tools=tool_descriptions)),
            HumanMessage(content=f"Task: {task}"),
        ]

        response = await llm.ainvoke(messages)
        raw_text = response.content if hasattr(response, "content") else str(response)
        parsed = _parse_json_from_text(raw_text)

        # Validate parsed output
        if isinstance(parsed, list) and len(parsed) > 0:
            plan = [_validate_step(s, i + 1) for i, s in enumerate(parsed[:6])]
        elif isinstance(parsed, dict):
            plan = [_validate_step(parsed, 1)]
        else:
            logger.warning("Failed to parse plan from LLM output, using fallback")
            plan = [
                {
                    "step": 1,
                    "action": f"Search for information about: {task}",
                    "tool": "web_search",
                    "needs_new_tool": False,
                    "tool_params": {"query": task},
                }
            ]

        skill_names = [t["name"] for t in tools]

        agent_events.append({
            "event": "agent_status",
            "status": "planning_complete",
            "message": f"Created plan with {len(plan)} steps",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("Created plan with %d steps for task: %s", len(plan), task[:100])

        return {
            "plan": plan,
            "current_step": 0,
            "status": "executing",
            "evolution_needed": False,
            "agent_events": agent_events,
            "available_skills": skill_names,
        }

    except Exception as exc:
        logger.error("Planner failed: %s", exc, exc_info=True)

        fallback_plan = [
            {
                "step": 1,
                "action": f"Search for information about: {task}",
                "tool": "web_search",
                "needs_new_tool": False,
                "tool_params": {"query": task},
            }
        ]

        agent_events.append({
            "event": "agent_status",
            "status": "planning_fallback",
            "message": f"Planning failed ({exc}), using fallback web search plan",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "plan": fallback_plan,
            "current_step": 0,
            "status": "executing",
            "evolution_needed": False,
            "agent_events": agent_events,
            "available_skills": [t["name"] for t in CORE_TOOLS_FALLBACK],
        }
