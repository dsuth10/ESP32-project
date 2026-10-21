# Image feature implementation record

21 October 2026 — development candidate

## Isolation and preservation

The user authorised implementation and requested a new feature branch while leaving the live device on the original baseline. `codex/companion-media-agent` was created from `main` at `e98b7bc7831d49a283104c1b41215843b684492a` in a separate managed worktree. The existing companion/History/assistant source and research documents were copied into the feature checkout with SHA-256 comparison. User credentials, databases, logs, firmware configuration and unrelated Graphify changes were excluded. The original source files remain byte-identical to that preservation manifest; only the separately requested Hermes skill was added to the original checkout.

## Implemented candidate

- `media_store.py`: separate media schema v2 SQLite, validated content-addressed PNG/JPEG/WebP blobs, immutable versions and parent lineage, literal Unicode search, explicit canonical naming, ordered outbox, remote-event deduplication, conflict recording/resolution, local-only prompts/jobs and verified no-overwrite backup/restore. The text History schema remains v1 and is not migrated.
- `media_library_server.py` and `media_sync.py`: authenticated private API, strict metadata allowlist, verified/size-bounded blob transfer, durable event identity and revision checks, two-cache convergence, explicit canonical conflicts, shared atomic AUD allocation reservations, HTTPS-only remote client URLs, cancellation and closed database/HTTP connections. The GUI sync worker resumes automatically when configured.
- `media_service.py` and `media_providers.py`: Groq-primary bounded intent interpretation, library-first lookup, explicit Commons search/import with rights acknowledgement, OpenAI generation/refinement adapter, durable preparation/dispatch/preview states, pre-dispatch held allocation and no automatic replay of ambiguous paid requests.
- `media_panel.py`: image library, previews/version selection, canonical approval, queue/copy/export, conversational/PC-speech requests, job review, backup/restore and conflict resolution. Generated images require preview before insertion. Canonical approval and insertion remain separate actions.
- `media_targets.py`: Word embedding with document/caret/selection guards; OneNote guarded clipboard handoff with manual-copy fallback. Insertion receipts distinguish an Office picture object from a requested paste and from actual teacher acceptance.
- `media_voice_bridge.py` and opt-in receiver integration: authenticated loopback transcript handoff into durable local jobs; existing text paths remain available. Feature receiver ports and application-instance identity are distinct from production.
- `companion_settings.py`, `settings_panel.py` and preview launch/setup/package scripts: local masked setup, Windows user-bound encrypted credentials, isolated feature data, inputs disabled by default and an allowlisted source preview with a hash manifest.
- `.agents/skills/hermes-collaboration/`: reusable authenticated Hermes workflow, immutable request identities, endpoint/credential-bound retries, status/events, exact one-time approval handling, run-specific stop and documented connection lessons. Installed in the original project directory too, with runtime endpoint/credential kept ignored.

## Verification

The final integrated command `python -m pytest tools/compose/tests tests server/tests -q` passed **164 tests**. The Hermes client's separate offline suite passed **9 tests**, and the skill validator passed. The source preview builder verified every archived file against its SHA-256 manifest; its privacy test injected unique fake secrets into excluded files and confirmed their absence from the archive. Native previews were rendered and checked at 920 × 740 and 720 × 640 with synthetic data; queue/clear refresh and small-window metadata/control visibility were repaired and rechecked. Windows DPAPI passed an actual synthetic encrypt/decrypt round trip without accessing user secrets.

A new hidden Word instance embedded a synthetic image through the actual COM adapter, saved a DOCX containing one embedded media item and reopened with one picture. The harness bound that private instance directly; it did not access an existing user document and is not physical foreground/caret acceptance.

Using the new skill, Linux Hermes verified source hashes and ran the portable server suite. The first environment lacked Pillow and correctly skipped image validation. A deliberately separate development task provisioned a disposable virtual environment with Pillow 12.3.0 and ran **4 tests, 0 failures, 0 errors, 0 skips** on Python 3.14.7. Tool events and runtime receipts identified the existing Luna model. Only isolated development files/dependencies were created; Hermes configuration and live services were not changed. The relevant source/test hashes and private run receipts are retained locally.

## Remaining acceptance and programme

This is an implemented image-workflow candidate, not a declaration that the full product programme is finished. Required next gates are live Word and OneNote placement/selection/undo/save-reopen, physical PC/handheld speech, a private Linux deployment with persistent storage/backup, two actual Windows hosts across home/work connectivity, and explicitly authorised paid image quality/cost evaluation. No provider account was charged for image generation in this work.

Later agreed increments remain PowerPoint, audio/video, runtime firmware customisation, deeper agent administration, isolated development-worker updates, signed installation, accessibility/school pilot, licensing/provenance and public distribution. The original firmware and main branch remain the rollback baseline. See [the testing guide](feature-media-testing.md) and [master plan](2026-10-21-companion-media-agent-master-plan.md).
