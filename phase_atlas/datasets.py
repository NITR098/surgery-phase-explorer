"""Dataset registry: datasets.json maps a name -> {kind, root}.

`kind` picks the loader (cholec80 / cataract1k / ci-inhouse); `root` is the
dataset folder. Relative roots are resolved against the repo folder, so the
shipped config works no matter where the scripts are launched from.
"""
from __future__ import annotations

import json
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


def dataset_names() -> list[str]:
    return list(config())


def load_dataset(name: str) -> list[VideoAnnotation]:
    cfg = config()
    if name not in cfg:
        raise SystemExit(f"unknown dataset {name!r} — configured: {', '.join(cfg)} "
                         f"(edit {CONFIG_PATH.name} to add one)")
    entry = cfg[name]
    kind = entry.get("kind", name)
    if kind not in LOADERS:
        raise SystemExit(f"dataset {name!r} has unknown kind {kind!r} "
                         f"— available: {', '.join(LOADERS)}")
    root = Path(entry["root"])
    if not root.is_absolute():
        root = REPO_DIR / root
    if not root.exists():
        raise SystemExit(f"dataset {name!r}: root {root} does not exist "
                         f"(edit {CONFIG_PATH.name})")
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
