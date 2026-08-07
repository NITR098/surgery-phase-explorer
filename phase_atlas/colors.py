"""Stable label -> color assignment shared by every figure and the player.

Colors are assigned per dataset in order of first appearance across its
videos, so the timeline ribbon, boundary montages, and player all agree.
The in-house taxonomy keeps the exact colors used inside ci-annotator.
"""
from __future__ import annotations

from .schema import VideoAnnotation

# matches ci-annotator/annotator/core.py LABELS
CI_INHOUSE_COLORS = {
    "Mastoidectomy":       "#1f77b4",
    "Cochleostomy":        "#2ca02c",
    "Sizing":              "#9467bd",
    "Electrode Loading":   "#ff7f0e",
    "Electrode Insertion": "#d62728",
    "Fluid Suction":       "#843c39",
    "Lubrication":         "#8c6d31",
    "Packing":             "#17becf",
    "IDLE":                "#bcbd22",
    "Unknown":             "#7f7f7f",
    "Hand Occlusion":      "#393b79",
    "Blurry":              "#8c564b",
    "Junk":                "#e377c2",
}

# tab20-ish palette, high-contrast ordering
PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
    "#e377c2", "#17becf", "#bcbd22", "#393b79", "#843c39", "#8c6d31",
    "#7b4173", "#637939", "#d6616b", "#ce6dbd", "#9c9ede", "#e7ba52",
]
UNLABELED = "#d9dee3"


def label_colors(videos: list[VideoAnnotation]) -> dict[str, str]:
    labels: list[str] = []
    for v in videos:
        for lab in v.labels():
            if lab not in labels:
                labels.append(lab)
    if videos and videos[0].dataset == "ci-inhouse":
        base = dict(CI_INHOUSE_COLORS)
        extra = [lab for lab in labels if lab not in base]
        base.update({lab: PALETTE[i % len(PALETTE)] for i, lab in enumerate(extra)})
        return {lab: base[lab] for lab in labels}
    return {lab: PALETTE[i % len(PALETTE)] for i, lab in enumerate(sorted(labels))}


def hex_to_bgr(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return b, g, r
