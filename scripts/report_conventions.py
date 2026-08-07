#!/usr/bin/env python
"""Annotation-convention report -> outputs/reports/<dataset>.md (+ transition matrix PNG)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_atlas import dataset_names, load_dataset
from phase_atlas.analysis import write_report

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "reports"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=dataset_names(), help="default: all configured")
    args = ap.parse_args()

    for name in [args.dataset] if args.dataset else dataset_names():
        videos = load_dataset(name)
        md = write_report(videos, OUT_DIR)
        print(f"wrote {md}")
        print(md.read_text())


if __name__ == "__main__":
    main()
