"""Skill management system for GENESIS.

Provides skill registry, skill tree visualization, and core tools.
"""

import logging

from backend.skills.registry import SkillRegistry
from backend.skills.skill_tree import SkillTree

logger = logging.getLogger(__name__)

_registry: SkillRegistry | None = None
_skill_tree: SkillTree | None = None


async def create_skill_system() -> tuple[SkillRegistry, SkillTree]:
    """Initialize and return the complete skill system.

    Loads persisted skill tree state, initializes core tools if needed,
    discovers generated skills, and returns the ready-to-use registry and tree.
    Sets module-level singletons so other modules can access via get_registry().
    """
    global _registry, _skill_tree

    tree = SkillTree()
    await tree.load()

    if not tree.nodes:
        await tree.initialize_core_tree()

    registry = SkillRegistry()
    await registry.initialize(skill_tree=tree)
    await tree.save()

    _registry = registry
    _skill_tree = tree

    logger.info("Skill system initialized with %d skills", len(registry.skills))
    return registry, tree


def get_registry() -> SkillRegistry:
    """Return the initialized skill registry singleton.

    Raises:
        RuntimeError: If create_skill_system() has not been called yet.
    """
    if _registry is None:
        raise RuntimeError("Skill system not initialized — call create_skill_system() first")
    return _registry


def get_skill_tree() -> SkillTree:
    """Return the initialized skill tree singleton.

    Raises:
        RuntimeError: If create_skill_system() has not been called yet.
    """
    if _skill_tree is None:
        raise RuntimeError("Skill system not initialized — call create_skill_system() first")
    return _skill_tree
