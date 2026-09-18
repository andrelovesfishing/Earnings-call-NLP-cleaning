"""How many calls it takes to see an effect of a given size.

    python docs/figures/power_curve.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from earnings.evaluation import detectable_ic  # noqa: E402
from experiments.headline import load_scored_calls  # noqa: E402
from style import frame, text, write  # noqa: E402

W, H = 720, 360
PAD_L, PAD_R, PAD_T, PAD_B = 68, 24, 44, 56
X0, X1 = 20, 3300         # number of calls
Y0, Y1 = 0.0, 0.8         # smallest detectable |IC|
TARGET_IC = 0.05          # the effect size a tradeable signal actually has


def render(t, n_actual: int, n_target: int):
    px = lambda n: PAD_L + (n - X0) / (X1 - X0) * (W - PAD_L - PAD_R)
    py = lambda v: H - PAD_B - (v - Y0) / (Y1 - Y0) * (H - PAD_T - PAD_B)
    mid_y = (PAD_T + H - PAD_B) / 2

    out = [frame(W, H, t)]
    out.append(text(PAD_L, 26, "The smallest signal you can reliably detect, against sample size", t,
                    size=13, color="ink", weight="600"))

    for v in (0.0, 0.2, 0.4, 0.6, 0.8):
        y = py(v)
        out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
                   f'stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(text(PAD_L - 10, y + 4, f"{v:.1f}", t, size=11, color="muted", anchor="end"))

    for n in (500, 1000, 1500, 2000, 2500, 3000):
        out.append(text(px(n), H - PAD_B + 18, f"{n:,}", t, size=11, color="muted", anchor="middle"))
    out.append(text((PAD_L + W - PAD_R) / 2, H - 14, "earnings calls in the sample", t,
                    size=11, color="muted", anchor="middle"))
    out.append(f'<text x="18" y="{mid_y:.1f}" font-size="11" fill="{t["muted"]}" '
               f'text-anchor="middle" transform="rotate(-90 18 {mid_y:.1f})">'
               f'smallest detectable |IC|</text>')

    # The effect size a signal worth trading actually has.
    y_ref = py(TARGET_IC)
    out.append(f'<line x1="{PAD_L}" y1="{y_ref:.1f}" x2="{W - PAD_R}" y2="{y_ref:.1f}" '
               f'stroke="{t["null"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    out.append(text(PAD_L + 6, y_ref - 9, f"IC of {TARGET_IC:.2f}, the size worth finding", t,
                    size=11, color="ink2"))

    points = [(n, detectable_ic(n)) for n in range(X0, X1 + 1, 5)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{px(n):.1f},{py(v):.1f}"
                    for i, (n, v) in enumerate(points))
    out.append(f'<path d="{path}" fill="none" stroke="{t["accent"]}" stroke-width="2.5"/>')

    for n, label, anchor, dx in (
        (n_actual, f"this study: {n_actual} calls, detects {detectable_ic(n_actual):.2f}", "start", 12),
        (n_target, f"{n_target:,} calls to detect {TARGET_IC:.2f}", "end", -12),
    ):
        cx, cy = px(n), py(detectable_ic(n))
        out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{H - PAD_B}" '
                   f'stroke="{t["accent"]}" stroke-width="1" stroke-dasharray="3 3"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{t["accent"]}"/>')
        out.append(text(cx + dx, cy - 10, label, t, size=12, color="ink", weight="600", anchor=anchor))

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    n = len(load_scored_calls().dropna(subset=["sentiment", "active_return_5d"]))
    target = next(m for m in range(100, 50000) if detectable_ic(m) <= TARGET_IC)
    write(lambda t: render(t, n, target), "power-curve", Path(__file__).parent)
    print(f"n={n} detects {detectable_ic(n):.3f}; {target} calls needed for {TARGET_IC}")
