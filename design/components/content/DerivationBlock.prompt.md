`DerivationBlock` renders the typeset result summary, keyword chips, numbered derivation steps (each with an optional equation line), and Copy/Export actions.

```jsx
<DerivationBlock
  summaryEquation="x(t) = A e^(−ζωₙt) cos(ωd t + φ)"
  keywords={['damped oscillator', 'second-order ODE']}
  steps={[
    { text: 'Start from Newton\u2019s second law for the mass-spring-damper system.', equation: 'm x\u2032\u2032 + c x\u2032 + k x = 0' },
    { text: 'Divide through by mass and define natural frequency and damping ratio.' },
  ]}
  onCopy={copy} onExport={exportPdf}
/>
```

The summary equation sits in a canvas-gradient plate for emphasis; treat it as the single most important element on the Derivation-focus screen. This is a placeholder for real LaTeX/MathJax typesetting — swap the mono-italic string for rendered math in production.
