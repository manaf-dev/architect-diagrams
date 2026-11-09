#!/usr/bin/env python3
"""Render diagrams to PNG so you can *look* at them before delivering.

  python render.py file.svg out.png [--scale 2]
  python render.py file.drawio out.png [--engine auto|desktop|viewer] [--scale 2]

SVG -> PNG uses a headless Chromium browser (Edge or Chrome).
.drawio -> PNG uses draw.io's own renderer, so native stencils (AWS/GCP/Kubernetes) look exactly as in draw.io:
  desktop  draw.io Desktop CLI, fully offline (preferred when installed)
  viewer   draw.io's public viewer script (viewer.diagrams.net) inside a local HTML page in headless Chromium.
           The diagram XML stays in the local page; only the viewer script is downloaded.
Set CHROME_PATH / DRAWIO_PATH to override executable discovery.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
BROWSER_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"]
DRAWIO = [
    r"C:\Program Files\draw.io\draw.io.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\draw.io\draw.io.exe"),
    "/Applications/draw.io.app/Contents/MacOS/draw.io",
]
DRAWIO_NAMES = ["drawio", "draw.io"]


def find(env: str, paths: list[str], names: list[str]) -> str | None:
    if os.environ.get(env):
        return os.environ[env]
    for p in paths:
        if Path(p).exists():
            return p
    for n in names:
        if shutil.which(n):
            return shutil.which(n)
    return None


def canvas_size(drawio_xml: str) -> tuple[int, int]:
    w = re.search(r'pageWidth="(\d+)"', drawio_xml)
    h = re.search(r'pageHeight="(\d+)"', drawio_xml)
    return (int(w.group(1)) if w else 1600, int(h.group(1)) if h else 900)


def screenshot(url: str, out: Path, w: int, h: int, scale: float, wait_ms: int = 0) -> None:
    browser = find("CHROME_PATH", BROWSERS, BROWSER_NAMES)
    if not browser:
        sys.exit("No Chromium-based browser found (Edge/Chrome/Chromium). Set CHROME_PATH.")
    with tempfile.TemporaryDirectory(prefix="archdiagram-") as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               f"--user-data-dir={profile}", f"--window-size={w},{h}", f"--force-device-scale-factor={scale}",
               f"--screenshot={out.resolve()}"]
        if wait_ms:
            cmd.append(f"--virtual-time-budget={wait_ms}")
        cmd.append(url)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    if not out.exists():
        sys.exit("Screenshot failed (browser produced no file).")


def render_svg(src: Path, out: Path, scale: float) -> None:
    head = src.read_text(encoding="utf-8", errors="ignore")[:2000]
    w = re.search(r'<svg[^>]*\swidth="([\d.]+)', head)
    h = re.search(r'<svg[^>]*\sheight="([\d.]+)', head)
    screenshot(src.resolve().as_uri(), out, int(float(w.group(1))) if w else 1600, int(float(h.group(1))) if h else 900, scale)


def render_drawio(src: Path, out: Path, scale: float, engine: str) -> None:
    xml = src.read_text(encoding="utf-8")
    if engine in ("auto", "desktop"):
        exe = find("DRAWIO_PATH", DRAWIO, DRAWIO_NAMES)
        if exe:
            subprocess.run([exe, "--export", "--format", "png", "--scale", str(scale), "--border", "0",
                            "--output", str(out.resolve()), str(src.resolve())],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if out.exists():
                print(f"rendered with draw.io Desktop -> {out}")
                return
        if engine == "desktop":
            sys.exit("draw.io Desktop not found (set DRAWIO_PATH) or export failed.")
    w, h = canvas_size(xml)
    cfg = {"xml": xml, "toolbar": "", "nav": False, "resize": False, "lightbox": False, "border": 0, "zoom": 1}
    page = ('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}'
            f'.mxgraph{{width:{w}px}}</style></head><body><div class="mxgraph" data-mxgraph="{html.escape(json.dumps(cfg), quote=True)}"></div>'
            '<script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script></body></html>')
    with tempfile.TemporaryDirectory(prefix="archdiagram-page-") as tmp:
        page_file = Path(tmp) / "view.html"
        page_file.write_text(page, encoding="utf-8")
        screenshot(page_file.as_uri(), out, w, h, scale, wait_ms=20000)
    print(f"rendered with draw.io viewer -> {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--engine", choices=["auto", "desktop", "viewer"], default="auto")
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    if out.exists():
        out.unlink()
    if src.suffix.lower() == ".svg":
        render_svg(src, out, a.scale)
        print(f"rendered SVG -> {out}")
    elif src.suffix.lower() in (".drawio", ".xml"):
        render_drawio(src, out, a.scale, a.engine)
    else:
        sys.exit("source must be .svg or .drawio")


if __name__ == "__main__":
    main()
