`NavRailItem` is one destination in the persistent left rail (Solve / Refs / Scene / Params / History).

```jsx
<NavRailItem icon="sigma" label="Solve" active />
```

`active` shows a cyan left-edge indicator + tinted background + cyan icon/label — only one item should be active at a time, and it should map 1:1 to what's showing in the workspace (see readme.md spatial model). `disabled` dims and blocks clicks (e.g. Params before a result exists).
