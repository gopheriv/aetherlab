import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function ParameterRow({ label, value, min, max, step = 0.01, unit = '', defaultValue, onChange }) {
  const pct = ((value - min) / (max - min)) * 100;
  const changed = defaultValue !== undefined && value !== defaultValue;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: 'var(--font-ui)' }}>
      <div style={{ width: 84, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{label}</div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={e => onChange && onChange(parseFloat(e.target.value))}
        style={{
          flex: 1, height: 4, borderRadius: 'var(--radius-pill)', appearance: 'none',
          background: `linear-gradient(90deg, var(--accent-cyan) ${pct}%, var(--border-default) ${pct}%)`,
          outline: 'none', cursor: 'pointer',
        }}
      />
      <div style={{
        width: 74, textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)',
        color: 'var(--text-primary)', background: 'var(--surface-input)', border: '1px solid var(--border-default)',
        borderRadius: 'var(--radius-sm)', padding: '3px 6px',
      }}>{value}{unit}</div>
      <button
        onClick={() => defaultValue !== undefined && onChange && onChange(defaultValue)}
        disabled={!changed}
        title="Reset"
        style={{
          background: 'none', border: 'none', cursor: changed ? 'pointer' : 'default',
          color: changed ? 'var(--text-secondary)' : 'var(--text-low)', padding: 4,
        }}
      >
        <Icon name="rotate-ccw" size={14} />
      </button>
    </div>
  );
}
