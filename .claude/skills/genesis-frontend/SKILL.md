---
name: genesis-frontend
description: Use when working on GENESIS React frontend (skill tree, code viewer, agent feed)
---

## react-force-graph-2d Key Props
- graphData: {nodes: [{id, name, val, color}], links: [{source, target}]}
- nodeCanvasObject: custom canvas drawing function
- onNodeClick, onNodeHover
- cooldownTicks: 100 (stop simulation after settling)
- d3AlphaDecay: 0.02 (slower = smoother animation)

## WebSocket Events to Handle
- agent_status → update AgentFeed
- code_stream → append to CodeViewer
- skill_tree_update → add node to graph, trigger glow animation
- test_result → show in CodeViewer
- task_complete → show response in ChatPanel

## Design Tokens
- Background: #09090b
- Card border: #1a1a2e
- Cyan accent: #06b6d4
- Amber accent: #f59e0b
- Font mono: JetBrains Mono