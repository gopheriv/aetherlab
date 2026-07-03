/* @ds-bundle: {"format":4,"namespace":"AetherLabDesignSystem_448260","components":[{"name":"DerivationBlock","sourcePath":"components/content/DerivationBlock.jsx"},{"name":"ReferenceCard","sourcePath":"components/content/ReferenceCard.jsx"},{"name":"ReferenceEmptyState","sourcePath":"components/content/ReferenceCard.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"CommandBar","sourcePath":"components/forms/CommandBar.jsx"},{"name":"ParameterRow","sourcePath":"components/forms/ParameterRow.jsx"},{"name":"SettingsField","sourcePath":"components/forms/SettingsField.jsx"},{"name":"VideoControls","sourcePath":"components/media/VideoControls.jsx"},{"name":"NavRailItem","sourcePath":"components/navigation/NavRailItem.jsx"},{"name":"PipelineTimeline","sourcePath":"components/pipeline/PipelineTimeline.jsx"}],"sourceHashes":{"components/content/DerivationBlock.jsx":"3d9a343f171e","components/content/ReferenceCard.jsx":"b650a822333d","components/core/Button.jsx":"9eb6d931061d","components/core/Icon.jsx":"0c256ab0cd80","components/feedback/Toast.jsx":"ba937819b4c1","components/forms/CommandBar.jsx":"133257867bc7","components/forms/ParameterRow.jsx":"79dfb9bd8276","components/forms/SettingsField.jsx":"169a614061b7","components/media/VideoControls.jsx":"5192c4e09e13","components/navigation/NavRailItem.jsx":"139f54622d98","components/pipeline/PipelineTimeline.jsx":"6d9044560b56","ui_kits/aetherlab-desktop/App.jsx":"3cffeeeaaf22","ui_kits/aetherlab-desktop/DerivationView.jsx":"b23cf4e375b8","ui_kits/aetherlab-desktop/EmptyState.jsx":"641902b80b31","ui_kits/aetherlab-desktop/HistoryView.jsx":"c464a8da2d93","ui_kits/aetherlab-desktop/LibraryManager.jsx":"4c317ee3e3ce","ui_kits/aetherlab-desktop/Rail.jsx":"dc81e2c35270","ui_kits/aetherlab-desktop/RunningView.jsx":"9ab016938ace","ui_kits/aetherlab-desktop/SceneView.jsx":"7e5b008288ef","ui_kits/aetherlab-desktop/SettingsDialog.jsx":"d60b73d155bc","ui_kits/aetherlab-desktop/TitleBar.jsx":"443c76d9bebd"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.AetherLabDesignSystem_448260 = window.AetherLabDesignSystem_448260 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Icon.jsx
try { (() => {
// Thin wrapper around the Lucide icon set (loaded from CDN — see readme.md
// Iconography section). Renders a placeholder <i data-lucide> tag and asks
// Lucide to hydrate it into inline SVG once mounted / whenever `name` changes.
function Icon({
  name,
  size = 16,
  strokeWidth = 1.75,
  color = 'currentColor',
  style
}) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      ref.current.appendChild(i);
      window.lucide.createIcons({
        nameAttr: 'data-lucide',
        attrs: {},
        icons: undefined,
        root: ref.current
      });
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
      ...style
    },
    'data-icon-fallback': name
  });
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/content/DerivationBlock.jsx
try { (() => {
function DerivationBlock({
  summaryEquation,
  steps,
  keywords = [],
  onCopy,
  onExport
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-5)',
      fontFamily: 'var(--font-ui)',
      display: 'flex',
      flexDirection: 'column',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--bg-canvas-top)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)',
      padding: '18px 20px',
      textAlign: 'center',
      fontFamily: 'var(--font-mono)',
      fontSize: 20,
      color: 'var(--accent-cyan)',
      fontStyle: 'italic',
      letterSpacing: 'var(--tracking-tight)'
    }
  }, summaryEquation), keywords.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      flexWrap: 'wrap'
    }
  }, keywords.map(k => /*#__PURE__*/React.createElement("span", {
    key: k,
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--accent-violet)',
      border: '1px solid var(--accent-violet)',
      borderRadius: 'var(--radius-pill)',
      padding: '3px 9px',
      background: 'var(--accent-violet-tint-10)'
    }
  }, k))), /*#__PURE__*/React.createElement("ol", {
    style: {
      margin: 0,
      paddingLeft: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, steps.map((s, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    style: {
      color: 'var(--text-primary)',
      fontSize: 'var(--text-base)',
      lineHeight: 'var(--leading-relaxed)'
    }
  }, s.text, s.equation && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 4,
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)'
    }
  }, s.equation)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      borderTop: '1px solid var(--border-default)',
      paddingTop: 12
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onCopy,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'none',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-secondary)',
      fontSize: 'var(--text-sm)',
      padding: '6px 12px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "copy",
    size: 13
  }), "Copy"), /*#__PURE__*/React.createElement("button", {
    onClick: onExport,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'none',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-secondary)',
      fontSize: 'var(--text-sm)',
      padding: '6px 12px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "download",
    size: 13
  }), "Export")));
}
Object.assign(__ds_scope, { DerivationBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/content/DerivationBlock.jsx", error: String((e && e.message) || e) }); }

// components/content/ReferenceCard.jsx
try { (() => {
function scoreColor(score) {
  if (score >= 0.8) return 'var(--accent-emerald)';
  if (score >= 0.5) return 'var(--accent-amber)';
  return 'var(--text-tertiary)';
}
function ReferenceCard({
  source,
  page,
  score = 0,
  excerpt,
  onOpen
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "book-open",
    size: 14,
    color: "var(--accent-cyan)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-base)',
      fontWeight: 600,
      color: 'var(--text-primary)'
    }
  }, source), page && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary)'
    }
  }, "p.", page), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-xs)',
      color: scoreColor(score),
      border: `1px solid ${scoreColor(score)}`,
      borderRadius: 'var(--radius-pill)',
      padding: '2px 8px'
    }
  }, score.toFixed(2))), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)',
      lineHeight: 'var(--leading-normal)'
    }
  }, excerpt), /*#__PURE__*/React.createElement("button", {
    onClick: onOpen,
    style: {
      alignSelf: 'flex-start',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'none',
      border: 'none',
      color: 'var(--accent-cyan)',
      fontSize: 'var(--text-sm)',
      fontWeight: 500,
      cursor: 'pointer',
      padding: 0
    }
  }, "Open ", /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "arrow-up-right",
    size: 13
  })));
}
function ReferenceEmptyState({
  onAdd
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      border: '1px dashed var(--border-emphasis)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-8)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 10,
      fontFamily: 'var(--font-ui)',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "library",
    size: 24,
    color: "var(--text-tertiary)"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--text-secondary)',
      fontSize: 'var(--text-base)'
    }
  }, "No textbooks indexed yet"), /*#__PURE__*/React.createElement("button", {
    onClick: onAdd,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'var(--accent-cyan)',
      color: 'var(--text-on-accent)',
      border: 'none',
      borderRadius: 'var(--radius-md)',
      padding: '8px 14px',
      fontWeight: 600,
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "folder-plus",
    size: 14
  }), "Add textbooks\u2026"));
}
Object.assign(__ds_scope, { ReferenceCard, ReferenceEmptyState });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/content/ReferenceCard.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
const buttonBase = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  fontFamily: 'var(--font-ui)',
  fontWeight: 600,
  border: '1px solid transparent',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  transition: 'background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast), color var(--duration-fast)',
  whiteSpace: 'nowrap'
};
const sizes = {
  sm: {
    padding: '6px 12px',
    fontSize: 'var(--text-sm)'
  },
  md: {
    padding: '9px 16px',
    fontSize: 'var(--text-base)'
  }
};
function variantStyle(variant, disabled) {
  if (disabled) {
    return {
      background: 'var(--bg-panel-2)',
      color: 'var(--text-low)',
      borderColor: 'var(--border-default)',
      cursor: 'not-allowed'
    };
  }
  switch (variant) {
    case 'primary':
      return {
        background: 'var(--accent-cyan)',
        color: 'var(--text-on-accent)',
        borderColor: 'var(--accent-cyan)'
      };
    case 'danger':
      return {
        background: 'transparent',
        color: 'var(--accent-rose)',
        borderColor: 'var(--accent-rose)'
      };
    case 'ghost':
      return {
        background: 'transparent',
        color: 'var(--text-secondary)',
        borderColor: 'transparent'
      };
    default:
      return {
        background: 'var(--bg-panel-2)',
        color: 'var(--text-primary)',
        borderColor: 'var(--border-emphasis)'
      };
  }
}
function Button({
  children,
  variant = 'secondary',
  size = 'md',
  icon,
  disabled = false,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  const style = {
    ...buttonBase,
    ...sizes[size],
    ...variantStyle(variant, disabled)
  };
  if (!disabled && hover) {
    if (variant === 'primary') style.background = 'var(--accent-cyan-hover)';else if (variant === 'danger') style.background = 'var(--accent-rose-tint-10)';else if (variant === 'ghost') style.color = 'var(--text-primary)';else style.borderColor = 'var(--accent-cyan)';
  }
  return /*#__PURE__*/React.createElement("button", {
    style: style,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false)
  }, icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 14
  }), children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
const kindMap = {
  error: {
    color: 'var(--accent-rose)',
    bg: 'var(--accent-rose-tint-10)',
    icon: 'alert-triangle'
  },
  warning: {
    color: 'var(--accent-amber)',
    bg: 'var(--accent-amber-tint-10)',
    icon: 'alert-circle'
  },
  success: {
    color: 'var(--accent-emerald)',
    bg: 'var(--accent-emerald-tint-10)',
    icon: 'check-circle-2'
  },
  info: {
    color: 'var(--accent-cyan)',
    bg: 'var(--accent-cyan-tint-10)',
    icon: 'info'
  }
};
function Toast({
  kind = 'error',
  message,
  detail,
  onDismiss,
  onDetails
}) {
  const k = kindMap[kind];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      background: k.bg,
      border: `1px solid ${k.color}`,
      borderRadius: 'var(--radius-md)',
      padding: '10px 12px',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: k.icon,
    size: 16,
    color: k.color,
    style: {
      marginTop: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-primary)',
      fontWeight: 500
    }
  }, message), detail && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-secondary)',
      marginTop: 2
    }
  }, detail), onDetails && /*#__PURE__*/React.createElement("button", {
    onClick: onDetails,
    style: {
      background: 'none',
      border: 'none',
      color: k.color,
      fontSize: 'var(--text-xs)',
      fontWeight: 600,
      cursor: 'pointer',
      padding: '4px 0 0'
    }
  }, "Details")), onDismiss && /*#__PURE__*/React.createElement("button", {
    onClick: onDismiss,
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-tertiary)',
      cursor: 'pointer',
      padding: 2
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 14
  })));
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/forms/CommandBar.jsx
try { (() => {
const barBox = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  background: 'var(--surface-panel-raised)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-lg)',
  padding: '8px 10px',
  boxShadow: 'var(--shadow-panel)'
};
function CommandBar({
  value = '',
  onChange,
  placeholder = 'Describe a physics or math problem…  (Ctrl+Enter to run)',
  busy = false,
  quality = 'standard',
  onQualityChange,
  examples = ['Damped harmonic oscillator', 'Projectile motion with drag', 'Simple pendulum phase portrait'],
  onRun,
  onCancel
}) {
  const [focused, setFocused] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    style: barBox
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setMenuOpen(v => !v),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'transparent',
      border: 'none',
      color: 'var(--text-secondary)',
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-sm)',
      cursor: 'pointer',
      padding: '6px 8px'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "lightbulb",
    size: 14
  }), "Examples", /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron-down",
    size: 12
  })), menuOpen && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: '110%',
      left: 0,
      minWidth: 260,
      background: 'var(--bg-panel-2)',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-popover)',
      padding: 6,
      zIndex: 10
    }
  }, examples.map(ex => /*#__PURE__*/React.createElement("div", {
    key: ex,
    onClick: () => {
      onChange && onChange(ex);
      setMenuOpen(false);
    },
    style: {
      padding: '8px 10px',
      borderRadius: 'var(--radius-sm)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-primary)',
      cursor: 'pointer'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'var(--bg-panel-1)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, ex)))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 1,
      alignSelf: 'stretch',
      background: 'var(--border-default)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    value: value,
    disabled: busy,
    placeholder: placeholder,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    onChange: e => onChange && onChange(e.target.value),
    style: {
      flex: 1,
      background: 'transparent',
      border: 'none',
      outline: 'none',
      color: 'var(--text-primary)',
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-md)',
      boxShadow: focused ? 'none' : 'none'
    }
  }), /*#__PURE__*/React.createElement("select", {
    value: quality,
    onChange: e => onQualityChange && onQualityChange(e.target.value),
    style: {
      background: 'var(--bg-panel-1)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)',
      padding: '8px 10px',
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "draft"
  }, "Draft"), /*#__PURE__*/React.createElement("option", {
    value: "standard"
  }, "Standard"), /*#__PURE__*/React.createElement("option", {
    value: "high"
  }, "High")), busy ? /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "danger",
    icon: "square",
    onClick: onCancel
  }, "Cancel") : /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "primary",
    icon: "play",
    onClick: onRun
  }, "Run"));
}
Object.assign(__ds_scope, { CommandBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/CommandBar.jsx", error: String((e && e.message) || e) }); }

// components/forms/ParameterRow.jsx
try { (() => {
function ParameterRow({
  label,
  value,
  min,
  max,
  step = 0.01,
  unit = '',
  defaultValue,
  onChange
}) {
  const pct = (value - min) / (max - min) * 100;
  const changed = defaultValue !== undefined && value !== defaultValue;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 84,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)'
    }
  }, label), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: min,
    max: max,
    step: step,
    value: value,
    onChange: e => onChange && onChange(parseFloat(e.target.value)),
    style: {
      flex: 1,
      height: 4,
      borderRadius: 'var(--radius-pill)',
      appearance: 'none',
      background: `linear-gradient(90deg, var(--accent-cyan) ${pct}%, var(--border-default) ${pct}%)`,
      outline: 'none',
      cursor: 'pointer'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 74,
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-primary)',
      background: 'var(--surface-input)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-sm)',
      padding: '3px 6px'
    }
  }, value, unit), /*#__PURE__*/React.createElement("button", {
    onClick: () => defaultValue !== undefined && onChange && onChange(defaultValue),
    disabled: !changed,
    title: "Reset",
    style: {
      background: 'none',
      border: 'none',
      cursor: changed ? 'pointer' : 'default',
      color: changed ? 'var(--text-secondary)' : 'var(--text-low)',
      padding: 4
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "rotate-ccw",
    size: 14
  })));
}
Object.assign(__ds_scope, { ParameterRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/ParameterRow.jsx", error: String((e && e.message) || e) }); }

// components/forms/SettingsField.jsx
try { (() => {
const inputBox = {
  width: '100%',
  boxSizing: 'border-box',
  background: 'var(--surface-input)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text-primary)',
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-base)',
  padding: '9px 12px',
  outline: 'none'
};
function SettingsField({
  label,
  kind = 'text',
  value,
  options = [],
  placeholder,
  hint,
  onChange,
  onBrowse
}) {
  const [show, setShow] = React.useState(false);
  const [focused, setFocused] = React.useState(false);
  const boxStyle = {
    ...inputBox,
    borderColor: focused ? 'var(--accent-cyan)' : 'var(--border-default)'
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-sm)',
      fontWeight: 500,
      color: 'var(--text-secondary)'
    }
  }, label), kind === 'select' && /*#__PURE__*/React.createElement("select", {
    value: value,
    onChange: e => onChange && onChange(e.target.value),
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    style: boxStyle
  }, options.map(o => /*#__PURE__*/React.createElement("option", {
    key: o,
    value: o
  }, o))), kind === 'path' && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("input", {
    value: value,
    placeholder: placeholder,
    readOnly: true,
    style: {
      ...boxStyle,
      flex: 1,
      color: 'var(--text-secondary)',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-sm)'
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onBrowse,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'var(--bg-panel-2)',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-primary)',
      padding: '0 12px',
      cursor: 'pointer',
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "folder-open",
    size: 14
  }), "Browse")), kind === 'secret' && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: show ? 'text' : 'password',
    value: value,
    placeholder: placeholder,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    onChange: e => onChange && onChange(e.target.value),
    style: {
      ...boxStyle,
      paddingRight: 36,
      fontFamily: 'var(--font-mono)'
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: () => setShow(s => !s),
    style: {
      position: 'absolute',
      right: 8,
      top: '50%',
      transform: 'translateY(-50%)',
      background: 'none',
      border: 'none',
      color: 'var(--text-tertiary)',
      cursor: 'pointer',
      padding: 4
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: show ? 'eye-off' : 'eye',
    size: 14
  }))), kind === 'text' && /*#__PURE__*/React.createElement("input", {
    value: value,
    placeholder: placeholder,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    onChange: e => onChange && onChange(e.target.value),
    style: boxStyle
  }), hint && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary)'
    }
  }, hint));
}
Object.assign(__ds_scope, { SettingsField });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/SettingsField.jsx", error: String((e && e.message) || e) }); }

// components/media/VideoControls.jsx
try { (() => {
function VideoControls({
  playing,
  currentTime,
  duration,
  progress,
  speed = 1,
  onPlayPause,
  onStop,
  onSeek,
  onSpeedChange,
  onSave
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      background: 'var(--surface-panel-raised)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      padding: '10px 14px',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onPlayPause,
    style: {
      width: 32,
      height: 32,
      borderRadius: '50%',
      border: 'none',
      background: 'var(--accent-cyan)',
      color: 'var(--text-on-accent)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: playing ? 'pause' : 'play',
    size: 15
  })), /*#__PURE__*/React.createElement("button", {
    onClick: onStop,
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-secondary)',
      cursor: 'pointer',
      padding: 4
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "square",
    size: 14
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary)',
      width: 40
    }
  }, currentTime), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: 0,
    max: 100,
    value: progress,
    onChange: e => onSeek && onSeek(parseFloat(e.target.value)),
    style: {
      flex: 1,
      height: 4,
      borderRadius: 'var(--radius-pill)',
      appearance: 'none',
      outline: 'none',
      cursor: 'pointer',
      background: `linear-gradient(90deg, var(--accent-cyan) ${progress}%, var(--border-default) ${progress}%)`
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary)',
      width: 40
    }
  }, duration), /*#__PURE__*/React.createElement("select", {
    value: speed,
    onChange: e => onSpeedChange && onSpeedChange(parseFloat(e.target.value)),
    style: {
      background: 'var(--bg-panel-1)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-sm)',
      fontFamily: 'var(--font-mono)',
      fontSize: 'var(--text-xs)',
      padding: '4px 6px'
    }
  }, [0.5, 1, 1.5, 2].map(s => /*#__PURE__*/React.createElement("option", {
    key: s,
    value: s
  }, s, "\xD7"))), /*#__PURE__*/React.createElement("button", {
    onClick: onSave,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'none',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-secondary)',
      fontSize: 'var(--text-xs)',
      padding: '6px 10px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "save",
    size: 13
  }), "Save"));
}
Object.assign(__ds_scope, { VideoControls });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/VideoControls.jsx", error: String((e && e.message) || e) }); }

// components/navigation/NavRailItem.jsx
try { (() => {
function NavRailItem({
  icon,
  label,
  active = false,
  disabled = false,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  const bg = active ? 'var(--accent-cyan-tint-10)' : hover && !disabled ? 'var(--bg-panel-2)' : 'transparent';
  const color = disabled ? 'var(--text-low)' : active ? 'var(--accent-cyan)' : 'var(--text-secondary)';
  return /*#__PURE__*/React.createElement("div", {
    onClick: disabled ? undefined : onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 4,
      width: 64,
      padding: '10px 4px',
      borderRadius: 'var(--radius-md)',
      background: bg,
      color,
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'background var(--duration-fast) var(--ease-standard), color var(--duration-fast)'
    }
  }, active && /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      left: -8,
      top: '50%',
      transform: 'translateY(-50%)',
      width: 3,
      height: 20,
      borderRadius: 'var(--radius-pill)',
      background: 'var(--accent-cyan)',
      boxShadow: 'var(--glow-cyan)'
    }
  }), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 18
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      fontWeight: 500,
      letterSpacing: 'var(--tracking-wide)'
    }
  }, label));
}
Object.assign(__ds_scope, { NavRailItem });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/NavRailItem.jsx", error: String((e && e.message) || e) }); }

// components/pipeline/PipelineTimeline.jsx
try { (() => {
const statusColor = {
  pending: 'var(--state-pending)',
  active: 'var(--state-active)',
  complete: 'var(--state-complete)',
  error: 'var(--state-error)'
};
function Node({
  stage,
  isLast,
  onCancel
}) {
  const color = statusColor[stage.status];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 8,
      minWidth: 96
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 32,
      height: 32,
      borderRadius: '50%',
      border: `2px solid ${color}`,
      background: stage.status === 'complete' ? color : 'var(--bg-panel-1)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: stage.status === 'active' ? 'var(--glow-cyan)' : 'none',
      animation: stage.status === 'active' ? 'aeth-pulse 1.6s var(--ease-standard) infinite' : 'none'
    }
  }, stage.status === 'complete' && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "check",
    size: 16,
    color: "var(--text-on-accent)"
  }), stage.status === 'error' && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 16,
    color: color
  }), stage.status === 'active' && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "loader-2",
    size: 16,
    color: color,
    style: {
      animation: 'aeth-spin 1s linear infinite'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 12.5,
      fontWeight: 600,
      color: stage.status === 'pending' ? 'var(--text-low)' : 'var(--text-primary)'
    }
  }, stage.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--text-tertiary)',
      height: 14
    }
  }, stage.elapsed || ''), stage.status === 'active' && onCancel && /*#__PURE__*/React.createElement("button", {
    onClick: onCancel,
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      color: 'var(--accent-rose)',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: 0
    }
  }, "Cancel")), !isLast && /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 2,
      background: stage.status === 'complete' ? 'var(--state-complete)' : 'var(--border-default)',
      marginTop: 16
    }
  }));
}
function PipelineTimeline({
  stages,
  onCancel
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("style", null, `
        @keyframes aeth-pulse { 0%,100% { box-shadow: 0 0 0 0 var(--accent-cyan-glow); } 50% { box-shadow: 0 0 0 6px transparent; } }
        @keyframes aeth-spin { to { transform: rotate(360deg); } }
      `), stages.map((s, i) => /*#__PURE__*/React.createElement(Node, {
    key: s.label,
    stage: s,
    isLast: i === stages.length - 1,
    onCancel: onCancel
  })));
}
Object.assign(__ds_scope, { PipelineTimeline });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/pipeline/PipelineTimeline.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/App.jsx
try { (() => {
const {
  Rail,
  TitleBar,
  EmptyState,
  RunningView,
  DerivationView,
  SceneView,
  LibraryManager,
  SettingsDialog,
  HistoryView
} = window;
const STAGE_LABELS = ['Solve', 'RAG', 'Scene', 'Render'];
function App() {
  const {
    CommandBar,
    Toast
  } = window.AetherLabDesignSystem_448260;
  const [prompt, setPrompt] = React.useState('');
  const [quality, setQuality] = React.useState('standard');
  const [running, setRunning] = React.useState(false);
  const [hasResult, setHasResult] = React.useState(false);
  const [stageIndex, setStageIndex] = React.useState(-1);
  const [rail, setRail] = React.useState('solve');
  const [sceneTab, setSceneTab] = React.useState('canvas');
  const [showParams, setShowParams] = React.useState(false);
  const [overlay, setOverlay] = React.useState(true);
  const [params, setParams] = React.useState({
    g: 9.81,
    zeta: 0.15,
    omega: 2.0
  });
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [error, setError] = React.useState(null);
  const timerRef = React.useRef(null);
  const stages = STAGE_LABELS.map((label, i) => ({
    label,
    status: i < stageIndex ? 'complete' : i === stageIndex ? 'active' : 'pending',
    elapsed: i < stageIndex ? `${(1 + i * 0.6).toFixed(1)}s` : undefined
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
    workspace = /*#__PURE__*/React.createElement(RunningView, {
      stages: stages,
      onCancel: cancel
    });
  } else if (!hasResult) {
    workspace = /*#__PURE__*/React.createElement(EmptyState, {
      onOpenSettings: () => setSettingsOpen(true),
      onOpenLibrary: () => setRail('refs'),
      onPickExample: setPrompt
    });
  } else if (rail === 'refs') {
    workspace = /*#__PURE__*/React.createElement(LibraryManager, {
      onAdd: () => {}
    });
  } else if (rail === 'history') {
    workspace = /*#__PURE__*/React.createElement(HistoryView, {
      onRerun: setPrompt,
      onClear: () => {}
    });
  } else if (rail === 'scene') {
    workspace = /*#__PURE__*/React.createElement(SceneView, {
      stages: stages,
      tab: sceneTab,
      onTabChange: setSceneTab,
      showParams: showParams,
      overlay: overlay,
      onOverlayToggle: setOverlay,
      params: params,
      onParamChange: (k, v) => setParams(p => ({
        ...p,
        [k]: v
      }))
    });
  } else {
    workspace = /*#__PURE__*/React.createElement(DerivationView, {
      stages: stages
    });
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 1500,
      height: 950,
      background: 'var(--surface-app)',
      display: 'flex',
      flexDirection: 'column',
      borderRadius: 10,
      overflow: 'hidden',
      position: 'relative',
      boxShadow: '0 30px 80px rgba(0,0,0,0.6)'
    }
  }, /*#__PURE__*/React.createElement(TitleBar, {
    onOpenSettings: () => setSettingsOpen(true)
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(Rail, {
    screen: rail,
    onSelect: id => {
      setRail(id);
      if (id === 'params') setShowParams(v => !v);
    },
    hasResult: hasResult
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      minWidth: 0
    }
  }, error && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 20px'
    }
  }, /*#__PURE__*/React.createElement(Toast, {
    kind: "error",
    message: error,
    onDismiss: () => setError(null)
  })), workspace, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 20px',
      borderTop: '1px solid var(--border-default)',
      background: 'var(--bg-panel-1)'
    }
  }, /*#__PURE__*/React.createElement(CommandBar, {
    value: prompt,
    onChange: setPrompt,
    quality: quality,
    onQualityChange: setQuality,
    busy: running,
    onRun: run,
    onCancel: cancel
  })))), settingsOpen && /*#__PURE__*/React.createElement(SettingsDialog, {
    onClose: () => setSettingsOpen(false)
  }));
}
window.App = App;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/DerivationView.jsx
try { (() => {
// Screen 3 — Result, Derivation focus: typeset summary + steps, keyword chips,
// references list beside the derivation.
function DerivationView({
  stages
}) {
  const {
    PipelineTimeline,
    DerivationBlock,
    ReferenceCard
  } = window.AetherLabDesignSystem_448260;
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "03 Result \u2014 Derivation Focus",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-ui)',
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '16px 28px',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(PipelineTimeline, {
    stages: stages
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 24,
      padding: 28,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1.4
    }
  }, /*#__PURE__*/React.createElement(DerivationBlock, {
    summaryEquation: "x(t) = A e^(-\u03B6\u03C9\u2099t) cos(\u03C9d t + \u03C6)",
    keywords: ['damped oscillator', '2nd-order ODE', 'underdamped'],
    steps: [{
      text: "Start from Newton's second law for the mass–spring–damper system.",
      equation: "m x'' + c x' + k x = 0"
    }, {
      text: 'Divide through by mass and define natural frequency \u03C9\u2099 and damping ratio \u03B6.',
      equation: "x'' + 2\u03B6\u03C9\u2099 x' + \u03C9\u2099\u00B2 x = 0"
    }, {
      text: 'Solve the characteristic equation; for \u03B6 < 1 the roots are complex, giving oscillatory decay.'
    }, {
      text: 'Apply initial conditions x(0) = A, x\u2032(0) = 0 to fix the phase \u03C6.'
    }]
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      color: 'var(--text-secondary)',
      letterSpacing: 'var(--tracking-wide)',
      textTransform: 'uppercase'
    }
  }, "References"), /*#__PURE__*/React.createElement(ReferenceCard, {
    source: "Goldstein \u2014 Classical Mechanics",
    page: "87",
    score: 0.92,
    excerpt: "The equation of motion for a damped harmonic oscillator follows directly from Newton's second law."
  }), /*#__PURE__*/React.createElement(ReferenceCard, {
    source: "Taylor \u2014 Classical Mechanics",
    page: "154",
    score: 0.61,
    excerpt: "Underdamped, critically damped, and overdamped regimes are distinguished by the discriminant sign."
  }))));
}
window.DerivationView = DerivationView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/DerivationView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/EmptyState.jsx
try { (() => {
// Screen 1 — Empty / first-run: no API key, no library. Clear CTAs.
function EmptyState({
  onOpenSettings,
  onOpenLibrary,
  onPickExample
}) {
  const {
    Icon,
    Button
  } = window.AetherLabDesignSystem_448260;
  const examples = ['Damped harmonic oscillator with ζ = 0.15', 'Projectile motion with quadratic drag', 'Simple pendulum phase portrait'];
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "01 Empty / First-Run",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 24,
      fontFamily: 'var(--font-ui)',
      padding: 40,
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "atom",
    size: 40,
    color: "var(--accent-cyan)"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-2xl)',
      fontWeight: 700,
      color: 'var(--text-primary)'
    }
  }, "Describe a problem to begin"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-base)',
      color: 'var(--text-secondary)',
      marginTop: 8
    }
  }, "Type a physics or math prompt below, or start from an example.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      flexWrap: 'wrap',
      justifyContent: 'center',
      maxWidth: 640
    }
  }, examples.map(ex => /*#__PURE__*/React.createElement("button", {
    key: ex,
    onClick: () => onPickExample(ex),
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      color: 'var(--text-primary)',
      fontSize: 'var(--text-sm)',
      padding: '10px 16px',
      cursor: 'pointer'
    }
  }, ex))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 24,
      marginTop: 12,
      padding: '14px 20px',
      border: '1px dashed var(--border-emphasis)',
      borderRadius: 'var(--radius-lg)',
      background: 'var(--surface-panel)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "key-round",
    size: 16,
    color: "var(--accent-amber)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)'
    }
  }, "No API key configured"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm",
    onClick: onOpenSettings
  }, "Open Settings")), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 1,
      background: 'var(--border-default)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "library",
    size: 16,
    color: "var(--accent-amber)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)'
    }
  }, "No textbooks indexed"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm",
    onClick: onOpenLibrary
  }, "Add textbooks"))));
}
window.EmptyState = EmptyState;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/EmptyState.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/HistoryView.jsx
try { (() => {
// Screen 8 — History: past runs (prompt, time, status, refs count), click to
// re-run, clear.
const runs = [{
  prompt: 'Damped harmonic oscillator with ζ = 0.15',
  time: '2 min ago',
  status: 'complete',
  refs: 3
}, {
  prompt: 'Projectile motion with quadratic drag',
  time: '1 hour ago',
  status: 'complete',
  refs: 2
}, {
  prompt: 'Simple pendulum phase portrait',
  time: 'Yesterday',
  status: 'error',
  refs: 0
}, {
  prompt: 'Coupled oscillators, normal modes',
  time: '2 days ago',
  status: 'complete',
  refs: 4
}];
function HistoryView({
  onRerun,
  onClear
}) {
  const {
    Icon,
    Button
  } = window.AetherLabDesignSystem_448260;
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "08 History",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-ui)',
      padding: 28,
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xl)',
      fontWeight: 700,
      color: 'var(--text-primary)'
    }
  }, "History"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    icon: "trash-2",
    onClick: onClear
  }, "Clear")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 1,
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden'
    }
  }, runs.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    onClick: () => onRerun(r.prompt),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      padding: '14px 18px',
      background: 'var(--surface-card)',
      borderBottom: '1px solid var(--border-default)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: r.status === 'complete' ? 'check-circle-2' : 'x-circle',
    size: 16,
    color: r.status === 'complete' ? 'var(--accent-emerald)' : 'var(--accent-rose)'
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-base)',
      color: 'var(--text-primary)'
    }
  }, r.prompt), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary)',
      fontFamily: 'var(--font-mono)',
      marginTop: 2
    }
  }, r.time, " \xB7 ", r.refs, " refs")), /*#__PURE__*/React.createElement(Icon, {
    name: "rotate-cw",
    size: 14,
    color: "var(--text-tertiary)"
  })))));
}
window.HistoryView = HistoryView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/HistoryView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/LibraryManager.jsx
try { (() => {
// Screen 6 — References / Library manager: indexed sources + add folder / ingest /
// re-index and index status.
const sources = [{
  name: 'Goldstein — Classical Mechanics.pdf',
  pages: 638,
  status: 'Indexed'
}, {
  name: 'Taylor — Classical Mechanics.pdf',
  pages: 786,
  status: 'Indexed'
}, {
  name: 'Griffiths — Electrodynamics.pdf',
  pages: 599,
  status: 'Indexing…'
}];
function LibraryManager({
  onAdd
}) {
  const {
    Icon,
    Button,
    ReferenceEmptyState
  } = window.AetherLabDesignSystem_448260;
  const hasSources = sources.length > 0;
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "06 References / Library Manager",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-ui)',
      padding: 28,
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xl)',
      fontWeight: 700,
      color: 'var(--text-primary)'
    }
  }, "Library"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    icon: "folder-plus",
    onClick: onAdd
  }, "Add folder"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    icon: "refresh-cw"
  }, "Re-index")), hasSources ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 1,
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden'
    }
  }, sources.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.name,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 16px',
      background: 'var(--surface-card)',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "file-text",
    size: 16,
    color: "var(--text-tertiary)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-primary)'
    }
  }, s.name), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      fontFamily: 'var(--font-mono)',
      color: 'var(--text-tertiary)'
    }
  }, s.pages, "p"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      padding: '2px 9px',
      borderRadius: 'var(--radius-pill)',
      color: s.status === 'Indexed' ? 'var(--accent-emerald)' : 'var(--accent-cyan)',
      border: `1px solid ${s.status === 'Indexed' ? 'var(--accent-emerald)' : 'var(--accent-cyan)'}`
    }
  }, s.status)))) : /*#__PURE__*/React.createElement(ReferenceEmptyState, {
    onAdd: onAdd
  }));
}
window.LibraryManager = LibraryManager;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/LibraryManager.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/Rail.jsx
try { (() => {
// Persistent left icon rail — pure navigation, each item maps 1:1 to
// what the single workspace shows. No item ever silently acts elsewhere.
function Rail({
  screen,
  onSelect,
  hasResult
}) {
  const {
    NavRailItem
  } = window.AetherLabDesignSystem_448260;
  const items = [{
    id: 'solve',
    icon: 'sigma',
    label: 'Solve'
  }, {
    id: 'refs',
    icon: 'book-open',
    label: 'Refs'
  }, {
    id: 'scene',
    icon: 'clapperboard',
    label: 'Scene'
  }, {
    id: 'params',
    icon: 'sliders-horizontal',
    label: 'Params',
    disabled: !hasResult
  }, {
    id: 'history',
    icon: 'history',
    label: 'History'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 84,
      flex: 'none',
      background: 'var(--bg-panel-1)',
      borderRight: '1px solid var(--border-default)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 6,
      paddingTop: 16
    }
  }, items.map(it => /*#__PURE__*/React.createElement(NavRailItem, {
    key: it.id,
    icon: it.icon,
    label: it.label,
    active: screen === it.id,
    disabled: it.disabled,
    onClick: () => onSelect(it.id)
  })));
}
window.Rail = Rail;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/Rail.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/RunningView.jsx
try { (() => {
// Screen 2 — Prompt entered, pipeline running. Timeline mid-flight (Scene active),
// cancel control, live status, loading state in the workspace.
function RunningView({
  stages,
  onCancel
}) {
  const {
    PipelineTimeline,
    Icon
  } = window.AetherLabDesignSystem_448260;
  const activeStage = stages.find(s => s.status === 'active');
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "02 Pipeline Running",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px 28px',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(PipelineTimeline, {
    stages: stages,
    onCancel: onCancel
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      width: 88,
      height: 88
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      position: 'absolute',
      inset: i * 14,
      borderRadius: '50%',
      border: '2px solid var(--accent-cyan)',
      opacity: 0.35 + i * 0.15,
      animation: `aeth-ring 1.8s var(--ease-standard) ${i * 0.2}s infinite`
    }
  })), /*#__PURE__*/React.createElement("style", null, `@keyframes aeth-ring { 0%,100% { transform: scale(0.9); opacity: 0.25; } 50% { transform: scale(1.05); opacity: 0.7; } }`)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-lg)',
      fontWeight: 600,
      color: 'var(--text-primary)'
    }
  }, activeStage ? `Running ${activeStage.label}…` : 'Working…'), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-tertiary)',
      fontFamily: 'var(--font-mono)'
    }
  }, "generating Manim scene from derivation")));
}
window.RunningView = RunningView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/RunningView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/SceneView.jsx
try { (() => {
// Screens 4 & 5 — Result, Visualization + Code focus. Canvas/Video/Code pill tabs,
// phase-portrait overlay toggle, parameter dock alongside.
const codeSample = `class DampedOscillator(Scene):
    def construct(self):
        g = 9.81      # gravity
        zeta = 0.15   # damping ratio
        omega_n = 2.0 # natural frequency (rad/s)

        axes = Axes(x_range=[0, 10], y_range=[-1, 1])
        curve = axes.plot(
            lambda t: math.exp(-zeta * omega_n * t)
            * math.cos(omega_n * math.sqrt(1 - zeta**2) * t)
        )
        self.play(Create(axes), Create(curve))
`;
function SceneView({
  stages,
  tab,
  onTabChange,
  showParams,
  overlay,
  onOverlayToggle,
  params,
  onParamChange
}) {
  const {
    PipelineTimeline,
    Icon,
    VideoControls,
    ParameterRow
  } = window.AetherLabDesignSystem_448260;
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "04-05 Result \u2014 Visualization / Code Focus",
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '16px 28px',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(PipelineTimeline, {
    stages: stages
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flex: 1,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      padding: 24,
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, ['canvas', 'video', 'code'].map(t => /*#__PURE__*/React.createElement("button", {
    key: t,
    onClick: () => onTabChange(t),
    style: {
      padding: '7px 16px',
      borderRadius: 'var(--radius-pill)',
      border: `1px solid ${tab === t ? 'var(--accent-cyan)' : 'var(--border-default)'}`,
      background: tab === t ? 'var(--accent-cyan-tint-10)' : 'transparent',
      color: tab === t ? 'var(--accent-cyan)' : 'var(--text-secondary)',
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      cursor: 'pointer',
      textTransform: 'capitalize'
    }
  }, t)), tab === 'canvas' && /*#__PURE__*/React.createElement("label", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-secondary)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: overlay,
    onChange: e => onOverlayToggle(e.target.checked)
  }), "Phase-portrait overlay")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-default)',
      background: 'linear-gradient(180deg, var(--bg-canvas-top), var(--bg-canvas-bottom))',
      position: 'relative',
      overflow: 'hidden',
      minHeight: 260
    }
  }, tab !== 'code' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("svg", {
    width: "100%",
    height: "100%",
    viewBox: "0 0 400 220",
    preserveAspectRatio: "none",
    style: {
      position: 'absolute',
      inset: 0
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M0,110 Q40,20 80,110 T160,110 T240,110 T320,110 T400,110",
    stroke: "var(--accent-cyan)",
    strokeWidth: "2",
    fill: "none"
  }), overlay && tab === 'canvas' && /*#__PURE__*/React.createElement("ellipse", {
    cx: "200",
    cy: "110",
    rx: "120",
    ry: "60",
    stroke: "var(--accent-violet)",
    strokeWidth: "1.5",
    fill: "none",
    strokeDasharray: "4 4"
  })), tab === 'video' && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: 14,
      left: 14,
      right: 14
    }
  }, /*#__PURE__*/React.createElement(VideoControls, {
    playing: true,
    currentTime: "0:04",
    duration: "0:12",
    progress: 33,
    onSeek: () => {}
  }))), tab === 'code' && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      padding: 18,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      lineHeight: 1.6,
      color: 'var(--accent-emerald)',
      whiteSpace: 'pre-wrap'
    }
  }, codeSample))), tab === 'code' && /*#__PURE__*/React.createElement("button", {
    style: {
      alignSelf: 'flex-start',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: 'none',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-secondary)',
      fontSize: 'var(--text-sm)',
      padding: '6px 12px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "download",
    size: 13
  }), "Export scene.py")), showParams && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 300,
      flex: 'none',
      borderLeft: '1px solid var(--border-default)',
      background: 'var(--surface-panel)',
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      color: 'var(--text-secondary)',
      letterSpacing: 'var(--tracking-wide)',
      textTransform: 'uppercase'
    }
  }, "Parameters"), /*#__PURE__*/React.createElement(ParameterRow, {
    label: "Gravity",
    value: params.g,
    min: 0,
    max: 20,
    step: 0.01,
    unit: " m/s\xB2",
    defaultValue: 9.81,
    onChange: v => onParamChange('g', v)
  }), /*#__PURE__*/React.createElement(ParameterRow, {
    label: "Damping",
    value: params.zeta,
    min: 0,
    max: 1,
    step: 0.01,
    defaultValue: 0.2,
    onChange: v => onParamChange('zeta', v)
  }), /*#__PURE__*/React.createElement(ParameterRow, {
    label: "Frequency",
    value: params.omega,
    min: 0,
    max: 10,
    step: 0.1,
    unit: " rad/s",
    defaultValue: 2,
    onChange: v => onParamChange('omega', v)
  }))));
}
window.SceneView = SceneView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/SceneView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/SettingsDialog.jsx
try { (() => {
// Screen 7 — Settings dialog: provider (API key, base URL, model), render engine
// & quality, data/library paths, sensible defaults.
function SettingsDialog({
  onClose
}) {
  const {
    Icon,
    Button,
    SettingsField
  } = window.AetherLabDesignSystem_448260;
  const [apiKey, setApiKey] = React.useState('sk-live-aeth-83fd92');
  const [baseUrl, setBaseUrl] = React.useState('https://api.anthropic.com');
  const [model, setModel] = React.useState('claude-sonnet');
  const [engine, setEngine] = React.useState('Manim (Community)');
  const [quality, setQuality] = React.useState('Standard (1080p)');
  const [libPath, setLibPath] = React.useState('C:\\Users\\aeth\\AetherLab\\Library');
  const [outPath, setOutPath] = React.useState('C:\\Users\\aeth\\AetherLab\\Output');
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "07 Settings",
    style: {
      position: 'absolute',
      inset: 0,
      background: 'var(--surface-overlay)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 480,
      maxHeight: '86%',
      overflow: 'auto',
      background: 'var(--bg-panel-2)',
      border: '1px solid var(--border-emphasis)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-popover)',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      padding: '16px 20px',
      borderBottom: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 16,
    color: "var(--text-secondary)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 8,
      fontSize: 'var(--text-lg)',
      fontWeight: 600,
      color: 'var(--text-primary)'
    }
  }, "Settings"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-tertiary)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "x",
    size: 16
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      fontWeight: 700,
      color: 'var(--accent-cyan)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-widest)'
    }
  }, "Provider"), /*#__PURE__*/React.createElement(SettingsField, {
    label: "API Key",
    kind: "secret",
    value: apiKey,
    onChange: setApiKey,
    placeholder: "sk-\u2026"
  }), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Base URL",
    kind: "text",
    value: baseUrl,
    onChange: setBaseUrl
  }), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Model",
    kind: "select",
    value: model,
    options: ['claude-sonnet', 'claude-opus', 'claude-haiku'],
    onChange: setModel
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      fontWeight: 700,
      color: 'var(--accent-cyan)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-widest)',
      marginTop: 4
    }
  }, "Rendering"), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Render engine",
    kind: "select",
    value: engine,
    options: ['Manim (Community)', 'Manim (GL)'],
    onChange: setEngine
  }), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Default quality",
    kind: "select",
    value: quality,
    options: ['Draft (480p)', 'Standard (1080p)', 'High (4K)'],
    onChange: setQuality
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      fontWeight: 700,
      color: 'var(--accent-cyan)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-widest)',
      marginTop: 4
    }
  }, "Paths"), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Library path",
    kind: "path",
    value: libPath,
    onBrowse: () => {},
    hint: "Where indexed textbooks are stored"
  }), /*#__PURE__*/React.createElement(SettingsField, {
    label: "Output path",
    kind: "path",
    value: outPath,
    onBrowse: () => {},
    hint: "Where rendered videos are saved"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 8,
      padding: '14px 20px',
      borderTop: '1px solid var(--border-default)'
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    onClick: onClose
  }, "Cancel"), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    onClick: onClose
  }, "Save"))));
}
window.SettingsDialog = SettingsDialog;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/SettingsDialog.jsx", error: String((e && e.message) || e) }); }

// ui_kits/aetherlab-desktop/TitleBar.jsx
try { (() => {
function TitleBar({
  onOpenSettings
}) {
  const {
    Icon
  } = window.AetherLabDesignSystem_448260;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: 44,
      flex: 'none',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '0 16px',
      background: 'var(--bg-deepest)',
      borderBottom: '1px solid var(--border-default)',
      fontFamily: 'var(--font-ui)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "atom",
    size: 16,
    color: "var(--accent-cyan)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-primary)',
      letterSpacing: 'var(--tracking-wide)'
    }
  }, "AetherLab"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onOpenSettings,
    title: "Settings",
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-secondary)',
      cursor: 'pointer',
      padding: 6,
      display: 'flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 16
  })));
}
window.TitleBar = TitleBar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/aetherlab-desktop/TitleBar.jsx", error: String((e && e.message) || e) }); }

__ds_ns.DerivationBlock = __ds_scope.DerivationBlock;

__ds_ns.ReferenceCard = __ds_scope.ReferenceCard;

__ds_ns.ReferenceEmptyState = __ds_scope.ReferenceEmptyState;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.CommandBar = __ds_scope.CommandBar;

__ds_ns.ParameterRow = __ds_scope.ParameterRow;

__ds_ns.SettingsField = __ds_scope.SettingsField;

__ds_ns.VideoControls = __ds_scope.VideoControls;

__ds_ns.NavRailItem = __ds_scope.NavRailItem;

__ds_ns.PipelineTimeline = __ds_scope.PipelineTimeline;

})();
