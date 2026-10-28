# Install and recover the isolated desktop preview

This is a Python source preview for local evaluation. It is not a signed public
Windows installer. Main and the installed ESP32-S3 firmware remain the reference.
Close the feature app before updating, rolling back or removing installed files.

## Build and verify

From the feature checkout:

```powershell
python tools/build_companion_preview.py --output .local/companion-preview.zip
python tools/companion_package.py install --package .local/companion-preview.zip
```

The default install folder is `%LOCALAPPDATA%/ESP32CompanionFeature`.
Use `--destination` for a disposable test location. Every archive entry and
SHA-256 digest is checked before extraction. Unlisted files, traversal paths,
symlinks and Windows path collisions are rejected. Hash verification establishes
internal integrity; download authenticity and code signing remain release gates.

Open **Start Companion Feature.cmd** in the installation folder. Current packages
open the shared teacher window and a separate pupil presentation window. On the
first installation, run `tools/compose/setup_unified_desktop.ps1` inside the
current release folder to prepare its isolated Board and voice dependencies. This
requires network access and may need school IT approval. Setup is not run by the
package tool. Python 3.12 or 3.13 and the requirements files remain prerequisites.
See the [shared-window guide](2026-10-28-unified-desktop-guide.md). The existing
`setup_companion_feature.bat` and `start_companion_feature.bat` remain voice-only
recovery routes; the standalone Board launcher is retained too.

The feature launcher uses separate data at
`%LOCALAPPDATA%/ESP32ClassroomCompanion-Feature`. Hardware inputs default off;
receiver and discovery ports differ from the production companion. Changing
Hermes or media settings never enrols a computer in Tailscale or deploys Linux.

## Update, rollback and removal

Install a newer preview with the same command and destination. Source releases
are retained separately and the launcher switches only after full verification.
If managed source files have local edits, update stops and preserves them.
Back up those edits before proceeding. Voice settings, History and image media
live outside the installed source tree. The provisional Board still stores its
lessons, saved-lesson catalogue, reusable resources and Qt environment under each
checkout/release's `.local` folder. Updating a source preview selects a new
release folder; it does not migrate that Board data or environment. The old
release/data remains available for rollback or deliberate portable lesson export
and import. Automatic Board continuity across installed updates is not accepted;
back up/export lessons before updating. Signed unified installation and stable
external Board storage remain release work.

```powershell
python tools/companion_package.py rollback
python tools/companion_package.py uninstall
```

Rollback selects the previous verified source release; it does not migrate or
revert user databases. Removal deletes only unchanged managed source files and
the generated launcher, retaining extra files (including locally installed
dependencies), older release residue and all separate user data. Inspect the
reported remaining-file count before any deliberate manual cleanup.
Never remove a folder merely because its name looks disposable.

Local fixture tests cover install, update, rollback, tamper rejection, unsafe
archives and preserved user files. Installed application launch, accessibility,
school permissions, signed packages and two-location teacher acceptance remain
separate checks in the master programme.
