from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = REPO_ROOT / "concept/characters/rig_assets/june_oxley_oral_interior_atlas_v2.png"
REPLACEMENT = REPO_ROOT / "concept/characters/rig_assets/june_oxley_oral_G_v1.png"
OUTPUT = REPO_ROOT / "concept/characters/rig_assets/june_oxley_oral_interior_atlas_v3.png"
CELL_SIZE = 418
MINIMUM_CELL_PADDING = 24


class OralAtlasBuildError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _premultiplied_resize(rgba: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    premultiplied = rgba[:, :, :3].astype(np.float32) * alpha[:, :, None]
    resized_alpha = cv2.resize(alpha, size, interpolation=cv2.INTER_LANCZOS4)
    resized_premultiplied = cv2.resize(premultiplied, size, interpolation=cv2.INTER_LANCZOS4)
    resized_alpha = np.clip(resized_alpha, 0.0, 1.0)
    rgb = np.zeros_like(resized_premultiplied)
    valid = resized_alpha > 1e-5
    rgb[valid] = resized_premultiplied[valid] / resized_alpha[valid][:, None]
    return np.dstack((np.clip(rgb, 0, 255).astype(np.uint8), np.clip(resized_alpha * 255.0, 0, 255).astype(np.uint8)))


def build() -> dict[str, str | int]:
    atlas = np.asarray(Image.open(BASE).convert("RGBA"), dtype=np.uint8).copy()
    replacement = np.asarray(Image.open(REPLACEMENT).convert("RGBA"), dtype=np.uint8)
    if atlas.shape != (CELL_SIZE * 3, CELL_SIZE * 3, 4):
        raise OralAtlasBuildError(f"base atlas dimensions changed: {atlas.shape}")
    visible = replacement[:, :, 3] >= 16
    yy, xx = np.where(visible)
    if not yy.size:
        raise OralAtlasBuildError("replacement G sprite is empty")
    crop = replacement[int(yy.min()):int(yy.max()) + 1, int(xx.min()):int(xx.max()) + 1]
    available = CELL_SIZE - 2 * MINIMUM_CELL_PADDING
    scale = min(available / crop.shape[1], available / crop.shape[0])
    target_width = max(1, int(round(crop.shape[1] * scale)))
    target_height = max(1, int(round(crop.shape[0] * scale)))
    resized = _premultiplied_resize(crop, (target_width, target_height))
    cell = np.zeros((CELL_SIZE, CELL_SIZE, 4), dtype=np.uint8)
    x1 = (CELL_SIZE - target_width) // 2
    y1 = (CELL_SIZE - target_height) // 2
    cell[y1:y1 + target_height, x1:x1 + target_width] = resized
    if np.any(cell[0, :, 3] >= 16) or np.any(cell[-1, :, 3] >= 16) or np.any(cell[:, 0, 3] >= 16) or np.any(cell[:, -1, 3] >= 16):
        raise OralAtlasBuildError("repacked G touches its cell boundary")
    atlas[2 * CELL_SIZE:3 * CELL_SIZE, CELL_SIZE:2 * CELL_SIZE] = cell
    Image.fromarray(atlas, "RGBA").save(OUTPUT, format="PNG", optimize=True)
    return {
        "output": str(OUTPUT),
        "sha256": _sha256(OUTPUT),
        "cell_size": CELL_SIZE,
        "G_padding_top": y1,
        "G_padding_bottom": CELL_SIZE - (y1 + target_height),
        "G_padding_left": x1,
        "G_padding_right": CELL_SIZE - (x1 + target_width),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build(), indent=2))
