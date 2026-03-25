"""GENESIS Core Tool: Browser

Browse and interact with web pages using browser-use or httpx fallback.
"""

import logging
import os

logger = logging.getLogger(__name__)

SKILL_ID = "browser_tool"
SKILL_NAME = "Browser"
SKILL_DESCRIPTION = "Browse and interact with web pages"
SKILL_CATEGORY = "browser"

_BROWSER_USE_AVAILABLE = False
_BS4_AVAILABLE = False

try:
    from browser_use import Agent as BrowserAgent  # noqa: F401
    from langchain_openai import ChatOpenAI  # noqa: F401

    _BROWSER_USE_AVAILABLE = True
except ImportError:
    logger.debug("browser-use or langchain-openai not available")

try:
    from bs4 import BeautifulSoup  # noqa: F401

    _BS4_AVAILABLE = True
except ImportError:
    logger.debug("beautifulsoup4 not available")


async def browse(task: str, url: str | None = None) -> dict:
    """Browse a web page and extract information.

    Uses a three-tier fallback strategy:
    1. browser-use with ChatOpenAI (full browser automation)
    2. httpx + BeautifulSoup (static page fetch)
    3. Error if nothing works

    Args:
        task: Description of what to do on the page.
        url: Optional URL to navigate to.

    Returns:
        Dict with success status and page content or error.
    """
    if not task or not task.strip():
        return {"success": False, "error": "Empty task provided"}

    # Tier 1: browser-use
    if _BROWSER_USE_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        result = await _browse_with_browser_use(task, url)
        if result is not None:
            return result

    # Tier 2: httpx + BeautifulSoup
    if url and _BS4_AVAILABLE:
        result = await _browse_with_httpx(task, url)
        if result is not None:
            return result

    # Tier 3: Error
    missing = []
    if not _BROWSER_USE_AVAILABLE:
        missing.append("browser-use package")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not url:
        missing.append("URL (required for httpx fallback)")
    if not _BS4_AVAILABLE:
        missing.append("beautifulsoup4 package")

    return {
        "success": False,
        "error": f"No browsing method available. Missing: {', '.join(missing)}",
    }


async def _browse_with_browser_use(task: str, url: str | None) -> dict | None:
    """Attempt browsing with browser-use agent."""
    try:
        from browser_use import Agent as BrowserAgent
        from langchain_openai import ChatOpenAI

        logger.info("Using browser-use for task: %s", task[:100])
        llm = ChatOpenAI(model="gpt-4o")

        full_task = task
        if url:
            full_task = f"Go to {url} and {task}"

        agent = BrowserAgent(task=full_task, llm=llm)
        result = await agent.run()

        return {
            "success": True,
            "result": str(result),
            "method": "browser-use",
            "task": task,
            "url": url,
        }

    except Exception as e:
        logger.warning("browser-use failed: %s", e)
        return None


async def _browse_with_httpx(task: str, url: str) -> dict | None:
    """Attempt page fetch with httpx + BeautifulSoup."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        logger.info("Using httpx+bs4 fallback for URL: %s", url)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; GENESIS/1.0; "
                        "+https://github.com/genesis-ai)"
                    )
                },
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.title.string if soup.title else "No title"
        text = soup.get_text(separator="\n", strip=True)
        text = text[:5000]

        return {
            "success": True,
            "result": {
                "title": title,
                "text": text,
                "url": url,
            },
            "method": "httpx+bs4",
            "task": task,
        }

    except Exception as e:
        logger.warning("httpx+bs4 fallback failed: %s", e)
        return None
