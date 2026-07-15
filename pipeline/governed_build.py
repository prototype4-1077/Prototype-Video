"""Drop-in entrypoint that places the existing build under Governor control."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import traceback

import build
from governor import PipelineGovernor, atomic_write_json, normalize_error


EXACT_VOICE_SHA256 = "8b6961debba312df72407fe8fabfd4546cec9e7298c9637372b6d7866ee8bc8f"


def _decode_part_set(parts: list[Path]) -> list[bytes]:
    """Return plausible decodes for split-stream and independently encoded parts."""
    texts = ["".join(path.read_text(encoding="ascii").split()) for path in parts]
    candidates: list[bytes] = []
    try:
        candidates.append(base64.b64decode("".join(texts), validate=True))
    except Exception:
        pass
    try:
        candidates.append(b"".join(base64.b64decode(text, validate=True) for text in texts))
    except Exception:
        pass
    return candidates


def _restore_exact_voice(build_dir: Path) -> None:
    """Recover James's exact supplied MP3 before alignment or mixing.

    ``force_tts`` is an explicit per-video escape hatch for a fresh continuous
    ElevenLabs render. It is used when the attached performance's model and
    settings are known but its legacy connector chunks are not byte-correct.
    Every ordinary supplied-voice build still requires the exact checksum.
    """
    target = build_dir / "vo.mp3"
    try:
        script = json.loads((build_dir / "script.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        script = {}
    if script.get("force_tts"):
        target.unlink(missing_ok=True)
        print("force_tts requested: generating one continuous narration from script settings", flush=True)
        return

    if target.exists():
        try:
            if hashlib.sha256(target.read_bytes()).hexdigest() == EXACT_VOICE_SHA256:
                return
        except OSError:
            pass

    exact_parts = sorted(build_dir.glob("voice_exact.mp3.b64.part*"))
    candidate_sets: list[tuple[str, list[Path]]] = []
    if exact_parts:
        candidate_sets.append(("voice_exact", exact_parts))

    legacy = sorted(build_dir.glob("vo.mp3.b64.part*"))
    if legacy:
        numeric = [
            path for path in legacy
            if re.fullmatch(r"vo\.mp3\.b64\.part\d{3}", path.name)
        ]
        if numeric:
            candidate_sets.append(("legacy_numeric", numeric))
        candidate_sets.append(("legacy_all", legacy))

        fixed = [
            path for path in legacy
            if re.fullmatch(r"vo\.mp3\.b64\.part(?:00[1-9]|010)", path.name)
        ]
        tail = [path for path in legacy if path not in fixed]
        if len(fixed) == 10 and len(tail) <= 10:
            for mask in range(1 << len(tail)):
                selected = fixed + [tail[i] for i in range(len(tail)) if mask & (1 << i)]
                if len(selected) > len(fixed):
                    candidate_sets.append((f"legacy_tail_{mask:0{len(tail)}b}", sorted(selected)))

    seen: set[tuple[str, ...]] = set()
    for label, parts in candidate_sets:
        key = tuple(path.name for path in parts)
        if not parts or key in seen:
            continue
        seen.add(key)
        for raw in _decode_part_set(parts):
            digest = hashlib.sha256(raw).hexdigest()
            if digest != EXACT_VOICE_SHA256:
                continue
            tmp = build_dir / ".vo.mp3.exact.tmp"
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            print(
                f"restored exact supplied voiceover from {label}: "
                f"{len(raw)} bytes sha256={digest}",
                flush=True,
            )
            return

    names = ", ".join(path.name for path in exact_parts + legacy)
    raise RuntimeError(
        "Exact supplied voiceover could not be reconstructed from repository parts; "
        f"expected sha256={EXACT_VOICE_SHA256}; found parts: {names or '(none)'}"
    )


def _install_probe_cache(build_dir: Path) -> None:
    """Cache successful ffprobe results across resumable build passes."""
    cache_path = build_dir / ".probe-cache.json"
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        cache = raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        cache = {}

    def cached_probe_ok(filename) -> bool:
        path = Path(filename)
        try:
            stat = path.stat()
        except OSError:
            return False
        key = str(path.resolve())
        signature = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        entry = cache.get(key)
        if isinstance(entry, dict) and entry.get("valid") is True and all(
            entry.get(field) == value for field, value in signature.items()
        ):
            return True

        result = build.sh([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ])
        valid = result.returncode == 0
        if valid:
            cache[key] = {**signature, "valid": True}
            atomic_write_json(cache_path, cache)
        else:
            cache.pop(key, None)
        return valid

    build.probe_ok = cached_probe_ok


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("ERROR: no build dir given | FIX: run governed_build.py build/<slug>", file=sys.stderr)
        return 1
    build_dir = Path(args[0]).resolve()
    _restore_exact_voice(build_dir)
    socket.setdefaulttimeout(float(os.environ.get("GOVERNOR_SOCKET_TIMEOUT_SECONDS", "60")))
    governor = PipelineGovernor(build_dir)
    build.sh = governor.run
    build.audio_variants.set_runner(governor.run)
    _install_probe_cache(build_dir)

    requested_budget = os.environ.get("BUILD_PASS_BUDGET")
    if requested_budget:
        build.BUDGET = max(30.0, float(requested_budget))
    elif os.environ.get("GITHUB_ACTIONS"):
        build.BUDGET = 120.0

    governor.record_event(
        "build_pass_start", pid=os.getpid(), build_budget_s=build.BUDGET,
        probe_cache=str(build_dir / ".probe-cache.json"),
    )
    try:
        build.main(str(build_dir))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        governor.record_event("build_pass_exit", exit_code=code)
        return int(code)
    except BaseException as exc:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        governor.record_event(
            "build_pass_crash",
            exception=type(exc).__name__,
            normalized_error=normalize_error(detail),
            traceback_tail=detail[-2000:],
        )
        print(detail, file=sys.stderr)
        return 1
    governor.record_event("build_pass_exit", exit_code=0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
