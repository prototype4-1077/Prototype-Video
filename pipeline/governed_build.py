"""Drop-in entrypoint that places the existing build under Governor control."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import traceback

import build
from governor import PipelineGovernor, atomic_write_json, normalize_error


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