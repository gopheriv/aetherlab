`Toast` is the inline, dismissible banner replacing the old scattered status bar / error banner — used for pipeline errors, warnings, and confirmations, anchored at the top of the workspace.

```jsx
<Toast kind="error" message="Render failed: Manim exited with code 1" detail="ffmpeg not found on PATH" onDetails={openLog} onDismiss={clear} />
```

`kind`: error (rose), warning (amber), success (emerald), info (cyan) — tinted background + matching border, never a solid fill (keeps the dark panel legible behind it).
