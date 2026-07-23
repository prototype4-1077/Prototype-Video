"""Drop-in entrypoint that places the existing build under Governor control."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import traceback

import animation_profiles
import build
import profiles
from governor import PipelineGovernor, atomic_write_json, normalize_error


def _install_storyline_router(governor: PipelineGovernor):
    """Route stock acquisition through the approved narrative-fidelity layer."""
    storyline_entry = Path(__file__).with_name("storyline_footage.py")

    def governed_runner(command, **kwargs):
        if isinstance(command, (list, tuple)):
            parts = [str(part) for part in command]
            script_index = next(
                (i for i, part in enumerate(parts) if Path(part).name == "footage.py"),
                None,
            )
            if script_index is not None:
                parts[script_index] = str(storyline_entry)
                tail = parts[script_index + 1:]
                stage = "credits" if "credits" in tail else "footage"
                return governor.run(parts, stage_override=stage, **kwargs)
        return governor.run(command, **kwargs)

    build.sh = governed_runner
    return governed_runner


def _apply_animation_contract(build_dir: Path) -> dict | None:
    """Persist a requested animation profile before any production stage runs."""
    script_path = build_dir / "script.json"
    if not script_path.exists():
        return None
    try:
        script = json.loads(script_path.read_text(encoding="utf-8"))
        character_profile = profiles.resolve(script, strict=True)
        changed = animation_profiles.apply_defaults(
            script, character_profile=character_profile, strict=True
        )
        animation_name = animation_profiles.resolve(script, strict=True)
        if animation_name:
            # The literal author query remains in animation_base_query. The styled
            # query becomes the actual acquisition query so the selected contract
            # changes real footage selection rather than merely documenting intent.
            for scene in script.get("scenes") or []:
                styled = animation_profiles.effective_query(scene, animation_name)
                if styled and scene.get("query") != styled:
                    scene["query"] = styled
                    changed = True
        errors = animation_profiles.validate(script, character_profile)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"animation profile validation failed: {exc}") from exc
    if errors:
        raise ValueError("animation profile validation failed: " + "; ".join(errors))
    if changed:
        script_path.write_text(
            json.dumps(script, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return script


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
    try:
        prepared = _apply_animation_contract(build_dir)
    except ValueError as exc:
        print(f"ERROR: {exc} | FIX: choose a supported animation_profile and repair its contract", file=sys.stderr)
        return 1
    # Covers direct network work performed inside build.py itself (currently
    # font acquisition). Child stages are bounded independently by the Governor.
    socket.setdefaulttimeout(float(os.environ.get("GOVERNOR_SOCKET_TIMEOUT_SECONDS", "60")))
    governor = PipelineGovernor(build_dir)
    governed_runner = _install_storyline_router(governor)
    build.audio_variants.set_runner(governed_runner)
    _install_probe_cache(build_dir)

    # Local quick passes stay short. CI receives enough room to cross an entire
    # validation/checkpoint boundary rather than repeatedly stopping just before
    # overlays or final assembly.
    requested_budget = os.environ.get("BUILD_PASS_BUDGET")
    if requested_budget:
        build.BUDGET = max(30.0, float(requested_budget))
    elif os.environ.get("GITHUB_ACTIONS"):
        build.BUDGET = 120.0

    animation_name = animation_profiles.resolve(prepared or {})
    governor.record_event(
        "build_pass_start", pid=os.getpid(), build_budget_s=build.BUDGET,
        probe_cache=str(build_dir / ".probe-cache.json"),
        narrative_fidelity=str(Path(__file__).with_name("editorial_memory.json")),
        animation_profile=animation_name,
        animation_quality_tier=(prepared or {}).get("animation_quality_tier"),
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
