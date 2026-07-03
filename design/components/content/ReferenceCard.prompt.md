`ReferenceCard` shows one RAG hit — source, page, relevance score chip, excerpt, Open action. `ReferenceEmptyState` is the paired empty state when no library is indexed yet.

```jsx
<ReferenceCard source="Goldstein — Classical Mechanics" page="87" score={0.92} excerpt="…the equation of motion for a damped oscillator…" onOpen={open} />
<ReferenceEmptyState onAdd={openLibraryManager} />
```

Score chip colors: ≥0.8 emerald, ≥0.5 amber, below that text-tertiary (low confidence, still shown — never hidden).
