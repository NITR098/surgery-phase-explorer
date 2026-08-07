"""Interactive OpenCV player: video + phase banner + colored timeline bar.

Made for boundary inspection: pause, single-frame stepping, and direct jumps
to the next/previous phase boundary. Keys (window focused):

    space        play / pause
    d / a        step +1 / -1 frame (pauses)
    D / A        step +10 / -10 frames
    l / j        jump +1s / -1s
    n / p        jump to next / previous phase boundary (first frame of a segment)
    ] / [        playback speed x2 / /2
    s            save annotated frame PNG next to the window title's path
    h            show / hide the key help footer
    q or ESC     quit

Clicking on the timeline bar seeks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

from .colors import UNLABELED, hex_to_bgr, label_colors
from .schema import VideoAnnotation

FONT = cv2.FONT_HERSHEY_SIMPLEX
BAR_H = 26
BANNER_H = 58
HELP_ITEMS = [  # ASCII only: cv2.putText cannot draw glyphs like the middle dot
    "space play/pause", "a/d +-1 frame", "A/D +-10", "j/l +-1s",
    "n/p prev/next boundary", "[/] speed", "s screenshot",
    "click bar to seek", "h hide help", "q quit",
]


def _fmt_t(frame: int, fps: float) -> str:
    t = frame / fps
    return f"{int(t // 60):02d}:{t % 60:06.3f}"


class Player:
    def __init__(self, v: VideoAnnotation, colors: dict[str, str] | None = None):
        if not v.video_path:
            raise SystemExit(f"{v.video_id}: no video file on disk for this annotation")
        self.v = v
        self.cap = cv2.VideoCapture(str(v.video_path))
        if not self.cap.isOpened():
            raise SystemExit(f"cannot open {v.video_path}")
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or (v.last_frame + 1)
        self.colors = colors or label_colors([v])
        self.frame_idx = 0
        self.playing = False
        self.speed = 1.0
        self.show_help = True
        self.cur_img: np.ndarray | None = None
        self.boundaries = sorted({s.start_frame for s in v.segments}
                                 | {s.end_frame + 1 for s in v.segments})
        self._per_frame = v.per_frame(max(self.n, v.last_frame + 1))

    # ---- drawing ----------------------------------------------------------
    def _timeline(self, width: int) -> np.ndarray:
        bar = np.full((BAR_H, width, 3), 0, np.uint8)
        bar[:] = hex_to_bgr(UNLABELED)
        total = max(self.n, self.v.last_frame + 1)
        for s in self.v.segments:
            x0 = int(s.start_frame / total * width)
            x1 = max(x0 + 1, int((s.end_frame + 1) / total * width))
            bar[:, x0:x1] = hex_to_bgr(self.colors[s.label])
        x = int(self.frame_idx / total * (width - 1))
        bar[:, max(0, x - 1):x + 2] = (255, 255, 255)
        return bar

    def _help_strip(self, width: int) -> np.ndarray:
        """Key bindings wrapped into as many lines as the window width needs."""
        scale, line_h, pad = 0.42, 20, 10
        sep = "   "
        lines: list[str] = []
        cur = ""
        for item in HELP_ITEMS:
            cand = item if not cur else cur + sep + item
            if cur and cv2.getTextSize(cand, FONT, scale, 1)[0][0] > width - 2 * pad:
                lines.append(cur)
                cur = item
            else:
                cur = cand
        lines.append(cur)
        strip = np.full((6 + line_h * len(lines), width, 3), 24, np.uint8)
        for i, line in enumerate(lines):
            cv2.putText(strip, line, (pad, line_h * (i + 1)), FONT, scale,
                        (170, 170, 170), 1, cv2.LINE_AA)
        return strip

    def render(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        scale = min(1.0, 1280 / w)
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
            h, w = img.shape[:2]
        lab = self._per_frame[self.frame_idx] if self.frame_idx < len(self._per_frame) else None
        color = hex_to_bgr(self.colors[lab]) if lab else hex_to_bgr(UNLABELED)
        banner = np.full((BANNER_H, w, 3), 32, np.uint8)
        banner[:, :10] = color
        cv2.putText(banner, lab or "(unlabeled)", (18, 24), FONT, 0.7, color, 2, cv2.LINE_AA)
        status = (f"#{self.frame_idx}/{self.n - 1}  t={_fmt_t(self.frame_idx, self.v.fps)}"
                  f"  {'PLAY' if self.playing else 'PAUSE'} x{self.speed:g}")
        cv2.putText(banner, status, (18, 48), FONT, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
        nxt = next((b for b in self.boundaries if b > self.frame_idx), None)
        if nxt is not None and nxt < self.n:
            nxt_lab = self._per_frame[nxt] if nxt < len(self._per_frame) else None
            dt = (nxt - self.frame_idx) / self.v.fps
            status_w = cv2.getTextSize(status, FONT, 0.5, 1)[0][0]
            cv2.putText(banner, f"next: {nxt_lab or '(unlabeled)'} in {dt:.2f}s (#{nxt})",
                        (max(w // 2, status_w + 40), 48), FONT, 0.5, (180, 220, 255),
                        1, cv2.LINE_AA)
        parts = [banner, img]
        if self.show_help:
            parts.append(self._help_strip(w))
        parts.append(self._timeline(w))
        return cv2.vconcat(parts)

    # ---- control ----------------------------------------------------------
    def seek(self, frame: int):
        self.frame_idx = int(np.clip(frame, 0, self.n - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_idx)
        ok, img = self.cap.read()
        if ok:
            self.cur_img = img

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and y >= param["img_h"] - BAR_H:
            total = max(self.n, self.v.last_frame + 1)
            self.seek(int(x / param["img_w"] * total))

    def run(self):
        win = f"{self.v.dataset}/{self.v.video_id}"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        self.seek(0)
        mouse_param = {"img_w": 1, "img_h": 1}
        cv2.setMouseCallback(win, self._on_mouse, mouse_param)
        while True:
            if self.playing:
                skip = int(self.speed) - 1
                for _ in range(max(0, skip)):
                    self.cap.grab()
                ok, img = self.cap.read()
                if ok:
                    self.cur_img = img
                    self.frame_idx = min(self.frame_idx + 1 + max(0, skip), self.n - 1)
                else:
                    self.playing = False
            frame = self.render(self.cur_img if self.cur_img is not None
                                else np.zeros((360, 640, 3), np.uint8))
            mouse_param["img_w"], mouse_param["img_h"] = frame.shape[1], frame.shape[0]
            cv2.imshow(win, frame)
            delay = max(1, int(1000 / (self.v.fps * max(self.speed, 0.125)))) if self.playing else 30
            k = cv2.waitKey(delay) & 0xFF
            if k in (ord("q"), 27):
                break
            elif k == ord(" "):
                self.playing = not self.playing
            elif k == ord("d"):
                self.playing = False; self.seek(self.frame_idx + 1)
            elif k == ord("a"):
                self.playing = False; self.seek(self.frame_idx - 1)
            elif k == ord("D"):
                self.playing = False; self.seek(self.frame_idx + 10)
            elif k == ord("A"):
                self.playing = False; self.seek(self.frame_idx - 10)
            elif k == ord("l"):
                self.seek(self.frame_idx + int(self.v.fps))
            elif k == ord("j"):
                self.seek(self.frame_idx - int(self.v.fps))
            elif k == ord("n"):
                nxt = next((b for b in self.boundaries if b > self.frame_idx), None)
                if nxt is not None:
                    self.playing = False; self.seek(nxt)
            elif k == ord("p"):
                prv = next((b for b in reversed(self.boundaries) if b < self.frame_idx), None)
                if prv is not None:
                    self.playing = False; self.seek(prv)
            elif k == ord("h"):
                self.show_help = not self.show_help
            elif k == ord("]"):
                self.speed = min(16.0, self.speed * 2)
            elif k == ord("["):
                self.speed = max(0.125, self.speed / 2)
            elif k == ord("s"):
                out = Path(f"{self.v.video_id}_f{self.frame_idx}.png")
                cv2.imwrite(str(out), frame)
                print(f"saved {out.resolve()}", file=sys.stderr)
        self.cap.release()
        cv2.destroyAllWindows()

    def dump_frame(self, frame: int, out_path: Path) -> Path:
        """Headless render of one annotated frame (used for testing/preview)."""
        self.seek(frame)
        img = self.render(self.cur_img if self.cur_img is not None
                          else np.zeros((360, 640, 3), np.uint8))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), img)
        self.cap.release()
        return out_path
