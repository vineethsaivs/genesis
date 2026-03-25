"""Sandbox node — safely tests generated tool code via AST check + isolated subprocess."""

import ast
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from backend.agent.state import AgentState
except ImportError:
    AgentState = dict  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

GENERATED_SKILLS_DIR = Path("./generated_skills")
TEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3


def _check_syntax(code: str) -> tuple[bool, str]:
    """Check Python code for syntax errors using ast.parse.

    Args:
        code: Python source code string.

    Returns:
        Tuple of (is_valid, error_message). error_message is empty on success.
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        error_msg = f"SyntaxError at line {exc.lineno}: {exc.msg}"
        logger.warning("Syntax check failed: %s", error_msg)
        return False, error_msg


async def _run_tests_subprocess(file_path: str) -> dict[str, Any]:
    """Run test functions from a generated skill file in an isolated subprocess.

    Args:
        file_path: Absolute path to the Python file to test.

    Returns:
        Dict with 'success', 'results' (list of test outcomes), and 'error' keys.
    """
    test_script = f"""
import sys
import json
import importlib.util
import asyncio

# Try to limit memory (may not work on all platforms)
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
except Exception:
    pass

results = []
try:
    spec = importlib.util.spec_from_file_location("test_module", {file_path!r})
    if spec is None or spec.loader is None:
        print(json.dumps({{"success": False, "results": [], "error": "Could not load module"}}))
        sys.exit(0)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find all test_ functions
    test_fns = [
        (name, obj) for name, obj in module.__dict__.items()
        if name.startswith("test_") and callable(obj)
    ]

    if not test_fns:
        print(json.dumps({{"success": True, "results": [{{"name": "no_tests", "passed": True, "detail": "No test functions found"}}], "error": ""}}))
        sys.exit(0)

    for name, fn in test_fns:
        try:
            if asyncio.iscoroutinefunction(fn):
                asyncio.get_event_loop().run_until_complete(fn())
            else:
                fn()
            results.append({{"name": name, "passed": True, "detail": ""}})
        except Exception as e:
            results.append({{"name": name, "passed": False, "detail": str(e)}})

    all_passed = all(r["passed"] for r in results)
    print(json.dumps({{"success": all_passed, "results": results, "error": ""}}))

except Exception as e:
    print(json.dumps({{"success": False, "results": results, "error": str(e)}}))
"""

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", test_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=TEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "success": False,
                "results": [],
                "error": f"Tests timed out after {TEST_TIMEOUT_SECONDS}s",
            }

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if stderr_text:
            logger.debug("Test subprocess stderr: %s", stderr_text[:500])

        if not stdout_text:
            return {
                "success": False,
                "results": [],
                "error": f"No output from test subprocess. stderr: {stderr_text[:200]}",
            }

        # Parse the last line of stdout as JSON (test script prints one JSON line)
        last_line = stdout_text.strip().split("\n")[-1]
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            return {
                "success": False,
                "results": [],
                "error": f"Could not parse test output: {last_line[:200]}",
            }

    except Exception as exc:
        return {
            "success": False,
            "results": [],
            "error": f"Subprocess execution error: {exc}",
        }


def _cleanup_file(path: str) -> None:
    """Remove a file, ignoring errors.

    Args:
        path: Path to the file to delete.
    """
    try:
        os.unlink(path)
    except OSError as exc:
        logger.debug("Could not clean up %s: %s", path, exc)


async def sandbox_node(state: dict) -> dict:
    """LangGraph node that tests generated tool code in an isolated sandbox.

    Performs AST syntax checking, writes code to a temp file, runs embedded
    test functions in a subprocess, and routes based on results.

    Args:
        state: The current agent state dictionary.

    Returns:
        Updated state with test_results, status, and possibly updated evolution_context.
    """
    new_skill_code = state.get("new_skill_code", "")
    new_skill_metadata = state.get("new_skill_metadata", {})
    evolution_context = dict(state.get("evolution_context", {}))
    agent_events = list(state.get("agent_events", []))

    name = new_skill_metadata.get("name", "unknown_skill")
    retry_count = evolution_context.get("retry_count", 0)

    logger.info("Sandbox testing skill: %s (attempt %d)", name, retry_count + 1)

    agent_events.append({
        "event": "agent_status",
        "status": "testing",
        "message": f"Testing generated code for '{name}'",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Phase 1: Syntax check
    syntax_ok, syntax_error = _check_syntax(new_skill_code)
    if not syntax_ok:
        logger.warning("Syntax check failed for '%s': %s", name, syntax_error)

        agent_events.append({
            "event": "test_result",
            "skill_name": name,
            "passed": False,
            "details": f"Syntax error: {syntax_error}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if retry_count < MAX_RETRIES - 1:
            evolution_context["retry_count"] = retry_count + 1
            evolution_context["last_error"] = syntax_error
            return {
                "status": "evolving",
                "evolution_context": evolution_context,
                "agent_events": agent_events,
                "test_results": {"passed": False, "error": syntax_error},
            }

        agent_events.append({
            "event": "agent_status",
            "status": "error",
            "message": f"Tool '{name}' failed after {MAX_RETRIES} attempts: {syntax_error}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "error",
            "agent_events": agent_events,
            "test_results": {"passed": False, "error": syntax_error},
        }

    # Phase 2: Write temp file
    os.makedirs(GENERATED_SKILLS_DIR, exist_ok=True)
    temp_filename = f"_test_{name}.py"
    temp_path = str(GENERATED_SKILLS_DIR / temp_filename)

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(new_skill_code)
    except OSError as exc:
        logger.error("Could not write temp file %s: %s", temp_path, exc)
        agent_events.append({
            "event": "agent_status",
            "status": "error",
            "message": f"Could not write test file: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "status": "error",
            "agent_events": agent_events,
            "test_results": {"passed": False, "error": str(exc)},
        }

    # Phase 3: Run tests in subprocess
    test_output = await _run_tests_subprocess(temp_path)
    all_passed = test_output.get("success", False)
    test_results_list = test_output.get("results", [])
    test_error = test_output.get("error", "")

    details = ""
    if test_results_list:
        passed_count = sum(1 for r in test_results_list if r.get("passed"))
        total_count = len(test_results_list)
        details = f"{passed_count}/{total_count} tests passed"
        failed = [r for r in test_results_list if not r.get("passed")]
        if failed:
            details += ". Failures: " + "; ".join(
                f"{r['name']}: {r.get('detail', 'unknown')}" for r in failed
            )
    elif test_error:
        details = test_error

    agent_events.append({
        "event": "test_result",
        "skill_name": name,
        "passed": all_passed,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    if all_passed:
        logger.info("All tests passed for '%s'", name)
        # Keep the temp file — registrar will rename it
        return {
            "status": "registering",
            "agent_events": agent_events,
            "test_results": {"passed": True, "details": details},
        }

    # Tests failed
    logger.warning("Tests failed for '%s': %s", name, details)

    if retry_count < MAX_RETRIES - 1:
        _cleanup_file(temp_path)
        evolution_context["retry_count"] = retry_count + 1
        evolution_context["last_error"] = details
        return {
            "status": "evolving",
            "evolution_context": evolution_context,
            "agent_events": agent_events,
            "test_results": {"passed": False, "error": details},
        }

    # Max retries exceeded
    _cleanup_file(temp_path)
    agent_events.append({
        "event": "agent_status",
        "status": "error",
        "message": f"Tool '{name}' failed after {MAX_RETRIES} attempts",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "status": "error",
        "agent_events": agent_events,
        "test_results": {"passed": False, "error": details},
    }
