# Raspberry Pi Teacher Touchscreen Integration Plan

Prepared 4 November 2026 (Australia/Brisbane).
Current programme governance: [consolidated branch plan](2026-10-21-companion-media-agent-master-plan.md).
Target hardware baseline: Raspberry Pi 3 Model B Rev 1.2 (`companionpi`), Raspberry Pi OS Lite 64-bit (Debian 13 Trixie), 1 GB RAM.

> **Security & Git boundary:** All private Wi-Fi credentials, SSH host keys, IP receipts and imaging artefacts remain strictly inside `.local/raspberry-pi/` (which is excluded by `.gitignore`). All source code, systemd templates, UI modules, protocol schemas and this plan live in tracked repository directories (`docs/`, `tools/compose/`, `tools/pi_touchscreen/`) with zero hardcoded secrets or school/home network identifiers.

---

## 1. Purpose and Teacher Workflow

When presenting in the classroom, the student-facing display (`classroom_display`) shows the active Teaching Board pupil window or a placed classroom application (OneNote, Word, Chrome), while the ESP32-S3 handheld provides mobile voice/button triggers around the room. However, the teacher lacks a dedicated, glanceable podium surface showing **all available visual assets, generated image candidates, and presentation controls** without disturbing the student view or alt-tabbing on the host PC.

The Raspberry Pi touchscreen acts as a **dedicated teacher-facing control deck and media staging surface** situated at the teaching station at school:

1. **Image Series & Library Staging:** When an agent or image request generates multiple candidate images (or when browsing the reusable resource library), the Pi touchscreen displays a touch-friendly thumbnail grid. The teacher taps an image on the Pi touchscreen to preview it and taps **"Put on Board"** to place it directly onto the active Teaching Board page (in clear space, preserving existing objects per the 29 October content-preservation policy).
2. **Board & Page Deck:** Glanceable view of current lesson pages, Live vs Freeze status, **Freeze / Resume** toggle, **Previous / Next Page**, **New Page**, and **Undo / Redo**.
3. **Classroom Display Switcher:** One-tap buttons to bring **OneNote**, **Word**, **Chrome**, or the **Teaching Board pupil display** to the student screen (reusing the existing `MonitorShortcutController` desktop actions).

---

## 2. Architectural Options & Recommendation

Because the Raspberry Pi 3B has **1 GB of RAM** (approx. 949 MB usable) and runs 64-bit Raspberry Pi OS Lite, the UI architecture must keep memory consumption on the Pi low while keeping the Windows companion as the single authority for `BoardSession`, `MediaStore`, DPAPI credentials, and Win32 window placement.

| Option | Description | Pros | Cons / Risks |
| --- | --- | --- | --- |
| **Option A: Windows-Hosted Local API + Lightweight Native Qt/PySide6 Kiosk on Pi (Recommended)** | Windows `UnifiedDesktop` / `BoardCandidate` runs a bounded, token-authenticated HTTP/JSON control & thumbnail API. The Pi runs a lightweight Python/PySide6 (or Tkinter/Cage) fullscreen touch client rendering JSON state and thumbnails. | - Very low RAM footprint on Pi 3B (~60–90 MB, no Chromium OOM risk).<br>- Reuses existing PySide6 patterns already in `tools/compose/`.<br>- Windows retains 100% ownership of `BoardSession`, `MediaStore`, and Office/monitor controls.<br>- Easy to test locally on Windows at home using a mock/windowed Pi client without the physical Pi present. | - Requires installing `python3-pyside6` (or minimal Wayland/X11 kiosk) on the Pi. |
| **Option B: Windows-Hosted Web App + Chromium Kiosk on Pi** | Windows serves a responsive HTML/JS web UI; the Pi boots `cage` or `xinit` with `chromium --kiosk`. | - Zero UI code deployed to the Pi after initial kiosk setup.<br>- Very fast UI iteration in HTML/CSS. | - **High memory pressure on Pi 3B (1 GB RAM)**: 64-bit Chromium easily consumes 450–700 MB+ when decoding multiple image thumbnails, risking Linux OOM kills during class. |
| **Option C: Full Companion Sync + Standalone Media Store on Pi** | Synchronise the SQLite media store to the Pi and run a full `BoardCandidate` node on the Pi. | - Works if Windows PC is offline. | - Violates single-authority session ownership; duplicates state; unnecessary since the student display is connected to the Windows PC anyway. |

### Recommended Architecture: Option A (Windows-Hosted Teacher Deck API + Lightweight Python Touch Client on Pi)

1. **Windows PC remains the single source of truth:** `tools/compose/` exposes an opt-in, bearer-token-authenticated **Teacher Deck Server** (`tools/compose/teacher_deck_server.py`) bound to the local network interface (or loopback for home testing).
2. **Lightweight Pi Touch Client:** A dedicated, tracked package `tools/pi_touchscreen/` runs on the Pi (and can also run in a simulated 800×480 / 1024×600 window on Windows at home). Because the Pi will live exclusively at school, **being able to launch the exact same `pi_touchscreen` client in a local desktop window at home** makes home-to-school development seamless.

---

## 3. Repository Structure (Tracked on GitHub vs Ignored in `.local/`)

To ensure clean collaboration between home and school via GitHub without leaking credentials:

```text
ESP32 project/
├── docs/
│   └── 2026-11-04-raspberry-pi-touchscreen-plan.md   # Tracked: this architecture & build plan
├── tools/
│   ├── compose/
│   │   ├── teacher_deck_server.py                    # Tracked: Windows-side authenticated HTTP/SSE bridge
│   │   ├── teacher_deck_models.py                    # Tracked: Request/response schemas & multi-image staging queue
│   │   └── tests/
│   │       └── test_teacher_deck.py                  # Tracked: Unit & integration tests (runs on Windows & Linux)
│   └── pi_touchscreen/
│       ├── README.md                                 # Tracked: School/home setup & service instructions
│       ├── deck_client.py                            # Tracked: API client with automatic reconnect & token auth
│       ├── deck_ui.py                                # Tracked: Touch-first UI ( Staging Grid, Board Controls, Display Switcher )
│       ├── config.example.json                       # Tracked: Template config (no secrets)
│       ├── systemd/
│       │   └── companion-touchscreen.service         # Tracked: Systemd unit template for Pi auto-start
│       └── tests/
│           └── test_deck_ui.py                       # Tracked: Offscreen UI & state tests
└── .local/
    └── raspberry-pi/                                 # Git-ignored: SSH keys, Wi-Fi passwords, school/home IP receipts
```

---

## 4. Detailed Phased Implementation Plan

### Phase 1: Multi-Image Candidate Staging & Windows Teacher Deck API (`tools/compose/`)
**Goal:** Allow the Windows companion to stage a series of generated or searched images and expose safe, authenticated endpoints for the teacher touchscreen.

1. **Staging Queue & Series Generation (`teacher_deck_models.py`):**
   - Extend the Board/Media workflow to maintain a **Staging Tray** of candidate images (e.g., when an agent generates a batch/series of 2–4 images for a prompt, or returns a shortlist from the reusable library).
   - Each staged item holds an immutable `version_id`, `asset_id`, `sha256`, title, origin (`generated` vs `library`), review state, and thumbnail endpoint.
2. **Authenticated Teacher Deck HTTP Server (`teacher_deck_server.py`):**
   - Built on Python's `ThreadingHTTPServer` (matching `server/media_library_server.py` patterns—zero heavy external web frameworks, constant-time `hmac.compare_digest` bearer-token verification).
   - **Read Endpoints:**
     - `GET /api/v1/status` — Lesson title, current `page_id`, page list, `frozen` state, active classroom display status, and state revision counter.
     - `GET /api/v1/staged` — List of staged/generated candidate images and recent reusable library matches for the current lesson topic.
     - `GET /api/v1/library?q=<query>` — Fast filtered search of `BoardResourceLibrary`.
     - `GET /api/v1/thumb/<version_id>` — Downscaled JPEG/PNG thumbnail (e.g., max 320×240) served from memory/disk cache so the Pi never downloads 20 MiB raw blobs.
   - **Action Endpoints (Mutating, Idempotent, Revision-Checked):**
     - `POST /api/v1/board/present-image` — Accepts `{version_id, expected_revision, target: "current_page" | "new_page"}`. Uses `simple_image_composition` / `insert_prepared_image` to place the chosen image into clear space on the Board (preserving existing objects) and records first-use teacher approval if the image was newly generated.
     - `POST /api/v1/board/generate-series` — Triggers a bounded series generation or library shortlist for a teacher prompt/preset.
     - `POST /api/v1/board/control` — Executes `freeze`, `resume`, `prev_page`, `next_page`, `new_page`, `undo`, or `redo` on the main Qt thread via thread-safe queue/signals.
     - `POST /api/v1/display/switch` — Invokes `MonitorShortcutController` to bring `onenote`, `word`, `chrome`, or `board` to the student display.

### Phase 2: Touch-First Teacher Deck UI (`tools/pi_touchscreen/`)
**Goal:** Build the touchscreen interface so it can be developed and tested in a desktop window at home, and run fullscreen on the Pi at school.

1. **Three-Zone Touch Layout (Designed for 7" 800×480 up to 10" 1280×800 touchscreens):**
   - **Top Bar (Always Visible):**
     - Connection indicator (`Connected to Classroom PC` / `Reconnecting…`).
     - Prominent **Pupil Status Pill**: `LIVE ON STUDENT SCREEN` (green) vs `FROZEN (PRIVATE EDITING)` (amber), with a single large **Freeze / Resume** toggle button.
     - Quick **Classroom Display Bar**: 4 large touch buttons (`Board`, `OneNote`, `Word`, `Chrome`).
   - **Main Centre Area (Tabbed Touch Workspace):**
     - **Tab 1: Image Staging & Series Selector (Default):**
       - Displays the series of generated/staged images as large touch cards with thumbnails and titles.
       - Tapping a card opens a high-clarity preview with two primary actions: **"Put on Current Page"** (adds in clear space) and **"Put on New Page"** (creates a fresh page and places the image).
       - Quick prompt/topic bar to request a new image series or filter saved library images.
     - **Tab 2: Lesson Pages & Layout Overview:**
       - Visual strip of all pages in the current lesson; tap any page to navigate the teacher or pupil view.
   - **Bottom Control Strip:**
     - Large touch targets (minimum 56×56 px) for `◀ Prev Page`, `Next Page ▶`, `+ New Page`, `Undo`, and `Redo`.
2. **Home Simulator Mode (`--windowed`):**
   - Running `python tools/pi_touchscreen/deck_ui.py --windowed --url http://127.0.0.1:8790` on the Windows PC opens the exact Pi touchscreen interface in a fixed-aspect window alongside `UnifiedDesktop`. This lets you build, debug, and rehearse every feature at home while the physical Pi stays at school.

### Phase 3: Raspberry Pi OS Display & Network Provisioning (School Deployment)
**Goal:** Configure the headless Raspberry Pi OS Lite (`companionpi`) to drive the attached touchscreen in an appliance/kiosk mode and connect reliably on the school network.

1. **Minimal Display Stack on Raspberry Pi OS Lite:**
   - Rather than installing a heavy desktop environment, install only the minimal Wayland kiosk compositor (`cage` or `labwc`), Mesa/DRM drivers, and `python3-pyside6.qtwidgets` (or `python3-tk` if keeping dependencies minimal).
   - Configure `/boot/firmware/config.txt` overlays for the specific touchscreen (DSI ribbon or HDMI + USB touch) and verify touch calibration/rotation via `libinput`.
2. **School Network & Discovery Strategy:**
   - Since the Pi will reside permanently at school:
     - Provision the school Wi-Fi (or Ethernet DHCP) in NetworkManager (`nmcli`) on the Pi, keeping credentials in `.local/raspberry-pi/` only.
     - Support **mDNS (`companionpi.local`) + UDP Broadcast / Tailscale fallback**: The Windows companion can either connect outbound to `companionpi.local` or broadcast its Teacher Deck endpoint on the local subnet, or communicate over the shared private Tailscale tailnet if school Wi-Fi AP isolation blocks client-to-client LAN traffic.
     - *School Wi-Fi Isolation Guardrail:* Many school networks enable client isolation on Wi-Fi. If the Windows PC and Pi cannot reach each other over school Wi-Fi directly, we have two proven fallbacks ready:
       1. **Tailscale subnet/node routing** between the Windows PC and `companionpi`.
       2. **USB Ethernet Gadget / Direct Ethernet patch** if the Pi is on the teacher's desk next to the laptop/PC.
3. **Appliance Auto-Start (`systemd`):**
   - Install `tools/pi_touchscreen/systemd/companion-touchscreen.service` to launch the touch UI automatically on boot, restart on crash, and display a clean "Waiting for Classroom Companion PC…" standby screen when the teacher's computer is asleep or disconnected.

### Phase 4: Verification & Classroom Acceptance Gates
Per `AGENTS.md`, local tests, deployment checks, and physical classroom acceptance are tracked separately:

1. **Gate 1 — Local Automated & Windowed Verification (Home & School):**
   - Unit tests for `teacher_deck_server.py` covering token authentication, revision checks, additive-only image placement (never deleting existing objects), and display switching.
   - End-to-end test using `--windowed` Pi client on Windows: generate/stage 3 candidate images -> tap image #2 in the Pi client window -> verify it appears on the `BoardCandidate` pupil canvas with proper attribution and Undo support.
2. **Gate 2 — Physical Pi + Touchscreen Hardware Check:**
   - Verify Pi 3B boots directly into the touch UI within 25 seconds, memory usage stays `< 250 MB` (`free -m`), `vcgencmd get_throttled` remains `0x0`, and touch taps register accurately without cursor drift.
3. **Gate 3 — School Network & Classroom Acceptance:**
   - Verify live teacher presentation workflow at school: handheld ESP32-S3 used for mobility, Pi touchscreen used at the desk to pick from generated image series and switch student display targets.
