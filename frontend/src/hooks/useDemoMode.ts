import { useState, useEffect, useRef, useCallback } from 'react';

import type { AgentEvent, GraphData, SkillNode } from '../lib/types';
import { DEFAULT_GRAPH_DATA, CATEGORY_COLORS } from '../lib/types';

const DEMO_GENERATED_NODES: SkillNode[] = [
  {
    id: 'price_scraper',
    name: 'Price Scraper',
    category: 'web',
    is_core: false,
    status: 'active',
    use_count: 3,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    val: 6,
    color: CATEGORY_COLORS.web,
    description: 'Scrapes product prices from e-commerce sites',
    code_content: 'async def price_scraper(url: str) -> dict:\n    """Scrape price from URL."""\n    async with httpx.AsyncClient() as client:\n        resp = await client.get(url)\n        return {"price": parse_price(resp.text)}',
  },
  {
    id: 'pdf_parser',
    name: 'PDF Parser',
    category: 'file',
    is_core: false,
    status: 'active',
    use_count: 1,
    created_at: new Date(Date.now() - 43200000).toISOString(),
    val: 6,
    color: CATEGORY_COLORS.file,
    description: 'Extracts text content from PDF files',
    code_content: 'async def pdf_parser(path: str) -> str:\n    """Extract text from PDF."""\n    import pdfplumber\n    with pdfplumber.open(path) as pdf:\n        return "\\n".join(p.extract_text() for p in pdf.pages)',
  },
  {
    id: 'email_sender',
    name: 'Email Sender',
    category: 'api',
    is_core: false,
    status: 'active',
    use_count: 5,
    created_at: new Date(Date.now() - 21600000).toISOString(),
    val: 6,
    color: CATEGORY_COLORS.api,
    description: 'Sends emails via SMTP',
    code_content: 'async def email_sender(to: str, subject: str, body: str) -> bool:\n    """Send email via SMTP."""\n    import aiosmtplib\n    msg = MIMEText(body)\n    msg["Subject"] = subject\n    await aiosmtplib.send(msg, hostname="smtp.gmail.com")\n    return True',
  },
];

const DEMO_GENERATED_LINKS = [
  { source: 'web_search', target: 'price_scraper' },
  { source: 'file_io', target: 'pdf_parser' },
  { source: 'web_search', target: 'email_sender' },
];

interface DemoSkill {
  id: string;
  name: string;
  category: string;
  parentId: string;
  code: string;
  testName: string;
}

const DEMO_SKILLS: DemoSkill[] = [
  {
    id: 'stock_tracker',
    name: 'Stock Tracker',
    category: 'api',
    parentId: 'web_search',
    testName: 'test_stock_tracker_fetches_price',
    code: `import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stock_tracker")

@mcp.tool()
async def stock_tracker(symbol: str) -> dict:
    """Fetch current stock price for a ticker symbol."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.stockdata.org/v1/data/quote",
            params={"symbols": symbol}
        )
        data = resp.json()
        quote = data["data"][0]
        return {
            "symbol": quote["ticker"],
            "price": quote["price"],
            "change": quote["day_change"],
            "volume": quote["volume"],
        }`,
  },
  {
    id: 'weather_api',
    name: 'Weather API',
    category: 'api',
    parentId: 'web_search',
    testName: 'test_weather_api_returns_forecast',
    code: `import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather_api")

@mcp.tool()
async def weather_api(city: str) -> dict:
    """Get current weather for a city."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": "KEY", "units": "metric"}
        )
        data = resp.json()
        return {
            "city": data["name"],
            "temp_c": data["main"]["temp"],
            "condition": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
        }`,
  },
  {
    id: 'csv_analyzer',
    name: 'CSV Analyzer',
    category: 'data',
    parentId: 'text_analysis',
    testName: 'test_csv_analyzer_parses_columns',
    code: `import csv
import io
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("csv_analyzer")

@mcp.tool()
async def csv_analyzer(content: str) -> dict:
    """Analyze CSV data and return summary statistics."""
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    columns = list(rows[0].keys()) if rows else []
    return {
        "row_count": len(rows),
        "columns": columns,
        "sample": rows[:3],
        "column_count": len(columns),
    }`,
  },
  {
    id: 'reddit_scraper',
    name: 'Reddit Scraper',
    category: 'web',
    parentId: 'web_search',
    testName: 'test_reddit_scraper_fetches_posts',
    code: `import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("reddit_scraper")

@mcp.tool()
async def reddit_scraper(subreddit: str, limit: int = 10) -> list:
    """Scrape top posts from a subreddit."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": limit},
            headers={"User-Agent": "genesis-agent/1.0"}
        )
        data = resp.json()
        posts = data["data"]["children"]
        return [
            {"title": p["data"]["title"],
             "score": p["data"]["score"],
             "url": p["data"]["url"]}
            for p in posts
        ]`,
  },
];

export function useDemoMode(
  enabled: boolean,
  addNode: (node: SkillNode, edge?: { source: string; target: string }) => void,
  setGraphData: React.Dispatch<React.SetStateAction<GraphData>>
) {
  const [demoEvents, setDemoEvents] = useState<AgentEvent[]>([]);
  const [lastDemoEvent, setLastDemoEvent] = useState<AgentEvent | null>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const skillIndexRef = useRef(0);
  const cycleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    if (cycleTimerRef.current) {
      clearTimeout(cycleTimerRef.current);
      cycleTimerRef.current = null;
    }
  }, []);

  const emit = useCallback((event: AgentEvent) => {
    const timestamped = { ...event, timestamp: new Date().toISOString() };
    setDemoEvents((prev) => [...prev, timestamped]);
    setLastDemoEvent(timestamped);
  }, []);

  const runCycle = useCallback(() => {
    const skill = DEMO_SKILLS[skillIndexRef.current % DEMO_SKILLS.length];
    skillIndexRef.current++;
    const lines = skill.code.split('\n');

    const schedule = (delay: number, fn: () => void) => {
      const id = setTimeout(fn, delay);
      timersRef.current.push(id);
    };

    schedule(0, () =>
      emit({ event: 'agent_status', status: 'planning', message: `Planning: need ${skill.name} capability` })
    );

    schedule(500, () =>
      emit({ event: 'agent_status', status: 'evolving', message: `Evolving new skill: ${skill.name}` })
    );

    schedule(1000, () =>
      emit({ event: 'evolution_start', skill_name: skill.name, message: `Writing ${skill.name}...` })
    );

    lines.forEach((line, i) => {
      schedule(1000 + (i + 1) * 50, () =>
        emit({ event: 'code_stream', chunk: (i === 0 ? '' : '\n') + line, skill_name: skill.name })
      );
    });

    const codeEndTime = 1000 + (lines.length + 1) * 50;

    schedule(codeEndTime + 500, () =>
      emit({ event: 'agent_status', status: 'testing', message: `Running tests for ${skill.name}` })
    );

    schedule(codeEndTime + 1500, () =>
      emit({
        event: 'test_result',
        skill_name: skill.name,
        passed: true,
        message: `${skill.testName}: PASSED`,
        details: skill.testName,
      })
    );

    schedule(codeEndTime + 2000, () =>
      emit({ event: 'agent_status', status: 'registering', message: `Registering ${skill.name}` })
    );

    schedule(codeEndTime + 2500, () => {
      const newNode: SkillNode = {
        id: skill.id,
        name: skill.name,
        category: skill.category,
        is_core: false,
        status: 'active',
        use_count: 0,
        created_at: new Date().toISOString(),
        val: 6,
        color: CATEGORY_COLORS[skill.category] ?? CATEGORY_COLORS.default,
        description: `Auto-generated ${skill.name} skill`,
        code_content: skill.code,
      };
      const edge = { source: skill.parentId, target: skill.id };
      emit({ event: 'skill_tree_update', node: newNode, edge, message: `Registered ${skill.name}` });
      addNode(newNode, edge);
    });

    schedule(codeEndTime + 3000, () =>
      emit({ event: 'task_complete', status: 'idle', message: `${skill.name} evolution complete`, response: `Successfully created ${skill.name} skill.` })
    );

    // Schedule next cycle
    cycleTimerRef.current = setTimeout(() => runCycle(), codeEndTime + 10000);
    timersRef.current.push(cycleTimerRef.current);
  }, [emit, addNode]);

  useEffect(() => {
    if (enabled) {
      // Reset state
      setDemoEvents([]);
      setLastDemoEvent(null);
      skillIndexRef.current = 0;

      // Set initial graph with pre-populated nodes
      setGraphData({
        nodes: [...DEFAULT_GRAPH_DATA.nodes, ...DEMO_GENERATED_NODES],
        links: [...DEFAULT_GRAPH_DATA.links, ...DEMO_GENERATED_LINKS],
      });

      // Start first cycle after a brief delay
      const startTimer = setTimeout(() => runCycle(), 2000);
      timersRef.current.push(startTimer);
    } else {
      clearTimers();
      setGraphData(DEFAULT_GRAPH_DATA);
      setDemoEvents([]);
      setLastDemoEvent(null);
    }

    return () => clearTimers();
  }, [enabled, clearTimers, runCycle, setGraphData]);

  return { demoEvents, lastDemoEvent };
}
