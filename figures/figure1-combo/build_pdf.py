#!/usr/bin/env python3
"""Render figure1-combo.svg to PDF with every embedded raster intact.

Two things break the obvious `magick`/`rsvg-convert`/Inkscape one-liner on this file:

1.  The pathology panels are data: URIs of 3.2, 3.0, 2.0 and 1.4 MB. libxml2 caps
    accumulated text/attribute content at 10 MB unless XML_PARSE_HUGE is set, and
    neither librsvg nor ImageMagick's SVG delegate sets it. The parse aborts partway
    through <defs>, so the pathology rasters silently vanish while everything that
    parsed before them still draws. Fix: write each data: URI out as a real PNG and
    point the href at the file, which leaves no oversized attribute behind. The
    rasters still end up embedded in the PDF.

2.  The radiology half asks for IBM Plex Serif/Sans. matplotlib found those via the
    vendored copies in figures/trends-figure/assets/fonts when it built the panel,
    but they are not installed system-wide, so the renderer falls through to the
    Georgia/Arial fallbacks in the family list and the type ladder shifts. Fix: hand
    rsvg a fontconfig file that adds the vendored directory, and set
    PANGOCAIRO_BACKEND=fc — pango defaults to CoreText on macOS and would otherwise
    ignore that file entirely.

Usage:  python3 build_pdf.py [-o OUTPUT.pdf]
"""

from __future__ import annotations

import argparse
import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SVG = HERE / "figure1-combo.svg"
FONT_DIR = HERE.parent / "trends-figure" / "assets" / "fonts"
SYSTEM_FONT_DIRS = ("/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts")

DATA_URI = re.compile(r'xlink:href="data:image/([a-z]+);base64,([A-Za-z0-9+/=\s]+?)"')
EXT = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "gif": "gif"}


def externalize(svg_text: str, out_dir: Path) -> tuple[str, int]:
    """Replace every data: URI with a sibling file, so no attribute stays huge."""
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        mime, payload = match.group(1), re.sub(r"\s+", "", match.group(2))
        name = "img_%02d.%s" % (count, EXT.get(mime, "png"))
        (out_dir / name).write_bytes(base64.b64decode(payload))
        count += 1
        return 'xlink:href="%s"' % name

    return DATA_URI.sub(replace, svg_text), count


def write_fontconfig(path: Path, cache_dir: Path) -> None:
    """fontconfig reads XML, and the repo path contains an ampersand — escape it."""
    dirs = [FONT_DIR, *SYSTEM_FONT_DIRS]
    entries = "\n".join("  <dir>%s</dir>" % escape(str(d)) for d in dirs)
    path.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig>\n"
        "%s\n"
        "  <cachedir>%s</cachedir>\n"
        "</fontconfig>\n" % (entries, escape(str(cache_dir)))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=SVG.with_suffix(".pdf"))
    args = parser.parse_args()

    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert not found (brew install librsvg)")
    if not SVG.exists():
        sys.exit("missing %s" % SVG)
    if not FONT_DIR.is_dir():
        print("warning: %s not found; IBM Plex will be substituted" % FONT_DIR)

    with tempfile.TemporaryDirectory(prefix="figure1-combo-") as tmp:
        work = Path(tmp)
        flat = work / "combo.svg"
        svg_text, n = externalize(SVG.read_text(encoding="utf-8"), work)
        flat.write_text(svg_text, encoding="utf-8")

        conf = work / "fonts.conf"
        cache = work / "fc-cache"
        cache.mkdir()
        write_fontconfig(conf, cache)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["rsvg-convert", "-f", "pdf", flat.name, "-o", str(args.output.resolve())],
            cwd=work,
            env={
                "FONTCONFIG_FILE": str(conf),
                # pango defaults to the CoreText backend on macOS, which never
                # consults FONTCONFIG_FILE; force the fontconfig backend instead.
                "PANGOCAIRO_BACKEND": "fc",
                "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
            },
            check=True,
        )

    pdf = args.output.read_bytes()
    print(
        "%s — %.1f MB, %d rasters unpacked, %d image XObjects, fonts: %s"
        % (
            args.output.name,
            len(pdf) / 1e6,
            n,
            len(re.findall(rb"/Subtype\s*/Image", pdf)),
            ", ".join(sorted({m.decode().split("+")[-1] for m in re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)", pdf)})),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
