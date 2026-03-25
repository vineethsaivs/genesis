"""GENESIS Core Tool: File I/O

Read, write, and list files in the outputs directory.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_ID = "file_io"
SKILL_NAME = "File I/O"
SKILL_DESCRIPTION = "Read, write, and list files in the outputs directory"
SKILL_CATEGORY = "file"

OUTPUTS_DIR = Path("./outputs")


def _ensure_outputs_dir() -> None:
    """Create the outputs directory if it doesn't exist."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _validate_path(filename: str) -> Path:
    """Validate and resolve a filename within the outputs directory.

    Args:
        filename: The filename to validate.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the path is unsafe.
    """
    if ".." in filename:
        raise ValueError("Path traversal not allowed: '..' in filename")

    path = Path(filename)
    if path.is_absolute():
        raise ValueError("Absolute paths not allowed")

    _ensure_outputs_dir()
    resolved = (OUTPUTS_DIR / path).resolve()
    outputs_resolved = OUTPUTS_DIR.resolve()

    if not str(resolved).startswith(str(outputs_resolved)):
        raise ValueError("Path escapes outputs directory")

    return resolved


async def read_file(filename: str) -> dict:
    """Read contents of a file from the outputs directory.

    Args:
        filename: Name of the file to read, relative to outputs/.

    Returns:
        Dict with success status and file content or error.
    """
    try:
        path = _validate_path(filename)

        if not path.exists():
            return {"success": False, "error": f"File not found: {filename}"}

        content = await asyncio.to_thread(path.read_text, encoding="utf-8")

        return {
            "success": True,
            "result": content,
            "filename": filename,
            "size": len(content),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error("Error reading file %r: %s", filename, e)
        return {"success": False, "error": f"Read error: {e}"}


async def write_file(filename: str, content: str) -> dict:
    """Write content to a file in the outputs directory.

    Args:
        filename: Name of the file to write, relative to outputs/.
        content: Content to write to the file.

    Returns:
        Dict with success status and file info or error.
    """
    try:
        path = _validate_path(filename)

        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, encoding="utf-8")

        return {
            "success": True,
            "result": f"Written {len(content)} characters to {filename}",
            "filename": filename,
            "size": len(content),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error("Error writing file %r: %s", filename, e)
        return {"success": False, "error": f"Write error: {e}"}


async def list_files() -> dict:
    """List all files in the outputs directory.

    Returns:
        Dict with success status and list of files or error.
    """
    try:
        _ensure_outputs_dir()

        def _scan() -> list[dict]:
            files = []
            for item in sorted(OUTPUTS_DIR.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(OUTPUTS_DIR)
                    files.append({
                        "name": str(rel),
                        "size": item.stat().st_size,
                    })
            return files

        files = await asyncio.to_thread(_scan)

        return {
            "success": True,
            "result": files,
            "count": len(files),
        }

    except Exception as e:
        logger.error("Error listing files: %s", e)
        return {"success": False, "error": f"List error: {e}"}
