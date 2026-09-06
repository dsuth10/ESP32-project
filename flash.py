"""
ESP32-S3 (ES3C28P 2.8" Touch Display) Flashing Script
Usage:
    python flash.py widgets      # Flash LVGL Widgets Interactive Touch Demo
    python flash.py music        # Flash LVGL Music Player Demo
    python flash.py benchmark    # Flash LVGL Benchmark Demo
    python flash.py stress       # Flash LVGL Stress Test Demo
    python flash.py xiaozhi      # Flash Xiaozhi AI Demo
"""

import sys
import subprocess
import os

BIN_DIR = os.path.join(os.path.dirname(__file__), "bin")
DEFAULT_PORT = "COM5"

BIN_MAP = {
    "widgets": os.path.join(BIN_DIR, "lv_demo_widgets.bin"),
    "music": os.path.join(BIN_DIR, "lv_demo_music.bin"),
    "benchmark": os.path.join(BIN_DIR, "lv_demo_benchmark.bin"),
    "stress": os.path.join(BIN_DIR, "lv_demo_stress.bin"),
    "xiaozhi": os.path.join(BIN_DIR, "common.bin"),
}

def flash(bin_name="widgets", port=DEFAULT_PORT):
    if bin_name not in BIN_MAP:
        print(f"Unknown target '{bin_name}'. Available: {list(BIN_MAP.keys())}")
        sys.exit(1)

    bin_path = BIN_MAP[bin_name]
    if not os.path.exists(bin_path):
        print(f"Error: Binary file not found at {bin_path}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "esptool",
        "--port", port,
        "--baud", "921600",
        "--chip", "esp32s3",
        "write_flash",
        "--flash_mode", "dio",
        "--flash_size", "16MB",
        "--flash_freq", "80m",
        "0x0000",
        bin_path
    ]

    print(f"Flashing '{bin_name}' to {port} from {bin_path}...")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\nSuccessfully flashed {bin_name} to {port}!")
    else:
        print(f"\nFlashing failed with exit code {res.returncode}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "widgets"
    port = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORT
    flash(target, port)
