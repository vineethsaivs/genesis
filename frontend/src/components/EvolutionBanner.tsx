import { Sparkles, CircleCheck } from 'lucide-react';

import type { EvolutionPhase } from '../lib/types';
import { EVOLUTION_PHASES } from '../lib/types';

interface EvolutionBannerProps {
  skillName: string;
  currentPhase: EvolutionPhase;
  visible: boolean;
}

const PHASE_LABELS: Record<EvolutionPhase, string> = {
  analyzing: 'Analyzing',
  writing: 'Writing Code',
  testing: 'Testing',
  registering: 'Registering',
};

export default function EvolutionBanner({ skillName, currentPhase, visible }: EvolutionBannerProps) {
  const currentIndex = EVOLUTION_PHASES.indexOf(currentPhase);

  return (
    <div
      style={{
        transition: 'opacity 300ms ease, transform 300ms ease',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(-12px)',
        pointerEvents: visible ? 'auto' : 'none',
      }}
    >
      {/* Shimmer border wrapper */}
      <div
        style={{
          background: 'linear-gradient(90deg, var(--border-primary), var(--accent-cyan), var(--accent-purple), var(--border-primary))',
          backgroundSize: '200% 100%',
          animation: 'shimmer 3s linear infinite',
          padding: '1px',
        }}
      >
        <div
          className="flex items-center justify-between px-4 py-2"
          style={{ background: 'var(--bg-secondary)' }}
        >
          <div className="flex items-center gap-2">
            <Sparkles size={14} style={{ color: 'var(--accent-cyan)' }} />
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                color: 'var(--text-primary)',
              }}
            >
              Evolving: <strong>{skillName}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2">
            {EVOLUTION_PHASES.map((phase, i) => {
              const isComplete = i < currentIndex;
              const isActive = i === currentIndex;

              return (
                <div
                  key={phase}
                  className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11px',
                    background: isComplete
                      ? 'rgba(16,185,129,0.2)'
                      : isActive
                        ? 'rgba(6,182,212,0.2)'
                        : 'transparent',
                    border: `1px solid ${
                      isComplete
                        ? 'rgba(16,185,129,0.3)'
                        : isActive
                          ? 'rgba(6,182,212,0.3)'
                          : 'var(--border-secondary)'
                    }`,
                    color: isComplete
                      ? '#10b981'
                      : isActive
                        ? '#06b6d4'
                        : 'var(--text-muted)',
                  }}
                >
                  {isComplete ? (
                    <CircleCheck size={10} />
                  ) : isActive ? (
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full"
                      style={{
                        background: '#06b6d4',
                        animation: 'blink 1s ease-in-out infinite',
                      }}
                    />
                  ) : null}
                  {PHASE_LABELS[phase]}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
