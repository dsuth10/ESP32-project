# Detailed build guide

[Back to the project overview](../README.md)

This walkthrough uses Windows PowerShell for the main examples. Linux/macOS differences are noted where relevant. Start with the firmware and Bluetooth connection; enclosure editing and voice can be added independently.

The guide was checked against repository commit `a4f9bd9` on 2 October 2026. Documentation checks were performed; this revision of the guide has not been physically tested on another builder's board.

## 1. Install the tools

| Tool | Needed for | Check |
|---|---|---|
| Git | Downloading and tracking the project | `git --version` |
| PlatformIO Core | Compiling and uploading firmware | `pio --version` |
| Cursor or local Codex | Reading, editing and running project commands with an AI agent | Open the repository and verify terminal access |
| Python | Voice receiver and supporting scripts | `python --version` |
| Blender | Editing enclosure models | Open a supplied `.blend` file |
| uv / uvx | Launching the Blender MCP server | `uvx --version` |
| Slicer | Checking and preparing printed parts | Open a supplied shell STL |

Install PlatformIO using its [official installation instructions](https://docs.platformio.org/en/latest/core/installation/index.html). The VS Code PlatformIO extension is another route. If your IDE cannot use the extension, PlatformIO Core still works in its terminal. Reopen the IDE after installing command-line tools so it can find them.

For Blender work, use a version that supports the repository's scripts: they use the Blender 4.x-style `bpy.ops.wm.stl_export` operator. Match the add-on to your Blender version using the [Blender MCP project](https://github.com/ahujasid/blender-mcp).

For a reproducible setup, record the exact versions you installed, including Blender and its MCP add-on/server. The firmware's PlatformIO platform is not pinned in this repository, so a future toolchain update may need compatibility work.

## 2. Open the repository and give the agent context

Clone the project and create your own working branch:

```bash
git clone https://github.com/dsuth10/ESP32-project.git
cd ESP32-project
git switch -c my-classroom-companion
```

Open this folder in Cursor or run local Codex with this folder as its working directory. Use an agent mode with file and terminal access under your normal permission settings.

Useful files to give the agent:

| File | Purpose |
|---|---|
| `platformio.ini` | Board memory settings, build environments and USB ports |
| `GEMINI.md` | Engineering rules and known regression risks |
| `src/main.cpp` | Setup, touch events, serial commands and main loop |
| `src/macropad_config.cpp` | Profile names, labels and shortcut actions |
| `src/gui.cpp`, `src/ui_layout.h` | Screen drawing and orientation |
| `src/wifi_config.h.example` | Firmware network configuration template |
| `server/hermes_voice_receiver.py` | Host receiver, transcription and AI routing |

A useful initial prompt:

> Inspect these files and identify the build target, required local configuration and serial port. Run read-only tool checks first. Build the existing portrait firmware before proposing changes. Report actual command results and distinguish software checks from hardware tests I need to perform.

The local agent needs access to the machine that owns the USB port. If your IDE is connected to a remote workspace or WSL, its terminal may not see Windows COM ports. The simplest arrangement is to build and flash from Windows on the computer with the board attached.

## 3. Connect the board, build and upload

### Identify the USB port

1. Connect the board with a USB data cable.
2. Run `pio device list` and compare the list with the board disconnected.
3. On Windows, check **Device Manager → Ports (COM & LPT)**. On Linux/macOS, use the path reported by PlatformIO.
4. Replace the repository's `COM5` in both `upload_port` and `monitor_port`, or override it in each command.

No separate serial MCP server is required: an IDE agent with local terminal access can invoke PlatformIO directly.

### Create the local configuration

PowerShell:

```powershell
Copy-Item src/wifi_config.h.example src/wifi_config.h
```

Linux/macOS:

```bash
cp src/wifi_config.h.example src/wifi_config.h
```

Edit the copied file locally. Keep each Home/Work profile's Wi-Fi credentials, receiver URL, status URL, token and timeout together. For example, a receiver at your computer's LAN address uses:

```c
#define HOME_RECEIVER_URL "http://YOUR_HOST_LAN_IP:8787/voice"
#define HOME_STATUS_URL   "http://YOUR_HOST_LAN_IP:8787/status"
#define HOME_AUTH_TOKEN   "YOUR_RECEIVER_TOKEN"
```

Replace all placeholders before trying voice. A hostname or IP of `127.0.0.1` in ESP32 configuration points to the ESP32 itself, so use the receiver computer's address on the shared network.

### Build, upload and inspect

From the repository root, using your detected port:

```bash
pio run -e esp32-s3-portrait
pio run -e esp32-s3-portrait -t upload --upload-port COM5
pio device monitor --port COM5 --baud 115200
```

Check for a successful build and upload, then normal startup messages. The firmware should identify itself for pairing as `ESP32 MacroPad`.

If flashing fails because the board does not enter download mode, hold **BOOT**, press and release **RESET**, then release **BOOT**. List ports again; the bootloader may appear under a different port. Retry the upload, then reset the board to run the firmware. See [Espressif's boot-mode instructions](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/advanced-topics/boot-mode-selection.html).

Close any serial monitor before an upload. After a reset, check the port again if monitoring stops.

The existing landscape build is:

```bash
pio run -e esp32-s3-devkitc-1 -t upload --upload-port COM5
```

Both environments flash the same board. The older `flash.py` utility writes demo firmware from `bin/`; it is separate from the classroom companion build.

## 4. Test and customise Bluetooth

Pair `ESP32 MacroPad` in the target computer's Bluetooth settings. Test in a disposable document so that shortcut effects are easy to see. The paired computer can be different from the USB development computer.

For a first modification:

> In src/macropad_config.cpp, change one Custom Keys action to my chosen shortcut. Keep its label short enough for the current layout. Preserve the other actions and show the diff. Build the portrait target, then upload through the USB port we identified. Tell me the exact physical test to perform.

Choose a shortcut that your target application already supports. Bluetooth sends key events to the active application; it does not inherently identify a OneNote page or move an application between monitors. More complex workflows need a host-side script or companion application.

After testing:

```bash
git diff
git status --short
git add src/macropad_config.cpp
git commit -m "Customise one classroom shortcut"
```

Stage the specific files you intended to change. Keep credentials and diagnostic logs containing private information out of commits.

## 5. Set up the optional voice receiver

### Install Python dependencies

From the repository root on Windows:

```powershell
python -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install faster-whisper
Copy-Item server/receiver.env.example server/.env
```

On Linux/macOS:

```bash
python3 -m venv server/.venv
server/.venv/bin/python -m pip install faster-whisper
cp server/receiver.env.example server/.env
```

The first `faster-whisper` startup may download the `base` transcription model. Run that once with internet access before attempting offline operation.

For the first test, edit `server/.env` and set:

```dotenv
VOICE_RECEIVER_TOKEN=YOUR_SHARED_RECEIVER_TOKEN
API_SERVER_KEY=YOUR_EXISTING_HERMES_GATEWAY_KEY
ENABLE_TTS=0
SPEAK_ON_HOST=0
```

Use a separate receiver token; do not put the Hermes gateway key on the ESP32. Set the active profile's `HOME_AUTH_TOKEN` or `WORK_AUTH_TOKEN` to the receiver token, then rebuild/upload if you changed firmware configuration.

### Select the AI route explicitly

The receiver reads only selected settings from `.env`. In particular, copying the example does **not** load every field into the process environment. Set mode and host settings explicitly before launching.

For Home mode, in PowerShell:

```powershell
$env:RECEIVER_ENV = "home"
$env:RECEIVER_HOST = "0.0.0.0"
$env:RECEIVER_PORT = "8787"
$env:HERMES_BASE_URL = "http://127.0.0.1:8642"
$env:DISABLE_TELEGRAM = "1"
server/.venv/Scripts/python.exe -u server/hermes_voice_receiver.py
```

For Work mode, set `RECEIVER_ENV` to `work` and `OLLAMA_MODEL` to the exact installed model name before launching the same command. Work mode tries local Ollama first; if it fails, the receiver tries Hermes.

On Linux/macOS, export those environment variables and launch `server/.venv/bin/python -u server/hermes_voice_receiver.py`.

For Hermes, follow its [installation and configuration documentation](https://github.com/NousResearch/hermes-agent), configure a provider, and start your gateway. The current receiver expects these routes under `HERMES_BASE_URL`:

- Session creation/listing at `/api/sessions`.
- Session inspection at `/api/sessions/{id}`.
- Chat at `/api/sessions/{id}/chat`.
- Health probes at `/health` and `/health/detailed`.

Confirm that your installed Hermes version exposes this API. An OpenAI-compatible chat-completions endpoint alone does not satisfy the current receiver. The template's `HERMES_GATEWAY_URL` is a legacy setting; current chat dispatch uses `HERMES_BASE_URL` and the session routes.

For Ollama, install and start it using [its documentation](https://docs.ollama.com/), download your selected model and verify it runs locally. The receiver's default Ollama host is `http://127.0.0.1:11434`. A direct Ollama reply uses the model, rather than Hermes agent tools.

### Check network reachability

In a second PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
```

Then test the same `/health` endpoint using the computer's LAN IP. The ESP32 and receiver must share a reachable network. Allow TCP 8787 from that local network through the host firewall; UDP 8788 is used for discovery. A phone hotspot may isolate clients, in which case use another network or correct the hotspot settings.

On the device, select the matching Home/Work profile and try a short voice question. Watch the receiver's `Backend used` log entry. An HTTP health response proves the receiver is reachable; receiving a real transcription and reply proves more of the pipeline works.

Leave speech synthesis disabled until text replies work. Then configure Voicebox and/or the Windows SAPI fallback as required. Windows SAPI requires `pywin32` in the receiver environment. Audio is an additional test, not a prerequisite for Bluetooth.

Work mode suppresses Telegram, but it can fall back to Hermes. To operate offline, pre-download transcription and inference models and configure that Hermes instance to use local resources too.

## 6. Connect Blender MCP

The connection uses two components: an add-on inside Blender and an MCP server launched by the IDE. Use the [upstream setup instructions](https://github.com/ahujasid/blender-mcp#installation) for a matching pair. Current upstream examples use package `mcp-for-blender`; older installations may use `blender-mcp`.

Install uv from [its official instructions](https://docs.astral.sh/uv/getting-started/installation/). Install the Blender add-on:

```bash
uvx --python 3.11 mcp-for-blender install-addon
```

Enable the add-on in Blender's preferences, open its panel in the viewport sidebar (`N`), and start the connection on port **9876**. The button label varies by add-on version. Keep Blender running.

### Cursor

Merge this entry into `.cursor/mcp.json` in your working copy; preserve any existing servers:

```json
{
  "mcpServers": {
    "blender": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--python", "3.11", "mcp-for-blender"],
      "env": {
        "BLENDER_HOST": "127.0.0.1",
        "BLENDER_PORT": "9876"
      }
    }
  }
}
```

Cursor also supports a global `~/.cursor/mcp.json`. See [Cursor's MCP documentation](https://cursor.com/docs/mcp).

### Codex

Register the local server:

```bash
codex mcp add blender --env BLENDER_HOST=127.0.0.1 --env BLENDER_PORT=9876 -- uvx --python 3.11 mcp-for-blender
codex mcp list
```

Or merge the following into your user-level `~/.codex/config.toml`:

```toml
[mcp_servers.blender]
command = "uvx"
args = ["--python", "3.11", "mcp-for-blender"]

[mcp_servers.blender.env]
BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = "9876"
```

On Windows, that user file is `%USERPROFILE%\.codex\config.toml`. The local Codex CLI and IDE extension share this configuration. See [the official MCP documentation](https://developers.openai.com/codex/mcp).

Restart the selected client after configuration. If it cannot find `uvx`, use its absolute executable path, found with `where.exe uvx` on Windows or `which uvx` on Linux/macOS. Connect one client at a time.

### Verify the connection

Ask the agent:

> Use Blender MCP to inspect the current scene. Report the Blender version, scene units, object names and enclosure dimensions. Make no changes yet.

A successful server listing alone does not prove the add-on is connected; the scene inspection should return data from the open Blender session.

The repository's `blender_client.py` is a separate socket helper using a null-terminated `execute` protocol. It is not a complete MCP server and should not be assumed compatible with every upstream add-on version.

## 7. Refine the enclosure and print it

Open `docs/Case.blend`, or choose a battery enclosure from `docs/dimensions/`. Save a working copy before editing. For a new enclosure, use the board drawing, STEP reference and measured hardware.

Give the agent a constrained task:

> Work in millimetres. Inspect the existing shells and compare mounting holes, screen opening, USB access and microphone opening with the board drawing. Use my measured battery dimensions, including its lead and connector. Propose a fit allowance before editing. Preserve the original file, save a separate working model and export only the printable shells.

Then:

1. Inspect the changed model from the front, back and sides.
2. Check clearances around ports, buttons, microphone, speaker and battery wiring.
3. Check manifold geometry and applied transforms.
4. Export each shell, open it in the slicer and confirm dimensions in millimetres.
5. Print a fit test before committing to a complete enclosure.
6. Record the working model, print orientation and settings.

`generate_case.py`, `render_views.py` and `render_beauty_shots.py` use a hard-coded `workspace_dir`. Ask the agent to adapt those paths in your working copy before running them. Scripts using `bpy` run inside Blender or through Blender's Python execution facilities, rather than ordinary system Python.

`Full_Enclosure_Assembly.stl` includes the board and screen reference geometry. Use it to inspect the assembly; print `Case_Top.stl` and `Case_Bottom.stl` separately.

Blender unit labels do not establish STL scale. The final slicer dimensions and a physical fit test are the checks that matter.

## 8. Use a repeatable development loop

For each feature:

1. Describe the action and what a successful result looks like.
2. Ask the agent to inspect the relevant code and propose a small change.
3. Review the diff and compile.
4. Upload through the verified USB port.
5. Test on the physical device and capture relevant logs.
6. Fix one identified cause at a time.
7. Commit the working result before starting the next feature.

Useful feedback is concrete: “The display boots, touch works, and Bluetooth connects, but Copy produces no text action in this application.” Include the command, observed result and relevant error text. Remove secrets from logs before sharing them; the current receiver startup log prints a prefix of its gateway key.

## Troubleshooting

| Symptom | First checks |
|---|---|
| No USB port | Data cable, another USB socket, Device Manager, BOOT/RESET sequence |
| Port busy during upload | Close PlatformIO and other serial monitors |
| Upload works, monitor is blank | List ports again after reboot; check monitor port and 115200 baud |
| Screen or touch fails | Exact ES3C28P board, correct root project and environment, existing board driver settings |
| Bluetooth pairs but shortcut does nothing | Active application, supported shortcut, correct profile and old pairing records |
| Voice transmission fails | Matching profile, reachable host IP, receiver running, TCP 8787 and matching receiver token |
| Reply arrives but Hermes does not log a run | Check backend log; Work tries Ollama first and Home can fall back |
| Hermes session setup fails | Gateway key, session API compatibility and HERMES_BASE_URL |
| Blender MCP has no tools | Client config, uvx executable path and client restart |
| Tools exist but scene inspection fails | Blender open, add-on enabled, matching port 9876 and compatible versions |
| Enclosure exports at the wrong size | Blender transforms, export scale and measured slicer dimensions |

Keep a known working firmware commit and an untouched enclosure model. They give you a practical way to recover while continuing to experiment.
