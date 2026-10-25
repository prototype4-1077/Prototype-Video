"""Validate supplied narration without deleting, replacing, or transcoding it."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from exact_audio import ExactAudioError, probe_audio


def validate(build: Path) -> dict:
    script = json.loads((build / "script.json").read_text(encoding="utf-8"))
    supplied = bool(script.get("user_vo") or list(build.glob("vo.mp3.b64.part*")))
    if not supplied:
        return {"applicable": False, "passed": True}
    voice = build / "vo.mp3"
    if not voice.is_file() or not voice.stat().st_size:
        raise ExactAudioError("supplied narration is missing; restore the exact attachment before rendering")
    data = voice.read_bytes()
    fmt, duration = probe_audio(voice)
    if "mp3" not in fmt.split(",") or not math.isfinite(duration) or duration <= 0:
        raise ExactAudioError("supplied narration must be a decodable MP3 with positive duration")
    actual = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
              "duration_seconds": duration}
    manifest = build / "audio-verification.json"
    if manifest.exists():
        expected = json.loads(manifest.read_text(encoding="utf-8"))
        for key in ("sha256", "size_bytes"):
            if expected.get(key) is not None and actual[key] != expected[key]:
                raise ExactAudioError(f"supplied narration {key} mismatch; stop without replacing the attachment")
        if expected.get("duration_seconds") is not None and abs(
            duration - float(expected["duration_seconds"])
        ) > 0.001:
            raise ExactAudioError("supplied narration duration mismatch")
    return {"applicable": True, "passed": True, **actual,
            "policy": "preserve exact bytes; no minimum file size or duration"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.build), indent=2))
