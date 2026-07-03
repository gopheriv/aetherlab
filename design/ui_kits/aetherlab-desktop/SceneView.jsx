// Screens 4 & 5 — Result, Visualization + Code focus. Canvas/Video/Code pill tabs,
// phase-portrait overlay toggle, parameter dock alongside.
const codeSample = `class DampedOscillator(Scene):
    def construct(self):
        g = 9.81      # gravity
        zeta = 0.15   # damping ratio
        omega_n = 2.0 # natural frequency (rad/s)

        axes = Axes(x_range=[0, 10], y_range=[-1, 1])
        curve = axes.plot(
            lambda t: math.exp(-zeta * omega_n * t)
            * math.cos(omega_n * math.sqrt(1 - zeta**2) * t)
        )
        self.play(Create(axes), Create(curve))
`;

function SceneView({ stages, tab, onTabChange, showParams, overlay, onOverlayToggle, params, onParamChange }) {
  const { PipelineTimeline, Icon, VideoControls, ParameterRow } = window.AetherLabDesignSystem_448260;

  return (
    <div data-screen-label="04-05 Result — Visualization / Code Focus" style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-ui)' }}>
      <div style={{ padding: '16px 28px', borderBottom: '1px solid var(--border-default)' }}>
        <PipelineTimeline stages={stages} />
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 24, gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {['canvas', 'video', 'code'].map(t => (
              <button key={t} onClick={() => onTabChange(t)} style={{
                padding: '7px 16px', borderRadius: 'var(--radius-pill)', border: `1px solid ${tab === t ? 'var(--accent-cyan)' : 'var(--border-default)'}`,
                background: tab === t ? 'var(--accent-cyan-tint-10)' : 'transparent', color: tab === t ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize',
              }}>{t}</button>
            ))}
            {tab === 'canvas' && (
              <label style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <input type="checkbox" checked={overlay} onChange={e => onOverlayToggle(e.target.checked)} />
                Phase-portrait overlay
              </label>
            )}
          </div>

          <div style={{
            flex: 1, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)',
            background: 'linear-gradient(180deg, var(--bg-canvas-top), var(--bg-canvas-bottom))',
            position: 'relative', overflow: 'hidden', minHeight: 260,
          }}>
            {tab !== 'code' && (
              <React.Fragment>
                <svg width="100%" height="100%" viewBox="0 0 400 220" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0 }}>
                  <path d="M0,110 Q40,20 80,110 T160,110 T240,110 T320,110 T400,110" stroke="var(--accent-cyan)" strokeWidth="2" fill="none" />
                  {overlay && tab === 'canvas' && (
                    <ellipse cx="200" cy="110" rx="120" ry="60" stroke="var(--accent-violet)" strokeWidth="1.5" fill="none" strokeDasharray="4 4" />
                  )}
                </svg>
                {tab === 'video' && (
                  <div style={{ position: 'absolute', bottom: 14, left: 14, right: 14 }}>
                    <VideoControls playing currentTime="0:04" duration="0:12" progress={33} onSeek={() => {}} />
                  </div>
                )}
              </React.Fragment>
            )}
            {tab === 'code' && (
              <div style={{ position: 'absolute', inset: 0, padding: 18, overflow: 'auto' }}>
                <pre style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.6, color: 'var(--accent-emerald)', whiteSpace: 'pre-wrap' }}>{codeSample}</pre>
              </div>
            )}
          </div>

          {tab === 'code' && (
            <button style={{
              alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6, background: 'none',
              border: '1px solid var(--border-emphasis)', borderRadius: 'var(--radius-md)', color: 'var(--text-secondary)',
              fontSize: 'var(--text-sm)', padding: '6px 12px', cursor: 'pointer',
            }}><Icon name="download" size={13} />Export scene.py</button>
          )}
        </div>

        {showParams && (
          <div style={{
            width: 300, flex: 'none', borderLeft: '1px solid var(--border-default)', background: 'var(--surface-panel)',
            padding: 20, display: 'flex', flexDirection: 'column', gap: 18,
          }}>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>Parameters</div>
            <ParameterRow label="Gravity" value={params.g} min={0} max={20} step={0.01} unit=" m/s²" defaultValue={9.81} onChange={v => onParamChange('g', v)} />
            <ParameterRow label="Damping" value={params.zeta} min={0} max={1} step={0.01} defaultValue={0.2} onChange={v => onParamChange('zeta', v)} />
            <ParameterRow label="Frequency" value={params.omega} min={0} max={10} step={0.1} unit=" rad/s" defaultValue={2} onChange={v => onParamChange('omega', v)} />
          </div>
        )}
      </div>
    </div>
  );
}
window.SceneView = SceneView;
