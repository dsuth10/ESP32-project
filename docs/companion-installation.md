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

Open **Start Companion Feature.cmd** in the installation folder. On the first
installation, run `setup_companion_feature.bat` inside the current release folder
to create its Python environment and install dependencies. This separately
requires network access and may need school IT approval. Setup is not run by the
package tool. Python 3.12 or 3.13 and the requirements file remain prerequisites.

The feature launcher uses separate data at
`%LOCALAPPDATA%/ESP32ClassroomCompanion-Feature`. Hardware inputs default off;
receiver and discovery ports differ from the production companion. Changing
Hermes or media settings never enrols a computer in Tailscale or deploys Linux.

## Update, rollback and removal

Install a newer preview with the same command and destination. Source releases
are retained separately and the launcher switches only after full verification.
If managed source files have local edits, update stops and preserves them.
Back up those edits before proceeding. Settings, History and media live outside
the installed source tree.

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
