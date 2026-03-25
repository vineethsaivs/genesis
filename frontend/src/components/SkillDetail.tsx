import { useState, useEffect, useCallback } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { X, Trash2 } from 'lucide-react';

import type { SkillNode } from '../lib/types';
import { CATEGORY_COLORS } from '../lib/types';
import { api } from '../lib/api';

interface SkillDetailProps {
  skill: SkillNode | null;
  onClose: () => void;
  onDelete: (skillId: string) => void;
}

export default function SkillDetail({ skill, onClose, onDelete }: SkillDetailProps) {
  const [fullSkill, setFullSkill] = useState<SkillNode | null>(null);

  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (skill) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [skill, handleEscape]);

  useEffect(() => {
    if (skill && !skill.code_content && !skill.is_core) {
      api.getSkill(skill.id).then((data) => {
        if (data) setFullSkill(data);
      });
    } else {
      setFullSkill(null);
    }
  }, [skill]);

  if (!skill) return null;

  const displaySkill = fullSkill ?? skill;
  const categoryColor = CATEGORY_COLORS[displaySkill.category] ?? CATEGORY_COLORS.default;
  const createdDate = new Date(displaySkill.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const handleDelete = () => {
    if (window.confirm(`Delete skill "${displaySkill.name}"? This cannot be undone.`)) {
      onDelete(displaySkill.id);
      onClose();
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50"
        style={{ background: 'rgba(0,0,0,0.5)' }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 z-50 h-full flex flex-col"
        style={{
          width: '400px',
          background: 'var(--bg-secondary)',
          borderLeft: '1px solid var(--border-primary)',
          animation: 'slide-in-right 0.3s ease-out',
        }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between p-4 shrink-0"
          style={{ borderBottom: '1px solid var(--border-primary)' }}
        >
          <div className="flex flex-col gap-2">
            <h2
              style={{
                fontSize: '20px',
                fontWeight: 700,
                color: 'var(--text-primary)',
              }}
            >
              {displaySkill.name}
            </h2>
            <span
              className="inline-flex px-2 py-0.5 rounded-full text-xs"
              style={{
                background: categoryColor + '20',
                color: categoryColor,
                border: `1px solid ${categoryColor}40`,
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                width: 'fit-content',
              }}
            >
              {displaySkill.category}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded cursor-pointer transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <X size={18} />
          </button>
        </div>

        {/* Stats */}
        <div
          className="grid grid-cols-3 gap-3 p-4 shrink-0"
          style={{ borderBottom: '1px solid var(--border-primary)' }}
        >
          {[
            { label: 'Created', value: createdDate },
            { label: 'Uses', value: String(displaySkill.use_count) },
            { label: 'Status', value: displaySkill.status },
          ].map((stat) => (
            <div key={stat.label}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '2px',
                }}
              >
                {stat.label}
              </div>
              <div
                style={{
                  fontSize: '13px',
                  color: 'var(--text-primary)',
                }}
              >
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Description */}
        {displaySkill.description && (
          <div className="p-4 shrink-0" style={{ borderBottom: '1px solid var(--border-primary)' }}>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: '6px',
              }}
            >
              Description
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              {displaySkill.description}
            </p>
          </div>
        )}

        {displaySkill.evolution_trigger && (
          <div className="p-4 shrink-0" style={{ borderBottom: '1px solid var(--border-primary)' }}>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: '6px',
              }}
            >
              Evolution Trigger
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5', fontStyle: 'italic' }}>
              &ldquo;{displaySkill.evolution_trigger}&rdquo;
            </p>
          </div>
        )}

        {/* Source code (generated skills only) */}
        {!displaySkill.is_core && displaySkill.code_content && (
          <div className="flex-1 flex flex-col min-h-0 p-4">
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: '6px',
              }}
            >
              Source Code
            </div>
            <div className="flex-1 overflow-y-auto rounded" style={{ border: '1px solid var(--border-primary)' }}>
              <SyntaxHighlighter
                language="python"
                style={oneDark}
                showLineNumbers
                customStyle={{
                  margin: 0,
                  padding: '12px',
                  background: '#0d1117',
                  fontSize: '11px',
                  lineHeight: '1.5',
                  fontFamily: 'var(--font-mono)',
                }}
                codeTagProps={{ style: { fontFamily: 'var(--font-mono)' } }}
              >
                {displaySkill.code_content}
              </SyntaxHighlighter>
            </div>
          </div>
        )}

        {/* Core skill info */}
        {displaySkill.is_core && (
          <div className="flex-1 flex items-center justify-center">
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>
              Core skill — not editable
            </span>
          </div>
        )}

        {/* Delete button (generated skills only) */}
        {!displaySkill.is_core && (
          <div className="p-4 shrink-0" style={{ borderTop: '1px solid var(--border-primary)' }}>
            <button
              onClick={handleDelete}
              className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded text-sm cursor-pointer transition-colors"
              style={{
                background: 'transparent',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#ef4444',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <Trash2 size={14} />
              Delete Skill
            </button>
          </div>
        )}
      </div>
    </>
  );
}
