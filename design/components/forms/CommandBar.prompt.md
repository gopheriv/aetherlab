`CommandBar` is the bottom-of-window primary input — examples menu, prompt field, quality selector, Run/Cancel. Swaps Run→Cancel while `busy`.

```jsx
<CommandBar value={prompt} onChange={setPrompt} quality="standard" onRun={run} busy={isRunning} onCancel={cancel} />
```

Keyboard: Run maps to Ctrl+Enter, wire that at the page level. Examples dropdown opens upward (bar lives at the bottom of the window).
