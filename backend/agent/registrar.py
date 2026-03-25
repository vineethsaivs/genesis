"""Registrar node — persists new skills to DB, registry, and skill tree."""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from backend.agent.state import AgentState
except ImportError:
    AgentState = dict  # type: ignore[assignment,misc]

try:
    from backend.db.database import save_evolution_history, save_skill
except ImportError:
    save_skill = None  # type: ignore[assignment]
    save_evolution_history = None  # type: ignore[assignment]

try:
    from backend.skills import get_registry, get_skill_tree
except ImportError:
    get_registry = None  # type: ignore[assignment]
    get_skill_tree = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

GENERATED_SKILLS_DIR = Path("./generated_skills")

CATEGORY_COLORS: dict[str, str] = {
    "core": "#7F77DD",
    "web": "#1D9E75",
    "data": "#D85A30",
    "browser": "#378ADD",
    "api": "#639922",
    "file": "#D4537E",
    "analysis": "#BA7517",
}

_DEFAULT_COLOR = "#888780"


async def registrar_node(state: dict) -> dict:
    """LangGraph node that registers a tested skill into the system.

    Renames temp file to final, persists to DB, registers with SkillRegistry,
    updates the skill tree, and routes back to executor for retry.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with the new skill registered and status set to 'executing'.
    """
    new_skill_code = state.get("new_skill_code", "")
    new_skill_metadata = state.get("new_skill_metadata", {})
    evolution_context = dict(state.get("evolution_context", {}))
    agent_events = list(state.get("agent_events", []))
    available_skills = list(state.get("available_skills", []))

    name = new_skill_metadata.get("name", "unknown_skill")
    category = new_skill_metadata.get("category", "general")
    parent_id = new_skill_metadata.get("parent_id")
    description = new_skill_metadata.get("description", f"Generated {category} tool")
    task_context = evolution_context.get("task_context", "")

    skill_id = name
    color = CATEGORY_COLORS.get(category, _DEFAULT_COLOR)

    logger.info("Registering new skill: %s (category=%s, parent=%s)", name, category, parent_id)

    # Rename temp file to final
    temp_path = GENERATED_SKILLS_DIR / f"_test_{name}.py"
    final_path = GENERATED_SKILLS_DIR / f"{name}.py"

    try:
        if temp_path.exists():
            os.rename(str(temp_path), str(final_path))
            logger.info("Renamed %s -> %s", temp_path, final_path)
        elif not final_path.exists():
            # Write code directly if temp file doesn't exist
            os.makedirs(GENERATED_SKILLS_DIR, exist_ok=True)
            with open(final_path, "w", encoding="utf-8") as f:
                f.write(new_skill_code)
            logger.info("Wrote skill code directly to %s", final_path)
    except OSError as exc:
        logger.error("Failed to rename/write skill file: %s", exc)

    # DB persist: save_skill
    try:
        if save_skill is not None:
            await save_skill({
                "id": skill_id,
                "name": name,
                "description": description,
                "category": category,
                "parent_id": parent_id,
                "is_core": False,
                "code_path": str(final_path),
                "use_count": 0,
                "status": "active",
            })
            logger.info("Saved skill '%s' to database", name)
    except Exception as exc:
        logger.error("Failed to save skill to DB: %s", exc)

    # DB persist: save_evolution_history
    try:
        if save_evolution_history is not None:
            await save_evolution_history({
                "id": uuid.uuid4().hex[:12],
                "skill_id": skill_id,
                "skill_name": name,
                "trigger_task": task_context,
                "code_snippet": new_skill_code[:2000],
                "test_passed": True,
            })
            logger.info("Saved evolution history for '%s'", name)
    except Exception as exc:
        logger.error("Failed to save evolution history: %s", exc)

    # Register with SkillRegistry singleton (also updates the skill tree)
    try:
        if get_registry is not None:
            registry = get_registry()
            await registry.register_generated_skill(
                skill_id=name,
                name=name,
                description=description,
                category=category,
                parent_id=parent_id,
                code_path=str(final_path),
            )
            logger.info("Registered skill '%s' with SkillRegistry singleton", name)
    except Exception as exc:
        logger.error("Failed to register skill with registry: %s", exc)

    # Build skill tree event data for WebSocket broadcast
    skill_tree_data: dict[str, Any] = {
        "action": "add_node",
        "node": {
            "id": skill_id,
            "name": name,
            "category": category,
            "is_core": False,
            "val": 8,
            "color": color,
            "glow": True,
        },
        "edge": {"source": parent_id, "target": skill_id} if parent_id else None,
    }

    # Emit events
    agent_events.append({
        "event": "skill_tree_update",
        "node": skill_tree_data.get("node", {}),
        "edge": skill_tree_data.get("edge"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    agent_events.append({
        "event": "agent_status",
        "status": "registering",
        "message": f"New skill '{name}' registered successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Add new skill to available_skills
    if name not in available_skills:
        available_skills.append(name)

    # Update the current plan step to use the newly created tool's ID
    # so the executor finds the right tool on retry instead of looping.
    plan = list(state.get("plan", []))
    current_step = state.get("current_step", 0)
    if plan and current_step < len(plan):
        plan[current_step] = {
            **plan[current_step],
            "tool": name,
            "needs_new_tool": False,
        }
        logger.info(
            "Updated plan step %d tool to '%s'",
            current_step + 1,
            name,
        )

    return {
        "status": "executing",
        "evolution_needed": False,
        "evolution_context": {},
        "plan": plan,
        "available_skills": available_skills,
        "skill_tree_update": skill_tree_data,
        "agent_events": agent_events,
    }
