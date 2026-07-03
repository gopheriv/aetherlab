import React from 'react';
import { Icon } from '../core/Icon.jsx';

export function NavRailItem({ icon, label, active = false, disabled = false, onClick }) {
  const [hover, setHover] = React.useState(false);

  const bg = active ? 'var(--accent-cyan-tint-10)' : hover && !disabled ? 'var(--bg-panel-2)' : 'transparent';
  const color = disabled ? 'var(--text-low)' : active ? 'var(--accent-cyan)' : 'var(--text-secondary)';

  return (
    <div
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        width: 64,
        padding: '10px 4px',
        borderRadius: 'var(--radius-md)',
        background: bg,
        color,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background var(--duration-fast) var(--ease-standard), color var(--duration-fast)',
      }}
    >
      {active && (
        <span style={{
          position: 'absolute', left: -8, top: '50%', transform: 'translateY(-50%)',
          width: 3, height: 20, borderRadius: 'var(--radius-pill)', background: 'var(--accent-cyan)',
          boxShadow: 'var(--glow-cyan)',
        }} />
      )}
      <Icon name={icon} size={18} />
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 11, fontWeight: 500, letterSpacing: 'var(--tracking-wide)' }}>{label}</span>
    </div>
  );
}
