"""Validate June's AI-assisted facial atlas and render a 2.5D viseme proof."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


ATLAS_CONTRACT_VERSION = 1
REQUIRED_VISEMES = tuple("ABCDEFGHX")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_viseme_atlas_contract(path: str | Path) -> tuple[dict[str, Any], Path]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != ATLAS_CONTRACT_VERSION:
        raise ValueError(f"atlas contract_version must be {ATLAS_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("viseme atlas must explicitly target June Oxley")
    if contract.get("neutral_viseme") != "X":
        raise ValueError("viseme atlas neutral_viseme must be X")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0:
        raise ValueError("viseme atlas must preserve the zero-cash production contract")
    grid = contract.get("grid") or {}
    order = tuple(grid.get("order") or [])
    if order != REQUIRED_VISEMES:
        raise ValueError("viseme atlas grid must contain A-H and X in canonical order")
    columns = int(grid.get("columns", 0))
    rows = int(grid.get("rows", 0))
    cell_width = int(grid.get("cell_width", 0))
    cell_height = int(grid.get("cell_height", 0))
    if (columns, rows) != (3, 3) or cell_width <= 0 or cell_height <= 0:
        raise ValueError("viseme atlas must use a positive 3x3 cell grid")
    image_spec = contract.get("image") or {}
    repo_root = contract_path.parents[2]
    image_path = repo_root / str(image_spec.get("path", ""))
    if not image_path.is_file():
        raise ValueError(f"viseme atlas image is missing: {image_path}")
    if _sha256(image_path) != image_spec.get("sha256"):
        raise ValueError("viseme atlas image hash does not match")
    with Image.open(image_path) as atlas:
        expected = (columns * cell_width, rows * cell_height)
        if atlas.size != expected or atlas.size != (int(image_spec.get("width", 0)), int(image_spec.get("height", 0))):
            raise ValueError("viseme atlas image dimensions do not match the grid contract")
        if atlas.mode != image_spec.get("mode"):
            raise ValueError("viseme atlas image mode does not match the contract")
    identity_spec = contract.get("canonical_identity_reference") or {}
    identity_path = repo_root / str(identity_spec.get("path", ""))
    if not identity_path.is_file():
        raise ValueError(f"canonical identity reference is missing: {identity_path}")
    if _sha256(identity_path) != identity_spec.get("sha256"):
        raise ValueError("canonical identity reference hash does not match")
    box = tuple(int(value) for value in (contract.get("mouth_patch_box") or []))
    if len(box) != 4 or not (0 <= box[0] < box[2] <= cell_width and 0 <= box[1] < box[3] <= cell_height):
        raise ValueError("mouth_patch_box must stay inside one atlas cell")
    feather = int(contract.get("patch_feather_px", 0))
    if not 2 <= feather <= 32:
        raise ValueError("patch_feather_px must be between two and thirty-two")
    return contract, image_path


def atlas_cells(atlas: Image.Image, contract: dict[str, Any]) -> dict[str, Image.Image]:
    grid = contract["grid"]
    width = int(grid["cell_width"])
    height = int(grid["cell_height"])
    cells = {}
    for index, shape in enumerate(grid["order"]):
        column = index % int(grid["columns"])
        row = index // int(grid["columns"])
        cells[shape] = atlas.crop((column * width, row * height, (column + 1) * width, (row + 1) * height)).convert("RGB")
    return cells


def mouth_patch_mask(contract: dict[str, Any]) -> Image.Image:
    left, top, right, bottom = (int(value) for value in contract["mouth_patch_box"])
    width = right - left
    height = bottom - top
    feather = int(contract["patch_feather_px"])
    mask = Image.new("L", (width, height), 0)
    inset = feather + 2
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, width - inset - 1, height - inset - 1),
        radius=max(8, height // 3),
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=feather / 2.0))


def _ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def render_viseme_preview(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    fps: int = 30,
    transition_frames: int = 5,
    hold_frames: int = 10,
    output_scale: int = 2,
) -> dict[str, Any]:
    if fps <= 0 or transition_frames < 2 or hold_frames < 2:
        raise ValueError("preview timing values must be positive production-safe values")
    if not 1 <= output_scale <= 4:
        raise ValueError("output_scale must be between one and four")
    contract, image_path = load_viseme_atlas_contract(contract_path)
    output = Path(output_dir).resolve()
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame_*.png"):
        stale.unlink()
    with Image.open(image_path) as atlas:
        cells = atlas_cells(atlas, contract)
    neutral = str(contract["neutral_viseme"])
    base = cells[neutral].copy()
    box = tuple(int(value) for value in contract["mouth_patch_box"])
    patches = {shape: cell.crop(box) for shape, cell in cells.items()}
    mask = mouth_patch_mask(contract)
    sequence = list(REQUIRED_VISEMES)
    grid = contract["grid"]
    render_size = (
        int(grid["cell_width"]) * output_scale,
        int(grid["cell_height"]) * output_scale,
    )

    def save_frame(frame: Image.Image, number: int) -> None:
        frame.resize(render_size, Image.Resampling.LANCZOS).save(
            frames_dir / f"frame_{number:04d}.png",
            compress_level=1,
        )

    frame_number = 1
    previous = neutral
    for shape in sequence:
        for index in range(transition_frames):
            amount = _ease_in_out_cubic((index + 1) / transition_frames)
            patch = Image.blend(patches[previous], patches[shape], amount)
            frame = base.copy()
            frame.paste(patch, box[:2], mask)
            save_frame(frame, frame_number)
            frame_number += 1
        for _ in range(hold_frames):
            frame = base.copy()
            frame.paste(patches[shape], box[:2], mask)
            save_frame(frame, frame_number)
            frame_number += 1
        previous = shape
    video = output / "june-2p5d-viseme-preview.mp4"
    partial_video = output / "june-2p5d-viseme-preview.partial.mp4"
    partial_video.unlink(missing_ok=True)
    executable = str(Path(ffmpeg)) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")
    subprocess.run(
        [
            executable, "-y", "-v", "error", "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%04d.png"), "-c:v", "libx264",
            "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(partial_video),
        ],
        check=True,
    )
    if not partial_video.is_file() or partial_video.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable viseme preview")
    partial_video.replace(video)
    frame_count = frame_number - 1
    first_frame = frames_dir / "frame_0001.png"
    last_frame = frames_dir / f"frame_{frame_count:04d}.png"
    report = {
        "contract_version": ATLAS_CONTRACT_VERSION,
        "atlas_id": contract["atlas_id"],
        "atlas_version": contract["atlas_version"],
        "atlas_sha256": contract["image"]["sha256"],
        "sequence": sequence,
        "neutral_base": neutral,
        "fps": fps,
        "transition_frames": transition_frames,
        "hold_frames": hold_frames,
        "frame_count": frame_count,
        "duration_seconds": frame_count / fps,
        "width": render_size[0],
        "height": render_size[1],
        "first_frame_sha256": _sha256(first_frame),
        "last_frame_sha256": _sha256(last_frame),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    (output / "june-2p5d-viseme-preview-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and preview June's 2.5D viseme atlas")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", default="build/june-2p5d-viseme-preview")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--scale", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(
        render_viseme_preview(
            args.contract,
            args.output_dir,
            ffmpeg=args.ffmpeg,
            output_scale=args.scale,
        ),
        indent=2,
    ))


if __name__ == "__main__":
    main()
