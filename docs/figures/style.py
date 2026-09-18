"""Shared look for the README figures: light and dark palettes and SVG helpers."""

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", band="#e8e7e0", accent="#b8860b",
                  null="#b4b2a9"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", base="#4a4a46", band="#26262400", accent="#ffd23f",
                 null="#6f6e69"),
}
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def text(x, y, s, t, size=12, color="ink2", anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"{w} fill="{t[color]}" '
            f'style="font-variant-numeric:tabular-nums">{s}</text>')


def frame(width, height, t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}">'
            f'<rect width="{width}" height="{height}" fill="{t["surface"]}"/>')


def write(render, stem, out_dir):
    for name, theme in THEMES.items():
        (out_dir / f"{stem}-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote {stem}-{name}.svg")
