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

## Live result

The approved candidate was flashed through the scoped route. esptool verified
its write, and an independent application read-back matched SHA-256
`7a8c95b8ada30bcc97be3ab9b52f3de64488d7bb7ddbd62f2bab12c26260c59b`.
The boot/settings prefix and partition table were unchanged. The registry bytes
and stable write lock were retained; no identity or fingerprint was edited.

After restart, the actual S3 completed the identity-checked `page7-v1` handshake
and acknowledged page **7**. The desktop reported **USB: linked** and the device
acknowledged live display state **Image ready / Kangaroo targeted addition**.
One initial handshake timed out while the board was starting; the display link's
bounded reconnect succeeded. This repeated no generation, insertion or flash.

The user confirmed **“Layout visible and Library works”**. This is user-reported
physical evidence, distinct from automated tests and the serial page/status
acknowledgement. Full end-to-end Compose, Dictate, Images and Paste Ready checks
on this candidate remain open; prior home acceptance is not automatically
transferred to a new firmware build.

For a controlled follow-up, the desktop was placed on Compose & Dictate before
the user pressed the physical Library button. The user then confirmed:
**“Yes, it switches to Image library”**. The physical tab-switch check therefore
passes independently of the library having already been visible.

An image had been explicitly queued before the trial. Its durable undispatched
queue was preserved and restored with the same version and insertion job. The
restart displayed its preview without inserting it, generating another image or
creating a replacement insertion job. Startup never resumes uncertain/inserting
jobs. Queue preservation has a regression test.

Final desktop core selection: **345 passed, one Windows symlink skip**; both
end-to-end cases passed separately. The two whole-app native layout cases passed
in fresh processes. Earlier combined runs encountered intermittent Windows
directory-rename denials in backup/installation tests; the affected isolated
selections passed. The 39 board guard/recovery tests and 57 focused
feedback/writing tests passed; these overlap other selections and are not added
into a claimed total. Physical recovery was not needed or performed.

Actual flash/identity/recovery details, original flash image, candidate binaries,
source/tool snapshots, queue identity, protected settings and error/transition
events remain private in `.local`. The desktop contains exactly one active home
companion and one existing home ledger. No extra paid image request was made.

PC microphone handling is retained. Handheld audio, wireless return feedback,
cross-location services, broader device/classroom acceptance and a stable release
remain separate gates. The device is left on the approved trial for the user's
live inspection, with its original firmware recoverable and registry locked.
