# Create & Paste: approved page 7 device trial

24 October 2026. The user selected the Dedicated actions design and explicitly
requested implementation and flashing to the original S3 for a live look. This
authorises a recoverable local trial, not a stable release or public publishing.

## Candidate

The 240 × 320 portrait page 7/8 (zero-based `PAGE_COMPOSE=6`) becomes **Create &
Paste**. Compose, Dictate, Images and Library have separate touch areas. Paste
Ready is a fixed full-width bottom button. Existing pages/navigation remain.

- Compose: existing F13 plus Ctrl+Alt+Shift+F9; spoken writing instruction.
- Dictate: existing F14 plus Ctrl+Alt+Shift+F10; spoken words.
- Images: F16 plus Ctrl+Alt+Shift+F8; a distinct image-request recording mode.
- Library: F17 plus Ctrl+Alt+Shift+F7; open the desktop image library once.
- Paste Ready: existing F15 plus Ctrl+Alt+Shift+F11, delivered on release.

Record controls retain tap/start, tap/finish and hold/release semantics. Their
new transition function is non-blocking, preserves the 60-second cap, stops on
BLE disconnect and coalesces extended/fallback key pairs on Windows. Holding
Library/Paste never repeats. Eleven target-compiled assertions cover gestures.
The desktop preserves queued text/images when another recording is requested.
Compose always means writing; the old session checkbox that invisibly rerouted
Compose to image requests has been replaced by an explicit Images command.

## Attached feedback

This trial uses the **connected USB cable** for a bounded display-only return
channel. Bluetooth remains the action transport. Wireless return feedback is
not implemented by this slice. Without USB feedback the established BLE controls
remain usable, and the device states that PC ready status is unavailable.

The desktop opens only an explicitly configured port, with reset lines disabled,
and checks a nonce-bound firmware handshake against the private registered S3
identity before sending feedback. There is no port scan or network listener.
Sequenced frames contain only an allowlisted state and bounded ASCII labels.
The worker never accesses Tk widgets. Malformed/stale frames are rejected; the
device clears PC status after four seconds without valid feedback.

States distinguish actual recording, processing, prepared image brief, selected
image needing review, queued text and queued reviewed image. Provider generation
still needs the desktop's explicit Generate action; no device status message
generates, inserts, configures or spends. Full writing/transcripts/credentials
are excluded. Feedback identity is stored with existing Windows DPAPI settings.

## Recovery and verification before writing

The actual 16 MiB original flash was saved privately and matched a second complete
device read. The original registration remains stable/write-locked. The new
[scoped trial route](board-upload-safety.md#scoped-s3-application-trial-and-recovery)
binds one exact candidate and writes only the application. It preserves boot,
partition/OTA, settings and filesystem data, claims writes before dispatch and
independently reads back written bytes. Recovery restores exactly the sectors
overwritten by the trial; normal NVS changes are preserved.

The existing guard's 26 tests and 13 new scoped trial/recovery tests pass. They
include complete fake-device backup → trial → recovery, wrong identity,
modified backup/candidate, unchanged boot/settings, refusal to replay and recovery
when candidate source is lost. A simulated recovery is not a physical restore.
Both full-app native layouts (720 × 640 and 920 × 740) pass with synthetic
feedback and no microphone capture or network traffic.

Live upload/read-back, device handshake and physical user observations will be
recorded after the guarded trial. Until then these remain open. PC microphone
handling is retained; handheld audio, cross-location services, wider classroom
acceptance and a stable release are separate gates. No extra paid image request
is part of this firmware/UI trial.
