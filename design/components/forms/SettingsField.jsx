import React from 'react';
import { Icon } from '../core/Icon.jsx';

const inputBox = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--surface-input)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
  color: 'var(--text-primary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-base)', padding: '9px 12px',
  outline: 'none',
};

export function SettingsField({ label, kind = 'text', value, options = [], placeholder, hint, onChange, onBrowse }) {
  const [show, setShow] = React.useState(false);
  const [focused, setFocused] = React.useState(false);
  const boxStyle = { ...inputBox, borderColor: focused ? 'var(--accent-cyan)' : 'var(--border-default)' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-secondary)' }}>{label}</label>

      {kind === 'select' && (
        <select value={value} onChange={e => onChange && onChange(e.target.value)}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={boxStyle}>
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      )}

      {kind === 'path' && (
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={value} placeholder={placeholder} readOnly style={{ ...boxStyle, flex: 1, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }} />
          <button onClick={onBrowse} style={{
            display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-panel-2)', border: '1px solid var(--border-emphasis)',
            borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', padding: '0 12px', cursor: 'pointer', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
          }}><Icon name="folder-open" size={14} />Browse</button>
        </div>
      )}

      {kind === 'secret' && (
        <div style={{ position: 'relative' }}>
          <input
            type={show ? 'text' : 'password'} value={value} placeholder={placeholder}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            onChange={e => onChange && onChange(e.target.value)}
            style={{ ...boxStyle, paddingRight: 36, fontFamily: 'var(--font-mono)' }}
          />
          <button onClick={() => setShow(s => !s)} style={{
            position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', padding: 4,
          }}><Icon name={show ? 'eye-off' : 'eye'} size={14} /></button>
        </div>
      )}

      {kind === 'text' && (
        <input value={value} placeholder={placeholder}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          onChange={e => onChange && onChange(e.target.value)} style={boxStyle} />
      )}

      {hint && <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>{hint}</div>}
    </div>
  );
}
