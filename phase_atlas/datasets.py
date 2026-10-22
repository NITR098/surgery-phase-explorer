"""Dataset registry: datasets.json maps a name -> {kind, root[, annotations]}.

`kind` picks the loader (cholec80 / cataract1k / ci-inhouse); `root` is the
dataset folder — either one path or a list of candidate paths (e.g. the macOS
and Windows locations), where the first existing one wins. Relative roots are
resolved against the repo folder, so the shipped config works no matter where
the scripts are launched from.

For `ci-inhouse` the root is the video folder, and every annotation folder of
it becomes a dataset of its own, named "<name>/<folder>" (e.g.
ci-set1/macro_phase_annotations). By default these are all subfolders of the
root that hold ci-annotator CSVs, so a label set added later appears without a
config change; `annotations` (a glob or a list of globs, relative to the root
or absolute) picks folders instead, including ones stored elsewhere.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

from .loaders import cataract1k, cholec80, ci_inhouse
from .schema import VideoAnnotation

REPO_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_DIR / "datasets.json"

LOADERS = {
    "cholec80": cholec80.load,      # also fits m2cai16-workflow (same format)
    "cataract1k": cataract1k.load,
    "ci-inhouse": ci_inhouse.load,
}


def config() -> dict[str, dict]:
    with CONFIG_PATH.open() as fh:
        return json.load(fh)


def _as_list(value) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _roots(entry: dict) -> list[Path]:
    paths = [Path(c).expanduser() for c in _as_list(entry["root"])]
    return [p if p.is_absolute() else REPO_DIR / p for p in paths]


@lru_cache(maxsize=None)
def _datasets() -> dict[str, tuple[str, Path | None]]:
    """Every loadable dataset name -> (its datasets.json entry name, annotation folder)."""
    out: dict[str, tuple[str, Path | None]] = {}
    for name, entry in config().items():
        root = None
        if entry.get("kind", name) == "ci-inhouse":
            root = next((r for r in _roots(entry) if r.exists()), None)
        if root is None:
            out[name] = (name, None)
            continue
        patterns = _as_list(entry["annotations"]) if "annotations" in entry else None
        dirs = ci_inhouse.annotation_dirs(root, patterns)
        if not dirs:
            out[name] = (name, None)    # loading reports that nothing was found
        for d in dirs:
            view = name if d == root else f"{name}/{d.name}"
            if view in out:
                print(f"[datasets] {name}: {d} skipped, {view} is already "
                      f"{out[view][1]}", file=sys.stderr)
                continue
            out[view] = (name, d)
    return out


def dataset_names() -> list[str]:
    return list(_datasets())


def load_dataset(name: str) -> list[VideoAnnotation]:
    datasets = _datasets()
    if name not in datasets:
        raise SystemExit(f"unknown dataset {name!r} — configured: {', '.join(datasets)} "
                         f"(edit {CONFIG_PATH.name} to add one)")
    entry_name, ann_dir = datasets[name]
    entry = config()[entry_name]
    kind = entry.get("kind", entry_name)
    if kind not in LOADERS:
        raise SystemExit(f"dataset {name!r} has unknown kind {kind!r} "
                         f"— available: {', '.join(LOADERS)}")
    roots = _roots(entry)
    root = next((r for r in roots if r.exists()), None)
    if root is None:
        raise SystemExit(f"dataset {name!r}: no root exists among "
                         f"{', '.join(map(str, roots))} (edit {CONFIG_PATH.name})")
    if kind == "ci-inhouse":
        if ann_dir is None:
            wanted = (f" matching {entry['annotations']!r}" if "annotations" in entry
                      else " (subfolders with ci-annotator CSVs)")
            raise SystemExit(f"dataset {name!r}: no annotation folder{wanted} "
                             f"under {root} (edit {CONFIG_PATH.name})")
        videos = ci_inhouse.load(root, ann_dir)
    else:
        videos = LOADERS[kind](root)
    for v in videos:
        v.dataset = name
    return videos


def get_video(name: str, video_id: str) -> VideoAnnotation:
    videos = load_dataset(name)
    for v in videos:
        if v.video_id == video_id:
            return v
    ids = ", ".join(v.video_id for v in videos[:12])
    raise SystemExit(f"video {video_id!r} not in {name} — e.g.: {ids} ...")
