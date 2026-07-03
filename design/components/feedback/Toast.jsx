import React from 'react';
import { Icon } from '../core/Icon.jsx';

const kindMap = {
  error: { color: 'var(--accent-rose)', bg: 'var(--accent-rose-tint-10)', icon: 'alert-triangle' },
  warning: { color: 'var(--accent-amber)', bg: 'var(--accent-amber-tint-10)', icon: 'alert-circle' },
  success: { color: 'var(--accent-emerald)', bg: 'var(--accent-emerald-tint-10)', icon: 'check-circle-2' },
  info: { color: 'var(--accent-cyan)', bg: 'var(--accent-cyan-tint-10)', icon: 'info' },
};

export function Toast({ kind = 'error', message, detail, onDismiss, onDetails }) {
  const k = kindMap[kind];
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10, background: k.bg, border: `1px solid ${k.color}`,
      borderRadius: 'var(--radius-md)', padding: '10px 12px', fontFamily: 'var(--font-ui)',
    }}>
      <Icon name={k.icon} size={16} color={k.color} style={{ marginTop: 1 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 500 }}>{message}</div>
        {detail && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 2 }}>{detail}</div>}
        {onDetails && (
          <button onClick={onDetails} style={{ background: 'none', border: 'none', color: k.color, fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer', padding: '4px 0 0' }}>Details</button>
        )}
      </div>
      {onDismiss && (
        <button onClick={onDismiss} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', padding: 2 }}>
          <Icon name="x" size={14} />
        </button>
      )}
    </div>
  );
}
