#!/usr/bin/env python
"""Timeline ribbon per dataset -> outputs/timelines/<dataset>.png"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_atlas import dataset_names, load_dataset
from phase_atlas.timeline import plot_timelines

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "timelines"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=dataset_names(), help="default: all configured")
    ap.add_argument("--max-videos", type=int, help="only the first N videos")
    args = ap.parse_args()

    for name in [args.dataset] if args.dataset else dataset_names():
        videos = load_dataset(name)
        if args.max_videos:
            videos = videos[:args.max_videos]
        path = plot_timelines(videos, OUT_DIR / f"{name}.png",
                              title=f"{name} — {len(videos)} videos")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
