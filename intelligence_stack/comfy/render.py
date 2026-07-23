#!/usr/bin/env python3
"""Resolve and optionally submit a lower-model-safe ComfyUI workflow."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = Path(__file__).with_name("workflows")


def replace_tokens(value: Any, tokens: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: replace_tokens(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tokens(item, tokens) for item in value]
    if isinstance(value, str) and value in tokens:
        return tokens[value]
    if isinstance(value, str):
        for token, replacement in tokens.items():
            value = value.replace(token, str(replacement))
    return value


def validate_contract(contract: dict[str, Any]) -> None:
    required = (
        "workflow_id", "prompt", "negative_prompt", "seed", "subject_count",
        "action_count", "impossible_element_count", "constraints", "checkpoint",
        "width", "height", "filename_prefix",
    )
    missing = [key for key in required if contract.get(key) in (None, "")]
    if missing:
        raise ValueError("missing contract fields: " + ", ".join(missing))
    if contract["workflow_id"] != "single_subject_v1":
        raise ValueError("unsupported workflow_id")
    if int(contract["subject_count"]) != 1:
        raise ValueError("subject_count must equal one")
    if int(contract["action_count"]) > 1:
        raise ValueError("action_count must be at most one")
    if int(contract["impossible_element_count"]) > 1:
        raise ValueError("impossible_element_count must be at most one")
    if len(contract.get("constraints") or []) < 4:
        raise ValueError("at least four constraints are required")

    scene = {
        "image_prompt": contract["prompt"],
        "generation_constraints": contract["constraints"],
        "lower_model_safe": True,
        "generation_route": "comfyui",
        "comfy_workflow_id": contract["workflow_id"],
        "hero": True,
    }
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    from visual_risk import assess_scene

    report = assess_scene(scene)
    if not report["passes_enforcement"]:
        raise ValueError(
            f"visual contract remains too risky: score={report['effective_risk_score']} "
            f"recommendation={report['recommendation']}"
        )


def resolve(contract: dict[str, Any]) -> dict[str, Any]:
    validate_contract(contract)
    workflow_path = WORKFLOWS / f"{contract['workflow_id']}.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    negative = ", ".join(
        [contract["negative_prompt"]]
        + [str(item) for item in contract.get("constraints") or []]
        + ["extra fingers", "fused fingers", "duplicate subject", "cropped anatomy", "text", "watermark"]
    )
    tokens = {
        "${CHECKPOINT}": contract["checkpoint"],
        "${WIDTH}": int(contract["width"]),
        "${HEIGHT}": int(contract["height"]),
        "${POSITIVE_PROMPT}": contract["prompt"],
        "${NEGATIVE_PROMPT}": negative,
        "${SEED}": int(contract["seed"]),
        "${FILENAME_PREFIX}": contract["filename_prefix"],
    }
    return replace_tokens(workflow, tokens)


def http_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def submit(base_url: str, workflow: dict[str, Any], output_dir: Path) -> list[Path]:
    base = base_url.rstrip("/")
    client_id = str(uuid.uuid4())
    queued = http_json(f"{base}/prompt", {"prompt": workflow, "client_id": client_id})
    prompt_id = queued["prompt_id"]
    deadline = time.time() + 900
    history = None
    while time.time() < deadline:
        history_payload = http_json(f"{base}/history/{prompt_id}")
        history = history_payload.get(prompt_id)
        if history and history.get("outputs"):
            break
        time.sleep(2)
    if not history:
        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete")

    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for node in history.get("outputs", {}).values():
        for image in node.get("images", []):
            query = urllib.parse.urlencode({
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            })
            destination = output_dir / Path(image["filename"]).name
            urllib.request.urlretrieve(f"{base}/view?{query}", destination)
            files.append(destination)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract")
    parser.add_argument("--workflow-out")
    parser.add_argument("--output-dir", default="build/comfy-output")
    parser.add_argument("--comfy-url", default=os.environ.get("COMFYUI_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    workflow = resolve(contract)
    workflow_out = Path(args.workflow_out or f"{args.contract}.resolved.json")
    workflow_out.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    print(f"resolved workflow -> {workflow_out}")

    if args.dry_run or not args.comfy_url:
        print("dry run: no ComfyUI request submitted")
        return 0
    files = submit(args.comfy_url, workflow, Path(args.output_dir))
    for path in files:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
