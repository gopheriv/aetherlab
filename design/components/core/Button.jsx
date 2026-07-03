import React from 'react';
import { Icon } from './Icon.jsx';

const buttonBase = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  fontFamily: 'var(--font-ui)',
  fontWeight: 600,
  border: '1px solid transparent',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  transition: 'background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast), color var(--duration-fast)',
  whiteSpace: 'nowrap',
};

const sizes = {
  sm: { padding: '6px 12px', fontSize: 'var(--text-sm)' },
  md: { padding: '9px 16px', fontSize: 'var(--text-base)' },
};

function variantStyle(variant, disabled) {
  if (disabled) {
    return { background: 'var(--bg-panel-2)', color: 'var(--text-low)', borderColor: 'var(--border-default)', cursor: 'not-allowed' };
  }
  switch (variant) {
    case 'primary':
      return { background: 'var(--accent-cyan)', color: 'var(--text-on-accent)', borderColor: 'var(--accent-cyan)' };
    case 'danger':
      return { background: 'transparent', color: 'var(--accent-rose)', borderColor: 'var(--accent-rose)' };
    case 'ghost':
      return { background: 'transparent', color: 'var(--text-secondary)', borderColor: 'transparent' };
    default:
      return { background: 'var(--bg-panel-2)', color: 'var(--text-primary)', borderColor: 'var(--border-emphasis)' };
  }
}

export function Button({ children, variant = 'secondary', size = 'md', icon, disabled = false, onClick }) {
  const [hover, setHover] = React.useState(false);
  const style = { ...buttonBase, ...sizes[size], ...variantStyle(variant, disabled) };

  if (!disabled && hover) {
    if (variant === 'primary') style.background = 'var(--accent-cyan-hover)';
    else if (variant === 'danger') style.background = 'var(--accent-rose-tint-10)';
    else if (variant === 'ghost') style.color = 'var(--text-primary)';
    else style.borderColor = 'var(--accent-cyan)';
  }

  return (
    <button
      style={style}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {icon && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}
