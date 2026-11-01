> **Coordinator review:** This is a research lead, not an implementation specification or proof of end-to-end behaviour. Several statements below are hypotheses or overly categorical: display identifiers can be missing, duplicated or change; resolution alone must not silently choose a target; foreground activation is not guaranteed by input-queue attachment or simulated Alt; claims about maximised-window corruption and OneNote class names require verification on the installed version. Do not set process-wide DPI awareness at module import: Microsoft says process-default DPI awareness must be chosen before creating UI and recommends a manifest. The installed OneNote COM interface and mixed-DPI behaviour need a controlled test. PowerToys has evolving command-line support, so no general absence of a CLI is established. The coordinator's synthesis takes precedence for proposed safeguards: [investigation](2026-11-01-device-shortcut-monitor-investigation.md). Sources: [foreground restrictions](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow), [DPI awareness](https://learn.microsoft.com/en-us/windows/win32/learnwin32/dpi-and-device-independent-pixels).
# External Research: Windows Multi-Monitor Window Management & OneNote Orchestration

> **Document Type:** External Technical Research & Architecture Investigation
> **Date:** 1 November 2026
> **Target Systems:** Windows 10 / Windows 11 (Host Companion), Microsoft OneNote (Desktop M365 & UWP), ES3C28P ESP32-S3 (MacroPad BLE HID Controller)
> **Status:** Research only. No firmware, application, or display configuration changes.

---

## 1. Executive Summary

This investigation evaluates official Windows Win32/COM Application Programming Interfaces (APIs) and established open-source GitHub repositories to solve a core requirement of the **ESP32 Classroom Companion**: reliably finding or launching Microsoft OneNote, restoring its window state, moving it to a designated monitor (e.g. primary laptop vs classroom interactive whiteboard/projector vs home secondary monitor), maximising it, and bringing it to the foreground.

### Key Findings

1. **Host-Side Architecture is Mandatory:**
   Bluetooth Low Energy (BLE) Human Interface Device (HID) hardware cannot inspect desktop state, query display topology, or target specific monitors. As established in the project's [integration review](2026-11-01-monitor-shortcut-project-integration.md) and [core rules](../../GEMINI.md), the handheld MacroPad must remain a lightweight HID trigger (emitting an assigned function key or chord), whilst the Windows companion host service executes the semantic window, process, and monitor orchestration.
2. **Volatile vs Persistent Display Identity:**
   Windows display indices (`Display 1`, `Display 2`) and Win32 GDI device names (`\\.\DISPLAY1`) are **volatile**. GPU driver re-enumeration, USB-C/Thunderbolt docking stations, HDMI projector handshakes, and monitor sleep cycles frequently reassign these indices. Reliable home vs work monitor identification requires the Windows **Connecting and Configuring Displays (CCD)** API (`QueryDisplayConfig`) or WMI (`WmiMonitorID`) to extract persistent Extended Display Identification Data (EDID): Manufacturer ID, Product Code, and Device Instance Path.
3. **The Maximised Window Trap:**
   Calling `SetWindowPos` directly on a maximised window either fails silently or corrupts the window's restore rectangle (`rcNormalPosition`). To reposition a maximised window across displays with different resolutions and DPI scaling, the orchestration service must inspect `WINDOWPLACEMENT`, unmaximise/restore the window, reposition it to the target monitor's work area (`rcWork`), and re-maximise it via `SetWindowPlacement` or `ShowWindow(SW_SHOWMAXIMIZED)`.
4. **Foreground Lock Restriction:**
   Since Windows 2000 and reinforced in Windows 10/11, `SetForegroundWindow` called from a background process or service is restricted by the Windows shell to prevent focus stealing. It will return `FALSE` and flash the window icon in the taskbar unless the calling thread satisfies specific criteria (e.g. bridging input queues via `AttachThreadInput` to the current foreground window, or pulsing a virtual key input like `VK_MENU`).
5. **OneNote Architectural Bifurcation:**
   - **OneNote Desktop (M365 / Office 365 / 2016–2024):** Runs as `ONENOTE.EXE`, top-level window class `Framework::CFrame`. It exposes a full COM Interop interface (`OneNote.Application`) with a `Windows` collection providing direct access to native `WindowHandle` (`HWND`), `Active`, `FullPageView`, and page navigation.
   - **OneNote for Windows 10 (UWP / Store app):** Hosted inside `ApplicationFrameHost.exe` with class `ApplicationFrameWindow`. It lacks COM automation, and standard PID queries return the container rather than the inner application. Microsoft has officially deprecated this version; the companion should focus primarily on OneNote Desktop whilst providing fallback class matching.
6. **Open-Source Tool Suitability:**
   - **Microsoft PowerToys (FancyZones / Workspaces):** Excellent reference for native C++ CCD monitor identification and window placement, but lacks a headless, lightweight CLI/REST API for single-window orchestration.
   - **AutoHotkey (v1 / v2):** Convenient for rapid prototyping, but introduces an external interpreter dependency, GPLv2 licensing implications, and script-level race conditions.
   - **komorebi:** High-performance tiling manager in Rust, but its current licence (**PolyForm Strict 1.0.0**) explicitly **prohibits commercial and workplace use** without purchasing per-seat commercial licences, disqualifying it for open educational/classroom deployment.
   - **Recommended Path:** A self-contained Python module within the existing Windows companion service (`tools/compose/` or `server/`) utilising Win32 APIs via `ctypes` or `pywin32` (BSD/PSF licence). This requires zero external runtime binaries, integrates directly with `tools/compose/focus_tracker.py`, and gives full control over error receipts and fallback behaviours.

---

## 2. Official Windows APIs for Window and Monitor Orchestration

### 2.1 Monitor Enumeration, Topology, and Persistent Identification

In Windows, multiple physical displays form a unified virtual desktop coordinate space. The primary monitor always has its top-left corner at $(0, 0)$. Secondary monitors placed to the left of or above the primary monitor have **negative coordinates** ($\text{left} < 0$ or $\text{top} < 0$).

```
                      [-1920, 0]                [0, 0]              [1920, 0]
             ┌────────────────────────┐┌────────────────────────┐┌────────────────────────┐
             │   Classroom Display    ││     Primary Laptop     ││   Secondary Monitor    │
             │     1920 x 1080        ││      1920 x 1080       ││      1920 x 1080       │
             │   (Negative Virtual)   ││      (Origin 0,0)      ││   (Positive Virtual)   │
             └────────────────────────┘└────────────────────────┘└────────────────────────┘
```

#### The Volatile Win32 GDI Layer
Historically, applications query monitors via:
- `EnumDisplayMonitors(hdc, lprcClip, lpfnEnum, dwData)`: Iterates over active display monitors.
- `GetMonitorInfoW(hMonitor, &mi)`: Returns `MONITORINFOEXW`, containing `rcMonitor` (full bounds), `rcWork` (usable workspace excluding taskbar and docked toolbars), and `szDevice` (e.g. `\\.\DISPLAY1`).
- `EnumDisplayDevicesW(lpDevice, iDevNum, &dispDev, dwFlags)`: Enumerates graphics adapters and attached monitors.

**Critical Limitation:** `szDevice` (`\\.\DISPLAY1`, `\\.\DISPLAY2`) and `hMonitor` handles are ephemeral. When a teacher unplugs their laptop to teach in another room or docks to a different projector, the operating system routinely swaps `\\.\DISPLAY1` and `\\.\DISPLAY2`. Furthermore, `EnumDisplayDevicesW` often returns `"Generic Pnp Monitor"` for `.DeviceString`, hiding the actual monitor model.

#### The Persistent CCD (Connecting and Configuring Displays) API
Introduced in Windows 7 and standard in Windows 10/11, the CCD API provides low-level access to the graphics driver display paths and hardware EDID descriptors.

*Primary Header:* `<wingdi.h>`, `<winuser.h>`
*Core Functions:*
1. `GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, &pathCount, &modeCount)`: Retrieves required buffer allocations for active displays.
2. `QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, &pathCount, paths, &modeCount, modes, nullptr)`: Populates array of `DISPLAYCONFIG_PATH_INFO` and `DISPLAYCONFIG_MODE_INFO`.
3. `DisplayConfigGetDeviceInfo(&targetName.header)`: Queries `DISPLAYCONFIG_TARGET_DEVICE_NAME` using the target adapter ID and target ID from the path.

*Extracted Identifiers in `DISPLAYCONFIG_TARGET_DEVICE_NAME`:*
- `monitorFriendlyDeviceName`: User-facing model name (e.g. `"Promethean ActivPanel"`, `"DELL U2719D"`, `"Odyssey G5"`).
- `edidManufactureId`: 3-character compressed ASCII manufacturer code (e.g. `PRM`, `DEL`, `SAM`, `RTK`).
- `edidProductCodeId`: 16-bit hex product code specified by the manufacturer.
- `monitorDevicePath`: Unique Windows PnP device instance path (e.g. `<monitor device path>`).

#### The WMI Alternative: `WmiMonitorID`
For environments running Python or PowerShell without native C++ compilation, Windows exposes parsed EDID descriptors through WMI/CIM:
- Namespace: `root\wmi`
- Class: `WmiMonitorID`
- Fields: `ManufacturerName` (uint16 array), `ProductCodeID` (uint16 array), `SerialNumberID` (uint16 array), `UserFriendlyName` (uint16 array), and `InstanceName`.

Matching a live `hMonitor` (from `EnumDisplayMonitors`) to a `WmiMonitorID` record is achieved by comparing the device instance path returned from `GetMonitorInfoW` -> `GetDisplayDeviceW`.

---

### 2.2 Per-Monitor DPI Scaling Considerations

When moving windows between displays with disparate DPI scaling factors (for example, a modern 14-inch laptop display at 150% scaling [144 DPI] and a 65-inch classroom Promethean board at 100% scaling [96 DPI]):
1. **DPI Unaware Host Processes:** If the host companion process is not declared Per-Monitor DPI Aware, Windows DWM (Desktop Window Manager) virtualises its coordinate space. Calls to `GetWindowRect` or `GetMonitorInfo` return scaled, synthetic coordinates, causing window repositioning to miss target boundaries or clip off-screen.
2. **Per-Monitor V2 Awareness:** The host process must call:
   ```c
   SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
   ```
   Under Per-Monitor V2, `SetWindowPos` and `GetWindowRect` operate in real physical pixels.
3. **Coordinate Scaling Formula:** When moving a restored window to a display with a different DPI, its logical size must be scaled to the target display's DPI to maintain relative visual proportions:
   $$\text{Pixel Dimension}_{\text{target}} = \text{MulDiv}\left(\text{Pixel Dimension}_{\text{source}}, \text{DPI}_{\text{target}}, \text{DPI}_{\text{source}}\right)$$
   where $\text{MulDiv}(a, b, c) = \lfloor (a \times b) / c \rfloor$. The target monitor DPI is queried via `GetDpiForMonitor(hMonitor, MDT_EFFECTIVE_DPI, &dpiX, &dpiY)`.

---

### 2.3 Window Finding and Identity Verification

To avoid moving unintended applications or catching temporary splash screens, window resolution must verify both process identity and window characteristics.

```
                     EnumWindows (Top-Level Windows)
                                   │
                     IsWindowVisible(hWnd) == TRUE
                                   │
                   GetWindowLong(hWnd, GWL_EXSTYLE)
                   Exclude WS_EX_TOOLWINDOW
                                   │
                   GetWindowThreadProcessId(hWnd, &pid)
                                   │
                 QueryFullProcessImageNameW(hProcess)
                    Must match ONENOTE.EXE
                                   │
                        GetClassNameW(hWnd)
                    Must match "Framework::CFrame"
                                   │
                 Window Rect Dimensions > 600 x 400
                     (Excludes splash screens)
```

#### Win32 APIs Involved:
- `EnumWindows(lpEnumFunc, lParam)`: Traverses all top-level desktop windows.
- `GetWindowThreadProcessId(hWnd, &dwProcessId)`: Extracts the owning process PID.
- `QueryFullProcessImageNameW(hProcess, 0, lpImageName, &dwSize)`: Returns the full binary path (e.g. `C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE`).
- `GetClassNameW(hWnd, lpClassName, nMaxCount)`: Returns the window class name.
- `GetWindowTextW(hWnd, lpString, nMaxCount)`: Returns the window title bar text.

#### The UWP / Packaged App Complication:
For Store apps (such as the legacy OneNote for Windows 10):
- The top-level window belongs to `ApplicationFrameHost.exe` with class `ApplicationFrameWindow`.
- `GetWindowThreadProcessId` returns the PID of `ApplicationFrameHost.exe`, **not** the underlying application.
- To identify the real hosted app, the orchestrator must call `EnumChildWindows(hWndParent, ...)` to inspect the inner `Windows.UI.Core.CoreWindow` and query the child window's PID.

---

### 2.4 Window State Restoration and Movement

A primary source of failure in window automation is attempting to move a **maximised** or **minimised** window directly using `SetWindowPos`.

#### The Maximised Window Problem
When a window is maximised on Monitor A:
1. Its live window rectangle equals Monitor A's work area.
2. Its internal `WINDOWPLACEMENT.rcNormalPosition` stores its previous restored coordinates on Monitor A.
3. Calling `SetWindowPos(hWnd, NULL, targetX, targetY, targetW, targetH, SWP_NOZORDER)` on a maximised window is either rejected by Windows or places the window in a corrupted visual state where DWM renders it on Monitor B but thinks its restore bounds remain on Monitor A. When the user subsequently clicks "Restore Down", the window flies back to Monitor A.

#### The Correct Win32 Sequence:
```cpp
void MoveAndMaximiseToMonitor(HWND hWnd, HMONITOR hTargetMonitor) {
    MONITORINFO mi = { sizeof(MONITORINFO) };
    if (!GetMonitorInfoW(hTargetMonitor, &mi)) return;

    WINDOWPLACEMENT wp = { sizeof(WINDOWPLACEMENT) };
    if (!GetWindowPlacement(hWnd, &wp)) return;

    // Step 1: If minimised or maximised, restore it first
    if (wp.showCmd == SW_SHOWMINIMIZED || wp.showCmd == SW_SHOWMAXIMIZED) {
        ShowWindow(hWnd, SW_RESTORE);
    }

    // Step 2: Position window into target monitor work area
    int targetX = mi.rcWork.left;
    int targetY = mi.rcWork.top;
    int targetW = mi.rcWork.right - mi.rcWork.left;
    int targetH = mi.rcWork.bottom - mi.rcWork.top;

    SetWindowPos(
        hWnd,
        HWND_TOP,
        targetX,
        targetY,
        targetW,
        targetH,
        SWP_NOACTIVATE | SWP_FRAMECHANGED
    );

    // Step 3: Maximise on target display
    ShowWindow(hWnd, SW_SHOWMAXIMIZED);
}
```

---

### 2.5 Foreground Activation and Focus Stealing Prevention

Windows actively blocks background processes from forcing windows to the foreground via `SetForegroundWindow(hWnd)`. If the calling thread does not currently own the foreground input queue or have user interaction rights, `SetForegroundWindow` returns `FALSE` and the target window flashes orange in the taskbar.

#### Methods to Grant Foreground Rights:
1. **Queue Attachment via `AttachThreadInput` (Standard Workaround):**
   Temporarily bridges the companion's thread message queue to the currently active foreground window's thread:
   ```cpp
   HWND hForeground = GetForegroundWindow();
   DWORD foreThread = GetWindowThreadProcessId(hForeground, NULL);
   DWORD appThread = GetCurrentThreadId();

   if (foreThread != appThread) {
       AttachThreadInput(appThread, foreThread, TRUE);
       BringWindowToTop(targetHwnd);
       SetForegroundWindow(targetHwnd);
       AttachThreadInput(appThread, foreThread, FALSE);
   } else {
       BringWindowToTop(targetHwnd);
       SetForegroundWindow(targetHwnd);
   }
   ```
   *Note:* As implemented in `tools/compose/focus_tracker.py`, `AttachThreadInput` is proven in this repository. However, it will fail if User Interface Privilege Isolation (UIPI) intervenes (e.g. if the foreground app is elevated as Administrator and the companion is running at standard user privileges).
2. **Virtual Keystroke Pulse (`VK_MENU` Alt Pulse):**
   Simulating a momentary press and release of the Alt key (`VK_MENU`) via `SendInput` resets the Windows shell's foreground lock timer, because Windows considers the process that received the last input event eligible to set foreground.
3. **`AllowSetForegroundWindow(ASFW_ANY)`:**
   Can be called by an active foreground process to delegate foreground privileges to a child or background process.

---

### 2.6 Process Launch and Synchronisation

If OneNote is not currently running, launching it and positioning its window requires asynchronous synchronisation:
1. **Process Spawning:** Call `CreateProcessW` or Python `subprocess.Popen(["C:\\...\\ONENOTE.EXE"])`.
2. **Waiting for Message Queue Initialization:** Call `WaitForInputIdle(hProcess, timeoutMs)`. This API blocks until the target application is waiting for user input with no pending input messages.
3. **Polling for Document Window:** `WaitForInputIdle` returns as soon as the process creates its first window, which in OneNote is often a splash screen (`SplashScreenBitmap`) or loader stub. The orchestrator must poll (with a bounded loop, e.g. 100 ms intervals up to 5000 ms) using `EnumWindows` until a window with class `Framework::CFrame` and non-zero dimensions is visible.

---

## 3. Microsoft OneNote Specifics

Microsoft OneNote behaves differently from standard SDI (Single Document Interface) applications:

| Attribute | OneNote Desktop (M365 / Office 16) | OneNote for Windows 10 (UWP) |
| :--- | :--- | :--- |
| **Executable** | `ONENOTE.EXE` | `ApplicationFrameHost.exe` hosting package |
| **Window Class** | `Framework::CFrame` | `ApplicationFrameWindow` |
| **Child Canvas Class** | `OneNote::DocumentCanvas` | `Windows.UI.Core.CoreWindow` |
| **Lifecycle Status** | Primary active Microsoft codebase | Deprecated (support concluded) |
| **COM Automation** | **Full Support** (`OneNote.Application`) | None (Protocol URI only) |
| **Multi-Window Mode** | Multiple full windows, SideNotes, Docked | Single instance / tabbed views |
| **Full Page Presentation** | F11 / COM `Window.FullPageView = true` | Full Screen button / F11 |

### 3.1 The OneNote COM Object Model

OneNote Desktop exposes a rich COM interface registered as `OneNote.Application.15` or `OneNote.Application.16` (TypeLib: `Microsoft OneNote 15.0/16.0 Type Library`).

Using Python (`win32com.client`) or C#, OneNote windows can be managed deterministically:

```python
import win32com.client

# Connect to running instance or launch OneNote automatically
on_app = win32com.client.Dispatch("OneNote.Application")

# Inspect open windows
for window in on_app.Windows:
    hwnd = window.WindowHandle  # Returns native HWND (unsigned long)
    is_active = window.Active
    is_side_note = window.SideNote
    is_full_page = window.FullPageView
    current_page = window.CurrentPageId

    # Example: Set window to presentation Full Page view
    window.FullPageView = True
```

**Architectural Benefit:** `window.WindowHandle` eliminates all ambiguity around window class enumeration, splash screens, or matching window title strings.

### 3.2 Command-Line Protocol URIs

OneNote registers the `onenote:` protocol. Calling:
```shell
start onenote:https://d.docs.live.net/.../Notebook/Section.one#Page
```
or
```shell
start onenote:///C:\Path\To\Section.one#Page
```
will launch or focus OneNote directly to that notebook page. However, protocol launching alone **does not specify the target monitor**. Combining a protocol launch with subsequent COM or Win32 monitor placement achieves the desired classroom workflow.

---

## 4. Established GitHub Projects & Open-Source Comparison

| Project / Tool | Primary Licence | Maintenance Status | Technical Architecture | Strengths | Fatal Flaws / Limitations for Classroom Companion | Primary Source Link |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Microsoft PowerToys (FancyZones & Workspaces)** | MIT License | Very Active (Microsoft Open Source) | Native C++ Win32 DLL, `SetWinEventHook`, CCD API (`QueryDisplayConfig`), monitor instance paths `\\?\DISPLAY#...` | Production-grade display topology handling; highly reliable DPI scaling; robust multi-monitor zone snapping. | Monolithic installer (>500 MB); FancyZonesCLI is diagnostic-only and does not expose a headless window placement REST/socket API. Workspaces launches full app sets, causing visual jumping. | [microsoft/PowerToys](https://github.com/microsoft/PowerToys) |
| **AutoHotkey (AHK v2)** | GNU GPLv2 | Active (Steve Gray / Lexikos) | Standalone C++ interpreter running custom `.ahk` scripts; Win32 wrappers (`WinMove`, `WinActivate`, `SysGet`). | Rapid script prototyping; built-in focus stealing tricks (`AttachThreadInput` / Alt-key pulse inside `WinActivate`). | External runtime binary dependency (`AutoHotkey.exe`); relies on volatile monitor indexes (`SysGet, Mon, MonitorWorkArea, 2`); GPLv2 licence restrictions; script race conditions without event hooks. | [AutoHotkey/AutoHotkey](https://github.com/AutoHotkey/AutoHotkey) |
| **DisplayMagician** | GNU GPLv3 | Active (Terry MacDonald) | C# / .NET 8 desktop utility; Windows CCD APIs (`QueryDisplayConfig`, `SetDisplayConfig`), vendor APIs (NVIDIA/AMD). | Industry standard for capturing, saving, and switching multi-monitor display layouts, resolutions, HDR, and app shortcuts. | Designed as a heavyweight gaming profile switcher; GPLv3 licence; requires full .NET runtime; lacks a lightweight micro-service IPC for single-window movement. | [terrymacdonald/DisplayMagician](https://github.com/terrymacdonald/DisplayMagician) |
| **komorebi** | **PolyForm Strict 1.0.0** (Non-commercial) | Active (LGUG2Z) | Rust Win32 window manager using WinEvents (`SetWinEventHook`) and named pipe IPC (`komorebic.exe`). | Extremely fast; full socket/CLI interface to move windows to specific monitors; excellent window management. | **Fatal Licence Restriction:** PolyForm Strict 1.0.0 strictly prohibits commercial and workplace use without purchasing commercial licences. Intrusive full-desktop tiling model. | [LGUG2Z/komorebi](https://github.com/LGUG2Z/komorebi) |
| **PyWinCtl & PyMonCtl** | BSD 3-Clause | Active (Kalmat) | Python wrappers using `ctypes` directly calling `user32.dll` and `shcore.dll`. | Permissive BSD licence; clean Python API (`win.moveTo(x, y)`, `win.maximize()`); multi-monitor geometry support. | Relies on GDI/WMI and lacks full CCD target device path persistence; can struggle with complex mixed-DPI scaling across negative coordinates. | [Kalmat/PyWinCtl](https://github.com/Kalmat/PyWinCtl) |
| **pywin32 / ctypes Native Implementation** | PSF / MIT | Standard Python Ecosystem | Direct P/Invoke bindings into `user32.dll`, `gdi32.dll`, and COM `IDispatch`. | Zero external binary dependencies; 100% control over error handling, retries, and receipts; seamless integration with `tools/compose/`. | Requires explicit C-struct declarations (`WINDOWPLACEMENT`, `MONITORINFOEXW`) and manual memory management in Python. | [mhammond/pywin32](https://github.com/mhammond/pywin32) |
| **NirCmd / MultiMonitorTool** | Proprietary Freeware | Mature / Infrequent (NirSoft) | Closed-source Win32 C utility (`nircmd.exe win move ...`). | Single portable binary; scriptable via command line. | Closed-source; commercial redistribution terms; non-deterministic window finding; no structured JSON receipt. | [NirSoft MultiMonitorTool](https://www.nirsoft.net/utils/multi_monitor_tool.html) |

---

## 5. Home vs Work Monitor Identification Strategy

A core failure mode in multi-monitor setups is the assumption that monitor ordering is static.

### Why Monitor Indexing Fails
- At home, a teacher may use a Surface Laptop connected to an external 27-inch HDMI monitor. The external monitor is assigned `Display 2`.
- At school, the teacher plugs into a USB-C dock connected to a Promethean interactive board and an overhead projector. Windows may assign the Promethean board `Display 3` on Monday, but if the dock is plugged in after booting on Tuesday, Windows may assign it `Display 2`.
- Attempting to target "Monitor 2" results in OneNote appearing on the wrong screen (or the teacher's private laptop screen during a presentation).

### The Recommended Hardware Fingerprinting Architecture

In alignment with **Rule 1 (Strict Environment Binding)** in [`GEMINI.md`](../../GEMINI.md), monitor configuration must be treated as an atomic profile bound to the environment:
$$\text{DisplayTarget} = \{\text{EnvironmentID}, \text{Role}, \text{ManufacturerID}, \text{ProductCodeID}, \text{FriendlyNamePattern}, \text{FallbackResolution}\}$$

```
                Incoming Move Request: Role="Classroom Display"
                                      │
                 Check Environment Profile (ENV_WORK / ENV_HOME)
                                      │
                 Enumerate Active CCD Paths (QueryDisplayConfig)
                                      │
                  Extract EDID (Manufacturer, ProductCode, Name)
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
        Exact Hardware Match?                         Fallback Match?
      (e.g. "PRM" / 0x1234)                        (Resolution / Aspect)
               │                                             │
               ├─────────────────────────────────────────────┘
               ▼
     Resolve Live HMONITOR & rcWork Coordinates
               │
     Execute Window Move & Maximise Sequence
               │
     Generate Audited JSON Receipt
```

#### Step-by-Step Resolution Algorithm:
1. **Query Active Topology:** Call `QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS)` to obtain all physically active display outputs.
2. **Match Target Role:**
   - At `ENV_WORK`, search for EDID manufacturer code matching known school hardware (e.g. `PRM` for Promethean, `SMT` for SMART Technologies, `EPS` for Epson, or user-selected friendly name substring).
   - At `ENV_HOME`, search for the secondary desktop display (e.g. `SAM` / `Odyssey G5`, `DEL` / `Dell U2719D`).
3. **Handle Duplicates (Identical Monitors):** If the teacher has two identical Dell monitors at home, distinguish them using the unique Windows `monitorDevicePath` or the relative coordinate position (e.g. `Position.Left < 0`).
4. **Fallback and Safety Bailout:** If the designated display is disconnected or in deep sleep (DisplayPort power down), **refuse silent movement**. Do not move OneNote off-screen into a non-existent virtual space. Return an explicit status: `{"status": "error", "error": "TARGET_MONITOR_OFFLINE"}`.

---

## 6. Failure Modes, Traps, and Mitigations

| Failure Mode | Root Cause | Impact | Mitigation / Defensive Architecture |
| :--- | :--- | :--- | :--- |
| **Negative Virtual Coordinates** | Secondary monitor positioned to the left or above primary display has negative $(x, y)$. | Naive coordinate validation clamps $x < 0$ to $0$, snapping window to primary monitor. | Allow signed integers for all window coordinates; validate bounds against `UnionRect` of all active monitors. |
| **DPI Scaling Distortion** | Moving from 150% laptop display to 100% classroom board. | Window size explodes to 150% of screen or renders blurry text. | Host process sets `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`. Window is moved and maximised so DWM recomputes native client DPI. |
| **The Maximised Window Bug** | Calling `SetWindowPos` directly on a maximised window. | Window snaps back to original monitor when unmaximised, or renders with broken frame borders. | Inspect `WINDOWPLACEMENT.showCmd`. If `SW_SHOWMAXIMIZED`, call `ShowWindow(SW_RESTORE)` $\rightarrow$ position to `rcWork` $\rightarrow$ `ShowWindow(SW_SHOWMAXIMIZED)`. |
| **Minimised Window Lock** | Window is minimised to taskbar (`SW_SHOWMINIMIZED`). | `SetWindowPos` places window at $(-32000, -32000)$ without activating it. | Call `ShowWindow(hWnd, SW_RESTORE)` before attempting coordinate movement. |
| **Taskbar Overlap** | Positioning window using full monitor bounds (`rcMonitor`) instead of workspace bounds (`rcWork`). | Window title bar or bottom controls are hidden beneath the Windows Taskbar. | Always use `MONITORINFO.rcWork` for window positioning unless explicit exclusive fullscreen is requested. |
| **Splash Screen Capture Race** | `EnumWindows` catches OneNote's splash screen during launch. | Splash screen is moved; main document window opens later on the default display. | Filter out windows without `WS_VISIBLE` or with `WS_EX_TOOLWINDOW`; require window width $> 600\text{ px}$ and class `Framework::CFrame`. |
| **Foreground Lockout (Silent Failure)** | Windows blocks `SetForegroundWindow` from background service. | Target window stays behind existing windows; taskbar icon flashes orange. | Use `AttachThreadInput` queue bridging or pulse `VK_MENU` prior to activation; verify outcome with `GetForegroundWindow() == targetHwnd`. |
| **Multiple OneNote Windows** | Teacher has multiple notebooks or SideNotes / Quick Notes open. | Arbitrary window is moved, displacing a private note to the public screen. | Enumerate all OneNote windows; ignore windows where `SideNote == TRUE`; select the most recently focused main window. |
| **Sleeping / Disconnected Display** | DisplayPort link drops when monitor sleeps; USB-C dock unplugged. | Window moved to "phantom" coordinates, becoming inaccessible to the teacher. | Validate monitor handle via `GetMonitorInfoW` before moving; abort and return actionable error if handle is invalid. |

---

## 7. Actionable Architectural & Test Recommendations

### 7.1 Proposed System Architecture (Windows Host Service)

Rather than introducing external third-party software (AutoHotkey, PowerToys, or DisplayMagician), the Windows companion should implement a dedicated, lightweight Python module: `tools/compose/window_monitor_manager.py`.

```
     ESP32 MacroPad                     Windows Companion Host Service
   ┌─────────────────┐                 ┌────────────────────────────────────────────────────────┐
   │ Button Press    │                 │ tools/compose/hotkey_state.py                          │
   │ (e.g. F18 chord)│───[BLE HID]────►│ - Detects key combination                              │
   └─────────────────┘                 │ - Dispatches Action                                    │
                                       └──────────────────────────┬─────────────────────────────┘
                                                                  │
                                                                  ▼
                                       ┌────────────────────────────────────────────────────────┐
                                       │ tools/compose/window_monitor_manager.py                │
                                       │                                                        │
                                       │ 1. Resolve Target Display:                             │
                                       │    QueryDisplayConfig / WmiMonitorID                   │
                                       │    Match "Classroom Display" profile                   │
                                       │                                                        │
                                       │ 2. Resolve / Launch Target Application:                │
                                       │    Find ONENOTE.EXE (Framework::CFrame)                │
                                       │    Or spawn process and wait for input idle            │
                                       │                                                        │
                                       │ 3. Restore, Move, and Maximise:                        │
                                       │    Unmaximise -> Move to target rcWork -> Maximise     │
                                       │                                                        │
                                       │ 4. Verified Foreground Activation:                     │
                                       │    AttachThreadInput -> SetForegroundWindow            │
                                       │                                                        │
                                       │ 5. Audit Receipt:                                      │
                                       │    Return JSON receipt to Companion UI                 │
                                       └────────────────────────────────────────────────────────┘
```

### 7.2 Implementation Checklist for `window_monitor_manager.py`

1. **Per-Monitor V2 Initialization:** Ensure `ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)` is executed at module load.
2. **Display Enumerator (`get_display_topology`):**
   - Call `EnumDisplayMonitors` to collect all `HMONITOR` handles and `rcWork` rectangles.
   - Cross-reference with `WmiMonitorID` or `QueryDisplayConfig` to populate friendly names and EDID codes.
3. **Window Finder (`find_application_window`):**
   - For OneNote: Try COM connection (`win32com.client.Dispatch("OneNote.Application")`). If successful, extract `app.Windows[i].WindowHandle`.
   - Fallback: Enumerate top-level windows matching executable `ONENOTE.EXE` and class `Framework::CFrame`.
4. **Window Mover (`place_window_on_monitor`):**
   - Execute the 3-step restore $\rightarrow$ `SetWindowPos` $\rightarrow$ `ShowWindow(SW_SHOWMAXIMIZED)` procedure.
5. **Foreground Verifier (`activate_window`):**
   - Execute `AttachThreadInput` bridging as established in `tools/compose/focus_tracker.py`.
   - Assert `GetForegroundWindow() == target_hwnd`.
6. **Receipt Generation:** Return a structured receipt dictionary:
   ```json
   {
     "status": "success",
     "application": "OneNote",
     "hwnd": 131248,
     "target_monitor": {
       "role": "classroom_display",
       "friendly_name": "Promethean ActivPanel",
       "edid_manufacturer": "PRM",
       "work_area": [ -1920, 0, 0, 1080 ]
     },
     "placement": "maximized",
     "foreground_verified": true,
     "duration_ms": 142
   }
   ```

---

## 8. Test Matrix and Verification Plan

To satisfy project governance ([`AGENTS.md`](../../AGENTS.md)), testing must proceed through strict, isolated verification gates prior to any physical handheld integration:

### Gate 1: Synthetic Window Mover Unit Tests (Desktop Only)
- **Harness:** Create a lightweight Python test script launching a standard Tkinter/PyQt window (`"Test Target Window"`).
- **Test Cases:**
  1. Target window in normal (restored) state $\rightarrow$ move to secondary monitor $\rightarrow$ verify `GetWindowRect`.
  2. Target window maximised on Monitor 1 $\rightarrow$ move to Monitor 2 $\rightarrow$ verify maximised bounds match Monitor 2's `rcWork`.
  3. Target window minimised $\rightarrow$ trigger move $\rightarrow$ verify window is restored and visible on target monitor.
  4. Target display disconnected $\rightarrow$ trigger move $\rightarrow$ verify graceful refusal with error code (`TARGET_MONITOR_NOT_FOUND`).

### Gate 2: OneNote Multi-Window Integration Tests (Home Setup)
- **Environment:** 2-monitor home setup (e.g. Laptop + Samsung Odyssey G5).
- **Test Cases:**
  1. OneNote closed $\rightarrow$ trigger move shortcut $\rightarrow$ verify OneNote launches, splash screen is ignored, and main window appears maximised on Monitor 2.
  2. OneNote already open on Monitor 1 $\rightarrow$ trigger move $\rightarrow$ verify instantaneous move without restarting process.
  3. OneNote has a Quick Note / SideNote floating $\rightarrow$ trigger move $\rightarrow$ verify main notebook window is moved, floating note is untouched.
  4. Foreground focus test $\rightarrow$ click desktop/browser $\rightarrow$ trigger move $\rightarrow$ verify OneNote takes active keyboard focus.

### Gate 3: Work / Classroom Multi-Monitor Acceptance
- **Environment:** School laptop docked to USB-C multi-monitor setup (e.g. Laptop + Classroom Interactive Display + HDMI Projector).
- **Test Cases:**
  1. Cold boot dock connection $\rightarrow$ verify hardware fingerprint accurately selects the classroom display regardless of assigned Windows display index.
  2. Monitor sleep / wake cycle $\rightarrow$ let displays sleep for 10 minutes $\rightarrow$ wake up $\rightarrow$ verify shortcut moves OneNote reliably without coordinates drifting off-screen.
  3. Resolution / DPI divergence $\rightarrow$ verify text scaling and UI elements remain sharp on the classroom board without blurry scaling artefacts.

---

## 9. Conclusion

Implementing monitor-aware window placement entirely on the Windows companion host via native Win32/COM APIs is technically proven, architecturally compliant with project rules, and avoids the licensing traps and binary bloat of external tools like AutoHotkey, PowerToys, or Komorebi.

The existing codebase already contains the key foundational blocks:
- `tools/compose/hotkey_state.py` for keyboard trigger edge-detection.
- `tools/compose/focus_tracker.py` for `AttachThreadInput` foreground activation.
- `tools/compose/board_candidate.py` for display selection concepts.

Extending these capabilities with a persistent CCD/WMI hardware fingerprinting module will provide deterministic, one-touch OneNote presentation for the classroom companion.
