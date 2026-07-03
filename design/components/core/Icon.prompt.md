`Icon` renders a Lucide glyph by name — the design system's only icon primitive, loaded live from the Lucide CDN (no hand-drawn SVGs).

```jsx
<Icon name="play" size={16} color="var(--accent-cyan)" />
```

Requires `<script src="https://unpkg.com/lucide@latest"></script>` on the page (see readme.md → Iconography). Falls back to nothing rendered if Lucide hasn't loaded yet — always pair with a text label where the icon alone wouldn't be legible.
