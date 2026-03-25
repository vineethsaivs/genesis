"""Skill tree visualization data manager for GENESIS.

Manages the directed graph of skills and their relationships,
providing data in react-force-graph-2d compatible format.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_CATEGORY_COLORS: dict[str, str] = {
    "core": "#7F77DD",
    "web": "#1D9E75",
    "data": "#D85A30",
    "browser": "#378ADD",
    "api": "#639922",
    "file": "#D4537E",
    "analysis": "#BA7517",
}

_DEFAULT_COLOR = "#888780"


class SkillTree:
    """Manages the skill tree graph for visualization and persistence."""

    def __init__(self, persist_path: str = "./data/skill_tree.json") -> None:
        """Initialize the skill tree.

        Args:
            persist_path: Path to the JSON file for persisting tree state.
        """
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self._persist_path: Path = Path(persist_path).resolve()

    async def add_node(
        self,
        node_id: str,
        name: str,
        category: str,
        is_core: bool = False,
        parent_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Add a node to the skill tree.

        Args:
            node_id: Unique identifier for the node.
            name: Display name for the node.
            category: Skill category (core, web, browser, etc.).
            is_core: Whether this is a built-in core tool.
            parent_id: Optional parent node ID to create an edge.
            **kwargs: Additional node properties.

        Returns:
            The created node dict.
        """
        node = {
            "id": node_id,
            "name": name,
            "category": category,
            "is_core": is_core,
            "status": kwargs.get("status", "active"),
            "use_count": kwargs.get("use_count", 0),
            "created_at": kwargs.get("created_at", datetime.now(timezone.utc).isoformat()),
            "val": 12 if is_core else 8,
            "color": self._category_color(category),
        }
        node.update({k: v for k, v in kwargs.items() if k not in node})

        self.nodes[node_id] = node

        if parent_id and parent_id in self.nodes:
            edge = {"source": parent_id, "target": node_id}
            if edge not in self.edges:
                self.edges.append(edge)

        logger.info("Added skill tree node: %s (%s)", name, category)
        return node

    async def get_graph_data(self) -> dict:
        """Get graph data in react-force-graph-2d format.

        Returns:
            Dict with 'nodes' list and 'links' list.
        """
        return {
            "nodes": list(self.nodes.values()),
            "links": list(self.edges),
        }

    def _category_color(self, category: str) -> str:
        """Get the color hex code for a category.

        Args:
            category: The skill category.

        Returns:
            Hex color string.
        """
        return _CATEGORY_COLORS.get(category, _DEFAULT_COLOR)

    async def increment_usage(self, node_id: str) -> None:
        """Increment the usage counter for a node.

        Args:
            node_id: The node ID to increment.
        """
        if node_id in self.nodes:
            self.nodes[node_id]["use_count"] = self.nodes[node_id].get("use_count", 0) + 1

    async def save(self) -> None:
        """Persist the skill tree to JSON file."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "nodes": self.nodes,
                "edges": self.edges,
            }
            content = json.dumps(data, indent=2, default=str)
            await asyncio.to_thread(self._persist_path.write_text, content, "utf-8")
            logger.debug("Skill tree saved to %s", self._persist_path)
        except Exception as e:
            logger.error("Failed to save skill tree: %s", e)

    async def load(self) -> None:
        """Load the skill tree from JSON file. No-op if file doesn't exist."""
        try:
            if not self._persist_path.exists():
                logger.debug("No skill tree file at %s, starting fresh", self._persist_path)
                return

            content = await asyncio.to_thread(self._persist_path.read_text, "utf-8")
            data = json.loads(content)

            self.nodes = data.get("nodes", {})
            self.edges = data.get("edges", [])
            logger.info("Loaded skill tree with %d nodes", len(self.nodes))
        except Exception as e:
            logger.error("Failed to load skill tree: %s", e)
            self.nodes = {}
            self.edges = []

    async def initialize_core_tree(self) -> None:
        """Create the initial core tool nodes in the tree."""
        core_tools = [
            ("web_search", "Web Search", "web"),
            ("browser_tool", "Browser", "browser"),
            ("file_io", "File I/O", "file"),
            ("calculator", "Calculator", "core"),
            ("text_analysis", "Text Analysis", "analysis"),
        ]

        for node_id, name, category in core_tools:
            await self.add_node(
                node_id=node_id,
                name=name,
                category=category,
                is_core=True,
            )

        logger.info("Initialized core skill tree with %d nodes", len(core_tools))
