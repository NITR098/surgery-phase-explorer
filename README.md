# Surgery Phase Explorer

Load public surgical-video datasets with their **phase annotations** and
inspect them — timeline ribbons, an interactive player with the label overlay,
and frame strips around every phase boundary — to learn **how each dataset was
annotated** (boundary placement, transition handling, ambiguous frames) and
distill those conventions into the annotation protocol for the in-house
cochlear-implant dataset.

## Setup

No install needed — everything runs with the existing `torch` conda env:

```bash
PY=/opt/miniconda3/envs/torch/bin/python   # has cv2, numpy, matplotlib
```

Datasets are wired up in [`datasets.json`](datasets.json) (`name -> {kind, root}`):

| name | root | status |
|---|---|---|
| `cholec80` | `~/Documents/Dataset/Surgery_Datasets/cholec80/` | complete: 80 videos + 80 phase annotations |
| `cataract1k` | `~/Documents/Dataset/Surgery_Datasets/cataract1k/` | complete: 56 cases, videos + annotations |

To view the **in-house CI annotations** with the same tools, add to `datasets.json`:

```json
"ci-inhouse": { "kind": "ci-inhouse", "root": "/path/to/your/video-folder" }
```

where the folder is a ci-annotator workspace (videos + `annotations/*.csv`).
`m2cai16-workflow`, if ever downloaded, uses `"kind": "cholec80"` (same format).

## Scripts

```bash
$PY scripts/list_videos.py [--dataset X] [--sequences]     # inventory + phase orders
$PY scripts/plot_timelines.py [--dataset X]                # -> outputs/timelines/<X>.png
$PY scripts/report_conventions.py [--dataset X]            # -> outputs/reports/<X>.md + transition matrix
$PY scripts/export_boundaries.py --dataset X [--video ID]  # -> outputs/boundaries/X/ID/*.png
$PY scripts/play.py --dataset X --video ID                 # interactive player
```

Player keys: `space` play/pause · `a`/`d` ±1 frame · `A`/`D` ±10 · `j`/`l` ±1 s ·
`n`/`p` next/prev phase boundary · `[`/`]` speed · `s` screenshot · `h` hide/show
the in-window key help · `q` quit. Click the bottom timeline bar to seek.
The same key list is shown as a footer inside the player window.

The boundary strips are the core tool for protocol design: each transition is
one PNG showing the LAST frame of the previous phase, the FIRST frame of the
next, ±context frames, and (Cataract-1K) the unlabeled gap between them.

## Annotation conventions found so far

Full numbers in `outputs/reports/`. The two references disagree on every axis,
so the in-house protocol has to pick a side deliberately:

| axis | Cholec80 (laparoscopy) | Cataract-1K (microscope) |
|---|---|---|
| coverage | 100% — every frame has exactly one phase | 84.5% mean — only surgical activity labeled |
| transitions | 465/465 hard cuts; the first frame of the next phase IS the boundary decision | 717/717 gapped; median 2.6 s unlabeled between phases (tool exchange) |
| idle handling | absorbed into the surrounding phases | left unlabeled (no idle class) |
| phase grammar | strictly linear, no phase recurs; 6 order variants across 80 videos | phases recur (Viscoelastic 2.0x, Tonifying/Antibiotics 2.2x per video); 10 order variants |
| start of video | always labeled from frame 0 | 39/56 videos start unlabeled |
| shortest instance | 4 s (GallbladderRetraction) | 0.02–1 s micro-instances |
| boundary cue (from strips) | activity change while instruments stay in view | instrument enters / leaves the eye |

Relevance for the CI protocol: the in-house 13-label taxonomy (explicit IDLE /
Unknown / Hand Occlusion / Blurry / Junk) is closer to Cholec80's exhaustive
style but with the idle period made explicit — effectively a third convention:
*exhaustive labeling with a dedicated idle class*, which keeps both the
Cataract-1K-style "activity boundaries" (phase = instrument working) and full
frame coverage for training.

Known quirk handled by the loader: `case_4863`'s annotation timebase is 240 fps
while its mp4 is ~60 fps; frames are rebuilt from the `sec` columns.

## Layout

```
phase_atlas/            # library: schema, loaders, colors, viz, analysis
  schema.py             # Segment / Transition / VideoAnnotation (+gaps/transitions/coverage)
  loaders/              # cholec80.py, cataract1k.py, ci_inhouse.py
  timeline.py           # ribbon figure        montage.py  # boundary strips
  player.py             # interactive player   analysis.py # convention report
scripts/                # CLI wrappers (see above)
outputs/                # generated figures/reports (git-ignored)
docs/design.md          # design notes
```
