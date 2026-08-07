"""Cholec80 (and same-format m2cai16-workflow) loader.

Layout expected under `root`:
    phase_annotations/videoNN-phase.txt   per-frame TSV "Frame\tPhase", 0-based
    videos/videoNN.mp4                    optional (only some may be extracted)

Videos and annotations are both 25 fps; every frame is labeled (no gaps).
The annotation file occasionally has one row more or fewer than the container
reports — harmless for convention analysis, so it is not "fixed" here.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..schema import Segment, VideoAnnotation

FPS = 25.0


def load(root: Path) -> list[VideoAnnotation]:
    root = Path(root)
    out: list[VideoAnnotation] = []
    ann_files = sorted((root / "phase_annotations").glob("*-phase.txt"))
    if not ann_files:
        print(f"[cholec80] no phase_annotations/*-phase.txt under {root}", file=sys.stderr)
    for path in ann_files:
        video_id = path.name.replace("-phase.txt", "")
        segments: list[Segment] = []
        n_frames = 0
        cur_label, cur_start = None, 0
        with path.open() as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 2 or parts[0] == "Frame":
                    continue
                try:
                    frame = int(parts[0])
                except ValueError:
                    print(f"[cholec80] {path.name}: bad row {line!r}", file=sys.stderr)
                    continue
                label = parts[1]
                if label != cur_label:
                    if cur_label is not None:
                        segments.append(Segment(cur_label, cur_start, frame - 1))
                    cur_label, cur_start = label, frame
                n_frames = frame + 1
        if cur_label is not None:
            segments.append(Segment(cur_label, cur_start, n_frames - 1))
        video_path = root / "videos" / f"{video_id}.mp4"
        out.append(VideoAnnotation(
            dataset="cholec80", video_id=video_id, fps=FPS, n_frames=n_frames,
            segments=segments, video_path=video_path if video_path.exists() else None))
    return out
