"""Timeline ribbon figure: one row per video, colored phase spans, gray gaps."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from .colors import UNLABELED, label_colors
from .schema import VideoAnnotation


def plot_timelines(videos: list[VideoAnnotation], out_path: Path,
                   title: str | None = None) -> Path:
    colors = label_colors(videos)
    n = len(videos)
    fig_h = max(2.5, 0.32 * n + 1.6)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    for i, v in enumerate(videos):
        y = n - 1 - i
        end_min = (v.last_frame + 1) / v.fps / 60
        ax.broken_barh([(0, end_min)], (y + 0.08, 0.84), color=UNLABELED, lw=0)
        spans = [((s.start_frame / v.fps / 60), (s.n_frames / v.fps / 60))
                 for s in v.segments]
        span_colors = [colors[s.label] for s in v.segments]
        ax.broken_barh(spans, (y + 0.08, 0.84), color=span_colors, lw=0)
    ax.set_yticks([n - 1 - i + 0.5 for i in range(n)])
    ax.set_yticklabels([v.video_id for v in videos], fontsize=7)
    ax.set_ylim(0, n)
    ax.set_xlabel("time (min)")
    ax.set_title(title or (videos[0].dataset if videos else "timeline"))
    handles = [Patch(color=c, label=lab) for lab, c in colors.items()]
    handles.append(Patch(color=UNLABELED, label="(unlabeled)"))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.005, 1),
              fontsize=7, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
