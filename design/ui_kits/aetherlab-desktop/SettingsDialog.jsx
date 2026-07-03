// Screen 7 — Settings dialog: provider (API key, base URL, model), render engine
// & quality, data/library paths, sensible defaults.
function SettingsDialog({ onClose }) {
  const { Icon, Button, SettingsField } = window.AetherLabDesignSystem_448260;
  const [apiKey, setApiKey] = React.useState('sk-live-aeth-83fd92');
  const [baseUrl, setBaseUrl] = React.useState('https://api.anthropic.com');
  const [model, setModel] = React.useState('claude-sonnet');
  const [engine, setEngine] = React.useState('Manim (Community)');
  const [quality, setQuality] = React.useState('Standard (1080p)');
  const [libPath, setLibPath] = React.useState('C:\\Users\\aeth\\AetherLab\\Library');
  const [outPath, setOutPath] = React.useState('C:\\Users\\aeth\\AetherLab\\Output');

  return (
    <div data-screen-label="07 Settings" style={{
      position: 'absolute', inset: 0, background: 'var(--surface-overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
    }}>
      <div style={{
        width: 480, maxHeight: '86%', overflow: 'auto', background: 'var(--bg-panel-2)', border: '1px solid var(--border-emphasis)',
        borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-popover)', fontFamily: 'var(--font-ui)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--border-default)' }}>
          <Icon name="settings" size={16} color="var(--text-secondary)" />
          <span style={{ marginLeft: 8, fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>Settings</span>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}><Icon name="x" size={16} /></button>
        </div>

        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)' }}>Provider</div>
          <SettingsField label="API Key" kind="secret" value={apiKey} onChange={setApiKey} placeholder="sk-…" />
          <SettingsField label="Base URL" kind="text" value={baseUrl} onChange={setBaseUrl} />
          <SettingsField label="Model" kind="select" value={model} options={['claude-sonnet', 'claude-opus', 'claude-haiku']} onChange={setModel} />

          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)', marginTop: 4 }}>Rendering</div>
          <SettingsField label="Render engine" kind="select" value={engine} options={['Manim (Community)', 'Manim (GL)']} onChange={setEngine} />
          <SettingsField label="Default quality" kind="select" value={quality} options={['Draft (480p)', 'Standard (1080p)', 'High (4K)']} onChange={setQuality} />

          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)', marginTop: 4 }}>Paths</div>
          <SettingsField label="Library path" kind="path" value={libPath} onBrowse={() => {}} hint="Where indexed textbooks are stored" />
          <SettingsField label="Output path" kind="path" value={outPath} onBrowse={() => {}} hint="Where rendered videos are saved" />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '14px 20px', borderTop: '1px solid var(--border-default)' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={onClose}>Save</Button>
        </div>
      </div>
    </div>
  );
}
window.SettingsDialog = SettingsDialog;
