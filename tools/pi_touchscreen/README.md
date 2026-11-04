# Raspberry Pi Teacher Touchscreen Deck

Touch-first teacher podium control client and desktop simulator for the Teaching Board.

Designed for 7" to 10" touchscreens (800×480 to 1280×800) attached to a Raspberry Pi 3 Model B Rev 1.2 (`companionpi`) running Raspberry Pi OS Lite 64-bit (Debian 13 Trixie), and for desktop windowed simulation on Windows at home.

---

## 1. Running Home Simulator Mode on Windows

You can run and test the complete touchscreen interface on your Windows development laptop without the physical Raspberry Pi present:

1. **Start the Windows Companion & Teacher Deck API:**
   Ensure the Teacher Deck service is running (default port `8790`):
   ```powershell
   & .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/teacher_deck_server.py
   ```

2. **Launch the Touchscreen Client in Windowed Mode:**
   ```powershell
   & .local/teaching-board-renderer-env/Scripts/python.exe tools/pi_touchscreen/deck_ui.py --windowed --url http://127.0.0.1:8790 --token "<YOUR_SECRET_TOKEN>"
   ```

3. **Verify the Layout:**
   - The simulator opens in a fixed 1024×600 window.
   - You can test image candidate staging, clear-space image placement, page navigation, board freezing, and classroom application switching (OneNote, Word, Chrome).

---

## 2. Deploying on the Raspberry Pi 3B at School

The physical Raspberry Pi 3B lives permanently at school at the teacher's podium.

### Minimal Appliance Package Prerequisites
To keep memory usage well within the Pi 3B's 1 GB RAM boundary (~60–90 MB total footprint, avoiding Chromium OOM crashes), run on Raspberry Pi OS Lite with the minimal Wayland kiosk compositor:

```bash
sudo apt update
sudo apt install -y cage python3-pyside6.qtwidgets python3-pip
```

### Configuration & Security Boundary
Per project safety rules, **never commit credentials, tokens, or school Wi-Fi passwords to Git**.

1. Copy `tools/pi_touchscreen/config.example.json` to an untracked local path on the Pi:
   ```bash
   mkdir -p ~/.config/companion-touchscreen
   cp tools/pi_touchscreen/config.example.json ~/.config/companion-touchscreen/config.json
   ```
2. Edit `~/.config/companion-touchscreen/config.json` with the local companion URL and your token:
   ```json
   {
     "url": "http://companion-pc.local:8790",
     "token": "YOUR_ACTUAL_TOKEN",
     "windowed": false,
     "kiosk": true,
     "width": 1024,
     "height": 600,
     "poll_ms": 1000
   }
   ```
3. Store any private network scripts, SSH identities, and receipts exclusively inside `.local/raspberry-pi/`.

### School Network Connectivity & Wi-Fi Isolation Fallbacks
Many school Wi-Fi networks enforce Access Point (AP) client isolation, preventing devices on the same Wi-Fi subnet from establishing direct TCP connections.

If `companionpi` cannot connect to `companion-pc.local:8790`:
1. **Tailscale Fallback (Recommended):**
   Connect both the teacher laptop and the Pi to the shared private Tailscale tailnet. Configure the Pi's `config.json` URL to point to the laptop's Tailscale IP or MagicDNS hostname (e.g. `http://100.x.y.z:8790`).
2. **Direct Ethernet Patch / USB Gadget:**
   Connect a short Cat6 Ethernet patch lead directly between the laptop and Pi, or configure USB Ethernet gadget mode on the Pi.

### Systemd Appliance Service
Enable automatic start on boot so the touchscreen launches directly into the podium deck:

```bash
sudo cp tools/pi_touchscreen/systemd/companion-touchscreen.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable companion-touchscreen.service
sudo systemctl start companion-touchscreen.service
```

If the companion laptop is asleep or disconnected, the deck displays an amber `"Waiting for Classroom PC…"` status banner until the companion comes online.
