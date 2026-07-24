# System Diagnostic

Generated: 2026-07-24T15:03:22+00:00

Findings: 9 — priorities {"high": 1, "low": 1, "medium": 7}

## Action queue

### [HIGH] Visual-memory data exists without a reviewed-evidence action report
- Area: `visual_memory`
- Code: `visual_memory_unanalyzed`
- Evidence: {"decisions": {"approved": 38, "revise": 5, "unreviewed": 2223}, "records": 2266}
- Action: Run the visual-memory analyzer and commit its reviewed feedback cohorts and review queue.

### [MEDIUM] Permanent stock exclusion now has a measured supply signal
- Area: `asset_selection`
- Code: `stock_supply:insufficient_evidence`
- Evidence: {"exclusions": {"banned_ids": 102, "used_ids": 1021}, "fallback_rate": 0.0, "low_supply_rate": 0.0, "measurement_boundary": "Candidate decisions reflect narrative-fidelity reranking after search. This report cannot reconstruct every raw API result or prove that exclusions caused a missing candidate.", "reports_analyzed": 0, "scenes_analyzed": 0, "state": "insufficient_evidence"}
- Action: Persist candidate-decision reports for more completed renders before evaluating a cooldown. The exclusion-set size alone is not evidence of starvation.

### [MEDIUM] The evolution queue is flooded with taxonomy gaps
- Area: `concept_engine`
- Code: `evolution_taxonomy_gap_flood`
- Evidence: {"count": 55, "examples": ["awake-inside-the-dream", "belief-is-gravity", "can-you-fly", "can-you-fly-v3", "deepest-sleep", "dmt-customs", "dmt-loading-screen", "dmt-other-side-of-the-door", "dmt-the-understudy", "futures-fingerprints", "how-you-doing", "inner-search", "june-oxley-folks-aint-roadblocks-tier1", "june-oxley-left-the-vehicle", "message-from-your-future-20260716"]}
- Action: Separate legacy packages missing metadata from genuinely novel concepts before treating every uncataloged slug as a map failure.

### [MEDIUM] Stored feedback has been organized into provisional rule candidates
- Area: `learning`
- Code: `feedback_rule_candidates_ready`
- Evidence: {"candidate_count": 14, "top_candidates": [{"evidence_count": 13, "id": "effects_still_preference", "title": "Use a strong still with effects when stock cannot explain the beat"}, {"evidence_count": 6, "id": "caption_restraint", "title": "Do not print performance tags or dense paragraph captions"}, {"evidence_count": 5, "id": "character_lip_sync", "title": "Visible speaking character requires mouth movement"}, {"evidence_count": 5, "id": "dmt_motion_language", "title": "DMT videos benefit from psychedelic moving graphics in moderation"}, {"evidence_count": 5, "id": "stock_first_preference", "title": "Prefer genuine moving stock when a direct match exists"}, {"evidence_count": 5, "id": "visual_semantic_match", "title": "Visual must clearly represent the spoken concept"}, {"evidence_count": 3, "id": "title_safe_zone", "title": "Titles must remain readable inside platform crop zones"}, {"evidence_count": 2, "id": "deep_parallax", "title": "Concept backgrounds should use strong layered depth"}, {"evidence_count": 2, "id": "literal_action_accuracy", "title": "Literal actions must visibly perform the stated action"}, {"evidence_count": 1, "id": "cartoon_animation_definition", "title": "Animated requests mean coherent cartoon animation"}], "unique_commented_evidence": 124}
- Action: Review candidate scope and counterexamples. Promote only candidates with a human decision and a regression test.

### [MEDIUM] Too few reviewable videos have exported human feedback
- Area: `learning`
- Code: `human_feedback_coverage_low`
- Evidence: {"coverage": 0.2857, "feedback_count": 2, "feedback_slugs": ["belief-is-gravity", "the-edge-of-you-is-negotiable"], "reviewable_count": 7, "reviewable_slugs": ["a-chair-not-a-throne", "belief-is-gravity", "june-oxley-left-the-vehicle", "the-edge-of-you-is-negotiable", "the-emotion-scam-tier1", "the-reality-machine-dmt-v3", "who-wrote-the-menu"]}
- Action: Review the highest-value completed videos first. Keep automated risk tags as screening evidence until James supplies a decision.

### [MEDIUM] Some operational solutions still need verification
- Area: `operations`
- Code: `provisional_operational_solutions`
- Evidence: ["sol-animation-contract-preflight-v1", "sol-hero-readiness-v1"]
- Action: Satisfy each stated verification requirement before marking it verified; do not promote by elapsed time alone.

### [MEDIUM] Youtube queue contains already-published videos
- Area: `publishing`
- Code: `youtube_published_still_queued`
- Evidence: ["the-edge-of-you-is-negotiable", "the-forecast-in-your-chest", "the-museum-that-repaints-itself", "the-person-you-replaced", "the-press-secretary-in-your-skull", "the-reality-machine-dmt-v3", "who-wrote-the-menu", "you-are-a-flame-wearing-a-name-tag"]
- Action: Keep the metadata queue if useful, but rely on durable receipt checks and make duplicate posting require an explicit force flag.

### [MEDIUM] Quality warning repeats: low_bitrate
- Area: `quality`
- Code: `repeated_quality_warning:low_bitrate`
- Evidence: {"current_build_reports": 2}
- Action: Run a targeted encoding or assembly challenger and require unchanged visual/audio quality before adoption.

### [LOW] The WhisperX challenger has no materialized benchmark ledger
- Area: `alignment`
- Code: `whisperx_ledger_absent`
- Evidence: "pipeline/whisperx-benchmark-ledger.json is absent"
- Action: Run shadow alignment on eligible successful videos and add the first manually reviewed timing references before considering promotion.

## Authority boundary

This diagnostic may propose or apply deterministic infrastructure safeguards. It cannot rewrite narration, change science or political meaning, alter James's approved visual intent, publish, or promote experimental systems without the relevant approval gate.
