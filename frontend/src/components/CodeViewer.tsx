import { useRef, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FileCode, Dna, CircleCheck, CircleX } from 'lucide-react';

import type { TestResult } from '../lib/types';

interface CodeViewerProps {
  code: string | null;
  skillName: string | null;
  isStreaming: boolean;
  testResults: TestResult[];
}

export default function CodeViewer({ code, skillName, isStreaming, testResults }: CodeViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [code]);

  if (code === null) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-2"
        style={{ color: 'var(--text-muted)' }}
      >
        <Dna size={28} strokeWidth={1.5} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
          No active evolution
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
          Skills appear here as they&apos;re generated
        </span>
      </div>
    );
  }

  const displayCode = isStreaming ? code + '█' : code;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 shrink-0"
        style={{
          borderBottom: '1px solid var(--border-primary)',
        }}
      >
        <FileCode size={14} style={{ color: 'var(--accent-cyan)' }} />
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--text-primary)',
          }}
        >
          {skillName ?? 'unknown'}.py
        </span>
        {isStreaming && (
          <span
            className="w-2 h-2 rounded-full ml-auto"
            style={{
              background: 'var(--accent-green)',
              animation: 'blink 1s ease-in-out infinite',
            }}
          />
        )}
      </div>

      {/* Code area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0">
        <SyntaxHighlighter
          language="python"
          style={oneDark}
          showLineNumbers
          customStyle={{
            margin: 0,
            padding: '12px',
            background: '#0d1117',
            fontSize: '12px',
            lineHeight: '1.6',
            fontFamily: 'var(--font-mono)',
            minHeight: '100%',
          }}
          codeTagProps={{
            style: { fontFamily: 'var(--font-mono)' },
          }}
        >
          {displayCode}
        </SyntaxHighlighter>
      </div>

      {/* Test results */}
      {testResults.length > 0 && (
        <div
          className="shrink-0 px-3 py-2 space-y-1"
          style={{ borderTop: '1px solid var(--border-primary)' }}
        >
          {testResults.map((result, i) => (
            <div
              key={i}
              className="flex items-center gap-2"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
              }}
            >
              {result.passed ? (
                <CircleCheck size={12} style={{ color: '#10b981' }} />
              ) : (
                <CircleX size={12} style={{ color: '#ef4444' }} />
              )}
              <span style={{ color: 'var(--text-secondary)' }}>{result.name}</span>
              <span
                style={{
                  color: result.passed ? '#10b981' : '#ef4444',
                  marginLeft: 'auto',
                }}
              >
                {result.passed ? 'PASS' : 'FAIL'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
