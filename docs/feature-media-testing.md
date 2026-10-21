# Image companion feature: testing and recovery

21 October 2026

This is an implementation candidate on `codex/companion-media-agent`, in an isolated managed checkout. The original checkout remains on `main`; no firmware was built or flashed and no feature service was deployed. The first release follows the agreed image workflow. Audio/video, PowerPoint, runtime handheld customisation and public distribution remain later milestones in the [master plan](2026-10-21-companion-media-agent-master-plan.md).

## Start the feature preview

From this feature checkout, run `start_companion_feature.bat` (or `start_companion.bat`, which routes to it). It uses `%LOCALAPPDATA%\ESP32ClassroomCompanion-Feature` for its data, a distinct application-instance mutex, and defaults hardware hotkeys and receiver startup off. It does not copy production credentials, change the original launcher, or open the live History database.

Python and the companion requirements are needed. On another Windows computer, `setup_companion_feature.bat` creates a feature-local virtual environment and installs `tools/compose/requirements.txt` before launching. This is a source preview setup, not a signed installer or bundled Python distribution. School-managed installation permissions and dependencies still need testing. An existing compatible Python environment can launch directly.

Open **Image library**, import a teacher-owned PNG/JPEG/WebP, inspect the preview, and choose **Keep named version**. Earlier versions remain available in the version selector. **Queue for Paste Ready** retains the image until a deliberate destination gesture. **Copy image** and **Export image** support a manual application handoff. The **Library tools** menu creates verified backups, restores into a new folder and reviews interrupted attempts. Backups contain local media prompts/jobs; treat them as private. They do not contain text History or provider credentials.

## Agent and generation workflow

The media request box uses the embedded Groq assistant when configured, or the selected Ollama endpoint under local-only policy. It can find saved assets, prepare an image or refinement, keep a selected version, queue an insertion, and request an explicitly external search. Media interpretation is retained in local History only when its existing retention control is enabled. Document identity and caret data are not sent to the model.

Image requests first become durable preparations. **Generate prepared image** dispatches one attempt only after Settings enables generation and supplies the image key, model, conservative AUD allocation and shared budget service. A new generation previews before insertion; refinements create immutable child versions. Choosing a canonical version does not insert it. The image provider adapter uses the documented OpenAI generation/edit endpoints; no live image-provider call or paid quality evaluation has been performed. Its current model default was checked against [official image documentation](https://developers.openai.com/api/docs/guides/image-generation).

The Linux ledger coordinates a default A$30 monthly design allowance across clients. Allocation amounts are conservative estimates, not invoice amounts or currency conversions. An allocation becomes held before provider dispatch. Ambiguous dispatches are never automatically retried or released. Review the provider account and library, then use **Review selected job** to close an uncertain attempt while retaining its allocation. A fresh attempt is a deliberate new request.

## Word and OneNote

For Word, focus the intended document with a collapsed caret and press Paste Ready. The adapter verifies foreground HWND/process, active document and caret before embedding an independent picture. A PC-microphone request to insert a uniquely matched saved image can use the original Word target only if those checks still match; otherwise it remains queued. Typed requests from the companion and handheld transcripts queue for a fresh destination gesture.

OneNote uses a guarded clipboard-paste adapter. It requires an identifiable OneNote desktop target and a collapsed selection verified through UI Automation. If that check is unavailable, use **Copy image** and paste manually. A paste receipt reports that a shortcut was sent; it does not claim OneNote saved or embedded the image. OneNote caret, selection, undo and save/reopen behaviour remain acceptance gates on the actual installed edition. Word's real COM embedding and save/reopen have been checked in an isolated synthetic document; live foreground/caret behaviour still needs user acceptance.

## Private sync and hardware tests

Configure the separate media service using [the server guide](media-sync-server.md). Its token is separate from the Hermes API key. Settings encrypts Windows credentials for the current user. Automatic sync transfers validated image bytes, version metadata and explicit canonical choices, excluding History, prompts, credentials, settings and job records. An unavailable server leaves cached assets usable and prevents paid jobs requiring shared budget authority. Conflicts are displayed; preview the intended version and **Keep named version** to resolve a competing canonical choice explicitly.

Windows loopback tests exercised two independent desktop stores. Linux Hermes verified exact supplied source hashes and ran all four portable server tests in a disposable Python 3.14.7 environment with Pillow 12.3.0. This does not establish deployment or two actual Windows computers over a home/work route. Tailscale/private HTTPS, persistent storage, backup and service ownership still need deliberate configuration and verification.

Enable feature hardware inputs only when ready. Close the production companion or use a separate Windows computer before enabling the same global shortcuts: a second handheld alone does not isolate Windows hotkeys. The feature receiver uses TCP 8788 and discovery UDP 8789 by default; the original receiver is left alone. A feature-owned receiver passes transcripts through an authenticated loopback bridge to durable media jobs. It does not call a second agent or mirror these media requests to Telegram. Physical handheld audio/transcription and PC-microphone acceptance are still required.

## Evidence and rollback

Automated checks cover old writing/History/assistant behaviour, image validation and version integrity, conflicts, budgets, retry uncertainty, focus guards, protected settings, voice handoff and source-package privacy. Native Tk previews passed at 920 × 740 and 720 × 640. See [the implementation record](2026-10-21-media-feature-implementation.md) for final counts and remaining gates.

To leave the preview, close its window and keep using the original `main` checkout and device. No merge, push, firmware flash, production database migration, live service deployment or paid image generation is part of this checkpoint. Restore a media backup into a new folder, never over an active library. Source previews can be generated with `python tools/build_companion_preview.py --output <new-preview.zip>`; the allowlist excludes credentials, databases, virtual environments, logs and firmware binaries. Public licensing/provenance and signed packaging remain release work.
