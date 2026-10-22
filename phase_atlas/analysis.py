"""Annotation-convention report: how a dataset was labeled, as markdown.

Quantifies the conventions that matter when writing an annotation protocol:
  * coverage — are all frames labeled, or only surgical activity (gaps)?
  * boundary handling — hard cuts vs unlabeled transition gaps, gap durations
  * phase grammar — strict linear order vs variable order, repeated instances
  * granularity — instance durations, shortest annotated spans
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .colors import label_colors
from .schema import VideoAnnotation


def _fmt_s(sec: float) -> str:
    return f"{sec / 60:.1f} min" if sec >= 90 else f"{sec:.1f} s"


def transition_matrix_png(videos: list[VideoAnnotation], out_path: Path) -> Path:
    labels: list[str] = []
    for v in videos:
        for lab in v.labels():
            if lab not in labels:
                labels.append(lab)
    idx = {lab: i for i, lab in enumerate(labels)}
    mat = np.zeros((len(labels), len(labels)), int)
    for v in videos:
        for tr in v.transitions():
            mat[idx[tr.prev_label], idx[tr.next_label]] += 1
    fig, ax = plt.subplots(figsize=(1.1 + 0.55 * len(labels), 1.0 + 0.5 * len(labels)))
    ax.imshow(mat, cmap="Blues")
    for i in range(len(labels)):
        for j in range(len(labels)):
            if mat[i, j]:
                ax.text(j, i, str(mat[i, j]), ha="center", va="center", fontsize=8,
                        color="white" if mat[i, j] > mat.max() * 0.6 else "black")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_xlabel("next phase")
    ax.set_ylabel("previous phase")
    ax.set_title(f"{videos[0].dataset}: transition counts")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def conventions_report(videos: list[VideoAnnotation]) -> str:
    name = videos[0].dataset
    lines = [f"# {name}: annotation conventions", ""]

    # ---- inventory ---------------------------------------------------------
    durs = [v.duration_sec for v in videos]
    fpss = sorted({round(v.fps, 2) for v in videos})
    covs = [v.coverage() for v in videos]
    lines += [
        "## Inventory",
        f"- **{len(videos)} annotated videos** ({sum(1 for v in videos if v.video_path)} "
        f"with a video file on disk), fps: {', '.join(map(str, fpss))}",
        f"- duration: mean {_fmt_s(mean(durs))}, min {_fmt_s(min(durs))}, max {_fmt_s(max(durs))}",
        f"- labeled coverage of the timeline: mean {mean(covs):.1%}, "
        f"min {min(covs):.1%}, max {max(covs):.1%}",
        "",
    ]

    # ---- per-phase stats ---------------------------------------------------
    inst: dict[str, list[float]] = defaultdict(list)     # instance durations (s)
    vids_with: dict[str, int] = Counter()
    for v in videos:
        for s in v.segments:
            inst[s.label].append(s.n_frames / v.fps)
        for lab in v.labels():
            vids_with[lab] += 1
    lines += ["## Phases",
              "| phase | videos | instances | inst/video | total | mean inst | median inst | min inst |",
              "|---|---|---|---|---|---|---|---|"]
    for lab, ds in sorted(inst.items(), key=lambda kv: -sum(kv[1])):
        lines.append(f"| {lab} | {vids_with[lab]}/{len(videos)} | {len(ds)} "
                     f"| {len(ds) / vids_with[lab]:.2f} | {_fmt_s(sum(ds))} "
                     f"| {_fmt_s(mean(ds))} | {_fmt_s(median(ds))} | {_fmt_s(min(ds))} |")
    lines.append("")

    # ---- boundary handling ---------------------------------------------------
    all_tr = [(v, tr) for v in videos for tr in v.transitions()]
    cuts = [t for _, t in all_tr if t.is_cut]
    gaps = [(v, t) for v, t in all_tr if not t.is_cut]
    lines += ["## Boundary handling",
              f"- {len(all_tr)} transitions: **{len(cuts)} hard cuts "
              f"({len(cuts) / len(all_tr):.0%})**, {len(gaps)} with an unlabeled gap "
              f"({len(gaps) / len(all_tr):.0%})"]
    if gaps:
        gap_s = [t.gap_frames / v.fps for v, t in gaps]
        lines.append(f"- gap length: mean {_fmt_s(mean(gap_s))}, median {_fmt_s(median(gap_s))}, "
                     f"max {_fmt_s(max(gap_s))}")
        pair_gaps: dict[tuple[str, str], list[float]] = defaultdict(list)
        for v, t in gaps:
            pair_gaps[(t.prev_label, t.next_label)].append(t.gap_frames / v.fps)
        top = sorted(pair_gaps.items(), key=lambda kv: -len(kv[1]))[:8]
        lines.append("- most-gapped transitions: " + "; ".join(
            f"{a}→{b} ({len(ds)}x, median {_fmt_s(median(ds))})" for (a, b), ds in top))
    edge_start = sum(1 for v in videos if v.segments and v.segments[0].start_frame > 0)
    lines += [f"- videos whose first labeled frame is not frame 0: {edge_start}/{len(videos)}", ""]

    # ---- phase grammar ---------------------------------------------------------
    orders = Counter(tuple(v.phase_sequence()) for v in videos)
    repeats = Counter()
    for v in videos:
        seq = v.phase_sequence()
        for lab, cnt in Counter(seq).items():
            if cnt > 1:
                repeats[lab] += 1
    lines += ["## Phase grammar",
              f"- {len(orders)} distinct phase orders across {len(videos)} videos "
              f"(most common covers {orders.most_common(1)[0][1]}/{len(videos)})",
              f"- most common order: {' → '.join(orders.most_common(1)[0][0])}"]
    if repeats:
        lines.append("- phases that RECUR within a video (non-consecutive instances): "
                     + "; ".join(f"{lab} (in {n} videos)" for lab, n in repeats.most_common(6)))
    else:
        lines.append("- no phase ever recurs within a video (strictly linear grammar)")
    lines.append("")

    # ---- convention summary ------------------------------------------------------
    lines.append("## Convention summary")
    if mean(covs) > 0.999:
        lines.append("- **Exhaustive labeling**: every frame belongs to exactly one phase; "
                     "transitions are hard cuts, so the boundary frame itself carries the "
                     "annotator's decision of when the next phase starts.")
    else:
        lines.append(f"- **Activity-only labeling**: only surgical activity is annotated "
                     f"({mean(covs):.0%} of the timeline); idle/transition periods are left "
                     f"unlabeled instead of being given an idle class.")
    short = [(lab, min(ds)) for lab, ds in inst.items() if min(ds) < 3]
    if short:
        lines.append("- shortest annotated instances: " + "; ".join(
            f"{lab} {_fmt_s(d)}" for lab, d in sorted(short, key=lambda kv: kv[1])[:5])
            + " — a lower bound on the segment granularity the annotators used.")
    return "\n".join(lines) + "\n"


def write_report(videos: list[VideoAnnotation], out_dir: Path) -> Path:
    name = videos[0].dataset
    md = out_dir / f"{name}.md"    # "ci-set1/macro_phase_annotations" nests a folder
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(conventions_report(videos))
    transition_matrix_png(videos, out_dir / f"{name}_transitions.png")
    return md
