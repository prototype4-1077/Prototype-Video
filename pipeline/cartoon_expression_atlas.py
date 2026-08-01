"""Validate and schedule June's identity-locked 2.5D expression atlas."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


EXPRESSION_CONTRACT_VERSION = 1
REQUIRED_EXPRESSIONS = (
    "neutral",
    "blink",
    "squint",
    "brow_raise",
    "brow_knit",
    "concern",
    "warm_eyes",
    "gaze_down",
    "compassion",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def load_expression_atlas_contract(path: str | Path) -> tuple[dict[str, Any], Path]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != EXPRESSION_CONTRACT_VERSION:
        raise ValueError(f"expression contract_version must be {EXPRESSION_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("expression atlas must explicitly target June Oxley")
    if contract.get("neutral_expression") != "neutral":
        raise ValueError("expression atlas neutral_expression must be neutral")
    if (contract.get("generation") or {}).get("cash_cost") != 0:
        raise ValueError("expression atlas must preserve the zero-cash production contract")
    grid = contract.get("grid") or {}
    if tuple(grid.get("order") or []) != REQUIRED_EXPRESSIONS:
        raise ValueError("expression atlas grid must contain the canonical nine states in order")
    columns = int(grid.get("columns", 0))
    rows = int(grid.get("rows", 0))
    cell_width = int(grid.get("cell_width", 0))
    cell_height = int(grid.get("cell_height", 0))
    if (columns, rows) != (3, 3) or cell_width <= 0 or cell_height <= 0:
        raise ValueError("expression atlas must use a positive 3x3 cell grid")
    repo_root = contract_path.parents[2]
    image_spec = contract.get("image") or {}
    image_path = repo_root / str(image_spec.get("path", ""))
    if not image_path.is_file() or _sha256(image_path) != image_spec.get("sha256"):
        raise ValueError("expression atlas image is missing or its hash does not match")
    with Image.open(image_path) as atlas:
        expected = (columns * cell_width, rows * cell_height)
        if atlas.size != expected or atlas.size != (
            int(image_spec.get("width", 0)),
            int(image_spec.get("height", 0)),
        ):
            raise ValueError("expression atlas dimensions do not match the grid contract")
        if atlas.mode != image_spec.get("mode"):
            raise ValueError("expression atlas mode does not match the contract")
    identity = contract.get("canonical_identity_reference") or {}
    identity_path = repo_root / str(identity.get("path", ""))
    if not identity_path.is_file() or _sha256(identity_path) != identity.get("sha256"):
        raise ValueError("expression atlas canonical identity hash does not match")
    viseme = contract.get("paired_viseme_atlas") or {}
    viseme_path = repo_root / str(viseme.get("path", ""))
    if not viseme_path.is_file() or _sha256(viseme_path) != viseme.get("sha256"):
        raise ValueError("expression atlas paired viseme hash does not match")
    box = tuple(int(value) for value in (contract.get("expression_patch_box") or []))
    if len(box) != 4 or not (
        0 <= box[0] < box[2] <= cell_width and 0 <= box[1] < box[3] <= cell_height
    ):
        raise ValueError("expression_patch_box must stay inside one atlas cell")
    feather = int(contract.get("patch_feather_px", 0))
    if not 2 <= feather <= 32:
        raise ValueError("expression patch_feather_px must be between two and thirty-two")
    return contract, image_path


def expression_cells(atlas: Image.Image, contract: dict[str, Any]) -> dict[str, Image.Image]:
    grid = contract["grid"]
    width = int(grid["cell_width"])
    height = int(grid["cell_height"])
    cells = {}
    for index, state in enumerate(grid["order"]):
        column = index % int(grid["columns"])
        row = index // int(grid["columns"])
        cells[state] = atlas.crop(
            (column * width, row * height, (column + 1) * width, (row + 1) * height)
        ).convert("RGB")
    return cells


def expression_patch_mask(contract: dict[str, Any]) -> Image.Image:
    left, top, right, bottom = (int(value) for value in contract["expression_patch_box"])
    width = right - left
    height = bottom - top
    feather = int(contract["patch_feather_px"])
    mask = Image.new("L", (width, height), 0)
    inset = feather + 2
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, width - inset - 1, height - inset - 1),
        radius=max(12, height // 3),
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=feather / 2.0))


def expression_performance_plan(
    path: str | Path,
    *,
    expected_atlas_id: str = "june_oxley_canonical_expressions",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cue_path = Path(path).resolve()
    payload = json.loads(cue_path.read_text(encoding="utf-8"))
    if payload.get("contract_version") != 1:
        raise ValueError("expression cue contract_version must be one")
    if payload.get("character_id") != "june_oxley" or payload.get("atlas_id") != expected_atlas_id:
        raise ValueError("expression cues must target June and the selected expression atlas")
    fps = int(payload.get("fps", 0))
    duration = float(payload.get("duration_seconds", 0.0))
    frame_count = int(payload.get("frame_count", 0))
    if fps <= 0 or not math.isfinite(duration) or duration <= 0 or frame_count != round(duration * fps):
        raise ValueError("expression cues must define one exact positive frame clock")
    default_transition = int(payload.get("default_transition_frames", 0))
    if not 1 <= default_transition <= 12:
        raise ValueError("default expression transition must be between one and twelve frames")
    cues = payload.get("cues") or []
    if not cues:
        raise ValueError("expression cues cannot be empty")
    cursor = 0.0
    parsed = []
    for index, cue in enumerate(cues):
        start = float(cue.get("start", -1.0))
        end = float(cue.get("end", -1.0))
        state = str(cue.get("state", ""))
        transition = int(cue.get("transition_frames", default_transition))
        if abs(start - cursor) > 1e-6 or end <= start:
            raise ValueError(f"expression cue {index} must be contiguous and positive")
        if state not in REQUIRED_EXPRESSIONS:
            raise ValueError(f"expression cue {index} has unsupported state {state!r}")
        if not 1 <= transition <= 12:
            raise ValueError(f"expression cue {index} has unsafe transition_frames")
        parsed.append({"start": start, "end": end, "state": state, "transition_frames": transition})
        cursor = end
    if abs(cursor - duration) > 1e-6:
        raise ValueError("expression cues must cover the complete performance duration")

    targets = []
    cue_index = 0
    for frame_index in range(frame_count):
        sample_time = (frame_index + 0.5) / fps
        while cue_index + 1 < len(parsed) and sample_time >= parsed[cue_index]["end"]:
            cue_index += 1
        targets.append(parsed[cue_index])

    plan = []
    active = targets[0]["state"]
    transition_from = active
    transition_start = 0
    transition_length = targets[0]["transition_frames"]
    for frame_index, target in enumerate(targets):
        if target["state"] != active:
            transition_from = active
            active = target["state"]
            transition_start = frame_index
            transition_length = target["transition_frames"]
        offset = frame_index - transition_start
        if transition_from == active or offset >= transition_length:
            amount = 1.0
            transition_from = active
        else:
            amount = _ease_in_out_cubic((offset + 1) / transition_length)
        plan.append({
            "frame": frame_index + 1,
            "from_state": transition_from,
            "to_state": active,
            "blend": amount,
        })
    metadata = {
        "path": cue_path,
        "sha256": _sha256(cue_path),
        "performance_id": payload["performance_id"],
        "fps": fps,
        "duration_seconds": duration,
        "frame_count": frame_count,
        "cue_count": len(parsed),
        "states": sorted({cue["state"] for cue in parsed}),
    }
    return metadata, plan
