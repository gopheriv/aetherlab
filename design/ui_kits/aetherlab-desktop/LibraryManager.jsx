// Screen 6 — References / Library manager: indexed sources + add folder / ingest /
// re-index and index status.
const sources = [
  { name: 'Goldstein — Classical Mechanics.pdf', pages: 638, status: 'Indexed' },
  { name: 'Taylor — Classical Mechanics.pdf', pages: 786, status: 'Indexed' },
  { name: 'Griffiths — Electrodynamics.pdf', pages: 599, status: 'Indexing…' },
];

function LibraryManager({ onAdd }) {
  const { Icon, Button, ReferenceEmptyState } = window.AetherLabDesignSystem_448260;
  const hasSources = sources.length > 0;
  return (
    <div data-screen-label="06 References / Library Manager" style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-ui)', padding: 28, gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)' }}>Library</div>
        <div style={{ flex: 1 }} />
        <Button variant="secondary" icon="folder-plus" onClick={onAdd}>Add folder</Button>
        <Button variant="secondary" icon="refresh-cw">Re-index</Button>
      </div>

      {hasSources ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          {sources.map(s => (
            <div key={s.name} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: 'var(--surface-card)', borderBottom: '1px solid var(--border-default)',
            }}>
              <Icon name="file-text" size={16} color="var(--text-tertiary)" />
              <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{s.name}</span>
              <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{s.pages}p</span>
              <span style={{
                fontSize: 'var(--text-xs)', padding: '2px 9px', borderRadius: 'var(--radius-pill)',
                color: s.status === 'Indexed' ? 'var(--accent-emerald)' : 'var(--accent-cyan)',
                border: `1px solid ${s.status === 'Indexed' ? 'var(--accent-emerald)' : 'var(--accent-cyan)'}`,
              }}>{s.status}</span>
            </div>
          ))}
        </div>
      ) : (
        <ReferenceEmptyState onAdd={onAdd} />
      )}
    </div>
  );
}
window.LibraryManager = LibraryManager;
