#!/usr/bin/env python
"""Inventory of configured datasets: videos, segments, coverage, phase order."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_atlas import dataset_names, load_dataset


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=dataset_names(), help="default: all configured")
    ap.add_argument("--sequences", action="store_true", help="print each video's phase order")
    args = ap.parse_args()

    for name in [args.dataset] if args.dataset else dataset_names():
        videos = load_dataset(name)
        print(f"\n=== {name}: {len(videos)} videos ===")
        for v in videos:
            mark = "video" if v.video_path else "  -  "
            print(f"  {v.video_id:<12} [{mark}] fps={v.fps:g} "
                  f"dur={v.duration_sec / 60:6.1f}m segs={len(v.segments):3d} "
                  f"cov={v.coverage():5.1%}")
            if args.sequences:
                print("      " + " > ".join(v.phase_sequence()))


if __name__ == "__main__":
    main()
