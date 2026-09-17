"""How big an effect this many calls can actually find.

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
PAD_L, PAD_R, PAD_T, PAD_B = 62, 24, 40, 52
X0, X1 = 20, 600          # number of calls
Y0, Y1 = 0.0, 0.8         # smallest detectable |IC|
REFERENCE_IC = 0.21       # the size of effect this project set out to be able to see


def render(t, n_actual: int):
    px = lambda n: PAD_L + (n - X0) / (X1 - X0) * (W - PAD_L - PAD_R)
    py = lambda v: H - PAD_B - (v - Y0) / (Y1 - Y0) * (H - PAD_T - PAD_B)

    out = [frame(W, H, t)]
    out.append(text(PAD_L, 24, "The smallest effect a sample this size can reliably find", t,
                    size=13, color="ink", weight="600"))

    for v in (0.0, 0.2, 0.4, 0.6, 0.8):
        y = py(v)
        out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
                   f'stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(text(PAD_L - 10, y + 4, f"{v:.1f}", t, size=11, color="muted", anchor="end"))

    for n in (100, 200, 300, 400, 500, 600):
        out.append(text(px(n), H - PAD_B + 18, str(n), t, size=11, color="muted", anchor="middle"))
    out.append(text((PAD_L + W - PAD_R) / 2, H - 12, "earnings calls in the sample", t,
                    size=11, color="muted", anchor="middle"))
    out.append(text(PAD_L - 46, PAD_T - 14, "detectable |IC|", t, size=11, color="muted"))

    # The effect size worth caring about.
    y_ref = py(REFERENCE_IC)
    out.append(f'<line x1="{PAD_L}" y1="{y_ref:.1f}" x2="{W - PAD_R}" y2="{y_ref:.1f}" '
               f'stroke="{t["null"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    out.append(text(W - PAD_R, y_ref - 8, f"IC of {REFERENCE_IC:.2f}, the size worth finding", t,
                    size=11, color="ink2", anchor="end"))

    points = [(n, detectable_ic(n)) for n in range(X0, X1 + 1, 2)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{px(n):.1f},{py(v):.1f}"
                    for i, (n, v) in enumerate(points))
    out.append(f'<path d="{path}" fill="none" stroke="{t["accent"]}" stroke-width="2.5"/>')

    value = detectable_ic(n_actual)
    cx, cy = px(n_actual), py(value)
    out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{H - PAD_B}" '
               f'stroke="{t["accent"]}" stroke-width="1" stroke-dasharray="3 3"/>')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{t["accent"]}"/>')
    out.append(text(cx + 12, cy - 6, f"this study: {n_actual} calls, detects {value:.2f}", t,
                    size=12, color="ink", weight="600"))

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    n = len(load_scored_calls().dropna(subset=["sentiment", "active_return_5d"]))
    write(lambda t: render(t, n), "power-curve", Path(__file__).parent)
