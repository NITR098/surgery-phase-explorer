#!/usr/bin/env python
"""Boundary montage strips for every transition ->
outputs/boundaries/<dataset>/<video>/NN_<prev>__<next>.png"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_atlas import dataset_names, load_dataset
from phase_atlas.colors import label_colors
from phase_atlas.montage import export_boundaries

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "boundaries"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True, choices=dataset_names())
    ap.add_argument("--video", action="append",
                    help="video id (repeatable); default: every video that has a file")
    ap.add_argument("--context", type=float, nargs="+", default=[2.0, 0.5],
                    metavar="SECS", help="context offsets around each boundary")
    args = ap.parse_args()

    videos = load_dataset(args.dataset)
    colors = label_colors(videos)
    if args.video:
        missing = set(args.video) - {v.video_id for v in videos}
        if missing:
            raise SystemExit(f"not in {args.dataset}: {', '.join(sorted(missing))}")
        videos = [v for v in videos if v.video_id in set(args.video)]
    videos = [v for v in videos if v.video_path]
    if not videos:
        raise SystemExit("no selected video has a video file on disk")
    for v in videos:
        paths = export_boundaries(v, OUT_DIR / args.dataset / v.video_id,
                                  context_secs=tuple(args.context), colors=colors)
        print(f"{v.video_id}: {len(paths)} transition strips -> "
              f"{OUT_DIR / args.dataset / v.video_id}")


if __name__ == "__main__":
    main()
