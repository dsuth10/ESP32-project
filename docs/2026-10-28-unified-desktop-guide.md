# Classroom Companion: shared teacher window

28 October 2026. Local feature candidate, not a stable release or classroom
acceptance. See the [implementation plan](2026-10-28-unified-desktop-plan.md).

## Open the application

Double-click **start_companion.bat** in this checkout. It now opens one teacher
window with **Teaching Board** and **Voice companion** workspaces. The existing
pupil presentation remains a separate optional window.
Close older standalone Board/voice windows before the first shared launch with
the same lesson/profile.

Normal launch checks installed dependencies without installing packages,
downloading models, changing firmware or deploying services. It uses the
isolated Qt environment and reuses a locally installed compatible voice Python
when necessary. To check dependencies without opening a window or listeners:

```powershell
& tools/compose/run_unified_desktop.ps1 -CheckOnly
```

If dependencies are missing, explicitly prepare the isolated environment:

```powershell
& tools/compose/setup_unified_desktop.ps1
```

Setup requires Python 3.12/3.13 and package-index access. It prepares the existing
checkout-local `.local/teaching-board-renderer-env`, then adds the declared voice
dependencies there. It does not modify the system Python, stable companion data,
lesson files, protected credentials or firmware. A dependency failure preserves
user data; rerun setup after resolving access/package problems.

## Two independent workspaces

**Teaching Board** retains the existing editor, lesson saving/copies, Undo/Redo,
Freeze/Resume, pupil display controls, typed/PC-microphone Board requests,
reusable resources, profiles, chart data, request recovery, portable lessons
and PDF export. Switching teacher tabs does not change the pupil page or its
Freeze snapshot. The pupil window can remain on the projector while the teacher
uses private companion controls.

**Voice companion** retains Compose & Dictate, Ask/Manage, separate Hermes tasks,
History & saved text, Image library and Settings. Its microphone controls still
target its writing/image workflows; they are not Board commands. Existing Office
target checks, queues, image previews, paid-attempt decisions and recovery remain.

One workspace can record from the PC microphone at a time. Finish the recording
in that workspace before starting the other. No transcript is forwarded between
them. The teacher shell and pupil display are excluded from the voice companion's
external document targets.

**Open saved lessons** selects a saved lesson and opens it in the same Board
workspace, retaining the companion. Resume first when the pupil view is frozen;
finish active Board work and save before switching. **File → Open saved lessons
folder (recovery)** retains the older folder-based standalone launch entries.
Those entries intentionally open the standalone Board. The application prevents
a second editor from owning the same lesson, including after Save a copy/import
or switching saved lessons.

## Data and settings

The default lesson remains `.local/teaching-board-candidate/review`. The voice
companion uses the existing `%LOCALAPPDATA%/ESP32ClassroomCompanion-Feature`
profile, or an explicit feature-profile override. Lesson files, reusable
resources, History, image jobs and protected settings are not merged or migrated.

Voice Settings controls the voice workspace. The Board remains local-only by
default. To use an explicitly selected existing feature configuration for Board
requests, supply its protected settings folder when launching:

```powershell
& tools/compose/run_unified_desktop.ps1 -BoardSettingsRoot '<feature settings folder>'
```

The Board loads that selected configuration at launch; later voice Settings edits
do not silently reconfigure a running Board. Close and relaunch with the selected
profile when you want the Board to load updated settings. Do not pass credentials
as arguments or copy Windows-protected credentials between computers.

Other optional launcher arguments are `-DataRoot`, `-CompanionDataRoot`,
`-LibraryRoot`, `-PythonExecutable`, `-CompanionPythonExecutable` and `-Demo`.
Lesson roots retain the existing reserved-candidate-folder validation. Demo
requires a fresh lesson folder. Stable companion storage and overlapping
lesson/companion folders are rejected.

## Closing and recovery

Close the teacher window or choose **Save and close**. The shell saves/checks the
Board and asks the voice runtime to prepare closure before either is torn down.
Active recording, requests or settings writes can keep the application open.
Queued text requires a deliberate Discard or Cancel choice; cancelling retains
it. Queued images retain their existing durable restart behaviour. A remote
cancellation request or a closed window is not proof of a remote task ending.

If the companion fails to start, the Board stays available and an explicit retry
is offered. An existing live child cannot be duplicated. A recoverable host
connection failure can release the voice controls into their standalone window;
the implementation never force-kills active work simply to hide a window.
Normal detach recovery was checked locally. Hard process termination, Windows
session termination and power loss retain a separate recovery acceptance gap.

Standalone recovery launchers remain:

- Voice only: **start_companion_feature.bat**.
- Board only: **tools/compose/run_teaching_board_candidate.ps1**.

Close the shared application before using a standalone route with the same
profile/lesson. Source-preview install/update/rollback/removal remain available;
see [installation](companion-installation.md).

The provisional Board's lesson/resource data and Qt runtime are per checkout or
installed source release. A source-preview update does not automatically move
them into the new release. Retain the previous release, export/back up lessons
before updating and use deliberate portable import or rollback. Automatic Board
continuity across installed updates remains an open packaging acceptance gate.

## Verification and remaining acceptance

The implementation plan records exact automated and native results. Tests use
synthetic lesson content and local-only disposable voice data; no real audio,
provider call, firmware write or deployment is required for these checks.

Manual acceptance remains for normal Word/OneNote paste/focus, physical handheld
input, microphone quality, Tk file/message dialogues, keyboard navigation,
Windows scaling, pen/touch, projector/second-display use and a lesson rehearsal.
Existing remote deployment, image-cost/quality, signed-installer and classroom
gates remain separate.
