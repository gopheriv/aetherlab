// Screen 3 — Result, Derivation focus: typeset summary + steps, keyword chips,
// references list beside the derivation.
function DerivationView({ stages }) {
  const { PipelineTimeline, DerivationBlock, ReferenceCard } = window.AetherLabDesignSystem_448260;
  return (
    <div data-screen-label="03 Result — Derivation Focus" style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-ui)', overflow: 'auto' }}>
      <div style={{ padding: '16px 28px', borderBottom: '1px solid var(--border-default)' }}>
        <PipelineTimeline stages={stages} />
      </div>
      <div style={{ display: 'flex', gap: 24, padding: 28, flex: 1 }}>
        <div style={{ flex: 1.4 }}>
          <DerivationBlock
            summaryEquation={"x(t) = A e^(-\u03B6\u03C9\u2099t) cos(\u03C9d t + \u03C6)"}
            keywords={['damped oscillator', '2nd-order ODE', 'underdamped']}
            steps={[
              { text: "Start from Newton's second law for the mass–spring–damper system.", equation: "m x'' + c x' + k x = 0" },
              { text: 'Divide through by mass and define natural frequency \u03C9\u2099 and damping ratio \u03B6.', equation: "x'' + 2\u03B6\u03C9\u2099 x' + \u03C9\u2099\u00B2 x = 0" },
              { text: 'Solve the characteristic equation; for \u03B6 < 1 the roots are complex, giving oscillatory decay.' },
              { text: 'Apply initial conditions x(0) = A, x\u2032(0) = 0 to fix the phase \u03C6.' },
            ]}
          />
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>References</div>
          <ReferenceCard source="Goldstein — Classical Mechanics" page="87" score={0.92} excerpt="The equation of motion for a damped harmonic oscillator follows directly from Newton's second law." />
          <ReferenceCard source="Taylor — Classical Mechanics" page="154" score={0.61} excerpt="Underdamped, critically damped, and overdamped regimes are distinguished by the discriminant sign." />
        </div>
      </div>
    </div>
  );
}
window.DerivationView = DerivationView;
