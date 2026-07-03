// Persistent left icon rail — pure navigation, each item maps 1:1 to
// what the single workspace shows. No item ever silently acts elsewhere.
function Rail({ screen, onSelect, hasResult }) {
  const { NavRailItem } = window.AetherLabDesignSystem_448260;
  const items = [
    { id: 'solve', icon: 'sigma', label: 'Solve' },
    { id: 'refs', icon: 'book-open', label: 'Refs' },
    { id: 'scene', icon: 'clapperboard', label: 'Scene' },
    { id: 'params', icon: 'sliders-horizontal', label: 'Params', disabled: !hasResult },
    { id: 'history', icon: 'history', label: 'History' },
  ];
  return (
    <div style={{
      width: 84, flex: 'none', background: 'var(--bg-panel-1)', borderRight: '1px solid var(--border-default)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, paddingTop: 16,
    }}>
      {items.map(it => (
        <NavRailItem key={it.id} icon={it.icon} label={it.label} active={screen === it.id} disabled={it.disabled}
          onClick={() => onSelect(it.id)} />
      ))}
    </div>
  );
}
window.Rail = Rail;
