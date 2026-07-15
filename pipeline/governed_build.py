"""Drop-in entrypoint that places the existing build under Governor control."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import traceback

import build
from governor import PipelineGovernor, normalize_error


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
    governor.record_event("build_pass_start", pid=os.getpid())
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
