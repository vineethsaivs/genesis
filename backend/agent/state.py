"""LangGraph state definitions for the GENESIS agent."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class SkillNode(TypedDict, total=False):
    """Represents a single skill in the skill tree."""

    id: str
    name: str
    description: str
    category: str
    parent_id: str | None
    is_core: bool
    code_path: str
    created_at: str
    use_count: int
    status: str


class AgentState(TypedDict, total=False):
    """Top-level state flowing through the LangGraph agent graph."""

    messages: Annotated[list, add_messages]
    task: str
    plan: str
    current_step: str
    tool_results: list[dict[str, Any]]
    available_skills: list[SkillNode]
    evolution_needed: bool
    evolution_context: dict[str, Any]
    new_skill_code: str
    new_skill_metadata: dict[str, Any]
    test_results: dict[str, Any]
    skill_tree_update: dict[str, Any]
    agent_events: list[dict[str, Any]]
    final_response: str
    status: str
