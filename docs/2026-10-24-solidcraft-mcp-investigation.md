# SolidCraft enclosure and MCP investigation

24 October 2026. The initial investigation below was research only. The subsequent user-installed 0.21.0 application has now been connected and tested through MCP; see the [pilot verification record](dimensions/solidcraft/README.md). No firmware, board registration or existing enclosure files were changed.

## Recommendation

Install the Windows x64 desktop release for a bounded enclosure pilot. SolidCraft provides an editable sketch/feature/parameter workflow suited to small dimension changes by the user and modelling through MCP. Preserve the existing Blender/STL designs and establish a new native parametric model from the recorded dimensions.

Use the upstream [stable v0.21.0 release](https://github.com/tangency-labs/solidcraft/releases/tag/v0.21.0), released today, rather than a nightly. Its native design format is 34 and cannot be opened by 0.20.0 or older. The website's static [download inventory](https://solidcraft.io/download/) still advertises v0.12.0 and says its saved package details were checked on 15 October; prefer upstream release assets.

For this x64 Windows computer, use [solidcraft-0.21.0-windows-x64.msi](https://github.com/tangency-labs/solidcraft/releases/download/v0.21.0/solidcraft-0.21.0-windows-x64.msi). The upstream [asset inventory](https://github.com/tangency-labs/solidcraft/releases/expanded_assets/v0.21.0) lists SHA-256 `c19f8d531ec11097a47f500c0eb3c3b4888183f2226af778c267c6efc9a7511f`. The EXE and portable ZIP are alternatives. The upstream [README](https://github.com/tangency-labs/solidcraft) says downloads are currently unsigned. This investigation has not independently verified a downloaded package or publisher signature.

## Capabilities and migration

The [version-pinned capability inventory](https://github.com/tangency-labs/solidcraft/blob/v0.21.0/docs/capabilities.md) describes constrained sketches, unit-aware parameters/configurations and an editable feature timeline, including extrude, fillet/chamfer, shell, holes, patterns, mirror and combine. It explicitly calls the software early but usable for simple parts; its reference checks do not establish complete geometric or workflow equivalence.

The [format inventory](https://solidcraft.io/features/) distinguishes native `.solidcraft` history from STEP geometry and mesh bodies. STEP imports become base geometry and do not recover another CAD application's feature history. Existing STL/OBJ meshes will not automatically become a useful editable enclosure history. Reconstruct the enclosure with named dimensions, using the original board STEP as a possible reference after import/scale checks.

Local starting evidence is `generate_case_battery_only.py`: PCB 50 × 86 × 1.6 mm, wall 2 mm and lateral clearance 0.4 mm per side. These are recorded generator inputs, not fresh physical measurements. The repository contains Blender assemblies, separate upper/lower STL parts and `docs/dimensions/3d_model/ES3C28P_3D/ES3C28P_3D.step`.

## MCP connection to the visible desktop

The [v0.21.0 MCP instructions](https://github.com/tangency-labs/solidcraft/blob/v0.21.0/docs/mcp.md) specify local STDIO MCP through `solidcraft-cli.exe`. The Windows installer places the CLI beside the application in `C:\Program Files\SolidCraft`. For the visible application, explicitly launch `solidcraft.exe --control 7878`, then run the MCP server with `mcp --connect 127.0.0.1:7878`. Without `--connect`, this release starts a separate headless design session. The server supports inspecting/measuring geometry, changing parameters, executing modelling commands, saving/exporting and screenshots.

Version matters: the current online guide describes automatic discovery/default port 27878, whereas the pinned stable instructions above use an explicit control port. Verify the installed executable's help before using newer online instructions.

The [control protocol](https://github.com/tangency-labs/solidcraft/blob/v0.21.0/docs/control-protocol.md) binds to loopback and authenticates connections with a per-launch token restricted to the Windows user. Keep the connection local. The MCP server supports `--allow-path`; allow only a dedicated enclosure workspace, not the entire repository or private `.local/` material. Never print the token.

Codex supports local STDIO servers in its [official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). The proposed configuration below combines the documented Codex format with SolidCraft's pinned invocation; this combination remains unconfigured and untested:

```toml
[mcp_servers.solidcraft]
command = 'C:\Program Files\SolidCraft\solidcraft-cli.exe'
args = ["mcp", "--connect", "127.0.0.1:7878", "--allow-path", '<absolute dedicated enclosure folder>']
```

Replace the placeholder only after creating and selecting the workspace. Confirm both executable paths after installation.

## Pilot acceptance

1. Confirm installed version and CLI; connect to a disposable native design in the visible app.
2. Create a constrained, parameter-driven base and lid; inspect dimensions and feature errors.
3. Change one named clearance/wall parameter manually, then through the agent; verify the same file and model rebuild correctly.
4. Save, close and reopen the native design, then export upper/lower STEP and STL separately and check dimensions and solid/mesh validity.
5. Migrate ports, fasteners, screen and battery clearances from the existing evidence. A printed fit test on the actual S3 remains necessary before claiming physical enclosure acceptance.

At the initial research checkpoint, installation, live MCP control, saved-model roundtrip, exported geometry and physical fit were unverified. The subsequent [pilot record](dimensions/solidcraft/README.md) establishes the first four locally; native Codex tool discovery after restart, the user's manual edit and physical fit remain open.
