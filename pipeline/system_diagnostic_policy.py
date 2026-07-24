"""Calibrate the raw system diagnostic to evidence-eligible denominators.

The repository contains many abandoned, experimental, and never-rendered build
packages. Those remain useful inventory, but they are not a fair denominator for
telemetry or review coverage. This policy layer compares telemetry to builds with
render evidence and feedback to builds that actually have a review package.
"""
from __future__ import annotations

from collections import Counter
import argparse
import json
import os
from pathlib import Path
from typing import Any

import system_diagnostics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "pipeline" / "system_diagnostics"


def pct(part: int, total: int) -> float:
    return round(part / total, 4) if total else 0.0


def evidence_coverage(root: Path) -> dict[str, Any]:
    packages = [
        path for path in sorted((root / "build").glob("*"))
        if path.is_dir() and (path / "script.json").exists()
    ]
    render_evidence_names = (
        "governor-summary.json", "render-status.json", "quality_report.json",
        "telemetry-summary.json", "run-id.txt",
    )
    review_names = ("scene-review.json", "scene-review.html")
    feedback_names = ("scene-review-feedback.json", "scene-feedback.request.json")
    observed = [path for path in packages if any((path / name).exists() for name in render_evidence_names)]
    reviewable = [path for path in packages if any((path / name).exists() for name in review_names)]
    telemetry = [path for path in observed if (path / "telemetry-summary.json").exists()]
    feedback = [path for path in reviewable if any((path / name).exists() for name in feedback_names)]
    governor = [path for path in observed if (path / "governor-summary.json").exists()]
    quality = [path for path in observed if (path / "quality_report.json").exists()]
    return {
        "package_count": len(packages),
        "render_observed_count": len(observed),
        "reviewable_count": len(reviewable),
        "telemetry_count": len(telemetry),
        "governor_summary_count": len(governor),
        "quality_report_count": len(quality),
        "human_feedback_count": len(feedback),
        "telemetry_coverage_of_render_observed": pct(len(telemetry), len(observed)),
        "human_feedback_coverage_of_reviewable": pct(len(feedback), len(reviewable)),
        "inventory_boundary": (
            "package_count includes experiments and abandoned builds; telemetry and feedback "
            "coverage use only render-observed or reviewable builds respectively."
        ),
        "render_observed_slugs": [path.name for path in observed],
        "reviewable_slugs": [path.name for path in reviewable],
        "feedback_slugs": [path.name for path in feedback],
    }


def _finding(
    *, code: str, priority: str, area: str, title: str,
    evidence: Any, action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "priority": priority,
        "area": area,
        "title": title,
        "evidence": evidence,
        "action": action,
        "status": "open",
        "automatic_patch": False,
    }


def priority_rank(value: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(value, 5)


def build(root: Path = ROOT) -> dict[str, Any]:
    report = system_diagnostics.diagnostic(root)
    raw_coverage = report.get("coverage") or {}
    coverage = evidence_coverage(root)
    coverage["all_package_file_coverage"] = raw_coverage
    report["coverage"] = coverage
    findings = [
        item for item in (report.get("findings") or [])
        if item.get("code") not in {"telemetry_coverage_low", "human_feedback_coverage_low"}
    ]

    telemetry_ratio = coverage["telemetry_coverage_of_render_observed"]
    if coverage["render_observed_count"] and telemetry_ratio < 0.80:
        findings.append(_finding(
            code="telemetry_coverage_low",
            priority="high" if telemetry_ratio < 0.50 else "medium",
            area="observability",
            title="Render-observed builds are missing telemetry summaries",
            evidence={
                "coverage": telemetry_ratio,
                "telemetry_count": coverage["telemetry_count"],
                "render_observed_count": coverage["render_observed_count"],
            },
            action=(
                "Backfill honest stage summaries from Governor evidence where available and "
                "keep native OpenTelemetry capture mandatory for new renders."
            ),
        ))

    feedback_ratio = coverage["human_feedback_coverage_of_reviewable"]
    if coverage["reviewable_count"] and feedback_ratio < 0.50:
        findings.append(_finding(
            code="human_feedback_coverage_low",
            priority="medium",
            area="learning",
            title="Too few reviewable videos have exported human feedback",
            evidence={
                "coverage": feedback_ratio,
                "feedback_count": coverage["human_feedback_count"],
                "reviewable_count": coverage["reviewable_count"],
                "reviewable_slugs": coverage["reviewable_slugs"],
                "feedback_slugs": coverage["feedback_slugs"],
            },
            action=(
                "Review the highest-value completed videos first. Keep automated risk tags as "
                "screening evidence until James supplies a decision."
            ),
        ))

    findings.sort(key=lambda item: (priority_rank(str(item.get("priority"))), str(item.get("area")), str(item.get("code"))))
    report["findings"] = findings
    report["summary"] = {
        "finding_count": len(findings),
        "open_count": sum(item.get("status") == "open" for item in findings),
        "priorities": dict(Counter(str(item.get("priority") or "unknown") for item in findings)),
        "automatic_patch_candidates": sum(bool(item.get("automatic_patch")) for item in findings),
    }
    report["denominator_policy"] = coverage["inventory_boundary"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    report = build(Path(args.root).resolve())
    out = Path(args.out_dir)
    system_diagnostics.atomic_json(out / "LATEST.json", report)
    system_diagnostics.atomic_text(out / "LATEST.md", system_diagnostics.render_markdown(report))
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
