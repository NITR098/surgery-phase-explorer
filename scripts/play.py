#!/usr/bin/env python
"""Interactive player: video + phase banner + timeline. See phase_atlas/player.py
for the key bindings (space, a/d frame-step, n/p boundary jump, ...)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_atlas import dataset_names, get_video, load_dataset
from phase_atlas.colors import label_colors
from phase_atlas.player import Player


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True, choices=dataset_names())
    ap.add_argument("--video", required=True, help="video id, e.g. video13 / case_5058")
    ap.add_argument("--start-frame", type=int, default=0)
    ap.add_argument("--dump-frame", type=int, metavar="N",
                    help="headless: render annotated frame N to --out and exit")
    ap.add_argument("--out", type=Path, default=Path("frame.png"))
    args = ap.parse_args()

    videos = load_dataset(args.dataset)
    v = get_video(args.dataset, args.video)
    player = Player(v, colors=label_colors(videos))
    if args.dump_frame is not None:
        print(f"wrote {player.dump_frame(args.dump_frame, args.out)}")
        return
    player.seek(args.start_frame)
    player.run()


if __name__ == "__main__":
    main()
