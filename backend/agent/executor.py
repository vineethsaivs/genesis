"""Executor node — dispatches the current plan step to the skill registry."""

import logging
from datetime import datetime, timezone
from typing import Any

try:
    from backend.agent.state import AgentState
except ImportError:
    AgentState = dict  # type: ignore[assignment,misc]

try:
    from backend.skills import get_registry
except ImportError:
    get_registry = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

CORE_TOOL_NAMES: set[str] = {
    "web_search",
    "browser",
    "file_io",
    "calculator",
    "text_analysis",
}

MAX_EVOLUTION_RETRIES: int = 2


async def _execute_skill(tool_name: str, tool_params: dict) -> dict[str, Any]:
    """Execute a skill through the registry.

    Args:
        tool_name: Name of the skill/tool to execute.
        tool_params: Parameters to pass to the skill.

    Returns:
        A dict with 'success', 'result', and optionally 'error' keys.
    """
    if get_registry is None:
        return {
            "success": False,
            "result": None,
            "error": "Skill registry not available",
        }

    try:
        registry = get_registry()
        result = await registry.execute_skill(tool_name, **tool_params)
        return {
            "success": True,
            "result": result,
            "error": None,
        }
    except Exception as exc:
        logger.error("Skill execution failed for '%s': %s", tool_name, exc)
        return {
            "success": False,
            "result": None,
            "error": str(exc),
        }


async def executor_node(state: dict) -> dict:
    """LangGraph node that executes the current plan step.

    Dispatches to the skill registry, or triggers evolution if the required
    tool is missing or execution fails.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with tool_results, status, and possibly evolution_context.
    """
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    tool_results = list(state.get("tool_results", []))
    agent_events = list(state.get("agent_events", []))
    available_skills = state.get("available_skills", [])
    task = state.get("task", "")

    # Guard: no plan or all steps already done
    if not plan or current_step >= len(plan):
        logger.info("No more steps to execute, moving to responding")
        agent_events.append({
            "event": "agent_status",
            "status": "execution_complete",
            "message": "All plan steps completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "responding",
            "tool_results": tool_results,
            "agent_events": agent_events,
        }

    step = plan[current_step]
    tool_name = step.get("tool", "")
    tool_params = step.get("tool_params", {})
    needs_new_tool = step.get("needs_new_tool", False)
    action = step.get("action", "Execute step")

    logger.info(
        "Executing step %d/%d: %s (tool=%s)",
        current_step + 1,
        len(plan),
        action,
        tool_name,
    )

    agent_events.append({
        "event": "agent_status",
        "status": "executing_step",
        "message": f"Step {current_step + 1}/{len(plan)}: {action}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Track per-step evolution attempts to prevent infinite loops
    evolution_attempts = step.get("evolution_attempts", 0)

    # Case: step explicitly requires a new tool
    if needs_new_tool:
        if evolution_attempts >= MAX_EVOLUTION_RETRIES:
            logger.warning(
                "Step %d exceeded max evolution retries (%d), skipping",
                current_step + 1,
                MAX_EVOLUTION_RETRIES,
            )
            agent_events.append({
                "event": "agent_status",
                "status": "step_skipped",
                "message": (
                    f"Step {current_step + 1} skipped after "
                    f"{evolution_attempts} failed evolution attempts"
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            tool_results.append({
                "step": current_step + 1,
                "tool": tool_name,
                "result": None,
                "success": False,
                "error": f"Skipped: exceeded {MAX_EVOLUTION_RETRIES} evolution retries",
            })
            new_step = current_step + 1
            new_status = "responding" if new_step >= len(plan) else "evaluating"
            return {
                "current_step": new_step,
                "status": new_status,
                "tool_results": tool_results,
                "agent_events": agent_events,
            }

        logger.info("Step %d requires a new tool, triggering evolution", current_step + 1)
        # Increment evolution_attempts on the plan step
        updated_plan = list(plan)
        updated_plan[current_step] = {
            **step,
            "evolution_attempts": evolution_attempts + 1,
        }
        agent_events.append({
            "event": "agent_status",
            "status": "evolution_triggered",
            "message": f"Step {current_step + 1} requires a new tool — triggering evolution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "evaluating",
            "evolution_needed": True,
            "evolution_context": {
                "failed_step": step,
                "error": "No existing tool for this task",
                "task_context": task,
                "suggested_name": None,
                "retry_count": 0,
            },
            "plan": updated_plan,
            "tool_results": tool_results,
            "agent_events": agent_events,
        }

    # Case: tool not found in available skills or core tools
    if tool_name not in available_skills and tool_name not in CORE_TOOL_NAMES:
        if evolution_attempts >= MAX_EVOLUTION_RETRIES:
            logger.warning(
                "Step %d exceeded max evolution retries (%d), skipping",
                current_step + 1,
                MAX_EVOLUTION_RETRIES,
            )
            agent_events.append({
                "event": "agent_status",
                "status": "step_skipped",
                "message": (
                    f"Step {current_step + 1} skipped: tool '{tool_name}' not found "
                    f"after {evolution_attempts} evolution attempts"
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            tool_results.append({
                "step": current_step + 1,
                "tool": tool_name,
                "result": None,
                "success": False,
                "error": f"Skipped: tool '{tool_name}' not found after {MAX_EVOLUTION_RETRIES} evolution retries",
            })
            new_step = current_step + 1
            new_status = "responding" if new_step >= len(plan) else "evaluating"
            return {
                "current_step": new_step,
                "status": new_status,
                "tool_results": tool_results,
                "agent_events": agent_events,
            }

        logger.warning(
            "Tool '%s' not found in available skills or core tools", tool_name
        )
        updated_plan = list(plan)
        updated_plan[current_step] = {
            **step,
            "evolution_attempts": evolution_attempts + 1,
        }
        agent_events.append({
            "event": "agent_status",
            "status": "evolution_triggered",
            "message": f"Tool '{tool_name}' not found — triggering evolution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "evaluating",
            "evolution_needed": True,
            "evolution_context": {
                "failed_step": step,
                "error": f"Tool '{tool_name}' not found in available skills",
                "task_context": task,
                "suggested_name": None,
                "retry_count": 0,
            },
            "plan": updated_plan,
            "tool_results": tool_results,
            "agent_events": agent_events,
        }

    # Case: tool exists — execute it
    result = await _execute_skill(tool_name, tool_params)

    if result["success"]:
        logger.info("Step %d executed successfully", current_step + 1)
        tool_results.append({
            "step": current_step + 1,
            "tool": tool_name,
            "result": result["result"],
            "success": True,
        })

        new_step = current_step + 1
        new_status = "responding" if new_step >= len(plan) else "evaluating"

        agent_events.append({
            "event": "agent_status",
            "status": "step_complete",
            "message": f"Step {current_step + 1} completed successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "current_step": new_step,
            "status": new_status,
            "tool_results": tool_results,
            "agent_events": agent_events,
        }

    # Execution failed — trigger evolution (with retry limit)
    logger.warning(
        "Step %d failed: %s", current_step + 1, result["error"]
    )

    tool_results.append({
        "step": current_step + 1,
        "tool": tool_name,
        "result": None,
        "success": False,
        "error": result["error"],
    })

    if evolution_attempts >= MAX_EVOLUTION_RETRIES:
        logger.warning(
            "Step %d exceeded max evolution retries (%d), skipping",
            current_step + 1,
            MAX_EVOLUTION_RETRIES,
        )
        agent_events.append({
            "event": "agent_status",
            "status": "step_skipped",
            "message": (
                f"Step {current_step + 1} skipped: execution failed "
                f"after {evolution_attempts} evolution attempts"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        new_step = current_step + 1
        new_status = "responding" if new_step >= len(plan) else "evaluating"
        return {
            "current_step": new_step,
            "status": new_status,
            "tool_results": tool_results,
            "agent_events": agent_events,
        }

    updated_plan = list(plan)
    updated_plan[current_step] = {
        **step,
        "evolution_attempts": evolution_attempts + 1,
    }

    agent_events.append({
        "event": "agent_status",
        "status": "evolution_triggered",
        "message": f"Step {current_step + 1} failed: {result['error']} — triggering evolution",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "status": "evaluating",
        "evolution_needed": True,
        "evolution_context": {
            "failed_step": step,
            "error": result["error"],
            "task_context": task,
            "suggested_name": None,
            "retry_count": 0,
        },
        "plan": updated_plan,
        "tool_results": tool_results,
        "agent_events": agent_events,
    }
