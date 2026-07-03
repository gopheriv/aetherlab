`ParameterRow` is one slider in the parameter dock — label, rail, live monospace readout, reset-to-default.

```jsx
<ParameterRow label="Gravity" value={9.81} min={0} max={20} step={0.01} unit=" m/s²" defaultValue={9.81} onChange={setG} />
<ParameterRow label="Damping" value={0.15} min={0} max={1} step={0.01} defaultValue={0.2} onChange={setZeta} />
```

Reset icon only becomes active (and clickable) once `value !== defaultValue`. Works identically for large (gravity 9.81) and small (damping 0.15) ranges — the fill percentage always derives from min/max.
