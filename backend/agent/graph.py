"""Graph assembly — compiles the full LangGraph StateGraph and exports run_agent()."""

import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

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
    from backend.agent.planner import planner_node
except ImportError:
    planner_node = None  # type: ignore[assignment]

try:
    from backend.agent.executor import executor_node
except ImportError:
    executor_node = None  # type: ignore[assignment]

try:
    from backend.agent.evaluator import evaluator_node
except ImportError:
    evaluator_node = None  # type: ignore[assignment]

try:
    from backend.agent.evolver import evolver_node
except ImportError:
    evolver_node = None  # type: ignore[assignment]

try:
    from backend.agent.sandbox import sandbox_node
except ImportError:
    sandbox_node = None  # type: ignore[assignment]

try:
    from backend.agent.registrar import registrar_node
except ImportError:
    registrar_node = None  # type: ignore[assignment]

try:
    from backend.api.streaming import AgentEventEmitter
except ImportError:
    AgentEventEmitter = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

RESPONDER_SYSTEM_PROMPT = """You are GENESIS, a self-evolving AI agent. Synthesize the tool results below into a clear, helpful response for the user.

Be concise and direct. If results contain errors, acknowledge them and explain what was attempted.
If the task required evolving new tools, mention that capability briefly."""


def _get_llm(temperature: float = 0.3) -> Any:
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


async def responder_node(state: dict) -> dict:
    """LangGraph node that synthesizes tool results into a final user response.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with final_response, status='complete', and agent_events.
    """
    task = state.get("task", "")
    tool_results = state.get("tool_results", [])
    agent_events = list(state.get("agent_events", []))

    # Build a text summary of tool results
    results_text = ""
    for tr in tool_results:
        step = tr.get("step", "?")
        tool = tr.get("tool", "unknown")
        success = tr.get("success", False)
        result = tr.get("result", "")
        error = tr.get("error", "")
        if success:
            result_str = str(result)[:1000] if result else "No output"
            results_text += f"Step {step} ({tool}): SUCCESS\n{result_str}\n\n"
        else:
            results_text += f"Step {step} ({tool}): FAILED - {error}\n\n"

    if not results_text:
        results_text = "No tool results available."

    try:
        llm = _get_llm(temperature=0.3)
        messages = [
            SystemMessage(content=RESPONDER_SYSTEM_PROMPT),
            HumanMessage(content=f"Task: {task}\n\nTool Results:\n{results_text}"),
        ]

        response = await llm.ainvoke(messages)
        final_response = response.content if hasattr(response, "content") else str(response)

    except Exception as exc:
        logger.warning("Responder LLM call failed, using plain text fallback: %s", exc)

        # Fallback: plain text summary
        lines = [f"Results for task: {task}\n"]
        for tr in tool_results:
            step = tr.get("step", "?")
            tool = tr.get("tool", "unknown")
            success = tr.get("success", False)
            if success:
                result = str(tr.get("result", ""))[:500]
                lines.append(f"Step {step} ({tool}): {result}")
            else:
                lines.append(f"Step {step} ({tool}): Failed - {tr.get('error', 'unknown')}")
        final_response = "\n".join(lines)

    agent_events.append({
        "event": "agent_status",
        "status": "complete",
        "message": "Response generated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "final_response": final_response,
        "status": "complete",
        "agent_events": agent_events,
    }


_MAX_EVOLUTIONS_SAFETY = 3


def _evolution_count(state: dict) -> int:
    """Count skill_tree_update events as a proxy for completed evolutions."""
    return sum(
        1 for e in state.get("agent_events", [])
        if e.get("event") == "skill_tree_update"
    )


def route_after_evaluation(state: dict) -> str:
    """Route after evaluator based on status.

    Args:
        state: The current agent state dictionary.

    Returns:
        Next node name: 'evolver', 'executor', or 'responder'.
    """
    if _evolution_count(state) >= _MAX_EVOLUTIONS_SAFETY:
        logger.warning("Evolution safety limit reached (%d), forcing responder", _MAX_EVOLUTIONS_SAFETY)
        return "responder"
    status = state.get("status", "")
    if status == "evolving":
        return "evolver"
    if status == "executing":
        return "executor"
    return "responder"


def route_after_testing(state: dict) -> str:
    """Route after sandbox testing based on status.

    Args:
        state: The current agent state dictionary.

    Returns:
        Next node name: 'registrar', 'evolver', or 'responder'.
    """
    if _evolution_count(state) >= _MAX_EVOLUTIONS_SAFETY:
        logger.warning("Evolution safety limit reached (%d), forcing responder", _MAX_EVOLUTIONS_SAFETY)
        return "responder"
    status = state.get("status", "")
    if status == "registering":
        return "registrar"
    if status == "evolving":
        return "evolver"
    return "responder"


def build_genesis_graph() -> Any:
    """Assemble and compile the full GENESIS LangGraph state graph.

    Returns:
        A compiled LangGraph graph ready for execution.

    Raises:
        RuntimeError: If required node functions are not available.
    """
    missing = []
    for name, fn in [
        ("planner", planner_node),
        ("executor", executor_node),
        ("evaluator", evaluator_node),
        ("evolver", evolver_node),
        ("sandbox", sandbox_node),
        ("registrar", registrar_node),
    ]:
        if fn is None:
            missing.append(name)

    if missing:
        raise RuntimeError(f"Missing node functions: {', '.join(missing)}")

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("evolver", evolver_node)
    workflow.add_node("sandbox", sandbox_node)
    workflow.add_node("registrar", registrar_node)
    workflow.add_node("responder", responder_node)

    # Set entry point
    workflow.set_entry_point("planner")

    # Fixed edges
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "evaluator")
    workflow.add_edge("evolver", "sandbox")
    workflow.add_edge("registrar", "executor")
    workflow.add_edge("responder", END)

    # Conditional edges
    workflow.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {"evolver": "evolver", "executor": "executor", "responder": "responder"},
    )
    workflow.add_conditional_edges(
        "sandbox",
        route_after_testing,
        {"registrar": "registrar", "evolver": "evolver", "responder": "responder"},
    )

    compiled = workflow.compile()
    logger.info("GENESIS graph compiled with 7 nodes")
    return compiled


# Build graph at module level
graph = build_genesis_graph()


async def run_agent(task: str, emitter: Any) -> None:
    """Execute the GENESIS agent graph and stream events to the emitter.

    This is the bridge between LangGraph execution and WebSocket streaming.
    It tracks which events have already been forwarded to avoid duplicates.

    Args:
        task: The user's task description.
        emitter: An AgentEventEmitter instance for streaming events.
    """
    try:
        await emitter.emit_status(f"Starting task: {task}", status="starting")

        # Build initial state
        initial_state: dict[str, Any] = {
            "task": task,
            "plan": [],
            "current_step": 0,
            "tool_results": [],
            "available_skills": [],
            "evolution_needed": False,
            "evolution_context": {},
            "new_skill_code": "",
            "new_skill_metadata": {},
            "test_results": {},
            "skill_tree_update": {},
            "agent_events": [],
            "final_response": "",
            "status": "planning",
        }

        events_forwarded = 0
        final_response = ""

        async for step_output in graph.astream(initial_state):
            # step_output is a dict of {node_name: state_update}
            for node_name, state_update in step_output.items():
                logger.debug("Graph step from node: %s", node_name)

                # Track final response
                if "final_response" in state_update and state_update["final_response"]:
                    final_response = state_update["final_response"]

                # Forward new events only
                agent_events = state_update.get("agent_events", [])
                new_events = agent_events[events_forwarded:]
                events_forwarded = len(agent_events)

                for event in new_events:
                    event_type = event.get("event", "")

                    if event_type == "code_stream":
                        await emitter.emit_code_chunk(event.get("chunk", ""))
                    elif event_type == "test_result":
                        await emitter.emit_test_result(
                            passed=event.get("passed", False),
                            detail=event.get("details", ""),
                        )
                    elif event_type == "skill_tree_update":
                        await emitter.emit_skill_tree_update(
                            event.get("data", {}),
                        )
                    elif event_type == "evolution_start":
                        await emitter.emit_evolution_start(
                            skill_name=event.get("tool_name", "unknown"),
                            trigger_task=task,
                        )
                    else:
                        # Default: emit as status
                        await emitter.emit_status(
                            event.get("message", ""),
                            status=event.get("status", "running"),
                        )

        await emitter.emit_complete(final_response or "Task complete")

    except Exception as exc:
        logger.error("Agent execution failed: %s", exc, exc_info=True)
        await emitter.emit_status(f"Error: {exc}", status="error")
        await emitter.emit_complete("Task failed due to an error")


__all__ = ["graph", "build_genesis_graph", "run_agent"]
