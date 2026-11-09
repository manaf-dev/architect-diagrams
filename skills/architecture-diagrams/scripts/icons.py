#!/usr/bin/env python3
"""Find and resolve real vendor icons for architecture diagrams.

Icon reference syntax (used in diagram specs):

  stencil:<set>/<Title>      native draw.io stencil from a bundled catalog, e.g. stencil:aws4/Lambda,
                             stencil:gcp2/BigQuery, stencil:kubernetes/Pod  (append @N to pick the Nth match)
  drawio:<path>              SVG from draw.io's own icon folders (img/lib), embedded as data,
                             e.g. drawio:azure2/compute/Function_Apps.svg, drawio:mscae/Kubernetes.svg
  lib:<alias|path|url>#<Title>  icon from a draw.io library XML (<mxlibrary>), e.g. lib:fabric-artifacts#Lakehouse
  simpleicons:<slug>[#hex]   brand logo from Simple Icons (3,000+ SaaS/OSS brands) in its brand colour, e.g. simpleicons:snowflake
  svg:<path|url>             any SVG/PNG file, embedded as data
  style:<draw.io style>      raw draw.io style string (escape hatch)

CLI:
  icons.py search <words...> [--set aws4|gcp2|kubernetes|drawio|<lib alias/path/url>] [--limit 25]
  icons.py list-lib <alias|path|url>
  icons.py show <ref>                     resolve one reference and print what it becomes
  icons.py preview <ref> <ref>... [--out sheet.svg]   contact sheet to compare candidates side by side
  icons.py build-catalogs                 refresh bundled catalogs from github.com/jgraph/drawio

Stencil catalogs are parsed *statically* from draw.io's sidebar sources (no downloaded code is executed).
Downloads are cached in ~/.cache/archdiagram.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CATALOG_DIR = SKILL_DIR / "assets" / "catalogs"
CACHE_DIR = Path.home() / ".cache" / "archdiagram"
DRAWIO_RAW = "https://raw.githubusercontent.com/jgraph/drawio/dev/src/main/webapp"
FABRIC_PACK = ("https://raw.githubusercontent.com/astrzala/FabricToolset/main/"
               "Microsoft%20Fabric%20%26%20Azure%20Icon%20Pack/xml/")

# Well-known draw.io icon libraries (MIT-licensed community packs). Specs can add their own aliases.
LIBRARY_ALIASES = {
    "fabric-core": FABRIC_PACK + "Fabric_Core.xml",
    "fabric-artifacts": FABRIC_PACK + "Fabric_Artifacts.xml",
    "fabric-datasources": FABRIC_PACK + "Fabric_Datasources.xml",
    "fabric-black": FABRIC_PACK + "Fabric_Black.xml",
    "azure-core": FABRIC_PACK + "Azure_Core.xml",
    "azure-devops": FABRIC_PACK + "Azure_DevOps.xml",
    "microsoft-platforms": FABRIC_PACK + "Microsoft_Tool_and_Platforms.xml",
}

SIMPLE_ICONS_VERSION = "13.21.0"
SIMPLE_ICONS_CDN = f"https://cdn.jsdelivr.net/npm/simple-icons@{SIMPLE_ICONS_VERSION}"

STENCIL_SOURCES = {
    "aws4": "js/diagramly/sidebar/Sidebar-AWS4.js",
    "gcp2": "js/diagramly/sidebar/Sidebar-GCP2.js",
    "kubernetes": "js/diagramly/sidebar/Sidebar-Kubernetes.js",
}


@dataclass
class Icon:
    ref: str
    kind: str              # "image" (embedded data URI) or "stencil" (native draw.io style)
    title: str
    aspect: float          # width / height
    data_uri: str = ""     # data:image/svg+xml;base64,... (kind=image)
    style: str = ""        # draw.io style (kind=stencil)

    def drawio_style(self) -> str:
        """Style fragment for draw.io. Data URIs drop ';base64' because ';' separates style keys."""
        if self.kind == "image":
            mime, _, payload = self.data_uri.partition(",")
            mime = mime.replace("data:", "").replace(";base64", "")
            return f"shape=image;image=data:{mime},{payload};imageAspect=0;aspect=fixed;"
        return self.style if self.style.endswith(";") else self.style + ";"


# --------------------------------------------------------------------------- fetching / cache

def fetch(location: str, binary: bool = True):
    """Read a local path or an http(s) URL (cached)."""
    if re.match(r"^https?://", location):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1(location.encode()).hexdigest()[:16] + "_" + Path(urllib.parse.urlparse(location).path).name[-60:]
        cached = CACHE_DIR / key
        if not cached.exists():
            req = urllib.request.Request(location, headers={"User-Agent": "archdiagram-skill"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(50_000_000)
            cached.write_bytes(data)
        data = cached.read_bytes()
    else:
        data = Path(location).expanduser().read_bytes()
    return data if binary else data.decode("utf-8")


def _normalise_b64_uri(uri: str) -> str:
    """Re-encode a base64 data URI. draw.io sources sometimes omit '=' padding, which browsers reject."""
    head, _, payload = uri.partition(",")
    payload = re.sub(r"\s+", "", payload)
    data = base64.b64decode(payload + "=" * (-len(payload) % 4))
    return f"{head},{base64.b64encode(data).decode()}"


def to_data_uri(data: bytes, name: str) -> str:
    mime = mimetypes.guess_type(name)[0] or ("image/svg+xml" if data.lstrip()[:5] in (b"<?xml", b"<svg ") else "image/png")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def svg_aspect(data: bytes) -> float:
    head = data[:4000].decode("utf-8", "ignore")
    vb = re.search(r'viewBox\s*=\s*"\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', head)
    if vb and float(vb.group(2)):
        return float(vb.group(1)) / float(vb.group(2))
    w = re.search(r'<svg[^>]*\swidth\s*=\s*"([\d.]+)', head)
    h = re.search(r'<svg[^>]*\sheight\s*=\s*"([\d.]+)', head)
    if w and h and float(h.group(1)):
        return float(w.group(1)) / float(h.group(1))
    return 1.0


# --------------------------------------------------------------------------- draw.io libraries (<mxlibrary>)

def load_library(spec: str, aliases: dict | None = None) -> list[dict]:
    location = {**LIBRARY_ALIASES, **(aliases or {})}.get(spec, spec)
    text = fetch(location, binary=False)
    m = re.search(r"<mxlibrary>(.*)</mxlibrary>", text, re.S)
    if not m:
        raise ValueError(f"{spec}: not a draw.io library (<mxlibrary> not found)")
    return json.loads(m.group(1))


# --------------------------------------------------------------------------- stencil catalogs (static parse)

_TOKEN = re.compile(r"""\s*(?:(?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")|(?P<num>\d+(?:\.\d+)?)|(?P<id>[A-Za-z_$][\w$.]*)|(?P<op>[-+*/()]))""")


def _unescape(raw: str) -> str:
    out, i = [], 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            i += 1
            ch = {"n": "\n", "t": "\t", "r": ""}.get(raw[i], raw[i])
        out.append(ch)
        i += 1
    return "".join(out)


def _clean_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("-\n", "-")).strip()


def _eval(expr: str, env: dict):
    """Evaluate a JS expression made only of string/number literals, known variables, + - * / and ()."""
    toks, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            return None
        pos = m.end()
        kind, val = m.lastgroup, m.group(m.lastgroup)
        toks.append((kind, _unescape(val[1:-1]) if kind == "str" else float(val) if kind == "num" else val))
    i = 0

    def atom():
        nonlocal i
        kind, val = toks[i]
        i += 1
        if kind in ("str", "num"):
            return val
        if kind == "id":
            if val in env:
                return env[val]
            raise KeyError(val)
        if val == "(":
            v = add()
            i += 1
            return v
        if val == "-":
            return -atom()
        raise ValueError(val)

    def mul():
        nonlocal i
        v = atom()
        while i < len(toks) and toks[i][1] in ("*", "/"):
            op = toks[i][1]
            i += 1
            r = atom()
            v = v * r if op == "*" else v / r
        return v

    def add():
        nonlocal i
        v = mul()
        while i < len(toks) and toks[i][1] in ("+", "-"):
            op = toks[i][1]
            i += 1
            r = mul()
            if op == "+":
                v = f"{v}{r}" if isinstance(v, str) or isinstance(r, str) else v + r
            else:
                v = v - r
        return v

    try:
        v = add()
        return v if i == len(toks) else None
    except (KeyError, ValueError, TypeError, ZeroDivisionError, IndexError):
        return None


def _scan_until(text: str, pos: int, stops: str) -> int:
    depth, quote = 0, None
    while pos < len(text):
        ch = text[pos]
        if quote:
            if ch == "\\":
                pos += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return pos
            depth -= 1
        elif ch in stops and depth == 0:
            return pos
        pos += 1
    return pos


def _split_args(text: str, pos: int) -> list[str]:
    args = []
    while True:
        end = _scan_until(text, pos, ",")
        args.append(text[pos:end])
        if end >= len(text) or text[end] != ",":
            return args
        pos = end + 1


def parse_sidebar(js: str) -> list[dict]:
    """Extract {title, style, w, h} from a draw.io Sidebar-*.js file without executing it."""
    events = [(m.end(), "assign", m.group(1)) for m in
              re.finditer(r"(?:\bvar\s+|\blet\s+|\bconst\s+|[;{}\n,]\s*)([A-Za-z_$][\w$]*)\s*=\s*(?!=)", js)]
    events += [(m.end(), "call", None) for m in re.finditer(r"createVertexTemplateEntry\s*\(", js)]
    # GCP product cards embed real SVG icons: addGCP2UserProductCardSet(label, ..., icon) / addGCP2ProductCardSet(label, icon, ...)
    events += [(m.end(), "card", m.group(1)) for m in re.finditer(r"\.(addGCP2UserProductCardSet|addGCP2ProductCardSet)\s*\(", js)]
    env = {"mxConstants.STYLE_SHAPE": "shape"}
    out, seen = [], set()
    for pos, kind, name in sorted(events):
        if kind == "assign":
            val = _eval(js[pos:_scan_until(js, pos, ";,")], env)
            if val is None:
                env.pop(name, None)
            else:
                env[name] = val
            continue
        if kind == "card":
            args = _split_args(js, pos)
            label = _eval(args[0], env)
            icon_arg = args[8] if name == "addGCP2UserProductCardSet" and len(args) > 8 else args[1] if len(args) > 1 else ""
            b64 = _eval(icon_arg, env)
            if isinstance(label, str) and isinstance(b64, str) and b64.startswith("PHN2Zy"):
                title = _clean_title(label)
                if ("card", title) not in seen:
                    seen.add(("card", title))
                    out.append({"title": title, "image": _normalise_b64_uri("data:image/svg+xml;base64," + b64), "w": None, "h": None})
            continue
        args = _split_args(js, pos)
        if len(args) < 5:
            continue
        style = _eval(args[0], env)
        if not isinstance(style, str) or not style or style in seen:
            continue
        title = _eval(args[4], env)
        if not isinstance(title, str) or not title.strip():
            title = _eval(args[3], env) or ""
        w, h = _eval(args[1], env), _eval(args[2], env)
        seen.add(style)
        out.append({"title": _clean_title(str(title)), "style": style,
                    "w": round(w) if isinstance(w, (int, float)) else None,
                    "h": round(h) if isinstance(h, (int, float)) else None})
    return out


def build_catalogs() -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    for name, path in STENCIL_SOURCES.items():
        url = f"{DRAWIO_RAW}/{path}"
        icons = parse_sidebar(fetch(url, binary=False))
        (CATALOG_DIR / f"{name}.json").write_text(json.dumps({"set": name, "source": url, "icons": icons}), encoding="utf-8")
        print(f"{name}: {len(icons)} icons")
    tree = json.loads(fetch("https://api.github.com/repos/jgraph/drawio/git/trees/dev?recursive=1", binary=False))
    prefix = "src/main/webapp/img/lib/"
    paths = sorted(t["path"][len(prefix):] for t in tree["tree"]
                   if t["path"].startswith(prefix) and t["path"].lower().endswith(".svg"))
    (CATALOG_DIR / "drawio-images.json").write_text(json.dumps({"set": "drawio", "base": f"{DRAWIO_RAW}/img/lib/", "paths": paths}), encoding="utf-8")
    print(f"drawio images: {len(paths)} SVGs")
    data = json.loads(fetch(f"{SIMPLE_ICONS_CDN}/_data/simple-icons.json", binary=False))
    data = data.get("icons", data) if isinstance(data, dict) else data
    logos = [{"title": d["title"], "slug": d.get("slug") or simple_icons_slug(d["title"]), "hex": d.get("hex", "000000")} for d in data]
    (CATALOG_DIR / "simpleicons.json").write_text(json.dumps({"set": "simpleicons", "version": SIMPLE_ICONS_VERSION, "icons": logos}), encoding="utf-8")
    print(f"simple-icons: {len(logos)} brand logos")


def simple_icons_slug(title: str) -> str:
    """Port of simple-icons' titleToSlug."""
    import unicodedata
    t = title.lower()
    for a, b in {"+": "plus", ".": "dot", "&": "and", "đ": "d", "ħ": "h", "ı": "i", "ĸ": "k", "ŀ": "l", "ł": "l",
                 "ß": "ss", "ŧ": "t", "ø": "o"}.items():
        t = t.replace(a, b)
    t = unicodedata.normalize("NFD", t)
    return re.sub(r"[^a-z0-9]", "", t)


def load_catalog(name: str) -> dict:
    p = CATALOG_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"catalog {name!r} missing - run: python {Path(__file__).name} build-catalogs")
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- resolution

def resolve(ref: str, aliases: dict | None = None) -> Icon:
    scheme, _, rest = ref.partition(":")
    if scheme == "stencil":
        set_name, _, title = rest.partition("/")
        title, _, nth = title.partition("@")
        icons = load_catalog(set_name)["icons"]
        matches = [e for e in icons if e["title"].lower() == title.lower()]
        if not matches:
            close = [e["title"] for e in icons if title.lower() in e["title"].lower()][:8]
            raise KeyError(f"{ref}: no exact title match. Close: {close}")
        e = matches[int(nth) - 1 if nth else 0]
        if "image" in e:  # embedded SVG product icon (e.g. GCP product cards)
            uri = _normalise_b64_uri(e["image"])
            return Icon(ref, "image", e["title"], svg_aspect(base64.b64decode(uri.split(",", 1)[1])), data_uri=uri)
        aspect = (e["w"] / e["h"]) if e.get("w") and e.get("h") else 1.0
        return Icon(ref, "stencil", e["title"], aspect, style=e["style"])
    if scheme == "drawio":
        data = fetch(f"{DRAWIO_RAW}/img/lib/{urllib.parse.quote(rest)}")
        return Icon(ref, "image", Path(rest).stem.replace("_", " "), svg_aspect(data), data_uri=to_data_uri(data, rest))
    if scheme == "lib":
        lib, _, title = rest.rpartition("#")
        items = load_library(lib, aliases)
        hit = [i for i in items if i.get("title", "").lower() == title.lower()]
        if not hit:
            close = [i.get("title") for i in items if title.lower() in i.get("title", "").lower()][:8]
            raise KeyError(f"{ref}: not in library. Close: {close}")
        item = hit[0]
        if "data" not in item:
            raise ValueError(f"{ref}: library entry is a shape (xml), not an image; use its style via style:")
        uri = item["data"]
        if ";base64," not in uri:  # draw.io sometimes stores 'data:image/svg+xml,<b64>'
            mime, _, payload = uri.partition(",")
            uri = f"{mime};base64,{payload}"
        uri = _normalise_b64_uri(uri)
        aspect = (item["w"] / item["h"]) if item.get("w") and item.get("h") else 1.0
        return Icon(ref, "image", item.get("title", title), aspect, data_uri=uri)
    if scheme == "simpleicons":  # brand logo in its brand colour; override with simpleicons:<slug>#RRGGBB
        slug, _, colour = rest.partition("#")
        entry = next((e for e in load_catalog("simpleicons")["icons"] if e["slug"] == slug), None)
        if entry is None:
            raise KeyError(f"{ref}: unknown simple-icons slug (search: icons.py search <name> --set simpleicons)")
        svg = fetch(f"{SIMPLE_ICONS_CDN}/icons/{slug}.svg", binary=False)
        svg = svg.replace("<svg ", f'<svg fill="#{colour or entry["hex"]}" ', 1)
        data = svg.encode()
        return Icon(ref, "image", entry["title"], svg_aspect(data), data_uri=to_data_uri(data, slug + ".svg"))
    if scheme == "svg":
        data = fetch(rest)
        return Icon(ref, "image", Path(rest).stem, svg_aspect(data) if rest.lower().endswith(".svg") else 1.0,
                    data_uri=to_data_uri(data, rest))
    if scheme == "style":
        return Icon(ref, "stencil", "", 1.0, style=rest)
    raise ValueError(f"unknown icon reference {ref!r} (use stencil:, drawio:, lib:, simpleicons:, svg: or style:)")


# --------------------------------------------------------------------------- search

def _score(query: list[str], text: str) -> int:
    t = text.lower()
    if not all(q in t for q in query):
        return 0
    joined = " ".join(query)
    return 3 if t == joined else 2 if t.startswith(joined) else 1


K8S_ABBREVIATIONS = {
    "deployment": "deploy", "service": "svc", "ingress": "ing", "statefulset": "sts", "stateful set": "sts",
    "daemonset": "ds", "daemon set": "ds", "configmap": "cm", "config map": "cm", "persistent volume claim": "pvc",
    "persistent volume": "pv", "namespace": "ns", "horizontal pod autoscaler": "hpa", "autoscaler": "hpa",
    "service account": "sa", "replicaset": "rs", "replica set": "rs", "endpoints": "ep", "endpoint": "ep",
    "network policy": "netpol", "storage class": "sc", "cluster role binding": "crb", "cluster role": "c-role",
    "role binding": "rb", "custom resource": "crd", "scheduler": "sched", "volume": "vol", "kube-proxy": "k-proxy",
    "controller manager": "c-m", "cloud controller manager": "c-c-m", "resource quota": "quota", "limit range": "limits",
}


def search(words: list[str], set_name: str | None, limit: int, aliases: dict | None = None) -> list[tuple[str, str]]:
    q = [w.lower() for w in words]
    abbr = K8S_ABBREVIATIONS.get(" ".join(q)) if set_name in (None, "kubernetes") else None
    if abbr:  # Kubernetes icons are titled with official abbreviations (ING, SVC, Deploy, ...)
        hits = _search([abbr], "kubernetes", limit, aliases)
        rest = _search(q, set_name, limit, aliases)
        return (hits + [h for h in rest if h not in hits])[:limit]
    return _search(q, set_name, limit, aliases)


def _search(q: list[str], set_name: str | None, limit: int, aliases: dict | None = None) -> list[tuple[str, str]]:
    results = []
    sets = [set_name] if set_name else list(STENCIL_SOURCES) + ["drawio", "simpleicons"] + list(LIBRARY_ALIASES)
    for s in sets:
        if s == "simpleicons":
            for e in load_catalog("simpleicons")["icons"]:
                sc = _score(q, e["title"]) or _score(q, e["slug"])
                if sc:
                    results.append((sc - 1, f"simpleicons:{e['slug']}", f"brand logo - {e['title']}"))
            continue
        if s in STENCIL_SOURCES:
            for e in load_catalog(s)["icons"]:
                shape = re.findall(r"(?:resIcon|prIcon|shape)=mxgraph\.[\w]+\.([\w]+)", e.get("style", ""))
                sc = _score(q, e["title"]) or (_score(q, " ".join(shape).replace("_", " ")) and 1)
                if sc:
                    hint = "embedded SVG" if "image" in e else e["style"][-70:]
                    results.append((sc + (1 if "image" in e else 0), f"stencil:{s}/{e['title']}", hint))
        elif s == "drawio":
            for p in load_catalog("drawio-images")["paths"]:
                sc = _score(q, p.replace("_", " "))
                if sc:
                    results.append((sc, f"drawio:{p}", ""))
        else:
            try:
                items = load_library(s, aliases)
            except Exception as exc:  # an unreachable library must not break a global search
                if set_name:
                    raise
                print(f"(skipped library {s}: {exc})", file=sys.stderr)
                continue
            for item in items:
                sc = _score(q, item.get("title", ""))
                if sc:
                    results.append((sc, f"lib:{s}#{item.get('title')}", ""))
    results.sort(key=lambda r: (-r[0], len(r[1])))
    return [(r[1], r[2]) for r in results[:limit]]


def preview(refs: list[str], out: Path, cols: int = 6) -> int:
    """Write an SVG contact sheet of candidate icons (ref printed under each) to compare them visually."""
    from html import escape
    cell_w, cell_h, size = 220, 130, 56
    rows = (len(refs) + cols - 1) // cols
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{cols * cell_w}" '
             f'height="{rows * cell_h}" font-family="Segoe UI, Helvetica, Arial, sans-serif"><rect width="100%" height="100%" fill="#fff"/>']
    for i, ref in enumerate(refs):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        parts.append(f'<rect x="{x + 4}" y="{y + 4}" width="{cell_w - 8}" height="{cell_h - 8}" rx="8" fill="none" stroke="#E2E8F0"/>')
        try:
            ic = resolve(ref)
            w = round(size * ic.aspect)
            if ic.kind == "image":
                parts.append(f'<image x="{x + (cell_w - w) / 2}" y="{y + 16}" width="{w}" height="{size}" href="{ic.data_uri}" xlink:href="{ic.data_uri}"/>')
            else:
                parts.append(f'<rect x="{x + (cell_w - w) / 2}" y="{y + 16}" width="{w}" height="{size}" rx="6" fill="#F1F5F9" stroke="#94A3B8" stroke-dasharray="3 2"/>'
                             f'<text x="{x + cell_w / 2}" y="{y + 48}" text-anchor="middle" font-size="9" fill="#64748B">native stencil</text>')
        except Exception as exc:
            parts.append(f'<text x="{x + cell_w / 2}" y="{y + 48}" text-anchor="middle" font-size="10" fill="#DC2626">{escape(str(exc)[:40])}</text>')
        short = ref if len(ref) <= 38 else "…" + ref[-37:]
        parts.append(f'<text x="{x + cell_w / 2}" y="{y + 96}" text-anchor="middle" font-size="10" fill="#1E293B">{escape(short)}</text>')
    parts.append("</svg>")
    out.write_text("\n".join(parts), encoding="utf-8")
    return len(refs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("preview", help="contact sheet of candidate icons (SVG); render it with render.py to look")
    pv.add_argument("refs", nargs="+")
    pv.add_argument("--out", default="icon-preview.svg")
    s = sub.add_parser("search")
    s.add_argument("words", nargs="+")
    s.add_argument("--set")
    s.add_argument("--limit", type=int, default=25)
    l = sub.add_parser("list-lib")
    l.add_argument("library")
    sh = sub.add_parser("show")
    sh.add_argument("ref")
    sub.add_parser("build-catalogs")
    a = ap.parse_args()
    if a.cmd == "search":
        for ref, hint in search(a.words, a.set, a.limit):
            print(ref + (f"    ...{hint}" if hint else ""))
    elif a.cmd == "list-lib":
        for item in load_library(a.library):
            print(f"lib:{a.library}#{item.get('title')}   ({item.get('w')}x{item.get('h')})")
    elif a.cmd == "show":
        ic = resolve(a.ref)
        print(json.dumps({"ref": ic.ref, "kind": ic.kind, "title": ic.title, "aspect": round(ic.aspect, 3),
                          "style": ic.drawio_style()[:300] + ("..." if len(ic.drawio_style()) > 300 else "")}, indent=2))
    elif a.cmd == "build-catalogs":
        build_catalogs()
    elif a.cmd == "preview":
        n = preview(a.refs, Path(a.out))
        print(f"wrote {a.out} with {n} icons - render with: python {Path(__file__).parent / 'render.py'} {a.out} sheet.png")


if __name__ == "__main__":
    main()
