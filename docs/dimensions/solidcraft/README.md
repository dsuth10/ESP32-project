# SolidCraft enclosure workspace

24 October 2026. SolidCraft 0.21.0, Windows x64.

Open `ESP32-S3-enclosure-pilot.solidcraft` for the editable model. It contains
separate **Case base** and **Case lid** bodies, two fully constrained sketches,
and seven timeline features. The lid is displayed 12 mm above the tray.

This is a connection and parametric modelling pilot. It has no screen opening,
USB/SD/button apertures, mounting bosses, battery restraint or lid fastening.
Its 18 mm base height is provisional. It is not a print-ready replacement for
the established enclosure.

## Make a small edit

Open **Change Parameters** and change `base_height` from `18 mm` to `20 mm`.
The base should grow and the lid should move up by 2 mm. Restore `18 mm` or undo
when finished. `clearance`, `wall`, `corner_radius` and `lid_thickness` are also
named user parameters. `outer_width` and `outer_length` are derived expressions.
Keep the native `.solidcraft` file for future edits; STEP/STL files carry geometry.

The dimensions start from the existing generator: board 50 × 86 mm, 0.4 mm
clearance per side and 2 mm walls. This gives an external footprint of
54.8 × 90.8 mm. These inputs have not been physically remeasured in this task.

## MCP connection

The Codex MCP server `solidcraft` is registered and enabled in the user's global
configuration. It runs Python 3.13 and `tools/cad/solidcraft_mcp_launcher.py`.
The launcher connects to `127.0.0.1:7878`; if absent, it opens a SolidCraft window
with `--control 7878`. This is a separate window from an ordinary shortcut launch.
The bridge authenticates using SolidCraft's own per-launch token and explicitly
allows this folder. SolidCraft additionally allows its recovery/scratch folders
and the current design's folder under its documented rules. Do not open a private
design in the agent-controlled window. No tokens are stored in this repository.

Restart Codex once to load the newly configured server into its native tool list.
This task already verified actual MCP calls through a local diagnostic client;
native tool discovery after the restart remains to be checked.

Reproducible diagnostic client:

```powershell
& C:/Python313/python.exe tools/cad/solidcraft_mcp_client.py docs/dimensions/solidcraft/connection-check.json
```

`pilot-build.json` only builds into a verified empty design. It refuses to start
when the design contains work. Do not replay `pilot-check-save.json` over edited
work: it is the original save/export/reopen acceptance sequence and uses fixed
pilot filenames. The current native model is already saved.

## Verified locally

| Check | Result |
| --- | --- |
| MCP initialise and live window inspection | Passed; server 0.21.0 |
| Sketch constraints | Both solved with zero degrees of freedom |
| Feature history | Seven features; no errors or warnings after reopening |
| Clearance 0.4 → 0.6 → 0.4 mm | Both bodies rebuilt; footprint 54.8 × 90.8 → 55.2 × 91.2 → 54.8 × 90.8 mm |
| Native save/reopen | Passed; parameters and sketches retained |
| STEP export/reimport | One solid per file; dimensions preserved |
| STL exports | One watertight component each; consistent winding |
| Model preview | `pilot-preview.png`, rendered through the connected app |

Analytic volumes for rounded rectangles, external radius 6 mm and internal
radius 4 mm: base 18,677.5843 mm³ and lid 9,889.8747 mm³. Native measurements:
18,677.5228 mm³ and 9,889.8341 mm³ (each within 0.001%). STEP reimports measured
18,677.4651 mm³ and 9,889.8503 mm³. STL tessellation measured 18,679.4838 mm³ and
9,889.5093 mm³ (within 0.02%).

The original failed lid batch rolled back because its generated body was named
`Body2`, not `Body1`; the corrected lid-only batch succeeded. Existing enclosure
files, the firmware, board registration and `main` were not changed.

## Still unverified

- Native MCP tool discovery after restarting Codex.
- User's own manual dimension edit and preferred workflow.
- Detailed enclosure migration, connector/battery/fastener clearances and printed fit.
- Physical application and classroom acceptance; CAD checks do not close those gates.

Sources: [pinned SolidCraft MCP guide](https://github.com/tangency-labs/solidcraft/blob/v0.21.0/docs/mcp.md),
[control protocol](https://github.com/tangency-labs/solidcraft/blob/v0.21.0/docs/control-protocol.md),
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
