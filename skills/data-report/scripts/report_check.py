#!/usr/bin/env python3
"""Check a standalone HTML report: what is wrong in the file, what breaks in a browser, how it looks.

    report_check.py REPORT.html [--shots DIR] [--widths 1280,390] [--no-browser]
    report_check.py REPORT.html --shots DIR --part WIDTH,FROM,TO

Prints JSON. `problems` lists what to fix. With a Chrome on the machine the script measures the page
at each width: sideways scrolling, chart labels that overlap or are cut off, shapes drawn outside
their chart, charts too small to read. With --shots it writes one overview picture per width: the
whole page as columns, scaled down, with the distance from the top marked every 500 px. --part
writes one full-size picture of the page between two such marks.

Without Chrome it checks the file only, and draws the pictures with weasyprint and pdftoppm when both
are installed. Python 3.11+, standard library only.
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

MARK = "__report_check__"
CHROME_ENV = (
    "REPORT_CHROME",
    "AGENT_BROWSER_EXECUTABLE_PATH",
    "CHROME_PATH",
    "PUPPETEER_EXECUTABLE_PATH",
)
CHROME_NAMES = ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome", "chrome")
BAD_TEXT = re.compile(r"(?<![\w.])(NaN|nan|undefined|None|null|inf|Infinity|NaT)(?![\w.])")
PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}|\{[a-zA-Z_][\w.\[\]'\"]*(?::[^{}]*)?\}|\$\{[^{}]*\}")
EXTERNAL = re.compile(r"^(https?:)?//", re.I)
CSS_URL = re.compile(r"url\(\s*['\"]?((?:https?:)?//[^'\")]+)", re.I)
CSS_IMPORT = re.compile(r"@import\s+(?:url\()?['\"]?((?:https?:)?//[^'\")\s;]+)", re.I)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", re.I)
PLAIN = re.compile(r"\s*-?\d+(\.\d+)?\s*")
HEADINGS = ("h1", "h2", "h3", "h4", "figcaption")
SHAPES = ("rect", "circle", "ellipse", "line", "polyline", "polygon", "text")
HIDDEN = ("defs", "clippath", "mask", "pattern", "symbol")
EMBEDS = ("img", "image", "iframe", "source", "video", "audio", "embed", "object", "use")
PDF_WIDTH, PDF_PAGE, GAP = 1180, 2800, 16
HIDE_BARS = "<style>html{scrollbar-width:none}::-webkit-scrollbar{display:none}</style>"

RULER = (
    "addEventListener('load',()=>{for(let y=Math.ceil(%d/500)*500;y<%d;y+=500){"
    "const m=document.createElement('div');m.textContent=y;m.style.cssText='position:absolute;left:0;"
    "top:'+y+'px;z-index:2147483647;font:bold 22px monospace;background:#ffe600;color:#000;"
    "padding:0 6px;line-height:26px';document.body.appendChild(m);}scrollTo(0,%d);});"
)

IN_PAGE = r"""
(() => {
  const out = {width: innerWidth, height: 0, overflow_x: false, problems: []};
  const add = (text, where) => { if (out.problems.length < 60) out.problems.push({text, where}); };
  const label = (el) => {
    const fig = el.closest('figure');
    const cap = fig && fig.querySelector('figcaption');
    if (cap && cap.textContent.trim()) return cap.textContent.trim().slice(0, 60);
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      for (let prev = node.previousElementSibling; prev; prev = prev.previousElementSibling) {
        if (/^H[1-6]$/.test(prev.tagName) && prev.textContent.trim()) return prev.textContent.trim().slice(0, 60);
        const inside = prev.querySelectorAll('h1,h2,h3,h4,h5,h6');
        if (inside.length) return inside[inside.length - 1].textContent.trim().slice(0, 60);
      }
    }
    return '';
  };
  const visible = (el) => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05; };
  const scrolls = (el) => { for (let n = el.parentElement; n && n !== document.documentElement; n = n.parentElement) { const o = getComputedStyle(n).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return true; } return false; };
  const de = document.documentElement;
  out.height = Math.max(de.scrollHeight, document.body ? document.body.scrollHeight : 0);
  out.overflow_x = de.scrollWidth > innerWidth + 1;
  if (out.overflow_x) {
    const seen = new Set();
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.right <= innerWidth + 1 || scrolls(el) || !visible(el)) continue;
      const parent = el.parentElement;
      if (parent && parent !== document.body && parent.getBoundingClientRect().right > innerWidth + 1) continue;
      const key = el.tagName + '|' + label(el);
      if (seen.has(key)) continue;
      seen.add(key);
      add(`a <${el.tagName.toLowerCase()}> is ${Math.round(r.width)} px wide and reaches ${Math.round(r.right - innerWidth)} px past the edge`, label(el));
      if (seen.size >= 6) break;
    }
  }
  const tiny = [];
  for (const svg of document.querySelectorAll('svg')) {
    const box = svg.getBoundingClientRect();
    if (box.width < 40 || box.height < 30 || !visible(svg)) continue;
    const where = label(svg);
    const shapes = [...svg.querySelectorAll('rect,path,circle,line,polyline,polygon,ellipse')].filter((g) => visible(g) && !g.closest('defs,clipPath,mask,pattern,symbol'));
    const texts = [...svg.querySelectorAll('text')].filter((t) => t.textContent.trim() && visible(t)).map((t) => ({t: t.textContent.trim().slice(0, 30), r: t.getBoundingClientRect()})).filter((x) => x.r.width > 0);
    if (!shapes.length && !texts.length && !svg.querySelector('image,use')) { add('a chart with nothing drawn in it', where); continue; }
    const outside = shapes.filter((g) => { const r = g.getBoundingClientRect(); return (r.width > 0 || r.height > 0) && (r.right < box.left - 1 || r.left > box.right + 1 || r.bottom < box.top - 1 || r.top > box.bottom + 1); }).length;
    if (outside) add(`${outside} of ${shapes.length} shapes are drawn outside the chart area and cannot be seen: check the scale`, where);
    let small = 0, cut = 0, over = 0;
    const clips = getComputedStyle(svg).overflow !== 'visible';
    for (const a of texts) {
      if (a.r.height < 7.5) small++;
      if (clips && (a.r.left < box.left - 2 || a.r.right > box.right + 2 || a.r.top < box.top - 2 || a.r.bottom > box.bottom + 2) && cut++ < 3) add(`the label "${a.t}" runs out of its chart`, where);
    }
    for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
      const a = texts[i].r, b = texts[j].r;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w <= 1 || h <= 1) continue;
      if (w * h > 0.2 * Math.min(a.width * a.height, b.width * b.height) && over++ < 4) add(`the labels "${texts[i].t}" and "${texts[j].t}" overlap`, where);
    }
    if (over > 4) add(`${over - 4} more overlapping labels in this chart`, where);
    if (texts.length && small / texts.length > 0.5) tiny.push(where || 'a chart');
  }
  if (tiny.length) add(`${tiny.length} chart(s) are scaled down so far that their labels are under 8 px high: ${[...new Set(tiny)].slice(0, 6).join('; ')}`, '');
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg') || !visible(el) || !el.clientWidth || el.children.length) continue;
    const s = getComputedStyle(el);
    if ((s.overflowX === 'hidden' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 2 && el.textContent.trim()) add(`the text "${el.textContent.trim().slice(0, 40)}" is cut off`, label(el));
  }
  for (const img of document.images) if (img.complete && img.naturalWidth === 0) add(`an image does not load: ${(img.getAttribute('src') || '').slice(0, 60)}`, label(img));
  const s = document.createElement('script');
  s.type = 'application/json'; s.id = '__report_check__'; s.textContent = JSON.stringify(out);
  document.body.appendChild(s);
})();
"""


def numbers(text: str, count: int) -> tuple[float, ...] | None:
    found = [float(x) for x in NUMBER.findall(text or "")]
    return tuple(found[:count]) if len(found) >= count else None


def view_box(attrs: dict[str, str]) -> tuple[float, ...] | None:
    box = numbers(attrs.get("viewbox", ""), 4)
    if box:
        return box
    size = attrs.get("width", "") + " " + attrs.get("height", "")
    both = numbers(size, 2)
    return (0.0, 0.0, both[0], both[1]) if both and "%" not in size else None


def shape_points(tag: str, attrs: dict[str, str]) -> list[tuple[float, float]]:
    """The points of a shape whose coordinates are plain numbers. An empty list when they are not."""

    def value(name: str, default: str = "") -> float | None:
        text = attrs.get(name, default)
        return float(text) if PLAIN.fullmatch(text) else None

    if tag in ("polyline", "polygon"):
        found = [float(x) for x in NUMBER.findall(attrs.get("points", ""))]
        return list(zip(found[0::2], found[1::2], strict=False))
    if tag == "line":
        ends = [value(name, "0") for name in ("x1", "y1", "x2", "y2")]
        return [] if None in ends else [(ends[0], ends[1]), (ends[2], ends[3])]
    if tag in ("circle", "ellipse"):
        center = (value("cx", "0"), value("cy", "0"))
        return [] if None in center else [center]
    if tag == "rect":
        x, y, wide, high = value("x", "0"), value("y", "0"), value("width"), value("height")
        if None in (x, y, wide, high):
            return []
        return [(x, y), (x + wide, y), (x, y + high), (x + wide, y + high)]
    corner = (value("x", "0"), value("y", "0"))
    return [] if None in corner else [corner]


class Page(HTMLParser):
    """What the file alone tells: outside addresses, visible text, and the charts with plain coordinates."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.external: list[str] = []
        self.text: list[str] = []
        self.css: list[str] = []
        self.outside: list[str] = []
        self.cut: list[str] = []
        self.scripts = self.charts = self.fixed = self.tables = self.images = 0
        self.viewport = False
        self.lang = ""
        self._skip = ""
        self._heading = ""
        self._in_heading = False
        self._box: tuple[float, ...] | None = None
        self._depth = self._moved = self._shapes = self._lost = 0
        self._label: tuple[float, str, float] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {key: (value or "") for key, value in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "meta" and a.get("name", "").lower() == "viewport":
            self.viewport = True
        if tag == "script":
            self.scripts += 1
            self._skip = "script"
            self._outside_address(a.get("src", ""))
        elif tag == "style":
            self._skip = "style"
        elif tag == "link":
            self._outside_address(a.get("href", ""))
        elif tag in EMBEDS:
            self.images += tag == "img"
            self._outside_address(
                a.get("src") or a.get("href") or a.get("xlink:href") or a.get("data") or ""
            )
        elif tag == "table":
            self.tables += 1
        elif tag == "svg":
            self.charts += 1
            self.fixed += "viewbox" not in a and a.get("width", "").removesuffix("px").isdigit()
            if self._box is None:
                self._box = view_box(a)
                self._depth = self._moved = self._shapes = self._lost = 0
        if tag in HEADINGS:
            self._in_heading, self._heading = True, ""
        if "style" in a:
            self.css.append(a["style"])
        if self._box is not None:
            self._shape(tag, a)

    def _outside_address(self, ref: str) -> None:
        if EXTERNAL.match(ref):
            self.external.append(ref)

    def _shape(self, tag: str, a: dict[str, str]) -> None:
        self._depth += 1
        if tag != "svg" and not self._moved and ("transform" in a or tag in HIDDEN):
            self._moved = self._depth
        if self._moved or tag not in SHAPES:
            return
        points = shape_points(tag, a)
        if not points:
            return
        left, top, wide, high = self._box
        pad_x, pad_y = wide * 0.02 + 1, high * 0.02 + 1
        inside = any(
            left - pad_x <= x <= left + wide + pad_x and top - pad_y <= y <= top + high + pad_y
            for x, y in points
        )
        self._shapes += 1
        self._lost += not inside
        if tag == "text" and inside:
            size = numbers(
                a.get("font-size", "") or a.get("style", "").partition("font-size:")[2], 1
            )
            self._label = (points[0][0], a.get("text-anchor", "start"), size[0] if size else 12.0)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._skip:
            self._skip = ""
        if tag in HEADINGS:
            self._in_heading = False
        if tag == "text":
            self._label = None
        if self._box is None:
            return
        if self._moved == self._depth:
            self._moved = 0
        self._depth -= 1
        if self._depth <= 0:
            if self._lost:
                self.outside.append(f"{self._lost} of {self._shapes} shapes{self._where()}")
            self._box = None

    def _where(self) -> str:
        heading = " ".join(self._heading.split())[:60]
        return f' in "{heading}"' if heading else ""

    def handle_data(self, data: str) -> None:
        if self._skip == "style":
            self.css.append(data)
        if self._skip or not data.strip():
            return
        self.text.append(data.strip())
        if self._in_heading:
            self._heading += data
        if self._label and self._box:
            x, anchor, size = self._label
            wide = len(data.strip()) * size * 0.56
            left = x - (wide if anchor == "end" else wide / 2 if anchor == "middle" else 0)
            over = max(self._box[0] - left, left + wide - (self._box[0] + self._box[2]))
            if over > max(6.0, wide * 0.15):
                self.cut.append(f'"{data.strip()[:30]}"{self._where()}')


def static_check(source: str) -> tuple[dict, list[str], list[str]]:
    page = Page()
    page.feed(source)
    problems: list[str] = []
    for css in page.css:
        page.external += CSS_URL.findall(css) + CSS_IMPORT.findall(css)
    external = sorted(set(page.external))
    if external:
        problems.append(
            f"not standalone: the file loads from {len(external)} outside address(es): "
            + ", ".join(external[:5])
        )
    if not page.viewport:
        problems.append(
            'no <meta name="viewport" content="width=device-width, initial-scale=1">: a phone shows the page tiny'
        )
    bad = []
    for chunk in page.text:
        for found in [*BAD_TEXT.finditer(chunk), *PLACEHOLDER.finditer(chunk)]:
            bad.append(chunk[max(0, found.start() - 25) : found.end() + 15])
    if bad:
        problems.append(
            f"{len(bad)} place(s) show a missing value or an unfilled placeholder: "
            + " | ".join(bad[:6])
        )
    for found in page.outside[:6]:
        problems.append(
            f"drawn outside the chart area, so nobody sees it: {found}. Check the scale of that chart."
        )
    if page.fixed:
        problems.append(
            f"{page.fixed} chart(s) have a fixed width and no viewBox: they do not scale with the page"
        )
    size = len(source.encode("utf-8"))
    if size > 5_000_000:
        problems.append(f"the file has {size / 1e6:.1f} MB: large to mail and to preview")
    facts = {
        "bytes": size,
        "lang": page.lang,
        "charts": page.charts,
        "tables": page.tables,
        "images": page.images,
        "scripts": page.scripts,
    }
    return facts, problems, page.cut


def find_chrome() -> str | None:
    for name in CHROME_ENV:
        value = os.environ.get(name)
        if value and os.access(value, os.X_OK):
            return value
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path.home() / ".cache" / "ms-playwright"
    )
    found = sorted(
        glob.glob(f"{cache}/chromium_headless_shell-*/*/chrome-headless-shell")
    ) or sorted(glob.glob(f"{cache}/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else None


def chrome(binary: str, *args: str) -> str:
    base = [
        binary,
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        "--disable-dev-shm-usage",
    ]
    done = subprocess.run(
        [*base, "--virtual-time-budget=3000", *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return done.stdout


def with_script(source: str, script: str) -> str:
    tag = f"<script>{script}</script>"
    at = source.lower().rfind("</body>")
    return source[:at] + tag + source[at:] if at >= 0 else source + tag


def measure(binary: str, source: str, width: int, work: Path) -> dict:
    probe = work / f"probe-{width}.html"
    probe.write_text(
        with_script(source, f"addEventListener('load',()=>{{{IN_PAGE}}});"), encoding="utf-8"
    )
    dom = chrome(binary, f"--window-size={width},900", "--dump-dom", probe.as_uri())
    found = re.search(rf'<script type="application/json" id="{MARK}">(.*?)</script>', dom, re.S)
    if not found:
        return {"width": width, "error": "the page did not finish loading in the browser"}
    return json.loads(html.unescape(found.group(1)))


def columns(source: str, width: int, top: int, bottom: int, column: int) -> tuple[str, int, int]:
    """One page that shows the report from `top` to `bottom` as columns next to each other."""
    frames = []
    for offset in range(top, bottom, column):
        high = min(column, bottom - offset)
        doc = with_script(source + HIDE_BARS, RULER % (offset, offset + high, offset))
        style = f"width:{width}px;height:{high}px;border:0;background:#fff;flex:none"
        frames.append(f'<iframe srcdoc="{html.escape(doc, quote=True)}" style="{style}"></iframe>')
    body = (
        f'<body style="margin:0;display:flex;align-items:flex-start;gap:{GAP}px;background:#777">'
    )
    return (
        f"<!doctype html><meta charset=utf-8>{body}{''.join(frames)}</body>",
        len(frames),
        min(column, bottom - top),
    )


def overview(
    binary: str, source: str, width: int, height: int, shots: Path, work: Path
) -> list[str]:
    column, per_image, scale = (2400, 5, 0.75) if width < 700 else (3000, 3, 0.5)
    starts = list(range(0, height, column * per_image))
    written = []
    for index, top in enumerate(starts, 1):
        doc, count, high = columns(
            source, width, top, min(height, top + column * per_image), column
        )
        page = work / f"sheet-{width}-{index}.html"
        page.write_text(doc, encoding="utf-8")
        name = shots / (f"page-{width}.png" if len(starts) == 1 else f"page-{width}-{index}.png")
        size = f"--window-size={count * width + (count - 1) * GAP},{high}"
        chrome(
            binary,
            size,
            f"--force-device-scale-factor={scale}",
            f"--screenshot={name}",
            page.as_uri(),
        )
        if name.exists():
            written.append(str(name))
    return written


def part(
    binary: str, source: str, width: int, top: int, bottom: int, shots: Path, work: Path
) -> str:
    high = max(200, min(bottom - top, 2400))
    doc, _, _ = columns(source, width, top, top + high, high)
    page = work / f"part-{width}-{top}.html"
    page.write_text(doc, encoding="utf-8")
    name = shots / f"part-{width}-{top}-{top + high}.png"
    chrome(binary, f"--window-size={width},{high}", f"--screenshot={name}", page.as_uri())
    return str(name) if name.exists() else ""


def pdf_tools() -> bool:
    return bool(shutil.which("weasyprint") and shutil.which("pdftoppm"))


def run(*command: str) -> None:
    subprocess.run(command, capture_output=True, timeout=180, check=False)


def to_pdf(page: Path, pdf: Path, width: int, height: int) -> None:
    style = pdf.with_suffix(".css")
    style.write_text(f"@page{{size:{width}px {height}px;margin:0}}", encoding="utf-8")
    run("weasyprint", str(page), str(pdf), "-s", str(style))


def pdf_overview(report: Path, shots: Path, work: Path) -> list[str]:
    """Without a browser: the pages of a PDF, three next to each other per picture, at half size."""
    pdf = work / "report.pdf"
    to_pdf(report, pdf, PDF_WIDTH, PDF_PAGE)
    run("pdftoppm", "-png", "-r", "48", str(pdf), str(work / "pg"))
    pages = sorted(work.glob("pg-*.png"))
    wide, high = PDF_WIDTH // 2, PDF_PAGE // 2
    written = []
    for start in range(0, len(pages), 3):
        group = pages[start : start + 3]
        cells = []
        for offset, image in enumerate(group):
            top = (start + offset) * PDF_PAGE
            marks = "".join(
                f'<span style="position:absolute;left:0;top:{(mark - top) // 2}px;background:#ffe600;'
                f'font:bold 11px monospace;padding:0 3px">{mark}</span>'
                for mark in range(-(-top // 500) * 500, top + PDF_PAGE, 500)
            )
            cells.append(
                f'<div style="position:absolute;left:{offset * (wide + GAP)}px;top:0;width:{wide}px;height:{high}px">'
                f'<img src="{image.name}" style="width:{wide}px;height:{high}px">{marks}</div>'
            )
        sheet = work / f"sheet-{start}.html"
        sheet.write_text(
            f'<!doctype html><meta charset=utf-8><body style="margin:0;background:#777">{"".join(cells)}</body>',
            encoding="utf-8",
        )
        total = len(group) * wide + (len(group) - 1) * GAP
        to_pdf(sheet, sheet.with_suffix(".pdf"), total, high)
        name = shots / ("page-pdf" if len(pages) <= 3 else f"page-pdf-{start // 3 + 1}")
        run(
            "pdftoppm", "-png", "-r", "96", "-singlefile", str(sheet.with_suffix(".pdf")), str(name)
        )
        if name.with_suffix(".png").exists():
            written.append(str(name.with_suffix(".png")))
    return written


def pdf_part(report: Path, top: int, bottom: int, shots: Path, work: Path) -> str:
    pdf = work / "report.pdf"
    to_pdf(report, pdf, PDF_WIDTH, PDF_PAGE)
    number = top // PDF_PAGE + 1
    start = top - (number - 1) * PDF_PAGE
    high = max(200, min(bottom - top, PDF_PAGE - start))
    name = shots / f"part-pdf-{top}-{top + high}"
    crop = ["-x", "0", "-y", str(start), "-W", str(PDF_WIDTH), "-H", str(high)]
    run(
        "pdftoppm",
        "-png",
        "-r",
        "96",
        "-f",
        str(number),
        "-l",
        str(number),
        *crop,
        "-singlefile",
        str(pdf),
        str(name),
    )
    return str(name.with_suffix(".png")) if name.with_suffix(".png").exists() else ""


def fail(message: str) -> int:
    print(json.dumps({"error": message}), file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("report")
    parser.add_argument("--shots", help="folder for the pictures")
    parser.add_argument(
        "--widths", default="1280,390", help="page widths to check, default 1280,390"
    )
    parser.add_argument(
        "--part", help="WIDTH,FROM,TO: one full-size picture between two marks, needs --shots"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="check the file only, even with a Chrome"
    )
    args = parser.parse_args()
    report = Path(args.report)
    if not report.is_file():
        return fail(f"{report} is not a file")
    try:
        widths = [int(x) for x in args.widths.split(",") if x.strip()]
        cut = [int(x) for x in args.part.split(",")] if args.part else []
    except ValueError:
        return fail("--widths and --part take whole numbers separated by commas")
    if args.part and (len(cut) != 3 or not args.shots):
        return fail("--part takes WIDTH,FROM,TO and needs --shots")
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    source = report.read_text(encoding="utf-8", errors="replace")
    binary = None if args.no_browser else find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if cut:
            if binary:
                image = part(binary, source, cut[0], cut[1], cut[2], shots, work)
            else:
                image = (
                    pdf_part(report.resolve(), cut[1], cut[2], shots, work) if pdf_tools() else ""
                )
            if not image:
                return fail("no picture: this needs a Chrome, or weasyprint with pdftoppm")
            print(json.dumps({"image": image}))
            return 0
        facts, problems, guessed = static_check(source)
        result: dict = {
            "file": str(report),
            **facts,
            "browser": bool(binary),
            "widths": [],
            "images": [],
        }
        if binary:
            measured: dict[str, list[int]] = {}
            for width in widths:
                seen = measure(binary, source, width, work)
                if seen.get("error"):
                    problems.append(f"at {width} px: {seen['error']}")
                    continue
                result["widths"].append(
                    {key: seen[key] for key in ("width", "height", "overflow_x")}
                )
                if seen["overflow_x"]:
                    measured.setdefault("the page scrolls sideways", []).append(width)
                for item in seen["problems"]:
                    where = f'in "{item["where"]}": ' if item.get("where") else ""
                    measured.setdefault(where + item["text"], []).append(width)
                if shots:
                    result["images"] += overview(binary, source, width, seen["height"], shots, work)
            if any("drawn outside" in text for text in measured):
                problems[:] = [p for p in problems if not p.startswith("drawn outside")]
            for text, seen_at in measured.items():
                problems.append("at " + " and ".join(f"{w} px" for w in seen_at) + ": " + text)
        else:
            if guessed:
                problems.append(
                    f"{len(guessed)} chart label(s) probably run out of their chart (estimated, not measured): "
                    + "; ".join(guessed[:6])
                )
            if shots and pdf_tools():
                result["images"] = pdf_overview(report.resolve(), shots, work)
            result["note"] = "No browser found, so the layout was not measured." + (
                " The pictures come from a PDF engine: it draws inline SVG and tables like a browser, "
                "but not every CSS layout, and it shows no phone."
                if result["images"]
                else ""
            )
        result["problems"] = problems
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
