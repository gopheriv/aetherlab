import React from 'react';
import { Icon } from '../core/Icon.jsx';

const statusColor = {
  pending: 'var(--state-pending)',
  active: 'var(--state-active)',
  complete: 'var(--state-complete)',
  error: 'var(--state-error)',
};

function Node({ stage, isLast, onCancel }) {
  const color = statusColor[stage.status];
  return (
    <React.Fragment>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, minWidth: 96 }}>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          border: `2px solid ${color}`,
          background: stage.status === 'complete' ? color : 'var(--bg-panel-1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: stage.status === 'active' ? 'var(--glow-cyan)' : 'none',
          animation: stage.status === 'active' ? 'aeth-pulse 1.6s var(--ease-standard) infinite' : 'none',
        }}>
          {stage.status === 'complete' && <Icon name="check" size={16} color="var(--text-on-accent)" />}
          {stage.status === 'error' && <Icon name="x" size={16} color={color} />}
          {stage.status === 'active' && <Icon name="loader-2" size={16} color={color} style={{ animation: 'aeth-spin 1s linear infinite' }} />}
        </div>
        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 12.5, fontWeight: 600, color: stage.status === 'pending' ? 'var(--text-low)' : 'var(--text-primary)' }}>
          {stage.label}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-tertiary)', height: 14 }}>
          {stage.elapsed || ''}
        </div>
        {stage.status === 'active' && onCancel && (
          <button onClick={onCancel} style={{
            fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--accent-rose)',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          }}>Cancel</button>
        )}
      </div>
      {!isLast && (
        <div style={{ flex: 1, height: 2, background: stage.status === 'complete' ? 'var(--state-complete)' : 'var(--border-default)', marginTop: 16 }} />
      )}
    </React.Fragment>
  );
}

export function PipelineTimeline({ stages, onCancel }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', width: '100%' }}>
      <style>{`
        @keyframes aeth-pulse { 0%,100% { box-shadow: 0 0 0 0 var(--accent-cyan-glow); } 50% { box-shadow: 0 0 0 6px transparent; } }
        @keyframes aeth-spin { to { transform: rotate(360deg); } }
      `}</style>
      {stages.map((s, i) => (
        <Node key={s.label} stage={s} isLast={i === stages.length - 1} onCancel={onCancel} />
      ))}
    </div>
  );
}
