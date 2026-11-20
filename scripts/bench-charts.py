#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Draw the benchmark charts in docs/img/ from docs/data/benchmarks.json.

    scripts/bench-charts.py            write docs/img/<id>.svg and <id>-dark.svg
    scripts/bench-charts.py --check    fail if a committed SVG differs from what
                                       the data gives (CI runs this)

Plain Python, no plotting library: horizontal grouped bars, one light and one
dark image per chart (the README picks one with <picture>). A value is a
number or [low, high]; a range is drawn as a bar to the low value with a
whisker to the high one. Every value in the data file names its source
document; the chart's footer lists them.
"""
import argparse
import json
import math
import os
import sys
from xml.sax.saxutils import escape

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(TOP, "docs", "data", "benchmarks.json")
OUT = os.path.join(TOP, "docs", "img")

# Categorical slots 1-3 (blue, orange, aqua), validated as adjacent pairs in
# both modes; each role keeps its colour in every chart.
THEMES = {
    "light": {
        "surface": "#fcfcfb", "border": "#e1e0d9", "ink": "#0b0b0b",
        "ink2": "#52514e", "muted": "#6f6e69", "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "after": "#2a78d6", "before": "#eb6834", "reference": "#1baf7a",
    },
    "dark": {
        "surface": "#1a1a19", "border": "#2c2c2a", "ink": "#f0efec",
        "ink2": "#c3c2b7", "muted": "#9b9a94", "grid": "#2c2c2a",
        "axis": "#383835",
        "after": "#3987e5", "before": "#d95926", "reference": "#199e70",
    },
}
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif'
W = 760          # image width
PAD = 20         # outer padding
BAR = 14         # bar thickness
GAP = 2          # gap between bars of a group
GROUP_GAP = 14   # gap between groups
CHAR = 0.56      # average glyph width per px of font size (estimate)


def text_w(s, size):
    return len(s) * size * CHAR


def fmt(v):
    if v >= 100:
        return f"{v:.0f}" if v == int(v) else f"{v:.1f}"
    if v >= 1 or v == 0:
        return f"{v:g}"
    return f"{v:.2f}".rstrip("0").rstrip(".")


def fmt_range(lo, hi):
    """'4.0-4.2', not '4-4.2': both ends with the same number of decimals."""
    if lo == hi:
        return fmt(lo)
    a, b = fmt(lo), fmt(hi)
    dec = max(len(x.partition(".")[2]) for x in (a, b))
    return f"{lo:.{dec}f}-{hi:.{dec}f}"


def nice_max(v):
    """Axis end and tick step: 4-6 ticks at 1/2/2.5/5 x 10^n."""
    raw = v / 5
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    end = math.ceil(v / step) * step
    if end - v < step * 0.15:   # room for the value label
        end += step
    return end, step


def wrap(s, size, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and text_w(t, size) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def bar_path(x0, y, length, h, r=4):
    """Bar from the baseline x0, square there, 4px rounded data-end."""
    r = min(r, length / 2, h / 2)
    x1 = x0 + length
    return (f"M{x0:.1f},{y:.1f}H{x1 - r:.1f}"
            f"A{r},{r} 0 0 1 {x1:.1f},{y + r:.1f}V{y + h - r:.1f}"
            f"A{r},{r} 0 0 1 {x1 - r:.1f},{y + h:.1f}H{x0:.1f}Z")


def lohi(v):
    if v is None:
        return None, None
    if isinstance(v, list):
        return float(v[0]), float(v[1])
    return float(v), float(v)


def render(chart, mode):
    t = THEMES[mode]
    series = chart["series"]
    cats = []
    for d in chart["data"]:
        if d["category"] not in cats:
            cats.append(d["category"])
    val = {(d["category"], d["series"]): d for d in chart["data"]}
    vmax = max(lohi(d.get("value"))[1] or 0 for d in chart["data"])
    end, step = nice_max(vmax)

    # vertical layout
    o = []
    y = PAD + 18
    title_y = y
    sub_lines = wrap(chart["subtitle"], 12.5, W - 2 * PAD)
    y += 22 + 17 * (len(sub_lines) - 1)   # baseline of the last subtitle line
    legend_y = None
    if len(series) > 1:
        legend_y = y + 26
        lx, rows = PAD, 1
        for s in series:
            wdt = 18 + text_w(s["name"], 12) + 20
            if lx + wdt > W - PAD:
                lx, rows = PAD, rows + 1
            lx += wdt
        y = legend_y + 18 * rows + 4
    plot_top = y + (16 if legend_y is not None else 24)
    label_w = min(260, max(text_w(c, 12.5) for c in cats) + 14)
    x0 = PAD + label_w
    plot_w = W - PAD - x0 - 54
    nser = len(series)
    group_h = nser * BAR + (nser - 1) * GAP
    plot_h = len(cats) * group_h + (len(cats) - 1) * GROUP_GAP
    plot_bottom = plot_top + plot_h
    axis_y = plot_bottom + 18
    sources = sorted({d["source"] for d in chart["data"]})
    foot_y = axis_y + 26
    H = int(foot_y + PAD - 4)

    def sx(v):
        return x0 + plot_w * v / end

    tid, did = f"{chart['id']}-title", f"{chart['id']}-desc"
    desc = "; ".join(
        f"{d['category']}, {d['series']}: "
        + (d.get("note") or "-" if d.get("value") is None else
           fmt_range(*lohi(d["value"])) + " " + chart["unit"])
        for d in chart["data"])
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="{tid} {did}" '
             f'font-family="{FONT}">')
    o.append(f'<title id="{tid}">{escape(chart["title"])}</title>')
    o.append(f'<desc id="{did}">{escape(chart["subtitle"])}. {escape(desc)}</desc>')
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8" '
             f'fill="{t["surface"]}" stroke="{t["border"]}"/>')
    o.append(f'<text x="{PAD}" y="{title_y}" font-size="16" font-weight="600" '
             f'fill="{t["ink"]}">{escape(chart["title"])}</text>')
    for i, line in enumerate(sub_lines):
        o.append(f'<text x="{PAD}" y="{title_y + 22 + 17 * i}" font-size="12.5" '
                 f'fill="{t["ink2"]}">{escape(line)}</text>')
    if legend_y is not None:
        lx, ly = PAD, legend_y
        for s in series:
            wdt = 18 + text_w(s["name"], 12) + 20
            if lx + wdt > W - PAD:
                lx, ly = PAD, ly + 18
            o.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="3" '
                     f'fill="{t[s["role"]]}"/>')
            o.append(f'<text x="{lx + 18}" y="{ly}" font-size="12" '
                     f'fill="{t["ink2"]}">{escape(s["name"])}</text>')
            lx += wdt

    # grid and ticks
    v = 0.0
    while v <= end + 1e-9:
        x = sx(v)
        o.append(f'<line x1="{x:.1f}" y1="{plot_top - 4}" x2="{x:.1f}" y2="{plot_bottom + 4}" '
                 f'stroke="{t["axis"] if v == 0 else t["grid"]}" stroke-width="1"/>')
        o.append(f'<text x="{x:.1f}" y="{axis_y}" font-size="11" text-anchor="middle" '
                 f'fill="{t["muted"]}">{fmt(v)}</text>')
        v += step
    o.append(f'<text x="{x0 + plot_w:.1f}" y="{axis_y + 14}" font-size="11" text-anchor="end" '
             f'fill="{t["muted"]}">{escape(chart["unit"])}</text>')

    # bars
    for ci, c in enumerate(cats):
        gy = plot_top + ci * (group_h + GROUP_GAP)
        o.append(f'<text x="{x0 - 10}" y="{gy + group_h / 2 + 4.5:.1f}" font-size="12.5" '
                 f'text-anchor="end" fill="{t["ink"]}">{escape(c)}</text>')
        for si, s in enumerate(series):
            d = val.get((c, s["name"]))
            if d is None:
                continue
            by = gy + si * (BAR + GAP)
            lo, hi = lohi(d.get("value"))
            if lo is None:
                o.append(f'<text x="{x0 + 6}" y="{by + BAR - 3}" font-size="11.5" font-style="italic" '
                         f'fill="{t["muted"]}">{escape(d.get("note", "n/a"))}</text>')
                continue
            tip = f'{c}, {s["name"]}: {fmt_range(lo, hi)} {chart["unit"]}'
            o.append(f'<g><title>{escape(tip)}</title>')
            length = max(sx(lo) - x0, 1.5)
            o.append(f'<path d="{bar_path(x0, by, length, BAR)}" fill="{t[s["role"]]}"/>')
            end_x = x0 + length
            label = fmt(lo)
            if hi > lo:
                wx = sx(hi)
                my = by + BAR / 2
                o.append(f'<line x1="{end_x:.1f}" y1="{my:.1f}" x2="{wx:.1f}" y2="{my:.1f}" '
                         f'stroke="{t[s["role"]]}" stroke-width="2"/>')
                o.append(f'<line x1="{wx:.1f}" y1="{by + 2}" x2="{wx:.1f}" y2="{by + BAR - 2}" '
                         f'stroke="{t[s["role"]]}" stroke-width="2" stroke-linecap="round"/>')
                end_x = wx
                label = fmt_range(lo, hi)
            o.append(f'<text x="{end_x + 5:.1f}" y="{by + BAR - 3}" font-size="11.5" '
                     f'fill="{t["ink2"]}">{label}</text></g>')

    label = "Source" if len(sources) == 1 else "Sources"
    o.append(f'<text x="{PAD}" y="{foot_y}" font-size="11" fill="{t["muted"]}">'
             f'{label}: {escape(", ".join(sources))}</text>')
    o.append("</svg>")
    return "\n".join(o) + "\n"


def validate(charts):
    ids = set()
    for c in charts:
        assert c["id"] not in ids, f"duplicate chart id {c['id']}"
        ids.add(c["id"])
        names = {s["name"] for s in c["series"]}
        for s in c["series"]:
            assert s["role"] in ("after", "before", "reference"), s
        for d in c["data"]:
            assert d["series"] in names, f"{c['id']}: unknown series {d['series']}"
            assert d.get("source"), f"{c['id']}: {d['category']} has no source"
            assert os.path.isfile(os.path.join(TOP, d["source"])), \
                f"{c['id']}: source {d['source']} does not exist"
            v = d.get("value")
            assert v is not None or d.get("note"), f"{c['id']}: {d['category']}: no value, no note"
            if isinstance(v, list):
                assert len(v) == 2 and v[0] <= v[1], f"{c['id']}: bad range {v}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="compare with the committed SVGs instead of writing them")
    a = ap.parse_args()
    with open(DATA, encoding="utf-8") as f:
        charts = json.load(f)["charts"]
    validate(charts)
    stale = []
    for c in charts:
        for mode in ("light", "dark"):
            name = f"{c['id']}{'' if mode == 'light' else '-dark'}.svg"
            path = os.path.join(OUT, name)
            svg = render(c, mode)
            if a.check:
                try:
                    with open(path, encoding="utf-8") as f:
                        if f.read() != svg:
                            stale.append(name)
                except FileNotFoundError:
                    stale.append(name)
            else:
                os.makedirs(OUT, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(svg)
                print(f"wrote docs/img/{name}")
    if stale:
        sys.exit("out of date (run scripts/bench-charts.py): " + ", ".join(stale))


if __name__ == "__main__":
    main()
