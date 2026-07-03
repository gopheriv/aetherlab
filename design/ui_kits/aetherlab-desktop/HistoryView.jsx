// Screen 8 — History: past runs (prompt, time, status, refs count), click to
// re-run, clear.
const runs = [
  { prompt: 'Damped harmonic oscillator with ζ = 0.15', time: '2 min ago', status: 'complete', refs: 3 },
  { prompt: 'Projectile motion with quadratic drag', time: '1 hour ago', status: 'complete', refs: 2 },
  { prompt: 'Simple pendulum phase portrait', time: 'Yesterday', status: 'error', refs: 0 },
  { prompt: 'Coupled oscillators, normal modes', time: '2 days ago', status: 'complete', refs: 4 },
];

function HistoryView({ onRerun, onClear }) {
  const { Icon, Button } = window.AetherLabDesignSystem_448260;
  return (
    <div data-screen-label="08 History" style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-ui)', padding: 28, gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)' }}>History</div>
        <div style={{ flex: 1 }} />
        <Button variant="ghost" icon="trash-2" onClick={onClear}>Clear</Button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        {runs.map((r, i) => (
          <div key={i} onClick={() => onRerun(r.prompt)} style={{
            display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: 'var(--surface-card)',
            borderBottom: '1px solid var(--border-default)', cursor: 'pointer',
          }}>
            <Icon name={r.status === 'complete' ? 'check-circle-2' : 'x-circle'} size={16} color={r.status === 'complete' ? 'var(--accent-emerald)' : 'var(--accent-rose)'} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>{r.prompt}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{r.time} · {r.refs} refs</div>
            </div>
            <Icon name="rotate-cw" size={14} color="var(--text-tertiary)" />
          </div>
        ))}
      </div>
    </div>
  );
}
window.HistoryView = HistoryView;
