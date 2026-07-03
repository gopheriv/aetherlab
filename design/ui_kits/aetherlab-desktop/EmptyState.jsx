// Screen 1 — Empty / first-run: no API key, no library. Clear CTAs.
function EmptyState({ onOpenSettings, onOpenLibrary, onPickExample }) {
  const { Icon, Button } = window.AetherLabDesignSystem_448260;
  const examples = [
    'Damped harmonic oscillator with ζ = 0.15',
    'Projectile motion with quadratic drag',
    'Simple pendulum phase portrait',
  ];
  return (
    <div data-screen-label="01 Empty / First-Run" style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24,
      fontFamily: 'var(--font-ui)', padding: 40, textAlign: 'center',
    }}>
      <Icon name="atom" size={40} color="var(--accent-cyan)" />
      <div>
        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>Describe a problem to begin</div>
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--text-secondary)', marginTop: 8 }}>
          Type a physics or math prompt below, or start from an example.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 640 }}>
        {examples.map(ex => (
          <button key={ex} onClick={() => onPickExample(ex)} style={{
            background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
            color: 'var(--text-primary)', fontSize: 'var(--text-sm)', padding: '10px 16px', cursor: 'pointer',
          }}>{ex}</button>
        ))}
      </div>

      <div style={{
        display: 'flex', gap: 24, marginTop: 12, padding: '14px 20px', border: '1px dashed var(--border-emphasis)',
        borderRadius: 'var(--radius-lg)', background: 'var(--surface-panel)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon name="key-round" size={16} color="var(--accent-amber)" />
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>No API key configured</span>
          <Button variant="ghost" size="sm" onClick={onOpenSettings}>Open Settings</Button>
        </div>
        <div style={{ width: 1, background: 'var(--border-default)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon name="library" size={16} color="var(--accent-amber)" />
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>No textbooks indexed</span>
          <Button variant="ghost" size="sm" onClick={onOpenLibrary}>Add textbooks</Button>
        </div>
      </div>
    </div>
  );
}
window.EmptyState = EmptyState;
