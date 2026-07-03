import React from 'react';
import { Icon } from '../core/Icon.jsx';

function scoreColor(score) {
  if (score >= 0.8) return 'var(--accent-emerald)';
  if (score >= 0.5) return 'var(--accent-amber)';
  return 'var(--text-tertiary)';
}

export function ReferenceCard({ source, page, score = 0, excerpt, onOpen }) {
  return (
    <div style={{
      background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 8, fontFamily: 'var(--font-ui)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name="book-open" size={14} color="var(--accent-cyan)" />
        <span style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>{source}</span>
        {page && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>p.{page}</span>}
        <span style={{
          marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: scoreColor(score),
          border: `1px solid ${scoreColor(score)}`, borderRadius: 'var(--radius-pill)', padding: '2px 8px',
        }}>{score.toFixed(2)}</span>
      </div>
      <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-normal)' }}>{excerpt}</p>
      <button onClick={onOpen} style={{
        alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
        color: 'var(--accent-cyan)', fontSize: 'var(--text-sm)', fontWeight: 500, cursor: 'pointer', padding: 0,
      }}>Open <Icon name="arrow-up-right" size={13} /></button>
    </div>
  );
}

export function ReferenceEmptyState({ onAdd }) {
  return (
    <div style={{
      border: '1px dashed var(--border-emphasis)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-8)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, fontFamily: 'var(--font-ui)', textAlign: 'center',
    }}>
      <Icon name="library" size={24} color="var(--text-tertiary)" />
      <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-base)' }}>No textbooks indexed yet</div>
      <button onClick={onAdd} style={{
        display: 'flex', alignItems: 'center', gap: 6, background: 'var(--accent-cyan)', color: 'var(--text-on-accent)',
        border: 'none', borderRadius: 'var(--radius-md)', padding: '8px 14px', fontWeight: 600, cursor: 'pointer',
      }}><Icon name="folder-plus" size={14} />Add textbooks…</button>
    </div>
  );
}
