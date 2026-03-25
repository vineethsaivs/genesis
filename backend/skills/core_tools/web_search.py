"""GENESIS Core Tool: Web Search

Search Google for information using the Serper API.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

SKILL_ID = "web_search"
SKILL_NAME = "Web Search"
SKILL_DESCRIPTION = "Search Google for information using Serper API"
SKILL_CATEGORY = "web"


async def search(query: str, max_results: int = 5) -> dict:
    """Search Google using the Serper API.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        Dict with success status and list of search results or error.
    """
    try:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": "SERPER_API_KEY environment variable not set",
            }

        if not query or not query.strip():
            return {"success": False, "error": "Empty query provided"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": max_results},
            )
            response.raise_for_status()
            data = response.json()

        organic = data.get("organic", [])
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in organic[:max_results]
        ]

        return {
            "success": True,
            "result": results,
            "query": query,
            "count": len(results),
        }

    except httpx.HTTPStatusError as e:
        logger.error("Serper API HTTP error: %s", e)
        return {"success": False, "error": f"Search API error: {e.response.status_code}"}
    except httpx.TimeoutException:
        logger.error("Serper API timeout for query: %s", query)
        return {"success": False, "error": "Search request timed out"}
    except Exception as e:
        logger.error("Error searching for %r: %s", query, e)
        return {"success": False, "error": f"Search error: {e}"}
