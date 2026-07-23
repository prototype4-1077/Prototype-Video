"""Promptfoo provider for fixture CI and live lower-model evaluation."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def call_api(prompt, options, context):
    config = (options or {}).get("config", {})
    command = os.environ.get("LOWER_MODEL_COMMAND") or config.get("command")
    if command:
        result = subprocess.run(
            shlex.split(command),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=int(config.get("timeout_seconds", 300)),
            check=False,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"model command exited {result.returncode}"}
        return {"output": result.stdout.strip()}

    case_id = str((context or {}).get("vars", {}).get("case_id") or "")
    fixture = HERE / "fixtures" / f"{case_id}.json"
    if not fixture.exists():
        return {"error": f"No fixture for case_id={case_id!r}; set LOWER_MODEL_COMMAND for live evaluation"}
    return {"output": fixture.read_text(encoding="utf-8")}
