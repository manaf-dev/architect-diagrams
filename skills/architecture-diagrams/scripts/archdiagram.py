#!/usr/bin/env python3
"""Build an iconified architecture diagram (.drawio + .svg) from a JSON/YAML spec, and lint its layout.

  python archdiagram.py spec.yaml --out-dir docs/architecture [--name my-arch] [--strict]

Outputs <name>.drawio (editable in draw.io, icons embedded) and <name>.svg (standalone vector image for
READMEs). Native draw.io stencils (stencil:aws4/...) render as labelled placeholders in the SVG; use
render.py on the .drawio to get the real look as PNG. See references/spec-format.md for the spec.
"""
from __future__ import annotations

import argparse
import json
import sys
from html import escape as hesc
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icons as iconlib  # noqa: E402

THEME = {
    "font": "Segoe UI, Inter, Helvetica, Arial, sans-serif",
    "text": "#1E293B", "muted": "#64748B", "border": "#CBD5E1", "background": "#FFFFFF",
    "group": "#2563EB", "groupFill": "#F5F9FF",
}
EDGE_KINDS = {
    "data":     {"color": "#1E293B", "dash": None,  "width": 2,   "both": False, "legend": "Data flow"},
    "control":  {"color": "#2563EB", "dash": "8 4", "width": 2,   "both": False, "legend": "Orchestration / control"},
    "alert":    {"color": "#DC2626", "dash": "8 4", "width": 2,   "both": False, "legend": "Alert / failure path"},
    "sync":     {"color": "#475569", "dash": None,  "width": 2,   "both": True,  "legend": "Two-way sync"},
    "deploy":   {"color": "#475569", "dash": "8 4", "width": 1.5, "both": False, "legend": "Deployment (CI/CD)"},
    "telemetry": {"color": "#0891B2", "dash": "6 3", "width": 1.5, "both": False, "legend": "Telemetry / logs"},
    "async":    {"color": "#7C3AED", "dash": "4 3", "width": 2,   "both": False, "legend": "Async / event"},
    "optional": {"color": "#94A3B8", "dash": "2 3", "width": 1.5, "both": False, "legend": "Optional / weak"},
}
GRID = 8
MIN_LAST_SEGMENT = 30


# --------------------------------------------------------------------------- text helpers

def lines_of(label, kind: str, theme: dict) -> list[dict]:
    """Normalise a label (str | list[str|dict]) into styled lines. First line is the name, the rest are details."""
    if label is None:
        return []
    raw = label.split("\n") if isinstance(label, str) else list(label)
    first = {"group": (15, 700), "box": (12, 700), "icon": (11, 600), "text": (12, 400)}.get(kind, (12, 700))
    out = []
    for i, ln in enumerate(raw):
        base = {"text": "", "size": first[0] if i == 0 else 10, "weight": first[1] if i == 0 else 400,
                "color": theme["text"] if i == 0 else theme["muted"], "mono": False}
        if kind == "text":
            base.update(size=first[0], weight=first[1], color=theme["text"])
        base.update({"text": ln} if isinstance(ln, str) else ln)
        out.append(base)
    return out


def text_width(ln: dict) -> float:
    k = 0.55 if ln.get("mono") else 0.54 if ln["weight"] >= 600 else 0.52  # average glyph width / font size (Consolas = 0.55em)
    return len(ln["text"]) * ln["size"] * k


def block_size(lines: list[dict], gap: float = 3) -> tuple[float, float]:
    if not lines:
        return 0, 0
    return max(text_width(l) for l in lines), sum(l["size"] + gap for l in lines) - gap


def html_label(lines: list[dict]) -> str:
    parts = []
    for ln in lines:
        css = f"font-size:{ln['size']}px;color:{ln['color']};"
        if ln["weight"] >= 600:
            css += "font-weight:bold;"
        if ln.get("mono"):
            css += "font-family:Consolas,Menlo,monospace;"
        parts.append(f'<span style="{css}">{hesc(ln["text"])}</span>')
    return "<br>".join(parts)


def snap(v: float) -> float:
    return round(v / GRID) * GRID


# --------------------------------------------------------------------------- model

class Diagram:
    def __init__(self, spec: dict, base_dir: Path):
        self.spec = spec
        self.theme = {**THEME, **spec.get("theme", {})}
        self.kinds = {k: {**v, **spec.get("edgeKinds", {}).get(k, {})} for k, v in EDGE_KINDS.items()}
        for k, v in spec.get("edgeKinds", {}).items():
            self.kinds.setdefault(k, {**EDGE_KINDS["data"], **v})
        canvas = spec.get("canvas", {})
        self.W, self.H = canvas.get("width", 1600), canvas.get("height", 900)
        self.aliases = spec.get("iconLibraries", {})
        self.base_dir = base_dir
        self.els: dict[str, dict] = {}
        self.order: list[dict] = []
        self.edges: list[dict] = []
        self.warnings: list[str] = []
        self._build()

    # ---- icons
    def icon(self, ref: str):
        if ref.startswith("svg:") and not ref[4:].startswith(("http://", "https://")):
            p = Path(ref[4:])
            ref = "svg:" + str(p if p.is_absolute() else (self.base_dir / p))
        return iconlib.resolve(ref, self.aliases)

    # ---- elements
    def _build(self):
        t = self.theme
        if self.spec.get("title"):
            self._add({"id": "_title", "type": "text", "x": 40, "y": 20, "w": self.W - 80, "h": 30,
                       "label": [{"text": self.spec["title"], "size": 22, "weight": 700}]})
        if self.spec.get("subtitle"):
            self._add({"id": "_subtitle", "type": "text", "x": 40, "y": 54, "w": self.W - 80, "h": 22,
                       "label": [{"text": self.spec["subtitle"], "size": 13, "weight": 400, "color": t["muted"]}]})
        for e in self.spec.get("elements", []):
            self._add(dict(e))
        for e in self.spec.get("edges", []):
            self._edge(dict(e))
        kinds_used = [k for k in self.kinds if any(e["kind"] == k for e in self.edges)]
        lg = self.spec.get("legend", {})
        if lg is not False and kinds_used:
            labels = {**{k: self.kinds[k]["legend"] for k in kinds_used}, **lg.get("labels", {})}
            items = [k for k in lg.get("order", kinds_used) if k in kinds_used]
            width = max(220, 80 + max(len(labels[k]) for k in items) * 6.4)
            self._add({"id": "_legend", "type": "legend", "x": lg.get("x", 40), "y": lg.get("y", self.H - 40 - (34 + 18 * len(items))),
                       "w": width, "h": 34 + 18 * len(items), "items": [(k, labels[k]) for k in items]})
        if self.spec.get("credits"):
            self._add({"id": "_credits", "type": "text", "x": self.W - 840, "y": self.H - 30, "w": 800, "h": 18, "align": "right",
                       "label": [{"text": self.spec["credits"], "size": 10, "weight": 400, "color": t["muted"]}]})

    def _add(self, e: dict):
        t, kind = self.theme, e.get("type", "box")
        if e["id"] in self.els:
            raise ValueError(f"duplicate element id {e['id']!r}")
        e["type"] = kind
        if kind == "icon":
            ic = self.icon(e["icon"])
            h = e.get("size", 48)
            w = round(h * ic.aspect)
            if "cx" in e:
                e["x"], e["y"] = e["cx"] - w / 2, e["cy"] - h / 2
            e.update(w=w, h=h, _icon=ic, _lines=lines_of(e.get("label"), "icon", t))
            e.setdefault("labelPos", "below")
        elif kind == "group":
            e["_lines"] = lines_of(e.get("label"), "group", t)
            e["_icon"] = self.icon(e["icon"]) if e.get("icon") else None
            e.setdefault("color", t["group"])
            e.setdefault("fill", t["groupFill"])
        elif kind == "zone":
            e.setdefault("headerHeight", 48)
            e["_lines"] = lines_of([{"text": e.get("title", ""), "size": 14, "weight": 700, "color": e.get("color", t["text"])}]
                                   + ([{"text": e["subtitle"], "size": 11, "weight": 400, "color": t["muted"]}] if e.get("subtitle") else []), "box", t)
        elif kind in ("box", "text"):
            e["_lines"] = lines_of(e.get("label"), kind, t)
            if e.get("icon"):
                e["_icon"] = self.icon(e["icon"])
        for k in ("x", "y", "w", "h"):
            if k not in e:
                raise ValueError(f"element {e['id']!r} needs {k} (icons accept cx/cy + size)")
        self.els[e["id"]] = e
        self.order.append(e)

    # ---- edges
    def anchor(self, el: dict, side: str, slot: float):
        x, y, w, h = el["x"], el["y"], el["w"], el["h"]
        return {"left": (x, y + h * slot), "right": (x + w, y + h * slot),
                "top": (x + w * slot, y), "bottom": (x + w * slot, y + h)}[side]

    def _auto_sides(self, a: dict, b: dict):
        ax, ay = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
        bx, by = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        if abs(bx - ax) >= abs(by - ay):
            return ("right", "left") if bx > ax else ("left", "right")
        return ("bottom", "top") if by > ay else ("top", "bottom")

    def _edge(self, e: dict):
        a, b = self.els[e["from"]], self.els[e["to"]]
        fs, ts = self._auto_sides(a, b)
        fs, ts = e.get("fromSide", fs), e.get("toSide", ts)
        p0 = self.anchor(a, fs, e.get("fromSlot", 0.5))
        p1 = self.anchor(b, ts, e.get("toSlot", 0.5))
        horiz = lambda s: s in ("left", "right")  # noqa: E731
        # near-aligned endpoints (< 2px apart) are meant to be straight: snap the source onto the target's line
        if not e.get("via"):
            if horiz(fs) and horiz(ts) and abs(p0[1] - p1[1]) < 2:
                p0 = (p0[0], p1[1])
            if not horiz(fs) and not horiz(ts) and abs(p0[0] - p1[0]) < 2:
                p0 = (p1[0], p0[1])
        pts = [p0]
        if e.get("via"):
            prev_h = horiz(fs)
            for v in [tuple(v) for v in e["via"]] + [p1]:
                last = pts[-1]
                if last[0] != v[0] and last[1] != v[1]:
                    pts.append((v[0], last[1]) if prev_h else (last[0], v[1]))
                    prev_h = not prev_h
                else:
                    prev_h = last[1] == v[1]
                pts.append(v)
        elif horiz(fs) and horiz(ts):
            if fs == ts:
                x = (max(p0[0], p1[0]) + 32) if fs == "right" else (min(p0[0], p1[0]) - 32)
                pts += [(x, p0[1]), (x, p1[1]), p1]
            elif p0[1] == p1[1]:
                pts.append(p1)
            else:
                mx = snap((p0[0] + p1[0]) / 2)
                pts += [(mx, p0[1]), (mx, p1[1]), p1]
        elif not horiz(fs) and not horiz(ts):
            if fs == ts:
                y = (max(p0[1], p1[1]) + 32) if fs == "bottom" else (min(p0[1], p1[1]) - 32)
                pts += [(p0[0], y), (p1[0], y), p1]
            elif p0[0] == p1[0]:
                pts.append(p1)
            else:
                my = snap((p0[1] + p1[1]) / 2)
                pts += [(p0[0], my), (p1[0], my), p1]
        elif horiz(fs):
            pts += [(p1[0], p0[1]), p1] if p1[0] != p0[0] and p1[1] != p0[1] else [p1]
        else:
            pts += [(p0[0], p1[1]), p1] if p1[0] != p0[0] and p1[1] != p0[1] else [p1]
        dedup = [pts[0]]
        for p in pts[1:]:
            if p != dedup[-1]:
                dedup.append(p)
        kind = e.get("kind", "data")
        if kind not in self.kinds:
            raise ValueError(f"edge {e['from']}->{e['to']}: unknown kind {kind!r} ({', '.join(self.kinds)})")
        lines = lines_of(e.get("label"), "text", self.theme)
        style = self.kinds[kind]
        for ln in lines:
            ln.update(size=ln.get("size", 10) if isinstance(e.get("label"), list) and isinstance(e["label"][0], dict) else 10)
            if ln["color"] == self.theme["text"]:
                ln["color"] = style["color"] if kind != "data" else self.theme["text"]
        edge = {"id": e.get("id", f"e{len(self.edges) + 1}_{e['from']}_{e['to']}"), "from": e["from"], "to": e["to"],
                "fromSide": fs, "toSide": ts, "fromSlot": e.get("fromSlot", 0.5), "toSlot": e.get("toSlot", 0.5),
                "pts": dedup, "kind": kind, "lines": lines}
        if lines:
            if e.get("labelAt"):
                edge["labelAt"] = tuple(e["labelAt"])
            else:
                segs = list(zip(dedup, dedup[1:]))
                (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
                lw, lh = block_size(lines)
                edge["labelAt"] = (((x0 + x1) / 2, y0 - lh / 2 - 6) if y0 == y1 else (x0 + lw / 2 + 8, (y0 + y1) / 2))
        self.edges.append(edge)

    # ----------------------------------------------------------------------- geometry for lint
    def label_box(self, el: dict):
        """Bounding box of an icon's caption."""
        lw, lh = block_size(el["_lines"])
        if not el["_lines"]:
            return None
        if el["labelPos"] == "right":
            return (el["x"] + el["w"] + 10, el["y"] + el["h"] / 2 - lh / 2, lw, lh)
        if el["labelPos"] == "left":
            return (el["x"] - 10 - lw, el["y"] + el["h"] / 2 - lh / 2, lw, lh)
        if el["labelPos"] == "above":
            return (el["x"] + el["w"] / 2 - lw / 2, el["y"] - 4 - lh, lw, lh)
        return (el["x"] + el["w"] / 2 - lw / 2, el["y"] + el["h"] + 4, lw, lh)

    def text_box(self, el: dict):
        lw, lh = block_size(el["_lines"])
        align = el.get("align", "left" if el["id"].startswith("_") else "center")
        x = el["x"] if align == "left" else el["x"] + el["w"] - lw if align == "right" else el["x"] + (el["w"] - lw) / 2
        return (x, el["y"] + (el["h"] - lh) / 2, lw, lh)

    def edge_label_box(self, e: dict):
        lw, lh = block_size(e["lines"])
        lx, ly = e["labelAt"]
        return (lx - lw / 2 - 4, ly - lh / 2 - 2, lw + 8, lh + 4)

    def solids(self):
        """(name, box, owner_id) for everything that must not be overlapped."""
        out = []
        for el in self.order:
            box = (el["x"], el["y"], el["w"], el["h"])
            if el["type"] == "icon":
                out.append((f"icon {el['id']}", box, el["id"]))
                lb = self.label_box(el)
                if lb:
                    out.append((f"caption of {el['id']}", lb, el["id"] + ":label"))
            elif el["type"] == "text":
                out.append((f"text {el['id']}", self.text_box(el), el["id"]))
            elif el["type"] != "group":
                out.append((f"{el['type']} {el['id']}", box, el["id"]))
        for e in self.edges:
            if e["lines"]:
                out.append((f"label of edge {e['id']}", self.edge_label_box(e), "edge:" + e["id"]))
        return out

    def lint(self) -> list[str]:
        w = []
        inter = lambda a, b, pad=0: (a[0] < b[0] + b[2] - pad and b[0] < a[0] + a[2] - pad and  # noqa: E731
                                     a[1] < b[1] + b[3] - pad and b[1] < a[1] + a[3] - pad)
        contains = lambda a, b: (a[0] <= b[0] and a[1] <= b[1] and a[0] + a[2] >= b[0] + b[2] and a[1] + a[3] >= b[1] + b[3])  # noqa: E731
        solids = self.solids()
        # 1. canvas bounds
        for name, b, _ in solids:
            if b[0] < 0 or b[1] < 0 or b[0] + b[2] > self.W or b[1] + b[3] > self.H:
                w.append(f"{name} extends outside the {self.W}x{self.H} canvas")
        # 2. overlaps between solids
        for i in range(len(solids)):
            for j in range(i + 1, len(solids)):
                (n1, b1, o1), (n2, b2, o2) = solids[i], solids[j]
                if o1.split(":")[0] == o2.split(":")[0]:
                    continue
                if inter(b1, b2, 1) and not contains(b1, b2) and not contains(b2, b1):
                    w.append(f"{n1} overlaps {n2}")
        # 2b. text that does not fit inside its own box / zone
        for el in self.order:
            if el["type"] == "box" and el["_lines"]:
                lw, lh = block_size(el["_lines"])
                if lw > el["w"] - 8 or lh > el["h"] - 8:
                    w.append(f"label of box {el['id']} (~{lw:.0f}x{lh:.0f}px) does not fit in {el['w']}x{el['h']}; widen the box or shorten the text")
            if el["type"] == "zone":
                mono = el.get("monoItems", True)
                for it in el.get("items", []):
                    iw = text_width({"text": "▸ " + it, "size": 11, "weight": 400, "mono": mono})
                    if iw > el["w"] - 20:
                        w.append(f"zone {el['id']} item {it!r} (~{iw:.0f}px) is wider than the zone ({el['w']}px)")
                rows = len(el.get("items", [])) * 18 + 12 + 14 * len(el.get("footer", [])) + 16
                if el["headerHeight"] + 8 + rows > el["h"]:
                    w.append(f"zone {el['id']} content (~{el['headerHeight'] + 8 + rows}px) is taller than the zone ({el['h']}px)")
        # 3. text crossing container borders (groups and zones)
        for el in self.order:
            if el["type"] not in ("group", "zone"):
                continue
            x, y, ww, hh = el["x"], el["y"], el["w"], el["h"]
            borders = [(x - 2, y - 2, ww + 4, 4), (x - 2, y + hh - 2, ww + 4, 4), (x - 2, y - 2, 4, hh + 4), (x + ww - 2, y - 2, 4, hh + 4)]
            for name, b, owner in solids:
                if owner == el["id"] or not (name.startswith(("caption", "label", "text"))):
                    continue
                if any(inter(b, br) for br in borders):
                    w.append(f"{name} sits on the border of {el['type']} {el['id']}")
        # 4. edges
        slots = {}
        segs_by_edge = {}
        for e in self.edges:
            pts = e["pts"]
            segs = list(zip(pts, pts[1:]))
            segs_by_edge[e["id"]] = segs
            for (x0, y0), (x1, y1) in segs:
                if x0 != x1 and y0 != y1:
                    w.append(f"edge {e['id']} has a diagonal segment ({x0},{y0})->({x1},{y1})")
            (x0, y0), (x1, y1) = segs[-1]
            if abs(x1 - x0) + abs(y1 - y0) < MIN_LAST_SEGMENT:
                w.append(f"edge {e['id']} last segment is {abs(x1 - x0) + abs(y1 - y0):.0f}px (<{MIN_LAST_SEGMENT}); arrowhead will crowd the target")
            for end, side, slot in ((e["from"], e["fromSide"], e["fromSlot"]), (e["to"], e["toSide"], e["toSlot"])):
                slots.setdefault((end, side, round(slot, 3)), []).append(e["id"])
            for name, b, owner in solids:
                base = owner.split(":")[0]
                if owner == "edge:" + e["id"] or (base in (e["from"], e["to"]) and not owner.endswith(":label")):
                    continue
                if owner.startswith("edge:"):
                    continue
                for (x0, y0), (x1, y1) in segs:
                    sb = (min(x0, x1), min(y0, y1), abs(x1 - x0) or 0.5, abs(y1 - y0) or 0.5)
                    if inter(sb, b, 1):
                        w.append(f"edge {e['id']} passes through {name}")
                        break
        for (el, side, slot), ids in slots.items():
            if len(ids) > 1:
                w.append(f"edges {', '.join(ids)} share the same attachment point ({el}.{side} @ {slot}); use fromSlot/toSlot 0.25/0.5/0.75")
        # 5. edge labels vs other edges' lines
        for e in self.edges:
            if not e["lines"]:
                continue
            lb = self.edge_label_box(e)
            for other, segs in segs_by_edge.items():
                if other == e["id"]:
                    continue
                for (x0, y0), (x1, y1) in segs:
                    sb = (min(x0, x1), min(y0, y1), abs(x1 - x0) or 0.5, abs(y1 - y0) or 0.5)
                    if inter(sb, lb, 1):
                        w.append(f"label of edge {e['id']} sits on edge {other}")
                        break
        # 6. collinear overlapping segments of different edges
        ids = list(segs_by_edge)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                for (a0, a1) in segs_by_edge[ids[i]]:
                    for (b0, b1) in segs_by_edge[ids[j]]:
                        if a0[1] == a1[1] == b0[1] == b1[1]:
                            lo, hi = max(min(a0[0], a1[0]), min(b0[0], b1[0])), min(max(a0[0], a1[0]), max(b0[0], b1[0]))
                        elif a0[0] == a1[0] == b0[0] == b1[0]:
                            lo, hi = max(min(a0[1], a1[1]), min(b0[1], b1[1])), min(max(a0[1], a1[1]), max(b0[1], b1[1]))
                        else:
                            continue
                        if hi - lo > 4:
                            w.append(f"edges {ids[i]} and {ids[j]} run on top of each other for {hi - lo:.0f}px")
        # 7. edges crossing each other (perpendicular segments intersecting away from shared endpoints)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                ei, ej = self.edges[i], self.edges[j]
                shared = {ei["from"], ei["to"]} & {ej["from"], ej["to"]}
                for (a0, a1) in segs_by_edge[ids[i]]:
                    for (b0, b1) in segs_by_edge[ids[j]]:
                        h, v = ((a0, a1), (b0, b1)) if a0[1] == a1[1] and b0[0] == b1[0] else \
                               ((b0, b1), (a0, a1)) if b0[1] == b1[1] and a0[0] == a1[0] else (None, None)
                        if h is None:
                            continue
                        x, y = v[0][0], h[0][1]
                        if (min(h[0][0], h[1][0]) + 2 < x < max(h[0][0], h[1][0]) - 2 and
                                min(v[0][1], v[1][1]) + 2 < y < max(v[0][1], v[1][1]) - 2) and not shared:
                            w.append(f"edges {ids[i]} and {ids[j]} cross at ({x:.0f},{y:.0f}); OK only if unavoidable, "
                                     "at a right angle, in open space - otherwise reroute with slots/via")
        seen, out = set(), []
        for x in w:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    # ----------------------------------------------------------------------- draw.io
    def to_drawio(self) -> str:
        t = self.theme
        font = t["font"]  # full stack, so systems without the first font fall back to sans-serif, not serif
        common = f"html=1;whiteSpace=wrap;fontFamily={font};"
        # invisible, locked canvas frame: keeps margins when draw.io crops exports/viewers to content bounds
        cells = [f'<mxCell id="_canvas" value="" style="rounded=0;fillColor=none;strokeColor=none;locked=1;selectable=0;" '
                 f'vertex="1" parent="1"><mxGeometry x="0" y="0" width="{self.W}" height="{self.H}" as="geometry"/></mxCell>']

        def vertex(cid, value, style, x, y, w, h):
            cells.append(f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(style)} vertex="1" parent="1">'
                         f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

        for el in self.order:
            k, x, y, w, h = el["type"], el["x"], el["y"], el["w"], el["h"]
            if k == "icon":
                pos = {"below": "labelPosition=center;verticalLabelPosition=bottom;align=center;verticalAlign=top;spacingTop=2;",
                       "right": "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=10;",
                       "left": "labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=10;",
                       "above": "labelPosition=center;verticalLabelPosition=top;align=center;verticalAlign=bottom;spacingBottom=2;"}[el["labelPos"]]
                vertex(el["id"], html_label(el["_lines"]),
                       el["_icon"].drawio_style() + f"html=1;whiteSpace=nowrap;fontFamily={font};labelBackgroundColor=none;" + pos, x, y, w, h)
            elif k == "group":
                dash = "dashed=1;dashPattern=8 4;" if el.get("dashed", False) else ""
                vertex(el["id"], "", f"rounded=1;arcSize={max(1, round(14 * 100 / min(w, h)))};{common}fillColor={el['fill']};"
                       f"strokeColor={el['color']};strokeWidth=1.5;{dash}", x, y, w, h)
                tx = x + 16
                if el.get("_icon"):
                    ih = el.get("iconSize", 30)
                    iw = round(ih * el["_icon"].aspect)
                    vertex(el["id"] + "_icon", "", el["_icon"].drawio_style(), x + 16, y + 12, iw, ih)
                    tx = x + 24 + iw
                if el["_lines"]:
                    lw, lh = block_size(el["_lines"])
                    vertex(el["id"] + "_label", html_label(el["_lines"]),
                           f"text;{common}align=left;verticalAlign=middle;whiteSpace=nowrap;", tx, y + 12, lw + 20, max(30, lh + 4))
            elif k == "zone":
                hd = el["headerHeight"]
                vertex(el["id"], html_label(el["_lines"]),
                       f"swimlane;startSize={hd};rounded=1;arcSize=6;{common}fillColor={el.get('headerFill', '#EEF2F7')};"
                       f"swimlaneFillColor={el.get('fill', '#FFFFFF')};strokeColor={el.get('color', t['border'])};strokeWidth=1.5;"
                       "collapsible=0;align=center;verticalAlign=middle;", x, y, w, h)
                rows = [("▸ " if el.get("monoItems", True) else "• ", it, True) for it in el.get("items", [])]
                if rows:
                    value = "<br>".join(f'<span style="font-size:11px;color:{t["text"]};'
                                        + ("font-family:Consolas,Menlo,monospace;" if el.get("monoItems", True) else "")
                                        + f'">{hesc(b + s)}</span>' for b, s, _ in rows)
                    vertex(el["id"] + "_items", value, f"text;{common}align=left;verticalAlign=top;spacingLeft=14;spacingTop=4;",
                           x, y + hd + 8, w, 18 * len(rows) + 12)
                if el.get("footer"):
                    value = "<br>".join(f'<span style="font-size:10px;color:{t["muted"]};">{hesc(s)}</span>' for s in el["footer"])
                    vertex(el["id"] + "_footer", value, f"text;{common}align=left;verticalAlign=bottom;spacingLeft=14;spacingBottom=8;",
                           x, y + h - 14 * len(el["footer"]) - 20, w, 14 * len(el["footer"]) + 16)
            elif k == "box":
                dash = "dashed=1;dashPattern=8 4;" if el.get("dashed") else ""
                vertex(el["id"], html_label(el["_lines"]),
                       f"rounded=1;arcSize={max(1, round(el.get('radius', 10) * 100 / min(w, h)))};{common}fillColor={el.get('fill', '#FFFFFF')};"
                       f"strokeColor={el.get('color', '#475569')};strokeWidth=1.5;{dash}align=center;verticalAlign=middle;", x, y, w, h)
            elif k == "text":
                align = el.get("align", "left" if el["id"].startswith("_") else "center")
                vertex(el["id"], html_label(el["_lines"]), f"text;{common}align={align};verticalAlign=middle;", x, y, w, h)
            elif k == "legend":
                vertex(el["id"], "", f"rounded=1;arcSize=8;fillColor=#FFFFFF;strokeColor={t['border']};", x, y, w, h)
                vertex(el["id"] + "_t", "Legend", f"text;html=1;fontStyle=1;fontSize=11;fontColor={t['text']};align=left;verticalAlign=middle;",
                       x + 12, y + 4, 100, 18)
                for i, (kind, label) in enumerate(el["items"]):
                    ly = y + 30 + i * 18 + 6
                    s = self.kinds[kind]
                    st = (f"endArrow=block;endFill=1;html=1;strokeColor={s['color']};strokeWidth={s['width']};"
                          + (f"dashed=1;dashPattern={s['dash']};" if s["dash"] else "") + ("startArrow=block;startFill=1;" if s["both"] else ""))
                    cells.append(f'<mxCell id="{el["id"]}_e{i}" style="{st}" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                                 f'<mxPoint x="{x + 14}" y="{ly}" as="sourcePoint"/><mxPoint x="{x + 58}" y="{ly}" as="targetPoint"/></mxGeometry></mxCell>')
                    vertex(f"{el['id']}_l{i}", hesc(label), f"text;html=1;fontSize=11;fontColor={t['text']};align=left;verticalAlign=middle;",
                           x + 66, ly - 9, w - 70, 18)

        for e in self.edges:
            a, b = self.els[e["from"]], self.els[e["to"]]
            (sx, sy), (tx, ty) = e["pts"][0], e["pts"][-1]
            s = self.kinds[e["kind"]]
            style = (f"edgeStyle=none;html=1;rounded=0;endArrow=block;endFill=1;strokeColor={s['color']};strokeWidth={s['width']};"
                     f"exitX={(sx - a['x']) / a['w']:.4f};exitY={(sy - a['y']) / a['h']:.4f};exitDx=0;exitDy=0;"
                     f"entryX={(tx - b['x']) / b['w']:.4f};entryY={(ty - b['y']) / b['h']:.4f};entryDx=0;entryDy=0;"
                     f"fontFamily={font};labelBackgroundColor=#FFFFFF;"
                     + (f"dashed=1;dashPattern={s['dash']};" if s["dash"] else "") + ("startArrow=block;startFill=1;" if s["both"] else ""))
            pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in e["pts"][1:-1])
            off = ""
            if e["lines"]:
                mx, my = _midpoint(e["pts"])
                lx, ly = e["labelAt"]
                off = f'<mxPoint x="{lx - mx}" y="{ly - my}" as="offset"/>'
            cells.append(f'<mxCell id={quoteattr(e["id"])} value={quoteattr(html_label(e["lines"]))} style={quoteattr(style)} edge="1" parent="1" '
                         f'source={quoteattr(e["from"])} target={quoteattr(e["to"])}><mxGeometry relative="1" as="geometry">'
                         + (f'<Array as="points">{pts}</Array>' if pts else "") + off + "</mxGeometry></mxCell>")
        name = self.spec.get("title", "Architecture")
        return (f'<mxfile host="archdiagram" type="device"><diagram id="architecture" name={quoteattr(name[:60])}>'
                f'<mxGraphModel dx="{self.W}" dy="{self.H}" grid="1" gridSize="{GRID}" guides="1" tooltips="1" connect="1" arrows="1" '
                f'fold="1" page="1" pageScale="1" pageWidth="{self.W}" pageHeight="{self.H}" background="{t["background"]}" math="0" shadow="0">'
                '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")

    # ----------------------------------------------------------------------- SVG
    def to_svg(self) -> tuple[str, int]:
        t = self.theme
        placeholders = 0
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{self.W}" height="{self.H}" '
               f'viewBox="0 0 {self.W} {self.H}" font-family="{t["font"]}">',
               f"<title>{hesc(self.spec.get('title', 'Architecture diagram'))}</title><defs>"]
        for name, s in self.kinds.items():
            svg.append(f'<marker id="m_{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                       f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{s["color"]}"/></marker>')
        svg.append("</defs>")
        svg.append(f'<rect width="{self.W}" height="{self.H}" fill="{t["background"]}"/>')

        def text_block(lines, x, y, anchor="middle", gap=3):
            out, cy = [], y
            for ln in lines:
                cy += ln["size"]
                fam = ' font-family="Consolas, Menlo, monospace"' if ln.get("mono") else ""
                out.append(f'<text x="{x:.1f}" y="{cy:.1f}" text-anchor="{anchor}" font-size="{ln["size"]}" '
                           f'font-weight="{ln["weight"]}" fill="{ln["color"]}"{fam}>{hesc(ln["text"])}</text>')
                cy += gap
            return out

        def image(ic, x, y, w, h, title=""):
            nonlocal placeholders
            if ic.kind == "image":
                return [f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{ic.data_uri}" xlink:href="{ic.data_uri}"/>']
            placeholders += 1
            return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#F1F5F9" stroke="#94A3B8" stroke-dasharray="3 2"/>',
                    f'<text x="{x + w / 2}" y="{y + h / 2 + 3}" text-anchor="middle" font-size="8" fill="#64748B">{hesc((ic.title or title)[:14])}</text>']

        for el in self.order:
            k, x, y, w, h = el["type"], el["x"], el["y"], el["w"], el["h"]
            if k == "group":
                dash = ' stroke-dasharray="8 4"' if el.get("dashed", False) else ""
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{el["fill"]}" stroke="{el["color"]}" stroke-width="1.5"{dash}/>')
                tx = x + 16
                if el.get("_icon"):
                    ih = el.get("iconSize", 30)
                    iw = round(ih * el["_icon"].aspect)
                    svg += image(el["_icon"], x + 16, y + 12, iw, ih)
                    tx = x + 24 + iw
                lw, lh = block_size(el["_lines"])
                svg += text_block(el["_lines"], tx, y + 12 + (30 - lh) / 2 - 1, anchor="start")
            elif k == "zone":
                hd, col = el["headerHeight"], el.get("color", t["border"])
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{el.get("fill", "#FFFFFF")}" stroke="{col}" stroke-width="1.5"/>')
                svg.append(f'<path d="M{x},{y + hd} V{y + 10} Q{x},{y} {x + 10},{y} H{x + w - 10} Q{x + w},{y} {x + w},{y + 10} V{y + hd} Z" '
                           f'fill="{el.get("headerFill", "#EEF2F7")}" stroke="{col}" stroke-width="1.5"/>')
                lw, lh = block_size(el["_lines"])
                svg += text_block(el["_lines"], x + w / 2, y + (hd - lh) / 2 - 2)
                cy = y + hd + 8 + 4
                mono = el.get("monoItems", True)
                for it in el.get("items", []):
                    cy += 11 + 7
                    fam = ' font-family="Consolas, Menlo, monospace"' if mono else ""
                    svg.append(f'<text x="{x + 14}" y="{cy}" font-size="11" fill="{t["text"]}"{fam}>{hesc(("▸ " if mono else "• ") + it)}</text>')
                fy = y + h - 8 - 14 * len(el.get("footer", []))
                for s in el.get("footer", []):
                    fy += 12
                    svg.append(f'<text x="{x + 14}" y="{fy}" font-size="10" fill="{t["muted"]}">{hesc(s)}</text>')
                    fy += 2
            elif k == "box":
                dash = ' stroke-dasharray="8 4"' if el.get("dashed") else ""
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{el.get("radius", 10)}" fill="{el.get("fill", "#FFFFFF")}" '
                           f'stroke="{el.get("color", "#475569")}" stroke-width="1.5"{dash}/>')
                lw, lh = block_size(el["_lines"])
                svg += text_block(el["_lines"], x + w / 2, y + (h - lh) / 2 - 2)
            elif k == "icon":
                svg += image(el["_icon"], x, y, w, h, el["_lines"][0]["text"] if el["_lines"] else "")
                lb = self.label_box(el)
                if lb:
                    if el["labelPos"] in ("right", "left"):
                        svg += text_block(el["_lines"], lb[0], lb[1] - 1, anchor="start")
                    else:
                        svg += text_block(el["_lines"], x + w / 2, lb[1] - 2)
            elif k == "text":
                bx, by, bw, bh = self.text_box(el)
                align = el.get("align", "left" if el["id"].startswith("_") else "center")
                anchor, tx = {"left": ("start", el["x"]), "right": ("end", el["x"] + el["w"]), "center": ("middle", el["x"] + el["w"] / 2)}[align]
                svg += text_block(el["_lines"], tx, by - 2, anchor=anchor)
            elif k == "legend":
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#FFFFFF" stroke="{t["border"]}"/>')
                svg.append(f'<text x="{x + 12}" y="{y + 18}" font-size="11" font-weight="700" fill="{t["text"]}">Legend</text>')
                for i, (kind, label) in enumerate(el["items"]):
                    s, ly = self.kinds[kind], y + 30 + i * 18 + 6
                    dash = f' stroke-dasharray="{s["dash"]}"' if s["dash"] else ""
                    ms = f' marker-start="url(#m_{kind})"' if s["both"] else ""
                    svg.append(f'<line x1="{x + 14}" y1="{ly}" x2="{x + 58}" y2="{ly}" stroke="{s["color"]}" stroke-width="{s["width"]}"{dash} '
                               f'marker-end="url(#m_{kind})"{ms}/>')
                    svg.append(f'<text x="{x + 66}" y="{ly + 4}" font-size="11" fill="{t["text"]}">{hesc(label)}</text>')

        for e in self.edges:
            s = self.kinds[e["kind"]]
            pts = " ".join(f"{x},{y}" for x, y in e["pts"])
            dash = f' stroke-dasharray="{s["dash"]}"' if s["dash"] else ""
            ms = f' marker-start="url(#m_{e["kind"]})"' if s["both"] else ""
            svg.append(f'<polyline points="{pts}" fill="none" stroke="{s["color"]}" stroke-width="{s["width"]}"{dash} marker-end="url(#m_{e["kind"]})"{ms}/>')
            if e["lines"]:
                bx, by, bw, bh = self.edge_label_box(e)
                svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{t["background"]}" fill-opacity="0.92" rx="3"/>')
                svg += text_block(e["lines"], e["labelAt"][0], by + 1)
        svg.append("</svg>")
        return "\n".join(svg), placeholders


def _midpoint(pts):
    segs = list(zip(pts, pts[1:]))
    total = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segs)
    half = total / 2
    for a, b in segs:
        L = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if half <= L:
            r = half / L if L else 0
            return (a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r)
        half -= L
    return pts[-1]


def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit("PyYAML is not installed: `pip install pyyaml`, or write the spec as .json")
        return yaml.safe_load(text)
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--name", help="output base name (default: spec file name)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero when lint finds problems")
    ap.add_argument("--no-svg", action="store_true")
    a = ap.parse_args()
    spec_path = Path(a.spec)
    d = Diagram(load_spec(spec_path), spec_path.parent)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or spec_path.stem.replace(".spec", "")
    (out / f"{name}.drawio").write_text(d.to_drawio(), encoding="utf-8")
    print(f"wrote {out / (name + '.drawio')}")
    if not a.no_svg:
        svg, placeholders = d.to_svg()
        (out / f"{name}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote {out / (name + '.svg')}" + (f"  ({placeholders} native stencil(s) drawn as placeholders - "
                                                  "render the .drawio with render.py for the real look)" if placeholders else ""))
    warnings = d.lint()
    print(f"{len(d.order)} elements, {len(d.edges)} edges")
    if warnings:
        print(f"LINT: {len(warnings)} issue(s)")
        for w in warnings:
            print("  - " + w)
        if a.strict:
            sys.exit(1)
    else:
        print("LINT: clean")


if __name__ == "__main__":
    main()
