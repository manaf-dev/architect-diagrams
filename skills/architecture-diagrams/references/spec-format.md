# Diagram spec format

YAML (needs PyYAML) or JSON. Coordinates are absolute canvas pixels, origin top-left; keep them on an 8 px grid.

```yaml
canvas: {width: 1600, height: 860}          # default 1600 x 900
title: Orders platform — AWS serverless       # optional, drawn at (40, 20)
subtitle: API intake → event fan-out → lake   # optional, drawn at (40, 54) — start content at y >= 96
credits: "Icons: AWS Architecture Icons"      # optional, bottom-right
iconLibraries: {acme: ./icons/acme.xml}      # optional extra aliases for lib:<alias>#<Title>
theme: {text: "#1E293B", muted: "#64748B"}   # optional overrides (font, text, muted, border, background, group, groupFill)
edgeKinds: {replication: {color: "#0EA5E9", dash: "6 3", width: 2, both: false, legend: Replication}}  # optional custom kinds

elements: [...]   # drawn in order: put boundaries first so they sit behind
edges: [...]
legend: {x: 40, y: 712, labels: {control: Orchestration}, order: [data, control]}   # or legend: false; height = 34 + 18 x kinds
```

## Labels

`label` is a string (`"\n"` separates lines) or a list. The first line is the name (bold), the rest are
details (10 px, muted). Any line can be an object to override: `{text, size, weight, color, mono}`.

## Elements

All need a unique `id`. Boxes, groups, zones and text use `x, y, w, h`. Icons use `cx, cy` (centre) or
`x, y`, plus `size` (height; width follows the icon's aspect ratio).

| type | fields |
|---|---|
| `group` | `label`, `icon` (optional ref shown top-left), `iconSize` (30), `color` (stroke), `fill`, `dashed` (default false) |
| `zone` | `title`, `subtitle`, `items` (list, monospace by default; `monoItems: false` for prose), `footer` (list), `color`, `headerFill`, `fill`, `headerHeight` (48) |
| `icon` | `icon` (ref), `size` (48), `label`, `labelPos`: `below` (default) / `right` / `left` / `above` |
| `box` | `label`, `color`, `fill`, `radius` (10), `dashed` |
| `text` | `label`, `align`: `center` (default) / `left` / `right` |

## Edges

```yaml
- from: api            # element ids
  to: fn
  kind: data           # data | control | async | alert | telemetry | deploy | sync (two-way) | optional | <custom>
  label: put order     # optional, same label format
  labelAt: [612, 340]  # optional label centre; default = beside the longest segment
  fromSide: right      # optional: left | right | top | bottom (default: chosen from relative position)
  toSide: left
  fromSlot: 0.25       # optional position along the face, 0..1 (default 0.5)
  toSlot: 0.5
  via: [[701, 228], [560, 228]]   # optional waypoints; elbows are inserted to keep segments orthogonal
  id: e_api_fn         # optional; used in lint messages and the .drawio
```

Auto-routing: straight when the endpoints line up (within 2 px), otherwise a Z-shape through the midpoint
(side→opposite side), an L-shape (side→top/bottom), or a U-shape (same side). Anchors are on the icon
image itself, not its caption — so an edge leaving the bottom of an icon with a caption below will cross
the caption (lint reports it).

## Outputs

`archdiagram.py spec --out-dir DIR [--name NAME] [--strict] [--no-svg]` writes `NAME.drawio` and
`NAME.svg`, prints lint findings, and with `--strict` exits non-zero if there are any.
