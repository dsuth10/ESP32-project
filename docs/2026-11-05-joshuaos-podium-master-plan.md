# JoshuaOS Podium & Unified Classroom Showrunner Plan

**Prepared:** 5 November 2026 (Australia/Brisbane)  
**Scope:** System-wide simplification and architectural integration across the **ESP32-S3 Handheld**, **14″ Raspberry Pi 3B (`companionpi` — "JoshuaOS Podium")**, **School & Home Windows Desktops**, **MrSutherland.net Interactive Lessons**, and the **Linux Hermes AI Showrunner** over a single **Tailscale Mesh**.  
**Governance:** Extends [2026-10-21-companion-media-agent-master-plan.md](2026-10-21-companion-media-agent-master-plan.md), [2026-11-04-raspberry-pi-touchscreen-plan.md](2026-11-04-raspberry-pi-touchscreen-plan.md), and [2026-11-05-classroom-hub-tailscale-brief.md](2026-11-05-classroom-hub-tailscale-brief.md). Preserves all safety and verification gates in `AGENTS.md` and `GEMINI.md`.

---

## 1. Executive Summary: Streamlining the Classroom Ecosystem

To eliminate network-switching friction and connect your presentation tools into a cohesive system:

1. **One Network for the Handheld (Zero Firmware Writes):**
   - The ESP32-S3 handheld stays permanently on your **Phone Hotspot (`WORK`)** profile. Its existing 4-tier UDP port `8788` auto-discovery (`HostDiscovery::discoverNow()`) automatically discovers the active Windows PC on the hotspot and caches `dyn_work_ip` in NVS—requiring zero reflashing and no toggling between Home and Work.
2. **One Network for All Computers (Tailscale Mesh):**
   - Every computer (**Linux Hermes**, **Home Windows PC**, **School Windows PC**, and **14″ Raspberry Pi 3B `companionpi`**) communicates over your shared **Tailscale tailnet**.
   - The Windows Teacher Deck Server persists its configuration/token in protected companion settings and binds to Tailscale/loopback so `companionpi` can connect reliably at school and home, with one-tap host switching between School PC and Home PC.
3. **"JoshuaOS Podium" on the 14″ Raspberry Pi Touchscreen:**
   - Designed as a custom, full-screen dark-slate appliance operating system shell running natively on PySide6 (`QtWidgets`) + `cage` Wayland (`< 200 MB` RAM on the 1 GB Pi 3B with `zram`).
   - Features a **4-Zone Layout**:
     1. **Top Status & Host Bar:** Connection state, active host selector (`School PC` / `Home PC`), and a prominent `LIVE ON STUDENT SCREEN` / `PUPIL SCREEN FROZEN` toggle.
     2. **Left Stage Switcher Rail:** One-tap display switching (`Board`, `OneNote`, `Word`, `Chrome / MrSutherland.net`) with live active-target highlighting.
     3. **Centre Tabbed Workspace:**
        - **Launchpad (`MrSutherland.net` Interactive Tools):** Seeded with curated interactive web lessons that launch directly onto the classroom display.
        - **Image Staging & Series:** Multi-image candidate grid with preview and clear-space board placement (`Put on Current Page`, `Put on New Page`).
        - **Lesson Pages:** Glanceable page list and navigation.
     4. **Right Glass Ink & Overlay Rail + Bottom Hermes Showrunner Strip:** Controls for drawing over *any* screen (`Draw`, `Interact / Click-Through`, pen colours, `Eraser`, `Clear`, `Snap & Keep to Board`) and 3 predictive lesson cues driven by Linux Hermes.
4. **Heavy Compute Stays on the Desktops + Linux Hermes Runs the Show:**
   - The Pi 3B stays fast and responsive because all heavy rendering, Office/monitor management, and AI generation happen on the Home/School Windows Desktops and the Linux Hermes server.

---

## 2. Phase 1 & Phase 2 Implementation Architecture

### 2.1 `MrSutherland.net` Interactive Launchpad & Allowlisted URL Opening
- **Tracked Catalogue (`tools/compose/classroom_catalogue.json`):**
  - Stores curated `MrSutherland.net` interactive web lessons and classroom tools (`id`, `title`, `category`, `url`, `description`, `display_target`).
  - Supports optional private overrides in `.local/classroom_catalogue.json`.
- **Safe Allowlisted Web Launching (`window_monitor_manager.py` & `monitor_shortcut.py`):**
  - `is_allowlisted_web_url(url)` validates `https://mrsutherland.net/...` (and `https://www.mrsutherland.net/...`).
  - `MonitorShortcutController.open_web_url_on_classroom_display(url, title)` launches Chrome with the allowlisted URL (preserving configured Chrome profile if any) and places/focuses the window on the classroom display without granting Paste Ready permissions.
- **Active Classroom Display Telemetry (`teacher_deck_server.py`):**
  - `GET /api/v1/status` reports `active_display_target` (`board`, `onenote`, `word`, `chrome`, or `none`), `catalogue_count`, `glass_ink` state, and `showrunner_cues`.

### 2.2 Unified "Glass Ink" Screen Annotation Overlay (`tools/compose/glass_overlay.py`)
- **`GlassInkOverlay` (`QWidget`) & `GlassInkController`:**
  - Frameless, translucent, always-on-top PySide6 overlay (`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`, `WA_TranslucentBackground`) positioned over the classroom display geometry.
  - Supports **Draw Mode** (`mode="draw"`, captures pen/mouse/touch strokes with configurable colour and width) and **Interact / Click-Through Mode** (`mode="interact"`, toggles Win32 `WS_EX_TRANSPARENT | WS_EX_LAYERED` on Windows so clicks pass through to `MrSutherland.net` or OneNote while drawings remain visible).
  - Supports **Clear Ink**, **Undo Stroke**, and **Snap & Keep to Board** (`snap_to_board`), which composites the screen + active glass ink strokes into a PNG, imports it into `lesson_media` (`MediaStore`), stages it in `StagingTray`, and places it onto a new or current Teaching Board page.

### 2.3 Persistent Tailscale / Multi-Host Teacher Deck Configuration
- **Windows Server (`teacher_deck_server.py`, `board_candidate.py`, `unified_desktop.py`):**
  - Supports persistent Teacher Deck settings (`teacher-deck-config.json` in the isolated companion/board settings folder) with auto-detected Tailscale interface IP (`100.x.y.z`) or configured bind host (`127.0.0.1` default for tests, configurable for Tailscale/LAN).
- **Pi Client (`tools/pi_touchscreen/deck_client.py`, `deck_ui.py`):**
  - Supports `hosts` list in `config.json` (`active_host_id`, `hosts: [{id, label, url, token}]`) so `companionpi` can switch cleanly between `School Classroom PC`, `Home Desktop PC`, and `Local Simulator`.
  - Branded as **JoshuaOS Podium** with full backward compatibility for all existing `TeacherDeckWindow` widget names and tests.

