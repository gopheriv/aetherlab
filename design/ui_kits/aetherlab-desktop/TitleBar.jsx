function TitleBar({ onOpenSettings }) {
  const { Icon } = window.AetherLabDesignSystem_448260;
  return (
    <div style={{
      height: 44, flex: 'none', display: 'flex', alignItems: 'center', gap: 10, padding: '0 16px',
      background: 'var(--bg-deepest)', borderBottom: '1px solid var(--border-default)', fontFamily: 'var(--font-ui)',
    }}>
      <Icon name="atom" size={16} color="var(--accent-cyan)" />
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: 'var(--tracking-wide)' }}>AetherLab</span>
      <div style={{ flex: 1 }} />
      <button onClick={onOpenSettings} title="Settings" style={{
        background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: 6, display: 'flex',
      }}><Icon name="settings" size={16} /></button>
    </div>
  );
}
window.TitleBar = TitleBar;
