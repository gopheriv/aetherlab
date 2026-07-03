const { Rail, TitleBar, EmptyState, RunningView, DerivationView, SceneView, LibraryManager, SettingsDialog, HistoryView } = window;

const STAGE_LABELS = ['Solve', 'RAG', 'Scene', 'Render'];

function App() {
  const { CommandBar, Toast } = window.AetherLabDesignSystem_448260;

  const [prompt, setPrompt] = React.useState('');
  const [quality, setQuality] = React.useState('standard');
  const [running, setRunning] = React.useState(false);
  const [hasResult, setHasResult] = React.useState(false);
  const [stageIndex, setStageIndex] = React.useState(-1);
  const [rail, setRail] = React.useState('solve');
  const [sceneTab, setSceneTab] = React.useState('canvas');
  const [showParams, setShowParams] = React.useState(false);
  const [overlay, setOverlay] = React.useState(true);
  const [params, setParams] = React.useState({ g: 9.81, zeta: 0.15, omega: 2.0 });
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [error, setError] = React.useState(null);
  const timerRef = React.useRef(null);

  const stages = STAGE_LABELS.map((label, i) => ({
    label,
    status: i < stageIndex ? 'complete' : i === stageIndex ? 'active' : 'pending',
    elapsed: i < stageIndex ? `${(1 + i * 0.6).toFixed(1)}s` : undefined,
  }));

  function run() {
    if (!prompt.trim()) return;
    setError(null);
    setRunning(true);
    setHasResult(false);
    setStageIndex(0);
    let i = 0;
    timerRef.current = setInterval(() => {
      i += 1;
      if (i >= STAGE_LABELS.length) {
        clearInterval(timerRef.current);
        setStageIndex(STAGE_LABELS.length);
        setRunning(false);
        setHasResult(true);
        setRail('solve');
      } else {
        setStageIndex(i);
      }
    }, 1100);
  }

  function cancel() {
    clearInterval(timerRef.current);
    setRunning(false);
    setStageIndex(-1);
    setError('Run cancelled by user.');
  }

  React.useEffect(() => () => clearInterval(timerRef.current), []);

  let workspace;
  if (running) {
    workspace = <RunningView stages={stages} onCancel={cancel} />;
  } else if (!hasResult) {
    workspace = <EmptyState onOpenSettings={() => setSettingsOpen(true)} onOpenLibrary={() => setRail('refs')} onPickExample={setPrompt} />;
  } else if (rail === 'refs') {
    workspace = <LibraryManager onAdd={() => {}} />;
  } else if (rail === 'history') {
    workspace = <HistoryView onRerun={setPrompt} onClear={() => {}} />;
  } else if (rail === 'scene') {
    workspace = (
      <SceneView
        stages={stages} tab={sceneTab} onTabChange={setSceneTab}
        showParams={showParams} overlay={overlay} onOverlayToggle={setOverlay}
        params={params} onParamChange={(k, v) => setParams(p => ({ ...p, [k]: v }))}
      />
    );
  } else {
    workspace = <DerivationView stages={stages} />;
  }

  return (
    <div style={{
      width: 1500, height: 950, background: 'var(--surface-app)', display: 'flex', flexDirection: 'column',
      borderRadius: 10, overflow: 'hidden', position: 'relative', boxShadow: '0 30px 80px rgba(0,0,0,0.6)',
    }}>
      <TitleBar onOpenSettings={() => setSettingsOpen(true)} />
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <Rail screen={rail} onSelect={id => { setRail(id); if (id === 'params') setShowParams(v => !v); }} hasResult={hasResult} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {error && (
            <div style={{ padding: '10px 20px' }}>
              <Toast kind="error" message={error} onDismiss={() => setError(null)} />
            </div>
          )}
          {workspace}
          <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-default)', background: 'var(--bg-panel-1)' }}>
            <CommandBar value={prompt} onChange={setPrompt} quality={quality} onQualityChange={setQuality} busy={running} onRun={run} onCancel={cancel} />
          </div>
        </div>
      </div>
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
window.App = App;
