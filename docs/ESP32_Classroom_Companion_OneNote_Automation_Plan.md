# ESP32 Classroom Companion & OneNote Automation Plan

## Purpose

This document proposes an extension of the existing **ESP32 Voice Satellite & MacroPad** project into a more capable **Classroom Companion / Teacher Console**.

The core idea is to move beyond simple Bluetooth keyboard shortcuts and allow the ESP32 to trigger **semantic host actions** on a connected Windows computer.

Examples include:

- Open OneNote.
- Navigate directly to a particular notebook, section or page.
- Move OneNote to a particular monitor.
- Maximise or enter a presentation-style view.
- Launch purpose-built classroom tools such as:
  - an interactive world map;
  - a whiteboard;
  - a timer;
  - a number line;
  - a Cartesian plane;
  - a protractor;
  - a browser resource.
- Trigger multi-step **lesson scenes** consisting of several coordinated actions.

The ESP32 should remain a lightweight control surface. Complex automation should be executed by a Windows companion service.

---

# 1. Current Project Architecture

The current project already provides most of the infrastructure required.

The ESP32 currently operates as:

- a Bluetooth Low Energy HID macro keyboard;
- a Hermes voice satellite;
- a Wi-Fi-connected device;
- a host-aware device with environment profiles;
- a telemetry dashboard;
- a local storage interface.

The current macro system supports action types such as:

```cpp
ACTION_MEDIA
ACTION_KEY_COMBO
ACTION_STRING
ACTION_VOICE
```

Standard custom keys are therefore primarily translated into Bluetooth HID actions.

For example:

```text
ESP32 Button
    ↓
ACTION_KEY_COMBO
    ↓
BLE HID
    ↓
Windows receives Ctrl+C, Win+Shift+S, etc.
```

This model is ideal for straightforward shortcuts.

It is not ideal for reliable workflows such as:

```text
Open OneNote
→ open a specific notebook
→ navigate to a specific page
→ move the OneNote window to another monitor
→ maximise it
→ enter Full Page view
```

Trying to implement these workflows as simulated keyboard and mouse actions would be fragile.

---

# 2. Proposed Architectural Change

Introduce a new action type:

```cpp
ACTION_HOST_COMMAND
```

Rather than simulating a complicated sequence of keystrokes, the ESP32 would send a semantic command to a Windows companion application.

For example:

```text
onenote.world_map
```

or:

```text
classroom.cartesian_plane
```

The ESP32 does not need to know how that command is performed.

Its responsibility is simply:

```text
Button Press
    ↓
Send Command ID
    ↓
Receive Success / Failure
```

The Windows computer becomes responsible for executing the requested action.

---

# 3. Proposed High-Level Architecture

```text
                         ESP32
                           │
                  Wi-Fi Host Commands
                           │
                           ▼
              ┌────────────────────────┐
              │ Classroom Companion    │
              │ Windows Host Service   │
              └────────────┬───────────┘
                           │
             ┌─────────────┼───────────────┐
             │             │               │
             ▼             ▼               ▼
       OneNote Provider  Classroom      Windows
                         Tools          Provider
             │             │               │
       COM / Add-in     Local Web      Win32 APIs
             │           App               │
             ▼                             ▼
       OneNote Pages                 Window / Monitor
                                     Management
```

The Windows companion becomes the orchestration layer.

The ESP32 remains the control surface.

---

# 4. Why the Windows Host Should Perform the Automation

The ESP32 currently works very well as a BLE HID keyboard.

That functionality should remain.

However, state-dependent workflows should not be implemented as long keyboard macros.

For example, this is fragile:

```text
Win key
→ type OneNote
→ Enter
→ wait
→ send keyboard shortcut
→ wait
→ click something
→ move window
→ maximise
```

The result depends on:

- timing;
- focus;
- the current desktop state;
- whether OneNote is already running;
- which monitor currently contains the window;
- pop-ups or notifications;
- changes to the OneNote UI.

A host-side application can instead inspect and control the actual state.

For example:

```text
Receive: onenote.world_map

    ↓

Is OneNote running?

    ├─ No → Launch OneNote
    └─ Yes → Reuse existing instance

    ↓

Navigate directly to World Map page

    ↓

Obtain OneNote window handle

    ↓

Find classroom display

    ↓

Move window to classroom display

    ↓

Maximise

    ↓

Enable Full Page view

    ↓

Return SUCCESS
```

This is much more deterministic.

---

# 5. OneNote Integration

OneNote is a strong first target because the Windows desktop application exposes automation interfaces that can be used to navigate its content and manipulate its windows.

A OneNote integration layer could support:

- opening OneNote;
- finding or reusing an existing OneNote instance;
- navigating to a notebook;
- navigating to a section;
- navigating to a page;
- potentially navigating to specific objects or locations inside a page;
- obtaining the OneNote window handle;
- changing view modes;
- bringing a OneNote window to the foreground.

The existing OneNote add-in project can potentially become the **OneNote Provider** for the broader Classroom Companion system.

That avoids forcing all classroom functionality into OneNote itself.

---

# 6. Example: World Map OneNote Command

The ESP32 could contain a button labelled:

```text
WORLD MAP
```

The firmware might associate it with:

```text
onenote.world_map
```

The ESP32 could send a request resembling:

```json
{
  "action": "onenote.world_map"
}
```

The Windows companion could contain the configuration:

```text
Command: onenote.world_map

Application: OneNote
Notebook: Geography
Section: Mapping
Page: World Map
Display: Classroom Display
Window State: Maximised
OneNote View: Full Page
Bring to Front: Yes
```

The host performs the complete workflow.

---

# 7. Multi-Monitor Support

Monitor placement should be controlled by Windows rather than by emulated keyboard shortcuts.

The companion should maintain named monitor identities such as:

```text
Teacher Monitor
Classroom Display
Interactive Panel
Projector
```

A command could therefore specify:

```text
Display: Classroom Display
```

The host application would:

1. enumerate Windows displays;
2. identify the requested monitor;
3. obtain the target application's window handle;
4. move the window into that monitor's bounds;
5. resize or maximise it.

This allows commands such as:

```text
Open OneNote on teacher monitor
Open world map on projector
Open timer on interactive panel
```

---

# 8. Classroom Tools Should Not All Live Inside OneNote

OneNote is an excellent destination for:

- lesson notes;
- handwritten content;
- images;
- student work;
- PDFs;
- worksheets;
- diagrams;
- annotations.

However, some classroom activities are better implemented as interactive applications.

The world-map example is a good case.

A purpose-built map could provide:

- zoom;
- pan;
- political layer;
- physical layer;
- satellite layer;
- country labels;
- latitude and longitude;
- country search;
- location search;
- drawing;
- highlighting;
- annotation;
- erase;
- clear;
- screenshots;
- export to OneNote.

Trying to recreate all of that inside OneNote would unnecessarily constrain the design.

The Classroom Companion should therefore be able to launch both:

```text
OneNote resources
```

and:

```text
Purpose-built classroom applications
```

---

# 9. Potential Classroom Tool Library

A future classroom toolkit could contain modules such as:

| Tool | Possible Function |
|---|---|
| World Map | Zoomable and annotatable map |
| Whiteboard | Blank pen/highlighter canvas |
| Timer | Full-screen timer or countdown |
| Number Line | Interactive number line |
| Cartesian Plane | Plot points and coordinates |
| Protractor | Angle demonstration |
| Ruler | Measurement demonstration |
| Clock | Analogue/digital time teaching |
| Fraction Wall | Interactive fraction comparison |
| Place Value | Manipulable place-value blocks |
| Hundreds Grid | Number-pattern exploration |
| Probability Tool | Dice, spinner and random events |
| Browser | Open a defined lesson resource |
| Media | Open a particular video or audio resource |

These tools could be built as a local web application.

A WebView2-based Windows shell would be a strong option because the educational tools could continue to use familiar HTML, CSS and JavaScript.

---

# 10. Classroom Companion Command Model

The Windows application should maintain a registry of commands.

Example:

```yaml
commands:

  onenote.world_map:
    provider: onenote
    notebook: Geography
    section: Mapping
    page: World Map
    monitor: classroom
    maximise: true
    full_page: true

  classroom.world_map:
    provider: classroom_tool
    route: /map/world
    monitor: classroom
    fullscreen: true

  classroom.timer:
    provider: classroom_tool
    route: /timer
    monitor: classroom
    fullscreen: true

  browser.lesson_video:
    provider: browser
    url: https://example.com/lesson
    monitor: classroom
```

The exact configuration format can be determined later.

JSON or YAML would both be suitable.

---

# 11. Do Not Hard-Code OneNote Page IDs into Firmware

The ESP32 should not contain:

- OneNote notebook IDs;
- OneNote page IDs;
- file paths;
- URLs;
- monitor coordinates;
- executable locations.

Instead, firmware should contain logical command IDs.

For example:

```text
ACTION_01
ACTION_02
ACTION_03
```

or:

```text
onenote.world_map
classroom.timer
classroom.whiteboard
```

The Windows host decides what these commands mean.

This has several advantages:

- ESP32 firmware does not need reflashing when lesson resources change.
- OneNote pages can be moved or replaced.
- Monitor arrangements can change.
- Different computers can map the same ESP32 command differently.
- HOME and WORK profiles can use different host behaviour.
- Commands can eventually be edited through a GUI.

---

# 12. Dynamic Button Configuration

A later phase could allow the Windows computer to send button definitions to the ESP32.

Instead of Page 4 being permanently hard-coded, the host could define:

```text
WORLD MAP
TIMER
WHITEBOARD
TODAY'S MATHS
TODAY'S ENGLISH
STUDENT WORK
```

A different lesson could dynamically change those buttons to:

```text
NUMBER LINE
FRACTIONS
PLACE VALUE
STOPWATCH
WORKED EXAMPLE
ANSWERS
```

This would turn the ESP32 into a lesson-specific control surface.

Eventually the device could receive:

- button label;
- subtitle;
- colour;
- icon;
- command ID;
- page name.

---

# 13. Lesson Scenes

The system should eventually support **scenes**.

A scene is a named collection of actions executed together.

For example:

## Geography — Mapping

```text
1. Open Geography OneNote page on Teacher Monitor.
2. Open interactive World Map on Classroom Display.
3. Maximise the map.
4. Centre map on Australia.
5. Enable country borders.
6. Enable annotation tools.
7. Load Geography ESP32 control layout.
```

A single ESP32 button could activate the entire scene.

---

## Maths — Coordinates

```text
1. Launch Classroom Tools.
2. Open /cartesian-plane.
3. Move it to Classroom Display.
4. Enter full-screen mode.
5. Configure range to -10 to +10.
6. Hide point coordinates.
7. Load coordinate controls onto ESP32.
```

The ESP32 could then expose contextual controls such as:

```text
SHOW COORDS
HIDE COORDS
NEW POINT
CLEAR
GRID
PEN
```

---

# 14. Windows Companion Providers

The companion application should be modular.

Possible providers include:

## OneNote Provider

Responsibilities:

- launch OneNote;
- navigate notebook/section/page;
- manipulate OneNote view;
- obtain OneNote HWND;
- communicate with the custom OneNote add-in if required.

---

## Classroom Tools Provider

Responsibilities:

- launch classroom tool shell;
- load a route;
- configure a tool;
- enter full screen;
- send commands to an already-running tool.

Example routes:

```text
/map/world
/timer
/whiteboard
/cartesian-plane
/number-line
/protractor
```

---

## Windows Provider

Responsibilities:

- enumerate monitors;
- resolve named monitors;
- move windows;
- resize windows;
- maximise;
- minimise;
- restore;
- focus applications;
- launch executables.

---

## Browser Provider

Responsibilities:

- launch a URL;
- reuse or isolate a browser window;
- move browser to selected display;
- potentially enter presentation/full-screen mode.

---

# 15. Proposed ESP32 Firmware Extension

Extend:

```cpp
enum ActionType {
    ACTION_MEDIA,
    ACTION_KEY_COMBO,
    ACTION_STRING,
    ACTION_VOICE,
    ACTION_HOST_COMMAND
};
```

The existing `MacroButton` definition could later gain something similar to:

```cpp
const char* commandId;
```

Conceptually:

```cpp
{
    "WORLD MAP",
    "Open Geography Map",
    ...,
    ACTION_HOST_COMMAND,
    ...,
    "onenote.world_map"
}
```

Execution becomes:

```text
ACTION_MEDIA
    → BLE HID media command

ACTION_KEY_COMBO
    → BLE HID keyboard command

ACTION_STRING
    → BLE HID text input

ACTION_HOST_COMMAND
    → authenticated HTTP host command

ACTION_VOICE
    → existing Hermes voice pipeline
```

The existing action types should remain intact.

---

# 16. Reuse Existing ESP32 Networking

The project already has:

- Wi-Fi connectivity;
- HOME and WORK environment profiles;
- authenticated requests;
- host discovery;
- host health checks;
- a Windows/Linux receiver architecture;
- telemetry;
- network retry behaviour.

This infrastructure can be extended rather than creating another independent communication stack.

One possible endpoint is:

```text
POST /command
```

Example request:

```json
{
  "action": "onenote.world_map"
}
```

Possible response:

```json
{
  "ok": true,
  "action": "onenote.world_map",
  "message": "World Map opened on Classroom Display"
}
```

Failure example:

```json
{
  "ok": false,
  "action": "onenote.world_map",
  "error": "OneNote page was not found"
}
```

---

# 17. Security Model

The command system should **not** expose arbitrary shell execution.

Do not allow requests such as:

```json
{
  "command": "powershell.exe ..."
}
```

The ESP32 should only request predefined semantic actions.

For example:

```text
onenote.world_map
classroom.timer
classroom.whiteboard
scene.geography_mapping
```

The host validates the ID against an allow-list.

Conceptually:

```python
ALLOWED_ACTIONS = {
    "onenote.world_map": ...,
    "classroom.timer": ...,
    "scene.geography_mapping": ...
}
```

Unknown commands are rejected.

The existing bearer-token security model can potentially be reused for authentication.

---

# 18. Command Acknowledgement

Unlike BLE keyboard events, host commands should return a result.

The ESP32 could display states such as:

```text
Opening...
```

then:

```text
WORLD MAP
Ready
```

or:

```text
WORLD MAP
Failed
```

Possible states:

```text
IDLE
SENDING
RUNNING
SUCCESS
FAILED
```

This makes the system much easier to troubleshoot in a classroom.

---

# 19. Recommended First Prototype

The first implementation should deliberately be small.

## Prototype Button

Create one temporary button:

```text
WORLD MAP
```

Command:

```text
onenote.world_map
```

---

## ESP32 Behaviour

On button press:

```text
POST /command

{
  "action": "onenote.world_map"
}
```

Display:

```text
Opening World Map...
```

---

## Windows Host Behaviour

The host should:

1. receive the command;
2. validate the command ID;
3. determine whether OneNote is running;
4. launch OneNote if necessary;
5. navigate to one predefined test page;
6. obtain the relevant OneNote window;
7. identify the configured classroom monitor;
8. move the OneNote window to that monitor;
9. maximise the window;
10. enter Full Page view if supported;
11. bring the window to the foreground;
12. return success to the ESP32.

---

## Prototype Success Criteria

The prototype passes when one ESP32 button can repeatedly perform:

```text
Button Press
    ↓
Specific OneNote Page
    ↓
Correct Monitor
    ↓
Maximised
    ↓
Ready for Teaching
```

without:

- manual mouse interaction;
- keyboard timing tricks;
- hard-coded screen coordinates;
- ESP32 reflashing when the OneNote page changes.

---

# 20. Suggested Development Sequence

## Stage 1 — Host Command Foundation

Add:

```text
ACTION_HOST_COMMAND
```

Implement:

```text
POST /command
```

Support one test command:

```text
system.test
```

Confirm:

```text
ESP32 → Windows → acknowledgement
```

---

## Stage 2 — Windows Application Control

Implement:

- process detection;
- process launch;
- window enumeration;
- foreground control;
- monitor enumeration;
- named monitor configuration;
- move window;
- maximise window.

Test with a simple application before OneNote.

---

## Stage 3 — OneNote Provider

Implement:

- locate OneNote;
- launch OneNote;
- navigate to known page;
- retrieve OneNote window;
- Full Page view;
- monitor placement.

Create:

```text
onenote.world_map
```

---

## Stage 4 — Command Configuration

Move command definitions outside source code.

Example:

```text
commands.json
```

Allow page destinations and monitor choices to be changed without rebuilding either the ESP32 or companion.

---

## Stage 5 — Classroom Tools Shell

Create a local classroom application.

Initial tools:

```text
World Map
Whiteboard
Timer
```

Potential stack:

```text
HTML
CSS
JavaScript
WebView2 desktop wrapper
```

---

## Stage 6 — Scene Engine

Support commands such as:

```text
scene.geography_mapping
scene.maths_coordinates
scene.english_writing
```

Each scene runs multiple actions.

---

## Stage 7 — Dynamic ESP32 Profiles

Allow the companion to send button layouts to the device.

Example:

```text
Lesson: Geography
```

ESP32 Page 4 becomes:

```text
WORLD MAP
AUSTRALIA
SATELLITE
DRAW
CLEAR
ONENOTE
```

Switch lesson:

```text
Lesson: Maths
```

ESP32 becomes:

```text
NUMBER LINE
GRID
TIMER
WHITEBOARD
ANSWERS
ONENOTE
```

---

# 21. Longer-Term Possibilities

Once the host-command layer exists, it could eventually support much more than OneNote.

Possible directions include:

- PowerPoint slide control;
- Teams controls;
- browser resource launching;
- document camera control;
- projector display management;
- classroom audio;
- OBS scenes;
- Minecraft Education launching;
- student demonstration tools;
- AI-generated lesson resources;
- screenshot-to-OneNote;
- voice-controlled classroom actions through Hermes.

A Hermes voice command might eventually trigger exactly the same actions as a physical button.

For example:

```text
"Joshua, bring up the world map."
```

Hermes could resolve that to:

```text
classroom.world_map
```

This gives the project three complementary control methods:

```text
Touchscreen buttons
Bluetooth HID
Voice
```

all routed into the same classroom automation system.

---

# 22. Recommended Architecture Decision

The preferred direction is:

> **Do not build increasingly complicated BLE keyboard macros.**

Retain BLE HID for simple universal shortcuts.

Add a semantic host-command layer for application automation.

Use:

- the **ESP32** as the physical control surface;
- the **Windows Classroom Companion** as the orchestrator;
- the **OneNote integration/add-in** as a provider;
- **purpose-built classroom tools** for interactive teaching applications.

This preserves the strengths of the current project while opening a much larger range of classroom automation possibilities.

---

# 23. Immediate Next Step

Implement one end-to-end vertical slice:

```text
ESP32 "WORLD MAP" button
        ↓
ACTION_HOST_COMMAND
        ↓
POST /command
        ↓
Windows Classroom Companion
        ↓
OneNote Provider
        ↓
Navigate to World Map page
        ↓
Move to Classroom Display
        ↓
Maximise / Full Page
        ↓
SUCCESS acknowledgement
```

Do not begin by building the full classroom-tool ecosystem.

Prove the command architecture with this one reliable workflow first.

Once that works, the same system can support every future application, lesson tool and multi-action scene.
