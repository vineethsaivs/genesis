"""Code generation templates and prompts for skill creation."""

TOOL_GENERATION_SYSTEM_PROMPT: str = """You are a code generator for the GENESIS self-evolving AI agent.
Generate a single Python module that implements an MCP tool.

CRITICAL: The import MUST be 'from mcp.server.fastmcp import FastMCP'. NEVER use 'from fastmcp import register_tool' or 'from fastmcp import FastMCP' — those do NOT work. The correct import path is mcp.server.fastmcp.

Required code pattern:
```python
from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("tool_name")

@mcp.tool()
async def function_name(query: str = "", **kwargs) -> dict:
    \"\"\"Description\"\"\"
    try:
        # implementation
        return {"success": True, "result": data}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

Requirements:
- Single file, self-contained module
- Use FastMCP for tool registration (import from mcp.server.fastmcp)
- Use httpx (not requests) for any HTTP calls
- All functions must be async
- Wrap implementation in try/except with proper error handling
- Include at least 2 test functions (prefixed with test_)
- All tool functions must return dicts with 'success' and either 'result' or 'error' keys
- Export these module-level constants: SKILL_ID, SKILL_NAME, SKILL_DESCRIPTION, SKILL_CATEGORY
- Use type hints on all functions
- Include docstrings on all public functions
- Use logging module instead of print()

CRITICAL RULES:
- Every @mcp.tool() function MUST accept **kwargs as its last parameter to handle unexpected arguments
- Do NOT put @mcp.tool() on test_ functions — only on the main tool function
- Test functions MUST use mock/hardcoded data — no real network calls
- When using httpx, always set timeout=15.0
- Return meaningful data in the 'result' field, not just True/False
- Handle edge cases: empty input, missing fields, etc.
- All helper functions must also be async
- Use %s style logging, not f-strings in logger calls

CRITICAL TEST RULES:
- Test functions must take ZERO parameters. No mocker, no fixtures, no arguments.
- NEVER use pytest-mock, unittest.mock, or mocker fixtures.
- Use simple hardcoded assertions or inline mock data instead.
- Tests run in a bare Python subprocess — only stdlib and httpx are available.
- Good test pattern:
  async def test_my_tool():
      result = await my_tool(query='test')
      assert isinstance(result, dict)
      assert 'success' in result
      return True
- BAD test pattern (NEVER DO THIS):
  async def test_my_tool(mocker):  # WRONG, no mocker parameter
      mocker.patch(...)  # WRONG, no mocking framework
"""

TOOL_CODE_TEMPLATE: str = '''"""GENESIS Generated Skill: {name}

{description}
Category: {category}
Trigger task: {trigger_task}
"""

import logging

{imports}

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

SKILL_ID = "{name}"
SKILL_NAME = "{name}"
SKILL_DESCRIPTION = "{description}"
SKILL_CATEGORY = "{category}"

mcp = FastMCP("{name}")


@mcp.tool()
async def {function_name}({params}) -> {return_type}:
    """Execute the {name} skill."""
    try:
{implementation}
    except Exception as e:
        logger.error("Error in {name}: %s", e)
        return {{"success": False, "error": str(e)}}


async def test_basic() -> None:
    """Basic functionality test."""
{test_basic}


async def test_error() -> None:
    """Error handling test."""
{test_error}
'''

CATEGORY_IMPORTS: dict[str, str] = {
    "web": "import httpx\nfrom bs4 import BeautifulSoup",
    "browser": "from browser_use import Agent as BrowserAgent\nfrom langchain_openai import ChatOpenAI",
    "data": "import json\nimport csv\nimport re",
    "api": "import httpx",
    "file": "import os\nfrom pathlib import Path",
    "analysis": "import re\nimport json",
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "web": "Web scraping and search tools",
    "browser": "Browser automation and interaction tools",
    "data": "Data processing and transformation tools",
    "api": "External API integration tools",
    "file": "File system operation tools",
    "analysis": "Text and data analysis tools",
    "core": "Core utility tools",
}
