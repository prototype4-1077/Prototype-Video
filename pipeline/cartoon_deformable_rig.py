from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


CONTRACT_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ACTIONS = {"TURN", "REACH", "HAND_OFF", "SIT_DOWN", "STAND_UP"}
EXPECTED_POSES = {"NEUTRAL", "TURN", "REACH", "HAND_OFF", "SIT"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"deformable rig asset escapes repository: {value}")
    return path


def _pinned_path(spec: dict[str, Any], label: str) -> Path:
    path = _asset_path(str(spec.get("path", "")))
    expected = str(spec.get("sha256", ""))
    if not path.is_file():
        raise FileNotFoundError(f"deformable rig {label} is missing: {path}")
    if len(expected) != 64 or _sha256(path) != expected:
        raise ValueError(f"deformable rig {label} failed its SHA-256 gate: {path}")
    return path


def _image_contract(path: Path, spec: dict[str, Any], label: str) -> None:
    with Image.open(path) as image:
        actual = (image.width, image.height, image.mode)
    expected = (int(spec["width"]), int(spec["height"]), str(spec["mode"]))
    if actual != expected:
        raise ValueError(f"deformable rig {label} image contract mismatch: {actual} != {expected}")


def load_deformable_rig_contract(path: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if int(contract.get("contract_version", 0)) != CONTRACT_VERSION:
        raise ValueError("unsupported deformable rig contract version")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("deformable rig must belong to June Oxley")
    if int(contract.get("cash_cost", -1)) != 0 or contract.get("paid_runtime_dependency") is not False:
        raise ValueError("deformable rig must remain zero cash at runtime")
    identity = contract.get("identity_invariants") or {}
    if (
        identity.get("presentation") != "elderly white rural man"
        or identity.get("sex") != "male"
        or identity.get("build") != "lean_wiry"
        or identity.get("hair") != "short_thinning_white"
        or identity.get("facial_hair") != "trimmed_white_beard_and_mustache"
        or set(identity.get("prohibited_interpretations") or []) != {"female", "wife", "hair_bun", "clean_shaven"}
    ):
        raise ValueError("deformable rig violates June's male identity invariants")

    output = contract.get("output") or {}
    output_clock = (
        int(output.get("width", 0)), int(output.get("height", 0)), int(output.get("fps", 0)),
        int(output.get("frame_count", 0)), float(output.get("duration_seconds", 0.0)),
        output.get("codec"), output.get("pixel_format"),
    )
    if output_clock != (1920, 1080, 30, 360, 12.0, "h264", "yuv420p"):
        raise ValueError("deformable rig must lock the exact 12-second 1080p delivery clock")

    source = contract.get("source_art") or {}
    background = contract.get("background") or {}
    alpha_source = source.get("alpha_derivation") or {}
    assets = {
        "source_art": _pinned_path(source, "source art"),
        "alpha_source": _pinned_path(
            {"path": alpha_source.get("source_path"), "sha256": alpha_source.get("source_sha256")},
            "alpha source",
        ),
        "background": _pinned_path(background, "background"),
    }
    _image_contract(assets["source_art"], source, "source art")
    _image_contract(assets["background"], background, "background")
    with Image.open(assets["source_art"]) as image:
        alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    if int(alpha[0, 0]) != 0 or int(alpha[-1, -1]) != 0 or np.count_nonzero(alpha) < 300_000:
        raise ValueError("deformable rig source art failed its alpha-matte gate")

    nodes = (contract.get("skeleton") or {}).get("nodes") or []
    node_ids = [str(node.get("id")) for node in nodes]
    if len(node_ids) < 20 or len(node_ids) != len(set(node_ids)):
        raise ValueError("deformable rig skeleton node set is incomplete or duplicated")
    pins = set((contract.get("skeleton") or {}).get("stationary_contact_pins") or [])
    if pins != {"screen_left_foot", "screen_right_foot"} or not pins.issubset(node_ids):
        raise ValueError("deformable rig must lock both planted foot contacts")

    poses = contract.get("poses") or {}
    if set(poses) != EXPECTED_POSES:
        raise ValueError("deformable rig pose set is incomplete")
    for pose in poses.values():
        if not set((pose.get("deltas") or {})).issubset(node_ids):
            raise ValueError("deformable rig pose references an unknown skeleton node")
    for pin in pins:
        if any(pin in (pose.get("deltas") or {}) for pose in poses.values()):
            raise ValueError("planted foot pins may not receive authored translation")

    actions = contract.get("actions") or []
    if {str(action.get("id")) for action in actions} != EXPECTED_ACTIONS:
        raise ValueError("deformable rig action coverage is incomplete")
    previous_end = 30
    for action in actions:
        start, end = int(action["start_frame"]), int(action["end_frame"])
        if start != previous_end + 1 or end - start + 1 != 60:
            raise ValueError("deformable rig action windows must be contiguous 60-frame spans")
        previous_end = end
    if previous_end != 330:
        raise ValueError("deformable rig action clock is incomplete")

    timeline = contract.get("timeline") or []
    frames = [int(item.get("frame", 0)) for item in timeline]
    if frames != sorted(set(frames)) or frames[0] != 1 or frames[-1] != 360:
        raise ValueError("deformable rig timeline is invalid")
    if not all(str(item.get("pose")) in EXPECTED_POSES for item in timeline):
        raise ValueError("deformable rig timeline references an unknown pose")
    reviews = [int(value) for value in contract.get("review_frames") or []]
    if not reviews or reviews != sorted(set(reviews)) or min(reviews) < 1 or max(reviews) > 360:
        raise ValueError("deformable rig review frames are invalid")
    layers = contract.get("layers") or []
    if [layer.get("id") for layer in layers] != ["body_base", "right_arm_foreground"]:
        raise ValueError("deformable rig must expose the depth-ordered body and right-arm layers")
    arm_layer = layers[1]
    if int(arm_layer.get("depth", -1)) != 1 or len(arm_layer.get("mask_polygon_source_pixels") or []) < 8:
        raise ValueError("deformable rig right-arm layer mask is incomplete")
    if set(arm_layer.get("bound_nodes") or []) != {
        "screen_right_shoulder", "screen_right_elbow", "screen_right_wrist", "screen_right_hand"
    }:
        raise ValueError("deformable rig right-arm layer binding is incomplete")
    return contract, assets


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def solve_pose_state(contract: dict[str, Any], frame: int) -> dict[str, Any]:
    if frame < 1 or frame > int(contract["output"]["frame_count"]):
        raise ValueError("deformable rig frame is outside the output clock")
    timeline = contract["timeline"]
    left = right = timeline[0]
    for item in timeline:
        if int(item["frame"]) <= frame:
            left = item
        if int(item["frame"]) >= frame:
            right = item
            break
    start, end = int(left["frame"]), int(right["frame"])
    amount = 0.0 if end == start else _smoothstep((frame - start) / (end - start))
    poses = contract["poses"]
    node_ids = [str(node["id"]) for node in contract["skeleton"]["nodes"]]
    deltas: dict[str, tuple[float, float]] = {}
    for node_id in node_ids:
        a = (poses[left["pose"]].get("deltas") or {}).get(node_id, [0.0, 0.0])
        b = (poses[right["pose"]].get("deltas") or {}).get(node_id, [0.0, 0.0])
        deltas[node_id] = (
            float(a[0]) + (float(b[0]) - float(a[0])) * amount,
            float(a[1]) + (float(b[1]) - float(a[1])) * amount,
        )
    period = int(contract["deformation"]["secondary_motion"]["period_frames"])
    breath = math.sin(math.tau * (frame - 1) / period)
    for node_id, amplitude in contract["deformation"]["secondary_motion"]["vertical_source_pixels"].items():
        x, y = deltas[node_id]
        deltas[node_id] = (x, y + float(amplitude) * breath)
    for pin in contract["skeleton"]["stationary_contact_pins"]:
        deltas[pin] = (0.0, 0.0)

    corrective_ids = [str(value["id"]) for value in contract["deformation"]["joint_correctives"]]
    correctives: dict[str, float] = {}
    for identifier in corrective_ids:
        a = float((poses[left["pose"]].get("correctives") or {}).get(identifier, 0.0))
        b = float((poses[right["pose"]].get("correctives") or {}).get(identifier, 0.0))
        correctives[identifier] = a + (b - a) * amount
    return {
        "left_pose": str(left["pose"]), "right_pose": str(right["pose"]), "amount": amount,
        "deltas": deltas, "correctives": correctives, "breath": breath,
    }


class DeformableRigRenderer:
    def __init__(self, contract: dict[str, Any], assets: dict[str, Path], *, render_scale: float = 1.0):
        if render_scale <= 0.0 or render_scale > 1.0:
            raise ValueError("render scale must be greater than zero and no more than one")
        self.contract = contract
        self.render_scale = float(render_scale)
        self.out_width = round(int(contract["output"]["width"]) * render_scale)
        self.out_height = round(int(contract["output"]["height"]) * render_scale)
        source = np.asarray(Image.open(assets["source_art"]).convert("RGBA"), dtype=np.uint8)
        self.source_width = int(contract["source_art"]["width"])
        self.source_height = int(contract["source_art"]["height"])
        self.sprite_height = round(int(contract["placement"]["sprite_height"]) * render_scale)
        self.sprite_width = round(self.source_width * self.sprite_height / self.source_height)
        source = cv2.resize(source, (self.sprite_width, self.sprite_height), interpolation=cv2.INTER_LANCZOS4)
        alpha = source[:, :, 3:4].astype(np.float32) / 255.0
        self.source_premult = np.concatenate((source[:, :, :3].astype(np.float32) * alpha, source[:, :, 3:4]), axis=2)
        self.source_alpha_area = int(np.count_nonzero(source[:, :, 3] > 32))
        arm_spec = next(layer for layer in contract["layers"] if layer["id"] == "right_arm_foreground")
        arm_mask = np.zeros((self.sprite_height, self.sprite_width), dtype=np.uint8)
        arm_polygon = np.asarray([
            [round(float(x) * self.sprite_width / self.source_width), round(float(y) * self.sprite_height / self.source_height)]
            for x, y in arm_spec["mask_polygon_source_pixels"]
        ], dtype=np.int32)
        cv2.fillPoly(arm_mask, [arm_polygon], 255, lineType=cv2.LINE_AA)
        feather = float(arm_spec["feather_source_pixels"]) * self.sprite_height / self.source_height
        if feather > 0.0:
            arm_mask = cv2.GaussianBlur(arm_mask, (0, 0), feather)
        arm_weight = arm_mask.astype(np.float32)[:, :, None] / 255.0
        self.right_arm_source = self.source_premult * arm_weight
        self.body_source = self.source_premult * (1.0 - arm_weight)
        self.right_arm_nodes = set(str(value) for value in arm_spec["bound_nodes"])

        background = cv2.imread(str(assets["background"]), cv2.IMREAD_COLOR)
        if background is None:
            raise RuntimeError("unable to read deformable rig background")
        self.background = cv2.resize(background, (self.out_width, self.out_height), interpolation=cv2.INTER_LANCZOS4)
        self.background = self._grade_background(self.background)

        placement = contract["placement"]
        source_scale = self.sprite_height / self.source_height
        center_x = float(placement["character_center_x"]) * render_scale
        self.left = round(center_x - float(placement["source_center_x"]) * source_scale)
        self.top = round(
            float(placement["output_baseline_y"]) * render_scale
            - float(placement["source_baseline_y"]) * source_scale
        )
        self.scale_x = self.sprite_width / self.source_width
        self.scale_y = self.sprite_height / self.source_height
        self.grid_x, self.grid_y = np.meshgrid(
            np.arange(self.sprite_width, dtype=np.float32), np.arange(self.sprite_height, dtype=np.float32)
        )
        self.nodes = {str(node["id"]): node for node in contract["skeleton"]["nodes"]}
        self.body_pose_flows = {
            name: self._build_flow({
                node_id: delta for node_id, delta in (pose.get("deltas") or {}).items()
                if node_id not in self.right_arm_nodes
            })
            for name, pose in contract["poses"].items()
        }
        self.right_arm_pose_flows = {
            # The arm samples only its own RGBA layer, but it follows the full
            # body field at the shared shoulder so crouches and turns cannot
            # open a seam. Distal arm controls remain local through the soft
            # anatomical gates in _build_flow.
            name: self._build_flow(pose.get("deltas") or {})
            for name, pose in contract["poses"].items()
        }
        breath_deltas = {
            node_id: [0.0, float(amount)]
            for node_id, amount in contract["deformation"]["secondary_motion"]["vertical_source_pixels"].items()
        }
        self.breath_flow = self._build_flow(breath_deltas)
        self.corrective_basis = self._build_corrective_basis()
        self.background_with_shadow = self._contact_shadow(self.background.copy())

    @staticmethod
    def _grade_background(frame: np.ndarray) -> np.ndarray:
        graded = frame.astype(np.float32)
        graded[:, :, 2] *= 1.025
        graded[:, :, 1] *= 1.005
        graded[:, :, 0] *= 0.965
        height, width = frame.shape[:2]
        x = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]
        y = np.linspace(-1.0, 1.0, height, dtype=np.float32)[:, None]
        vignette = np.clip(1.04 - 0.07 * (x * x + 0.65 * y * y), 0.88, 1.04)
        graded *= vignette[:, :, None]
        return np.clip(graded, 0, 255).astype(np.uint8)

    def _build_flow(self, deltas: dict[str, list[float]]) -> tuple[np.ndarray, np.ndarray]:
        numerator_x = np.zeros_like(self.grid_x)
        numerator_y = np.zeros_like(self.grid_y)
        denominator = np.full_like(self.grid_x, float(self.contract["deformation"]["normalization_floor"]))
        for node_id, node in self.nodes.items():
            cx = float(node["point"][0]) * self.scale_x
            cy = float(node["point"][1]) * self.scale_y
            sigma = float(node["influence_radius"]) * (self.scale_x + self.scale_y) * 0.5
            weight = np.exp(-((self.grid_x - cx) ** 2 + (self.grid_y - cy) ** 2) / (2.0 * sigma * sigma))
            weight *= self._anatomical_region_gate(node_id)
            delta = deltas.get(node_id, [0.0, 0.0])
            numerator_x += weight * float(delta[0]) * self.scale_x
            numerator_y += weight * float(delta[1]) * self.scale_y
            denominator += weight
        flow_x = numerator_x / denominator
        flow_y = numerator_y / denominator
        pin_sigma = float(self.contract["deformation"]["contact_pin_radius"]) * (self.scale_x + self.scale_y) * 0.5
        for node_id in self.contract["skeleton"]["stationary_contact_pins"]:
            node = self.nodes[node_id]
            cx = float(node["point"][0]) * self.scale_x
            cy = float(node["point"][1]) * self.scale_y
            attenuation = 1.0 - np.exp(
                -((self.grid_x - cx) ** 2 + (self.grid_y - cy) ** 2) / (2.0 * pin_sigma * pin_sigma)
            )
            flow_x *= attenuation
            flow_y *= attenuation
        return flow_x.astype(np.float32), flow_y.astype(np.float32)

    def _anatomical_region_gate(self, node_id: str) -> np.ndarray | float:
        """Keep limb controls from borrowing torso/hip pixels.

        June's neutral sleeves touch the jacket at the shoulder, so a radial
        field alone can pull the flank during a large reach.  These soft
        source-space boundaries retain a continuous shoulder transition while
        making the distal arm fields anatomically local.
        """
        arm_nodes = ("shoulder", "elbow", "wrist", "hand")
        if not any(node_id.endswith(value) for value in arm_nodes):
            return 1.0
        y_source = self.grid_y / self.scale_y
        feather = max(1.0, 14.0 * self.scale_x)
        if node_id.startswith("screen_right_"):
            boundary = (620.0 + 0.06 * (y_source - 390.0)) * self.scale_x
            z = np.clip((self.grid_x - boundary) / feather, -12.0, 12.0)
            return 1.0 / (1.0 + np.exp(-z))
        if node_id.startswith("screen_left_"):
            boundary = (400.0 - 0.04 * (y_source - 390.0)) * self.scale_x
            z = np.clip((boundary - self.grid_x) / feather, -12.0, 12.0)
            return 1.0 / (1.0 + np.exp(-z))
        return 1.0

    def _build_corrective_basis(self) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for spec in self.contract["deformation"]["joint_correctives"]:
            node = self.nodes[str(spec["node"])]
            cx = float(node["point"][0]) * self.scale_x
            cy = float(node["point"][1]) * self.scale_y
            radius = float(spec["radius"]) * (self.scale_x + self.scale_y) * 0.5
            weight = np.exp(-((self.grid_x - cx) ** 2 + (self.grid_y - cy) ** 2) / (2.0 * radius * radius))
            weight *= self._anatomical_region_gate(str(spec["node"]))
            result[str(spec["id"])] = (
                ((self.grid_x - cx) * weight * float(spec["expand_x"])).astype(np.float32),
                ((self.grid_y - cy) * weight * float(spec["expand_y"])).astype(np.float32),
            )
        return result

    def _contact_shadow(self, frame: np.ndarray) -> np.ndarray:
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        scale = self.sprite_height / self.source_height
        left_foot = self.nodes["screen_left_foot"]["point"]
        right_foot = self.nodes["screen_right_foot"]["point"]
        for point, axes in ((left_foot, (58, 15)), (right_foot, (68, 16))):
            center = (round(self.left + float(point[0]) * scale), round(self.top + float(point[1]) * scale + 18 * scale))
            cv2.ellipse(
                mask, center, (round(axes[0] * scale), round(axes[1] * scale)), 0.0, 0.0, 360.0, 150, -1, cv2.LINE_AA
            )
        mask = cv2.GaussianBlur(mask, (0, 0), max(1.0, 10.0 * self.render_scale))
        darkness = (mask.astype(np.float32) / 255.0 * 0.34)[:, :, None]
        return np.clip(frame.astype(np.float32) * (1.0 - darkness), 0, 255).astype(np.uint8)

    def _state_flows(self, frame: int) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray], dict[str, Any]]:
        state = solve_pose_state(self.contract, frame)
        amount = float(state["amount"])
        body_left_x, body_left_y = self.body_pose_flows[state["left_pose"]]
        body_right_x, body_right_y = self.body_pose_flows[state["right_pose"]]
        arm_left_x, arm_left_y = self.right_arm_pose_flows[state["left_pose"]]
        arm_right_x, arm_right_y = self.right_arm_pose_flows[state["right_pose"]]
        body_x = body_left_x * (1.0 - amount) + body_right_x * amount + self.breath_flow[0] * float(state["breath"])
        body_y = body_left_y * (1.0 - amount) + body_right_y * amount + self.breath_flow[1] * float(state["breath"])
        arm_x = arm_left_x * (1.0 - amount) + arm_right_x * amount
        arm_y = arm_left_y * (1.0 - amount) + arm_right_y * amount
        return (body_x, body_y), (arm_x, arm_y), state

    def render_frame(self, frame: int) -> tuple[np.ndarray, dict[str, Any]]:
        body_flow, arm_flow, state = self._state_flows(frame)
        body_map_x = self.grid_x - body_flow[0]
        body_map_y = self.grid_y - body_flow[1]
        arm_map_x = self.grid_x - arm_flow[0]
        arm_map_y = self.grid_y - arm_flow[1]
        for identifier, amount in state["correctives"].items():
            basis_x, basis_y = self.corrective_basis[identifier]
            if identifier == "right_elbow_volume":
                arm_map_x = arm_map_x - basis_x * float(amount)
                arm_map_y = arm_map_y - basis_y * float(amount)
            else:
                body_map_x = body_map_x - basis_x * float(amount)
                body_map_y = body_map_y - basis_y * float(amount)
        warped_body = cv2.remap(
            self.body_source, body_map_x.astype(np.float32), body_map_y.astype(np.float32),
            cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
        )
        warped_arm = cv2.remap(
            self.right_arm_source, arm_map_x.astype(np.float32), arm_map_y.astype(np.float32),
            cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
        )
        arm_alpha = np.clip(warped_arm[:, :, 3:4] / 255.0, 0.0, 1.0)
        warped = np.empty_like(warped_body)
        warped[:, :, :3] = warped_arm[:, :, :3] + warped_body[:, :, :3] * (1.0 - arm_alpha)
        warped[:, :, 3:4] = warped_arm[:, :, 3:4] + warped_body[:, :, 3:4] * (1.0 - arm_alpha)
        warped[:, :, 0] *= 0.93
        warped[:, :, 1] *= 1.005
        warped[:, :, 2] *= 1.035
        frame_bgr = self.background_with_shadow.copy()
        y0, x0 = self.top, self.left
        y1, x1 = y0 + self.sprite_height, x0 + self.sprite_width
        sy0, sx0 = max(0, -y0), max(0, -x0)
        sy1, sx1 = self.sprite_height - max(0, y1 - self.out_height), self.sprite_width - max(0, x1 - self.out_width)
        oy0, ox0 = max(0, y0), max(0, x0)
        oy1, ox1 = min(self.out_height, y1), min(self.out_width, x1)
        sprite = warped[sy0:sy1, sx0:sx1]
        alpha = np.clip(sprite[:, :, 3:4] / 255.0, 0.0, 1.0)
        premult_rgb = sprite[:, :, :3][:, :, ::-1]
        target = frame_bgr[oy0:oy1, ox0:ox1].astype(np.float32)
        frame_bgr[oy0:oy1, ox0:ox1] = np.clip(premult_rgb + target * (1.0 - alpha), 0, 255).astype(np.uint8)

        alpha_plane = warped[:, :, 3]
        opaque_area = int(np.count_nonzero(alpha_plane > 32))
        contacts = self._measure_contacts(alpha_plane)
        landmarks = {}
        for node_id, node in self.nodes.items():
            dx, dy = state["deltas"][node_id]
            landmarks[node_id] = [
                self.left + (float(node["point"][0]) + dx) * self.scale_x,
                self.top + (float(node["point"][1]) + dy) * self.scale_y,
            ]
        return frame_bgr, {
            "alpha_area": opaque_area,
            "alpha_area_ratio": opaque_area / self.source_alpha_area,
            "contacts": contacts,
            "landmarks": landmarks,
            "pose": [state["left_pose"], state["right_pose"], state["amount"]],
        }

    def _measure_contacts(self, alpha: np.ndarray) -> dict[str, float]:
        result: dict[str, float] = {}
        radius = round(115 * self.scale_x)
        for node_id in self.contract["skeleton"]["stationary_contact_pins"]:
            x = round(float(self.nodes[node_id]["point"][0]) * self.scale_x)
            crop = alpha[:, max(0, x - radius):min(self.sprite_width, x + radius + 1)]
            ys = np.where(crop > 48)[0]
            result[node_id] = float(self.top + (int(ys.max()) if ys.size else -10_000))
        return result


def _resolve_ffmpeg(value: str | Path) -> str:
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(str(value))
    if not resolved:
        raise FileNotFoundError(f"FFmpeg executable not found: {value}")
    return resolved


def _encoded_review(video: Path, expected_frames: int, review_frames: list[int], review_dir: Path) -> dict[str, Any]:
    review_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(review_frames)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode deformable rig proof: {video}")
    decoded = 0
    selected: dict[int, np.ndarray] = {}
    sharpness: dict[str, float] = {}
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        decoded += 1
        if decoded in wanted:
            selected[decoded] = frame.copy()
            sharpness[str(decoded)] = round(float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()), 6)
            cv2.imwrite(str(review_dir / f"frame_{decoded:04d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 94])
    capture.release()
    if decoded != expected_frames or set(selected) != wanted:
        raise RuntimeError("deformable rig proof failed its exact encoded-frame gate")
    return {"decoded_frame_count": decoded, "frames": selected, "sharpness": sharpness}


def _contact_sheet(frames: dict[int, np.ndarray], path: Path) -> None:
    items = sorted(frames.items())
    columns = 4
    thumb_w, thumb_h, label_h = 480, 270, 34
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), (24, 19, 16))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (frame_number, bgr) in enumerate(items):
        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_w
        y = (index // columns) * (thumb_h + label_h)
        sheet.paste(image, (x, y))
        draw.text((x + 12, y + thumb_h + 10), f"Frame {frame_number:03d}", fill=(236, 219, 188), font=font)
    sheet.save(path, quality=94)


def render_deformable_rig_proof(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str | Path = "ffmpeg",
    render_scale: float = 1.0,
) -> dict[str, Any]:
    contract, assets = load_deformable_rig_contract(contract_path)
    renderer = DeformableRigRenderer(contract, assets, render_scale=render_scale)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _resolve_ffmpeg(ffmpeg)
    suffix = "" if math.isclose(render_scale, 1.0) else f"-{render_scale:.2f}x"
    video = output / f"june-deformable-rig-proof{suffix}.mp4"
    partial = output / f"june-deformable-rig-proof{suffix}.partial.mp4"
    partial.unlink(missing_ok=True)
    command = [
        ffmpeg_bin, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{renderer.out_width}x{renderer.out_height}", "-r", str(contract["output"]["fps"]),
        "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial),
    ]
    started = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None:
        raise RuntimeError("unable to open FFmpeg input pipe")
    contact_series: dict[str, list[float]] = {pin: [] for pin in contract["skeleton"]["stationary_contact_pins"]}
    alpha_ratios: list[float] = []
    landmark_steps: list[float] = []
    previous_landmarks: dict[str, list[float]] | None = None
    right_hand_positions: list[list[float]] = []
    root_positions: list[list[float]] = []
    unique_landmarks: set[tuple[int, ...]] = set()
    try:
        for frame_number in range(1, int(contract["output"]["frame_count"]) + 1):
            frame, metrics = renderer.render_frame(frame_number)
            process.stdin.write(frame.tobytes())
            alpha_ratios.append(float(metrics["alpha_area_ratio"]))
            for pin, value in metrics["contacts"].items():
                contact_series[pin].append(float(value))
            landmarks = metrics["landmarks"]
            right_hand_positions.append(landmarks["screen_right_hand"])
            root_positions.append(landmarks["root"])
            compact = tuple(round(value * 10) for node in sorted(landmarks) for value in landmarks[node])
            unique_landmarks.add(compact)
            if previous_landmarks is not None:
                landmark_steps.append(max(
                    math.dist(landmarks[node], previous_landmarks[node]) for node in landmarks
                ))
            previous_landmarks = landmarks
    finally:
        process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg failed while encoding deformable rig proof: {stderr}")
    partial.replace(video)

    expected_frames = int(contract["output"]["frame_count"])
    review = _encoded_review(video, expected_frames, contract["review_frames"], output / "review_frames")
    sheet = output / f"june-deformable-rig-proof-contact-sheet{suffix}.jpg"
    _contact_sheet(review["frames"], sheet)
    quality = contract["quality_gate"]
    foot_drifts = {pin: max(values) - min(values) for pin, values in contact_series.items()}
    hand_excursion = max(math.dist(right_hand_positions[0], point) for point in right_hand_positions)
    root_vertical = max(point[1] for point in root_positions) - min(point[1] for point in root_positions)
    metrics = {
        "foot_contact_drift_output_px": {key: round(value, 6) for key, value in foot_drifts.items()},
        "right_hand_excursion_output_px": round(hand_excursion, 6),
        "root_vertical_excursion_output_px": round(root_vertical, 6),
        "maximum_landmark_step_output_px": round(max(landmark_steps), 6),
        "alpha_area_ratio_range": [round(min(alpha_ratios), 6), round(max(alpha_ratios), 6)],
        "unique_landmark_poses": len(unique_landmarks),
        "minimum_encoded_review_laplacian_variance": min(review["sharpness"].values()),
    }
    scale_tolerance = render_scale
    failures: list[str] = []
    if max(foot_drifts.values()) > float(quality["maximum_foot_contact_drift_output_px"]) * scale_tolerance:
        failures.append("foot_contact_drift")
    if hand_excursion < float(quality["minimum_right_hand_excursion_output_px"]) * scale_tolerance:
        failures.append("hand_excursion")
    if root_vertical < float(quality["minimum_root_vertical_excursion_output_px"]) * scale_tolerance:
        failures.append("root_excursion")
    if max(landmark_steps) > float(quality["maximum_landmark_step_output_px"]) * scale_tolerance:
        failures.append("temporal_landmark_step")
    if min(alpha_ratios) < float(quality["minimum_alpha_area_ratio"]) or max(alpha_ratios) > float(quality["maximum_alpha_area_ratio"]):
        failures.append("alpha_area_stability")
    if len(unique_landmarks) < int(quality["minimum_unique_landmark_poses"]):
        failures.append("unique_pose_count")
    if min(review["sharpness"].values()) < float(quality["minimum_encoded_review_laplacian_variance"]):
        failures.append("encoded_retained_detail")

    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "continuous_wide_body_deformation_proof",
        "rig_id": contract["rig_id"],
        "classification": contract["classification"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "source_art_sha256": contract["source_art"]["sha256"],
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "render_scale": render_scale,
        "actions": [action["id"] for action in contract["actions"]],
        "deformation": {
            "method": contract["deformation"]["method"],
            "depth_ordered_layer_count": len(contract["layers"]),
            "joint_corrective_count": len(contract["deformation"]["joint_correctives"]),
            "stationary_contact_pins": contract["skeleton"]["stationary_contact_pins"],
            "full_frame_optical_flow_used": False,
            "cross_dissolve_used": False,
            "paid_runtime_generation_used": False
        },
        "metrics": metrics,
        "encoded_review": {
            "decoded_frame_count": review["decoded_frame_count"],
            "review_frame_count": len(review["frames"]),
            "laplacian_variance": review["sharpness"],
        },
        "final": {
            "file": video.name,
            "sha256": _sha256(video),
            "contact_sheet": sheet.name,
            "contact_sheet_sha256": _sha256(sheet),
            "width": renderer.out_width,
            "height": renderer.out_height,
            "fps": int(contract["output"]["fps"]),
            "frame_count": expected_frames,
            "duration_seconds": float(contract["output"]["duration_seconds"]),
            "video_codec": "h264",
            "pixel_format": "yuv420p",
        },
        "quality_gate_passed": not failures,
        "quality_gate_failures": failures,
        "known_limitations": contract["known_limitations"],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    report_path = output / f"june-deformable-rig-proof-report{suffix}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(f"deformable rig proof failed quality gates: {', '.join(failures)}")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's continuously deforming wide-body rig proof")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--render-scale", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_deformable_rig_proof(
        args.contract, args.output_dir, ffmpeg=args.ffmpeg, render_scale=args.render_scale
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
