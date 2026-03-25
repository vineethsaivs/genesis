"""Skill registry for GENESIS.

Manages discovery, loading, and execution of core and generated skills.
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillEntry:
    """A registered skill with its metadata and callable."""

    id: str
    name: str
    description: str
    category: str
    parent_id: str | None = None
    is_core: bool = False
    code_path: str | None = None
    module: Any = None
    execute_fn: Any = None
    use_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "active"

    async def execute(self, **kwargs) -> dict:
        """Execute this skill's function.

        Args:
            **kwargs: Arguments to pass to the skill function.

        Returns:
            Dict with execution results.
        """
        if self.execute_fn is None:
            return {"success": False, "error": f"Skill '{self.id}' has no execute function"}

        try:
            if asyncio.iscoroutinefunction(self.execute_fn):
                result = await self.execute_fn(**kwargs)
            else:
                result = await asyncio.to_thread(self.execute_fn, **kwargs)

            self.use_count += 1

            if not isinstance(result, dict):
                result = {"success": True, "result": result}

            return result

        except Exception as e:
            logger.error("Error executing skill %r: %s", self.id, e)
            return {"success": False, "error": f"Execution error: {e}"}


class SkillRegistry:
    """Registry that discovers, loads, and manages all skills."""

    def __init__(
        self,
        core_tools_dir: str = "backend/skills/core_tools",
        generated_skills_dir: str = "generated_skills",
    ) -> None:
        """Initialize the skill registry.

        Args:
            core_tools_dir: Path to core tools package directory.
            generated_skills_dir: Path to generated skills directory.
        """
        self.skills: dict[str, SkillEntry] = {}
        self._core_tools_dir = Path(core_tools_dir)
        self._generated_skills_dir = Path(generated_skills_dir)
        self._skill_tree = None

    async def initialize(self, skill_tree: Any | None = None) -> None:
        """Load all skills from core tools and generated skills directories.

        Args:
            skill_tree: Optional SkillTree instance for syncing nodes.
        """
        self._skill_tree = skill_tree
        await self._load_core_tools()
        await self._load_generated_skills()
        logger.info(
            "Registry initialized: %d skills (%d core, %d generated)",
            len(self.skills),
            sum(1 for s in self.skills.values() if s.is_core),
            sum(1 for s in self.skills.values() if not s.is_core),
        )

    async def _load_core_tools(self) -> None:
        """Discover and load built-in core tool modules."""
        from backend.skills.core_tools import CORE_TOOL_MODULES

        for module_name in CORE_TOOL_MODULES:
            try:
                module = importlib.import_module(f"backend.skills.core_tools.{module_name}")

                skill_id = getattr(module, "SKILL_ID", None)
                skill_name = getattr(module, "SKILL_NAME", None)
                skill_description = getattr(module, "SKILL_DESCRIPTION", None)
                skill_category = getattr(module, "SKILL_CATEGORY", None)

                if not all([skill_id, skill_name, skill_description, skill_category]):
                    logger.warning(
                        "Core tool %r missing required constants, skipping", module_name
                    )
                    continue

                execute_fn = self._find_execute_function(module)
                status = "active" if execute_fn else "no_execute"

                if not execute_fn:
                    logger.warning("Core tool %r has no async execute function", module_name)

                entry = SkillEntry(
                    id=skill_id,
                    name=skill_name,
                    description=skill_description,
                    category=skill_category,
                    is_core=True,
                    module=module,
                    execute_fn=execute_fn,
                    status=status,
                )
                self.skills[skill_id] = entry
                logger.info("Loaded core tool: %s", skill_name)

            except ImportError as e:
                logger.warning("Failed to import core tool %r: %s", module_name, e)
            except Exception as e:
                logger.error("Error loading core tool %r: %s", module_name, e)

    async def _load_generated_skills(self) -> None:
        """Discover and load generated skill modules from disk."""
        if not self._generated_skills_dir.exists():
            self._generated_skills_dir.mkdir(parents=True, exist_ok=True)
            return

        for path in sorted(self._generated_skills_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue

            try:
                module_name = f"generated_skills.{path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    logger.warning("Could not create spec for %s", path)
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                skill_id = getattr(module, "SKILL_ID", None)
                skill_name = getattr(module, "SKILL_NAME", None)
                skill_description = getattr(module, "SKILL_DESCRIPTION", None)
                skill_category = getattr(module, "SKILL_CATEGORY", None)

                if not all([skill_id, skill_name, skill_description, skill_category]):
                    logger.warning(
                        "Generated skill %r missing required constants, skipping", path.name
                    )
                    continue

                execute_fn = self._find_execute_function(module)
                status = "active" if execute_fn else "no_execute"

                if not execute_fn:
                    logger.warning("Generated skill %r has no async execute function", path.name)

                entry = SkillEntry(
                    id=skill_id,
                    name=skill_name,
                    description=skill_description,
                    category=skill_category,
                    is_core=False,
                    code_path=str(path),
                    module=module,
                    execute_fn=execute_fn,
                    status=status,
                )
                self.skills[skill_id] = entry
                logger.info("Loaded generated skill: %s from %s", skill_name, path.name)

            except ImportError as e:
                logger.warning("Failed to import generated skill %r: %s", path.name, e)
            except Exception as e:
                logger.error("Error loading generated skill %r: %s", path.name, e)

    @staticmethod
    def _find_execute_function(module: Any) -> Any | None:
        """Find the first public async function in a module (source order).

        Skips functions starting with 'test_' or '_'.
        Uses module __dict__ to preserve definition order.

        Args:
            module: The loaded Python module.

        Returns:
            The async callable, or None if not found.
        """
        for name, obj in module.__dict__.items():
            if not inspect.isfunction(obj):
                continue
            if name.startswith("test_") or name.startswith("_"):
                continue
            if asyncio.iscoroutinefunction(obj):
                return obj
        return None

    async def get_skill(self, skill_id: str) -> SkillEntry | None:
        """Get a skill entry by ID.

        Args:
            skill_id: The skill identifier.

        Returns:
            The SkillEntry or None if not found.
        """
        return self.skills.get(skill_id)

    async def list_skills(self) -> list[dict]:
        """List all registered skills with their metadata.

        Returns:
            List of skill info dicts.
        """
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "is_core": s.is_core,
                "status": s.status,
                "use_count": s.use_count,
                "created_at": s.created_at,
            }
            for s in self.skills.values()
        ]

    async def list_skill_ids(self) -> list[str]:
        """List all registered skill IDs.

        Returns:
            List of skill ID strings.
        """
        return list(self.skills.keys())

    async def execute_skill(self, skill_id: str, **kwargs) -> dict:
        """Execute a skill by ID.

        Args:
            skill_id: The skill identifier.
            **kwargs: Arguments to pass to the skill function.

        Returns:
            Dict with execution results.
        """
        entry = self.skills.get(skill_id)
        if entry is None:
            return {"success": False, "error": f"Skill not found: {skill_id}"}

        result = await entry.execute(**kwargs)

        if self._skill_tree is not None:
            await self._skill_tree.increment_usage(skill_id)

        return result

    async def register_generated_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        category: str,
        parent_id: str | None,
        code_path: str,
    ) -> SkillEntry:
        """Register a newly generated skill from a code file.

        Args:
            skill_id: Unique skill identifier.
            name: Display name.
            description: Skill description.
            category: Skill category.
            parent_id: Parent skill ID for tree lineage.
            code_path: Path to the generated Python module.

        Returns:
            The created SkillEntry.
        """
        path = Path(code_path)
        module_name = f"generated_skills.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)

        module = None
        execute_fn = None
        status = "active"

        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            execute_fn = self._find_execute_function(module)
            if not execute_fn:
                status = "no_execute"

        entry = SkillEntry(
            id=skill_id,
            name=name,
            description=description,
            category=category,
            parent_id=parent_id,
            is_core=False,
            code_path=code_path,
            module=module,
            execute_fn=execute_fn,
            status=status,
        )
        self.skills[skill_id] = entry

        if self._skill_tree is not None:
            await self._skill_tree.add_node(
                node_id=skill_id,
                name=name,
                category=category,
                is_core=False,
                parent_id=parent_id,
            )
            await self._skill_tree.save()

        logger.info("Registered generated skill: %s (parent: %s)", name, parent_id)
        return entry

    async def remove_skill(self, skill_id: str) -> bool:
        """Remove a non-core skill from the registry.

        Args:
            skill_id: The skill identifier to remove.

        Returns:
            True if removed, False if not found or is a core skill.
        """
        entry = self.skills.get(skill_id)
        if entry is None:
            logger.warning("Cannot remove skill %r: not found", skill_id)
            return False

        if entry.is_core:
            logger.warning("Cannot remove core skill %r", skill_id)
            return False

        del self.skills[skill_id]
        logger.info("Removed skill: %s", skill_id)
        return True
