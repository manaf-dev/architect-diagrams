# Design rules for architecture diagrams

These rules are why a diagram reads as "designed" rather than "generated". Each has a reason — when a
situation isn't covered, reason from the purpose: the reader should grasp the main path in two seconds and
find any detail in ten.

## Composition

- **One main row.** Put the primary data/request path on a single horizontal line (same `cy` for icons,
  same vertical centre for zones). Straight arrows along one line are the fastest thing an eye can follow.
- **Direction = time/causality.** Left → right for flow; sources and producers on the left, consumers and
  people on the right. Don't make the reader trace arrows backwards.
- **Bands for secondary concerns.** Control plane / orchestration / identity above the main row;
  observability, CI/CD, Git, governance below it. Readers learn "top = who drives it, bottom = how it's run".
- **Boundaries carry meaning.** Use a `group` for each real boundary (account, subscription, region,
  VPC/VNet, cluster, workspace, storage account/lakehouse, on-prem site). Nest them; don't draw boundaries
  that aren't real. Put the boundary's own icon + name in its top-left and leave ~48 px of header room.
  Boundaries are **solid** by default; use `dashed: true` only for logical/virtual boundaries (a workspace,
  a trust zone) and never in the same colour as dashed control edges, or readers will confuse the two.
- **Layers as zones.** When a store has internal layers (Bronze/Silver/Gold, raw/curated/serving, staging/
  core/marts), show them as `zone` cards side by side with their key contents listed — it explains the data
  model without a second diagram.
- **Balance.** Aim for even whitespace; if one quadrant is crowded, widen the canvas or move a band rather
  than shrinking things. Typical canvases: 1400–1700 × 760–900 px.

## Grid and sizing

- 8 px grid for every coordinate. Pick column x-positions and row y-positions first, then place on them.
- Icons 44–52 px tall, all the same size within a diagram (aspect ratio preserved). Bigger icons look
  like clip-art; smaller ones lose detail.
- Columns ≥ 150 px apart when icons have captions below; ≥ 90 px when captions are to the side.
- Minimum text 10 px; names 11–12 px bold; boundary titles 13–15 px bold; title 22 px.

## Icons and captions

- Vendor icon for vendor services; a clean `box` for custom code, scripts and anything without a vendor
  identity. Never substitute a "similar-looking" icon from another vendor.
- Caption = **resource name** (bold, the actual name: `orders-api`, `lh_sales`) + 1–2 short muted lines
  (service type, one key fact: "Lambda · Python 3.12", "Direct Lake · 10 measures"). No sentences.
- The caption's side must be free of edges. Icons with vertical connections get `labelPos: right/left`
  (or `above`); icons on the main row keep captions below and connect left/right.
- **Busy main-row icons (edges on all four sides).** Put their captions `above`, keep the main flow on
  left/right, send control/identity partners out of the right face at slot 0.25 and up, and send ops traffic
  (telemetry, deploy) out of the bottom at slots 0.25 / 0.75. Decide this in the grid sketch: it is the most
  common layout problem in cloud diagrams.

## Edges

- Orthogonal only (horizontal/vertical segments). Diagonals read as mistakes.
- Encode **kind** with colour + dash, and keep it consistent: data = solid dark, control = dashed blue,
  async/event = dashed purple, alert = dashed red, sync/CI = slate with two arrowheads, optional = dotted grey.
  The legend lists only kinds that appear.
- One attachment point per edge per face: spread with slots 0.25 / 0.5 / 0.75. Fan-out from one component
  leaves from the same face at different slots and then splits — never from the exact same point.
- Final straight segment ≥ 30 px so the arrowhead is visible and clearly lands on its target.
- Edge labels: 1–2 words ("put order", "on failure", "Direct Lake"), placed beside the line in open space,
  never on a border, never on another edge. Skip labels that only repeat the target's caption.
- Avoid crossings. If two flows must cross, cross at right angles in open space, away from icons.

## Colour

- Neutral base (dark slate text, muted grey details, light grey borders). Colour is for meaning: edge kinds,
  layer zones (bronze/silver/gold tints), alerts. Vendor icons bring their own colour — don't add more.
- Boundary tints are very light (`#F5F9FF`, `#F8FAFC`); boundary strokes can use the vendor colour
  (AWS `#232F3E`, Azure `#0078D4`, GCP `#4285F4`, Fabric/OneLake teal `#0F766E`).

## Text in the picture

- Title (what system) + one-line subtitle (the story: "A → B → C, orchestrated by X").
- A legend whenever more than one edge kind appears. It is `34 + 18 x kinds` px tall and ~220–320 px wide;
  reserve that space (bottom-left by default) when planning the grid.
- A credits line when an icon pack's licence asks for attribution.
