"""Render June's Phase 29 GS030 deformable-performance adapter.

This adapter keeps the accepted GS030 production drawings as corrective
sources. Between those drawings it performs a local premultiplied-RGBA
inverse warp driven by a shared anatomical landmark interface. There is no
whole-frame cross-dissolve or optical flow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from pipeline.cartoon_pose_layers import (
    compose_pose_frame,
    load_pose_layer_contract,
    registered_pose_layer,
)
from pipeline.cartoon_shot_sequence import encoded_quality_metrics


CONTRACT_VERSION = 1
EXPECTED_SEMANTIC_CHANNELS = {
    "body_pose",
    "root_contact",
    "hand_contact",
    "prop_pose",
    "camera",
    "atmosphere",
}
REQUIRED_TOPOLOGY_LAYERS = {
    "receiving_shadow",
    "left_upper_leg",
    "left_lower_leg",
    "left_boot",
    "right_upper_leg",
    "right_lower_leg",
    "right_boot",
    "pelvis",
    "torso",
    "costume_hip_overlap_corrective",
    "left_upper_arm",
    "left_lower_arm",
    "left_hand",
    "chair_grasp_corrective",
    "right_upper_arm",
    "right_lower_arm",
    "right_hand",
    "mug",
    "mug_grasp_corrective",
    "neck",
    "head",
    "costume_shoulder_overlap_corrective",
    "light_wrap",
}
REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_asset(specification: dict[str, Any], label: str) -> Path:
    value = str(specification.get("path", ""))
    path = (REPO_ROOT / value).resolve()
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    expected = str(specification.get("sha256", ""))
    actual = _sha256(path)
    if len(expected) != 64 or actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _validate_point(value: Any, label: str, width: int, height: int) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-value point")
    x, y = float(value[0]), float(value[1])
    if not 0.0 <= x < width or not 0.0 <= y < height:
        raise ValueError(f"{label} must stay inside the source canvas")


def load_deformable_performance_contract(
    path: str | Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if int(contract.get("contract_version", 0)) != CONTRACT_VERSION:
        raise ValueError("unsupported deformable-performance contract version")
    if (
        contract.get("adapter_id") != "deformable_performance_3q"
        or contract.get("character_id") != "june_oxley"
        or contract.get("view_id") != "WIDE_BODY_3Q"
        or contract.get("action_id") != "STAND_UP"
    ):
        raise ValueError("deformable-performance identity and action boundary is invalid")
    if contract.get("cash_cost") != 0 or contract.get("paid_runtime_dependency") is not False:
        raise ValueError("deformable-performance runtime must remain zero cash")
    if contract.get("promotion_state") != "gate_a_private_adapter_fixture":
        raise ValueError("deformable-performance contract must remain a Gate A fixture")

    output = contract.get("output") or {}
    delivery = (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
        float(output.get("duration_seconds", 0.0)),
    )
    if delivery != (1920, 1080, 30, 171, 5.7):
        raise ValueError("deformable-performance output must retain the exact 171-frame Phase 27 clock")

    accepted = contract.get("accepted_sources") or {}
    assets = {
        identifier: _pinned_asset(specification, f"accepted source {identifier}")
        for identifier, specification in accepted.items()
    }
    required_assets = {
        "canonical_identity",
        "phase27_interface",
        "phase28_deformation_reference",
        "gs030_control",
        "background",
        "neutral_3q_reference",
        "seated_endpoint",
        "leverage_corrective",
        "weight_transfer_corrective",
        "release_corrective",
        "standing_endpoint",
    }
    if set(assets) != required_assets:
        raise ValueError("deformable-performance accepted source pack is incomplete")

    channels = contract.get("semantic_interface", {}).get("input_channels") or []
    channel_ids = {str(channel.get("id")) for channel in channels}
    if channel_ids != EXPECTED_SEMANTIC_CHANNELS or not all(channel.get("required") is True for channel in channels):
        raise ValueError("deformable-performance semantic channel boundary is invalid")

    layers = contract.get("topology", {}).get("layers") or []
    layer_ids = {str(layer.get("id")) for layer in layers}
    if layer_ids != REQUIRED_TOPOLOGY_LAYERS or len({layer.get("depth") for layer in layers}) != len(layers):
        raise ValueError("deformable-performance topology declaration is incomplete")
    topology = contract["topology"]
    if topology.get("runtime_cross_dissolve_allowed") is not False or topology.get("full_frame_optical_flow_allowed") is not False:
        raise ValueError("deformable-performance cannot enable whole-frame interpolation shortcuts")

    segments = contract.get("action", {}).get("segments") or []
    expected_start = 1
    for segment in segments:
        start = int(segment.get("start_frame", 0))
        end = int(segment.get("end_frame", 0))
        if start != expected_start or end < start:
            raise ValueError("deformable-performance segments must cover the 171-frame clock exactly")
        expected_start = end + 1
    if expected_start != 172:
        raise ValueError("deformable-performance segments must cover the 171-frame clock exactly")

    pack = contract.get("runtime_asset_pack") or {}
    if int(pack.get("version", 0)) != 1 or pack.get("runtime_cross_dissolve") is not False:
        raise ValueError("deformable-performance runtime asset pack is invalid")
    landmark_order = [str(value) for value in pack.get("landmark_order") or []]
    if len(landmark_order) < 12 or len(set(landmark_order)) != len(landmark_order):
        raise ValueError("deformable-performance landmark interface is incomplete")
    radii = pack.get("influence_radius_pixels") or {}
    if set(radii) != set(landmark_order) or not all(32.0 <= float(value) <= 256.0 for value in radii.values()):
        raise ValueError("deformable-performance landmark influence radii are invalid")
    anchors = pack.get("corrective_sources") or []
    if [float(anchor.get("progress", -1.0)) for anchor in anchors] != [0.0, 0.25, 0.5, 0.75, 1.0]:
        raise ValueError("deformable-performance requires five ordered corrective sources")
    source_roles = {str(anchor.get("source_role")) for anchor in anchors}
    if not source_roles.issubset(assets):
        raise ValueError("deformable-performance corrective source role is unknown")
    canvas = contract.get("source_canvas") or {}
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    if (width, height) != (1672, 941):
        raise ValueError("deformable-performance source canvas must remain 1672x941")
    for anchor in anchors:
        landmarks = anchor.get("landmarks") or {}
        if set(landmarks) != set(landmark_order):
            raise ValueError("deformable-performance corrective landmarks are incomplete")
        for identifier, point in landmarks.items():
            _validate_point(point, f"{anchor['pose_id']} {identifier}", width, height)
    if [int(value) for value in pack.get("source_switch_frames") or []] != [75, 83, 91, 95]:
        raise ValueError("deformable-performance corrective switches must match authored pose boundaries")
    smear_frames = [int(value) for value in contract["action"].get("declared_local_smear_frames") or []]
    smear_travel = int(pack.get("local_smear_travel_pixels", 0))
    if len(smear_frames) > 1 or not 1 <= smear_travel <= 4:
        raise ValueError("deformable-performance allows at most one restrained local smear")

    declarations = contract.get("gate_declarations") or {}
    if set(declarations) != {"delivery_integrity", "mechanical_integrity", "audience_quality"}:
        raise ValueError("deformable-performance gate declarations cannot be collapsed")
    audience = declarations["audience_quality"]
    if "passed" in audience or audience.get("status_before_gate_b") != "unevaluated":
        raise ValueError("audience quality cannot be claimed before the blinded Gate B comparison")
    return contract, assets


def _ease_in_out_cubic(value: float) -> float:
    value = min(1.0, max(0.0, value))
    # Cubic smoothstep keeps the midpoint velocity at 1.5x average.  The
    # steeper piecewise cubic (3x) made this short, physical rise snap.
    return value * value * (3.0 - 2.0 * value)


def _ease_out_cubic(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return 1.0 - (1.0 - value) ** 3


def _interpolate_value(left: Any, right: Any, amount: float) -> Any:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) + (float(right) - float(left)) * amount
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [_interpolate_value(a, b, amount) for a, b in zip(left, right)]
    return left if amount < 1.0 else right


def _compile_keyframes(
    keyframes: list[dict[str, Any]],
    frame: int,
    *,
    default_easing: str = "ease_in_out_cubic",
) -> dict[str, Any]:
    if frame <= int(keyframes[0]["frame"]):
        return dict(keyframes[0])
    if frame >= int(keyframes[-1]["frame"]):
        return dict(keyframes[-1])
    left = keyframes[0]
    right = keyframes[-1]
    for candidate_left, candidate_right in zip(keyframes, keyframes[1:]):
        if int(candidate_left["frame"]) <= frame <= int(candidate_right["frame"]):
            left, right = candidate_left, candidate_right
            break
    span = int(right["frame"]) - int(left["frame"])
    raw = (frame - int(left["frame"])) / max(1, span)
    easing = str(right.get("easing", default_easing))
    amount = _ease_out_cubic(raw) if easing == "ease_out_cubic" else _ease_in_out_cubic(raw)
    result: dict[str, Any] = {"frame": frame}
    for key in set(left) | set(right):
        if key in {"frame", "easing", "support_phase"}:
            continue
        if key in left and key in right:
            result[key] = _interpolate_value(left[key], right[key], amount)
        elif key in left:
            result[key] = left[key]
        else:
            result[key] = right[key]
    return result


def _active(frame: int, ranges: list[list[int]]) -> bool:
    return any(int(start) <= frame <= int(end) for start, end in ranges)


def _contact_mode(specification: dict[str, Any], frame: int) -> tuple[str, float]:
    for phase in specification.get("phases") or []:
        if int(phase["start_frame"]) <= frame <= int(phase["end_frame"]):
            return str(phase["mode"]), float(phase.get("maximum_heel_travel_px", 0.0))
    raise ValueError(f"contact phase does not cover frame {frame}")


def _segment_for_frame(contract: dict[str, Any], frame: int) -> dict[str, Any]:
    for segment in contract["action"]["segments"]:
        if int(segment["start_frame"]) <= frame <= int(segment["end_frame"]):
            return segment
    raise ValueError(f"frame {frame} is not covered by the action segments")


def compile_performance_frame(contract: dict[str, Any], frame: int) -> dict[str, Any]:
    if frame < 1 or frame > 171:
        raise ValueError("deformable-performance frame must be 1 through 171")
    tracks = contract["performance_tracks"]
    body_pose = _compile_keyframes(tracks["body_pose"]["keyframes"], frame)
    body_pose["interpolation"] = tracks["body_pose"]["interpolation"]

    root_contact = _compile_keyframes(tracks["root_contact"]["keyframes"], frame)
    for phase in tracks["root_contact"]["phase_ranges"]:
        if int(phase["start_frame"]) <= frame <= int(phase["end_frame"]):
            root_contact["support_phase"] = phase["support_phase"]
            break
    root_contact["interpolation"] = tracks["root_contact"]["interpolation"]

    compiled_hands: dict[str, Any] = {}
    contacts: dict[str, Any] = {}
    for specification in tracks["hand_contact"]["contacts"]:
        point = _compile_keyframes(specification["target_keyframes"], frame).get("point")
        active = _active(frame, specification["active_frame_ranges"])
        compiled = {
            "active": active,
            "point": point,
            "maximum_error_px": float(specification["maximum_error_px"]),
            "target_kind": specification["target_kind"],
        }
        compiled_hands[specification["id"]] = compiled
        contacts[specification["id"]] = dict(compiled)

    prop_pose = _compile_keyframes(tracks["prop_pose"]["keyframes"], frame)
    prop_pose["prop_id"] = tracks["prop_pose"]["prop_id"]
    prop_pose["interpolation"] = tracks["prop_pose"]["interpolation"]
    camera = _compile_keyframes(tracks["camera"]["keyframes"], frame)
    camera["interpolation"] = tracks["camera"]["interpolation"]

    chair_seat = contract["contact_constraints"]["chair_seat"]
    contacts["chair_seat"] = {
        "active": _active(frame, chair_seat["active_frame_ranges"]),
        "maximum_error_px": float(chair_seat["maximum_error_px"]),
    }
    for identifier in ("left_boot", "right_boot"):
        specification = contract["contact_constraints"][identifier]
        mode, maximum_heel = _contact_mode(specification, frame)
        contacts[identifier] = {
            "active": _active(frame, specification["active_frame_ranges"]),
            "point": [float(value) for value in specification["target_point"]],
            "mode": mode,
            "maximum_heel_travel_px": maximum_heel,
            "maximum_error_px": float(specification["maximum_error_px"]),
        }

    segment = _segment_for_frame(contract, frame)
    return {
        "frame": frame,
        "segment_id": segment["id"],
        "smear_allowed": frame in set(int(value) for value in contract["action"]["declared_local_smear_frames"]),
        "channels": {
            "body_pose": body_pose,
            "root_contact": root_contact,
            "hand_contact": compiled_hands,
            "prop_pose": prop_pose,
            "camera": camera,
            "atmosphere": dict(tracks["atmosphere"]),
        },
        "contacts": contacts,
    }


def _resolve_executable(value: str | Path) -> str:
    candidate = Path(value)
    resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(str(value))
    if not resolved:
        raise FileNotFoundError(f"executable not found: {value}")
    return resolved


def _decoded_frame_count(path: Path) -> int:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode rendered video: {path}")
    count = 0
    try:
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            count += 1
    finally:
        capture.release()
    return count


def _premultiplied_rgba(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    rgba[:, :, :3] *= rgba[:, :, 3:4] / 255.0
    return rgba


def _registered_point(
    point: list[float],
    pose: dict[str, Any],
    registration: dict[str, Any],
) -> np.ndarray:
    source_left = np.asarray(pose["source_contacts"]["left_support_boot"], dtype=np.float32)
    target_left = np.asarray(registration["target_left_support_boot"], dtype=np.float32)
    translation = target_left - source_left
    source_right = np.asarray(pose["source_contacts"]["right_boot"], dtype=np.float32) + translation
    target_right = np.asarray(registration["target_right_boot"], dtype=np.float32)
    correction = target_right - source_right
    transformed = np.asarray(point, dtype=np.float32) + translation
    warp = registration["right_leg_warp"]
    x_amount = (transformed[0] - float(warp["x_falloff_start"])) / (
        float(warp["x_falloff_end"]) - float(warp["x_falloff_start"])
    )
    y_amount = (transformed[1] - float(warp["y_falloff_start"])) / (
        float(warp["y_falloff_end"]) - float(warp["y_falloff_start"])
    )
    x_amount = min(1.0, max(0.0, float(x_amount)))
    y_amount = min(1.0, max(0.0, float(y_amount)))
    x_amount = x_amount * x_amount * (3.0 - 2.0 * x_amount)
    y_amount = y_amount * y_amount * (3.0 - 2.0 * y_amount)
    return transformed + correction * (x_amount * y_amount)


class DeformablePerformanceRenderer:
    def __init__(self, contract: dict[str, Any], assets: dict[str, Path]):
        self.contract = contract
        self.assets = assets
        control, background_path, pose_paths = load_pose_layer_contract(assets["gs030_control"])
        self.control = control
        self.background = Image.open(background_path).convert("RGB")
        self.pose_by_id = {str(pose["id"]): pose for pose in control["poses"]}
        self.pack = contract["runtime_asset_pack"]
        self.landmark_order = [str(value) for value in self.pack["landmark_order"]]
        self.anchors = self.pack["corrective_sources"]
        self.registered_images: list[Image.Image] = []
        self.registered_landmarks: list[np.ndarray] = []
        self.source_roles: list[str] = []
        for anchor in self.anchors:
            pose_id = str(anchor["pose_id"])
            pose = self.pose_by_id[pose_id]
            role = str(anchor["source_role"])
            source = Image.open(assets[role]).convert("RGBA")
            registered, _ = registered_pose_layer(source, pose, control["contact_registration"])
            source.close()
            self.registered_images.append(registered)
            self.registered_landmarks.append(
                np.asarray(
                    [
                        _registered_point(anchor["landmarks"][identifier], pose, control["contact_registration"])
                        for identifier in self.landmark_order
                    ],
                    dtype=np.float32,
                )
            )
            self.source_roles.append(role)

        alpha_union = np.zeros((941, 1672), dtype=np.uint8)
        for image in self.registered_images:
            alpha_union = np.maximum(alpha_union, np.asarray(image, dtype=np.uint8)[:, :, 3])
        ys, xs = np.where(alpha_union > 8)
        padding = int(self.pack["crop_padding_pixels"])
        self.crop = (
            max(0, int(xs.min()) - padding),
            max(0, int(ys.min()) - padding),
            min(1672, int(xs.max()) + padding + 1),
            min(941, int(ys.max()) + padding + 1),
        )
        x0, y0, x1, y1 = self.crop
        self.sources = [_premultiplied_rgba(image.crop(self.crop)) for image in self.registered_images]
        self.source_alpha_areas = [int(np.count_nonzero(source[:, :, 3] > 32)) for source in self.sources]
        self.crop_grid_y, self.crop_grid_x = np.indices((y1 - y0, x1 - x0), dtype=np.float32)
        self._basis_cache: dict[int, np.ndarray] = {}
        self._layer_cache_key: tuple[tuple[tuple[int, float], ...], bool, bytes] | None = None
        self._layer_cache_image: Image.Image | None = None
        self._layer_cache_metrics: dict[str, Any] | None = None

    def close(self) -> None:
        self.background.close()
        for image in self.registered_images:
            image.close()
        if self._layer_cache_image is not None:
            self._layer_cache_image.close()

    def _source_mix(self, state: dict[str, Any]) -> list[tuple[int, float]]:
        progress = float(state["channels"]["body_pose"]["stand_progress"])
        anchor_progress = [float(anchor["progress"]) for anchor in self.pack["corrective_sources"]]
        source_index = min(range(len(anchor_progress)), key=lambda index: abs(anchor_progress[index] - progress))
        return [(source_index, 1.0)]

    def _target_landmarks(self, state: dict[str, Any]) -> np.ndarray:
        body = state["channels"]["body_pose"]
        progress = float(body["stand_progress"])
        lower_progress = min(1.0, max(0.0, float(body.get("pelvis_progress", progress))))
        upper_progress = min(1.0, max(0.0, float(body.get("torso_progress", progress))))

        def interpolate_landmarks(authored_progress: float) -> np.ndarray:
            if authored_progress >= 1.0:
                return self.registered_landmarks[-1].copy()
            left_index = min(3, int(math.floor(authored_progress * 4.0)))
            right_index = left_index + 1
            local = (authored_progress - left_index * 0.25) / 0.25
            # stand_progress is already eased by the authored performance
            # track.  Applying another curve here concentrates travel into
            # one or two frames and creates a rubber snap.
            return self.registered_landmarks[left_index] * (1.0 - local) + self.registered_landmarks[right_index] * local

        index = {identifier: offset for offset, identifier in enumerate(self.landmark_order)}
        target = interpolate_landmarks(progress)
        lower_target = interpolate_landmarks(lower_progress)
        upper_target = interpolate_landmarks(upper_progress)
        for identifier in ("pelvis", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"):
            target[index[identifier]] = lower_target[index[identifier]]
        for identifier in ("head", "neck", "chest", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow"):
            target[index[identifier]] = upper_target[index[identifier]]

        anticipation = float(body.get("anticipation", 0.0))
        if anticipation > 0.0:
            # June faces screen-right.  A small right/down load moves his nose
            # and chest over the feet before lift, while hands and boots remain
            # governed by their contact tracks.
            anticipation_offsets = {
                "head": (17.0, 8.0),
                "neck": (14.0, 9.0),
                "chest": (11.0, 10.0),
                "pelvis": (5.0, 10.0),
                "left_shoulder": (11.0, 10.0),
                "right_shoulder": (11.0, 10.0),
                "left_elbow": (8.0, 7.0),
                "right_elbow": (9.0, 7.0),
                "left_hip": (5.0, 10.0),
                "right_hip": (5.0, 10.0),
                "left_knee": (3.0, 4.0),
                "right_knee": (3.0, 4.0),
            }
            for identifier, offset in anticipation_offsets.items():
                target[index[identifier]] += np.asarray(offset, dtype=np.float32) * anticipation

        hands = state["channels"]["hand_contact"]
        if hands["chair_hand"]["active"] and hands["chair_hand"]["point"] is not None:
            target[index["left_hand"]] = np.asarray(hands["chair_hand"]["point"], dtype=np.float32)
        if hands["mug_hand"]["point"] is not None:
            target[index["right_hand"]] = np.asarray(hands["mug_hand"]["point"], dtype=np.float32)
        target[index["mug_center"]] = np.asarray(state["channels"]["prop_pose"]["origin"], dtype=np.float32)
        target[index["left_foot"]] = np.asarray(state["contacts"]["left_boot"]["point"], dtype=np.float32)
        target[index["right_foot"]] = np.asarray(state["contacts"]["right_boot"]["point"], dtype=np.float32)

        if progress >= 1.0:
            pelvis = target[index["pelvis"]].copy()
            angle = math.radians(float(body.get("torso_pitch_degrees", 0.0)))
            breath = math.sin((state["frame"] - 96) / 30.0 * math.tau / 4.2)
            settle_y = float(body.get("settle_y_px", 0.0))
            for identifier, strength in (
                ("head", 1.0),
                ("neck", 0.78),
                ("chest", 0.46),
                ("left_shoulder", 0.38),
                ("right_shoulder", 0.38),
            ):
                point_index = index[identifier]
                vector = target[point_index] - pelvis
                rotated_x = math.cos(angle) * vector[0] - math.sin(angle) * vector[1]
                rotated_y = math.sin(angle) * vector[0] + math.cos(angle) * vector[1]
                target[point_index] = pelvis + np.asarray([rotated_x, rotated_y], dtype=np.float32)
                target[point_index, 1] += breath * 1.25 * strength
                target[point_index, 1] += settle_y * strength
            for identifier, strength in (
                ("pelvis", 1.0),
                ("left_hip", 0.85),
                ("right_hip", 0.85),
                ("left_knee", 0.5),
                ("right_knee", 0.5),
            ):
                target[index[identifier], 1] += settle_y * strength
        return target

    def _normalized_basis(self, source_index: int) -> np.ndarray:
        if source_index in self._basis_cache:
            return self._basis_cache[source_index]
        x0, y0, _, _ = self.crop
        nodes = self.registered_landmarks[source_index]
        weights: list[np.ndarray] = []
        denominator = np.full_like(self.crop_grid_x, float(self.pack["normalization_floor"]), dtype=np.float32)
        radii = self.pack["influence_radius_pixels"]
        for identifier, point in zip(self.landmark_order, nodes):
            cx = float(point[0]) - x0
            cy = float(point[1]) - y0
            radius = float(radii[identifier])
            weight = np.exp(
                -((self.crop_grid_x - cx) ** 2 + (self.crop_grid_y - cy) ** 2) / (2.0 * radius * radius)
            ).astype(np.float32)
            weights.append(weight)
            denominator += weight
        basis = np.stack([weight / denominator for weight in weights], axis=0)
        self._basis_cache[source_index] = basis
        return basis

    @staticmethod
    def _local_smear(source: np.ndarray, travel_y: int = 3) -> np.ndarray:
        height, width = source.shape[:2]
        result = np.zeros_like(source)
        offsets = np.linspace(float(travel_y), 0.0, 3)
        weights = (0.15, 0.30, 0.55)
        for offset, weight in zip(offsets, weights):
            shifted = cv2.warpAffine(
                source,
                np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, offset]], dtype=np.float32),
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0.0, 0.0, 0.0, 0.0),
            )
            result += shifted * float(weight)
        return result

    def _warp_source(self, source_index: int, target_nodes: np.ndarray) -> tuple[np.ndarray, float]:
        source_nodes = self.registered_landmarks[source_index]
        deltas = target_nodes - source_nodes
        basis = self._normalized_basis(source_index)
        flow_x = np.tensordot(deltas[:, 0], basis, axes=(0, 0)).astype(np.float32)
        flow_y = np.tensordot(deltas[:, 1], basis, axes=(0, 0)).astype(np.float32)

        index = {identifier: offset for offset, identifier in enumerate(self.landmark_order)}
        for identifier in ("left_foot", "right_foot"):
            point = source_nodes[index[identifier]]
            x0, y0, _, _ = self.crop
            cx, cy = float(point[0]) - x0, float(point[1]) - y0
            radius = 62.0
            attenuation = 1.0 - np.exp(
                -((self.crop_grid_x - cx) ** 2 + (self.crop_grid_y - cy) ** 2) / (2.0 * radius * radius)
            )
            flow_x *= attenuation.astype(np.float32)
            flow_y *= attenuation.astype(np.float32)

        map_x = self.crop_grid_x - flow_x
        map_y = self.crop_grid_y - flow_y
        warped = cv2.remap(
            self.sources[source_index],
            map_x,
            map_y,
            interpolation=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
        sample = slice(None, None, 8)
        mx = map_x[sample, sample]
        my = map_y[sample, sample]
        dmx_dy, dmx_dx = np.gradient(mx)
        dmy_dy, dmy_dx = np.gradient(my)
        determinant = dmx_dx * dmy_dy - dmx_dy * dmy_dx
        return warped, float(np.min(determinant))

    def render_layer(self, state: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
        source_mix = self._source_mix(state)
        target_nodes = self._target_landmarks(state)
        mix_key = tuple((index, round(weight, 6)) for index, weight in source_mix)
        cache_key = (mix_key, bool(state["smear_allowed"]), np.round(target_nodes, 4).tobytes())
        if (
            cache_key == self._layer_cache_key
            and self._layer_cache_image is not None
            and self._layer_cache_metrics is not None
        ):
            return self._layer_cache_image.copy(), json.loads(json.dumps(self._layer_cache_metrics))
        warped = np.zeros_like(self.sources[0])
        minimum_jacobian = math.inf
        for source_index, weight in source_mix:
            source_warped, source_jacobian = self._warp_source(source_index, target_nodes)
            warped += source_warped * float(weight)
            minimum_jacobian = min(minimum_jacobian, source_jacobian)
        if state["smear_allowed"]:
            warped = self._local_smear(warped, int(self.pack["local_smear_travel_pixels"]))

        alpha = np.clip(warped[:, :, 3:4], 0.0, 255.0)
        rgb = np.zeros_like(warped[:, :, :3])
        np.divide(warped[:, :, :3] * 255.0, np.maximum(alpha, 1e-5), out=rgb, where=alpha > 1e-5)
        rgba = np.concatenate((np.clip(rgb, 0.0, 255.0), alpha), axis=2).astype(np.uint8)
        full = Image.new("RGBA", (1672, 941), (0, 0, 0, 0))
        full.paste(Image.fromarray(rgba, mode="RGBA"), self.crop)

        index = {identifier: offset for offset, identifier in enumerate(self.landmark_order)}
        alpha_plane = rgba[:, :, 3]
        node_presence: dict[str, float] = {}
        crop_x, crop_y, _, _ = self.crop
        for identifier in ("left_hand", "right_hand", "mug_center", "left_foot", "right_foot"):
            point = target_nodes[index[identifier]]
            cx, cy = int(round(point[0] - crop_x)), int(round(point[1] - crop_y))
            radius = 16 if "foot" not in identifier else 22
            region = alpha_plane[max(0, cy - radius):cy + radius + 1, max(0, cx - radius):cx + radius + 1]
            node_presence[identifier] = float(np.mean(region > 24)) if region.size else 0.0
        alpha_area = int(np.count_nonzero(alpha_plane > 32))
        reference_alpha_area = sum(self.source_alpha_areas[source_index] * weight for source_index, weight in source_mix)
        metrics = {
            "source_mix": [
                {"source_index": source_index, "source_role": self.source_roles[source_index], "weight": weight}
                for source_index, weight in source_mix
            ],
            "landmarks": {
                identifier: [round(float(point[0]), 4), round(float(point[1]), 4)]
                for identifier, point in zip(self.landmark_order, target_nodes)
            },
            "alpha_area": alpha_area,
            "alpha_area_ratio_to_source": alpha_area / max(1.0, reference_alpha_area),
            "minimum_inverse_map_jacobian": minimum_jacobian,
            "node_alpha_presence": node_presence,
        }
        if self._layer_cache_image is not None:
            self._layer_cache_image.close()
        self._layer_cache_key = cache_key
        self._layer_cache_image = full.copy()
        self._layer_cache_metrics = json.loads(json.dumps(metrics))
        return full, metrics

    def render_frame(self, frame: int) -> tuple[Image.Image, dict[str, Any]]:
        state = compile_performance_frame(self.contract, frame)
        layer, metrics = self.render_layer(state)
        mug = metrics["landmarks"]["mug_center"]
        steam_origin = (float(mug[0]), float(mug[1]) - 50.0)
        composed = compose_pose_frame(self.background, layer, steam_origin, self.control, frame)
        metrics["state"] = state
        return composed, metrics


def _contact_sheet(frames: dict[int, Path], output: Path) -> None:
    images = [(frame, Image.open(path).convert("RGB")) for frame, path in sorted(frames.items())]
    if not images:
        return
    thumb_width, thumb_height = 480, 270
    columns = 4
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * thumb_height), (18, 16, 14))
    font = ImageFont.load_default(size=18)
    for index, (frame, source) in enumerate(images):
        thumbnail = source.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(thumbnail)
        draw.rounded_rectangle((10, 10, 126, 42), radius=6, fill=(10, 9, 8, 205))
        draw.text((20, 17), f"frame {frame}", fill=(255, 244, 222), font=font)
        sheet.paste(thumbnail, ((index % columns) * thumb_width, (index // columns) * thumb_height))
        source.close()
    sheet.save(output, quality=94)


def render_deformable_performance_3q(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    render_scale: float = 1.0,
) -> dict[str, Any]:
    if not 0.25 <= float(render_scale) <= 1.0:
        raise ValueError("render_scale must stay between 0.25 and 1.0")
    contract, assets = load_deformable_performance_contract(contract_path)
    renderer = DeformablePerformanceRenderer(contract, assets)
    ffmpeg_bin = _resolve_executable(ffmpeg)
    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()

    width = round(int(contract["output"]["width"]) * render_scale)
    height = round(int(contract["output"]["height"]) * render_scale)
    fps = int(contract["output"]["fps"])
    frame_count = int(contract["output"]["frame_count"])
    review_numbers = set(int(value) for value in contract["action"]["review_frames"])
    video = output / "june-gs030-deformable-performance-3q.mp4"
    partial = output / "june-gs030-deformable-performance-3q.partial.mp4"
    partial.unlink(missing_ok=True)
    command = [
        ffmpeg_bin,
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        "-frames:v",
        str(frame_count),
        "-movflags",
        "+faststart",
        str(partial),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        renderer.close()
        raise RuntimeError("unable to open deformable-performance FFmpeg pipe")

    rows: list[dict[str, Any]] = []
    saved: dict[int, Path] = {}
    try:
        for frame_number in range(1, frame_count + 1):
            frame, metrics = renderer.render_frame(frame_number)
            if render_scale != 1.0:
                frame = frame.resize((width, height), Image.Resampling.LANCZOS)
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            rows.append(metrics)
            if frame_number in review_numbers:
                destination = review_dir / f"frame_{frame_number:04d}.png"
                frame.save(destination, compress_level=2)
                saved[frame_number] = destination
        process.stdin.close()
        error_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    finally:
        renderer.close()
    if return_code != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"deformable-performance render failed: {error_output.strip()}")
    partial.replace(video)

    quality = encoded_quality_metrics(video, saved, frame_count)
    landmarks = [row["landmarks"] for row in rows]
    smear_frames = set(int(value) for value in contract["action"]["declared_local_smear_frames"])
    maximum_action_step = 0.0
    maximum_hold_step = 0.0
    for frame_index in range(1, len(landmarks)):
        frame_number = frame_index + 1
        if frame_number in smear_frames:
            continue
        for identifier in renderer.landmark_order:
            before = np.asarray(landmarks[frame_index - 1][identifier], dtype=np.float32)
            after = np.asarray(landmarks[frame_index][identifier], dtype=np.float32)
            step = float(np.linalg.norm(after - before)) * 1920.0 / 1672.0
            segment_id = str(rows[frame_index]["state"]["segment_id"])
            if segment_id in {"ANTICIPATION", "LEVERAGE", "WEIGHT_TRANSFER", "RELEASE", "SETTLE"}:
                maximum_action_step = max(maximum_action_step, step)
            else:
                maximum_hold_step = max(maximum_hold_step, step)

    boot_errors: list[float] = []
    hand_errors: list[float] = []
    minimum_presence = 1.0
    for row in rows:
        state = row["state"]
        points = row["landmarks"]
        for identifier, contact_id in (("left_foot", "left_boot"), ("right_foot", "right_boot")):
            boot_errors.append(
                float(np.linalg.norm(np.asarray(points[identifier]) - np.asarray(state["contacts"][contact_id]["point"])))
            )
        for identifier, contact_id in (("left_hand", "chair_hand"), ("right_hand", "mug_hand")):
            contact = state["contacts"][contact_id]
            if contact["active"] and contact.get("point") is not None:
                hand_errors.append(
                    float(np.linalg.norm(np.asarray(points[identifier]) - np.asarray(contact["point"])))
                )
        minimum_presence = min(minimum_presence, *row["node_alpha_presence"].values())

    all_contact_errors = boot_errors + hand_errors
    contact_p95 = float(np.percentile(all_contact_errors, 95)) if all_contact_errors else 0.0
    minimum_jacobian = min(float(row["minimum_inverse_map_jacobian"]) for row in rows)
    maximum_alpha_ratio = max(float(row["alpha_area_ratio_to_source"]) for row in rows)
    minimum_alpha_ratio = min(float(row["alpha_area_ratio_to_source"]) for row in rows)
    decoded_frame_count = _decoded_frame_count(video)
    mechanical_criteria = contract["gate_declarations"]["mechanical_integrity"]["criteria"]
    machine_passed = (
        contact_p95 <= 3.0
        and maximum_action_step <= float(mechanical_criteria["maximum_action_landmark_step_output_px"])
        and maximum_hold_step <= float(mechanical_criteria["maximum_hold_landmark_step_output_px"])
        and minimum_jacobian > 0.0
        and minimum_presence > 0.015
        and decoded_frame_count == frame_count
    )

    sheet = output / "june-gs030-deformable-performance-3q-contact-sheet.jpg"
    _contact_sheet(saved, sheet)
    quarter_speed = output / "june-gs030-deformable-performance-3q-quarter-speed.mp4"
    result = subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            str(video),
            "-an",
            "-vf",
            "setpts=4.0*PTS",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            str(quarter_speed),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"quarter-speed review render failed: {result.stderr.strip()}")

    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "gate_a_private_deformable_performance_fixture",
        "adapter_id": contract["adapter_id"],
        "classification": contract["classification"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "runtime_representation": contract["runtime_asset_pack"]["honest_representation"],
        "delivery_integrity": {
            "machine_passed": decoded_frame_count == frame_count,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration_seconds": frame_count / fps,
            "decoded_frame_count": decoded_frame_count,
            "full_decode": decoded_frame_count == frame_count,
            "video_sha256": _sha256(video),
            "minimum_encoded_laplacian_variance": quality["minimum_encoded_laplacian_variance"],
            "minimum_psnr_db": quality["minimum_psnr_db"],
        },
        "mechanical_integrity": {
            "machine_passed": machine_passed,
            "visual_review_status": "unevaluated",
            "contact_error_p95_source_px": contact_p95,
            "maximum_action_landmark_step_output_px": maximum_action_step,
            "maximum_hold_landmark_step_output_px": maximum_hold_step,
            "minimum_inverse_map_jacobian": minimum_jacobian,
            "minimum_node_alpha_presence_fraction": minimum_presence,
            "alpha_area_ratio_range": [minimum_alpha_ratio, maximum_alpha_ratio],
            "corrective_source_switch_frames": contract["runtime_asset_pack"]["source_switch_frames"],
            "whole_frame_cross_dissolve_used": False,
            "full_frame_optical_flow_used": False,
        },
        "audience_quality": {
            "status": "unevaluated",
            "may_be_inferred_from_delivery_or_mechanics": False,
            "requires_gate_b_blinded_comparison": True,
        },
        "gate_a_machine_passed": machine_passed,
        "gate_a_promoted": False,
        "render_scale": render_scale,
        "video": video.name,
        "contact_sheet": sheet.name,
        "quarter_speed_review": quarter_speed.name,
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "paid_runtime_dependency": False,
    }
    report_path = output / "june-gs030-deformable-performance-3q-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's Phase 29 deformable GS030 performance adapter")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--render-scale", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_deformable_performance_3q(
        args.contract,
        args.output_dir,
        ffmpeg=args.ffmpeg,
        render_scale=args.render_scale,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
