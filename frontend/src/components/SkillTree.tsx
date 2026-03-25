import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods } from 'react-force-graph-2d';

import type { GraphData, SkillNode } from '../lib/types';

interface SkillTreeProps {
  graphData: GraphData;
  onNodeClick: (node: SkillNode) => void;
  width: number;
  height: number;
}

export default function SkillTree({ graphData, onNodeClick, width, height }: SkillTreeProps) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const prevNodeCount = useRef(graphData.nodes.length);
  const containerRef = useRef<HTMLDivElement>(null);

  const [hoveredNode, setHoveredNode] = useState<SkillNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const hasGlow = useMemo(
    () => graphData.nodes.some((n) => n.glow),
    [graphData.nodes]
  );

  useEffect(() => {
    if (graphData.nodes.length !== prevNodeCount.current && fgRef.current) {
      fgRef.current.d3ReheatSimulation();
      prevNodeCount.current = graphData.nodes.length;
    }
  }, [graphData.nodes.length]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (rect) {
      setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  }, []);

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = node.val || 8;
      const x = node.x!;
      const y = node.y!;

      if (node.glow) {
        const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 300);
        const glowRadius = radius + 6 + pulse * 4;
        const gradient = ctx.createRadialGradient(x, y, radius, x, y, glowRadius);
        gradient.addColorStop(0, node.color + '60');
        gradient.addColorStop(1, node.color + '00');
        ctx.beginPath();
        ctx.arc(x, y, glowRadius, 0, 2 * Math.PI);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = node.color + 'AA';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      ctx.font = `${10 / globalScale}px 'Space Grotesk', sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#a1a1aa';
      ctx.fillText(node.name, x, y + radius + 3);
    },
    []
  );

  const paintPointerArea = useCallback(
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const radius = (node.val || 8) + 4;
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
    },
    []
  );

  const getLinkColor = useCallback(
    (link: any) => {
      const sourceNode =
        typeof link.source === 'object'
          ? link.source
          : graphData.nodes.find((n) => n.id === link.source);
      return (sourceNode?.color ?? '#71717a') + '66';
    },
    [graphData.nodes]
  );

  const getParticleColor = useCallback(
    (link: any) => {
      const sourceNode =
        typeof link.source === 'object'
          ? link.source
          : graphData.nodes.find((n) => n.id === link.source);
      return sourceNode?.color ?? '#71717a';
    },
    [graphData.nodes]
  );

  const stats = useMemo(() => {
    const total = graphData.nodes.length;
    const generated = graphData.nodes.filter((n) => !n.is_core);
    const lastGen = generated.length > 0
      ? generated.sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0]?.name
      : null;
    return { total, generatedCount: generated.length, lastGen };
  }, [graphData.nodes]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full"
      onMouseMove={handleMouseMove}
      style={{
        backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }}
    >
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'replace'}
        nodePointerAreaPaint={paintPointerArea}
        onNodeClick={(node) => onNodeClick(node as SkillNode)}
        onNodeHover={(node) => setHoveredNode(node as SkillNode | null)}
        linkColor={getLinkColor}
        linkWidth={1.5}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={3}
        linkDirectionalParticleColor={getParticleColor}
        autoPauseRedraw={!hasGlow}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        warmupTicks={50}
        backgroundColor="transparent"
        width={width}
        height={height}
      />

      {/* Hover tooltip */}
      {hoveredNode && (
        <div
          style={{
            position: 'absolute',
            left: tooltipPos.x + 15,
            top: tooltipPos.y - 10,
            background: '#111113',
            border: '1px solid #2e2e38',
            borderRadius: '8px',
            padding: '12px 16px',
            minWidth: '220px',
            maxWidth: '300px',
            pointerEvents: 'none',
            zIndex: 1000,
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#fafafa', marginBottom: '6px' }}>
            {hoveredNode.name}
          </div>
          {hoveredNode.description && (
            <div
              style={{
                fontSize: '12px',
                color: '#a1a1aa',
                marginBottom: '8px',
                lineHeight: '1.5',
              }}
            >
              {hoveredNode.description}
            </div>
          )}
          <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#71717a', alignItems: 'center' }}>
            <span
              style={{
                background: hoveredNode.color + '20',
                color: hoveredNode.color,
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
              }}
            >
              {hoveredNode.category}
            </span>
            <span>Used {hoveredNode.use_count || 0}x</span>
            {hoveredNode.is_core ? <span>Core</span> : <span>AI-generated</span>}
          </div>
          {hoveredNode.evolution_trigger && (
            <div
              style={{
                fontSize: '11px',
                color: '#71717a',
                marginTop: '8px',
                borderTop: '1px solid #1e1e24',
                paddingTop: '8px',
              }}
            >
              Created for: &ldquo;{hoveredNode.evolution_trigger}&rdquo;
            </div>
          )}
        </div>
      )}

      {/* Stats bar */}
      <div
        className="absolute bottom-0 left-0 right-0 flex items-center justify-center gap-3 px-3 py-2"
        style={{
          background: 'linear-gradient(transparent, var(--bg-primary))',
          borderTop: '1px solid var(--border-primary)',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          color: 'var(--text-muted)',
        }}
      >
        <span>{stats.total} skills</span>
        <span style={{ color: 'var(--border-secondary)' }}>&middot;</span>
        <span>{stats.generatedCount} generated</span>
        <span style={{ color: 'var(--border-secondary)' }}>&middot;</span>
        {stats.lastGen ? (
          <span>Last: {stats.lastGen}</span>
        ) : (
          <span style={{ color: 'var(--accent-cyan)', opacity: 0.6 }}>Ready to evolve</span>
        )}
      </div>
    </div>
  );
}
