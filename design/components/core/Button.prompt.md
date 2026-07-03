`Button` is the shared action control — used for Run/Cancel in the command bar, dialog actions, and inline card actions.

```jsx
<Button variant="primary" icon="play">Run</Button>
<Button variant="danger" icon="square">Cancel</Button>
```

Variants: `primary` (cyan fill, main action — one per view), `secondary` (default, bordered), `ghost` (text-only, low emphasis), `danger` (rose outline, destructive/cancel). Sizes: `sm`, `md`. Pass `icon` with any Lucide name; `disabled` dims and blocks pointer.
