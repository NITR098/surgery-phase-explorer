"""Loader for the in-house ci-annotator output.

`root` is a video folder as used by ci-annotator: videos at the top level and
an `annotations/` subfolder with one CSV per video. Both CSV schemas the tool
writes are accepted:
    segments:  video_id,subject,side,phase,start_frame,end_frame,...,fps,...
    per-frame: frame,time_s,label
The 13-label taxonomy includes explicit IDLE/Unknown/Hand Occlusion/Blurry/Junk
labels, so unlike Cataract-1K a gap here means "not annotated yet", not idle.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from ..schema import Segment, VideoAnnotation

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
DEFAULT_FPS = 30.0


def _segments_from_rows(reader: csv.DictReader) -> tuple[list[Segment], float | None]:
    cols = set(reader.fieldnames or [])
    segments: list[Segment] = []
    fps: float | None = None
    if {"start_frame", "end_frame"} <= cols:
        label_key = "phase" if "phase" in cols else "label"
        for row in reader:
            try:
                segments.append(Segment(row.get(label_key, ""), int(row["start_frame"]),
                                        int(row["end_frame"]), row.get("notes", "") or ""))
            except (ValueError, TypeError):
                continue
            if fps is None:
                try:
                    fps = float(row.get("fps") or 0) or None
                except ValueError:
                    pass
        return segments, fps
    if "frame" in cols and ("label" in cols or "phase" in cols):
        key = "label" if "label" in cols else "phase"
        cur_lab, cur_start, last_f = None, 0, -2
        for row in reader:
            try:
                f = int(row["frame"])
            except (KeyError, ValueError, TypeError):
                continue
            lab = (row.get(key) or "").strip() or None
            if cur_lab is not None and (lab != cur_lab or f != last_f + 1):
                segments.append(Segment(cur_lab, cur_start, last_f))
                cur_lab = None
            if lab is not None and cur_lab is None:
                cur_lab, cur_start = lab, f
            last_f = f
        if cur_lab is not None:
            segments.append(Segment(cur_lab, cur_start, last_f))
        return segments, None
    raise ValueError("unrecognized CSV schema")


def load(root: Path) -> list[VideoAnnotation]:
    root = Path(root)
    ann_dir = root / "annotations" if (root / "annotations").is_dir() else root
    out: list[VideoAnnotation] = []
    csvs = sorted(p for p in ann_dir.glob("*.csv") if not p.name.startswith("._"))
    if not csvs:
        print(f"[ci-inhouse] no CSVs under {ann_dir}", file=sys.stderr)
    for path in csvs:
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                segments, fps = _segments_from_rows(csv.DictReader(fh))
        except (ValueError, OSError) as exc:
            print(f"[ci-inhouse] {path.name}: {exc}, skipped", file=sys.stderr)
            continue
        stem = path.stem
        video_path = next((root / (stem + ext) for ext in VIDEO_EXTS
                           if (root / (stem + ext)).exists()), None)
        out.append(VideoAnnotation(
            dataset="ci-inhouse", video_id=stem, fps=fps or DEFAULT_FPS,
            n_frames=None, segments=segments, video_path=video_path))
    return out
