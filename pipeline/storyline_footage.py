"""Narrative-first wrapper around the existing stock footage selector.

It preserves the mature stock acquisition stack, but prevents it from choosing a
visually attractive clip that does not represent the spoken beat.  When no direct
stock match survives, a deterministic literal storyboard is rendered instead.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import footage
import narrative_fidelity
import profiles
import storyboard
import visual_symbols


class NoNarrativeMatch(RuntimeError):
    def __init__(self, decisions):
        super().__init__("no stock candidate passed narrative fidelity")
        self.decisions = decisions


_CURRENT = {"scene": None, "index": None, "total": None}
_ORIGINAL_RANK = footage.rank


def _gated_rank(query, vids, need=None, genre=None, profile=None):
    scored = _ORIGINAL_RANK(query, vids, need, genre, profile)
    scene = _CURRENT["scene"] or {}
    accepted, decisions = narrative_fidelity.rerank(
        scene, scored, _CURRENT["index"], _CURRENT["total"]
    )
    _CURRENT["decisions"] = decisions
    if narrative_fidelity.direct_match_required(
        scene, _CURRENT["index"], _CURRENT["total"]
    ) and not accepted:
        raise NoNarrativeMatch(decisions)
    return accepted or scored


def _write_report(build_dir: str, rows: list[dict]):
    path = Path(build_dir) / "narrative_fidelity_report.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        existing = current.get("scenes") if isinstance(current, dict) else []
    except (OSError, ValueError, TypeError):
        existing = []
    merged = {int(row.get("scene_index", -1)): row for row in existing or []}
    for row in rows:
        merged[int(row.get("scene_index", -1))] = row
    path.write_text(json.dumps({
        "schema_version": 1,
        "policy": narrative_fidelity.rules(),
        "scenes": [merged[key] for key in sorted(merged) if key >= 0],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _render_storyboard(build_dir: str, script: dict, index: int, reason: str, decisions=None):
    scene = script["scenes"][index]
    plan = storyboard.render_scene(build_dir, script, index)
    plan["fallback_reason"] = reason
    if decisions is not None:
        plan["candidate_decisions"] = decisions
    print(f"scene {index}: literal storyboard <- {reason}")
    return plan


def main(build_dir: str, idx: str | None = None):
    script_path = Path(build_dir) / "script.json"
    script = json.loads(script_path.read_text(encoding="utf-8"))
    profile = profiles.resolve(script)
    if visual_symbols.apply_plan(script, profile):
        script_path.write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")
    used = {
        scene.get("stock_id") or scene.get("pexels_id")
        for scene in script.get("scenes", [])
        if scene.get("stock_id") or scene.get("pexels_id")
    }
    targets = [int(idx)] if idx is not None else list(range(len(script.get("scenes", []))))
    report_rows = []
    footage.rank = _gated_rank
    try:
        for index in targets:
            scene = script["scenes"][index]
            _CURRENT.update({
                "scene": scene,
                "index": index,
                "total": len(script["scenes"]),
                "decisions": [],
            })
            row = {
                "scene_index": index,
                "text": scene.get("text"),
                "query": scene.get("query"),
                "narrative_mode_before": scene.get("narrative_mode"),
            }
            current_id = scene.get("stock_id") or scene.get("pexels_id")
            current_video = {
                "id": current_id,
                "url": scene.get("source_url"),
                "title": scene.get("source_title"),
            }
            rejected_existing = (
                narrative_fidelity.rejected_context(scene, current_video)
                if current_id else None
            )
            if rejected_existing:
                plan = _render_storyboard(
                    build_dir, script, index,
                    str(rejected_existing.get("reason") or "approved edit rejected this stock context"),
                )
                row.update({"result": "literal_storyboard", "plan": plan})
            elif storyboard.preferred(scene, index, len(script["scenes"])):
                plan = _render_storyboard(build_dir, script, index, "literal mechanism preferred")
                row.update({"result": "literal_storyboard", "plan": plan})
            else:
                try:
                    footage.fetch_scene(build_dir, script, index, used)
                    row.update({
                        "result": "stock",
                        "stock_id": scene.get("stock_id") or scene.get("pexels_id"),
                        "candidate_decisions": _CURRENT.get("decisions") or [],
                    })
                except NoNarrativeMatch as exc:
                    plan = _render_storyboard(
                        build_dir, script, index,
                        "no stock candidate represented the spoken anchors",
                        exc.decisions,
                    )
                    row.update({
                        "result": "literal_storyboard",
                        "candidate_decisions": exc.decisions,
                        "plan": plan,
                    })
                except SystemExit as exc:
                    message = str(exc)
                    if "no results" not in message and "no candidate" not in message:
                        raise
                    plan = _render_storyboard(
                        build_dir, script, index,
                        "stock search could not produce a usable direct match",
                        _CURRENT.get("decisions") or [],
                    )
                    row.update({"result": "literal_storyboard", "plan": plan})
            script_path.write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")
            report_rows.append(row)
    finally:
        footage.rank = _ORIGINAL_RANK
    _write_report(build_dir, report_rows)
    visual_symbols.write_report(build_dir, script, profile)


def cli(argv=None):
    args = list(argv or sys.argv[1:])
    if not args:
        raise SystemExit("usage: storyline_footage.py <build_dir> [scene_index|credits|pin]")
    build_dir = args[0]
    if len(args) > 1 and args[1] == "credits":
        footage.write_credits(build_dir)
        return 0
    if len(args) > 1 and args[1] == "pin":
        footage.pin(
            build_dir, int(args[2]), args[3], args[4] if len(args) > 4 else None,
        )
        return 0
    main(build_dir, args[1] if len(args) > 1 else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
