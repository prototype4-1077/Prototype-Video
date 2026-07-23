"""Perpetual Frontier Loop for the Concept Engine.

This is a constitutional, read-mostly evolution laboratory. It observes the
catalog, renders, audience results, feedback, external signals, and operational
telemetry; then writes hypotheses and proposals under concept/evolution_state.
It never edits scripts, frontier truth, render requests, or the permanent ethos.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
STATE_DIR = Path("concept/evolution_state")
CONSTITUTION_PATH = Path("concept/evolution_constitution.json")
RULES_PATH = Path("concept/provisional_rules.json")
CAPABILITIES_PATH = Path("concept/capability_constitution.json")
EXPEDITIONS_PATH = Path("concept/expedition_library.json")


def _load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _hash(value: Any, length: int = 16) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return statistics.mean(vals) if vals else 0.0


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text).lower())


def _performance_score(stats: Mapping[str, Any]) -> float:
    views = max(_float(stats.get("views")), 0.0)
    retention = _float(stats.get("avg_view_pct") or stats.get("average_view_percentage"))
    completion = _float(stats.get("completion_rate"))
    likes = _float(stats.get("likes"))
    comments = _float(stats.get("comments"))
    reach = math.log10(views + 1.0)
    return round(reach * max(retention, completion, 1.0) + math.log10(likes + comments + 1.0) * 5.0, 4)


def _overall_decision(feedback: Mapping[str, Any]) -> str | None:
    overall = feedback.get("overall") or {}
    if isinstance(overall, Mapping):
        value = overall.get("decision")
        return str(value).lower() if value else None
    return None


def _extract_failure_tags(text: str) -> list[str]:
    vocabulary = {
        "hand_anatomy": ("hand", "finger", "thumb", "wrist", "anatom"),
        "reflection": ("mirror", "reflection", "reflected"),
        "darkness": ("dark", "too dim", "black", "shadowed"),
        "semantic_mismatch": ("doesn't match", "does not match", "confusing", "unclear", "muddy"),
        "duplicate_object": ("duplicate", "extra", "double", "two heads", "two hands"),
        "synthetic_contact": ("fused", "merged", "holding", "gripping", "contact", "tool"),
        "title_layout": ("title", "cut off", "thumbnail", "placement", "text"),
        "motion_quality": ("still", "movement", "motion", "static", "lifeless"),
    }
    low = str(text).lower()
    return [tag for tag, needles in vocabulary.items() if any(needle in low for needle in needles)]


def _script_descriptors(script: Mapping[str, Any], catalog: Mapping[str, Any]) -> dict[str, Any]:
    scenes = script.get("scenes") or []
    human = 0
    hero = 0
    generated = 0
    for scene in scenes:
        blob = " ".join(str(scene.get(k) or "") for k in ("query", "image_prompt", "visual", "description", "human_role"))
        if re.search(r"\b(person|people|human|man|woman|face|body|hand|child|couple)\b", blob, re.I):
            human += 1
        if scene.get("hero"):
            hero += 1
        if scene.get("image_prompt") or scene.get("generated") or scene.get("generation_provider"):
            generated += 1
    count = max(len(scenes), 1)
    return {
        "pillars": list(catalog.get("pillars") or script.get("pillars") or []),
        "frontier": catalog.get("frontier") or script.get("frontier"),
        "narration": catalog.get("narration") or script.get("narration_style") or script.get("profile") or "unknown",
        "hook": catalog.get("hook") or script.get("hook_type") or "unknown",
        "series": catalog.get("series") or script.get("series") or "standalone",
        "fidelity": script.get("fidelity") or catalog.get("fidelity") or "unknown",
        "visual_mode": script.get("visual_mode") or "default",
        "profile": script.get("profile") or "liam",
        "human_ratio": round(human / count, 4),
        "hero_ratio": round(hero / count, 4),
        "generated_ratio": round(generated / count, 4),
        "scene_count": len(scenes),
        "word_count": sum(len(_norm_words(scene.get("text", ""))) for scene in scenes),
    }


def discover_records(root: Path) -> list[dict[str, Any]]:
    catalog_payload = _load(root / "concept/catalog.json", {}) or {}
    catalog = catalog_payload.get("videos") or {}
    records: list[dict[str, Any]] = []
    build_dirs = sorted((root / "build").glob("*")) if (root / "build").exists() else []
    for build_dir in build_dirs:
        if not build_dir.is_dir():
            continue
        script = _load(build_dir / "script.json", {}) or {}
        if not script:
            continue
        slug = str(script.get("slug") or build_dir.name)
        stats = _load(build_dir / "yt_stats.json", {}) or {}
        feedback = (
            _load(build_dir / "scene-review-feedback.json", None)
            or _load(build_dir / "scene-feedback.request.json", None)
            or _load(build_dir / "scene-review.json", {})
            or {}
        )
        telemetry = _load(build_dir / "telemetry-summary.json", {}) or {}
        quality = _load(build_dir / "quality_report.json", {}) or {}
        motion = _load(build_dir / "motion_report.json", {}) or {}
        descriptors = _script_descriptors(script, catalog.get(slug, {}) or {})
        revisions: list[dict[str, Any]] = []
        for item in feedback.get("scenes") or []:
            decision = str(item.get("decision") or "").lower()
            if decision in {"revise", "revision", "needs_revision"}:
                comment = str(item.get("comments") or item.get("comment") or "")
                revisions.append({
                    "scene_index": item.get("scene_index"),
                    "comment": comment,
                    "failure_tags": _extract_failure_tags(comment),
                })
        records.append({
            "slug": slug,
            "title": script.get("title") or slug,
            "script": script,
            "stats": stats,
            "score": _performance_score(stats) if stats else None,
            "feedback_decision": _overall_decision(feedback),
            "revisions": revisions,
            "telemetry": telemetry,
            "quality": quality,
            "motion": motion,
            "descriptors": descriptors,
        })
    return records


def _category_evidence(records: Sequence[Mapping[str, Any]], field: str) -> dict[str, list[float]]:
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    for record in records:
        score = record.get("score")
        if score is None:
            continue
        value = (record.get("descriptors") or {}).get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item not in (None, "", "unknown"):
                buckets[str(item)].append(float(score))
    return buckets


def build_hypotheses(records: Sequence[Mapping[str, Any]], previous: Mapping[str, Any]) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    all_scores = [float(r["score"]) for r in records if r.get("score") is not None]
    global_mean = _mean(all_scores)
    for field in ("pillars", "narration", "hook", "visual_mode", "profile", "fidelity"):
        for value, scores in sorted(_category_evidence(records, field).items()):
            lift = _mean(scores) - global_mean
            sample = len(scores)
            confidence = _bounded((sample / 8.0) * (abs(lift) / max(abs(global_mean), 1.0)))
            direction = "improves" if lift >= 0 else "reduces"
            hypotheses.append({
                "id": f"performance:{field}:{value}",
                "kind": "performance",
                "statement": f"The {field} value '{value}' may {direction} blended reach and retention in the present catalog.",
                "evidence_for": {"sample_count": sample, "mean_score": round(_mean(scores), 4), "global_mean": round(global_mean, 4), "lift": round(lift, 4)},
                "evidence_against": ["Topic demand, hook strength, visual quality, and publication timing may explain the same result."],
                "alternatives": ["Selection bias", "Small sample", "Confounded production quality"],
                "confidence": round(confidence, 4),
                "context": {"field": field, "value": value},
                "test": f"Hold topic, duration, voice, and visual-motion ratio constant while changing only {field}.",
            })

    failures: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        for revision in record.get("revisions") or []:
            for tag in revision.get("failure_tags") or ["uncategorized_revision"]:
                failures[tag].append({"slug": record.get("slug"), "scene_index": revision.get("scene_index")})
    for tag, examples in sorted(failures.items(), key=lambda pair: -len(pair[1])):
        hypotheses.append({
            "id": f"visual_failure:{tag}",
            "kind": "visual_reliability",
            "statement": f"Scenes involving {tag.replace('_', ' ')} may have an elevated revision risk.",
            "evidence_for": {"revision_count": len(examples), "examples": examples[:12]},
            "evidence_against": ["The failure may be provider-specific or caused by one prompt family."],
            "alternatives": ["Model version", "Prompt complexity", "Source image quality"],
            "confidence": round(_bounded(len(examples) / 8.0), 4),
            "context": {"failure_tag": tag},
            "test": "Compare stock, constrained workflow, and unconstrained generation for the same visual mechanism.",
        })

    stage_samples: dict[str, list[float]] = collections.defaultdict(list)
    for record in records:
        for stage, metrics in ((record.get("telemetry") or {}).get("stages") or {}).items():
            value = metrics.get("total_duration_s") or metrics.get("p95_s") or metrics.get("p95_success_s")
            if value is not None:
                stage_samples[str(stage)].append(_float(value))
    if stage_samples:
        medians = {stage: _mean(values) for stage, values in stage_samples.items()}
        global_stage = _mean(medians.values())
        for stage, value in sorted(medians.items(), key=lambda pair: -pair[1])[:6]:
            hypotheses.append({
                "id": f"efficiency:{stage}",
                "kind": "efficiency",
                "statement": f"The {stage} stage may be a high-leverage efficiency target without changing creative policy.",
                "evidence_for": {"mean_duration_s": round(value, 3), "stage_baseline_s": round(global_stage, 3), "runs": len(stage_samples[stage])},
                "evidence_against": ["Slow stages may be purchasing quality rather than wasting time."],
                "alternatives": ["Provider latency", "Cache miss", "Necessary model load"],
                "confidence": round(_bounded(len(stage_samples[stage]) / 10.0), 4),
                "context": {"stage": stage},
                "test": "Run champion/challenger timing with output hashes and James approval held as acceptance gates.",
            })

    prior = {item.get("id"): item for item in previous.get("hypotheses") or []}
    for item in hypotheses:
        old = prior.get(item["id"]) or {}
        item["previous_confidence"] = old.get("confidence")
        item["learning_progress"] = round(abs(_float(item["confidence"]) - _float(old.get("confidence"))), 4) if old else None
        item["last_tested"] = dt.date.today().isoformat()
    return sorted(hypotheses, key=lambda item: (-item["confidence"], item["id"]))


def build_diversity_atlas(records: Sequence[Mapping[str, Any]], constitution: Mapping[str, Any]) -> dict[str, Any]:
    dimensions = constitution.get("quality_diversity", {}).get("dimensions") or ["pillars", "fidelity", "hook", "narration", "human_band", "generation_band"]
    cells: dict[str, dict[str, Any]] = {}
    observed_values: dict[str, set[str]] = collections.defaultdict(set)
    for record in records:
        desc = dict(record.get("descriptors") or {})
        desc["human_band"] = "low" if desc.get("human_ratio", 0) < 0.25 else ("medium" if desc.get("human_ratio", 0) < 0.5 else "high")
        desc["generation_band"] = "low" if desc.get("generated_ratio", 0) < 0.2 else ("medium" if desc.get("generated_ratio", 0) < 0.5 else "high")
        values: list[str] = []
        cell_desc: dict[str, str] = {}
        for dim in dimensions:
            raw = desc.get(dim)
            if isinstance(raw, list):
                raw = raw[0] if raw else "none"
            value = str(raw or "none")
            observed_values[dim].add(value)
            values.append(f"{dim}={value}")
            cell_desc[dim] = value
        key = "|".join(values)
        score = record.get("score")
        incumbent = cells.get(key)
        if incumbent is None or (score is not None and _float(score, -1) > _float(incumbent.get("score"), -1)):
            cells[key] = {"cell": key, "elite_slug": record.get("slug"), "score": score, "descriptors": cell_desc}
    possible = 1
    for dim in dimensions:
        possible *= max(len(observed_values[dim]), 1)
    return {
        "dimensions": dimensions,
        "occupied_cells": len(cells),
        "observed_possible_cells": possible,
        "coverage": round(len(cells) / max(possible, 1), 4),
        "cells": sorted(cells.values(), key=lambda item: (item.get("score") is None, -_float(item.get("score")), item["cell"])),
        "observed_values": {key: sorted(values) for key, values in observed_values.items()},
    }


def detect_unknown_unknowns(records: Sequence[Mapping[str, Any]], atlas: Mapping[str, Any], hypotheses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    scored = [r for r in records if r.get("score") is not None]
    if scored:
        mean = _mean(r["score"] for r in scored)
        stdev = statistics.pstdev([float(r["score"]) for r in scored]) if len(scored) > 1 else 0.0
        for record in scored:
            z = (float(record["score"]) - mean) / stdev if stdev else 0.0
            if abs(z) >= 1.5:
                findings.append({
                    "kind": "performance_outlier",
                    "slug": record.get("slug"),
                    "surprise": round(z, 3),
                    "question": "Which unmodeled feature explains why this video performed far from the current category expectation?",
                })
    for record in records:
        desc = record.get("descriptors") or {}
        if not desc.get("pillars") and not desc.get("frontier"):
            findings.append({"kind": "taxonomy_gap", "slug": record.get("slug"), "question": "This video fits no declared pillar or frontier concept; is the map missing a dimension?"})
        if record.get("feedback_decision") in {"approved", "approve"} and record.get("score") is not None and scored:
            if float(record["score"]) < _mean(r["score"] for r in scored) * 0.4:
                findings.append({"kind": "taste_performance_disagreement", "slug": record.get("slug"), "question": "James approved the craft but audience performance lagged; was distribution, topic demand, or packaging the missing variable?"})
    known_tags = {h.get("context", {}).get("failure_tag") for h in hypotheses if h.get("kind") == "visual_reliability"}
    uncategorized = sum(1 for r in records for rev in r.get("revisions") or [] if not rev.get("failure_tags"))
    if uncategorized:
        findings.append({"kind": "unclassified_feedback", "count": uncategorized, "known_tags": sorted(tag for tag in known_tags if tag), "question": "Revision comments exist outside the current failure vocabulary; cluster them before adding another rule."})
    if atlas.get("coverage", 1.0) < 0.35:
        findings.append({"kind": "creative_monoculture_risk", "coverage": atlas.get("coverage"), "question": "The quality-diversity atlas is sparse; which absent region is both on-ethos and technically learnable?"})
    return findings


def _unused_frontier(frontier: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    used = {str((r.get("descriptors") or {}).get("frontier")) for r in records if (r.get("descriptors") or {}).get("frontier")}
    return [item for item in frontier if str(item.get("id")) not in used]


def build_curiosity_queue(hypotheses: Sequence[Mapping[str, Any]], unknowns: Sequence[Mapping[str, Any]], frontier: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]], patterns: Mapping[str, Any]) -> list[dict[str, Any]]:
    pillar_weights = {str(p.get("id")): _float(p.get("weight")) for p in patterns.get("pillars") or []}
    max_weight = max(pillar_weights.values(), default=1.0)
    queue: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        confidence = _float(hypothesis.get("confidence"))
        uncertainty = 1.0 - confidence
        progress = _float(hypothesis.get("learning_progress"), 0.1)
        reuse = 0.9 if hypothesis.get("kind") in {"visual_reliability", "efficiency"} else 0.65
        risk = 0.25 if hypothesis.get("kind") == "performance" else 0.15
        score = uncertainty * (0.4 + progress) * reuse / (0.4 + risk)
        queue.append({"id": hypothesis.get("id"), "source": "hypothesis", "question": hypothesis.get("statement"), "curiosity_score": round(score, 4), "why_now": hypothesis.get("test")})
    for item in unknowns:
        queue.append({"id": f"unknown:{_hash(item)}", "source": "unknown_unknown", "question": item.get("question"), "curiosity_score": 0.9, "why_now": item})
    for item in _unused_frontier(frontier, records):
        related = [token for token in _norm_words(item.get("science", "") + " " + item.get("metaphor", "")) if token in pillar_weights]
        relevance = max((pillar_weights[token] / max_weight for token in related), default=0.55)
        queue.append({"id": f"frontier:{item.get('id')}", "source": "untouched_frontier", "question": f"What can the channel learn by developing '{item.get('title')}' without imitating a current winner?", "curiosity_score": round(0.7 * relevance + 0.25, 4), "why_now": item.get("hook")})
    dedup: dict[str, dict[str, Any]] = {}
    for item in queue:
        current = dedup.get(str(item["id"]))
        if current is None or item["curiosity_score"] > current["curiosity_score"]:
            dedup[str(item["id"])] = item
    return sorted(dedup.values(), key=lambda item: (-item["curiosity_score"], str(item["id"])))


def build_dreams(patterns: Mapping[str, Any], expeditions: Mapping[str, Any], as_of: dt.date, count: int = 12) -> list[dict[str, Any]]:
    pillars = patterns.get("pillars") or []
    domains = expeditions.get("domains") or []
    if not pillars or not domains:
        return []
    rng = random.Random(int(as_of.strftime("%Y%m%d")))
    pairs = list(itertools.combinations(pillars, 2))
    rng.shuffle(pairs)
    domains = list(domains)
    rng.shuffle(domains)
    dreams: list[dict[str, Any]] = []
    for index, ((a, b), domain) in enumerate(zip(itertools.cycle(pairs), itertools.cycle(domains))):
        if index >= count:
            break
        mechanism = rng.choice(domain.get("mechanisms") or [domain.get("name", "unknown mechanism")])
        visual = rng.choice(domain.get("visual_languages") or ["a concrete moving object"])
        a_label = a.get("label") or a.get("id")
        b_label = b.get("label") or b.get("id")
        dreams.append({
            "id": f"dream:{as_of.isoformat()}:{index + 1:02d}",
            "title": f"{str(mechanism).title()}: {a.get('id')} × {b.get('id')}",
            "parents": [a.get("id"), b.get("id")],
            "expedition_domain": domain.get("name"),
            "borrowed_mechanism": mechanism,
            "visual_language": visual,
            "hook": f"What if {str(mechanism).lower()} is already happening inside the way you experience {str(a_label).lower()}?",
            "ruling_metaphor": f"Use {visual} as one continuous metaphor for the relationship between {a_label} and {b_label}.",
            "turn": "Move from being trapped by the mechanism to noticing where the viewer can examine or test it.",
            "invitation": f"Where might {str(mechanism).lower()} be shaping what you call '{a.get('id')}' or '{b.get('id')}' right now?",
            "fidelity": "metaphor",
            "science_warning": domain.get("analogy_warning") or "Borrow the mechanism as a metaphor unless direct evidence is separately established.",
            "surprise_score": round(rng.uniform(0.72, 0.99), 4),
            "status": "dream_only",
        })
    return dreams


def design_experiments(hypotheses: Sequence[Mapping[str, Any]], curiosity: Sequence[Mapping[str, Any]], constitution: Mapping[str, Any]) -> list[dict[str, Any]]:
    curiosity_map = {item.get("id"): item for item in curiosity}
    experiments: list[dict[str, Any]] = []
    for hypothesis in hypotheses[:24]:
        c = curiosity_map.get(hypothesis.get("id"), {})
        info = _float(c.get("curiosity_score"), 1.0 - _float(hypothesis.get("confidence")))
        kind = hypothesis.get("kind")
        context = hypothesis.get("context") or {}
        variable = context.get("field") or context.get("failure_tag") or context.get("stage") or kind
        experiments.append({
            "id": f"experiment:{_hash(hypothesis.get('id'))}",
            "hypothesis_id": hypothesis.get("id"),
            "question": hypothesis.get("statement"),
            "treatment": f"Change only {variable} using the challenger condition.",
            "control": f"Keep the current champion value for {variable}.",
            "fixed_factors": ["core concept", "narration text", "voice", "duration", "publication window", "motion ratio where possible"],
            "primary_metrics": ["first-3-second retention", "average view percentage", "James scene approval", "revision count"],
            "secondary_metrics": ["render cost", "render duration", "visual-risk incidents", "comments indicating belief analysis"],
            "information_value": round(info, 4),
            "budget_lane": "uncertainty",
            "stop_conditions": ["science-fidelity violation", "grounding removed", "approved narration changed", "visual quality below floor"],
            "requires_human_approval": True,
        })
    return sorted(experiments, key=lambda item: (-item["information_value"], item["id"]))


def build_disagreement_observatory(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    roles = {
        "scientist": "What evidence supports this, what would falsify it, and is the fidelity label honest?",
        "mystic": "What is the largest meaningful reading without pretending it is established fact?",
        "skeptic": "Which assumption is being smuggled in, and what is the strongest opposite explanation?",
        "audience_anthropologist": "How might different viewers hear blame, dread, comfort, or invitation in this?",
        "visual_physicist": "Can one concrete moving subject express the mechanism without fragile anatomy or impossible contact?",
        "editor": "Where does attention rise, where does the mechanism reveal, and where does the piece earn its turn?",
        "ordinary_person": "Would this make sense to someone tired at midnight without specialized vocabulary?",
        "archivist": "Have we already made this in another costume, and what is genuinely new?",
        "contrarian": "What becomes visible if the proposed interpretation is reversed?",
    }
    output = []
    for candidate in candidates[:12]:
        output.append({
            "candidate_id": candidate.get("id"),
            "candidate": candidate.get("question") or candidate.get("title"),
            "positions": [{"role": role, "challenge": challenge} for role, challenge in roles.items()],
            "resolution_policy": "Preserve the disagreement map; do not average it into a vote. A human decides which tensions the artifact must hold.",
        })
    return output


def build_lineage(records: Sequence[Mapping[str, Any]], dreams: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    child_counts: collections.Counter[str] = collections.Counter()
    for record in records:
        slug = str(record.get("slug"))
        nodes.append({"id": f"video:{slug}", "kind": "video", "title": record.get("title"), "score": record.get("score")})
        desc = record.get("descriptors") or {}
        parents = list(desc.get("pillars") or []) + ([desc.get("frontier")] if desc.get("frontier") else [])
        for parent in parents:
            parent_id = f"concept:{parent}"
            edges.append({"from": parent_id, "to": f"video:{slug}", "relation": "realized_in"})
            child_counts[parent_id] += 1
        for parent in record.get("script", {}).get("parent_concepts") or []:
            parent_id = f"concept:{parent}"
            edges.append({"from": parent_id, "to": f"video:{slug}", "relation": "declared_parent"})
            child_counts[parent_id] += 1
    for dream in dreams:
        dream_id = str(dream.get("id"))
        nodes.append({"id": dream_id, "kind": "dream", "title": dream.get("title"), "status": dream.get("status")})
        for parent in dream.get("parents") or []:
            parent_id = f"concept:{parent}"
            edges.append({"from": parent_id, "to": dream_id, "relation": "cross_pollinated_into"})
            child_counts[parent_id] += 1
        if dream.get("expedition_domain"):
            domain_id = f"domain:{dream['expedition_domain']}"
            edges.append({"from": domain_id, "to": dream_id, "relation": "borrowed_mechanism"})
            child_counts[domain_id] += 1
    existing = {node["id"] for node in nodes}
    for edge in edges:
        if edge["from"] not in existing:
            kind, _, title = edge["from"].partition(":")
            nodes.append({"id": edge["from"], "kind": kind, "title": title})
            existing.add(edge["from"])
    return {"nodes": nodes, "edges": edges, "reproductive_value": [{"id": key, "descendant_count": count} for key, count in child_counts.most_common()]}


def review_rules(root: Path, as_of: dt.date, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rules_payload = _load(root / RULES_PATH, {}) or {}
    reviewed = []
    for rule in rules_payload.get("rules") or []:
        item = dict(rule)
        if item.get("kind") == "constitutional":
            item.update({"effective_confidence": 1.0, "status": "permanent", "decay_applied": False})
            reviewed.append(item)
            continue
        last = item.get("last_evidence") or item.get("created_at") or as_of.isoformat()
        try:
            days = max((as_of - dt.date.fromisoformat(str(last)[:10])).days, 0)
        except ValueError:
            days = 0
        half_life = max(_float(item.get("half_life_days"), 90.0), 1.0)
        base = _float(item.get("confidence"), 0.5)
        effective = base * (0.5 ** (days / half_life))
        contexts = set(item.get("contexts") or [])
        contradictions = 0
        for record in records:
            if contexts and contexts.intersection(set((record.get("descriptors") or {}).get("pillars") or [])):
                if record.get("feedback_decision") in {"approved", "approve"} and record.get("score") is not None and float(record["score"]) > 0:
                    contradictions += 1 if item.get("direction") == "avoid" else 0
        effective *= 0.85 ** contradictions
        status = "active" if effective >= 0.55 else ("retest" if effective >= 0.25 else "retire_candidate")
        item.update({"effective_confidence": round(effective, 4), "status": status, "decay_applied": True, "days_since_evidence": days, "contradictions": contradictions})
        reviewed.append(item)
    return {"rules": reviewed, "retest_queue": [item for item in reviewed if item["status"] in {"retest", "retire_candidate"}]}


def score_coherence(candidate: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    text = " ".join(str(candidate.get(key) or "") for key in ("title", "question", "hook", "ruling_metaphor", "turn", "invitation", "science_warning"))
    layers = {
        "scientific": 1.0 if candidate.get("fidelity") in {"established", "emerging", "metaphor"} else 0.55,
        "conceptual": 0.9 if candidate.get("ruling_metaphor") or candidate.get("question") else 0.45,
        "emotional": 0.9 if candidate.get("turn") or "agency" in text.lower() else 0.6,
        "visual": 0.85 if candidate.get("visual_language") or "one" in text.lower() else 0.65,
        "temporal": 0.75,
        "ethical": 1.0 if "choose" not in text.lower() and "blame" not in text.lower() else 0.65,
        "catalog_novelty": 0.85,
        "audience": 0.9 if str(candidate.get("invitation") or candidate.get("question") or "").strip().endswith("?") else 0.6,
        "operational": 0.8,
        "channel": 0.95 if candidate.get("invitation") or candidate.get("requires_human_approval") else 0.7,
    }
    candidate_tokens = set(_norm_words(text))
    overlap = 0.0
    for record in records:
        title_tokens = set(_norm_words(record.get("title", "")))
        if candidate_tokens and title_tokens:
            overlap = max(overlap, len(candidate_tokens & title_tokens) / max(len(candidate_tokens | title_tokens), 1))
    layers["catalog_novelty"] = round(_bounded(1.0 - overlap), 4)
    blockers = [layer for layer, score in layers.items() if score < 0.6]
    return {"candidate_id": candidate.get("id"), "layers": {key: round(value, 4) for key, value in layers.items()}, "overall": round(_mean(layers.values()), 4), "blockers": blockers, "status": "eligible_for_human_review" if not blockers else "needs_revision"}


def score_multiple_selves(candidates: Sequence[Mapping[str, Any]], constitution: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selves = constitution.get("cognitive_selves") or []
    scored: dict[str, list[dict[str, Any]]] = {}
    coherence = {item.get("candidate_id"): item for item in [score_coherence(c, records) for c in candidates]}
    for self_config in selves:
        name = str(self_config.get("id"))
        weights = self_config.get("weights") or {}
        rows = []
        for candidate in candidates:
            c = coherence.get(candidate.get("id"), {})
            layers = c.get("layers") or {}
            total_weight = max(sum(_float(v) for v in weights.values()), 1.0)
            score = sum(_float(layers.get(layer), 0.5) * _float(weight) for layer, weight in weights.items()) / total_weight
            rows.append({"candidate_id": candidate.get("id"), "score": round(score, 4), "reason": self_config.get("mission")})
        scored[name] = sorted(rows, key=lambda row: (-row["score"], str(row["candidate_id"])))
    crossover_totals: collections.defaultdict[str, list[float]] = collections.defaultdict(list)
    for rows in scored.values():
        for row in rows:
            crossover_totals[str(row["candidate_id"])].append(float(row["score"]))
    crossovers = sorted(
        ({"candidate_id": cid, "mean_score": round(_mean(values), 4), "minimum_self_score": round(min(values), 4), "self_count": len(values)} for cid, values in crossover_totals.items()),
        key=lambda item: (-item["minimum_self_score"], -item["mean_score"], item["candidate_id"]),
    )
    return {"selves": scored, "crossovers": crossovers, "coherence": list(coherence.values())}


def evaluate_capabilities(root: Path) -> dict[str, Any]:
    payload = _load(root / CAPABILITIES_PATH, {}) or {}
    reports = []
    for capability in payload.get("capabilities") or []:
        evidence = []
        for path_pattern in capability.get("evidence_paths") or []:
            matches = list(root.glob(path_pattern))
            if matches:
                evidence.extend(str(path.relative_to(root)) for path in matches[:12])
        minimum = int(capability.get("minimum_evidence") or 1)
        status = "demonstrated" if len(evidence) >= minimum else ("developing" if evidence else "untested")
        reports.append({**capability, "status": status, "evidence_count": len(evidence), "evidence": evidence})
    return {"capabilities": reports, "demonstrated": sum(item["status"] == "demonstrated" for item in reports), "total": len(reports)}


def build_negative_space(frontier: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]], dreams: Sequence[Mapping[str, Any]], atlas: Mapping[str, Any], rule_review: Mapping[str, Any]) -> dict[str, Any]:
    rejected = []
    for record in records:
        for revision in record.get("revisions") or []:
            rejected.append({"slug": record.get("slug"), **revision, "classification": "execution_failure_until_proven_bad_concept"})
    quality_failures = []
    for record in records:
        for failure in (record.get("quality") or {}).get("failures") or []:
            quality_failures.append({"slug": record.get("slug"), **failure})
    return {
        "untouched_frontier": list(_unused_frontier(frontier, records)),
        "rejected_scene_ideas": rejected,
        "quality_failures": quality_failures,
        "dreams_not_selected": [dream for dream in dreams if dream.get("status") == "dream_only"],
        "sparse_atlas": {"coverage": atlas.get("coverage"), "observed_values": atlas.get("observed_values")},
        "rules_awaiting_retest": rule_review.get("retest_queue") or [],
        "revisit_question": "What was a good idea paired with immature evidence, tooling, timing, packaging, or model capability?",
    }


def surprise_portfolio(records: Sequence[Mapping[str, Any]], experiments: Sequence[Mapping[str, Any]], dreams: Sequence[Mapping[str, Any]], constitution: Mapping[str, Any]) -> dict[str, Any]:
    budget = constitution.get("surprise_budget") or {"proven": 0.7, "uncertainty": 0.2, "wild": 0.1}
    proven = sorted((r for r in records if r.get("score") is not None), key=lambda r: -float(r["score"]))[:7]
    return {
        "allocation": budget,
        "proven_lane": [{"slug": item.get("slug"), "score": item.get("score"), "descriptors": item.get("descriptors")} for item in proven],
        "uncertainty_lane": list(experiments[:4]),
        "wild_lane": list(sorted(dreams, key=lambda d: -_float(d.get("surprise_score")))[:3]),
        "policy": "The wild lane cannot be removed by short-term performance optimization; James decides whether any proposal becomes production work.",
    }


def _load_external_signals(root: Path) -> list[Mapping[str, Any]]:
    candidates = [
        root / "concept/external_signals/LATEST.json",
        root / "intelligence_stack/reach/output/LATEST.json",
        root / "intelligence_stack/reach/LATEST.json",
    ]
    for path in candidates:
        payload = _load(path, None)
        if isinstance(payload, Mapping):
            return list(payload.get("records") or payload.get("signals") or [])
    return []


def build_brief(state: Mapping[str, Any]) -> str:
    lines = [
        "# Perpetual Frontier Brief",
        "",
        f"_Cycle: {state.get('cycle_date')} · Records: {state.get('record_count')} · External signals: {state.get('external_signal_count')}_",
        "",
        "## Constitutional status",
        "The evolution laboratory generated observations and proposals only. It did not alter scripts, frontier truth, render requests, or permanent ethos rules.",
        "",
        "## Highest-curiosity questions",
    ]
    for item in (state.get("curiosity_queue") or [])[:5]:
        lines.append(f"- **{item.get('curiosity_score'):.3f}** — {item.get('question')}")
    lines += ["", "## Best uncertainty-reducing experiments"]
    for item in (state.get("experiments") or [])[:4]:
        lines.append(f"- **{item.get('question')}**  ")
        lines.append(f"  Control: {item.get('control')} Treatment: {item.get('treatment')}")
    lines += ["", "## Wild frontier proposals"]
    for item in (state.get("dreams") or [])[:3]:
        lines.append(f"- **{item.get('title')}** — {item.get('hook')}")
        lines.append(f"  Fidelity: metaphor. Invitation: {item.get('invitation')}")
    lines += ["", "## Unknown unknowns"]
    for item in (state.get("unknown_unknowns") or [])[:5]:
        lines.append(f"- {item.get('question')}")
    lines += ["", "## Rule review"]
    for item in (state.get("rule_review", {}).get("retest_queue") or [])[:5]:
        lines.append(f"- `{item.get('id')}` → **{item.get('status')}** (effective confidence {item.get('effective_confidence')})")
    lines += ["", "## Human gate", "Nothing in this brief is a command. The next act is a choice: which uncertainty is worth spending a real video to examine?"]
    return "\n".join(lines) + "\n"


def run_cycle(root: Path, as_of: dt.date) -> dict[str, Any]:
    root = root.resolve()
    constitution = _load(root / CONSTITUTION_PATH, {}) or {}
    patterns = _load(root / "concept/patterns.json", {}) or {}
    frontier_payload = _load(root / "concept/frontier.json", {}) or {}
    frontier = frontier_payload.get("frontier") or []
    expeditions = _load(root / EXPEDITIONS_PATH, {}) or {}
    previous = _load(root / STATE_DIR / "LATEST.json", {}) or {}
    records = discover_records(root)
    hypotheses = build_hypotheses(records, previous)
    atlas = build_diversity_atlas(records, constitution)
    unknowns = detect_unknown_unknowns(records, atlas, hypotheses)
    curiosity = build_curiosity_queue(hypotheses, unknowns, frontier, records, patterns)
    dreams = build_dreams(patterns, expeditions, as_of)
    experiments = design_experiments(hypotheses, curiosity, constitution)
    disagreement = build_disagreement_observatory(list(experiments[:6]) + list(dreams[:6]))
    lineage = build_lineage(records, dreams)
    rules = review_rules(root, as_of, records)
    selves = score_multiple_selves(list(experiments[:8]) + list(dreams[:8]), constitution, records)
    capabilities = evaluate_capabilities(root)
    negative_space = build_negative_space(frontier, records, dreams, atlas, rules)
    portfolio = surprise_portfolio(records, experiments, dreams, constitution)
    external_signals = _load_external_signals(root)
    state = {
        "schema_version": SCHEMA_VERSION,
        "cycle_date": as_of.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "record_count": len(records),
        "external_signal_count": len(external_signals),
        "constitutional_guards": constitution.get("immutable_principles") or [],
        "authority_boundary": constitution.get("authority_boundary") or {},
        "hypotheses": hypotheses,
        "diversity_atlas": atlas,
        "unknown_unknowns": unknowns,
        "curiosity_queue": curiosity,
        "dreams": dreams,
        "experiments": experiments,
        "disagreement_observatory": disagreement,
        "lineage": lineage,
        "rule_review": rules,
        "multiple_selves": selves,
        "capability_report": capabilities,
        "negative_space": negative_space,
        "surprise_portfolio": portfolio,
        "external_signal_digest": [
            {"source": item.get("source"), "topic": item.get("topic"), "signal_type": item.get("signal_type"), "claim_status": item.get("claim_status")}
            for item in external_signals[:50]
        ],
        "production_files_modified": False,
        "requires_human_selection": True,
    }
    out = root / STATE_DIR
    _write(out / "LATEST.json", state)
    _write(out / "hypotheses.json", {"hypotheses": hypotheses})
    _write(out / "experiment_queue.json", {"experiments": experiments})
    _write(out / "diversity_atlas.json", atlas)
    _write(out / "negative_space.json", negative_space)
    _write(out / "lineage.json", lineage)
    _write(out / "rule_review.json", rules)
    _write(out / "capability_report.json", capabilities)
    _write(out / "disagreement_observatory.json", {"items": disagreement})
    _write(out / "multiple_selves.json", selves)
    (out / "BRIEF.md").write_text(build_brief(state), encoding="utf-8")
    return state


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    state = run_cycle(Path(args.root), dt.date.fromisoformat(args.date))
    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False))
    else:
        print((Path(args.root) / STATE_DIR / "BRIEF.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
