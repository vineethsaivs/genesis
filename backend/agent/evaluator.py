"""Evaluator node — routes the agent to continue executing, evolve, or respond."""

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

logger = logging.getLogger(__name__)

MAX_EVOLUTIONS_PER_RUN: int = 3

TOOL_SUGGESTION_PROMPT = """You are helping an AI agent that needs a new tool to complete a task.

The agent tried to use a tool but it failed or doesn't exist. Based on the context below, suggest a name and category for a new tool that should be created.

Task: {task}
Failed step: {step_action}
Tool that was attempted: {tool_name}
Error: {error}

Respond with ONLY a JSON object:
{{"name": "descriptive_snake_case_tool_name", "category": "web|browser|data|api|file|analysis"}}

Rules:
- name should be descriptive and use snake_case
- category must be one of: web, browser, data, api, file, analysis
- Keep the name concise but clear about what the tool does"""


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


def _parse_json_object(text: str) -> dict | None:
    """Extract the first JSON object from text.

    Args:
        text: Raw text that may contain a JSON object.

    Returns:
        Parsed dict or None on failure.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Try regex extraction
    obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if obj_match:
        try:
            result = json.loads(obj_match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


async def evaluator_node(state: dict) -> dict:
    """LangGraph node that decides the next routing action.

    Routes to one of three states:
    - "evolving": evolution is needed, enriches context with tool suggestion
    - "responding": all steps are done, generate final response
    - "executing": more steps remain, continue execution

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with status and possibly enriched evolution_context.
    """
    status = state.get("status", "")
    evolution_needed = state.get("evolution_needed", False)
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    agent_events = list(state.get("agent_events", []))
    task = state.get("task", "")

    # Hard gate: if executor already decided we're done, pass through immediately.
    if status == "responding":
        logger.info("Evaluator: status is 'responding', passing through to responder")
        return {
            "status": "responding",
            "agent_events": agent_events,
        }

    # Global safety limit: if we've already registered 3+ skills this run, stop evolving.
    evolution_count = sum(
        1 for ev in agent_events if ev.get("event") == "skill_tree_update"
    )
    if evolution_count >= MAX_EVOLUTIONS_PER_RUN:
        logger.warning(
            "Global evolution limit reached (%d/%d), forcing responding",
            evolution_count,
            MAX_EVOLUTIONS_PER_RUN,
        )
        agent_events.append({
            "event": "agent_status",
            "status": "responding",
            "message": (
                f"Evolution limit reached ({evolution_count} tools created) "
                f"— generating final response with available results"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "responding",
            "evolution_needed": False,
            "agent_events": agent_events,
        }

    # Case 0: Check if the CURRENT step's result indicates a subtle failure
    # (marked success but returned empty/None/useless data).
    # Only inspect the result for current_step, never re-check old steps.
    if not evolution_needed:
        tool_results = state.get("tool_results", [])
        current_step_result = None
        for tr in tool_results:
            if tr.get("step") == current_step:
                current_step_result = tr
        # If current_step has already advanced past plan length, there's nothing to check
        if current_step_result is not None and current_step < len(plan):
            result_data = current_step_result.get("result")
            result_success = current_step_result.get("success", True)

            # Detect explicit failure
            is_failed = not result_success

            # Detect empty/None results that were marked as "success"
            is_empty = (
                result_data is None
                or result_data == ""
                or result_data == []
                or result_data == {}
            )

            # Detect dict results with success=False inside the result payload
            is_result_failure = (
                isinstance(result_data, dict)
                and result_data.get("success") is False
            )

            if is_failed or is_empty or is_result_failure:
                failed_step = (
                    plan[current_step]
                    if current_step < len(plan)
                    else {"action": "unknown", "tool": "unknown"}
                )
                error_msg = current_step_result.get("error", "")
                if is_empty:
                    error_msg = (
                        f"Tool '{current_step_result.get('tool', 'unknown')}' returned "
                        f"empty/None result — it cannot fulfill this task"
                    )
                elif is_result_failure:
                    error_msg = (
                        f"Tool '{current_step_result.get('tool', 'unknown')}' reported "
                        f"failure in result payload: {result_data.get('error', 'unknown')}"
                    )

                logger.info(
                    "Evaluator detected poor result quality for step %d: %s",
                    current_step + 1,
                    error_msg,
                )
                evolution_needed = True
                state = {**state, "evolution_needed": True, "evolution_context": {
                    "failed_step": failed_step,
                    "error": error_msg,
                    "task_context": task,
                    "suggested_name": None,
                    "retry_count": 0,
                }}

    # Case 1: Evolution needed — enrich context and route to evolver
    if evolution_needed:
        evolution_context = dict(state.get("evolution_context", {}))
        logger.info("Evolution needed: %s", evolution_context.get("error", "unknown"))

        # Suggest a tool name/category if not already present
        if not evolution_context.get("suggested_name"):
            suggested_name, suggested_category = await _suggest_tool(
                task=task,
                evolution_context=evolution_context,
            )
            evolution_context["suggested_name"] = suggested_name
            evolution_context["suggested_category"] = suggested_category

        agent_events.append({
            "event": "agent_status",
            "status": "evolving",
            "message": (
                f"Evolving: creating tool '{evolution_context.get('suggested_name', 'unknown')}' "
                f"(category: {evolution_context.get('suggested_category', 'general')})"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        agent_events.append({
            "event": "evolution_start",
            "tool_name": evolution_context.get("suggested_name", "unknown"),
            "category": evolution_context.get("suggested_category", "general"),
            "error": evolution_context.get("error", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Routing to evolver: tool=%s, category=%s",
            evolution_context.get("suggested_name"),
            evolution_context.get("suggested_category"),
        )

        return {
            "status": "evolving",
            "evolution_needed": True,
            "evolution_context": evolution_context,
            "agent_events": agent_events,
        }

    # Case 2: All steps done — route to responder
    if current_step >= len(plan):
        logger.info("All plan steps completed, routing to responder")
        agent_events.append({
            "event": "agent_status",
            "status": "responding",
            "message": "All steps completed — generating final response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "responding",
            "agent_events": agent_events,
        }

    # Case 3: More steps remain — continue execution
    logger.info(
        "Continuing execution: step %d/%d",
        current_step + 1,
        len(plan),
    )
    return {
        "status": "executing",
        "agent_events": agent_events,
    }


async def _suggest_tool(
    task: str,
    evolution_context: dict,
) -> tuple[str, str]:
    """Use LLM to suggest a tool name and category for evolution.

    Args:
        task: The original user task.
        evolution_context: Context about the failed step.

    Returns:
        A tuple of (suggested_name, suggested_category).
    """
    failed_step = evolution_context.get("failed_step", {})
    step_action = failed_step.get("action", "unknown action")
    tool_name = failed_step.get("tool", "unknown_tool")
    error = evolution_context.get("error", "unknown error")

    try:
        llm = _get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=TOOL_SUGGESTION_PROMPT.format(
                task=task,
                step_action=step_action,
                tool_name=tool_name,
                error=error,
            )),
            HumanMessage(content="Suggest a tool name and category."),
        ]

        response = await llm.ainvoke(messages)
        raw_text = response.content if hasattr(response, "content") else str(response)
        parsed = _parse_json_object(raw_text)

        if parsed and "name" in parsed:
            valid_categories = {"web", "browser", "data", "api", "file", "analysis"}
            category = parsed.get("category", "general")
            if category not in valid_categories:
                category = "general"
            return parsed["name"], category

    except Exception as exc:
        logger.warning("LLM tool suggestion failed: %s", exc)

    # Fallback: use the tool name from the failed step
    fallback_name = tool_name if tool_name != "unknown_tool" else "generic_tool"
    logger.info("Using fallback tool suggestion: %s", fallback_name)
    return fallback_name, "general"
