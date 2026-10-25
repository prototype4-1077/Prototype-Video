# Pipeline maintenance — October 25, 2026

This update targets reliable, literal, reviewable videos and evidence-aware
learning. It does not change James's narration, approve an output, or start a
production video. The active repository is prototype4-1077/Prototype-Video.

## Installed changes

- Enforce the standing 35% still-derived runtime ceiling in preflight and runtime.
  Packages may tighten the limit but cannot raise it. Source provenance overrides
  a misleading video label. Blender keyframe composites count as still-derived;
  they remain procedural graphic inputs rather than fabricated photographic
  stock references.
- Keep supplied MP3 narration byte-for-byte, including short/small recordings.
  Missing or checksum-mismatched supplied audio blocks rather than invoking TTS.
- Apply literal/mechanism relevance checks through the ending and to cached or
  pinned footage. Concrete visual anchors take priority over abstract caption
  words. A stock_ok label or human role cannot lower the 18% matching floor.
  Metadata coverage remains screening evidence, not proof of a correct frame.
- Preserve the rejected-candidate audit and narration fingerprint. Generation
  failure cannot quietly relax the scene into mood footage or plain 2D filler.
- Repair the enhanced-still disk/in-memory handoff so a successful generated
  visual and its provenance are not overwritten by the caller's stale scene.
- Store render outcomes by run/attempt/process in governor-history; latest
  summaries remain compatible. Future successful retries retain prior failures.
- Enforce explicitly exact final durations within 0.5 seconds, separately from
  automatically estimated narration duration. Supplied audio is not altered.
- Keep the manual assembly path consistent with the manifest: one canonical
  YouTube output by default, with alternate canvases/music only on request.
- Run external sensing through native Python GitHub/RSS collectors. Agent Reach
  is optional; packaging failures no longer stop the radar. Each source has a
  health outcome, provenance link, and unverified/reference-only classification.
- Separate authenticated retention snapshots from public-count refreshes.
  Public updates preserve older retention without inventing a collection date.
- Persist collector failures before failing Actions. Empty, partial, missing-key,
  and successful collections have distinct outcomes. Disabled OAuth clients get
  an explicit repair instruction rather than another blind token refresh.
- Upgrade intelligence recommendations: missing measurements remain unknown,
  stale/undated/very low-view evidence does not steer current recommendations,
  small cohorts are regularized and described as provisional associations, and
  frontier exploration is labelled editorial rather than a predicted winner.
- Distinguish video-level approvals, scene feedback, and new taste embeddings.
  An approved video with no new embeddings is reported honestly.
- Refresh diagnostics after render/analytics/radar completion, including failed
  workflows. Reports now inspect collector health/freshness as well as coverage.
- Add a read-only ElevenLabs credential probe without generating audio, storing
  account/billing data, or claiming it establishes TTS permission or media quality.
- Pin the updated core workflow actions to verified Node-24-native release SHAs.
  The exact releases are recorded in action_versions.json.

## Verification

Local regression suites cover pipeline media/learning, the intelligence stack,
and the Concept Engine. New regressions exercise source-policy bypasses, exact
narration preservation, late/pinned footage checks, failed-then-successful render
history, exact durations, partial collections, namespace-aware RSS, missing versus
zero retention, stale evidence, and approval scope.

A real-media smoke test renders generated test patterns and a tone through
caption/title preparation, scene assembly, selected DMT music, final mixing, and
full MP4 decoding. It verifies one native 1920x1080 H.264/AAC master with Deep
Portal and a matching manifest. This is a technical fixture, not a content or
voice-quality approval.

A live native-radar exercise collected 36 public GitHub release records. Both
configured RSS feeds responded successfully with no current entries. Optional
YouTube search was unavailable locally because yt-dlp was not installed, and that
limitation is recorded. No research claim is promoted automatically.

## Remaining external dependency

The latest public-statistics response reports disabled_client: the Google OAuth
client has been disabled. Repository code cannot re-enable that Google client or
replace account authorization. YouTube retention requires a working grant with
YouTube Analytics read access; public statistics can alternatively use YT_API_KEY.
Until this is repaired, the intelligence report excludes missing/currently
unsupported retention from winning-lane recommendations.

At this audit, 23 catalog videos joined to audience data: 12 had no retention
measurement and 11 had stale or undated retention. None was eligible to establish
a current winning lane. Existing human approvals and historical measurements
remain intact and explicitly scoped.

This upgrades the evidence, reliability, and decision logic. It does not retrain
a foundation model or promote a replacement voice/vision model without a live
quality benchmark. The learned taste model remains compatible with its existing
512-dimensional embeddings. Promptfoo fixtures remain offline contract tests.
