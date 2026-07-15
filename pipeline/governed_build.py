"""Drop-in entrypoint that places the existing build under Governor control."""
from __future__ import annotations

import base64
import hashlib
import itertools
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
EXACT_VOICE_BYTES = 2_919_902
EXACT_VOICE_B64_CHARS = 3_893_204


def _clean_b64(path: Path) -> str:
    return "".join(path.read_text(encoding="ascii").split())


def _write_if_exact(build_dir: Path, raw: bytes, label: str) -> bool:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXACT_VOICE_SHA256:
        return False
    tmp = build_dir / ".vo.mp3.exact.tmp"
    tmp.write_bytes(raw)
    os.replace(tmp, build_dir / "vo.mp3")
    print(
        f"restored exact supplied voiceover from {label}: "
        f"{len(raw)} bytes sha256={digest}",
        flush=True,
    )
    return True


def _try_order(build_dir: Path, ordered: list[Path], texts: dict[Path, str], label: str) -> bool:
    if not ordered:
        return False
    try:
        raw = base64.b64decode("".join(texts[path] for path in ordered), validate=True)
        if _write_if_exact(build_dir, raw, label + ":continuous"):
            return True
    except Exception:
        pass
    try:
        raw = b"".join(base64.b64decode(texts[path], validate=True) for path in ordered)
        if _write_if_exact(build_dir, raw, label + ":independent"):
            return True
    except Exception:
        pass
    return False


def _restore_exact_voice(build_dir: Path) -> None:
    """Recover James's exact supplied MP3 before alignment or mixing.

    The original connector transfer left a handful of alternate tail fragments.
    The correct bytes are still present, but lexicographic wildcard concatenation
    can place those alternatives in the wrong order. Reconstruct only candidates
    whose encoded or decoded size matches the known attachment, then accept the
    single byte sequence whose SHA-256 matches the uploaded MP3.
    """
    target = build_dir / "vo.mp3"
    if target.exists():
        try:
            if hashlib.sha256(target.read_bytes()).hexdigest() == EXACT_VOICE_SHA256:
                return
        except OSError:
            pass

    exact_parts = sorted(build_dir.glob("voice_exact.mp3.b64.part*"))
    legacy = sorted(build_dir.glob("vo.mp3.b64.part*"))
    parts = exact_parts or legacy
    if not parts:
        raise RuntimeError("No connector voiceover parts were found")

    texts = {path: _clean_b64(path) for path in parts}

    # Fast paths for clean transfers.
    if _try_order(build_dir, parts, texts, "all_parts"):
        return
    numeric = [path for path in parts if re.fullmatch(r"(?:voice_exact\.|vo\.)mp3\.b64\.part\d{3}", path.name)]
    if numeric and _try_order(build_dir, sorted(numeric), texts, "numeric_parts"):
        return

    # The first ten canonical parts were transferred successfully. The remaining
    # files contain the original tail plus a few alternate splits. Search only
    # size-compatible subsets and their orderings; at most six tail files exist.
    fixed = sorted(
        path for path in parts
        if re.fullmatch(r"vo\.mp3\.b64\.part(?:00[1-9]|010)", path.name)
    )
    tail = [path for path in parts if path not in fixed]
    if len(fixed) == 10 and len(tail) <= 8:
        fixed_text_chars = sum(len(texts[path]) for path in fixed)
        required_text_chars = EXACT_VOICE_B64_CHARS - fixed_text_chars
        for count in range(1, len(tail) + 1):
            for combo in itertools.combinations(tail, count):
                if sum(len(texts[path]) for path in combo) != required_text_chars:
                    continue
                for perm in itertools.permutations(combo):
                    if _try_order(build_dir, fixed + list(perm), texts, "legacy_encoded_tail"):
                        return

        decoded: dict[Path, bytes] = {}
        for path in parts:
            try:
                decoded[path] = base64.b64decode(texts[path], validate=True)
            except Exception:
                pass
        if all(path in decoded for path in fixed):
            fixed_raw_bytes = sum(len(decoded[path]) for path in fixed)
            required_raw_bytes = EXACT_VOICE_BYTES - fixed_raw_bytes
            decoded_tail = [path for path in tail if path in decoded]
            for count in range(1, len(decoded_tail) + 1):
                for combo in itertools.combinations(decoded_tail, count):
                    if sum(len(decoded[path]) for path in combo) != required_raw_bytes:
                        continue
                    for perm in itertools.permutations(combo):
                        raw = b"".join(decoded[path] for path in fixed + list(perm))
                        if _write_if_exact(build_dir, raw, "legacy_decoded_tail"):
                            return

    details = ", ".join(f"{path.name}:{len(texts[path])}" for path in parts)
    raise RuntimeError(
        "Exact supplied voiceover could not be reconstructed from repository parts; "
        f"expected bytes={EXACT_VOICE_BYTES} b64_chars={EXACT_VOICE_B64_CHARS} "
        f"sha256={EXACT_VOICE_SHA256}; parts={details}"
    )


def _install_probe_cache(build_dir: Path) -> None:
    """Avoid re-running ffprobe for every completed segment on every pass.

    A successful probe remains valid while the file's byte size and nanosecond
    modification time are unchanged. The cache is stored inside the build
    directory so resumable Governor passes share it, but a modified or replaced
    media file is always probed again.
    """
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
    # Covers direct network work performed inside build.py itself (currently
    # font acquisition). Child stages are bounded independently by the Governor.
    socket.setdefaulttimeout(float(os.environ.get("GOVERNOR_SOCKET_TIMEOUT_SECONDS", "60")))
    governor = PipelineGovernor(build_dir)
    build.sh = governor.run
    build.audio_variants.set_runner(governor.run)
    _install_probe_cache(build_dir)

    # Local quick passes stay short. CI receives enough room to cross an entire
    # validation/checkpoint boundary rather than repeatedly stopping just before
    # overlays or final assembly.
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
    except BaseException as exc:  # flight-recorder path for bugs outside child processes
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
