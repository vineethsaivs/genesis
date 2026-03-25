"""REST API routes for skills, skill tree, evolution history, and tasks."""

import logging
import uuid

from fastapi import APIRouter, HTTPException

from backend.db import database as db
from backend.db.models import (
    EvolutionHistoryResponse,
    EvolutionRecord,
    SkillListResponse,
    SkillResponse,
    SkillTreeLink,
    SkillTreeNode,
    SkillTreeResponse,
    TaskRequest,
    TaskResponse,
)
from backend.skills import get_skill_tree

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/skills", response_model=SkillListResponse)
async def list_skills() -> SkillListResponse:
    """Return all registered skills."""
    rows = await db.get_all_skills()
    skills = [SkillResponse(**{**r, "is_core": bool(r.get("is_core"))}) for r in rows]
    return SkillListResponse(skills=skills, total=len(skills))


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str) -> SkillResponse:
    """Return a single skill by id."""
    row = await db.get_skill_by_id(skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse(**{**row, "is_core": bool(row.get("is_core"))})


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str) -> dict:
    """Delete a generated skill. Core skills cannot be deleted."""
    row = await db.get_skill_by_id(skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if row.get("is_core"):
        raise HTTPException(status_code=403, detail="Cannot delete a core skill")
    await db.delete_skill(skill_id)
    return {"deleted": skill_id}


@router.get("/skill-tree", response_model=SkillTreeResponse)
async def skill_tree_endpoint() -> SkillTreeResponse:
    """Return the skill tree in react-force-graph-2d format."""
    tree = get_skill_tree()
    data = await tree.get_graph_data()
    nodes = [SkillTreeNode(**n) for n in data["nodes"]]
    links = [SkillTreeLink(**lnk) for lnk in data["links"]]
    return SkillTreeResponse(nodes=nodes, links=links)


@router.get("/evolution-history", response_model=EvolutionHistoryResponse)
async def get_evolution_history() -> EvolutionHistoryResponse:
    """Return the full evolution history."""
    rows = await db.get_evolution_history()
    records = [EvolutionRecord(**{**r, "test_passed": bool(r.get("test_passed"))}) for r in rows]
    return EvolutionHistoryResponse(records=records, total=len(records))


@router.post("/task", response_model=TaskResponse)
async def submit_task(request: TaskRequest) -> TaskResponse:
    """Accept a task and return a task_id. Use WebSocket for streaming results."""
    task_id = uuid.uuid4().hex[:12]
    logger.info("Task %s accepted: %s", task_id, request.task[:80])
    return TaskResponse(task_id=task_id)
