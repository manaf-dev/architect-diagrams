---
name: architecture-diagrams
description: Design and render professional, icon-accurate architecture diagrams — cloud (AWS, Azure, GCP), Kubernetes, data platforms (Microsoft Fabric, Power BI, Databricks, Snowflake), SaaS and on-prem — as an editable draw.io file plus an SVG/PNG ready for READMEs, docs and slides. Uses real vendor icons (never guessed), a planned grid layout, automatic layout linting and a render-and-look loop. Use this whenever the user asks to draw, design, diagram or visualise an architecture, solution design, system/infrastructure/data-platform/pipeline/deployment/network topology, "reference architecture", "architecture for the README", or wants a diagram with AWS/Azure/GCP/Fabric/vendor icons — even if they don't mention draw.io. Prefer it over generic diagram skills whenever vendor icons or a polished architecture picture are involved; use the plain drawio skill for flowcharts, UML, ER or academic figures without vendor icons.
license: MIT (bundled icon catalogs and icons keep their own licences - see THIRD_PARTY_NOTICES.md in the repo)
compatibility: Needs Python 3.10+ and a shell to run its scripts (Claude Code, Codex, Cursor, Gemini CLI and similar agents); PyYAML for YAML specs; Edge/Chrome/Chromium for PNG previews; draw.io Desktop or internet access to render native AWS/Kubernetes stencils.
---

# Architecture diagrams with real icons

Good architecture diagrams come from four things working together. Skipping any one is what makes
agent-drawn diagrams look amateur:

1. **Real icons, resolved — never guessed.** Every icon reference is looked up in a catalog or library and
   fails loudly if it does not exist.
2. **A planned layout.** One straight main flow, bands for secondary concerns, nested boundaries, an 8 px grid.
   Coordinates are chosen deliberately, not left to an auto-layouter.
3. **An objective check, then a visual check.** `archdiagram.py` lints overlaps, edges through captions, labels on
   borders, cramped arrowheads and shared attachment points. Then you render to PNG and actually *look* at it.
4. **Two outputs.** An editable `.drawio` (icons embedded, opens anywhere) and an image for docs.

Scripts live in `scripts/` next to this file. `${CLAUDE_SKILL_DIR}` below means **the folder that contains this
SKILL.md** — Claude Code fills it in automatically; in other agents substitute that folder's path yourself.
They need Python 3.10+; YAML specs need PyYAML (`pip install pyyaml`) — or write the spec as JSON. Rendering needs
Edge/Chrome/Chromium (headless) and, for native stencils, either draw.io Desktop or network access to
viewer.diagrams.net.

## Workflow

### 1. Model the system before drawing

List, in plain text: the **components**; the **boundaries** that contain them (account/subscription,
region, VPC/VNet, cluster, workspace, lakehouse, on-prem site); the **flows** between them and their kind
(data, control/orchestration, async/event, alert, sync/CI); the **sources** (left edge) and **consumers**
(right edge). If you are in a codebase, derive this from what is actually there — IaC (Terraform, Bicep,
CloudFormation, CDK), pipeline definitions, docker-compose/Helm, Fabric item folders, app config — rather
than from assumptions. Ask the user only for things you cannot discover.

### 2. Resolve an icon for every component

```bash
python ${CLAUDE_SKILL_DIR}/scripts/icons.py search lambda --set aws4
python ${CLAUDE_SKILL_DIR}/scripts/icons.py search "function apps"          # no --set: every catalog, library and logo set
python ${CLAUDE_SKILL_DIR}/scripts/icons.py list-lib fabric-artifacts        # browse a draw.io library
python ${CLAUDE_SKILL_DIR}/scripts/icons.py show "stencil:gcp2/Cloud Run"    # check what a ref resolves to
python ${CLAUDE_SKILL_DIR}/scripts/icons.py preview <ref> <ref> ... --out sheet.svg   # contact sheet; render it and look
```

Reference forms (details and vendor notes in `references/icon-sources.md`):

| Ref | Source | Renders in SVG? |
|---|---|---|
| `stencil:aws4/Lambda`, `stencil:kubernetes/Pod` | draw.io native stencils (bundled catalogs: AWS 952, K8s 78) | placeholder; use PNG via render.py |
| `stencil:gcp2/BigQuery` | GCP product icons (embedded SVG variant preferred) | yes |
| `drawio:azure2/compute/Function_Apps.svg` | draw.io's SVG sets: Azure (704), Microsoft/mscae, IBM, SAP, AD… | yes |
| `lib:fabric-artifacts#Lakehouse` | any draw.io icon library XML (aliases: fabric-core, fabric-artifacts, fabric-datasources, azure-core, azure-devops, microsoft-platforms) or a path/URL | yes |
| `simpleicons:snowflake` | 3,296 SaaS/OSS brand logos (GitHub, Snowflake, Databricks, Kafka…) in brand colour | yes |
| `svg:path/or/https-url.svg` | any SVG/PNG — official asset packs, your organisation's icons | yes |

Use the vendor's own icon for vendor services. Use a plain `box` for things that have no vendor identity
(your own services, scripts, "Business users" if no icon fits) — a fake or mismatched icon is worse than a
clean box. Search results show exact titles; copy them, don't retype from memory. When several candidates fit (old vs
current artwork such as Azure AD vs Entra ID, duplicates across sets, a vendor set vs a community library),
build a `preview` sheet, render it and pick by eye — vendor icons get redesigned and file names lag behind.

### 3. Plan the layout on a grid

Read `references/design-rules.md` before placing anything — it is short and it is where the quality comes
from. The core pattern:

- **Main row:** the primary data/request path runs left → right along one fixed `y`, so its edges are
  straight lines. Sources on the left, consumers on the right.
- **Bands:** orchestration/control above the main row; ops, DevOps, governance, observability below.
- **Boundaries:** nested `group`s with an icon + title in the top-left; keep ~48 px of header room.
- **Rhythm:** icons 44–52 px, columns ≥ 150 px apart when icons have captions, everything on an 8 px grid.
- **Captions:** bold name + 1–2 short detail lines (service type, key setting). The side a caption sits on
  must be free of edges — move the caption (`labelPos`) or the edge, never let a line cut through text.

Sketch the grid (columns x-positions, row y-positions) before writing coordinates.

### 4. Write the spec

YAML or JSON; full schema in `references/spec-format.md`. Start from the closest example:
`examples/fabric-medallion.yaml` (nested boundaries, medallion zones, orchestration band, Git/CI band),
`examples/aws-serverless.yaml` (native stencils, event fan-out, analytics lane) or
`examples/azure-web-app.yaml` (identity, edge/WAF, secrets, telemetry and CI/CD around one busy main row).

Element types: `group` (boundary), `zone` (layer card with header/items/footer), `icon`, `box`, `text`.
Edge kinds: `data`, `control`, `async`, `alert`, `telemetry`, `deploy` (one-way CI/CD), `sync` (two-way only),
`optional` — each has its own colour/dash, and the legend is generated from the kinds you use (add your own
with `edgeKinds:`). Edges auto-route orthogonally; set `fromSide`/`toSide`,
`fromSlot`/`toSlot` (0.25/0.5/0.75) and `via` waypoints when you need control.

### 5. Build and lint

```bash
python ${CLAUDE_SKILL_DIR}/scripts/archdiagram.py docs/architecture/system.yaml --out-dir docs/architecture
```

Fix every `LINT` line before looking further — each one is something a reader would notice:

| Lint says | Usual fix |
|---|---|
| `edge … passes through caption of X` | move X's caption (`labelPos: right/left/above`) or leave X from another side |
| `edge … passes through <element>` | add `via` waypoints around it, or move the element off the corridor |
| `label … sits on the border of group` / `overlaps` | move the label with `labelAt`, shorten it, or widen the gap |
| `share the same attachment point` | spread with `fromSlot`/`toSlot` 0.25 / 0.5 / 0.75 |
| `last segment is N px` | move the target or the elbow so the final straight run is ≥ 30 px |
| `does not fit` / `wider than the zone` | widen the element or shorten text — never shrink fonts below 10 px |
| `run on top of each other` | give the edges different slots or a separate corridor |
| `edges … cross at` | reroute with slots/`via`; keep it only if unavoidable, at a right angle, in open space |

Text widths are estimated, so treat a borderline warning as "check this in the render", not gospel.

### 6. Render and look

```bash
python ${CLAUDE_SKILL_DIR}/scripts/render.py docs/architecture/system.svg /tmp/preview.png         # all-embedded icons
python ${CLAUDE_SKILL_DIR}/scripts/render.py docs/architecture/system.drawio /tmp/preview.png      # native stencils / exact draw.io look
```

Both keep the full canvas framing (the `.drawio` carries an invisible, locked canvas frame).

Open the PNG (Read it) and review it as the reader will: Is the main path obvious within two seconds? Are
the boundaries meaningful? Is whitespace balanced, or is one corner crowded? Do colours encode meaning
consistently? Does every arrow have a clear direction and kind? Iterate on the spec until lint is clean
**and** the picture reads well. Two or three iterations is normal.

If the `drawio` skill is installed, its validator is a useful extra check:
`node <drawio-skill>/scripts/cli.js file.drawio --input-format drawio --validate`. It counts every text cell
as a node and does not read exit points back from `.drawio` files, so treat "too many nodes" and
"shared corridor" warnings on these diagrams as noise when the lint above is clean.

### 7. Deliver

- Put the spec, `.drawio` and image together (e.g. `docs/architecture/`) so the next edit starts from the
  spec, not from pixels.
- Image for docs: the `.svg` when every icon is embedded (crisp, small, GitHub renders it); otherwise a PNG
  from `render.py file.drawio out.png --scale 2`.
- README snippet: `![Architecture](docs/architecture/system.svg)` plus a link to the `.drawio` source.
- Keep the `credits` line for icon packs that ask for attribution, and mention licences when publishing.

## Gotchas this skill already handles (don't fight them)

- draw.io style strings use `;` as a separator, so embedded icons are written as `data:image/svg+xml,<base64>`
  without `;base64` — the format draw.io itself uses.
- Icon captions get `whiteSpace=nowrap`; otherwise draw.io wraps them to the icon's width.
- Native stencils (AWS, Kubernetes) only render inside draw.io, so the standalone SVG shows labelled
  placeholders for them and render.py uses draw.io's own renderer for the PNG.
- The viewer-based renderer downloads draw.io's viewer script; the diagram itself stays in a local page.
  For confidential diagrams prefer draw.io Desktop (fully offline, picked automatically when installed).
- Icon catalogs are parsed statically from draw.io's sidebar sources; never execute downloaded code to
  discover icons. Refresh them with `python ${CLAUDE_SKILL_DIR}/scripts/icons.py build-catalogs`.
