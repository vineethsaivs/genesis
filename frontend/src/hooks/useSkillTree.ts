import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import type { GraphData, SkillNode } from '../lib/types';
import { DEFAULT_GRAPH_DATA, CATEGORY_COLORS } from '../lib/types';
import { api } from '../lib/api';

export function useSkillTree() {
  const [graphData, setGraphData] = useState<GraphData>(DEFAULT_GRAPH_DATA);
  const [selectedNode, setSelectedNode] = useState<SkillNode | null>(null);
  const animationTimersRef = useRef<ReturnType<typeof setInterval>[]>([]);

  useEffect(() => {
    api.getSkillTree().then((data) => {
      if (data && data.nodes.length > 0) {
        // Ensure all nodes have required fields for the frontend
        const nodes = data.nodes.map((n) => ({
          ...n,
          status: n.status || 'active',
          use_count: n.use_count ?? 0,
          created_at: n.created_at || new Date().toISOString(),
          val: n.val || (n.is_core ? 14 : 8),
          color: n.color || CATEGORY_COLORS[n.category] || CATEGORY_COLORS.default,
        }));
        setGraphData({ nodes, links: data.links });
      }
    });

    return () => {
      animationTimersRef.current.forEach(clearInterval);
    };
  }, []);

  const addNode = useCallback(
    (node: SkillNode, edge?: { source: string; target: string }) => {
      const color = node.color || CATEGORY_COLORS[node.category] || CATEGORY_COLORS.default;
      const targetVal = node.val || 8;
      const animatedNode: SkillNode = {
        ...node,
        color,
        status: node.status || 'active',
        use_count: node.use_count ?? 0,
        created_at: node.created_at || new Date().toISOString(),
        val: 0,
        glow: true,
      };

      setGraphData((prev) => {
        // Avoid duplicate nodes
        if (prev.nodes.some((n) => n.id === animatedNode.id)) return prev;
        return {
          nodes: [...prev.nodes, animatedNode],
          links: edge ? [...prev.links, edge] : prev.links,
        };
      });

      // Animate node size over 600ms (8 steps at 75ms)
      let currentVal = 0;
      const increment = targetVal / 8;
      const timer = setInterval(() => {
        currentVal += increment;
        if (currentVal >= targetVal) {
          currentVal = targetVal;
          clearInterval(timer);
        }
        setGraphData((prev) => ({
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id === node.id ? { ...n, val: currentVal } : n
          ),
        }));
      }, 75);
      animationTimersRef.current.push(timer);

      // Remove glow after 3s
      setTimeout(() => {
        setGraphData((prev) => ({
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id === node.id ? { ...n, glow: false } : n
          ),
        }));
      }, 3000);
    },
    []
  );

  const stats = useMemo(() => {
    const totalSkills = graphData.nodes.length;
    const generatedCount = graphData.nodes.filter((n) => !n.is_core).length;
    const generated = graphData.nodes.filter((n) => !n.is_core);
    const lastEvolution =
      generated.length > 0
        ? generated.sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime()
          )[0]?.name ?? null
        : null;
    return { totalSkills, generatedCount, lastEvolution };
  }, [graphData]);

  return { graphData, setGraphData, selectedNode, setSelectedNode, addNode, stats };
}
