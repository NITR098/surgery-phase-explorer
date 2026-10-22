"""Unified in-memory representation of a phase-annotated surgical video.

Frames are inclusive [start_frame, end_frame] in the annotation timebase
(`fps`), matching the ci-annotator segments convention. Datasets that ship
per-frame labels (Cholec80) are run-length-encoded into segments on load, so
"gap" and "transition" queries mean the same thing for every dataset.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Segment:
    label: str
    start_frame: int
    end_frame: int          # inclusive
    note: str = ""

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame + 1


@dataclass
class Transition:
    """Boundary between two consecutive labeled segments.

    gap_frames == 0 means a hard cut (next starts on the frame right after
    prev ends); > 0 means unlabeled frames sit between the two phases.
    """
    prev_label: str
    next_label: str
    prev_end: int           # last frame of the earlier segment
    next_start: int         # first frame of the later segment

    @property
    def gap_frames(self) -> int:
        return self.next_start - self.prev_end - 1

    @property
    def is_cut(self) -> bool:
        return self.gap_frames == 0


@dataclass
class VideoAnnotation:
    dataset: str
    video_id: str
    fps: float                       # annotation timebase
    n_frames: int | None             # video length if known (annotation timebase)
    segments: list[Segment] = field(default_factory=list)
    video_path: Path | None = None
    colors: dict[str, str] = field(default_factory=dict)  # label -> hex, if the annotation tool fixes them

    def __post_init__(self):
        self.segments.sort(key=lambda s: (s.start_frame, s.end_frame))

    # ---- basic properties -------------------------------------------------
    def labels(self) -> list[str]:
        """Distinct labels in order of first appearance."""
        seen: list[str] = []
        for s in self.segments:
            if s.label not in seen:
                seen.append(s.label)
        return seen

    def phase_sequence(self) -> list[str]:
        """Segment labels with consecutive duplicates collapsed."""
        seq: list[str] = []
        for s in self.segments:
            if not seq or seq[-1] != s.label:
                seq.append(s.label)
        return seq

    @property
    def last_frame(self) -> int:
        """End of the annotated extent (n_frames-1 if known, else last segment end)."""
        end = self.segments[-1].end_frame if self.segments else 0
        if self.n_frames:
            end = max(end, self.n_frames - 1)
        return end

    @property
    def duration_sec(self) -> float:
        return (self.last_frame + 1) / self.fps if self.fps else 0.0

    # ---- annotation-convention queries -------------------------------------
    def gaps(self, include_edges: bool = False) -> list[tuple[int, int]]:
        """Unlabeled inclusive frame ranges between segments (and, optionally,
        before the first / after the last segment)."""
        out: list[tuple[int, int]] = []
        if not self.segments:
            return [(0, self.last_frame)] if include_edges and self.n_frames else []
        if include_edges and self.segments[0].start_frame > 0:
            out.append((0, self.segments[0].start_frame - 1))
        cursor = self.segments[0].end_frame
        for s in self.segments[1:]:
            if s.start_frame > cursor + 1:
                out.append((cursor + 1, s.start_frame - 1))
            cursor = max(cursor, s.end_frame)
        if include_edges and self.n_frames and cursor < self.n_frames - 1:
            out.append((cursor + 1, self.n_frames - 1))
        return out

    def transitions(self) -> list[Transition]:
        out: list[Transition] = []
        for a, b in zip(self.segments, self.segments[1:]):
            if a.label != b.label:
                out.append(Transition(a.label, b.label, a.end_frame, b.start_frame))
        return out

    def coverage(self) -> float:
        """Fraction of [0, last_frame] covered by labeled segments."""
        total = self.last_frame + 1
        if total <= 0:
            return 0.0
        covered = 0
        cursor = -1
        for s in self.segments:
            lo, hi = max(s.start_frame, cursor + 1), s.end_frame
            if hi >= lo:
                covered += hi - lo + 1
                cursor = hi
        return covered / total

    def label_at(self, frame: int) -> str | None:
        for s in self.segments:
            if s.start_frame <= frame <= s.end_frame:
                return s.label
            if s.start_frame > frame:
                break
        return None

    def per_frame(self, n: int | None = None) -> list[str | None]:
        n = n if n is not None else self.last_frame + 1
        arr: list[str | None] = [None] * n
        for s in self.segments:
            for f in range(max(0, s.start_frame), min(n, s.end_frame + 1)):
                arr[f] = s.label
        return arr
