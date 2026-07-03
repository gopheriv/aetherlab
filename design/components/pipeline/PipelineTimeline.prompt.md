`PipelineTimeline` is the hero component — a living Solve → RAG → Scene → Render timeline with per-stage status, elapsed time, and a cancel affordance on the active node.

```jsx
<PipelineTimeline
  stages={[
    { label: 'Solve', status: 'complete', elapsed: '1.2s' },
    { label: 'RAG', status: 'complete', elapsed: '0.8s' },
    { label: 'Scene', status: 'active', elapsed: '4.1s' },
    { label: 'Render', status: 'pending' },
  ]}
  onCancel={() => {}}
/>
```

Status colors: pending = text-low, active = cyan (pulsing glow + spinner + inline Cancel), complete = emerald check, error = rose x. Connecting line fills emerald once the stage before it completes.
