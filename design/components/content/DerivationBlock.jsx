import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function DerivationBlock({ summaryEquation, steps, keywords = [], onCopy, onExport }) {
  return (
    <div style={{
      background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-5)', fontFamily: 'var(--font-ui)', display: 'flex', flexDirection: 'column', gap: 16,
    }}>
      <div style={{
        background: 'var(--bg-canvas-top)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
        padding: '18px 20px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 20, color: 'var(--accent-cyan)',
        fontStyle: 'italic', letterSpacing: 'var(--tracking-tight)',
      }}>{summaryEquation}</div>

      {keywords.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {keywords.map(k => (
            <span key={k} style={{
              fontSize: 'var(--text-xs)', color: 'var(--accent-violet)', border: '1px solid var(--accent-violet)',
              borderRadius: 'var(--radius-pill)', padding: '3px 9px', background: 'var(--accent-violet-tint-10)',
            }}>{k}</span>
          ))}
        </div>
      )}

      <ol style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {steps.map((s, i) => (
          <li key={i} style={{ color: 'var(--text-primary)', fontSize: 'var(--text-base)', lineHeight: 'var(--leading-relaxed)' }}>
            {s.text}
            {s.equation && (
              <div style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{s.equation}</div>
            )}
          </li>
        ))}
      </ol>

      <div style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--border-default)', paddingTop: 12 }}>
        <button onClick={onCopy} style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: '1px solid var(--border-emphasis)',
          borderRadius: 'var(--radius-md)', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', padding: '6px 12px', cursor: 'pointer',
        }}><Icon name="copy" size={13} />Copy</button>
        <button onClick={onExport} style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: '1px solid var(--border-emphasis)',
          borderRadius: 'var(--radius-md)', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', padding: '6px 12px', cursor: 'pointer',
        }}><Icon name="download" size={13} />Export</button>
      </div>
    </div>
  );
}
