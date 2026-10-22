"""Loader for the in-house ci-annotator output.

The videos sit in one folder (e.g. Cochlea_Data/renamed_surgery_videos_set1)
and every label set has its own annotation folder next to them
(micro_phase_annotations/, macro_phase_annotations/, the older annotations/,
...). An annotation folder holds, per video:
    <video>.csv          segments: video_id,subject,side,phase,start_frame,end_frame,...,fps,...
    <video>_frames.csv   per-frame export of the same labels: frame,time_s,label
plus optionally taxonomy.json (label names and the colors ci-annotator shows),
all_frames_labels.csv (every video in one per-frame file: ignored, it repeats
the files above) and logs/. The segments CSV is read when present, the
per-frame one only for videos that lack it. Any folder of CSVs in either
schema is accepted wherever it lives; `annotation_dirs()` finds them under a
video folder, so a label set added later needs no code or config change.

The 13-label micro-phase taxonomy includes explicit IDLE/Unknown/Hand
Occlusion/Blurry/Junk labels, so unlike Cataract-1K a gap here means "not
annotated yet", not idle.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from pathlib import Path

from ..colors import CI_INHOUSE_COLORS
from ..schema import Segment, VideoAnnotation

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
DEFAULT_FPS = 30.0
FRAMES_SUFFIX = "_frames"


def _schema(cols) -> str | None:
    cols = set(cols or [])
    if {"start_frame", "end_frame"} <= cols:
        return "segments"
    if "frame" in cols and cols & {"label", "phase"}:
        # a `video` column marks the all-videos export (all_frames_labels.csv),
        # which repeats the per-video files
        return "all-videos" if "video" in cols else "per-frame"
    return None


def _csvs(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.csv") if not p.name.startswith("._"))


def _csv_schema(path: Path) -> str | None:
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            return _schema(next(csv.reader(fh), []))
    except (OSError, UnicodeDecodeError):
        return None


def is_annotation_dir(folder: Path) -> bool:
    """True if `folder` holds at least one per-video CSV in a ci-annotator schema."""
    return any(_csv_schema(p) in ("segments", "per-frame") for p in _csvs(folder))


def annotation_dirs(root: Path, patterns: list[str] | None = None) -> list[Path]:
    """Annotation folders of the video folder `root`.

    `patterns` are globs relative to `root` or absolute paths (default: every
    direct subfolder); only folders holding ci-annotator CSVs are kept. With
    no patterns given and no such subfolder, `root` itself is tried.
    """
    root = Path(root)
    found: list[Path] = []
    for pattern in patterns or ["*"]:
        pattern = os.path.expanduser(pattern)
        if not os.path.isabs(pattern):
            pattern = os.path.join(glob.escape(str(root)), pattern)
        for hit in sorted(glob.glob(pattern)):
            folder = Path(hit)
            if folder.is_dir() and folder not in found and is_annotation_dir(folder):
                found.append(folder)
    if not found and not patterns and is_annotation_dir(root):
        found.append(root)
    return found


def _segments_from_rows(reader: csv.DictReader) -> tuple[list[Segment], float | None]:
    cols = set(reader.fieldnames or [])
    segments: list[Segment] = []
    fps: float | None = None
    kind = _schema(cols)
    if kind == "segments":
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
    if kind == "per-frame":
        key = "label" if "label" in cols else "phase"
        cur_lab, cur_start, last_f = None, 0, -2
        for row in reader:
            try:
                f = int(row["frame"])
            except (KeyError, ValueError, TypeError):
                continue
            try:  # no fps column: the timebase follows from frame / time_s
                t = float(row.get("time_s") or 0)
                if f > 0 and t > 0:
                    fps = f / t
            except ValueError:
                pass
            lab = (row.get(key) or "").strip() or None
            if cur_lab is not None and (lab != cur_lab or f != last_f + 1):
                segments.append(Segment(cur_lab, cur_start, last_f))
                cur_lab = None
            if lab is not None and cur_lab is None:
                cur_lab, cur_start = lab, f
            last_f = f
        if cur_lab is not None:
            segments.append(Segment(cur_lab, cur_start, last_f))
        return segments, fps
    raise ValueError("unrecognized CSV schema")


def _taxonomy_colors(folder: Path) -> dict[str, str]:
    path = folder / "taxonomy.json"
    if not path.exists():
        return {}
    try:
        labels = json.loads(path.read_text(encoding="utf-8"))["labels"]
        return {lab["name"]: lab["color"] for lab in labels
                if lab.get("name") and lab.get("color")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[ci-inhouse] {path}: {exc!r}, colors ignored", file=sys.stderr)
        return {}


def _video_index(folders: list[Path]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for folder in folders:
        if folder.is_dir():
            for p in sorted(folder.iterdir()):
                if p.suffix.lower() in VIDEO_EXTS and not p.name.startswith("._"):
                    index.setdefault(p.stem, p)
    return index


def load(root: Path, annotations: Path | None = None) -> list[VideoAnnotation]:
    """Videos of `root` labeled by the annotation folder `annotations`
    (default: root/annotations if it exists, else `root`). Video files are
    looked up in `root`, then in and next to the annotation folder."""
    root = Path(root)
    if annotations is None:
        annotations = root / "annotations" if (root / "annotations").is_dir() else root
    ann_dir = Path(annotations)
    video_files = _video_index(list(dict.fromkeys([root, ann_dir, ann_dir.parent])))
    colors = {**CI_INHOUSE_COLORS, **_taxonomy_colors(ann_dir)}

    # video id -> its CSVs, segments export first, per-frame export second
    files: dict[str, list[Path]] = {}
    for path in _csvs(ann_dir):
        if _csv_schema(path) == "all-videos":
            continue
        stem = path.stem
        if stem.endswith(FRAMES_SUFFIX):
            files.setdefault(stem[:-len(FRAMES_SUFFIX)], []).append(path)
        else:
            files.setdefault(stem, []).insert(0, path)
    if not files:
        print(f"[ci-inhouse] no CSVs under {ann_dir}", file=sys.stderr)

    out: list[VideoAnnotation] = []
    for video_id, paths in sorted(files.items()):
        for path in paths:
            try:
                with path.open(newline="", encoding="utf-8") as fh:
                    segments, fps = _segments_from_rows(csv.DictReader(fh))
                break
            except (ValueError, OSError, UnicodeDecodeError) as exc:
                print(f"[ci-inhouse] {path.name}: {exc}, skipped", file=sys.stderr)
        else:
            continue
        out.append(VideoAnnotation(
            dataset="ci-inhouse", video_id=video_id, fps=fps or DEFAULT_FPS,
            n_frames=None, segments=segments, video_path=video_files.get(video_id),
            colors=colors))
    return out
