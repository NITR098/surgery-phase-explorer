"""Cataract-1K phase-recognition subset loader.

Layout expected under `root`:
    annotations/case_XXXX/case_XXXX_annotations_phases.csv
        caseId,comment,frame,endFrame,sec,endSec   (frames in the video timebase)
    annotations/case_XXXX/case_XXXX_video.csv      caseId,physician,done,date,fps
    videos/case_XXXX.mp4

Interval annotations: only surgical phases are labeled; idle/transition time
between phases is left unlabeled (real gaps), and a phase may appear as
several instances (e.g. two Incision spans).

CAUTION: the CSV `frame` columns are in the *annotation* timebase from
`case_*_video.csv`, which does not always match the video container
(case_4863 is annotated at 240 fps but its mp4 plays at ~60 fps). When the
video is on disk we therefore rebuild frame indices from the `sec` columns and
the container fps, so every downstream tool can seek by frame index directly.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2

from ..schema import Segment, VideoAnnotation

DEFAULT_FPS = 60.0


def _case_fps(case_dir: Path, case: str) -> float:
    meta = case_dir / f"{case}_video.csv"
    if meta.exists():
        with meta.open(newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    return float(row["fps"])
                except (KeyError, ValueError, TypeError):
                    break
    print(f"[cataract1k] {case}: missing/bad fps, assuming {DEFAULT_FPS}", file=sys.stderr)
    return DEFAULT_FPS


def load(root: Path) -> list[VideoAnnotation]:
    root = Path(root)
    out: list[VideoAnnotation] = []
    case_dirs = sorted(d for d in (root / "annotations").glob("case_*") if d.is_dir())
    if not case_dirs:
        print(f"[cataract1k] no annotations/case_* under {root}", file=sys.stderr)
    for case_dir in case_dirs:
        case = case_dir.name
        phases_csv = case_dir / f"{case}_annotations_phases.csv"
        if not phases_csv.exists():
            print(f"[cataract1k] {case}: no phases CSV, skipped", file=sys.stderr)
            continue
        video_path = root / "videos" / f"{case}.mp4"
        fps, n_frames = _case_fps(case_dir, case), None
        if video_path.exists():
            cap = cv2.VideoCapture(str(video_path))
            if cap.isOpened():
                video_fps = cap.get(cv2.CAP_PROP_FPS) or 0
                n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None
                if video_fps > 0:
                    if abs(video_fps - fps) / fps > 0.02:
                        print(f"[cataract1k] {case}: annotation timebase {fps:g} fps != "
                              f"container {video_fps:.2f} fps — using `sec` columns",
                              file=sys.stderr)
                    fps = video_fps
            cap.release()

        segments: list[Segment] = []
        with phases_csv.open(newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    segments.append(Segment(row["comment"].strip(),
                                            round(float(row["sec"]) * fps),
                                            round(float(row["endSec"]) * fps)))
                except (KeyError, ValueError, TypeError):
                    print(f"[cataract1k] {case}: bad row {row}", file=sys.stderr)
        out.append(VideoAnnotation(
            dataset="cataract1k", video_id=case, fps=fps, n_frames=n_frames,
            segments=segments, video_path=video_path if video_path.exists() else None))
    return out
