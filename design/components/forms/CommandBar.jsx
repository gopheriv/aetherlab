import React from 'react';
import { Icon } from '../core/Icon.jsx';
import { Button } from '../core/Button.jsx';

const barBox = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  background: 'var(--surface-panel-raised)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-lg)',
  padding: '8px 10px',
  boxShadow: 'var(--shadow-panel)',
};

export function CommandBar({
  value = '',
  onChange,
  placeholder = 'Describe a physics or math problem…  (Ctrl+Enter to run)',
  busy = false,
  quality = 'standard',
  onQualityChange,
  examples = ['Damped harmonic oscillator', 'Projectile motion with drag', 'Simple pendulum phase portrait'],
  onRun,
  onCancel,
}) {
  const [focused, setFocused] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);

  return (
    <div style={barBox}>
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setMenuOpen(v => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none',
            color: 'var(--text-secondary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', cursor: 'pointer', padding: '6px 8px',
          }}
        >
          <Icon name="lightbulb" size={14} />
          Examples
          <Icon name="chevron-down" size={12} />
        </button>
        {menuOpen && (
          <div style={{
            position: 'absolute', bottom: '110%', left: 0, minWidth: 260,
            background: 'var(--bg-panel-2)', border: '1px solid var(--border-emphasis)', borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-popover)', padding: 6, zIndex: 10,
          }}>
            {examples.map(ex => (
              <div key={ex}
                onClick={() => { onChange && onChange(ex); setMenuOpen(false); }}
                style={{ padding: '8px 10px', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-panel-1)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >{ex}</div>
            ))}
          </div>
        )}
      </div>

      <div style={{ width: 1, alignSelf: 'stretch', background: 'var(--border-default)' }} />

      <input
        value={value}
        disabled={busy}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={e => onChange && onChange(e.target.value)}
        style={{
          flex: 1, background: 'transparent', border: 'none', outline: 'none',
          color: 'var(--text-primary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)',
          boxShadow: focused ? 'none' : 'none',
        }}
      />

      <select
        value={quality}
        onChange={e => onQualityChange && onQualityChange(e.target.value)}
        style={{
          background: 'var(--bg-panel-1)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)', padding: '8px 10px', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
        }}
      >
        <option value="draft">Draft</option>
        <option value="standard">Standard</option>
        <option value="high">High</option>
      </select>

      {busy ? (
        <Button variant="danger" icon="square" onClick={onCancel}>Cancel</Button>
      ) : (
        <Button variant="primary" icon="play" onClick={onRun}>Run</Button>
      )}
    </div>
  );
}
