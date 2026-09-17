"""The measured correlation at each horizon, with what the uncertainty allows.

    python docs/figures/ic_by_horizon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from earnings.evaluation import ic_across_horizons  # noqa: E402
from experiments.common import HORIZONS, PRIMARY_SCORE  # noqa: E402
from experiments.headline import load_scored_calls  # noqa: E402
from style import frame, text, write  # noqa: E402

W, H = 720, 340
PAD_L, PAD_R, PAD_T, PAD_B = 96, 28, 44, 50
X0, X1 = -0.5, 0.5


def render(t, table):
    px = lambda v: PAD_L + (v - X0) / (X1 - X0) * (W - PAD_L - PAD_R)
    rows = len(table)
    band = (H - PAD_T - PAD_B) / rows
    py = lambda i: PAD_T + band * (i + 0.5)

    out = [frame(W, H, t)]
    out.append(text(PAD_L - 34, 24, "Correlation with what happened next, and what the data rules out", t,
                    size=13, color="ink", weight="600"))

    for v in (-0.4, -0.2, 0.0, 0.2, 0.4):
        x = px(v)
        out.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{H - PAD_B}" '
                   f'stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(text(x, H - PAD_B + 18, f"{v:+.1f}".replace("+0.0", "0.0"), t,
                        size=11, color="muted", anchor="middle"))

    x_zero = px(0.0)
    out.append(f'<line x1="{x_zero:.1f}" y1="{PAD_T}" x2="{x_zero:.1f}" y2="{H - PAD_B}" '
               f'stroke="{t["ink2"]}" stroke-width="1.5"/>')
    out.append(text((PAD_L + W - PAD_R) / 2, H - 12, "information coefficient (rank correlation)", t,
                    size=11, color="muted", anchor="middle"))

    for i, row in table.iterrows():
        y = py(i)
        lo, hi, ic = px(row.ci_low), px(row.ci_high), px(row.ic)
        out.append(text(PAD_L - 14, y + 4, f"{int(row.horizon_days)} day"
                        + ("s" if row.horizon_days != 1 else ""), t, size=12, anchor="end"))
        out.append(f'<line x1="{lo:.1f}" y1="{y:.1f}" x2="{hi:.1f}" y2="{y:.1f}" '
                   f'stroke="{t["null"]}" stroke-width="7" stroke-linecap="round"/>')
        out.append(f'<circle cx="{ic:.1f}" cy="{y:.1f}" r="5.5" fill="{t["accent"]}"/>')
        out.append(text(W - PAD_R, y - 12, f"IC {row.ic:+.2f}   p = {row.p_value:.2f}", t,
                        size=11, color="muted", anchor="end"))

    out.append(text(PAD_L - 34, H - 30, "Bars are 95% confidence intervals. Every one crosses zero.", t,
                    size=11, color="ink2"))
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    frame_ = load_scored_calls()
    table = ic_across_horizons(frame_, PRIMARY_SCORE, HORIZONS)
    write(lambda t: render(t, table), "ic-by-horizon", Path(__file__).parent)
