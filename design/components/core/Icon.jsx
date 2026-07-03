import React from 'react';

// Thin wrapper around the Lucide icon set (loaded from CDN — see readme.md
// Iconography section). Renders a placeholder <i data-lucide> tag and asks
// Lucide to hydrate it into inline SVG once mounted / whenever `name` changes.
export function Icon({ name, size = 16, strokeWidth = 1.75, color = 'currentColor', style }) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      ref.current.appendChild(i);
      window.lucide.createIcons({ nameAttr: 'data-lucide', attrs: {}, icons: undefined, root: ref.current });
    }
  }, [name]);

  return React.createElement('span', {
    ref,
    style: {
      display: 'inline-flex',
      width: size,
      height: size,
      color,
      flex: 'none',
      ...style,
    },
    'data-icon-fallback': name,
  });
}
