`SettingsField` covers all four Settings-dialog input kinds behind one API: `text`, `select` (dropdown), `path` (read-only + Browse), `secret` (masked + reveal toggle).

```jsx
<SettingsField label="API Key" kind="secret" value={key} onChange={setKey} placeholder="sk-…" />
<SettingsField label="Render engine" kind="select" value={engine} options={['Manim (Community)', 'Manim (GL)']} onChange={setEngine} />
<SettingsField label="Library path" kind="path" value={path} onBrowse={openDialog} />
```

`hint` renders a low-emphasis helper line below the control (defaults, format notes).
