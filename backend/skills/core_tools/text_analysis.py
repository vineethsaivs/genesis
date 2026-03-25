"""GENESIS Core Tool: Text Analysis

Summarize text, count words, and extract keywords.
"""

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

SKILL_ID = "text_analysis"
SKILL_NAME = "Text Analysis"
SKILL_DESCRIPTION = "Summarize text, count words, and extract keywords"
SKILL_CATEGORY = "analysis"

_STOPWORDS: set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "get", "got", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how",
    "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't",
    "it", "it's", "its", "itself", "just", "let's", "like", "may", "me", "might",
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "said", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the",
    "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through",
    "to", "too", "under", "until", "up", "us", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
    "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why",
    "why's", "will", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves",
}


async def summarize(text: str, max_length: int = 200) -> dict:
    """Summarize text content.

    Attempts to use an LLM for summarization, falling back to extractive
    summarization based on sentence scoring.

    Args:
        text: The text to summarize.
        max_length: Maximum character length for the summary.

    Returns:
        Dict with success status and summary or error.
    """
    try:
        if not text or not text.strip():
            return {"success": False, "error": "Empty text provided"}

        # Try LLM-based summarization
        summary = await _try_llm_summarize(text, max_length)
        if summary:
            return {
                "success": True,
                "result": summary,
                "method": "llm",
                "original_length": len(text),
            }

        # Fallback: extractive summarization
        summary = _extractive_summarize(text, max_length)
        return {
            "success": True,
            "result": summary,
            "method": "extractive",
            "original_length": len(text),
        }

    except Exception as e:
        logger.error("Error summarizing text: %s", e)
        return {"success": False, "error": f"Summarization error: {e}"}


async def _try_llm_summarize(text: str, max_length: int) -> str | None:
    """Attempt LLM-based summarization, returning None on failure."""
    try:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model="claude-sonnet-4-20250514")
        response = await llm.ainvoke(
            f"Summarize the following text in under {max_length} characters:\n\n{text}"
        )
        result = response.content
        if isinstance(result, str):
            return result[:max_length]
    except Exception:
        logger.debug("Anthropic summarization unavailable, trying OpenAI")

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini")
        response = await llm.ainvoke(
            f"Summarize the following text in under {max_length} characters:\n\n{text}"
        )
        result = response.content
        if isinstance(result, str):
            return result[:max_length]
    except Exception:
        logger.debug("OpenAI summarization unavailable, using extractive fallback")

    return None


def _extractive_summarize(text: str, max_length: int) -> str:
    """Score sentences by word frequency and return top ones."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return text[:max_length]

    words = re.findall(r'\b[a-z]+\b', text.lower())
    word_freq = Counter(w for w in words if w not in _STOPWORDS)

    scored = []
    for sentence in sentences:
        s_words = re.findall(r'\b[a-z]+\b', sentence.lower())
        score = sum(word_freq.get(w, 0) for w in s_words)
        scored.append((score, sentence))

    scored.sort(key=lambda x: x[0], reverse=True)

    summary_parts = []
    current_length = 0
    for _, sentence in scored:
        if current_length + len(sentence) + 1 > max_length:
            break
        summary_parts.append(sentence)
        current_length += len(sentence) + 1

    if not summary_parts:
        return sentences[0][:max_length]

    return " ".join(summary_parts)


async def word_count(text: str) -> dict:
    """Count words, characters, and lines in text.

    Args:
        text: The text to analyze.

    Returns:
        Dict with word, character, and line counts.
    """
    try:
        if not text:
            return {"success": False, "error": "Empty text provided"}

        words = text.split()
        return {
            "success": True,
            "result": {
                "word_count": len(words),
                "char_count": len(text),
                "line_count": text.count("\n") + 1,
            },
        }

    except Exception as e:
        logger.error("Error counting words: %s", e)
        return {"success": False, "error": f"Word count error: {e}"}


async def extract_keywords(text: str, top_n: int = 10) -> dict:
    """Extract top keywords from text by frequency.

    Args:
        text: The text to extract keywords from.
        top_n: Number of top keywords to return.

    Returns:
        Dict with success status and list of keyword/count pairs.
    """
    try:
        if not text or not text.strip():
            return {"success": False, "error": "Empty text provided"}

        cleaned = re.sub(r'[^\w\s]', '', text.lower())
        words = cleaned.split()

        filtered = [w for w in words if w not in _STOPWORDS and len(w) > 1]
        counts = Counter(filtered)
        top_keywords = [
            {"keyword": word, "count": count}
            for word, count in counts.most_common(top_n)
        ]

        return {
            "success": True,
            "result": top_keywords,
            "total_unique_words": len(counts),
        }

    except Exception as e:
        logger.error("Error extracting keywords: %s", e)
        return {"success": False, "error": f"Keyword extraction error: {e}"}
