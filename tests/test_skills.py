"""Tests for the GENESIS skill management system."""

import json
from pathlib import Path

import pytest


# --- Calculator Tests ---


class TestCalculator:
    """Tests for the calculator core tool."""

    async def test_basic_arithmetic(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("2 + 3")
        assert result["success"] is True
        assert result["result"] == 5.0

    async def test_complex_expression(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("2 ** 10")
        assert result["success"] is True
        assert result["result"] == 1024.0

    async def test_math_functions(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("sqrt(16)")
        assert result["success"] is True
        assert result["result"] == 4.0

    async def test_math_constants(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("pi")
        assert result["success"] is True
        assert abs(result["result"] - 3.14159265) < 0.001

    async def test_rejects_import(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate('__import__("os")')
        assert result["success"] is False
        assert "not allowed" in result["error"]

    async def test_rejects_lambda(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("(lambda: 1)()")
        assert result["success"] is False

    async def test_rejects_open(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate('open("/etc/passwd")')
        assert result["success"] is False

    async def test_division_by_zero(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("1/0")
        assert result["success"] is False

    async def test_empty_expression(self):
        from backend.skills.core_tools.calculator import calculate

        result = await calculate("")
        assert result["success"] is False


# --- File I/O Tests ---


class TestFileIO:
    """Tests for the file I/O core tool."""

    async def test_write_and_read(self, tmp_path):
        from backend.skills.core_tools import file_io

        original_dir = file_io.OUTPUTS_DIR
        file_io.OUTPUTS_DIR = tmp_path

        try:
            write_result = await file_io.write_file("test.txt", "hello world")
            assert write_result["success"] is True

            read_result = await file_io.read_file("test.txt")
            assert read_result["success"] is True
            assert read_result["result"] == "hello world"
        finally:
            file_io.OUTPUTS_DIR = original_dir

    async def test_list_files(self, tmp_path):
        from backend.skills.core_tools import file_io

        original_dir = file_io.OUTPUTS_DIR
        file_io.OUTPUTS_DIR = tmp_path

        try:
            await file_io.write_file("a.txt", "content a")
            await file_io.write_file("b.txt", "content b")

            result = await file_io.list_files()
            assert result["success"] is True
            assert result["count"] == 2
        finally:
            file_io.OUTPUTS_DIR = original_dir

    async def test_rejects_path_traversal(self):
        from backend.skills.core_tools.file_io import read_file

        result = await read_file("../../etc/passwd")
        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "not allowed" in result["error"].lower()

    async def test_rejects_absolute_path(self):
        from backend.skills.core_tools.file_io import read_file

        result = await read_file("/etc/passwd")
        assert result["success"] is False

    async def test_read_nonexistent(self, tmp_path):
        from backend.skills.core_tools import file_io

        original_dir = file_io.OUTPUTS_DIR
        file_io.OUTPUTS_DIR = tmp_path

        try:
            result = await file_io.read_file("nonexistent.txt")
            assert result["success"] is False
            assert "not found" in result["error"].lower()
        finally:
            file_io.OUTPUTS_DIR = original_dir


# --- Text Analysis Tests ---


class TestTextAnalysis:
    """Tests for the text analysis core tool."""

    async def test_word_count(self):
        from backend.skills.core_tools.text_analysis import word_count

        result = await word_count("Hello world this is a test")
        assert result["success"] is True
        assert result["result"]["word_count"] == 6

    async def test_extract_keywords(self):
        from backend.skills.core_tools.text_analysis import extract_keywords

        text = "python programming python code python developer programming code"
        result = await extract_keywords(text, top_n=3)
        assert result["success"] is True
        assert len(result["result"]) == 3
        assert result["result"][0]["keyword"] == "python"

    async def test_summarize_extractive(self):
        from backend.skills.core_tools.text_analysis import summarize

        text = "This is the first sentence. This is the second sentence. This is the third."
        result = await summarize(text, max_length=200)
        assert result["success"] is True
        assert len(result["result"]) <= 200

    async def test_empty_text(self):
        from backend.skills.core_tools.text_analysis import word_count

        result = await word_count("")
        assert result["success"] is False


# --- Web Search Tests ---


class TestWebSearch:
    """Tests for the web search core tool."""

    async def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)

        from backend.skills.core_tools.web_search import search

        result = await search("test query")
        assert result["success"] is False
        assert "SERPER_API_KEY" in result["error"]

    async def test_empty_query(self):
        from backend.skills.core_tools.web_search import search

        result = await search("")
        assert result["success"] is False


# --- Skill Tree Tests ---


class TestSkillTree:
    """Tests for the skill tree."""

    async def test_initialize_core_tree(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()
        assert len(tree.nodes) == 5

    async def test_graph_format(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()
        data = await tree.get_graph_data()

        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) == 5
        assert len(data["links"]) == 0

    async def test_node_has_required_fields(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()
        node = tree.nodes["calculator"]

        for field in ["id", "name", "category", "is_core", "status", "use_count",
                      "created_at", "val", "color"]:
            assert field in node, f"Missing field: {field}"

    async def test_category_colors(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()

        assert tree.nodes["calculator"]["color"] == "#7F77DD"  # core = purple
        assert tree.nodes["web_search"]["color"] == "#1D9E75"  # web = teal
        assert tree.nodes["browser_tool"]["color"] == "#378ADD"  # browser = blue

    async def test_add_node_with_parent(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()
        await tree.add_node("child_skill", "Child", "web", parent_id="web_search")

        assert "child_skill" in tree.nodes
        assert tree.nodes["child_skill"]["val"] == 8  # non-core
        assert {"source": "web_search", "target": "child_skill"} in tree.edges

    async def test_increment_usage(self):
        from backend.skills.skill_tree import SkillTree

        tree = SkillTree()
        await tree.initialize_core_tree()
        await tree.increment_usage("calculator")
        await tree.increment_usage("calculator")

        assert tree.nodes["calculator"]["use_count"] == 2

    async def test_save_and_load(self, tmp_path):
        from backend.skills.skill_tree import SkillTree

        path = str(tmp_path / "tree.json")
        tree = SkillTree(persist_path=path)
        await tree.initialize_core_tree()
        await tree.save()

        tree2 = SkillTree(persist_path=path)
        await tree2.load()
        assert len(tree2.nodes) == 5

        # Verify file is valid JSON
        with open(path) as f:
            data = json.load(f)
        assert "nodes" in data
        assert "edges" in data


# --- Registry Tests ---


class TestSkillRegistry:
    """Tests for the skill registry."""

    async def test_initialize_loads_core(self):
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        await registry.initialize()

        skills = await registry.list_skills()
        assert len(skills) == 5
        assert all(s["is_core"] for s in skills)

    async def test_execute_skill(self):
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        await registry.initialize()

        result = await registry.execute_skill("calculator", expression="3 * 7")
        assert result["success"] is True
        assert result["result"] == 21.0

    async def test_execute_nonexistent(self):
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        await registry.initialize()

        result = await registry.execute_skill("nonexistent")
        assert result["success"] is False

    async def test_remove_core_fails(self):
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        await registry.initialize()

        removed = await registry.remove_skill("calculator")
        assert removed is False

    async def test_list_skill_ids(self):
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        await registry.initialize()

        ids = await registry.list_skill_ids()
        assert "calculator" in ids
        assert "web_search" in ids
        assert len(ids) == 5


# --- Factory Tests ---


class TestCreateSkillSystem:
    """Tests for the factory function."""

    async def test_create_returns_tuple(self):
        from backend.skills import create_skill_system
        from backend.skills.registry import SkillRegistry
        from backend.skills.skill_tree import SkillTree

        registry, tree = await create_skill_system()
        assert isinstance(registry, SkillRegistry)
        assert isinstance(tree, SkillTree)

    async def test_tree_has_nodes_after_create(self):
        from backend.skills import create_skill_system

        _, tree = await create_skill_system()
        assert len(tree.nodes) == 5

    async def test_registry_has_skills_after_create(self):
        from backend.skills import create_skill_system

        registry, _ = await create_skill_system()
        assert len(registry.skills) == 5
