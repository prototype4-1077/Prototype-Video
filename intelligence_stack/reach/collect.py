#!/usr/bin/env python3
"""Collect external signals through Agent Reach's healthy upstream tools.

Agent Reach is treated as a capability/health layer, not a scraping wrapper. This
script records `agent-reach doctor`, then calls public upstream tools directly.
Authenticated channel exports can be ingested as minimized JSONL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("config.json")
DEFAULT_OUT = ROOT / "concept" / "external_signals"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def stable_id(*parts: Any) -> str:
    payload = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def command_json(args: list[str], timeout: int = 90) -> Any:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {clean_text(result.stderr, 500)}")
    return json.loads(result.stdout)


def doctor_report() -> dict[str, Any]:
    executable = shutil.which("agent-reach")
    if not executable:
        return {"available": False, "status": "not_installed"}
    result = subprocess.run(
        [executable, "doctor"], capture_output=True, text=True, timeout=120, check=False
    )
    return {
        "available": True,
        "returncode": result.returncode,
        "status": "healthy" if result.returncode == 0 else "review",
        "output": clean_text(result.stdout or result.stderr, 4000),
    }


def base_record(
    *, source: str, title: str, url: str, excerpt: str = "", query: str = "",
    published_at: str | None = None, signal_type: str = "external_signal",
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": stable_id(source, url, title),
        "source": source,
        "title": clean_text(title, 240),
        "url": clean_text(url, 1000),
        "excerpt": clean_text(excerpt),
        "query": clean_text(query, 240),
        "published_at": published_at,
        "collected_at": utc_now(),
        "signal_type": signal_type,
        "claim_status": "unverified",
        "rights_status": "reference_only",
        "raw": raw or {},
    }


def collect_github(config: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    if not shutil.which("gh"):
        return []
    records: list[dict[str, Any]] = []
    env = os.environ.copy()
    if env.get("GITHUB_TOKEN") and not env.get("GH_TOKEN"):
        env["GH_TOKEN"] = env["GITHUB_TOKEN"]
    for repo in config.get("github_repositories", []):
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/releases?per_page={limit}"],
            capture_output=True, text=True, timeout=90, check=False, env=env,
        )
        if result.returncode != 0:
            continue
        try:
            releases = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for release in releases if isinstance(releases, list) else []:
            records.append(base_record(
                source="github_release",
                title=f"{repo}: {release.get('name') or release.get('tag_name') or 'release'}",
                url=release.get("html_url") or "",
                excerpt=release.get("body") or "",
                query=repo,
                published_at=release.get("published_at") or release.get("created_at"),
                signal_type="tool_release",
                raw={"repository": repo, "tag": release.get("tag_name")},
            ))
    return records


def collect_youtube(config: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    executable = shutil.which("yt-dlp")
    if not executable:
        return []
    records: list[dict[str, Any]] = []
    for query in config.get("youtube_queries", []):
        result = subprocess.run(
            [
                executable, "--dump-single-json", "--flat-playlist", "--skip-download",
                f"ytsearch{limit}:{query}",
            ],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if result.returncode != 0:
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for entry in payload.get("entries") or []:
            video_id = entry.get("id")
            url = entry.get("url") or (
                f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            )
            records.append(base_record(
                source="youtube_search",
                title=entry.get("title") or "YouTube result",
                url=url,
                excerpt=entry.get("description") or "",
                query=query,
                published_at=entry.get("timestamp") or entry.get("upload_date"),
                signal_type="audience_language_or_research",
                raw={
                    "channel": entry.get("channel") or entry.get("uploader"),
                    "duration": entry.get("duration"),
                    "view_count": entry.get("view_count"),
                },
            ))
    return records


def _find_text(element: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        value = element.findtext(name)
        if value:
            return value
        for child in element:
            if child.tag.rsplit("}", 1)[-1] == name and child.text:
                return child.text
    return ""


def collect_rss(config: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    headers = {"User-Agent": "Prototype-Video-Signal-Radar/1.0"}
    for feed in config.get("rss_feeds", []):
        try:
            request = urllib.request.Request(feed["url"], headers=headers)
            with urllib.request.urlopen(request, timeout=45) as response:
                root = ET.fromstring(response.read())
        except (OSError, KeyError, ET.ParseError, urllib.error.URLError):
            continue
        items = list(root.findall(".//item"))
        if not items:
            items = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "entry"]
        for item in items[:limit]:
            title = _find_text(item, ("title",))
            link = _find_text(item, ("link",))
            if not link:
                for child in item:
                    if child.tag.rsplit("}", 1)[-1] == "link" and child.attrib.get("href"):
                        link = child.attrib["href"]
                        break
            records.append(base_record(
                source="rss",
                title=title or feed.get("name") or "RSS item",
                url=link,
                excerpt=_find_text(item, ("description", "summary", "content")),
                query=feed.get("name") or feed.get("url") or "rss",
                published_at=_find_text(item, ("pubDate", "published", "updated")) or None,
                signal_type="research_or_news",
                raw={"feed": feed.get("name"), "feed_url": feed.get("url")},
            ))
    return records


def ingest_jsonl(paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for value in paths:
        path = Path(value)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            source = clean_text(item.get("source") or "authenticated_export", 80)
            records.append(base_record(
                source=source,
                title=item.get("title") or item.get("text") or "External signal",
                url=item.get("url") or "",
                excerpt=item.get("excerpt") or item.get("text") or "",
                query=item.get("query") or "",
                published_at=item.get("published_at"),
                signal_type=item.get("signal_type") or "authenticated_signal",
                raw={
                    key: item.get(key) for key in ("platform", "metrics", "topic")
                    if item.get(key) is not None
                },
            ))
    return records


def score_and_tag(record: dict[str, Any], topics: list[dict[str, Any]]) -> None:
    haystack = " ".join(
        str(record.get(key) or "") for key in ("title", "excerpt", "query")
    ).lower()
    matches: list[str] = []
    score = 0
    for topic in topics:
        topic_hits = sum(haystack.count(str(term).lower()) for term in topic.get("terms", []))
        if topic_hits:
            matches.append(topic["id"])
            score += min(topic_hits, 4)
    record["topic_matches"] = matches
    record["editorial_relevance_score"] = min(score, 20)


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("url") or record.get("id")
        previous = output.get(key)
        if previous is None or record.get("editorial_relevance_score", 0) > previous.get(
            "editorial_relevance_score", 0
        ):
            output[key] = record
    return list(output.values())


def brief_markdown(records: list[dict[str, Any]], doctor: dict[str, Any]) -> str:
    lines = [
        "# External Signal Radar",
        "",
        f"Generated: {utc_now()}",
        "",
        "> External attention is a signal, never authority. Every item is unverified",
        "> until reviewed for evidence, autonomy, sequence, and channel fit.",
        "",
        f"Agent Reach health: **{doctor.get('status', 'unknown')}**",
        "",
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        topics = record.get("topic_matches") or ["unclustered"]
        for topic in topics[:2]:
            grouped.setdefault(topic, []).append(record)
    for topic, items in sorted(grouped.items(), key=lambda pair: -len(pair[1])):
        lines.extend([f"## {topic.replace('_', ' ').title()}", ""])
        for item in sorted(
            items, key=lambda value: -value.get("editorial_relevance_score", 0)
        )[:8]:
            lines.append(
                f"- **{item.get('title') or 'Untitled'}** — {item.get('source')} "
                f"(score {item.get('editorial_relevance_score', 0)}). "
                f"{item.get('excerpt') or 'No excerpt retained.'}"
            )
        lines.append("")
    lines.extend([
        "## Editorial handoff",
        "",
        "Before any item becomes a concept: identify the human question, verify the",
        "claim with primary sources, state the strongest alternative, define the safe",
        "landing, and hand James the choice.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--ingest", action="append", default=[])
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    limit = int(config.get("limits", {}).get("per_query", 6))
    records = ingest_jsonl(args.ingest)
    doctor = doctor_report()
    if args.live:
        records.extend(collect_github(config, limit))
        records.extend(collect_youtube(config, limit))
        records.extend(collect_rss(config, limit))

    for record in records:
        score_and_tag(record, config.get("topics", []))
    records = sorted(
        dedupe(records),
        key=lambda item: (-item.get("editorial_relevance_score", 0), item.get("title", "")),
    )[: int(config.get("limits", {}).get("max_records", 120))]

    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "editorial_rule": config.get("editorial_rule"),
        "agent_reach": doctor,
        "record_count": len(records),
        "records": records,
    }
    (output_dir / "LATEST.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "DAILY_SIGNAL_BRIEF.md").write_text(
        brief_markdown(records, doctor), encoding="utf-8"
    )
    print(f"external signal radar: {len(records)} records -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
