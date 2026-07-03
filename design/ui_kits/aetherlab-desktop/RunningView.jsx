// Screen 2 — Prompt entered, pipeline running. Timeline mid-flight (Scene active),
// cancel control, live status, loading state in the workspace.
function RunningView({ stages, onCancel }) {
  const { PipelineTimeline, Icon } = window.AetherLabDesignSystem_448260;
  const activeStage = stages.find(s => s.status === 'active');
  return (
    <div data-screen-label="02 Pipeline Running" style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-ui)' }}>
      <div style={{ padding: '20px 28px', borderBottom: '1px solid var(--border-default)' }}>
        <PipelineTimeline stages={stages} onCancel={onCancel} />
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{ position: 'relative', width: 88, height: 88 }}>
          {[0, 1, 2].map(i => (
            <span key={i} style={{
              position: 'absolute', inset: i * 14, borderRadius: '50%', border: '2px solid var(--accent-cyan)',
              opacity: 0.35 + i * 0.15, animation: `aeth-ring 1.8s var(--ease-standard) ${i * 0.2}s infinite`,
            }} />
          ))}
          <style>{`@keyframes aeth-ring { 0%,100% { transform: scale(0.9); opacity: 0.25; } 50% { transform: scale(1.05); opacity: 0.7; } }`}</style>
        </div>
        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>
          {activeStage ? `Running ${activeStage.label}…` : 'Working…'}
        </div>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          generating Manim scene from derivation
        </div>
      </div>
    </div>
  );
}
window.RunningView = RunningView;
