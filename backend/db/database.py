"""SQLite persistence layer using aiosqlite."""

import logging
import uuid
from datetime import UTC, datetime

import aiosqlite

from backend.config import settings

logger = logging.getLogger(__name__)

_SKILLS_TABLE = """
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    parent_id TEXT,
    is_core INTEGER NOT NULL DEFAULT 0,
    code_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    use_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active'
)
"""

_EVOLUTION_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS evolution_history (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    trigger_task TEXT NOT NULL DEFAULT '',
    code_snippet TEXT NOT NULL DEFAULT '',
    test_passed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""

_SKILL_TREE_EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS skill_tree_edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    PRIMARY KEY (source, target)
)
"""


async def init_db() -> None:
    """Create tables if they don't exist and enable WAL mode."""
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(_SKILLS_TABLE)
        await db.execute(_EVOLUTION_HISTORY_TABLE)
        await db.execute(_SKILL_TREE_EDGES_TABLE)
        await db.commit()
    logger.info("Database initialized at %s", settings.DB_PATH)


async def get_all_skills() -> list[dict]:
    """Return all skills as a list of dicts."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM skills ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_skill_by_id(skill_id: str) -> dict | None:
    """Return a single skill or None."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_skill(skill: dict) -> dict:
    """Insert or replace a skill. Returns the saved skill."""
    if "id" not in skill or not skill["id"]:
        skill["id"] = uuid.uuid4().hex[:12]
    if "created_at" not in skill or not skill["created_at"]:
        skill["created_at"] = datetime.now(UTC).isoformat()

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO skills
               (id, name, description, category, parent_id,
                is_core, code_path, created_at, use_count, status)
               VALUES (:id, :name, :description, :category,
                :parent_id, :is_core, :code_path, :created_at,
                :use_count, :status)""",
            {
                "id": skill["id"],
                "name": skill.get("name", ""),
                "description": skill.get("description", ""),
                "category": skill.get("category", "general"),
                "parent_id": skill.get("parent_id"),
                "is_core": int(skill.get("is_core", False)),
                "code_path": skill.get("code_path", ""),
                "created_at": skill["created_at"],
                "use_count": skill.get("use_count", 0),
                "status": skill.get("status", "active"),
            },
        )
        # Add edge if parent exists
        if skill.get("parent_id"):
            await db.execute(
                "INSERT OR IGNORE INTO skill_tree_edges (source, target) VALUES (?, ?)",
                (skill["parent_id"], skill["id"]),
            )
        await db.commit()

    logger.info("Saved skill %s (%s)", skill["id"], skill.get("name"))
    return skill


async def update_skill_usage(skill_id: str) -> None:
    """Increment use_count for a skill."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE skills SET use_count = use_count + 1 WHERE id = ?",
            (skill_id,),
        )
        await db.commit()


async def delete_skill(skill_id: str) -> bool:
    """Delete a skill. Returns True if a row was removed."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        await db.execute(
            "DELETE FROM skill_tree_edges WHERE source = ? OR target = ?",
            (skill_id, skill_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def save_evolution_history(record: dict) -> dict:
    """Insert an evolution history record."""
    if "id" not in record or not record["id"]:
        record["id"] = uuid.uuid4().hex[:12]
    if "created_at" not in record or not record["created_at"]:
        record["created_at"] = datetime.now(UTC).isoformat()

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """INSERT INTO evolution_history
               (id, skill_id, skill_name, trigger_task,
                code_snippet, test_passed, created_at)
               VALUES (:id, :skill_id, :skill_name,
                :trigger_task, :code_snippet, :test_passed,
                :created_at)""",
            {
                "id": record["id"],
                "skill_id": record.get("skill_id", ""),
                "skill_name": record.get("skill_name", ""),
                "trigger_task": record.get("trigger_task", ""),
                "code_snippet": record.get("code_snippet", ""),
                "test_passed": int(record.get("test_passed", False)),
                "created_at": record["created_at"],
            },
        )
        await db.commit()

    logger.info("Saved evolution record %s", record["id"])
    return record


async def get_evolution_history() -> list[dict]:
    """Return all evolution history records."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM evolution_history ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_skill_tree() -> dict:
    """Return the skill tree in react-force-graph-2d format: {nodes, links}."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id, name, category, is_core, use_count FROM skills")
        skill_rows = await cursor.fetchall()

        cursor = await db.execute("SELECT source, target FROM skill_tree_edges")
        edge_rows = await cursor.fetchall()

    nodes = [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "is_core": bool(row["is_core"]),
            "val": max(1, row["use_count"]),
        }
        for row in skill_rows
    ]
    links = [{"source": row["source"], "target": row["target"]} for row in edge_rows]

    return {"nodes": nodes, "links": links}
