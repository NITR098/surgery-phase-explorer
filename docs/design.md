# Dataset Annotation Explorer — design

2026-08-07

## Purpose

Load public surgical-video datasets together with their phase annotations and
visualize them (timeline ribbons, an interactive video player with the label
overlaid, and frame strips around every phase boundary) to study **how each
dataset was annotated**: where boundaries are placed, whether transition /
idle periods are labeled, and how ambiguous frames are handled. The findings
feed the annotation protocol for the in-house cochlear-implant dataset
(labeled with `ci-annotator`).

## Datasets available locally

| name | location | annotation format | convention |
|---|---|---|---|
| cholec80 | `data/cholec80/` (annotations for all 80 videos + 3 sample videos extracted from `~/Downloads/cholec80.zip`) | per-frame TSV `Frame\tPhase`, 0-based, 25 fps | every frame labeled — no gaps, hard cuts between phases |
| cataract1k | `../ci-video-processing/data/cataract1k/` (56 cases, videos + CSVs) | interval CSV `caseId,comment,frame,endFrame,sec,endSec`, 60 fps (`case_*_video.csv`) | gaps between phases left **unlabeled** (idle), phases may repeat |
| ci-inhouse | any `ci-annotator` folder (`annotations/*.csv` beside the videos) | segments CSV `phase,start_frame,end_frame,fps,…` or per-frame `frame,time_s,label` | 13-label taxonomy incl. explicit IDLE/Unknown/Blurry |

m2cai16-workflow uses the same per-frame format as cholec80, so its loader is
reused via config (`"kind": "cholec80"`) if that dataset is downloaded later.

## Approach

Small Python package (`phase_atlas`) + thin CLI scripts, run with the existing
`torch` conda env (`/opt/miniconda3/envs/torch/bin/python` — has cv2, numpy,
matplotlib, pandas). No new dependencies.

Alternatives considered: (a) extending the existing PySide6 `ci-annotator`
Review tab to open foreign datasets — rejected: couples exploratory tooling to
the production annotation tool and Qt; (b) a Streamlit web app — rejected:
new dependency, slower frame-accurate stepping than OpenCV.

## Unified schema (`phase_atlas/schema.py`)

- `Segment(label, start_frame, end_frame, note)` — frames **inclusive**, in the
  annotation timebase (`fps`), matching the ci-annotator convention.
- `VideoAnnotation(dataset, video_id, fps, n_frames, segments, video_path)` with
  helpers: `gaps()` (unlabeled ranges), `transitions()` (prev/next label, gap
  length between them), `per_frame()`, `labels()`, `coverage()`.
- Loaders (`phase_atlas/loaders/`) each expose
  `load(root: Path) -> list[VideoAnnotation]`; `datasets.json` maps a dataset
  name → `{kind, root}` so paths are edited in one place.

## Tools (scripts/)

1. `plot_timelines.py` — one ribbon row per video, colored phase spans, gray
   gaps; per-dataset PNG in `outputs/timelines/`.
2. `play.py` — OpenCV player: phase banner + colored timeline bar + playhead;
   pause, frame-step, jump to next/prev boundary, speed control. This is the
   frame-by-frame boundary inspection tool.
3. `export_boundaries.py` — for every transition, a montage strip of frames
   sampled around the boundary (±2 s and the exact cut) with frame/Δt/label
   captions → `outputs/boundaries/<dataset>/<video>/`. Answers "what does the
   annotator consider the first frame of the next phase?"
4. `report_conventions.py` — markdown report per dataset: label set, phase
   duration/instance stats, coverage vs unlabeled gaps, phase-order variability,
   transition matrix, direct-cut vs gapped-transition fractions →
   `outputs/reports/`.

## Error handling & verification

- Loaders tolerate the known Cholec80 off-by-one (annotation rows vs container
  frame count) and skip malformed rows with a warning, never silently.
- Player/montage verified headless (render frames to PNG); loaders and
  analysis verified against the real local data (spot-checked numbers).
