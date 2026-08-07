"""Boundary montages: a strip of frames around each phase transition.

For every transition the strip shows context frames anchored on the LAST
frame of the earlier phase and the FIRST frame of the next phase (plus the
middle of the unlabeled gap, when there is one). Captions carry the frame
index, timestamp, offset from the anchor, and the label at that frame, with
the label color as a bar over each tile — so you can see exactly which visual
event the annotator treated as the boundary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

from .colors import UNLABELED, hex_to_bgr, label_colors
from .schema import Transition, VideoAnnotation

TILE_W = 300
CAPTION_H = 46
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _fmt_t(frame: int, fps: float) -> str:
    t = frame / fps
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def _grab(cap: cv2.VideoCapture, frame: int) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ok, img = cap.read()
    return img if ok else None


def _tile(img: np.ndarray | None, tile_h: int, color: str, lines: list[str]) -> np.ndarray:
    if img is None:
        img = np.full((tile_h, TILE_W, 3), 30, np.uint8)
    else:
        img = cv2.resize(img, (TILE_W, tile_h))
    out = np.full((tile_h + CAPTION_H + 6, TILE_W, 3), 255, np.uint8)
    out[:6] = hex_to_bgr(color)
    out[6:6 + tile_h] = img
    for i, line in enumerate(lines[:2]):
        cv2.putText(out, line, (4, tile_h + 6 + 18 + 20 * i), FONT, 0.42, (20, 20, 20),
                    1, cv2.LINE_AA)
    return out


def transition_strip(v: VideoAnnotation, cap: cv2.VideoCapture, tr: Transition,
                     colors: dict[str, str], context_secs: tuple[float, ...] = (2.0, 0.5),
                     ) -> np.ndarray:
    probe = _grab(cap, tr.prev_end)
    tile_h = int(TILE_W * (probe.shape[0] / probe.shape[1])) if probe is not None else 170

    def tiles_for(anchor: int, offsets: list[int], anchor_name: str) -> list[np.ndarray]:
        tiles = []
        for off in offsets:
            f = anchor + off
            lab = v.label_at(f)
            color = colors.get(lab, UNLABELED) if lab else UNLABELED
            sign = f"{off:+d}f" if off else anchor_name
            tiles.append(_tile(_grab(cap, f), tile_h, color,
                               [f"{sign}  #{f}  {_fmt_t(f, v.fps)}", lab or "(unlabeled)"]))
        return tiles

    before = sorted({-int(s * v.fps) for s in context_secs} | {-1}) if context_secs else [-1]
    after = sorted({int(s * v.fps) for s in context_secs} | {1}) if context_secs else [1]
    tiles = tiles_for(tr.prev_end, before + [0], "LAST")
    if not tr.is_cut:
        mid = (tr.prev_end + tr.next_start) // 2
        gap_s = tr.gap_frames / v.fps
        tiles.append(_tile(_grab(cap, mid), tile_h, UNLABELED,
                           [f"gap mid  #{mid}  {_fmt_t(mid, v.fps)}",
                            f"(unlabeled {tr.gap_frames}f = {gap_s:.1f}s)"]))
    tiles += tiles_for(tr.next_start, [0] + after, "FIRST")

    strip = cv2.hconcat(tiles)
    header = np.full((34, strip.shape[1], 3), 245, np.uint8)
    kind = "hard cut" if tr.is_cut else f"gap {tr.gap_frames}f ({tr.gap_frames / v.fps:.1f}s)"
    cv2.putText(header,
                f"{v.dataset}/{v.video_id}   {tr.prev_label} -> {tr.next_label}   [{kind}]",
                (8, 23), FONT, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    return cv2.vconcat([header, strip])


def export_boundaries(v: VideoAnnotation, out_dir: Path,
                      context_secs: tuple[float, ...] = (2.0, 0.5),
                      colors: dict[str, str] | None = None) -> list[Path]:
    """`colors` should be the dataset-wide label_colors() map so montages match
    the timeline figure; falls back to this video's own labels."""
    if not v.video_path:
        print(f"[montage] {v.video_id}: no video file, skipped", file=sys.stderr)
        return []
    cap = cv2.VideoCapture(str(v.video_path))
    if not cap.isOpened():
        print(f"[montage] {v.video_id}: cannot open {v.video_path}", file=sys.stderr)
        return []
    colors = colors or label_colors([v])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, tr in enumerate(v.transitions(), 1):
        strip = transition_strip(v, cap, tr, colors, context_secs)
        safe = lambda s: s.replace("/", "-").replace(" ", "_")
        path = out_dir / f"{i:02d}_{safe(tr.prev_label)}__{safe(tr.next_label)}.png"
        cv2.imwrite(str(path), strip)
        paths.append(path)
    cap.release()
    return paths
